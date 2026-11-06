"""Static SQL checks for the query and execute actions.

This is the first of three layers. db_engines.py runs every query inside a
database-enforced read-only transaction (PostgreSQL, MySQL) or a transaction
that is never committed (SQL Server), and the README recommends a read-only
database login, which is the only layer that cannot be bypassed by SQL text.

The checks fail closed: anything that cannot be tokenized or parsed is rejected.
"""

import re
import unicodedata
from collections import Counter
from typing import Any, List, Optional, Sequence

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError
from sqlglot.tokens import Token, TokenType

MAX_SQL_LENGTH = 100_000

# Words that must not appear as bare (unquoted) tokens. T-SQL needs the longest
# list because SQL Server runs "SELECT 1 DELETE FROM t" as two statements with
# no separator, and sqlglot parses that DELETE as a column alias.
_COMMON_WRITE_WORDS = {"INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT"}
_COMMON_FORBIDDEN_WORDS = {
    "CREATE",
    "ALTER",
    "DROP",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "COMMIT",
    "ROLLBACK",
    "SAVEPOINT",
    "EXEC",
    "EXECUTE",
}
_DIALECT_FORBIDDEN_WORDS = {
    "postgres": set(),
    "mysql": {"OUTFILE", "DUMPFILE"},
    "tsql": {
        "BEGIN",
        "CHECKPOINT",
        "DECLARE",
        "DENY",
        "USE",
        "KILL",
        "SHUTDOWN",
        "BACKUP",
        "RESTORE",
        "DBCC",
        "RECONFIGURE",
        "BULK",
        "WAITFOR",
        "OPENQUERY",
        "OPENROWSET",
        "OPENDATASOURCE",
        "SETUSER",
        "REVERT",
        "WRITETEXT",
        "UPDATETEXT",
        "ENABLE",
        "DISABLE",
        "SEND",
        "RECEIVE",
    },
}
# Only meaningful in read-only queries: INTO creates tables or writes files, SET
# starts a second T-SQL statement, and these table hints take write locks or hold
# locks until the transaction ends (SERIALIZABLE and REPEATABLEREAD as hints).
_READ_ONLY_EXTRA_WORDS = {
    "postgres": {"INTO"},
    "mysql": {"INTO"},
    "tsql": {"INTO", "SET", "UPDLOCK", "XLOCK", "TABLOCK", "TABLOCKX", "HOLDLOCK", "SERIALIZABLE", "REPEATABLEREAD"},
}

# SQL Server's reserved keywords. SQL Server never reads one of these, unquoted,
# as a name, but sqlglot accepts most of them as column aliases: it parses
# "SELECT 1 CHECKPOINT" as one SELECT while SQL Server runs CHECKPOINT as a
# second statement. A parsed name that is a reserved word therefore means the
# two parsers disagree. Left out: DISK, DUMP, LOAD, PRECISION and SECURITYAUDIT,
# which SQL Server accepts as aliases, and DEFAULT, IDENTITYCOL, ROWGUIDCOL, TOP
# and USER, which sqlglot reads as names in valid statements (SET a = DEFAULT,
# DELETE TOP (5) ...) and which cannot start a statement.
_TSQL_RESERVED_WORDS = set(
    """
    ADD ALL ALTER AND ANY AS ASC AUTHORIZATION BACKUP BEGIN BETWEEN BREAK BROWSE BULK BY CASCADE CASE CHECK
    CHECKPOINT CLOSE CLUSTERED COALESCE COLLATE COLUMN COMMIT COMPUTE CONSTRAINT CONTAINS CONTAINSTABLE CONTINUE
    CONVERT CREATE CROSS CURRENT CURRENT_DATE CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER CURSOR DATABASE DBCC
    DEALLOCATE DECLARE DELETE DENY DESC DISTINCT DISTRIBUTED DOUBLE DROP ELSE END ERRLVL ESCAPE EXCEPT
    EXEC EXECUTE EXISTS EXIT EXTERNAL FETCH FILE FILLFACTOR FOR FOREIGN FREETEXT FREETEXTTABLE FROM FULL FUNCTION
    GOTO GRANT GROUP HAVING HOLDLOCK IDENTITY IDENTITY_INSERT IF IN INDEX INNER INSERT INTERSECT INTO IS JOIN KEY
    KILL LEFT LIKE LINENO MERGE NATIONAL NOCHECK NONCLUSTERED NOT NULL NULLIF OF OFF OFFSETS ON OPEN
    OPENDATASOURCE OPENQUERY OPENROWSET OPENXML OPTION OR ORDER OUTER OVER PERCENT PIVOT PLAN PRIMARY PRINT PROC
    PROCEDURE PUBLIC RAISERROR READ READTEXT RECONFIGURE REFERENCES REPLICATION RESTORE RESTRICT RETURN REVERT
    REVOKE RIGHT ROLLBACK ROWCOUNT RULE SAVE SCHEMA SELECT SEMANTICKEYPHRASETABLE SEMANTICSIMILARITYDETAILSTABLE
    SEMANTICSIMILARITYTABLE SESSION_USER SET SETUSER SHUTDOWN SOME STATISTICS SYSTEM_USER TABLE TABLESAMPLE
    TEXTSIZE THEN TO TRAN TRANSACTION TRIGGER TRUNCATE TRY_CONVERT TSEQUAL UNION UNIQUE UNPIVOT UPDATE
    UPDATETEXT USE VALUES VARYING VIEW WAITFOR WHEN WHERE WHILE WITH WRITETEXT
    """.split()
)

