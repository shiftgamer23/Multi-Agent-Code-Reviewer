"""FastAPI app entrypoint. Wires together the API routers."""
from fastapi import FastAPI

from app.api.review import router as review_router
from app.infra.logging import configure_logging

configure_logging()

app = FastAPI(title="Multi-Agent Code Review Assistant")
app.include_router(review_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
