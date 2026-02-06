from fastapi import FastAPI
from .routes import router

app = FastAPI(title="pmis-api")

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"message": "PMIS API — hello world"}

@app.get("/health")
def health():
    return {"status": "healthy"}
