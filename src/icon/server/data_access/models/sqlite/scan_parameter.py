import json
from typing import TYPE_CHECKING, Any, cast

import pydase.units as u
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm

from icon.serialization.deserializer import IconDeserializer
from icon.serialization.serializer import IconSerializer
from icon.server.data_access.experiment_data import DatabaseValueType
from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from pydase.utils.serialization.types import SerializedObject

    from icon.server.data_access.models.sqlite.device import Device
    from icon.server.data_access.models.sqlite.job import Job


class JSONEncodedList(sqlalchemy.TypeDecorator[Any]):
    """Custom SQLAlchemy type for storing lists as JSON-encoded strings.

    Stores Python lists as JSON-encoded text in the database and transparently decodes
    them back into lists on retrieval.
    """

    impl = sqlalchemy.TEXT

    cache_ok = True  # Cache optimization

    def process_bind_param(self, value: Any, dialect: sqlalchemy.Dialect) -> str:  # noqa: ARG002
        if value is None:
            value = []
        if not isinstance(value, list):
            raise TypeError("Value must be a list.")
        return json.dumps(value, cls=SpecialEncoder)

    def process_result_value(
        self,
        value: Any,
        dialect: sqlalchemy.Dialect,  # noqa: ARG002
    ) -> list[DatabaseValueType | u.Quantity]:
        if value is None:
            return []
        return json.loads(value, object_hook=special_decoder)


class SpecialEncoder(json.JSONEncoder):
    """JSON encoder for special cases like pydase.Quantity."""

    def default(self, obj: object) -> Any:
        if isinstance(obj, u.Quantity):
            return IconSerializer._serialize_quantity(obj)
        return super().default(obj)


def special_decoder(dct: dict[str, Any]) -> Any:
    if dct.get("type") == "Quantity":
        return IconDeserializer.deserialize_quantity(cast("SerializedObject", dct))
    return dct


class ScanParameter(Base):
    """SQLAlchemy model for scan parameters.

    Represents a parameter scanned during a job execution. Each parameter is linked to a
    job and optionally to a device.
    """

    __tablename__ = "scan_parameters"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    """Primary key identifier for the scan parameter."""

    job_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("job_submissions.id")
    )
    """Foreign key referencing the job this parameter belongs to."""

    job: sqlalchemy.orm.Mapped["Job"] = sqlalchemy.orm.relationship(
        back_populates="scan_parameters"
    )
    """Relationship to the job."""

    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(nullable=False)
    """Human-friendly display name persisted at submission time."""

    variable_id: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column()
    """Identifier of the parameter being scanned."""

    scan_values: sqlalchemy.orm.Mapped[list[DatabaseValueType | u.Quantity]] = (
        sqlalchemy.orm.mapped_column(JSONEncodedList, nullable=False)
    )
    """List of values scanned for this parameter (stored as JSON).

    Device scans of Quantity-typed parameters persist their values as pydase
    Quantities (magnitude + unit); everything downstream flattens them to the
    plain magnitude, and the unit is re-attached at the device boundary.
    """

    device_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("devices.id"), nullable=True
    )
    """Foreign key referencing the associated device, if any."""

    device: sqlalchemy.orm.Mapped["Device | None"] = sqlalchemy.orm.relationship(
        back_populates="scan_parameters", lazy="joined"
    )
    """Relationship to the device associated with this parameter."""
    realtime: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        default=False, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Parameter '{self.unique_id()}'>"

    def unique_id(self) -> str:
        """Return a unique identifier for the parameter.

        Returns:
            `"Device(<device_name>) <variable_id>"` if a device is associated, otherwise
                just `<variable_id>`.
        """
        return (
            f"Device({self.device.name}) {self.variable_id}"
            if self.device is not None
            else self.variable_id
        )

    @property
    def unit(self) -> str | None:
        """Unit of the scan values, if they are pydase Quantities.

        Returns:
            The unit as a string (e.g. ``"MHz"``), or None for plain values.
        """
        if self.scan_values and isinstance(self.scan_values[0], u.Quantity):
            return str(self.scan_values[0].units)
        return None


@sqlalchemy.event.listens_for(ScanParameter, "before_insert")
def receive_before_insert(
    mapper: sqlalchemy.orm.Mapper[ScanParameter],  # noqa: ARG001
    connection: sqlalchemy.engine.Connection,  # noqa: ARG001
    target: ScanParameter,
) -> None:
    if target.realtime and target.variable_id != "Real Time":
        raise ValueError(
            f"Cannot set 'realtime' on {ScanParameter} with id {target.variable_id!r}"
            " != 'Real Time'"
        )


def contains_realtime_parameter(params: list[ScanParameter]) -> bool:
    return any(sp.realtime for sp in params)