# Functions with side effects that a read-only transaction does not stop, such as
# dblink opening a second connection or pg_terminate_backend ending other sessions,
# and functions that run SQL given as text (query_to_xml, ts_stat, crosstab, ...).
_FORBIDDEN_FUNCTIONS = {
    "postgres": re.compile(
        r"dblink\w*|lo_\w+|set_config|pg_notify|query_to_xml\w*|cursor_to_xml\w*"
        r"|ts_stat|ts_rewrite|crosstab\w*|connectby|xpath_table|pg_background_\w+"
        r"|pg_(terminate|cancel)_backend|pg_reload_conf|pg_rotate_logfile\w*|pg_switch_wal"
        r"|pg_create_restore_point|pg_promote|pg_logical_emit_message|pg_\w*replication_slot\w*"
        r"|pg_logical_slot_\w+|pg_replication_origin_\w+|pg_read_(binary_)?file|pg_ls_\w+|pg_stat_file"
        r"|pg_file_\w+|pg_(try_)?advisory_\w+|pg_stat_reset\w*|pg_stat_statements_reset|pg_backup_\w+"
        r"|pg_(start|stop)_backup|pg_wal_replay_\w+|pg_import_system_collations|pg_log_\w+"
        r"|pg_(restore|clear)_\w*_stats|brin_\w*summarize\w*|gin_clean_pending_list|pg_truncate_visibility_map"
    ),
    "mysql": re.compile(
        r"get_lock|release_lock|release_all_locks|load_file|sys_exec|sys_eval"
        r"|master_pos_wait|source_pos_wait|wait_for_executed_gtid_set|wait_until_sql_thread_after_gtids"
    ),
    "tsql": re.compile(r"openquery|openrowset|opendatasource|xp_\w+|sp_\w+"),
}
# Sequence functions are fine in writes but advance the sequence even when a read rolls back.
_READ_ONLY_FORBIDDEN_FUNCTIONS = re.compile(r"nextval|setval")

_READ_ROOTS = (exp.Select, exp.SetOperation, exp.Subquery)
_WRITE_ROOTS = (exp.Insert, exp.Update, exp.Delete, exp.Merge)
_NEVER_ALLOWED_NODES = (
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Into,
    exp.Set,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Execute,
    exp.Copy,
    exp.Use,
    exp.Grant,
    exp.Revoke,
    exp.LoadData,
    exp.Kill,
)
_NEVER_IN_READ_NODES = _NEVER_ALLOWED_NODES + _WRITE_ROOTS + (exp.Lock, exp.NextValueFor)

_QUOTED_TOKEN_TYPES = {t for t in TokenType if t.name.endswith("STRING")} | {TokenType.IDENTIFIER}
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_$#@]*")
_ALLOWED_WHITESPACE = {" ", "\t", "\n", "\r"}
# Control, format (zero-width, bidi), separator, surrogate, private and unassigned
# characters. SQL Server treats U+200B as whitespace while sqlglot glues it to the
# next word, which would hide a keyword from the checks below.
_REJECTED_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zs", "Zl", "Zp"}
# MySQL/MariaDB execute the contents of /*! ... */ and /*M! ... */, and optimizer
# hints (/*+ ... */) can set session variables. sqlglot treats all three as comments.
_MYSQL_EXECUTABLE_COMMENT = re.compile(r"/\*(M?!|\+)")


class SqlRejectedError(ValueError):
    """Raised when SQL is refused before it is sent to the database."""


def check_read_only_query(sql: str, dialect: str, parameters: Optional[Sequence[Any]] = None) -> None:
    """Raise SqlRejectedError unless ``sql`` is a single statement that only reads data."""
    statement = _parse_single_statement(sql, dialect, parameters, read_only=True)
    if not isinstance(statement, _READ_ROOTS):
        raise SqlRejectedError(
            f"only SELECT statements are allowed (found {_statement_kind(statement)}). "
            "Use the execute action to insert, update or delete data."
        )
    _reject_nodes(statement, _NEVER_IN_READ_NODES)


