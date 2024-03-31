from pydantic import BaseModel


class RagQueryDTO(BaseModel):
    file_hash: str
    prompt: str
