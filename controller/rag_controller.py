from fastapi import APIRouter, Depends, Query, Request

rag_router = APIRouter()


@rag_router.post("/api/rag/index")
def index(request: Request):
    return {"message": "Hello World"}
