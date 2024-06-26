from fastapi import FastAPI
from core.logger import get_logger
from controller.rag_controller import rag_router
from controller.data_connect_controller import data_connect_router
from controller.pandas_controller import pandas_router
from controller.whisper_controller import whisper_router
from starlette.requests import Request
from starlette.responses import JSONResponse
from model.dto import ResData
from exceptions import BusinessException
from core.redis import get_redis_pool
from core.config import HOST
import redis
from core.executor import executor



app = FastAPI()


# 路由
app.include_router(rag_router)
app.include_router(pandas_router)
app.include_router(data_connect_router)
app.include_router(whisper_router)


# 业务异常处理
@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    logger = get_logger()
    logger.exception("An error occurred while processing request")
    return JSONResponse(
        status_code=200,
        content=ResData.error(exc.message)
    )


# 全局异常处理
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logger = get_logger()
    logger.exception("An error occurred while processing request")
    return JSONResponse(
        status_code=200,
        content=ResData.error("An error occurred while processing requests")
    )


@app.on_event("startup")
async def startup_event():
    logger = get_logger()
    app.state.redis: redis.Redis = get_redis_pool()
    logger.info("fastapi start")


@app.on_event("shutdown")
async def shutdown_event():
    logger = get_logger()
    app.state.redis.connection_pool.disconnect()
    logger.info("Redis disconnected")
    executor.shutdown()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app="app:app", host=HOST, port=8000, workers=4)
