import logging

import sqlalchemy.orm

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.sqlite.ttl_mask_state import TTLMaskState

logger = logging.getLogger(__name__)

_SINGLETON_ID = 1


class TTLRepository:
    """Data access object for the TTL mask state table.

    The table always contains at most one row (id=1), representing the last
    mask pair written to the Zedboard FPGA.
    """

    def get_masks(self) -> tuple[int, int]:
        """Return (high_mask, low_mask); returns (0, 0) if no row exists yet."""
        with sqlalchemy.orm.Session(engine) as session:
            row = session.get(TTLMaskState, _SINGLETON_ID)
            if row is None:
                return 0, 0
            return row.high_mask, row.low_mask

    def save_masks(self, high_mask: int, low_mask: int) -> None:
        """Upsert the single TTL state row with new mask values."""
        with sqlalchemy.orm.Session(engine) as session:
            row = session.get(TTLMaskState, _SINGLETON_ID)
            if row is None:
                row = TTLMaskState(id=_SINGLETON_ID, high_mask=high_mask, low_mask=low_mask)
                session.add(row)
            else:
                row.high_mask = high_mask
                row.low_mask = low_mask
            session.commit()
            logger.debug(
                "Saved TTL masks: high=0x%08x low=0x%08x", high_mask, low_mask
            )
