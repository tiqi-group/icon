from typing import Literal, NotRequired, TypedDict

from icon.server.data_access.experiment_data import DatabaseValueType


class UpdateQueue(TypedDict):
    event: Literal["update_parameters", "calibration"]
    job_id: NotRequired[int | None]
    new_parameters: NotRequired[dict[str, DatabaseValueType]]
