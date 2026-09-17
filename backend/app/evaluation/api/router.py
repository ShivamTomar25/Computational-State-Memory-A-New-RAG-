from __future__ import annotations

from fastapi import APIRouter

from app.evaluation.api.annotations_router.router import router as annotations_router
from app.evaluation.api.datasets_router.router import router as datasets_router
from app.evaluation.api.experiments_router.router import router as experiments_router
from app.evaluation.api.exports_router.router import router as exports_router
from app.evaluation.api.results_router.router import router as results_router


router = APIRouter(tags=["Evaluation"])
router.include_router(datasets_router)
router.include_router(experiments_router)
router.include_router(results_router)
router.include_router(annotations_router)
router.include_router(exports_router)
