"""Tests for the SQLAlchemy dict encoder used in socket.io emit payloads."""

import json

import pydase.units as u
import sqlalchemy
import sqlalchemy.orm

from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from tests.server.conftest import SeedJob


def test_encode_job_with_quantity_scan_values(
    database: sqlalchemy.engine.Engine, seed_job: SeedJob
) -> None:
    job_id, _ = seed_job(
        job_status=JobStatus.SUBMITTED, run_status=JobRunStatus.PENDING
    )

    with sqlalchemy.orm.Session(database) as session:
        job = session.get(Job, job_id)
        assert job is not None
        job.scan_parameters.append(
            ScanParameter(
                name="Voltage",
                variable_id="voltage",
                scan_values=[
                    u.convert_to_quantity(1.0, "V"),
                    u.convert_to_quantity(2.5, "V"),
                ],
            )
        )
        session.commit()

    # Same fetch path as the `job.new` emit in `JobRepository.submit_job`.
    job = JobRepository.get_job_by_id(
        job_id=job_id, load_experiment_source=True, load_scan_parameters=True
    )
    encoded = SQLAlchemyDictEncoder.encode(job)

    # The payload must be JSON-serializable for the socket.io emit bus.
    assert json.dumps(encoded)

    assert encoded["scan_parameters"][0]["scan_values"] == [1.0, 2.5]
