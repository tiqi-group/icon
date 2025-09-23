import logging

import sqlalchemy.orm

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource

logger = logging.getLogger(__name__)


class ExperimentSourceRepository:
    """Repository for `ExperimentSource` entities.

    Provides methods to query and persist experiment sources in the database.
    Encapsulates the SQLAlchemy session and query logic.
    """

    @staticmethod
    def get_or_create_experiment(
        *,
        experiment_source: ExperimentSource,
    ) -> ExperimentSource:
        """Return an existing experiment source or create it if not found.

        Args:
            experiment_source: The experiment source to look up by `experiment_id`. If
                no matching row exists, this instance is inserted into the database.

        Returns:
            The existing or newly created experiment source.
        """

        with sqlalchemy.orm.Session(engine) as session:
            experiment = (
                session.query(ExperimentSource)
                .filter_by(experiment_id=experiment_source.experiment_id)
                .first()
            )

            if not experiment:
                experiment = experiment_source
                session.add(experiment)
                session.commit()
                session.refresh(experiment)  # Refresh to get the ID
                logger.debug("Inserted new experiment %s", experiment)

        return experiment
