from llama_index.core import VectorStoreIndex, load_index_from_storage, StorageContext, SimpleDirectoryReader
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.llms.openai import OpenAI

from llama_index.core.agent import AgentRunner, ReActAgent
from llama_index.agent.openai import OpenAIAgentWorker, OpenAIAgent
from llama_index.agent.openai import OpenAIAgentWorker
from core.config import OPENAI_API_KEY
from core.redis_server import RedisServer
from model.dto import RagFileIndexDTO, RagQueryDTO
from utils import download_file
import os
from constants.rag_constants import RAG_PDF_DIR, RAG_PERSIST_DIR
from model.dto import FileDownloadDTO
from exceptions import BusinessException
from model.vo import RagFileIndexVO, RagQueryVO
from core.logger import get_logger
from core.config import RAG_LLM_MODEL


class RagService:

    def __init__(self):
        self.llm = OpenAI(model=RAG_LLM_MODEL)
        self.logger = get_logger()

    def get_query_engine_tool(self, hash_value: str):
        vector_index_path = f"{RAG_PERSIST_DIR}/{hash_value}"
        if not os.path.exists(vector_index_path):
            raise BusinessException("文件索引不存在")

        vector_index = load_index_from_storage(
            StorageContext.from_defaults(persist_dir=vector_index_path),
        )

        query_engine = vector_index.as_query_engine(similarity_top_k=3, llm=self.llm)
        query_engine_tool = QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name=hash_value,
                description=(
                    "File query engine"
                ),
            ),
        )
        return query_engine_tool

    def load_documents(self, file_paths: list[str]):
        return SimpleDirectoryReader(input_files=file_paths).load_data()

    def build_vector_index(self, file_download_dto: FileDownloadDTO):

        vector_index_path = f"{RAG_PERSIST_DIR}/{file_download_dto.hash_value}"
        if not os.path.exists(vector_index_path):
            self.logger.info(f"Start index: {vector_index_path}")
            vector_index = VectorStoreIndex.from_documents(self.load_documents([file_download_dto.file_path]))
            vector_index.storage_context.persist(persist_dir=vector_index_path)
        return vector_index_path

    def index_pdf(self, rag_file_index_dto: RagFileIndexDTO) -> RagFileIndexVO:
        file_download_dto = download_file(rag_file_index_dto.file_path, RAG_PDF_DIR)
        if not file_download_dto:
            raise BusinessException("下载文件失败")
        self.build_vector_index(file_download_dto)
        return RagFileIndexVO(hash=file_download_dto.hash_value)

    def query(self, rag_query_dto: RagQueryDTO) -> RagQueryVO:
        self.logger.info(f"START RAG QUERY, hash: {rag_query_dto.file_hash}, prompt: {rag_query_dto.prompt}")
        query_engine = self.get_query_engine_tool(rag_query_dto.file_hash)
        agent = ReActAgent.from_tools(
            [query_engine], llm=self.llm, verbose=True, max_iterations=20
        )
        response = agent.chat(rag_query_dto.prompt)
        self.logger.info(f"END RAG QUERY, hash: {rag_query_dto.file_hash}, prompt: {rag_query_dto.prompt}, response: {str(response)}")
        return RagQueryVO(message=str(response))
