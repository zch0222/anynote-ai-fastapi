from fastapi import FastAPI
from core.logger import get_logger

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    logger = get_logger()
    logger.info("fastapi start")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app="app:app", host="127.0.0.1", port=8000, workers=4)
