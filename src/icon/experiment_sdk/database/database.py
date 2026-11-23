import logging
import math
import random
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "Database",
    "DummyDB",
]

DatabaseCacheSpecifiers = dict[str, str]
Specifiers = dict[str, str | Enum]
DatabaseValueType = float | bool | int | str


class Database(ABC):
    """ABC that abstracts the way to retrieve / set values of parameters for the
    experiments.

    You have to inherit from this class and implement the abstract methods in order to
    instantiate an actual database.
    """

    @abstractmethod
    def query(
        self,
        **kwargs: Any,
    ) -> DatabaseValueType | None:
        """Retrieving the value of a parameter."""
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        new_value: DatabaseValueType,
        **kwargs: Any,
    ) -> None:
        """Implements a way to change the value of a parameter."""
        raise NotImplementedError


class DummyDB(Database):
    """Dummy database used to validate the code without a proper database."""

    seed = 42
    random.seed(seed)

    def query(
        self,
        **kwargs: Any,
    ) -> DatabaseValueType:
        """Retrieving the value of a parameter.

        Returns:
            Dummy value between 2 and 12.
        """
        return math.floor(random.random() * 10) + 2

    def update(
        self,
        new_value: DatabaseValueType,
        **kwargs: Any,
    ) -> None:
        """Implements a way to change the value of a parameter."""
