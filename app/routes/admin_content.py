# ========================================
# app/routes/admin_content.py - NEW FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

from app.database import get_db
from app.schemas.admin import (
    ContentFlag,
    ContentFlagResponse,
    BulkDeleteRequest
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin - Content Moderation"])


# ===========================
# HELPER: LOG AUDIT
# ===========================

async def log_admin_action(db, admin_id: str, admin_name: str, action: str, target_type: str, target_id: str = None, details: dict = None):
    """Helper to log admin actions"""
    await db.audit_logs.insert_one({
        "action": action,
        "admin_id": admin_id,
        "admin_name": admin_name,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
        "timestamp": datetime.utcnow()
    })


# ===========================
# ADMIN CHECK
# ===========================

def admin_required(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ===========================
# CONTENT MODERATION ENDPOINTS
# ===========================

# ✅ 1. GET ALL JOBS WITH MODERATION FILTERS
@router.get("/jobs")
async def get_all_jobs_admin(
    status: Optional[str] = Query(None, description="Filter by status"),
    is_flagged: Optional[bool] = Query(None, description="Show flagged jobs only"),
    recruiter_id: Optional[str] = Query(None, description="Filter by recruiter"),
    limit: int = Query(100, le=500),
    current_user: dict = Depends(admin_required)
):
    """Get all jobs with admin filters. Admin only."""

    db = get_db()

    query = {}

    if status:
        query["status"] = status

    if is_flagged is not None:
        query["is_flagged"] = is_flagged

    if recruiter_id:
        query["recruiter_id"] = recruiter_id

    jobs = await db.jobs.find(query).sort("posted_date", -1).limit(limit).to_list(limit)

    # Enrich with application counts
    result = []
    for job in jobs:
        job_id = str(job["_id"])
        app_count = await db.applications.count_documents({"job_id": job_id})

        result.append({
            "id": job_id,
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "recruiter_id": job.get("recruiter_id"),
            "owner_email": job.get("owner_email"),
            "status": job.get("status", "active"),
            "is_flagged": job.get("is_flagged", False),
            "flagged_reason": job.get("flagged_reason"),
            "posted_date": job.get("posted_date"),
            "application_count": app_count
        })

    return result


# ✅ 2. FLAG JOB AS INAPPROPRIATE
@router.put("/jobs/{job_id}/flag")
async def flag_job(
    job_id: str,
    flag_data: ContentFlag,
    current_user: dict = Depends(admin_required)
):
    """Flag a job as inappropriate. Admin only."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update job
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "is_flagged": True,
            "flagged_reason": flag_data.reason,
            "flagged_at": datetime.utcnow(),
            "flagged_by": str(current_user["_id"]),
            "flag_severity": flag_data.severity
        }}
    )

    # Create flag record
    flag_record = {
        "content_type": "job",
        "content_id": job_id,
        "flagged_by": str(current_user["_id"]),
        "flagged_by_name": current_user["name"],
        "reason": flag_data.reason,
        "severity": flag_data.severity,
        "status": "pending",
        "flagged_at": datetime.utcnow()
    }
    await db.content_flags.insert_one(flag_record)

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="job_flagged",
        target_type="job",
        target_id=job_id,
        details={
            "job_title": job.get("title"),
            "reason": flag_data.reason,
            "severity": flag_data.severity
        }
    )

    return {
        "message": "Job flagged successfully",
        "job_id": job_id,
        "job_title": job.get("title"),
        "reason": flag_data.reason
    }


# ✅ 3. UNFLAG JOB
@router.put("/jobs/{job_id}/unflag")
async def unflag_job(
    job_id: str,
    current_user: dict = Depends(admin_required)
):
    """Remove flag from a job. Admin only."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update job
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "is_flagged": False,
            "unflagged_at": datetime.utcnow(),
            "unflagged_by": str(current_user["_id"])
        }}
    )

    # Update flag records
    await db.content_flags.update_many(
        {"content_type": "job", "content_id": job_id, "status": "pending"},
        {"$set": {
            "status": "reviewed",
            "reviewed_by": str(current_user["_id"]),
            "reviewed_at": datetime.utcnow()
        }}
    )

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="job_unflagged",
        target_type="job",
        target_id=job_id,
        details={"job_title": job.get("title")}
    )

    return {
        "message": "Job unflagged successfully",
        "job_id": job_id,
        "job_title": job.get("title")
    }