def check_write_statement(
    sql: str,
    dialect: str,
    parameters: Optional[Sequence[Any]] = None,
    allow_all_rows: bool = False,
) -> str:
    """Raise SqlRejectedError unless ``sql`` is a single INSERT, UPDATE, DELETE or MERGE.

    Returns the statement type, e.g. ``"UPDATE"``.
    """
    statement = _parse_single_statement(sql, dialect, parameters, read_only=False)
    if not isinstance(statement, _WRITE_ROOTS):
        raise SqlRejectedError(
            f"only INSERT, UPDATE, DELETE or MERGE statements are allowed (found {_statement_kind(statement)}). "
            "Use the query action to read data."
        )
    _reject_nodes(statement, _NEVER_ALLOWED_NODES)
    if not allow_all_rows:
        for node in statement.find_all(exp.Update, exp.Delete):
            if not node.args.get("where") and not node.find_ancestor(exp.Merge):
                raise SqlRejectedError(
                    f"{_statement_kind(node)} without a WHERE clause would affect every row. "
                    "Add a WHERE clause, or set allow_all_rows to true if that is intended."
                )
    return _statement_kind(statement)


def split_placeholders(sql: str) -> List[str]:
    """Split ``sql`` on %s placeholders, unescaping %% (only %s and %% are allowed)."""
    parts = [""]
    i = 0
    while i < len(sql):
        if sql[i] != "%":
            parts[-1] += sql[i]
            i += 1
            continue
        marker = sql[i + 1 : i + 2]
        if marker == "s":
            parts.append("")
        elif marker == "%":
            parts[-1] += "%"
        else:
            raise SqlRejectedError(
                "when parameters are supplied, only %s placeholders are supported; write a literal % as %%"
            )
        i += 2
    return parts


def _parse_single_statement(
    sql: str,
    dialect: str,
    parameters: Optional[Sequence[Any]],
    read_only: bool,
) -> exp.Expression:
    if not sql or not sql.strip():
        raise SqlRejectedError("the SQL is empty")
    if len(sql) > MAX_SQL_LENGTH:
        raise SqlRejectedError(f"the SQL is longer than {MAX_SQL_LENGTH} characters")
    _check_characters(sql)
    if dialect == "mysql" and _MYSQL_EXECUTABLE_COMMENT.search(sql):
        raise SqlRejectedError(
            "MySQL executable comments and optimizer hints (/*! */, /*M! */, /*+ */) are not allowed"
        )

    placeholder_positions = set()
    if parameters is not None:
        parts = split_placeholders(sql)
        if len(parts) - 1 != len(parameters):
            raise SqlRejectedError(
                f"the SQL has {len(parts) - 1} %s placeholder(s) but {len(parameters)} parameter(s) were supplied"
            )
        # pymssql substitutes every %s or %d it finds and has no %% escape.
        if dialect == "tsql" and any(re.search(r"%[sd]", part) for part in parts):
            raise SqlRejectedError("SQL Server cannot send a literal %s or %d in SQL that also uses parameters")
        # Validate the statement shape the database will see; values are bound
        # separately, so a stand-in literal is enough.
        sql = parts[0]
        for part in parts[1:]:
            placeholder_positions.add(len(sql))
            sql += "0" + part

    try:
        tokens = sqlglot.Dialect.get_or_raise(dialect).tokenize(sql)
    except TokenError:
        raise SqlRejectedError("the SQL could not be tokenized (check for unterminated strings or comments)") from None
    # Driver escaping is safe only when a placeholder is a whole SQL value.
    # Inside quotes, e.g. SELECT '%s', the driver's own quotes can end the
    # surrounding literal and expose parameter text as executable SQL.
    value_positions = {
        token.start
        for token in tokens
        if token.token_type == TokenType.NUMBER and token.text == "0" and token.start == token.end
    }
    if not placeholder_positions <= value_positions:
        raise SqlRejectedError(
            "%s placeholders must be standalone values, outside strings, quoted identifiers and comments; "
            "do not put quotes around placeholders"
        )
    _check_tokens(tokens, dialect, read_only)

    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except (ParseError, TokenError) as e:
        first_line = str(e).splitlines()[0] if str(e) else type(e).__name__
        raise SqlRejectedError(f"the SQL could not be parsed ({first_line})") from None
    except RecursionError:
        raise SqlRejectedError("the SQL is too deeply nested to check") from None
    if len(statements) != 1:
        raise SqlRejectedError(f"exactly one statement is allowed (found {len(statements)})")
    if dialect == "tsql":
        _check_tsql_reserved_names(statements[0])
        if not read_only:
            _check_tsql_write_tokens(tokens, statements[0])
    return statements[0]


