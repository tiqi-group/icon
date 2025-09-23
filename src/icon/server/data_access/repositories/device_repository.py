import enum
import logging
from collections.abc import Sequence

import sqlalchemy.exc
import sqlalchemy.orm.session
from sqlalchemy import select, update

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


class NoDeviceFoundError(Exception):
    """Raised when a device could not be found by the given identifier."""


class DeviceRepository:
    """Repository for `Device` entities.

    Provides methods to create, update, and query devices in the SQLite database.
    All methods open their own SQLAlchemy session and return detached ORM objects.
    """

    @staticmethod
    def add_device(*, device: Device) -> Device:
        """Insert a new device into the database.

        Args:
            device: Device instance to persist.

        Returns:
            The persisted device with database-generated fields (e.g., `id`) populated.
        """

        with sqlalchemy.orm.session.Session(engine) as session:
            session.add(device)
            session.commit()
            session.refresh(device)
            logger.debug("Added new device %s", device)

        emit_queue.put(
            {
                "event": "device.new",
                "data": {
                    "device": SQLAlchemyDictEncoder.encode(obj=device),
                },
            }
        )

        return device

    @staticmethod
    def update_device(
        *,
        name: str,
        url: str | None = None,
        status: DeviceStatus | None = None,
        retry_attempts: int | None = None,
        retry_delay_seconds: float | None = None,
    ) -> Device:
        """Update an existing device by name.

        Args:
            name: Unique device name.
            url: New device URL (cannot change if the device is enabled).
            status: New device status (enabled/disabled).
            retry_attempts: Updated retry attempt count.
            retry_delay_seconds: Updated retry delay in seconds.

        Returns:
            The updated device.

        Raises:
            RuntimeError: If attempting to change the URL of an enabled device.
            NoDeviceFoundError: If no device with the given name exists.
        """

        updated_properties = {
            name: new_value
            for name, new_value in {
                "url": url,
                "status": status if status is not None else None,
                "retry_attempts": retry_attempts,
                "retry_delay_seconds": retry_delay_seconds,
            }.items()
            if new_value is not None
        }

        if "url" in updated_properties:
            device = DeviceRepository.get_device_by_name(name=name)
            if device.status == DeviceStatus.ENABLED:
                raise RuntimeError("Cannot change url of an enabled device")

        with sqlalchemy.orm.Session(engine) as session:
            session.execute(
                update(Device).where(Device.name == name).values(updated_properties)
            )
            session.commit()

            device = session.execute(
                select(Device).where(Device.name == name)
            ).scalar_one()
            session.expunge(device)

            logger.debug("Updated device %s", device)

        serialized_properties = {
            key: value.value if isinstance(value, enum.Enum) else value
            for key, value in updated_properties.items()
        }

        if "status" in updated_properties:
            serialized_properties["reachable"] = False

        emit_queue.put(
            {
                "event": "device.update",
                "data": {
                    "device_name": device.name,
                    "updated_properties": serialized_properties,
                },
            }
        )

        return device

    @staticmethod
    def get_devices_by_status(
        *,
        status: DeviceStatus | None = None,
    ) -> Sequence[Device]:
        """Return devices filtered by status.

        Args:
            status: Optional device status to filter on.

        Returns:
            All devices matching the filter (or all devices if no filter is given).
        """

        with sqlalchemy.orm.Session(engine) as session:
            stmt = sqlalchemy.select(Device)

            if status is not None:
                stmt = stmt.where(Device.status == status)

            return session.execute(stmt).scalars().all()

    @staticmethod
    def get_device_by_id(*, id: int) -> Device:
        """Return a device by database ID.

        Args:
            id: Primary key identifier of the device.

        Returns:
            The matching device.

        Raises:
            NoResultFound: If no device exists with the given ID.
        """

        with sqlalchemy.orm.Session(engine) as session:
            stmt = sqlalchemy.select(Device).where(Device.id == id)
            return session.execute(stmt).scalar_one()

    @staticmethod
    def get_device_by_name(*, name: str) -> Device:
        """Return a device by unique name.

        Args:
            name: Device name.

        Returns:
            The matching device.

        Raises:
            NoDeviceFoundError: If no device exists with the given name.
        """

        try:
            with sqlalchemy.orm.Session(engine) as session:
                stmt = sqlalchemy.select(Device).where(Device.name == name)
                return session.execute(stmt).scalar_one()
        except sqlalchemy.exc.NoResultFound:
            raise NoDeviceFoundError(
                f"Device with name {name!r} does not exist.",
            )

    @staticmethod
    def get_all_device_names() -> Sequence[str]:
        """Return the names of all devices.

        Returns:
            List of device names.
        """

        with sqlalchemy.orm.Session(engine) as session:
            stmt = sqlalchemy.select(Device.name)
            return session.execute(stmt).scalars().all()
