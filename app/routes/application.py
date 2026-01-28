# ========================================
# app/routes/application.py - UPDATED VERSION (COMPLETE REPLACEMENT)
# ========================================

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from bson import ObjectId
from datetime import datetime
from typing import List, Optional

from app.database import get_db
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationStatusUpdate,
    ApplicationDetailResponse,
    ApplicationFullDetailResponse,
    ApplicationBulkUpdate
)
from app.utils.auth import get_current_user

router = APIRouter(tags=["Applications"])

# ===========================
# JOBSEEKER ENDPOINTS
# ===========================

# ✅ 1. APPLY FOR JOB (Jobseeker)
@router.post("/applications", response_model=ApplicationResponse)
async def apply_job(application: ApplicationCreate, current_user: dict = Depends(get_current_user)):
    """Submit a job application. Only jobseekers can apply."""

    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(status_code=403, detail="Only jobseekers can apply")

    db = get_db()

    # Validate Job ID
    if not ObjectId.is_valid(application.job_id):
        raise HTTPException(status_code=400, detail="Invalid Job ID")

    job = await db.jobs.find_one({"_id": ObjectId(application.job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if job is accepting applications
    if job.get("status") != "active":
        raise HTTPException(
            status_code=400,
            detail=f"This job is no longer accepting applications. Status: {job.get('status')}"
        )

    # Validate Resume ID
    if not ObjectId.is_valid(application.resume_id):
        raise HTTPException(status_code=400, detail="Invalid Resume ID")

    resume = await db.resumes.find_one({"_id": ObjectId(application.resume_id)})
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    # Verify resume ownership
    if str(resume["jobseeker_id"]) != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Can only apply with your own resume")

    # Check for duplicate application
    existing = await db.applications.find_one({
        "job_id": application.job_id,
        "user_id": str(current_user["_id"])
    })
    if existing:
        raise HTTPException(status_code=400, detail="You have already applied to this job")

    application_data = {
        "job_id": application.job_id,
        "user_id": str(current_user["_id"]),
        "resume_id": application.resume_id,
        "cover_letter": application.cover_letter,
        "status": "Pending",
        "applied_at": datetime.utcnow(),
        "has_notes": False,  # NEW
        "notes_count": 0  # NEW
    }

    result = await db.applications.insert_one(application_data)
    return {**application_data, "id": str(result.inserted_id)}


# ✅ 2. GET MY APPLICATIONS (Jobseeker)
@router.get("/my-applications", response_model=List[ApplicationDetailResponse])
async def get_my_applications(
    status: Optional[str] = Query(None, description="Filter by status: Pending, Shortlisted, Rejected, Selected"),
    current_user: dict = Depends(get_current_user)
):
    """Get all applications submitted by the current jobseeker."""

    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(status_code=403, detail="Only jobseekers can view their applications")

    db = get_db()

    # Build query
    query = {"user_id": str(current_user["_id"])}
    if status:
        query["status"] = status

    # Get applications
    applications = await db.applications.find(query).sort("applied_at", -1).to_list(100)

    # Enrich with job details
    result = []
    for app in applications:
        job = await db.jobs.find_one({"_id": ObjectId(app["job_id"])})
        if job:  # Job might be deleted
            result.append({
                "application_id": str(app["_id"]),
                "job_id": str(job["_id"]),
                "job_title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "status": app["status"],
                "applied_at": app["applied_at"],
                "cover_letter": app.get("cover_letter"),
                "has_notes": app.get("has_notes", False),
                "notes_count": app.get("notes_count", 0)
            })

    return result


# ✅ 3. WITHDRAW APPLICATION (Jobseeker)
@router.delete("/applications/{application_id}")
async def withdraw_application(
    application_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Withdraw a job application. Only works for Pending applications."""

    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")

    db = get_db()

    # Check ownership
    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Only allow withdrawal if status is "Pending"
    if application["status"] != "Pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot withdraw application with status: {application['status']}"
        )

    await db.applications.delete_one({"_id": ObjectId(application_id)})

    return {"message": "Application withdrawn successfully"}


# ✅ 4. GET APPLICATION DETAILS (Jobseeker)
@router.get("/applications/{application_id}", response_model=ApplicationDetailResponse)
async def get_application_details(
    application_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific application."""

    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")

    db = get_db()

    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Check ownership (jobseeker) or admin/recruiter access
    if current_user["role"] in ["jobseeker", "user"]:
        if application["user_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized")

    # Get job details
    job = await db.jobs.find_one({"_id": ObjectId(application["job_id"])})
    if not job:
        raise HTTPException(status_code=404, detail="Job no longer available")

    return {
        "application_id": str(application["_id"]),
        "job_id": str(job["_id"]),
        "job_title": job.get("title"),
        "company": job.get("company"),
        "location": job.get("location"),
        "status": application["status"],
        "applied_at": application["applied_at"],
        "cover_letter": application.get("cover_letter"),
        "has_notes": application.get("has_notes", False),
        "notes_count": application.get("notes_count", 0)
    }


# ===========================
# RECRUITER ENDPOINTS
# ===========================

# ✅ 5. GET RECRUITER'S APPLICATIONS (Recruiter - NEW!)
@router.get("/recruiter/applications", response_model=List[ApplicationFullDetailResponse])
async def get_recruiter_applications(
    job_id: Optional[str] = Query(None, description="Filter by specific job"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """Get all applications for jobs posted by the current recruiter."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters and admins can access this")

    db = get_db()

    # Get recruiter's job IDs
    jobs_query = {"recruiter_id": str(current_user["_id"])}
    if current_user["role"] == "admin":
        jobs_query = {}  # Admins see all

    if job_id:
        # If specific job requested, verify ownership
        if not ObjectId.is_valid(job_id):
            raise HTTPException(status_code=400, detail="Invalid job ID")

        job = await db.jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if current_user["role"] == "recruiter" and job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized to view this job's applications")

        job_ids = [job_id]
    else:
        jobs = await db.jobs.find(jobs_query).to_list(1000)
        job_ids = [str(job["_id"]) for job in jobs]

    # Build applications query
    app_query = {"job_id": {"$in": job_ids}}
    if status:
        app_query["status"] = status

    # Get applications
    applications = await db.applications.find(app_query).sort("applied_at", -1).to_list(500)

    # Enrich with candidate and job details
    result = []
    for app in applications:
        # Get job details
        job = await db.jobs.find_one({"_id": ObjectId(app["job_id"])})
        if not job:
            continue

        # Get candidate details
        candidate = await db.users.find_one({"_id": ObjectId(app["user_id"])})
        if not candidate:
            continue

        result.append({
            "application_id": str(app["_id"]),
            "job_id": str(job["_id"]),
            "job_title": job.get("title", ""),
            "status": app["status"],
            "applied_at": app["applied_at"],
            "cover_letter": app.get("cover_letter"),
            "resume_id": app["resume_id"],

            # Candidate details
            "candidate_id": str(candidate["_id"]),
            "candidate_name": candidate.get("name", ""),
            "candidate_email": candidate.get("email", ""),
            "candidate_phone": candidate.get("phone"),
            "candidate_location": candidate.get("location"),
            "candidate_skills": candidate.get("skills"),
            "candidate_experience_years": candidate.get("experience_years"),
            "candidate_headline": candidate.get("headline"),

            # Social links
            "linkedin_url": candidate.get("linkedin_url"),
            "github_url": candidate.get("github_url"),
            "portfolio_url": candidate.get("portfolio_url"),

            # Notes tracking
            "has_notes": app.get("has_notes", False),
            "notes_count": app.get("notes_count", 0)
        })

    return result


# ✅ 6. GET FULL APPLICATION DETAILS (Recruiter - NEW!)
@router.get("/applications/{application_id}/full-details", response_model=ApplicationFullDetailResponse)
async def get_full_application_details(
    application_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get complete application details including candidate profile."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters and admins can access full details")

    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID")

    db = get_db()

    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Verify recruiter owns the job
    job = await db.jobs.find_one({"_id": ObjectId(application["job_id"])})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if current_user["role"] == "recruiter" and job.get("recruiter_id") != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get candidate details
    candidate = await db.users.find_one({"_id": ObjectId(application["user_id"])})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return {
        "application_id": str(application["_id"]),
        "job_id": str(job["_id"]),
        "job_title": job.get("title", ""),
        "status": application["status"],
        "applied_at": application["applied_at"],
        "cover_letter": application.get("cover_letter"),
        "resume_id": application["resume_id"],

        # Candidate details
        "candidate_id": str(candidate["_id"]),
        "candidate_name": candidate.get("name", ""),
        "candidate_email": candidate.get("email", ""),
        "candidate_phone": candidate.get("phone"),
        "candidate_location": candidate.get("location"),
        "candidate_skills": candidate.get("skills"),
        "candidate_experience_years": candidate.get("experience_years"),
        "candidate_headline": candidate.get("headline"),

        # Social links
        "linkedin_url": candidate.get("linkedin_url"),
        "github_url": candidate.get("github_url"),
        "portfolio_url": candidate.get("portfolio_url"),

        # Notes tracking
        "has_notes": application.get("has_notes", False),
        "notes_count": application.get("notes_count", 0)
    }


# ✅ 7. UPDATE APPLICATION STATUS (Recruiter/Admin)
@router.put("/applications/{application_id}/status")
async def update_status(
    application_id: str,
    status_update: ApplicationStatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update application status. Only recruiter/admin can update."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    db = get_db()

    # Get application
    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Verify recruiter owns the job
    if current_user["role"] == "recruiter":
        job = await db.jobs.find_one({"_id": ObjectId(application["job_id"])})
        if not job or job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Not authorized")

    # Update status
    result = await db.applications.update_one(
        {"_id": ObjectId(application_id)},
        {"$set": {
            "status": status_update.status,
            "status_updated_at": datetime.utcnow(),
            "updated_by": str(current_user["_id"])
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Application not found")

    return {"message": "Status updated successfully", "new_status": status_update.status}


# ✅ 8. BULK UPDATE APPLICATION STATUS (Recruiter - NEW!)
@router.put("/applications/bulk-update")
async def bulk_update_status(
    bulk_update: ApplicationBulkUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update status for multiple applications at once."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    db = get_db()

    # Validate all application IDs
    valid_ids = [ObjectId(id) for id in bulk_update.application_ids if ObjectId.is_valid(id)]
    if len(valid_ids) != len(bulk_update.application_ids):
        raise HTTPException(status_code=400, detail="Some application IDs are invalid")

    # Verify recruiter owns all these applications' jobs
    if current_user["role"] == "recruiter":
        applications = await db.applications.find({"_id": {"$in": valid_ids}}).to_list(1000)
        job_ids = list(set([app["job_id"] for app in applications]))

        for job_id in job_ids:
            job = await db.jobs.find_one({"_id": ObjectId(job_id)})
            if not job or job.get("recruiter_id") != str(current_user["_id"]):
                raise HTTPException(
                    status_code=403,
                    detail="You can only update applications for your own jobs"
                )

    # Perform bulk update
    result = await db.applications.update_many(
        {"_id": {"$in": valid_ids}},
        {"$set": {
            "status": bulk_update.status,
            "status_updated_at": datetime.utcnow(),
            "updated_by": str(current_user["_id"])
        }}
    )

    return {
        "message": f"Successfully updated {result.modified_count} applications",
        "updated_count": result.modified_count,
        "new_status": bulk_update.status
    }


# ✅ 9. EXPORT APPLICATIONS TO CSV (Recruiter - NEW!)
@router.get("/recruiter/applications/export")
async def export_applications_csv(
    job_id: Optional[str] = Query(None, description="Filter by specific job"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """Export applications to CSV format."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Only recruiters and admins can export")

    # Import export utility
    from app.utils.export import export_applications_to_csv, create_csv_response_headers

    db = get_db()

    # Get recruiter's job IDs
    jobs_query = {"recruiter_id": str(current_user["_id"])}
    if current_user["role"] == "admin":
        jobs_query = {}

    if job_id:
        jobs_query["_id"] = ObjectId(job_id)

    jobs = await db.jobs.find(jobs_query).to_list(1000)
    job_ids = [str(job["_id"]) for job in jobs]

    # Build applications query
    app_query = {"job_id": {"$in": job_ids}}
    if status:
        app_query["status"] = status

    # Get applications with candidate details
    applications = await db.applications.find(app_query).to_list(1000)

    export_data = []
    for app in applications:
        job = await db.jobs.find_one({"_id": ObjectId(app["job_id"])})
        candidate = await db.users.find_one({"_id": ObjectId(app["user_id"])})

        if job and candidate:
            export_data.append({
                "application_id": str(app["_id"]),
                "candidate_name": candidate.get("name", ""),
                "candidate_email": candidate.get("email", ""),
                "candidate_phone": candidate.get("phone", ""),
                "candidate_skills": candidate.get("skills", []),
                "candidate_experience": candidate.get("experience_years"),
                "candidate_location": candidate.get("location", ""),
                "job_title": job.get("title", ""),
                "status": app["status"],
                "applied_at": app["applied_at"],
                "resume_id": app["resume_id"]
            })

    # Generate CSV
    csv_content = export_applications_to_csv(export_data)

    # Return as downloadable file
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers=create_csv_response_headers(f"applications_{datetime.utcnow().strftime('%Y%m%d')}")
    )


# ===========================
# ADMIN ENDPOINTS
# ===========================

# ✅ 10. VIEW ALL APPLICATIONS (Admin)
@router.get("/applications", response_model=List[ApplicationResponse])
async def get_all_applications(current_user: dict = Depends(get_current_user)):
    """Get all applications in the system. Admin only."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    db = get_db()
    applications = await db.applications.find().to_list(100)

    return [{"id": str(app["_id"]), **app} for app in applications]