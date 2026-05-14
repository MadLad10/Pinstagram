from pydantic import BaseModel


class WalkStep(BaseModel):
    type: str = "walk"
    to: str
    distance_m: int
    duration_s: int


class BusStep(BaseModel):
    type: str = "bus"
    route_name: str
    from_stop: str
    to_stop: str
    duration_s: int
    fare: int


class BusOption(BaseModel):
    mode: str = "bus"
    steps: list[WalkStep | BusStep]
    total_cost: int
    total_duration_s: int
    label: str = "Cheapest"


class RideHailProvider(BaseModel):
    name: str
    cost_low: int
    cost_high: int
    duration_s: int


class RideHailOption(BaseModel):
    mode: str = "ride_hail"
    providers: list[RideHailProvider]
    label: str = "Fastest"


class TrainOption(BaseModel):
    mode: str = "train"
    from_station: str
    to_station: str
    fare: int
    duration_s: int
    label: str = "Train"


class WalkOption(BaseModel):
    mode: str = "walk"
    duration_s: int
    recommended: bool


class DirectionsResponse(BaseModel):
    distance_m: int
    options: list[BusOption | RideHailOption | TrainOption | WalkOption]
