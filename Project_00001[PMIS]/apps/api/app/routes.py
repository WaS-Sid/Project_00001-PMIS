import os
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from celery import Celery
from common import greet
from .schemas import TaskRequest, TaskResponse

router = APIRouter()

# Initialize Celery client
broker = os.getenv("CELERY_BROKER", "redis://localhost:6379/0")
celery_app = Celery("api", broker=broker)


@router.get("/hello")
def hello():
    return {"message": greet()}


@router.post("/tasks", response_model=TaskResponse)
def create_task(req: TaskRequest):
    """Submit an async task to the worker."""
    try:
        task = celery_app.send_task(
            "worker.process_task",
            kwargs={"name": req.name, "data": req.data or {}},
        )
        return TaskResponse(
            task_id=task.id,
            status="submitted",
            message=f"Task '{req.name}' submitted successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task submission failed: {str(e)}")


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    """Get the status of an async task."""
    task = celery_app.AsyncResult(task_id)
    if task.state == "PENDING":
        return {"task_id": task_id, "status": "pending", "result": None}
    elif task.state == "SUCCESS":
        return {"task_id": task_id, "status": "success", "result": task.result}
    elif task.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(task.info)}
    else:
        return {"task_id": task_id, "status": task.state, "result": None}
