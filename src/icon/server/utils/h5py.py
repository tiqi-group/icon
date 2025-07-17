import h5py  # type: ignore
import numpy as np


def get_hdf5_dtype(
    value: str | float | bool,
) -> type[np.float64 | np.bool | np.int64] | h5py.Datatype:
    """Return the HDF5-compatible dtype."""

    if isinstance(value, str):
        return h5py.string_dtype()
    if isinstance(value, bool):
        return np.bool
    if isinstance(value, int):
        return np.int64
    if isinstance(value, float):
        return np.float64

    raise TypeError(f"Unsupported parameter type: {type(value)}")
