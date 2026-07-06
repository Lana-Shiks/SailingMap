from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class BoatConfig(BaseModel):
    draft_m: float
    speed_curve_id: str
    max_wind_kt: float = 20.0

class WindForecast(BaseModel):
    time: datetime
    speed_kt: float
    gust_kt: float
    direction_deg: float

class CurrentVector(BaseModel):
    time: datetime
    lat: float
    lon: float
    speed_kt: float
    direction_deg: float

class TideWindow(BaseModel):
    min_tide_m: float

class PlanRouteRequest(BaseModel):
    start: str
    end: str
    departure_time: datetime
    duration_target_min: Optional[int] = None
    pinned_waypoints: List[str] = []
    boat: BoatConfig
    wind_forecast: List[WindForecast]
    current_vectors: List[CurrentVector]
    tide_window: TideWindow
    sunset_time: datetime

class Leg(BaseModel):
    from_idx: int
    to_idx: int
    heading_deg: float
    distance_nm: float
    point_of_sail: str
    est_sog_kt: float
    eta: datetime
    flags: List[str]

class PlanRouteResponse(BaseModel):
    status: str
    reason: Optional[str] = None
    coordinates: List[List[float]] = [] # [lat, lon]
    legs: List[Leg] = []
    return_eta: Optional[datetime] = None
    sunset_margin_min: Optional[int] = None
    grid_version: str = "v1"
