from pydantic import BaseModel
from typing import Optional
from datetime import date

class ExperienceCreate(BaseModel):
    company: str
    job_title: str
    start_date: date
    end_date: Optional[date] = None  # None if currently working
    is_current: bool = False
    description: Optional[str] = None
    location: Optional[str] = None

class ExperienceUpdate(BaseModel):
    company: Optional[str] = None
    job_title: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: Optional[bool] = None
    description: Optional[str] = None
    location: Optional[str] = None

class ExperienceResponse(BaseModel):
    id: str
    user_id: str
    company: str
    job_title: str
    start_date: date
    end_date: Optional[date] = None
    is_current: bool
    description: Optional[str] = None
    location: Optional[str] = None
    
    class Config:
        orm_mode = True
