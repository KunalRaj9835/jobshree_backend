# ========================================
# app/schemas/admin.py - NEW FILE
# ========================================

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Literal
from datetime import datetime

# ===========================
# USER MANAGEMENT SCHEMAS
# ===========================

class UserSuspend(BaseModel):
    """Schema for suspending a user"""
    reason: str
    duration_days: Optional[int] = None  # None = indefinite

    class Config:
        orm_mode = True


class UserRoleChange(BaseModel):
    """Schema for changing user role"""
    new_role: Literal["user", "jobseeker", "recruiter", "admin"]
    reason: Optional[str] = None

    class Config:
        orm_mode = True


class PasswordReset(BaseModel):
    """Schema for admin password reset"""
    new_password: str
    notify_user: bool = True  # Send email notification

    class Config:
        orm_mode = True


class UserDetailResponse(BaseModel):
    """Detailed user information for admin"""
    id: str
    name: str
    email: str
    role: str
    is_suspended: bool
    suspended_at: Optional[datetime] = None
    suspended_by: Optional[str] = None
    suspension_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    login_count: int = 0

    # Statistics
    total_jobs_posted: Optional[int] = 0
    total_applications: Optional[int] = 0
    total_resumes: Optional[int] = 0

    class Config:
        orm_mode = True


class UserActivityLog(BaseModel):
    """User activity log entry"""
    user_id: str
    action: str
    timestamp: datetime
    details: Optional[dict] = None
    ip_address: Optional[str] = None

    class Config:
        orm_mode = True


# ===========================
# CONTENT MODERATION SCHEMAS
# ===========================

class ContentFlag(BaseModel):
    """Schema for flagging content"""
    reason: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"

    class Config:
        orm_mode = True


class ContentFlagResponse(BaseModel):
    """Response for flagged content"""
    id: str
    content_type: str  # job, user, application
    content_id: str
    flagged_by: str
    flagged_by_name: Optional[str] = None
    reason: str
    severity: str
    status: str  # pending, reviewed, dismissed
    flagged_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class BulkDeleteRequest(BaseModel):
    """Schema for bulk delete operations"""
    ids: List[str]
    reason: Optional[str] = None

    class Config:
        orm_mode = True


# ===========================
# ANALYTICS SCHEMAS
# ===========================

class PlatformOverview(BaseModel):
    """Platform-wide overview statistics"""
    total_users: int
    total_jobseekers: int
    total_recruiters: int
    total_admins: int
    active_users: int  # Users active in last 30 days
    suspended_users: int

    total_jobs: int
    active_jobs: int
    closed_jobs: int
    filled_jobs: int
    flagged_jobs: int

    total_applications: int
    pending_applications: int
    shortlisted_applications: int
    selected_applications: int

    total_resumes: int

    # Growth metrics
    new_users_this_month: int
    new_jobs_this_month: int
    new_applications_this_month: int

    class Config:
        orm_mode = True


class UserGrowthStats(BaseModel):
    """User growth statistics"""
    period: str  # daily, weekly, monthly
    data: List[dict]  # [{date: "2024-01", count: 50}, ...]
    total_growth: int
    growth_rate: float  # Percentage

    class Config:
        orm_mode = True


class JobTrendStats(BaseModel):
    """Job posting trends"""
    period: str
    data: List[dict]
    top_locations: List[dict]
    top_job_types: List[dict]
    average_applications_per_job: float

    class Config:
        orm_mode = True


class TopRecruiter(BaseModel):
    """Top recruiter information"""
    recruiter_id: str
    recruiter_name: str
    recruiter_email: str
    total_jobs_posted: int
    total_applications_received: int
    active_jobs: int
    average_applications_per_job: float

    class Config:
        orm_mode = True


class GeographicDistribution(BaseModel):
    """Geographic distribution of jobs/users"""
    location: str
    jobs_count: int
    users_count: int
    applications_count: int

    class Config:
        orm_mode = True


class ConversionStats(BaseModel):
    """Application conversion rates"""
    total_applications: int
    shortlisted_rate: float
    selected_rate: float
    rejected_rate: float
    average_time_to_shortlist_days: float
    average_time_to_selection_days: float

    class Config:
        orm_mode = True


# ===========================
# AUDIT LOG SCHEMAS
# ===========================

class AuditLogCreate(BaseModel):
    """Schema for creating audit log"""
    action: str
    target_type: str  # user, job, application, system
    target_id: Optional[str] = None
    details: Optional[dict] = None

    class Config:
        orm_mode = True


class AuditLogResponse(BaseModel):
    """Audit log response"""
    id: str
    action: str
    admin_id: str
    admin_name: str
    target_type: str
    target_id: Optional[str] = None
    details: Optional[dict] = None
    timestamp: datetime
    ip_address: Optional[str] = None

    class Config:
        orm_mode = True