# ========================================
# app/schemas/job.py - UPDATED VERSION
# ========================================

from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime

# 1. Input: What the Recruiter sends
class JobCreate(BaseModel):
    title: str
    company: str
    location: str
    salary: str
    job_type: str  # Full-time, Part-time, Internship
    skills: List[str] = []
    description: Optional[str] = None
    application_deadline: Optional[datetime] = None  # NEW: Application deadline

# 2. Input: Update existing job
class JobUpdate(BaseModel):
    """Schema for updating job details"""
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    salary: Optional[str] = None
    job_type: Optional[str] = None
    skills: Optional[List[str]] = None
    description: Optional[str] = None
    application_deadline: Optional[datetime] = None

    class Config:
        orm_mode = True

# 3. Output: Basic Response
class JobResponse(JobCreate):
    id: str
    owner_email: str
    recruiter_id: Optional[str] = None
    status: str = "active"  # NEW: active, closed, filled
    view_count: int = 0  # NEW: Track views
    posted_date: Optional[datetime] = None  # NEW: Tracking

# 4. Output: Detailed Response with Extra Info
class JobDetailResponse(JobResponse):
    application_count: Optional[int] = 0
    pending_count: Optional[int] = 0  # NEW: Pending applications
    shortlisted_count: Optional[int] = 0  # NEW: Shortlisted applications

    class Config:
        orm_mode = True

# 5. Status Update Schema
class JobStatusUpdate(BaseModel):
    """Schema for updating job status"""
    status: Literal["active", "closed", "filled"]

    class Config:
        orm_mode = True