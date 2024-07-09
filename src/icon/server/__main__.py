import pydase
import pydase.server.web_server.sio_setup

import icon.serialization.deserializer
import icon.serialization.serializer
from icon.server.api.api_service import APIService

pydase.server.web_server.sio_setup.loads = icon.serialization.deserializer.loads
pydase.server.web_server.sio_setup.dump = icon.serialization.serializer.dump

pydase.Server(APIService()).run()
