# SQL Database Integration for Autohive

Run SQL against Microsoft SQL Server (including Azure SQL), PostgreSQL and MySQL/MariaDB databases.

## Description

The integration has two actions:

- **`query`**: runs one `SELECT` and returns the rows, with layered checks that reject writes and known side effects. It is also how you [discover the schema](#discovering-tables-and-columns).
- **`execute`**: runs one `INSERT`, `UPDATE`, `DELETE` or `MERGE` and commits it. It is disabled unless the connection's access mode is `read-write`.

Each action opens a new connection to the database, runs one statement and closes the connection.

## Setup & Authentication

| Field | Required | Description |
|-------|----------|-------------|
| `database_type` | Yes | `sqlserver`, `postgresql` or `mysql`, in any case (`SQL Server`, `PostgreSQL` and `MariaDB` also work). Use `sqlserver` for Azure SQL and `mysql` for MariaDB. |
| `connection_string` | Yes | The connection string in the format for that database (see below). Stored masked. |
| `access_mode` | No | `read-only` (the default) or `read-write`. Only `read-write` connections can use the `execute` action. |
| `ca_certificate` | No | PEM text of the certificate authority that signed the database server's certificate, such as the [Amazon RDS CA bundle](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html). When set, the server certificate is always verified against this CA instead of public CAs, including when the connection string asks for encryption without verification (`sslmode=require`, `ssl-mode=REQUIRED`, `TrustServerCertificate=True`; the host name is then not checked). A connection string that turns encryption off is rejected. Line breaks lost when pasting into a single-line field are fine. |

### Access mode

New connections are read-only: the `execute` action returns an error until `access_mode` is set to `read-write`. Give an agent a read-only connection when it should only answer questions about the data, and create a separate read-write connection, ideally with its own database login, for workflows that change data.

### Use a read-only login for querying

Use a database login restricted to reading whenever writes must be impossible. The checks described under [How read-only is enforced](#how-read-only-is-enforced) provide defence in depth, but SQL text checks cannot guarantee this with a write-capable login, especially on SQL Server:

- **SQL Server:** `CREATE USER autohive_reader FOR LOGIN autohive_reader; ALTER ROLE db_datareader ADD MEMBER autohive_reader;` and do not grant `EXECUTE`.
- **PostgreSQL:** `GRANT pg_read_all_data TO autohive_reader;` (PostgreSQL 14+) or `GRANT SELECT` on the tables it needs.
- **MySQL/MariaDB:** `GRANT SELECT ON mydb.* TO 'autohive_reader'@'%';`

Create a second, `read-write` Autohive connection with a read/write login only when the `execute` action is needed. Access mode controls which actions run; the database login controls what SQL can do, so use both.

These examples assume the login/user already exists and has permission to connect. Remove inherited write, administrative and procedure-execution permissions too; adding a reader role does not remove existing grants. Prefer grants on only the required tables over access to the entire database.

### SQL Server

ADO.NET and ODBC connection strings are accepted, including the one the Azure portal shows:

```
Server=tcp:myserver.database.windows.net,1433;Initial Catalog=mydb;User ID=autohive_reader;Password=...;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;
```

- `Server` / `Data Source`: `host`, `host,port` or `host\instance`. A `tcp:` prefix is fine.
- `Encrypt` defaults to `True`, and the server certificate is verified against public certificate authorities (the same default as Microsoft.Data.SqlClient), or against `ca_certificate` when it is set. Set `TrustServerCertificate=True` for servers with self-signed certificates, such as a default on-premises install or Docker. `Encrypt=False` uses TLS when the server offers it, without verifying the certificate. With `ca_certificate` set, `TrustServerCertificate=True` still checks the certificate against that CA but skips the host name check, and `Encrypt=False` is rejected.
- `Connection Timeout` is capped at 15 seconds, and `0` (no limit) also becomes 15.
- `ApplicationIntent=ReadOnly` is honoured and routes to a readable secondary replica in an availability group. It does **not** stop writes on its own.
- Only SQL authentication is supported. Windows authentication (`Integrated Security`) and Microsoft Entra ID (`Authentication=Active Directory ...`) are rejected with an error, as is `Encrypt=Strict` (TDS 8).
- Keywords that do not apply here, such as `Driver`, `Persist Security Info`, `MultipleActiveResultSets` and pooling settings, are ignored. Unknown keywords are rejected, so a typo like `Pasword` produces an error instead of being dropped silently. The error does not repeat an unknown keyword, because it may be part of a password that contains `;`. Wrap such a password in braces: `Password={a;b}`.

### PostgreSQL

A URL or libpq key/value string:

```
postgresql://autohive_reader:password@db.example.com:5432/mydb
host=db.example.com dbname=mydb user=autohive_reader password=... sslmode=verify-full
```

Connections are encrypted by default (`sslmode=require`), which protects the traffic but does not verify the server's identity. With `ca_certificate` set, the default becomes `verify-full`, and `require`, `prefer` and `allow` become `verify-ca` (which is also what libpq does for `require` when a root certificate is present); `disable` is rejected. `sslmode=verify-ca` and `verify-full` check the certificate against `ca_certificate` or, without it, public certificate authorities. Set `sslmode=disable` or `prefer` only for servers on a private network that do not support TLS. Options that read or write local files (`sslkey`, `sslcert`, `sslrootcert`, `passfile`, `service` and similar) are rejected, and `connect_timeout` is capped at 15 seconds (`0`, which means no limit, also becomes 15). Queries use unnamed extended-protocol execution and transaction-scoped settings, which avoid session state dependencies with transaction-mode poolers. PgBouncer, Supavisor and hosted database services have not been tested directly.

### MySQL and MariaDB

A URL. Percent-encode special characters in the user name or password (`@` is `%40`, `:` is `%3A`):

```
mysql://autohive_reader:password@db.example.com:3306/mydb
```

Connections are encrypted by default (`ssl-mode=REQUIRED`), without verifying the server's identity. With `ca_certificate` set, the default becomes `VERIFY_IDENTITY`, `REQUIRED` and `PREFERRED` become `VERIFY_CA`, and `DISABLED` is rejected. `VERIFY_CA` checks the certificate chain and `VERIFY_IDENTITY` also checks the host name, against `ca_certificate` or, without it, public certificate authorities. `PREFERRED` (TLS only when the server offers it) and `DISABLED` are explicit opt-outs for servers that do not support TLS. `mariadb://` also works.

### Network access

Autohive connects to the database directly over TCP, so the database must accept connections from Autohive. Allow Autohive's outbound addresses in the database firewall. For Azure SQL, the "Allow Azure services" option is not enough.

## Actions

### `query`

Runs a single read-only `SELECT`. `WITH` (CTEs), joins, subqueries and `UNION`/`INTERSECT`/`EXCEPT` are allowed.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `sql` | string | Yes | One `SELECT` in the database's own dialect. |
| `parameters` | array | No | Values for `%s` placeholders, in order. |
| `max_rows` | integer | No | Rows to return, 1–10000 (default 100). |
| `timeout_seconds` | integer | No | Cancel after this many seconds, 1–300 (default 30). |

Output:

```json
{
  "columns": ["id", "email", "total"],
  "rows": [{"id": 1, "email": "a@example.com", "total": "120.50"}],
  "row_count": 1,
  "truncated": false,
  "truncation_reason": null,
  "values_truncated": false
}
```

- Results are limited to `max_rows` rows and about 4 MB of JSON, which keeps them under AWS Lambda's 6 MB response limit. `truncated` is `true` when there were more rows, and `truncation_reason` says which limit was reached: `max_rows` (raise `max_rows` or add a `WHERE`/`ORDER BY`) or `max_bytes` (select fewer or shorter columns).
- Text and binary values longer than 65,536 characters are cut to that length, and `values_truncated` is `true`. Select a substring (for example `LEFT(body, 1000)`) when you only need the start of a long value.
- Unnamed columns (for example SQL Server's `COUNT(*)`) are called `column_N`, and duplicate names get a suffix (`id`, `id_2`).

#### Value formats

| Database type | JSON value |
|---------------|------------|
| Dates, times, timestamps | ISO 8601 strings (`2026-01-02T03:04:05`, with the offset when the type has one). PostgreSQL values outside Python's range (`infinity`, BC dates, `24:00:00`) are returned in PostgreSQL's own text form. |
| PostgreSQL `interval` | ISO 8601 duration (`P1DT2H`). |
| MySQL `TIME` | `[-]HH:MM:SS[.ffffff]`, with hours past 24 (`838:00:00`), since `TIME` can also hold durations. |
| Decimal, numeric, money | Strings, so no precision is lost. |
| Binary | Base64. |
| JSON | Objects and arrays on PostgreSQL and MySQL. MariaDB stores JSON as text, so it is returned as a string. |
| MySQL `BIT` | Integers (`BIT(1)` is `0` or `1`). |
| SQL Server `sql_variant`, `hierarchyid`, `geography`, `geometry` | Raw base64 bytes, because the driver cannot decode them. Convert in SQL instead: `CAST(v AS NVARCHAR(4000))`, `h.ToString()`, `g.STAsText()`. |

SQL Server `datetime2(7)` and `time(7)` keep microseconds, not the seventh fractional digit; use `CONVERT(VARCHAR(33), col, 126)` if you need it. Integers beyond 2^53 are returned as JSON numbers, which some JavaScript consumers round; cast them to text if exact values matter.

#### Discovering tables and columns

Use `query` to read the database's catalog. Results only include objects the login can see.

```sql
-- Tables and views (all three databases; on MySQL, table_schema is the database name)
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'sys', 'mysql', 'performance_schema')
ORDER BY table_schema, table_name;

-- Columns of one table (all three databases)
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'orders'
ORDER BY ordinal_position;

-- Primary and foreign keys (all three databases)
SELECT tc.constraint_type, kcu.column_name, kcu.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
WHERE tc.table_schema = 'public' AND tc.table_name = 'orders';
```

Use `dbo` as the schema on SQL Server and the database name on MySQL. An agent can be asked to "explore the database structure with the query action" and will use queries like these.

### `execute`

Runs a single `INSERT`, `UPDATE`, `DELETE` or `MERGE` in a transaction and commits it. The connection's `access_mode` must be `read-write`. Failed statements are rolled back on transactional storage engines. MySQL/MariaDB nontransactional tables and external effects from triggers or functions cannot be rolled back. If the connection is lost while committing, the action says that the change may or may not have been saved, rather than reporting a failure; check the data before running the statement again.

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `sql` | string | Yes | One `INSERT`, `UPDATE`, `DELETE` or `MERGE`. |
| `parameters` | array | No | Values for `%s` placeholders, in order. |
| `allow_all_rows` | boolean | No | Allow an `UPDATE` or `DELETE` with no `WHERE` clause (default false). |
| `timeout_seconds` | integer | No | Cancel after this many seconds, 1–300 (default 30). |

Output:

```json
{
  "statement_type": "UPDATE",
  "rows_affected": 3,
  "columns": ["id"],
  "returned_rows": [{"id": 4}, {"id": 7}, {"id": 9}],
  "returned_rows_truncated": false
}
```

`rows_affected` counts the rows the statement matched, on every database: an `UPDATE` that matches a row counts it even when the new values equal the old ones.

`returned_rows` is filled when the statement uses `RETURNING` (PostgreSQL) or `OUTPUT` (SQL Server). On MariaDB 11, `RETURNING` is available for `INSERT` and `DELETE`, but not `UPDATE`; support depends on the server version and statement. MySQL does not support `RETURNING`. At most 1000 returned rows and about 4 MB are included; `returned_rows_truncated` is `true` when more were produced or a long value was cut. Schema changes (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`), stored procedure calls, `REPLACE`, transaction control and multiple statements are rejected. An `UPDATE` or `DELETE` without a `WHERE` clause is rejected unless `allow_all_rows` is true. This guards against accidents and is not a security control.

### Parameters

Use `%s` placeholders for any value that comes from user input or an earlier workflow step:

```json
{
  "sql": "SELECT id, total FROM orders WHERE customer_email = %s AND total > %s",
  "parameters": ["a@example.com", 100]
}
```

The driver sends the values separately or escapes them. A placeholder must be a standalone value outside strings, identifiers and comments: use `WHERE name = %s`, without quotes around `%s`. Quoted or embedded placeholders are rejected before execution. When a nonempty `parameters` array is supplied, write a literal percent sign as `%%` (`LIKE 'A%%'`). Without parameters, `%` needs no escaping. On SQL Server, SQL that uses parameters cannot also contain the literal text `%s` or `%d`.

## How read-only is enforced

The `query` action uses three layers. Each one stops attacks that get past the others.

### 1. Static checks before anything is sent (`sql_guard.py`)

The SQL is tokenized and parsed with [sqlglot](https://github.com/tobymao/sqlglot) in the database's dialect. Anything that cannot be tokenized or parsed is rejected. The query must be exactly one statement whose root is a `SELECT` or set operation, and these are rejected:

- Any bare `INSERT`, `UPDATE`, `DELETE`, `MERGE`, DDL, `GRANT`/`REVOKE`, transaction-control or `EXEC` keyword anywhere in the token stream. This catches stacked statements that the parser misses (see below).
- `SELECT ... INTO`, row locks (`FOR UPDATE`, `FOR SHARE`, `LOCK IN SHARE MODE`, T-SQL `UPDLOCK`/`XLOCK`/`TABLOCKX`/`HOLDLOCK`/`SERIALIZABLE`/`REPEATABLEREAD` hints) and `NEXT VALUE FOR`.
- Functions with side effects that a read-only transaction does not stop, such as PostgreSQL `dblink*`, `set_config`, `pg_terminate_backend`, `pg_read_file`, `lo_export`, advisory locks, replication-slot functions and index maintenance (`brin_summarize_*`, `gin_clean_pending_list`), and functions that run SQL passed as text (`query_to_xml`, `ts_stat`, `ts_rewrite`, `crosstab`, `connectby`, `xpath_table`); MySQL `GET_LOCK`, `LOAD_FILE` and `sys_exec`; T-SQL `OPENQUERY`, `OPENROWSET` and `OPENDATASOURCE`. Quoted (`"set_config"(...)`) and schema-qualified names are caught too.
- T-SQL statements that can follow a `SELECT` without a separator, such as `SET`, `DECLARE`, `KILL`, `SHUTDOWN`, `BACKUP`, `DBCC`, `WAITFOR`, `CHECKPOINT` and `BULK`.
- T-SQL reserved words that the parser read as names. SQL Server never treats an unquoted reserved word as a name, but sqlglot accepts most of them as aliases (`SELECT 1 CHECKPOINT`), so the two parsers would disagree about where the statement ends. Put names that are reserved words in brackets, e.g. `[key]`.
- MySQL executable comments (`/*! ... */`, `/*M! ... */`) and optimizer hints (`/*+ ... */`).
- Control characters, zero-width and bidirectional formatting characters, and any whitespace other than space, tab and newline.
- Placeholders inside quotes, identifiers or comments. For SQL Server writes, every write keyword and `SET` must correspond to a parsed operation, preventing a hidden second write after `INSERT ... SELECT`.

### 2. The database refuses or discards writes (`db_engines.py`)

| Database | What happens |
|----------|--------------|
| PostgreSQL | `BEGIN READ ONLY`, never committed. Queries run through the extended protocol, so the server refuses multi-statement text. Writes use pipeline mode, which also uses the extended protocol. |
| MySQL / MariaDB | `SET SESSION TRANSACTION READ ONLY` plus `START TRANSACTION READ ONLY`, never committed. PyMySQL leaves multi-statements off, so the server refuses them. |
| SQL Server | SQL Server has no read-only transaction. The query runs in a transaction that is never committed, with `IMPLICIT_TRANSACTIONS ON`, and the connection is closed, so writes are rolled back. |

`timeout_seconds` is enforced by the server on PostgreSQL (`statement_timeout`) and MySQL/MariaDB (`max_execution_time`/`max_statement_time`, plus row and metadata lock waits), and by a driver timeout on SQL Server. MySQL has no server-side time limit for writes, so when the client times out it also cancels the statement with `KILL QUERY`. Rows are read one at a time and reading stops at `max_rows` + 1 rows or the size limit; the disposable connection then closes without downloading the rest. These settings are not a total wall-clock deadline for connection setup and result transfer.

### 3. A read-only database login

This is the only layer that SQL text cannot get around. See [Use a read-only login for querying](#use-a-read-only-login-for-querying).

### Bypass techniques the checks are built against

Each of these works against a real server when only one layer is in place. Every one is a test in `tests/test_sql_guard_unit.py` or `tests/test_sql_database_integration.py`.

- **Statements without semicolons (T-SQL).** SQL Server runs `SELECT 1 DELETE FROM t` as two statements. sqlglot parses `DELETE` there as a column alias and reports a harmless `SELECT`, so an AST-only check is bypassed. The token-level keyword check catches it.
- **Invisible separators.** SQL Server treats U+200B (zero-width space) as whitespace, while the tokenizer joins it to the next word, which hides the keyword. These characters are rejected up front.
- **Writable CTEs.** `WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d` has a `SELECT` at the root. Every node is checked, not just the root.
- **Escaping the read-only transaction.** In PostgreSQL, `SET TRANSACTION READ WRITE; DELETE ...` and `COMMIT; DELETE ...` defeat `BEGIN READ ONLY` when multi-statement text is allowed. `dblink_exec` opens a second connection that is not read-only at all.
- **Committing the rolled-back transaction (SQL Server).** `SELECT 1 COMMIT DELETE FROM t COMMIT` persists the delete despite the never-committed transaction, so the static check is the main control on SQL Server. A read-only login closes this gap.
- **Non-transactional side effects.** MySQL `SELECT ... INTO OUTFILE` writes a file inside a read-only transaction. A rolled-back `NEXT VALUE FOR` still advances the sequence. `ApplicationIntent=ReadOnly` does not block writes on a primary.
- **Parser differentials.** MySQL runs the contents of `/*! */` comments, and `--1` is arithmetic rather than a comment. To keep string parsing consistent, sessions turn on `standard_conforming_strings` (PostgreSQL) and turn off `NO_BACKSLASH_ESCAPES`, `ANSI_QUOTES` and composite modes that re-enable it (MySQL/MariaDB). PostgreSQL Unicode-escaped identifiers (`U&"..."`) are rejected because the server decodes function names that the parser leaves escaped.
- **Quoted placeholders.** Client-side substitution in `SELECT '%s'` can close the surrounding SQL string and turn parameter text into a second statement. The guard verifies that each placeholder is a standalone value token, including in write statements.
- **Hidden second writes.** `INSERT INTO t SELECT 1 DELETE FROM t` has the same alias misparse as the read-only example. SQL Server write keywords must also match operations in the parsed tree, including legitimate `MERGE` branches.
- **Negative parameters (SQL Server).** pymssql copies parameter values into the SQL text, so `SET x = x-%s WHERE id = %s` with `-1` would become `x--1`, a line comment that drops the `WHERE` clause and updates every row. A space is added before each value.

### Known limitations

- A denylist of side-effecting functions cannot cover every extension or user-defined function. Read-only transactions restrict ordinary table writes, but do not prevent every external side effect or access to other databases through extensions. On SQL Server, user-defined functions cannot ordinarily modify data, but extended stored procedures and CLR functions can have external side effects.
- `query` rejects some legitimate but uncommon SQL: PostgreSQL `VALUES`/`TABLE` statements and Unicode-escaped identifiers, `EXPLAIN`, `SHOW`, and unquoted column names that are reserved words (`SELECT update FROM t` — quote them instead).
- MySQL writes are cancelled from the client about five seconds after `timeout_seconds`, because MySQL's `max_execution_time` only applies to `SELECT`. Lock waits end at `timeout_seconds` on the server.
- Server-side outbound network rules are the platform's responsibility: the drivers open TCP connections to whatever host the connection string names.
- SQL Server actions run one at a time within each process, on their own thread, because pymssql/FreeTDS timeout settings are process-wide. Waiting for another SQL Server action is outside the statement timeout, but does not hold up PostgreSQL or MySQL actions. Connection login timeouts are capped at 15 seconds.
- MySQL streaming cleanup uses PyMySQL's internal result flags to prevent its close/destructor methods from downloading discarded rows. Keep the pinned driver series and run the live truncation tests when upgrading it.

## Requirements

- `autohive-integrations-sdk~=2.0.1`
- `sqlglot`: SQL tokenizer and parser used by the static checks. Pinned to an exact version because the checks depend on its parsing; run the bypass tests before upgrading it. The package also contains sqlglot's optional SQL executor, which runs generated code with `eval()` (`dependencies/sqlglot/executor/context.py`). Code scanners flag that line. The integration never imports `sqlglot.executor`, and a unit test fails if anything starts loading it.
- `psycopg[binary]`: PostgreSQL driver (bundles libpq)
- `PyMySQL[rsa]`: MySQL and MariaDB driver, including RSA authentication for servers without TLS
- `pymssql`: SQL Server driver (bundles FreeTDS and OpenSSL, so no system ODBC driver is needed). Its Linux wheel bundles Red Hat's patched OpenSSL 1.1.1k build, which only changes when pymssql publishes new wheels, so keep the pin current.
- `certifi`: public CA bundle for certificate verification

The integration follows the SDK's custom-auth envelope, registered `ActionHandler` classes and schema-validated results. Database protocols use their native drivers over TCP; HTTP `context.fetch` cannot carry these connections. Each action gets a fresh connection, and blocking driver calls run in `asyncio.to_thread` so they do not block the event loop. `pymssql` supplies SQL Server access without a separately installed ODBC driver; PostgreSQL and MySQL use their native protocols without introducing an ORM.

## Testing

### Unit tests

```bash
pytest sql-database/
```

The unit tests need no database. They cover the bypass corpus, connection-string parsing, the per-engine read-only setup (with mocked drivers) and the action handlers.

### Integration tests

The integration tests create, change and drop a table called `autohive_sqldb_test`, so only run them against disposable databases. `tests/docker-compose.yml` starts SQL Server, PostgreSQL, MySQL and MariaDB:

```bash
docker compose -f sql-database/tests/docker-compose.yml up -d
# set the SQL_DATABASE_TEST_* variables from .env.example in .env
pytest sql-database/tests/test_sql_database_integration.py -m integration
```

Each engine is skipped unless its variable is set. The PostgreSQL container has no TLS, so its connection string needs `sslmode=disable`. The custom-CA test also needs `SQL_DATABASE_TEST_MYSQL_CA`, the path of the MySQL container's own CA (see `.env.example`). Besides normal action behaviour, the tests call the database layer directly to verify read-only transaction restrictions and rollback behaviour. A separate SQL Server test demonstrates that repeated `COMMIT` can defeat rollback alone, while the static guard rejects that SQL. Another verifies that a database user granted only `SELECT` still cannot delete with the static guard bypassed; that test creates and drops `autohive_sqldb_test_reader`. The suite also checks certificate rejection and custom-CA verification, required TLS, value formats, size limits, matched-row counts, MySQL lock-wait and runaway-write cancellation, read-only connections, MySQL/MariaDB string-mode normalization and truncation without draining extra rows.

The live suite has been run against SQL Server 2022, PostgreSQL 16, MySQL 8.4 and MariaDB 11 in local containers, including SQL Server under amd64 emulation on Apple Silicon. Azure SQL, cloud networking and connection poolers still need environment-specific verification.

## Research references

- [SDK integration structure and authentication fields](https://github.com/autohive-ai/integrations-sdk/blob/master/docs/manual/integration_structure.md).
- [SQL Server database roles and permissions](https://learn.microsoft.com/en-us/sql/relational-databases/security/authentication-access/database-level-roles) and [application intent and read-only routing](https://learn.microsoft.com/en-us/sql/database-engine/availability-groups/windows/listeners-client-connectivity-application-failover).
- [PostgreSQL read-only transaction restrictions](https://www.postgresql.org/docs/16/sql-set-transaction.html) and [Psycopg streaming cursors](https://www.psycopg.org/psycopg3/docs/api/cursors.html#psycopg.Cursor.stream).
- [MySQL transaction access modes](https://dev.mysql.com/doc/refman/8.4/en/commit.html) and [executable comment syntax](https://dev.mysql.com/doc/refman/8.4/en/comments.html).
- [PyMySQL authentication dependencies](https://pymysql.readthedocs.io/en/latest/user/installation.html) and [MariaDB UPDATE/RETURNING version restrictions](https://mariadb.com/docs/server/reference/sql-statements/data-manipulation/changing-deleting-data/update).
- [pymssql driver options and timeout limitations](https://www.pymssql.org/en/stable/ref/pymssql.html).

The parser discrepancies above were checked against the local engines and are recorded as regression cases; the references describe the underlying database and driver behaviour.

## Troubleshooting

| Error | Cause |
|-------|-------|
| `Query rejected: the keyword DELETE is not allowed in a read-only query...` | Use the `execute` action to change data. |
| `Query rejected: ... could not be parsed` | The SQL is not valid in the selected database's dialect, or `database_type` is wrong. |
| `Statement rejected: DELETE without a WHERE clause...` | Add a `WHERE` clause, or set `allow_all_rows` if every row should change. |
| `...placeholder(s) but ... parameter(s) were supplied` | The number of `%s` placeholders must match `parameters`. Write a literal `%` as `%%`. |
| `This connection is read-only, so the execute action is disabled...` | Set `access_mode` to `read-write` in the connection settings. |
| `...server does not support SSL, but SSL was required` (PostgreSQL) or `SSL is required but the server doesn't support it` (MySQL) | The server has no TLS. Enable TLS on the server, or add `sslmode=disable` / `ssl-mode=DISABLED` if it is only reachable over a private network. |
| `...certificate verify failed...` | The server's certificate is not signed by a public CA. Paste the provider's CA into `ca_certificate`. |
| `Database error: 20009: ... Connection refused (111)` (SQL Server) | Something at that address answered but refused the connection on that port: the port is wrong, nothing forwards it to SQL Server, SQL Server is not listening on TCP, or a firewall rejects Autohive's IP address. |
| `Database error: 20009: ... Connection timed out (110)` (SQL Server) | No reply. A firewall is probably dropping traffic from Autohive's IP address, or the host or port is wrong. |
| `Database error: 20018: SQL Server rejected the login...` | Wrong user name or password, wrong database name, or the login cannot open that database. |
| `Database error: 20002: TDS server connection failed` (SQL Server) | The connection opened but setup failed, usually TLS. For self-signed certificates, add `TrustServerCertificate=True` or set `ca_certificate`. |
| `Database error: the statement did not finish within ...` | The statement ran past `timeout_seconds` and was cancelled. Raise the timeout or narrow the statement. |
| `Database error: the connection was lost while committing...` | The change may or may not have been saved. Check the data before running the statement again. |
| `Database error: 18456: Login failed...` | Wrong user or password, or the login has no access to the database. |
| `Unsupported PostgreSQL connection parameter(s)`, `...has a keyword that is not supported` (SQL Server) or `...support only the ssl-mode parameter` (MySQL) | Remove the option from the connection string. For SQL Server, wrap a password that contains `;` in braces; for MySQL, percent-encode special characters in the password. |
| `A CA certificate is set, but the connection string turns encryption off...` | Remove `sslmode=disable`, `ssl-mode=DISABLED` or `Encrypt=False`, or clear `ca_certificate`. |

## Version History

- **1.0.0**: Initial release with `query` and `execute` for SQL Server, PostgreSQL and MySQL/MariaDB.
