from pydantic import BaseModel


class RagGithubDTO(BaseModel):
    owner: str
    repo: str
    branch: str
    prompt: str
