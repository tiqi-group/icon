from typing import Literal, NotRequired, TypedDict

from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType


class UpdateParametersEvent(TypedDict):
    event: Literal["update_parameters"]
    job_id: NotRequired[int | None]


class CalibrationEvent(TypedDict):
    event: Literal["calibration"]
    new_parameters: dict[str, DatabaseValueType]


class RetakeDataPointsEvent(TypedDict):
    event: Literal["retake_data_points"]
    job_id: int
    no_data_points: int


UpdateQueue = UpdateParametersEvent | CalibrationEvent | RetakeDataPointsEvent
"""Event placed on a pre-processing worker's update queue."""

DataPointToProcess = tuple[int, dict[str, DatabaseValueType]]
"""A queued data point: ``(index, scan_parameter_values)``."""
