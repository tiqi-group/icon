"""This module defines the API layer of ICON, implemented as a
[`pydase.DataService`][pydase.DataService].

The main entry point is the [`APIService`][icon.server.api.api_service.APIService],
which is exposed by the [`IconServer`][icon.server.web_server.icon_server.IconServer].
The `IconServer` itself is a [`pydase.Server`][pydase.Server] hosting the API.

### Structure
The `APIService` aggregates multiple "controller" services as attributes. Each
controller is itself a `pydase.DataService` exposing related API methods.

### Background tasks
Controllers can define periodic
[`pydase` tasks](https://pydase.readthedocs.io/en/latest/user-guide/Tasks/),
which are asyncio tasks automatically started with the service.
"""
