from pydantic import BaseModel


class TaskRequest(BaseModel):
    name: str
    data: dict | None = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatus(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None
