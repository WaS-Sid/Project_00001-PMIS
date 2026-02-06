from fastapi import APIRouter
from common import greet

router = APIRouter()


@router.get("/hello")
def hello():
    return {"message": greet()}
