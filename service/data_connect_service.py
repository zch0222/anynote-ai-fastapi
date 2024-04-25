from core.redis_server import RedisServer


class DataConnectService:

    def __init__(self, redis_server: RedisServer):
        self.redis_server = redis_server
        pass
