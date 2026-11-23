from typing import Any

from pycrystal.database.database import Database, DatabaseValueType
from pycrystal.utils.parameter_id_utils import get_parameter_identifier_from_specifiers


class LocalCache(Database):
    def __init__(self, key_val_dict: dict[str, DatabaseValueType] = {}) -> None:
        self.key_val_dict = key_val_dict

    def query(self, **kwargs: Any) -> DatabaseValueType | None:
        param_id = get_parameter_identifier_from_specifiers(**kwargs)
        return self.key_val_dict.get(param_id, None)

    def update(self, new_value: DatabaseValueType, **kwargs: Any) -> None:
        param_id = get_parameter_identifier_from_specifiers(**kwargs)
        self.update_by_id(param_id=param_id, new_value=new_value)

    def update_by_id(self, param_id: str, new_value: DatabaseValueType) -> None:
        self.key_val_dict[param_id] = new_value
