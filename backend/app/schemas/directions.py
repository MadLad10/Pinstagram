from typing import Literal

from pydantic import BaseModel


class WalkStep(BaseModel):
    type: Literal["walk"] = "walk"
    to: str
    distance_m: int
    duration_s: int


class BusStep(BaseModel):
    type: Literal["bus"] = "bus"
    route_name: str
    operator: str | None = None
    from_stop: str
    to_stop: str
    num_stops: int
    duration_s: int
    fare: int


class TrainStep(BaseModel):
    type: Literal["train"] = "train"
    from_station: str
    to_station: str
    departure_time: str | None
    duration_s: int
    fare: int


class BusOption(BaseModel):
    mode: Literal["bus"] = "bus"
    steps: list[WalkStep | BusStep]
    total_cost: int
    total_duration_s: int
    label: str | None = None


class RideHailProvider(BaseModel):
    name: str
    cost_low: int
    cost_high: int
    duration_s: int


class RideHailOption(BaseModel):
    mode: Literal["ride_hail"] = "ride_hail"
    providers: list[RideHailProvider]
    distance_m: int
    total_cost: int
    total_duration_s: int
    label: str | None = None


class TrainOption(BaseModel):
    mode: Literal["train"] = "train"
    steps: list[WalkStep | TrainStep]
    from_station: str
    to_station: str
    next_departure: str | None
    fare: int
    duration_s: int
    total_cost: int
    total_duration_s: int
    label: str | None = None


class WalkOption(BaseModel):
    mode: Literal["walk"] = "walk"
    distance_m: int
    duration_s: int
    total_cost: int = 0
    total_duration_s: int
    recommended: bool
    label: str | None = None


class DirectionsResponse(BaseModel):
    distance_m: int
    options: list[BusOption | RideHailOption | TrainOption | WalkOption]
