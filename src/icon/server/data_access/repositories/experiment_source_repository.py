import logging

import sqlalchemy.orm

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource

logger = logging.getLogger(__name__)


class ExperimentSourceRepository:
    @staticmethod
    def get_or_create_experiment(
        *,
        experiment_source: ExperimentSource,
    ) -> ExperimentSource:
        """Gets the data of an already existing instance in the database or creates a
        new instance if it does not exist, and returns this instance.
        """

        with sqlalchemy.orm.Session(engine) as session:
            # Check if the experiment exists
            experiment = (
                session.query(ExperimentSource)
                .filter_by(experiment_id=experiment_source.experiment_id)
                .first()
            )

            # If it doesn't exist, create it
            if not experiment:
                experiment = experiment_source
                session.add(experiment)
                session.commit()
                session.refresh(experiment)  # Refresh to get the ID
                logger.debug("Inserted new experiment %s", experiment)
        return experiment
