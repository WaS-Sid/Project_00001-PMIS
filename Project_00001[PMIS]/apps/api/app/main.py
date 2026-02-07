from fastapi import FastAPI
from .routes import router
from .routes_v2 import router as router_v2
from .database import init_db

app = FastAPI(title="pmis-api")

app.include_router(router, prefix="/api")
app.include_router(router_v2)


@app.on_event("startup")
def on_startup():
    # Ensure DB tables exist for development/local runs (runs idempotently)
    try:
        init_db()
    except Exception:
        # don't crash if DB config is missing in some environments
        pass


@app.get("/")
def root():
    return {"message": "PMIS API — hello world"}


@app.get("/health")
def health():
    return {"status": "healthy"}
