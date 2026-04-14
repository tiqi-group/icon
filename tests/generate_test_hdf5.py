"""Generate synthetic HDF5 files visible to the running ICON server.

Creates HDF5 files in the configured results directory and inserts the
matching SQLite records (experiment_source, job, scan_parameter, job_run)
so the server can find the data by job ID.

Usage::

    uv run python tests/generate_test_hdf5.py

The script prints the job ID for each created entry so you can navigate to
it in the UI at http://localhost:8004.

Requirements:
- The ICON database must already exist (run the server at least once so
  Alembic has applied all migrations).
- The results directory must be writable.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import h5py  # type: ignore
import numpy as np
import sqlalchemy
import sqlalchemy.orm

from icon.config.config import get_config
from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter

# ---------------------------------------------------------------------------
# Shared experiment source — reused across all generated jobs
# ---------------------------------------------------------------------------

_EXPERIMENT_ID = "test.SyntheticExperiment (SyntheticExperiment)"


def _get_or_create_experiment_source(session: sqlalchemy.orm.Session) -> ExperimentSource:
    existing = session.execute(
        sqlalchemy.select(ExperimentSource).where(
            ExperimentSource.experiment_id == _EXPERIMENT_ID
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    source = ExperimentSource(experiment_id=_EXPERIMENT_ID)
    session.add(source)
    session.flush()  # populate source.id without committing
    return source


def _insert_job_and_run(
    session: sqlalchemy.orm.Session,
    source: ExperimentSource,
    scan_values: list[float],
    variable_id: str,
    scheduled_time: datetime,
) -> tuple[Job, JobRun]:
    """Insert a Job, ScanParameter, and JobRun; return both ORM objects."""
    job = Job(
        experiment_source_id=source.id,
        status=JobStatus.PROCESSED,
        repetitions=1,
        number_of_shots=1,
    )
    session.add(job)
    session.flush()  # populate job.id

    scan_param = ScanParameter(
        job_id=job.id,
        name=variable_id,
        variable_id=variable_id,
        scan_values=scan_values,
    )
    session.add(scan_param)

    run = JobRun(
        job_id=job.id,
        scheduled_time=scheduled_time,
        status=JobRunStatus.DONE,
    )
    session.add(run)
    session.flush()

    return job, run


def _hdf5_path(scheduled_time: datetime) -> str:
    """Return the HDF5 file path for a given scheduled time.

    Must match exactly how ``get_filename_by_job_id`` builds the name:
    ``f"{scheduled_time}.h5"``
    """
    results_dir = get_config().data.results_dir
    return f"{results_dir}/{scheduled_time}.h5"


def _write_hdf5(
    filepath: str,
    job_id: int,
    x: np.ndarray,
    y: np.ndarray,
    variable_id: str,
    result_channel: str,
) -> None:
    """Write a minimal ICON-compatible HDF5 file."""
    n = len(x)
    with h5py.File(filepath, "w") as h5:
        h5.attrs["number_of_data_points"] = n
        h5.attrs["number_of_shots"] = 1
        h5.attrs["experiment_id"] = _EXPERIMENT_ID
        h5.attrs["job_id"] = job_id
        h5.attrs["repetitions"] = 1
        h5.attrs["realtime_scan"] = False

        scan_dtype = [("timestamp", "S26"), (variable_id, np.float64)]
        scan_ds = h5.create_dataset(
            "scan_parameters",
            shape=(n, 1),
            dtype=scan_dtype,
            compression="gzip",
        )
        for i in range(n):
            scan_ds[i] = (b"2025-01-01T00:00:00.000000", x[i])

        result_dtype = [(result_channel, np.float64)]
        result_ds = h5.create_dataset(
            "result_channels",
            shape=(n,),
            dtype=result_dtype,
            compression="gzip",
        )
        result_ds[result_channel] = y
        result_ds.attrs["Plot window metadata"] = json.dumps([
            {"name": "Results", "index": 0, "type": "readout",
             "channel_names": [result_channel]},
        ])

        shot_group = h5.create_group("shot_channels")
        shot_group.attrs["Plot window metadata"] = json.dumps([])
        vector_group = h5.create_group("vector_channels")
        vector_group.attrs["Plot window metadata"] = json.dumps([])
        h5.create_group("parameters")


def _create_job(
    x: np.ndarray,
    y: np.ndarray,
    variable_id: str,
    result_channel: str,
    scheduled_time: datetime,
    label: str,
) -> int:
    """Create SQLite records + HDF5 file; return the job ID."""
    with sqlalchemy.orm.Session(engine) as session:
        source = _get_or_create_experiment_source(session)
        job, run = _insert_job_and_run(
            session,
            source,
            scan_values=x.tolist(),
            variable_id=variable_id,
            scheduled_time=scheduled_time,
        )
        session.commit()
        job_id = job.id

    filepath = _hdf5_path(scheduled_time)
    _write_hdf5(filepath, job_id, x, y, variable_id, result_channel)
    print(f"[{label}] job_id={job_id}  file={filepath}")
    return job_id


# ---------------------------------------------------------------------------
# Curve generators — one per scenario
# ---------------------------------------------------------------------------

# Use a fixed base time and offset each scenario by a minute so filenames
# don't collide even if the script is re-run on the same second.
_BASE_TIME = datetime(2025, 6, 1, 12, 0, 0)


def generate_clean_lorentzian() -> int:
    """Clean Lorentzian peak (y0=1, A=5, x0=150 MHz, gamma=5 MHz)."""
    x = np.linspace(100, 200, 100)
    y = 1.0 + 5.0 / (1 + ((x - 150.0) / 5.0) ** 2)
    y += np.random.default_rng(42).normal(0, 0.05, len(x))
    return _create_job(
        x, y,
        variable_id="frequency",
        result_channel="counts",
        scheduled_time=_BASE_TIME,
        label="lorentzian_clean",
    )


def generate_noisy_lorentzian() -> int:
    """Noisy Lorentzian peak (same params, noise=1.0)."""
    x = np.linspace(100, 200, 100)
    y = 1.0 + 5.0 / (1 + ((x - 150.0) / 5.0) ** 2)
    y += np.random.default_rng(42).normal(0, 1.0, len(x))
    return _create_job(
        x, y,
        variable_id="frequency",
        result_channel="counts",
        scheduled_time=_BASE_TIME + timedelta(minutes=1),
        label="lorentzian_noisy",
    )


def generate_w_shape() -> int:
    """W-shaped curve: two Lorentzian dips at 130 and 170 MHz."""
    x = np.linspace(100, 200, 200)
    y = (
        10.0
        - 5.0 / (1 + ((x - 130.0) / 3.0) ** 2)
        - 5.0 / (1 + ((x - 170.0) / 3.0) ** 2)
    )
    y += np.random.default_rng(42).normal(0, 0.1, len(x))
    return _create_job(
        x, y,
        variable_id="frequency",
        result_channel="counts",
        scheduled_time=_BASE_TIME + timedelta(minutes=2),
        label="w_shape",
    )


def generate_gaussian() -> int:
    """Gaussian peak (y0=2, A=3, x0=5, sigma=0.8)."""
    x = np.linspace(0, 10, 100)
    y = 2.0 + 3.0 * np.exp(-((x - 5.0) ** 2) / (2 * 0.8**2))
    y += np.random.default_rng(42).normal(0, 0.05, len(x))
    return _create_job(
        x, y,
        variable_id="detuning",
        result_channel="fluorescence",
        scheduled_time=_BASE_TIME + timedelta(minutes=3),
        label="gaussian",
    )


def generate_poly2() -> int:
    """Quadratic curve (a=2, b=-3, c=1)."""
    x = np.linspace(-5, 5, 50)
    y = 2.0 * x**2 - 3.0 * x + 1.0
    y += np.random.default_rng(42).normal(0, 0.5, len(x))
    return _create_job(
        x, y,
        variable_id="voltage",
        result_channel="counts",
        scheduled_time=_BASE_TIME + timedelta(minutes=4),
        label="poly2",
    )


def generate_harmonic() -> int:
    """Harmonic oscillation (y0=1, A=2, omega=4, phi=0.5)."""
    x = np.linspace(0, 10, 200)
    y = 1.0 + 2.0 * np.cos(4.0 * x + 0.5)
    y += np.random.default_rng(42).normal(0, 0.1, len(x))
    return _create_job(
        x, y,
        variable_id="time",
        result_channel="population",
        scheduled_time=_BASE_TIME + timedelta(minutes=5),
        label="harmonic",
    )


def generate_damped_harmonic() -> int:
    """Damped harmonic (y0=1, A=2, k=-0.3, omega=4, phi=0.5)."""
    x = np.linspace(0, 10, 200)
    y = 1.0 + np.exp(-0.3 * x) * 2.0 * np.cos(4.0 * x + 0.5)
    y += np.random.default_rng(42).normal(0, 0.05, len(x))
    return _create_job(
        x, y,
        variable_id="time",
        result_channel="population",
        scheduled_time=_BASE_TIME + timedelta(minutes=6),
        label="damped_harmonic",
    )


def _insert_job_and_run_2d(  # noqa: PLR0913
    session: sqlalchemy.orm.Session,
    source: ExperimentSource,
    scan_values_x: list[float],
    variable_id_x: str,
    scan_values_y: list[float],
    variable_id_y: str,
    scheduled_time: datetime,
) -> tuple[Job, JobRun]:
    """Insert a Job with two ScanParameters and a JobRun; return both ORM objects."""
    job = Job(
        experiment_source_id=source.id,
        status=JobStatus.PROCESSED,
        repetitions=1,
        number_of_shots=1,
    )
    session.add(job)
    session.flush()

    scan_param_x = ScanParameter(
        job_id=job.id,
        name=variable_id_x,
        variable_id=variable_id_x,
        scan_values=scan_values_x,
    )
    scan_param_y = ScanParameter(
        job_id=job.id,
        name=variable_id_y,
        variable_id=variable_id_y,
        scan_values=scan_values_y,
    )
    session.add(scan_param_x)
    session.add(scan_param_y)

    run = JobRun(
        job_id=job.id,
        scheduled_time=scheduled_time,
        status=JobRunStatus.DONE,
    )
    session.add(run)
    session.flush()

    return job, run


def _write_hdf5_2d(  # noqa: PLR0913
    filepath: str,
    job_id: int,
    x_flat: np.ndarray,
    y_flat: np.ndarray,
    z: np.ndarray,
    variable_id_x: str,
    variable_id_y: str,
    result_channel: str,
) -> None:
    """Write a minimal ICON-compatible HDF5 file for a 2D scan."""
    n = len(z)
    with h5py.File(filepath, "w") as h5:
        h5.attrs["number_of_data_points"] = n
        h5.attrs["number_of_shots"] = 1
        h5.attrs["experiment_id"] = _EXPERIMENT_ID
        h5.attrs["job_id"] = job_id
        h5.attrs["repetitions"] = 1
        h5.attrs["realtime_scan"] = False

        scan_dtype = [
            ("timestamp", "S26"),
            (variable_id_x, np.float64),
            (variable_id_y, np.float64),
        ]
        scan_ds = h5.create_dataset(
            "scan_parameters",
            shape=(n, 1),
            dtype=scan_dtype,
            compression="gzip",
        )
        for i in range(n):
            scan_ds[i] = (b"2025-01-01T00:00:00.000000", x_flat[i], y_flat[i])

        result_dtype = [(result_channel, np.float64)]
        result_ds = h5.create_dataset(
            "result_channels",
            shape=(n,),
            dtype=result_dtype,
            compression="gzip",
        )
        result_ds[result_channel] = z
        result_ds.attrs["Plot window metadata"] = json.dumps([
            {"name": "Results", "index": 0, "type": "readout",
             "channel_names": [result_channel]},
        ])

        shot_group = h5.create_group("shot_channels")
        shot_group.attrs["Plot window metadata"] = json.dumps([])
        vector_group = h5.create_group("vector_channels")
        vector_group.attrs["Plot window metadata"] = json.dumps([])
        h5.create_group("parameters")


def generate_2d_gaussian() -> int:
    """2D Gaussian peak over frequency x amplitude grid.

    z = A * exp(-((x-x0)^2/(2*sx^2) + (y-y0)^2/(2*sy^2))) + offset
    with A=5, x0=150, y0=5, sx=15, sy=2, offset=1.
    """
    variable_id_x = "frequency"
    variable_id_y = "amplitude"
    result_channel = "counts"
    scheduled_time = _BASE_TIME + timedelta(minutes=7)

    nx, ny = 20, 15
    x_vals = np.linspace(100, 200, nx)
    y_vals = np.linspace(0, 10, ny)

    # Outer loop over x, inner loop over y
    x_grid, y_grid = np.meshgrid(x_vals, y_vals, indexing="ij")
    x_flat = x_grid.ravel()
    y_flat = y_grid.ravel()

    # 2D Gaussian
    amp, x0, y0, sx, sy, offset = 5.0, 150.0, 5.0, 15.0, 2.0, 1.0
    z = amp * np.exp(-(
        (x_flat - x0) ** 2 / (2 * sx**2)
        + (y_flat - y0) ** 2 / (2 * sy**2)
    )) + offset
    z += np.random.default_rng(42).normal(0, 0.1, len(z))

    with sqlalchemy.orm.Session(engine) as session:
        source = _get_or_create_experiment_source(session)
        job, run = _insert_job_and_run_2d(
            session,
            source,
            scan_values_x=x_vals.tolist(),
            variable_id_x=variable_id_x,
            scan_values_y=y_vals.tolist(),
            variable_id_y=variable_id_y,
            scheduled_time=scheduled_time,
        )
        session.commit()
        job_id = job.id

    filepath = _hdf5_path(scheduled_time)
    _write_hdf5_2d(
        filepath, job_id, x_flat, y_flat, z,
        variable_id_x, variable_id_y, result_channel,
    )
    print(f"[2d_gaussian] job_id={job_id}  file={filepath}")
    return job_id


if __name__ == "__main__":
    print(f"Results dir : {get_config().data.results_dir}")
    print(f"Database    : {get_config().databases.sqlite.file}")
    print()

    generate_clean_lorentzian()
    generate_noisy_lorentzian()
    generate_w_shape()
    generate_gaussian()
    generate_poly2()
    generate_harmonic()
    generate_damped_harmonic()
    generate_2d_gaussian()

    print("\nDone. Open http://localhost:8004 and go to the Data page to see the jobs.")
