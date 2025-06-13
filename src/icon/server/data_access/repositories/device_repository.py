import logging
from collections.abc import Sequence

import sqlalchemy.orm.session

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.device import Device

logger = logging.getLogger(__name__)


class DeviceRepository:
    @staticmethod
    def add_device(*, device: Device) -> Device:
        """Create a new device instance in the database and returns this instance."""

        with sqlalchemy.orm.session.Session(engine) as session:
            session.add(device)
            session.commit()
            session.refresh(device)
            logger.debug("Added new device %s", device)
        return device

    @staticmethod
    def update_device_status(*, device: Device, status: DeviceStatus) -> Device:
        """Updates a device instance in the database and returns this instance."""

        with sqlalchemy.orm.session.Session(engine) as session:
            stmt = (
                sqlalchemy.update(Device)
                .where(Device.id == device.id)
                .values(status=status)
                .returning(Device)
            )
            device = session.execute(stmt).scalar_one()
            session.commit()

            logger.debug("Updated device %s", device)
        return device

    @staticmethod
    def get_device_by_status(
        *,
        status: DeviceStatus | None = None,
    ) -> Sequence[Device]:
        """Gets all the Device instances filtered by status."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = sqlalchemy.select(Device)

            if status is not None:
                stmt = stmt.where(Device.status == status)

            return session.execute(stmt).scalars().all()

    @staticmethod
    def get_device_by_id(
        *,
        id: int,
    ) -> Device:
        """Gets the Device instances with given id."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = sqlalchemy.select(Device).where(Device.id == id)

            return session.execute(stmt).scalar_one()

    @staticmethod
    def get_device_by_name(
        *,
        name: str,
    ) -> Device:
        """Gets the Device instances with given name."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = sqlalchemy.select(Device).where(Device.name == name)

            return session.execute(stmt).scalar_one()

    @staticmethod
    def get_all_device_names() -> Sequence[str]:
        """Return a list of all device names."""
        with sqlalchemy.orm.Session(engine) as session:
            stmt = sqlalchemy.select(Device.name)
            return session.execute(stmt).scalars().all()
