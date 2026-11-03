import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Dict, NamedTuple, Optional

from autohive_integrations_sdk import ActionError, ActionHandler, ActionResult, ExecutionContext, Integration

from db_engines import (
    DATABASE_ERRORS,
    READ_WRITE,
    SQLGLOT_DIALECTS,
    SQLSERVER,
    ConnectionConfigError,
    ca_certificate_file,
    describe_database_error,
    redact_secrets,
    resolve_access_mode,
    resolve_engine,
    run_query,
    run_write,
)
from sql_guard import SqlRejectedError, check_read_only_query, check_write_statement

sql_database = Integration.load()

DEFAULT_MAX_ROWS = 100
DEFAULT_TIMEOUT_SECONDS = 30

# FreeTDS settings are process-wide, so SQL Server statements run one at a time.
# They queue on their own thread instead of holding threads in the default pool
# that PostgreSQL and MySQL actions use.
_SQLSERVER_THREAD = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sql-database-sqlserver")


class Connection(NamedTuple):
    engine: str
    connection_string: str
    access_mode: str
    ca_file: Optional[str]


def _connection(credentials: Dict[str, Any]) -> Connection:
    connection_string = (credentials.get("connection_string") or "").strip()
    if not connection_string:
        raise ConnectionConfigError("The connection string is missing from the connection settings.")
    return Connection(
        engine=resolve_engine(credentials.get("database_type")),
        connection_string=connection_string,
        access_mode=resolve_access_mode(credentials.get("access_mode")),
        ca_file=ca_certificate_file(credentials.get("ca_certificate")),
    )


def _parameters(inputs: Dict[str, Any]) -> Optional[list]:
    # An empty list means "no parameters", so a literal % needs no escaping.
    return inputs.get("parameters") or None


async def _on_database_thread(connection: Connection, function: Callable[..., Any], *args: Any) -> Any:
    if connection.engine == SQLSERVER:
        return await asyncio.get_running_loop().run_in_executor(_SQLSERVER_THREAD, function, *args)
    return await asyncio.to_thread(function, *args)


async def _run(context: ExecutionContext, rejection: str, work: Callable[[Connection], Awaitable[Dict[str, Any]]]):
    credentials = context.auth.get("credentials", {})
    try:
        data = await work(_connection(credentials))
    except SqlRejectedError as e:
        return ActionError(message=f"{rejection}: {e}")
    except ConnectionConfigError as e:
        return ActionError(message=redact_secrets(str(e), credentials))
    except DATABASE_ERRORS as e:
        return ActionError(message=redact_secrets(f"Database error: {describe_database_error(e)}", credentials))
    except Exception as e:  # anything unexpected still becomes an action error, without secrets
        return ActionError(message=redact_secrets(f"Unexpected error ({type(e).__name__}): {e}", credentials))
    return ActionResult(data=data)


@sql_database.action("query")
class QueryAction(ActionHandler):
    """Run a single read-only SELECT statement."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        sql = inputs["sql"]
        parameters = _parameters(inputs)

        async def work(connection: Connection) -> Dict[str, Any]:
            # Parsing long SQL takes a moment, so keep it off the event loop too.
            await asyncio.to_thread(check_read_only_query, sql, SQLGLOT_DIALECTS[connection.engine], parameters)
            return await _on_database_thread(
                connection,
                run_query,
                connection.engine,
                connection.connection_string,
                sql,
                parameters,
                inputs.get("max_rows", DEFAULT_MAX_ROWS),
                inputs.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
                connection.ca_file,
            )

        return await _run(context, "Query rejected", work)


@sql_database.action("execute")
class ExecuteAction(ActionHandler):
    """Run a single INSERT, UPDATE, DELETE or MERGE statement and commit it."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        sql = inputs["sql"]
        parameters = _parameters(inputs)

        async def work(connection: Connection) -> Dict[str, Any]:
            if connection.access_mode != READ_WRITE:
                raise ConnectionConfigError(
                    "This connection is read-only, so the execute action is disabled. To allow writes, "
                    "set Access Mode to read-write in the connection settings."
                )
            statement_type = await asyncio.to_thread(
                check_write_statement,
                sql,
                SQLGLOT_DIALECTS[connection.engine],
                parameters,
                inputs.get("allow_all_rows", False),
            )
            data = await _on_database_thread(
                connection,
                run_write,
                connection.engine,
                connection.connection_string,
                sql,
                parameters,
                inputs.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
                connection.ca_file,
            )
            return {"statement_type": statement_type, **data}

        return await _run(context, "Statement rejected", work)
