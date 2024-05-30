import pydase

from icon.server.api.api_service import APIService

pydase.Server(APIService()).run()
