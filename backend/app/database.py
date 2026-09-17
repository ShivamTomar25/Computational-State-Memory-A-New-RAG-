from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
    pool_recycle=settings.database_pool_recycle_seconds,
)

from app.performance.database.query_profiler import install_query_profiler

install_query_profiler(engine)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    import app.doctor.model
    import app.document.models
    import app.evaluation.datasets.models.dataset
    import app.evaluation.experiments.models.experiment
    import app.evaluation.exports.models
    import app.evaluation.ground_truth.models.ground_truth
    import app.evaluation.judges.human_review.models
    import app.evaluation.judges.models
    import app.evaluation.metrics.cost.models
    import app.evaluation.metrics.models
    import app.evaluation.statistics.models
    import app.llm.common.models.llm
    import app.memory_systems.common.models.memory
    import app.memory_systems.csm.models
    import app.memory_systems.dense_rag.models
    import app.memory_systems.graph_rag.models
    import app.memory_systems.hippo_rag.models
    import app.memory_systems.hybrid_rag.models
    import app.memory_systems.long_context.models
    import app.memory_systems.rolling_summary.models
    import app.patient.model
    import app.patient_information.models

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
