import queue
from typing import TYPE_CHECKING

from icon.server.utils.types import DataPointToProcess

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType


def test_data_points_dispense_in_index_order() -> None:
    """Data points dispense by index.

    A tie on index must not fall back to comparing the (unorderable)
    scan-parameter dicts.
    """
    q: queue.PriorityQueue[DataPointToProcess] = queue.PriorityQueue()
    data_points: list[tuple[int, dict[str, DatabaseValueType]]] = [
        (5, {"freq": 5.0}),
        (3, {"freq": 3.0}),
        (3, {"amp": 1.0}),
        (0, {"freq": 0.0}),
    ]
    for index, scan_params in data_points:
        q.put(DataPointToProcess(index=index, scan_params=scan_params))

    assert [q.get().index for _ in range(4)] == [0, 3, 3, 5]
