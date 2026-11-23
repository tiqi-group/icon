import functools
import warnings
from collections.abc import Callable
from typing import Any

__all__ = ["reissue_warnings"]


def reissue_warnings(stacklevel: int = 2) -> Any:
    """Returning a decorator reissuing warnings with stacklevel given by the argument to
    this function."""

    def func_wrapper(func: Callable[..., Any]) -> Any:
        """Function decorator that uses 'warnings.catch_warnings' to copy and restore
        warnings issued down the callstack and prints those (messages and categories)
        with the stacklevel provided by the 'stacklevel' argument of the function
        'reissue_warnings'.
        """

        @functools.wraps(func)
        def handling_warnings(*args: Any, **kwargs: Any) -> Any:
            with warnings.catch_warnings(record=True) as warning_list:
                result = func(*args, **kwargs)
            for warning in warning_list:
                warnings.warn(
                    warning.message,
                    warning.category,
                    stacklevel=stacklevel,
                )
            return result

        return handling_warnings

    return func_wrapper
