from fastapi import APIRouter, Depends, Request
from core.redis_server import RedisServer

from service.data_connect_service import DataConnectService

data_connect_router = APIRouter()


def get_data_connect_service(request: Request) -> DataConnectService:
    return DataConnectService(RedisServer(request.app.state.redis))

