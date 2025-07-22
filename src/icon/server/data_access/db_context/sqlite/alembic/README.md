# Alembic

We use [alembic](https://alembic.sqlalchemy.org/en/latest/) as our database migration 
tool, i.e. tracking granular changes to your database schema, much like Git does for the
codebase. This makes it easier to manage, review, and roll back schema changes if 
necessary.

Alembic can automatically generate migration scripts by comparing the current database 
schema with the SQLAlchemy models.

## Usage

1. Update the database schema

    The SQLite database schema is described [here](../src/icon/server/data_access/models/sqlite/).
    If you add a model, make sure you add it to the `__init__.py` file s.t. alembic can
    pick it up.

2. Autogenerate the revision:

    ```bash
    # Install the required dependencies
    poetry install --with dev --all-extras
    poetry shell
    # actual migration
    alembic revision --autogenerate -m "<description>"
    ```
3. Check the revision manually in the [versions](./versions/) folder. 

    **Note** that alembic cannot detect the following changes:

    - Changes of table name.
    - Changes of column name.
    - Anonymously named constraints. 
    - CHECK constraints.

4. If the migration looks good, apply it

    ```bash
    alembic upgrade head
    ```
