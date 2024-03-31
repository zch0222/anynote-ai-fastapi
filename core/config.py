from dotenv import load_dotenv
import os

load_dotenv()

ORIGINS = os.environ.get("ORIGINS").split(",")
DATA_PATH = os.environ.get("DATA_PATH")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
RAG_LLM_MODEL = os.environ.get("RAG_LLM_MODEL")
