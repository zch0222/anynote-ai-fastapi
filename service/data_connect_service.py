import os.path

from core.redis_server import RedisServer
from model.dto import GithubIndexDTO, GithubQueryDTO
from model.vo import GithubQueryVO
from llama_index.readers.github import GithubRepositoryReader, GithubClient
from core.config import GITHUB_TOKEN
from llama_index.core import VectorStoreIndex, ServiceContext, load_index_from_storage, StorageContext, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from constants.data_connect_constants import GITHUB_PERSIST_DIR
from exceptions import BusinessException
from llama_index.core.node_parser import SentenceSplitter


class DataConnectService:

    def __init__(self, redis_server: RedisServer):
        self.redis_server = redis_server
        Settings.embed_model = HuggingFaceEmbedding("BAAI/bge-small-en-v1.5")
        pass

    def get_base_node_parser(self):
        return SentenceSplitter()

    def build_github_index(self, github_index_dto: GithubIndexDTO):
        documents = GithubRepositoryReader(
            github_client=GithubClient(github_token=GITHUB_TOKEN),
            owner=github_index_dto.owner,
            repo=github_index_dto.repo,
            use_parser=False,
            verbose=True,
        ).load_data(branch=github_index_dto.branch)
        node_parser = self.get_base_node_parser()
        nodes = node_parser.get_nodes_from_documents(documents)
        # index = VectorStoreIndex.from_documents(documents, service_context=ServiceContext
        #                                         .from_defaults(
        #     embed_model=HuggingFaceEmbedding("BAAI/bge-small-en-v1.5")))
        index = VectorStoreIndex(nodes, service_context=ServiceContext
                                 .from_defaults(embed_model=HuggingFaceEmbedding("BAAI/bge-small-en-v1.5")))
        index.storage_context.persist(
            persist_dir=f"{GITHUB_PERSIST_DIR}/{github_index_dto.owner}/{github_index_dto.repo}/{github_index_dto.branch}")

    def index_github(self, github_index_dto: GithubIndexDTO):
        self.build_github_index(github_index_dto)
        return "SUCCESS"

    def query_github(self, github_query_dto: GithubQueryDTO):
        vector_index_path = f"{GITHUB_PERSIST_DIR}/{github_query_dto.owner}/{github_query_dto.repo}/{github_query_dto.branch}"
        if not os.path.exists(vector_index_path):
            raise BusinessException("索引不存在")

        index = load_index_from_storage(StorageContext.from_defaults(persist_dir=vector_index_path))
        query_engine = index.as_query_engine()
        response = query_engine.query(github_query_dto.prompt)
        return GithubQueryVO(message=str(response))
