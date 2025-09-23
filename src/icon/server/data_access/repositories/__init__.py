"""This module contains the repository layer for ICON's data access.

Repositories encapsulate database access logic and hide the underlying persistence
technology (SQLAlchemy sessions, InfluxDB queries, etc.) from the rest of the
application. They expose simple, intention-revealing methods for creating, retrieving,
and updating domain objects, while emitting Socket.IO events when relevant.

By using repositories, controllers and services can work with high-level operations
(e.g. "submit a job", "update a device") without needing to know how the data is stored
or which database backend is used. This keeps the codebase modular, easier to maintain,
and allows the persistence layer to evolve independently of business logic.
"""
