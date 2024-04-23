# import uuid

from llama_index.core import VectorStoreIndex, load_index_from_storage, StorageContext, SimpleDirectoryReader
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.llms.openai import OpenAI
from llama_index.llms.ollama import Ollama
from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.core.node_parser import SentenceSplitter
import time
import json
from llama_index.embeddings.openai import OpenAIEmbedding
# from llama_index.core.postprocessor import MetadataReplacementPostProcessor
#
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
# from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core.agent import AgentRunner, ReActAgent
# from llama_index.agent.openai import OpenAIAgentWorker, OpenAIAgent
# from llama_index.agent.openai import OpenAIAgentWorker
# from core.config import OPENAI_API_KEY
# from core.redis_server import RedisServer
from model.dto import RagFileIndexDTO, RagQueryDTO
from utils import download_file
import os
from constants.rag_constants import RAG_PDF_DIR, RAG_PERSIST_DIR, RAG_TASK_REDIS_PREFIX
from model.dto import FileDownloadDTO
from exceptions import BusinessException
from model.vo import RagFileIndexVO, RagQueryVO
from core.logger import get_logger
from core.config import RAG_LLM_MODEL, EMBEDDING_MODEL
from core.redis_server import RedisServer
from llama_index.core import Settings
# from core.redis import get_redis_pool
import asyncio
# from model.dto import ResData


class RagService:

    def get_model(self):
        if "mistral" == RAG_LLM_MODEL:
            return Ollama(model="mistral", request_timeout=300.0)
        elif "llama3" == RAG_LLM_MODEL:
            return Ollama(model="llama3", request_timeout=300.0)
        else:
            return OpenAI(model=RAG_LLM_MODEL)

    def get_embed_model(self):
        # if "mistral" == EMBEDDING_MODEL:
        #     return OllamaEmbedding(
        #         model_name="mistral",
        #         base_url="http://localhost:11434",
        #         ollama_additional_kwargs={"mirostat": 0},
        #     )
        # elif "sentence-transformers/all-mpnet-base-v2" == EMBEDDING_MODEL:
        #     return HuggingFaceEmbedding(
        #         model_name="sentence-transformers/all-mpnet-base-v2", max_length=512
        #     )
        if "BAAI/bge-small-zh-v1.5" == EMBEDDING_MODEL:
            self.logger.info("Using BAAI/bge-small")
            return HuggingFaceEmbedding(model_name=EMBEDDING_MODEL)

        if EMBEDDING_MODEL is not None:
            print(EMBEDDING_MODEL)
            return OpenAIEmbedding(model_name=EMBEDDING_MODEL)
        return OpenAIEmbedding(model_name="text-embedding-ada-002")

    def __init__(self, redis_server: RedisServer):
        self.redis_server = redis_server
        self.llm = self.get_model()
        # self.embed_model = self.get_embed_model()
        self.logger = get_logger()
        Settings.embed_model = self.get_embed_model()

    def get_query_engine_tool(self, hash_value: str, file_name: str, author: str, category: str, description: str):
        vector_index_path = f"{RAG_PERSIST_DIR}/{hash_value}"
        if not os.path.exists(vector_index_path):
            raise BusinessException("文件索引不存在")

        vector_index = load_index_from_storage(
            StorageContext.from_defaults(persist_dir=vector_index_path),
        )

        query_engine = vector_index.as_query_engine(
            similarity_top_k=2,
            llm=self.llm
            # node_postprocessors=[
            #     MetadataReplacementPostProcessor(target_metadata_key="window")
            # ],
        )
        query_engine_tool = QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name="RAG",
                description=(
                    f"file name is {file_name}, author is {author}, category is {category}, {description}"
                    f"{file_name}"
                ),
            ),
        )
        return query_engine_tool

    def load_documents(self, file_paths: list[str]):
        return SimpleDirectoryReader(input_files=file_paths).load_data()

    def get_node_parser(self):
        return SentenceWindowNodeParser.from_defaults(
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="original_text"
        )

    def get_base_node_parser(self):
        return SentenceSplitter()

    def build_vector_index(self, file_download_dto: FileDownloadDTO):

        vector_index_path = f"{RAG_PERSIST_DIR}/{file_download_dto.hash_value}"
        if not os.path.exists(vector_index_path):
            self.logger.info(f"Start index: {vector_index_path}")
            node_parser = self.get_base_node_parser()
            documents = self.load_documents([file_download_dto.file_path])
            nodes = node_parser.get_nodes_from_documents(documents)
            vector_index = VectorStoreIndex(nodes)
            vector_index.storage_context.persist(persist_dir=vector_index_path)
        return vector_index_path

    def index_pdf(self, rag_file_index_dto: RagFileIndexDTO) -> RagFileIndexVO:
        self.logger.info(f"Start indexing: {rag_file_index_dto.file_path}")
        file_download_dto = download_file(rag_file_index_dto.file_path, RAG_PDF_DIR)
        if not file_download_dto:
            raise BusinessException("下载文件失败")
        self.build_vector_index(file_download_dto)
        return RagFileIndexVO(hash=file_download_dto.hash_value)

    async def run_agent(self, query_engines, llm, prompt: str, task_id: str):
        try:
            agent = ReActAgent.from_tools(
                query_engines, llm=llm, max_iterations=20, verbose=True
            )
            response = await agent.achat(prompt)
        except Exception as e:
            self.logger.exception("RAG ERROR")
            self.redis_server.set(f"{RAG_TASK_REDIS_PREFIX}:{task_id}", {
                "id": task_id,
                "status": "failed",
                "result": ""
            })
            raise e
        self.redis_server.set(f"{RAG_TASK_REDIS_PREFIX}:{task_id}", {
            "id": task_id,
            "status": "finished",
            "result": str(response)
        })

    def query(self, rag_query_dto: RagQueryDTO, task_id: str):
        self.logger.info(f"START RAG QUERY, hash: {rag_query_dto.file_hash}, prompt: {rag_query_dto.prompt}")
        query_engine = self.get_query_engine_tool(rag_query_dto.file_hash, rag_query_dto.file_name,
                                                  rag_query_dto.author, rag_query_dto.category,
                                                  rag_query_dto.description)
        # agent = ReActAgent.from_tools(
        #     [query_engine], llm=self.llm, verbose=True, max_iterations=20
        # )
        self.redis_server.set(f"{RAG_TASK_REDIS_PREFIX}:{task_id}", {
            "id": task_id,
            "status": "running",
            "result": ""
        })
        prompt = f"请使用markdown格式回答我的问题，以下是我的问题：{rag_query_dto.prompt}"
        asyncio.create_task(self.run_agent([query_engine], self.llm, prompt, task_id))

    def get_rag_stream(self, task_id: str):
        rag_data = self.redis_server.get(f"{RAG_TASK_REDIS_PREFIX}:{task_id}")
        while rag_data is not None and rag_data["status"] == "running":
            # self.logger.info(f"{json.dumps(rag_data)}")
            yield 'id: {}\nevent: message\ndata: {}\n\n'.format(int(time.time()), json.dumps(rag_data))
            time.sleep(2)
            rag_data = self.redis_server.get(f"{RAG_TASK_REDIS_PREFIX}:{task_id}")

        yield 'id: {}\nevent: message\ndata: {}\n\n'.format(int(time.time()), json.dumps(rag_data))
        self.logger.info(
            f"END RAG QUERY, task_id: {task_id}, "
            f"status: {rag_data['status']}, response: {rag_data['result']}")
