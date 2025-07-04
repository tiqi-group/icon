from typing import Literal, NotRequired, TypedDict

from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType


class UpdateQueue(TypedDict):
    event: Literal["update_parameters", "calibration"]
    job_id: NotRequired[int | None]
    new_parameters: NotRequired[dict[str, DatabaseValueType]]
