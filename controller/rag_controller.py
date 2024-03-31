from fastapi import APIRouter, Depends, Request

from service.rag_service import RagService
from model.dto import RagFileIndexDTO, ResData, RagQueryDTO

rag_router = APIRouter()


@rag_router.post("/api/rag/index")
def index(request: Request, data: RagFileIndexDTO, service: RagService = Depends()):
    rag_file_index_vo = service.index_pdf(data)
    return ResData.success(rag_file_index_vo.to_dict())


@rag_router.post("/api/rag/query")
def query(request: Request, data: RagQueryDTO, service: RagService = Depends()):
    rag_query_vo = service.query(data)
    return ResData.success(rag_query_vo.to_dict())
