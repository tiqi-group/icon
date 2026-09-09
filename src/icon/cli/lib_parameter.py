"""Shared helpers for the parameter database command line tools.

The tools in this package (``cmd_parameter_db``, ``cmd_migrate_influxdb_schema``) issue
many small queries against one InfluxDB in a single run, which is a different access
pattern from the server's - hence the cached session here rather than in
:mod:`icon.server.data_access.db_context.influxdb.influxdb_v1`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from icon.server.data_access.db_context.influxdb.influxdb_v1 import InfluxDBv1Session

if TYPE_CHECKING:
    import contextlib
    from types import TracebackType
    from typing import Self


class InfluxDBv1CachedSession(InfluxDBv1Session):
    """An :class:`InfluxDBv1Session` which reuses one connection across ``with`` blocks.

    Entering and leaving the context manager is a no-op, so the underlying client is not
    reconnected for every query. Call :meth:`disconnect` when done with it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.connect()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        pass


class InfluxDBv1CachedSessionProvider:
    """An :data:`InfluxDBSessionProvider` handing out one shared, connected session.

    Intended for tools which issue many small queries back to back; the server-side code
    uses :func:`default_session_provider` instead, which connects per operation.
    """

    def __init__(self) -> None:
        self.session = InfluxDBv1CachedSession()

    def __call__(self) -> contextlib.AbstractContextManager[InfluxDBv1Session]:
        return self.session

    def close(self) -> None:
        self.session.disconnect()
