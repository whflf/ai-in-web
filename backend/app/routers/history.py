# ORM — чтение истории генераций через SQLAlchemy async
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import GenerationRecord
from app.schemas import HistoryResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["history"])


@router.get(
    "/history",
    response_model=HistoryResponse,
    summary="История генераций",
)
async def get_history(
    page: int = Query(default=1, ge=1, description="Номер страницы"),
    page_size: int = Query(default=20, ge=1, le=100, description="Записей на странице"),
    db: AsyncSession = Depends(get_db),
) -> HistoryResponse:
    """Возвращает историю генераций с пагинацией, отсортированную по дате."""
    offset = (page - 1) * page_size

    count_result = await db.execute(select(func.count()).select_from(GenerationRecord))
    total = count_result.scalar_one()

    items_result = await db.execute(
        select(GenerationRecord)
        .order_by(GenerationRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = items_result.scalars().all()

    logger.info("History requested | page=%d | total=%d", page, total)
    return HistoryResponse(items=list(items), total=total, page=page, page_size=page_size)
