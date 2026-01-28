# ========================================
# app/routes/saved_job.py - COMPLETE FILE (REPLACE EXISTING)
# ========================================

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List

from app.database import get_db
from app.schemas.saved_job import SavedJobCreate, SavedJobResponse, SavedJobDetailResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/saved-jobs", tags=["Saved Jobs"])


# ✅ 1. Save a Job
@router.post("/", response_model=SavedJobResponse)
async def save_job(
    saved_job: SavedJobCreate,
    current_user: dict = Depends(get_current_user)
):
    """Save a job for later viewing. Only jobseekers can save jobs."""

    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(status_code=403, detail="Only jobseekers can save jobs")

    db = get_db()

    # Validate job ID format
    if not ObjectId.is_valid(saved_job.job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    # Validate job exists
    job = await db.jobs.find_one({"_id": ObjectId(saved_job.job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check for duplicate - prevent saving same job twice
    existing = await db.saved_jobs.find_one({
        "job_id": saved_job.job_id,
        "user_id": str(current_user["_id"])
    })

    if existing:
        raise HTTPException(status_code=400, detail="Job already saved")

    # Create saved job document
    data = {
        "job_id": saved_job.job_id,
        "user_id": str(current_user["_id"]),
        "saved_at": datetime.utcnow()
    }

    # Insert into MongoDB
    result = await db.saved_jobs.insert_one(data)

    return {
        "id": str(result.inserted_id),
        "user_id": data["user_id"],
        "job_id": data["job_id"],
        "saved_at": data["saved_at"]
    }


# ✅ 2. Get All Saved Jobs with Full Job Details
@router.get("/", response_model=List[SavedJobDetailResponse])
async def get_saved_jobs(current_user: dict = Depends(get_current_user)):
    """Get all saved jobs with complete job information."""

    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(status_code=403, detail="Only jobseekers can view saved jobs")

    db = get_db()

    # Get all saved job records for current user
    saved_jobs = await db.saved_jobs.find(
        {"user_id": str(current_user["_id"])}
    ).sort("saved_at", -1).to_list(100)

    # Fetch full job details for each saved job
    result = []
    for saved_job in saved_jobs:
        job = await db.jobs.find_one({"_id": ObjectId(saved_job["job_id"])})

        # Only include if job still exists (might have been deleted)
        if job:
            result.append({
                "saved_job_id": str(saved_job["_id"]),
                "job_id": str(job["_id"]),
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "salary": job.get("salary", ""),
                "job_type": job.get("job_type", ""),
                "skills": job.get("skills", []),
                "saved_at": saved_job["saved_at"]
            })

    return result


# ✅ 3. Check if Job is Saved
@router.get("/check/{job_id}")
async def check_if_saved(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Check if a specific job is already saved by the current user."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    db = get_db()

    # Check if saved job exists
    saved = await db.saved_jobs.find_one({
        "job_id": job_id,
        "user_id": str(current_user["_id"])
    })

    return {
        "is_saved": saved is not None,
        "saved_job_id": str(saved["_id"]) if saved else None,
        "saved_at": saved.get("saved_at") if saved else None
    }


# ✅ 4. Get Single Saved Job Details
@router.get("/{saved_job_id}", response_model=SavedJobDetailResponse)
async def get_saved_job_by_id(
    saved_job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific saved job."""

    if not ObjectId.is_valid(saved_job_id):
        raise HTTPException(status_code=400, detail="Invalid saved job ID format")

    db = get_db()

    # Find saved job
    saved_job = await db.saved_jobs.find_one({"_id": ObjectId(saved_job_id)})
    if not saved_job:
        raise HTTPException(status_code=404, detail="Saved job not found")

    # Check ownership
    if saved_job["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to view this saved job")

    # Get full job details
    job = await db.jobs.find_one({"_id": ObjectId(saved_job["job_id"])})
    if not job:
        raise HTTPException(status_code=404, detail="Original job no longer exists")

    return {
        "saved_job_id": str(saved_job["_id"]),
        "job_id": str(job["_id"]),
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "location": job.get("location", ""),
        "salary": job.get("salary", ""),
        "job_type": job.get("job_type", ""),
        "skills": job.get("skills", []),
        "saved_at": saved_job["saved_at"]
    }


# ✅ 5. Remove Saved Job (Unsave)
@router.delete("/{saved_job_id}")
async def remove_saved_job(
    saved_job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove a job from saved jobs. Only the owner can remove."""

    if not ObjectId.is_valid(saved_job_id):
        raise HTTPException(status_code=400, detail="Invalid saved job ID format")

    db = get_db()

    # Find saved job
    saved_job = await db.saved_jobs.find_one({"_id": ObjectId(saved_job_id)})
    if not saved_job:
        raise HTTPException(status_code=404, detail="Saved job not found")

    # Check ownership
    if saved_job["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to remove this saved job")

    # Delete from MongoDB
    result = await db.saved_jobs.delete_one({
        "_id": ObjectId(saved_job_id)
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Saved job not found")

    return {
        "message": "Saved job removed successfully",
        "deleted_id": saved_job_id
    }


# ✅ 6. Unsave by Job ID (Alternative delete method)
@router.delete("/by-job/{job_id}")
async def unsave_by_job_id(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Remove a saved job using the job ID instead of saved_job ID."""

    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    db = get_db()

    # Find and delete in one operation
    result = await db.saved_jobs.delete_one({
        "job_id": job_id,
        "user_id": str(current_user["_id"])
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Job not found in saved jobs")

    return {
        "message": "Job removed from saved jobs",
        "job_id": job_id
    }