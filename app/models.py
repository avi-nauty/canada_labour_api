from datetime import date, datetime

from pydantic import BaseModel

from app.series import AgeGroup, Region

SOURCE = (
    "Adapted from Statistics Canada, Table 14-10-0287, Labour force characteristics, "
    "monthly, seasonally adjusted and trend-cycle. "
    "This does not constitute an endorsement by Statistics Canada of this product."
)


class DataPoint(BaseModel):
    ref_period: date
    value: float | None


class Metadata(BaseModel):
    series_name: str
    region: Region
    age_group: AgeGroup
    unit: str
    frequency: str
    source: str
    vector_id: int
    retrieved_at: datetime
    cached: bool


class UnemploymentResponse(BaseModel):
    metadata: Metadata
    data: list[DataPoint]