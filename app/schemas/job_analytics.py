# ========================================
# app/schemas/job_analytics.py - NEW FILE
# ========================================

from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime

class JobAnalytics(BaseModel):
    """Analytics for a specific job posting"""
    job_id: str
    job_title: str
    total_applications: int
    applications_by_status: Dict[str, int]  # {"Pending": 5, "Shortlisted": 2, etc.}
    view_count: int
    posted_date: datetime
    application_deadline: Optional[datetime] = None
    status: str  # active, closed, filled
    days_active: int

    class Config:
        orm_mode = True


class RecruiterStats(BaseModel):
    """Overall statistics for a recruiter"""
    total_jobs_posted: int
    active_jobs: int
    closed_jobs: int
    filled_positions: int
    total_applications: int
    pending_applications: int
    shortlisted_applications: int
    rejected_applications: int
    selected_applications: int

    class Config:
        orm_mode = True


class JobListItem(BaseModel):
    """Simplified job listing for recruiter dashboard"""
    id: str
    title: str
    company: str
    location: str
    status: str
    posted_date: datetime
    application_count: int
    new_applications: int  # Applications in "Pending" status
    deadline: Optional[datetime] = None

    class Config:
        orm_mode = True


class ApplicationStats(BaseModel):
    """Application statistics for a job"""
    job_id: str
    total: int
    pending: int
    shortlisted: int
    rejected: int
    selected: int
    recent_applications: int  # Last 7 days

    class Config:
        orm_mode = True