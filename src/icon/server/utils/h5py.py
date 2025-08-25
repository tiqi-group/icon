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


def get_result_channels_dataset(
    h5file: h5py.File, result_channels: list[str], number_of_data_points: int = 1
) -> h5py.Dataset:
    sorted_result_channels = sorted(result_channels)
    result_dtype = np.dtype([(key, np.float64) for key in sorted_result_channels])

    return h5file.require_dataset(
        "result_channels",
        shape=(number_of_data_points,),
        maxshape=(None,),
        chunks=True,
        dtype=result_dtype,
        compression="gzip",
        compression_opts=9,
    )
