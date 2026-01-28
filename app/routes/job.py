# ========================================
# app/routes/job.py - UPDATED VERSION (COMPLETE REPLACEMENT)
# ========================================

from fastapi import APIRouter, Depends, HTTPException, status, Query
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

from app.database import get_db
from app.schemas.job import (
    JobCreate, 
    JobUpdate, 
    JobResponse, 
    JobDetailResponse,
    JobStatusUpdate
)
from app.utils.auth import get_current_user

router = APIRouter()

# ===========================
# PUBLIC ENDPOINTS
# ===========================

# ✅ 1. GET ALL JOBS WITH SEARCH AND FILTERS (Public)
@router.get("/jobs", response_model=List[JobResponse])
async def get_all_jobs(
    search: Optional[str] = Query(None, description="Search in title, company, or description"),
    location: Optional[str] = Query(None, description="Filter by location"),
    job_type: Optional[str] = Query(None, description="Filter by job type: Full-time, Part-time, Internship"),
    skills: Optional[str] = Query(None, description="Filter by skills (comma-separated)"),
    status: Optional[str] = Query("active", description="Filter by status: active, closed, filled"),
    limit: int = Query(100, le=500, description="Maximum number of results")
):
    """Get all jobs with optional search and filtering. Shows only active jobs by default."""

    db = get_db()

    # Build MongoDB query
    query = {"status": status} if status else {}

    # Text search across multiple fields
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]

    # Location filter
    if location:
        query["location"] = {"$regex": location, "$options": "i"}

    # Job type filter
    if job_type:
        query["job_type"] = job_type

    # Skills filter (match any of the provided skills)
    if skills:
        skill_list = [s.strip() for s in skills.split(",")]
        query["skills"] = {"$in": skill_list}

    jobs = await db.jobs.find(query).limit(limit).to_list(limit)

    # Convert _id to id for response
    for job in jobs:
        job["id"] = str(job["_id"])

    return jobs


# ✅ 2. GET SINGLE JOB DETAILS (Public)
@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job_details(job_id: str):
    """Get detailed information about a specific job."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job["id"] = str(job["_id"])

    # Get application counts
    total_count = await db.applications.count_documents({"job_id": job_id})
    pending_count = await db.applications.count_documents({"job_id": job_id, "status": "Pending"})
    shortlisted_count = await db.applications.count_documents({"job_id": job_id, "status": "Shortlisted"})

    job["application_count"] = total_count
    job["pending_count"] = pending_count
    job["shortlisted_count"] = shortlisted_count

    # Increment view count
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$inc": {"view_count": 1}}
    )

    return job


# ✅ 3. CHECK IF USER HAS APPLIED (Jobseeker)
@router.get("/jobs/{job_id}/check-application")
async def check_if_applied(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Check if the current user has already applied to this job."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    application = await db.applications.find_one({
        "job_id": job_id,
        "user_id": str(current_user["_id"])
    })

    return {
        "has_applied": application is not None,
        "application_id": str(application["_id"]) if application else None,
        "status": application.get("status") if application else None
    }


# ===========================
# RECRUITER ENDPOINTS
# ===========================

# ✅ 4. POST A JOB (Recruiter/Admin)
@router.post("/jobs", response_model=JobResponse)
async def create_job(job: JobCreate, current_user: dict = Depends(get_current_user)):
    """Create a new job posting. Only recruiters and admins can post jobs."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only recruiters or admins can post jobs"
        )

    db = get_db()

    new_job = job.dict()
    new_job["owner_email"] = current_user["email"]
    new_job["recruiter_id"] = str(current_user["_id"])
    new_job["status"] = "active"  # NEW: Default status
    new_job["view_count"] = 0  # NEW: Initialize view count
    new_job["posted_date"] = datetime.utcnow()  # NEW: Track posting date

    result = await db.jobs.insert_one(new_job)

    new_job["id"] = str(result.inserted_id)

    return new_job


# ✅ 5. UPDATE/EDIT JOB (Recruiter - NEW!)
@router.put("/jobs/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    job_update: JobUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update job details. Only the job owner or admin can update."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    # Get the job
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership (recruiter can only edit their own jobs)
    if current_user["role"] == "recruiter":
        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only edit your own job postings"
            )

    # Prepare update data
    update_data = job_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.utcnow()

    # Update the job
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": update_data}
    )

    # Fetch and return updated job
    updated_job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    updated_job["id"] = str(updated_job["_id"])

    return updated_job


# ✅ 6. DELETE JOB (Recruiter - NEW!)
@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a job posting. Only the job owner or admin can delete."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    # Get the job
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership
    if current_user["role"] == "recruiter":
        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only delete your own job postings"
            )

    # Check if there are applications
    app_count = await db.applications.count_documents({"job_id": job_id})

    # Delete the job
    await db.jobs.delete_one({"_id": ObjectId(job_id)})

    return {
        "message": "Job deleted successfully",
        "job_id": job_id,
        "applications_existed": app_count
    }


# ✅ 7. CLOSE JOB (Recruiter - NEW!)
@router.put("/jobs/{job_id}/close")
async def close_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Close a job posting (stop accepting applications). Only owner or admin."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    # Get the job
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership
    if current_user["role"] == "recruiter":
        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only close your own job postings"
            )

    # Update status to closed
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"status": "closed", "closed_at": datetime.utcnow()}}
    )

    return {
        "message": "Job closed successfully",
        "job_id": job_id,
        "status": "closed"
    }


# ✅ 8. MARK JOB AS FILLED (Recruiter - NEW!)
@router.put("/jobs/{job_id}/mark-filled")
async def mark_job_filled(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Mark a job as filled. Only owner or admin."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    # Get the job
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership
    if current_user["role"] == "recruiter":
        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only mark your own job postings as filled"
            )

    # Update status to filled
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {"status": "filled", "filled_at": datetime.utcnow()}}
    )

    return {
        "message": "Job marked as filled successfully",
        "job_id": job_id,
        "status": "filled"
    }


# ✅ 9. UPDATE JOB STATUS (Recruiter - NEW!)
@router.put("/jobs/{job_id}/status", response_model=JobResponse)
async def update_job_status(
    job_id: str,
    status_update: JobStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update job status (active/closed/filled). Only owner or admin."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")

    db = get_db()

    # Get the job
    job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership
    if current_user["role"] == "recruiter":
        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only update status of your own job postings"
            )

    # Update status
    await db.jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "status": status_update.status,
            "status_updated_at": datetime.utcnow()
        }}
    )

    # Return updated job
    updated_job = await db.jobs.find_one({"_id": ObjectId(job_id)})
    updated_job["id"] = str(updated_job["_id"])

    return updated_job


# ===========================
# ADMIN/DEV ENDPOINTS
# ===========================

# ✅ 10. DELETE ALL JOBS (Admin/Dev)
@router.delete("/jobs/delete_all")
async def delete_all_jobs():
    """Delete all jobs. USE WITH CAUTION - for development only."""
    db = get_db()
    await db.jobs.delete_many({})
    return {"message": "All jobs have been deleted. Clean slate!"}