# ✅ 4. BULK DELETE JOBS
@router.delete("/jobs/bulk-delete")
async def bulk_delete_jobs(
    bulk_delete: BulkDeleteRequest,
    current_user: dict = Depends(admin_required)
):
    """Delete multiple jobs at once. Admin only."""

    db = get_db()

    # Validate job IDs
    valid_ids = [ObjectId(id) for id in bulk_delete.ids if ObjectId.is_valid(id)]

    if not valid_ids:
        raise HTTPException(status_code=400, detail="No valid job IDs provided")

    # Get job details before deletion
    jobs = await db.jobs.find({"_id": {"$in": valid_ids}}).to_list(100)

    # Delete jobs
    result = await db.jobs.delete_many({"_id": {"$in": valid_ids}})

    # Also delete associated applications (optional - can be configured)
    apps_deleted = await db.applications.delete_many({"job_id": {"$in": [str(id) for id in valid_ids]}})

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="bulk_jobs_deleted",
        target_type="jobs",
        details={
            "count": result.deleted_count,
            "reason": bulk_delete.reason,
            "applications_deleted": apps_deleted.deleted_count,
            "job_ids": bulk_delete.ids
        }
    )

    return {
        "message": f"Deleted {result.deleted_count} jobs successfully",
        "jobs_deleted": result.deleted_count,
        "applications_deleted": apps_deleted.deleted_count,
        "deleted_job_ids": [str(id) for id in valid_ids]
    }


# ✅ 5. GET ALL FLAGGED CONTENT
@router.get("/flagged-content", response_model=List[ContentFlagResponse])
async def get_flagged_content(
    content_type: Optional[str] = Query(None, description="Filter by content type: job, user"),
    status: Optional[str] = Query("pending", description="Filter by status: pending, reviewed, dismissed"),
    limit: int = Query(100, le=500),
    current_user: dict = Depends(admin_required)
):
    """Get all flagged content. Admin only."""

    db = get_db()

    query = {}

    if content_type:
        query["content_type"] = content_type

    if status:
        query["status"] = status

    flags = await db.content_flags.find(query).sort("flagged_at", -1).limit(limit).to_list(limit)

    return [
        {
            "id": str(flag["_id"]),
            "content_type": flag["content_type"],
            "content_id": flag["content_id"],
            "flagged_by": flag["flagged_by"],
            "flagged_by_name": flag.get("flagged_by_name"),
            "reason": flag["reason"],
            "severity": flag.get("severity", "medium"),
            "status": flag["status"],
            "flagged_at": flag["flagged_at"],
            "reviewed_by": flag.get("reviewed_by"),
            "reviewed_at": flag.get("reviewed_at")
        }
        for flag in flags
    ]


# ✅ 6. DELETE ANY APPLICATION
@router.delete("/applications/{application_id}")
async def delete_application(
    application_id: str,
    reason: Optional[str] = Query(None, description="Reason for deletion"),
    current_user: dict = Depends(admin_required)
):
    """Delete any application. Admin only."""

    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")

    db = get_db()

    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Delete the application
    await db.applications.delete_one({"_id": ObjectId(application_id)})

    # Delete associated notes
    notes_deleted = await db.application_notes.delete_many({"application_id": application_id})

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="application_deleted",
        target_type="application",
        target_id=application_id,
        details={
            "reason": reason,
            "job_id": application["job_id"],
            "user_id": application["user_id"],
            "notes_deleted": notes_deleted.deleted_count
        }
    )

    return {
        "message": "Application deleted successfully",
        "application_id": application_id,
        "notes_deleted": notes_deleted.deleted_count
    }


# ✅ 7. GET MODERATION STATISTICS
@router.get("/moderation-stats")
async def get_moderation_stats(
    current_user: dict = Depends(admin_required)
):
    """Get content moderation statistics. Admin only."""

    db = get_db()

    # Count flagged content
    flagged_jobs = await db.jobs.count_documents({"is_flagged": True})
    pending_flags = await db.content_flags.count_documents({"status": "pending"})
    reviewed_flags = await db.content_flags.count_documents({"status": "reviewed"})

    # Recent flags
    recent_flags = await db.content_flags.find(
        {"status": "pending"}
    ).sort("flagged_at", -1).limit(10).to_list(10)

    return {
        "flagged_jobs_count": flagged_jobs,
        "pending_flags": pending_flags,
        "reviewed_flags": reviewed_flags,
        "total_flags": pending_flags + reviewed_flags,
        "recent_flags": [
            {
                "content_type": flag["content_type"],
                "content_id": flag["content_id"],
                "reason": flag["reason"],
                "severity": flag.get("severity"),
                "flagged_at": flag["flagged_at"]
            }
            for flag in recent_flags
        ]
    }