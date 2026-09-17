from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.database import init_db
from app.document.router import router as document_router
from app.doctor.router import router as doctor_router
from app.evaluation.api.router import router as evaluation_router
from app.health.router import router as health_router
from app.llm.api.router import router as llm_router
from app.memory_systems.csm.router import router as csm_router
from app.memory_systems.common.api.router import router as memory_systems_router
from app.patient_information.router import router as patient_information_router
from app.patient.router import router as patient_router
from app.performance.api.router import router as performance_router
from app.performance.middleware.compression import configure_compression
from app.performance.middleware.request_id import RequestIdMiddleware
from app.performance.middleware.request_timing import RequestTimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

configure_compression(app)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIdMiddleware)

app.include_router(health_router)
app.include_router(doctor_router)
app.include_router(patient_router)
app.include_router(patient_information_router)
app.include_router(document_router)
app.include_router(memory_systems_router)
app.include_router(csm_router)
app.include_router(llm_router)
app.include_router(evaluation_router)
app.include_router(performance_router)


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Backend running"}