def _check_tsql_reserved_names(statement: exp.Expression) -> None:
    for identifier in statement.find_all(exp.Identifier):
        word = identifier.name.upper()
        if not identifier.quoted and word in _TSQL_RESERVED_WORDS:
            raise SqlRejectedError(
                f"{word} is a reserved word in SQL Server and cannot be used as a name without brackets, "
                f"e.g. [{identifier.name}]; additional statements are not allowed"
            )


def _check_tsql_write_tokens(tokens: List[Token], statement: exp.Expression) -> None:
    # INSERT ... SELECT has the same parser ambiguity as SELECT: a trailing
    # DELETE can become an alias while SQL Server executes it as another write.
    # Every write keyword (and UPDATE's SET) must belong to a parsed operation.
    words = _COMMON_WRITE_WORDS | {"SET"}
    actual = Counter(
        token.text.upper()
        for token in tokens
        if token.token_type not in _QUOTED_TOKEN_TYPES and token.text.upper() in words
    )
    expected = Counter()
    for node in statement.walk():
        if isinstance(node, _WRITE_ROOTS):
            expected[_statement_kind(node)] += 1
            if isinstance(node, exp.Update):
                expected["SET"] += 1
        # sqlglot represents MERGE's THEN DELETE as a Var rather than a Delete.
        elif isinstance(node, exp.When) and isinstance(node.args.get("then"), exp.Var):
            if node.args["then"].name.upper() == "DELETE":
                expected["DELETE"] += 1
    if actual != expected:
        raise SqlRejectedError(
            "write keywords do not match one parsed statement; additional statements are not allowed"
        )


def _check_characters(sql: str) -> None:
    for ch in sql:
        if ch not in _ALLOWED_WHITESPACE and unicodedata.category(ch) in _REJECTED_CATEGORIES:
            raise SqlRejectedError(
                f"invisible, control or non-standard whitespace characters are not allowed (found U+{ord(ch):04X})"
            )


def _check_tokens(tokens: List[Token], dialect: str, read_only: bool) -> None:
    forbidden_words = _COMMON_FORBIDDEN_WORDS | _DIALECT_FORBIDDEN_WORDS[dialect]
    if read_only:
        forbidden_words |= _COMMON_WRITE_WORDS | _READ_ONLY_EXTRA_WORDS[dialect]
    for index, token in enumerate(tokens):
        next_type = tokens[index + 1].token_type if index + 1 < len(tokens) else None
        if (
            dialect == "postgres"
            and token.text.upper() == "U"
            and next_type == TokenType.AMP
            and index + 2 < len(tokens)
            and tokens[index + 2].token_type == TokenType.IDENTIFIER
        ):
            # PostgreSQL decodes U&"..." names, but sqlglot treats U & as an
            # operator and leaves escapes in the name, hiding forbidden functions.
            raise SqlRejectedError('PostgreSQL Unicode-escaped identifiers (U&"...") are not supported')
        # Quoted names can still be function calls, e.g. PostgreSQL's "set_config"(...).
        if next_type == TokenType.L_PAREN:
            name = token.text.lower()
            if _FORBIDDEN_FUNCTIONS[dialect].fullmatch(name) or (
                read_only and _READ_ONLY_FORBIDDEN_FUNCTIONS.fullmatch(name)
            ):
                raise SqlRejectedError(f"the function {token.text} is not allowed")
        if token.token_type in _QUOTED_TOKEN_TYPES or not _WORD.fullmatch(token.text):
            continue
        word = token.text.upper()
        # REPLACE(...) is a string function; a bare REPLACE is MySQL's delete-and-insert statement.
        if word in forbidden_words or (word == "REPLACE" and next_type != TokenType.L_PAREN):
            if read_only and word in _COMMON_WRITE_WORDS:
                raise SqlRejectedError(
                    f"the keyword {word} is not allowed in a read-only query. "
                    "Use the execute action to insert, update or delete data."
                )
            raise SqlRejectedError(f"the keyword {word} is not allowed here")


def _reject_nodes(statement: exp.Expression, node_types: tuple) -> None:
    node = statement.find(*node_types)
    if node is not None:
        raise SqlRejectedError(f"{_statement_kind(node)} is not allowed in this statement")


def _statement_kind(node: exp.Expression) -> str:
    names = {
        exp.Into: "SELECT ... INTO",
        exp.Lock: "a row-locking clause (FOR UPDATE / FOR SHARE)",
        exp.NextValueFor: "NEXT VALUE FOR",
        exp.TruncateTable: "TRUNCATE",
    }
    for node_type, name in names.items():
        if isinstance(node, node_type):
            return name
    return type(node).__name__.upper()
