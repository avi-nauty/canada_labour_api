import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.models import SOURCE, DataPoint, Metadata, UnemploymentResponse
from app.series import AgeGroup, Region, SeriesNotMappedError, get_series, list_series

from app.services.cache import get_points
from app.services.statcan import StatCanError, TableLockedError, fetch_latest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/series")
def series_list():
    return [
        {"region": region, "age_group": age, "vector_id": s.vector_id, "name": s.name}
        for region, age, s in list_series()
    ]


@router.get("/unemployment", response_model=UnemploymentResponse)
def unemployment(
    region: Region,
    age_group: AgeGroup,
    periods: int = Query(12, ge=1, le=120),
):
    try:
        series = get_series(region, age_group)
    except SeriesNotMappedError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        points, fetched_at, cached = get_points(series.vector_id)
    except TableLockedError as e:
        logger.warning("StatCan table locked: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Data source is temporarily locked, try again later",
            headers={"Retry-After": "300"},
        )
    except (StatCanError, httpx.HTTPError) as e:
        logger.warning("StatCan call failed: %r", e)
        raise HTTPException(status_code=502, detail="Data source failed")

    return UnemploymentResponse(
        metadata=Metadata(
            series_name=series.name,
            region=region,
            age_group=age_group,
            unit="percent",
            frequency="monthly",
            source=SOURCE,
            vector_id=series.vector_id,
            retrieved_at=fetched_at,
            cached=cached,
        ),
        data=[DataPoint(ref_period=p["refPer"], value=p.get("value")) for p in points[-periods:]],
    )