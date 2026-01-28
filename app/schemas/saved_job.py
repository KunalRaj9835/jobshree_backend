# ========================================
# app/schemas/saved_job.py - COMPLETE FILE (REPLACE EXISTING)
# ========================================

from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

class SavedJobCreate(BaseModel):
    """Schema for creating a saved job"""
    job_id: str

class SavedJobResponse(BaseModel):
    """Basic response for saved job"""
    id: str
    user_id: str
    job_id: str
    saved_at: Optional[Any] = None

    class Config:
        orm_mode = True

class SavedJobDetailResponse(BaseModel):
    """Detailed response with complete job information"""
    saved_job_id: str
    job_id: str
    title: str
    company: str
    location: str
    salary: str
    job_type: str
    skills: List[str]
    saved_at: datetime

    class Config:
        orm_mode = True