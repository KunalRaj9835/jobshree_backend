
# ========================================
# app/schemas/application_note.py - NEW FILE
# ========================================

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class ApplicationNoteCreate(BaseModel):
    """Schema for creating a note on an application"""
    note: str
    is_private: bool = True  # Private to recruiter by default

    class Config:
        orm_mode = True


class ApplicationNoteUpdate(BaseModel):
    """Schema for updating an existing note"""
    note: Optional[str] = None
    is_private: Optional[bool] = None

    class Config:
        orm_mode = True


class ApplicationNoteResponse(BaseModel):
    """Response schema for application notes"""
    id: str
    application_id: str
    note: str
    is_private: bool
    created_by: str  # User ID of note creator
    created_by_name: str  # Name of note creator
    created_by_role: str  # Role: recruiter, admin
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ApplicationWithNotes(BaseModel):
    """Application details with all notes"""
    application_id: str
    job_id: str
    job_title: str
    candidate_id: str
    candidate_name: str
    candidate_email: str
    status: str
    applied_at: datetime
    notes: list[ApplicationNoteResponse]
    notes_count: int

    class Config:
        orm_mode = True