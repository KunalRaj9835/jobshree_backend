# ========================================
# app/schemas/application.py - UPDATED VERSION
# ========================================

from pydantic import BaseModel
from typing import Optional, Any, List
from datetime import datetime

# 1. Input: Create Application
class ApplicationCreate(BaseModel):
    job_id: str
    resume_id: str
    cover_letter: Optional[str] = "No cover letter provided"

# 2. Input: Update Status
class ApplicationStatusUpdate(BaseModel):
    status: str  # Pending, Shortlisted, Rejected, Selected

# 3. Input: Bulk Update (NEW!)
class ApplicationBulkUpdate(BaseModel):
    """Schema for updating multiple applications at once"""
    application_ids: List[str]
    status: str  # Pending, Shortlisted, Rejected, Selected

    class Config:
        orm_mode = True

# 4. Output: Basic Response
class ApplicationResponse(BaseModel):
    id: Optional[str] = None
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    status: Optional[str] = None
    resume_id: Optional[str] = None
    cover_letter: Optional[str] = None
    applied_at: Optional[Any] = None
    has_notes: Optional[bool] = False  # NEW: Track if notes exist
    notes_count: Optional[int] = 0  # NEW: Count of notes

    class Config:
        orm_mode = True

# 5. Output: Detailed Response with Job Info
class ApplicationDetailResponse(BaseModel):
    application_id: str
    job_id: str
    job_title: str
    company: str
    location: str
    status: str
    applied_at: datetime
    cover_letter: Optional[str] = None
    has_notes: Optional[bool] = False  # NEW
    notes_count: Optional[int] = 0  # NEW

    class Config:
        orm_mode = True

# 6. Output: Full Details with Candidate Profile (NEW!)
class ApplicationFullDetailResponse(BaseModel):
    """Complete application details with candidate profile"""
    application_id: str
    job_id: str
    job_title: str
    status: str
    applied_at: datetime
    cover_letter: Optional[str] = None
    resume_id: str

    # Candidate details
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_phone: Optional[str] = None
    candidate_location: Optional[str] = None
    candidate_skills: Optional[List[str]] = None
    candidate_experience_years: Optional[int] = None
    candidate_headline: Optional[str] = None

    # Social links
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    # Notes tracking
    has_notes: bool = False
    notes_count: int = 0

    class Config:
        orm_mode = True

# 7. Status History Entry (NEW!)
class StatusHistoryEntry(BaseModel):
    """Track status changes over time"""
    status: str
    changed_at: datetime
    changed_by: str  # User ID who changed it
    changed_by_name: str

    class Config:
        orm_mode = True