from typing import Literal

import sys
if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

if sys.version_info < (3, 12):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict

from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType


class UpdateQueue(TypedDict):
    event: Literal["update_parameters", "calibration"]
    job_id: NotRequired[int | None]
    new_parameters: NotRequired[dict[str, DatabaseValueType]]
