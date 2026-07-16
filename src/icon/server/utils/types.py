from dataclasses import dataclass
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


@dataclass
class DataPointToProcess:
    """A data point queued for pre-processing.

    Orders by ``index`` only, so a priority queue of data points dispenses them
    in data-point order regardless of insertion order. Restricting the
    comparison to the index (instead of comparing whole tuples) keeps the heap
    from ever falling back to comparing the ``scan_params`` dicts, which do not
    support ``<``.
    """

    index: int
    scan_params: dict[str, DatabaseValueType]

    def __lt__(self, other: "DataPointToProcess") -> bool:
        return self.index < other.index
