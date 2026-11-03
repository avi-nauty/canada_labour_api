from dataclasses import dataclass
from enum import StrEnum


class Region(StrEnum):
    CA = "CA"
    ON = "ON"


class AgeGroup(StrEnum):
    ALL_15_PLUS = "15+"
    YOUTH_15_24 = "15-24"


@dataclass(frozen=True)
class Series:
    vector_id: int
    name: str


class SeriesNotMappedError(Exception):
    pass


_SERIES = {
    (Region.CA, AgeGroup.ALL_15_PLUS): Series(2062815, "Unemployment rate, Canada, 15 years and over"),
    (Region.ON, AgeGroup.ALL_15_PLUS): Series(2063949, "Unemployment rate, Ontario, 15 years and over"),
    (Region.CA, AgeGroup.YOUTH_15_24): Series(2062842, "Unemployment rate, Canada, 15 to 24 years"),
    (Region.ON, AgeGroup.YOUTH_15_24): Series(2063976, "Unemployment rate, Ontario, 15 to 24 years"),
}


def get_series(region: Region, age_group: AgeGroup) -> Series:
    try:
        return _SERIES[(region, age_group)]
    except KeyError:
        raise SeriesNotMappedError(
            f"No series for region {region} and age group {age_group}"
        ) from None

def list_series() -> list[tuple[Region, AgeGroup, Series]]:
    return [(region, age, series) for (region, age), series in _SERIES.items()]