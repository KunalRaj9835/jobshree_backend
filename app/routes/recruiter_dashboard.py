# ========================================
# app/routes/recruiter_dashboard.py - NEW FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional

from app.database import get_db
from app.schemas.job_analytics import (
    RecruiterStats,
    JobAnalytics,
    JobListItem,
    ApplicationStats
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/recruiter", tags=["Recruiter Dashboard"])


# ✅ 1. Get Recruiter Dashboard Overview
@router.get("/dashboard", response_model=RecruiterStats)
async def get_recruiter_dashboard(current_user: dict = Depends(get_current_user)):
    """Get overall statistics for the recruiter's account."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can access this dashboard"
        )

    db = get_db()

    # Get all jobs posted by this recruiter
    jobs_query = {"recruiter_id": str(current_user["_id"])}
    if current_user["role"] == "admin":
        jobs_query = {}  # Admins see all jobs

    all_jobs = await db.jobs.find(jobs_query).to_list(1000)
    job_ids = [str(job["_id"]) for job in all_jobs]

    # Count jobs by status
    total_jobs = len(all_jobs)
    active_jobs = len([j for j in all_jobs if j.get("status", "active") == "active"])
    closed_jobs = len([j for j in all_jobs if j.get("status") == "closed"])
    filled_jobs = len([j for j in all_jobs if j.get("status") == "filled"])

    # Get all applications for these jobs
    applications_query = {"job_id": {"$in": job_ids}}
    all_applications = await db.applications.find(applications_query).to_list(10000)

    # Count applications by status
    total_applications = len(all_applications)
    pending_apps = len([a for a in all_applications if a.get("status") == "Pending"])
    shortlisted_apps = len([a for a in all_applications if a.get("status") == "Shortlisted"])
    rejected_apps = len([a for a in all_applications if a.get("status") == "Rejected"])
    selected_apps = len([a for a in all_applications if a.get("status") == "Selected"])

    return {
        "total_jobs_posted": total_jobs,
        "active_jobs": active_jobs,
        "closed_jobs": closed_jobs,
        "filled_positions": filled_jobs,
        "total_applications": total_applications,
        "pending_applications": pending_apps,
        "shortlisted_applications": shortlisted_apps,
        "rejected_applications": rejected_apps,
        "selected_applications": selected_apps
    }


# ✅ 2. Get My Posted Jobs (Recruiter-Filtered)
@router.get("/my-jobs", response_model=List[JobListItem])
async def get_my_jobs(
    status: Optional[str] = Query(None, description="Filter by status: active, closed, filled"),
    current_user: dict = Depends(get_current_user)
):
    """Get all jobs posted by the current recruiter with application counts."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can access this endpoint"
        )

    db = get_db()

    # Build query
    query = {"recruiter_id": str(current_user["_id"])}
    if current_user["role"] == "admin":
        query = {}  # Admins see all jobs

    if status:
        query["status"] = status

    # Get jobs
    jobs = await db.jobs.find(query).sort("posted_date", -1).to_list(500)

    # Enrich with application counts
    result = []
    for job in jobs:
        job_id = str(job["_id"])

        # Get total applications
        total_apps = await db.applications.count_documents({"job_id": job_id})

        # Get pending (new) applications
        pending_apps = await db.applications.count_documents({
            "job_id": job_id,
            "status": "Pending"
        })

        result.append({
            "id": job_id,
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "status": job.get("status", "active"),
            "posted_date": job.get("posted_date", datetime.utcnow()),
            "application_count": total_apps,
            "new_applications": pending_apps,
            "deadline": job.get("application_deadline")
        })

    return result


# ✅ 3. Get Job-Specific Analytics
@router.get("/jobs/{job_id}/analytics", response_model=JobAnalytics)
async def get_job_analytics(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get detailed analytics for a specific job."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can view job analytics"
        )

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    db = get_db()

    # Get the job
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify ownership (recruiters can only see their own jobs)
    if current_user["role"] == "recruiter":
        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only view analytics for your own jobs"
            )

    # Get all applications for this job
    applications = await db.applications.find({"job_id": job_id}).to_list(10000)

    # Count by status
    status_counts = {
        "Pending": 0,
        "Shortlisted": 0,
        "Rejected": 0,
        "Selected": 0
    }

    for app in applications:
        status = app.get("status", "Pending")
        if status in status_counts:
            status_counts[status] += 1

    # Calculate days active
    posted_date = job.get("posted_date", datetime.utcnow())
    days_active = (datetime.utcnow() - posted_date).days

    return {
        "job_id": job_id,
        "job_title": job.get("title", ""),
        "total_applications": len(applications),
        "applications_by_status": status_counts,
        "view_count": job.get("view_count", 0),
        "posted_date": posted_date,
        "application_deadline": job.get("application_deadline"),
        "status": job.get("status", "active"),
        "days_active": days_active
    }


# ✅ 4. Get Application Statistics for a Job
@router.get("/jobs/{job_id}/application-stats", response_model=ApplicationStats)
async def get_application_stats(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get application statistics for a specific job."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can view application statistics"
        )

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    db = get_db()

    # Verify job exists and ownership
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if current_user["role"] == "recruiter":
        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only view statistics for your own jobs"
            )

    # Get all applications
    total = await db.applications.count_documents({"job_id": job_id})
    pending = await db.applications.count_documents({"job_id": job_id, "status": "Pending"})
    shortlisted = await db.applications.count_documents({"job_id": job_id, "status": "Shortlisted"})
    rejected = await db.applications.count_documents({"job_id": job_id, "status": "Rejected"})
    selected = await db.applications.count_documents({"job_id": job_id, "status": "Selected"})

    # Get recent applications (last 7 days)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent = await db.applications.count_documents({
        "job_id": job_id,
        "applied_at": {"$gte": seven_days_ago}
    })

    return {
        "job_id": job_id,
        "total": total,
        "pending": pending,
        "shortlisted": shortlisted,
        "rejected": rejected,
        "selected": selected,
        "recent_applications": recent
    }


# ✅ 5. Get Recent Activity Summary
@router.get("/recent-activity")
async def get_recent_activity(
    days: int = Query(7, description="Number of days to look back"),
    current_user: dict = Depends(get_current_user)
):
    """Get recent activity summary for the recruiter."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can view recent activity"
        )

    db = get_db()

    # Calculate date threshold
    threshold_date = datetime.utcnow() - timedelta(days=days)

    # Get recruiter's job IDs
    jobs_query = {"recruiter_id": str(current_user["_id"])}
    if current_user["role"] == "admin":
        jobs_query = {}

    jobs = await db.jobs.find(jobs_query).to_list(1000)
    job_ids = [str(job["_id"]) for job in jobs]

    # Get recent applications
    recent_applications = await db.applications.find({
        "job_id": {"$in": job_ids},
        "applied_at": {"$gte": threshold_date}
    }).to_list(100)

    # Get jobs posted in this period
    recent_jobs = [j for j in jobs if j.get("posted_date", datetime.utcnow()) >= threshold_date]

    return {
        "period_days": days,
        "new_applications": len(recent_applications),
        "new_jobs_posted": len(recent_jobs),
        "total_active_jobs": len([j for j in jobs if j.get("status", "active") == "active"]),
        "applications_by_status": {
            "Pending": len([a for a in recent_applications if a.get("status") == "Pending"]),
            "Shortlisted": len([a for a in recent_applications if a.get("status") == "Shortlisted"]),
            "Rejected": len([a for a in recent_applications if a.get("status") == "Rejected"]),
            "Selected": len([a for a in recent_applications if a.get("status") == "Selected"])
        }
    }