from pydantic import BaseModel
from datetime import datetime


class AvailabilitySlotCreate(BaseModel):
    start_datetime: datetime
    end_datetime: datetime


class AvailabilitySlotOut(BaseModel):
    id: int
    search_id: int
    start_datetime: datetime
    end_datetime: datetime
    is_booked: bool

    class Config:
        from_attributes = True
