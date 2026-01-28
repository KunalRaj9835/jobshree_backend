# ========================================
# app/routes/admin_analytics.py - NEW FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional
from collections import defaultdict

from app.database import get_db
from app.schemas.admin import (
    PlatformOverview,
    UserGrowthStats,
    JobTrendStats,
    TopRecruiter,
    GeographicDistribution,
    ConversionStats,
    AuditLogResponse
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin - Analytics"])


# ===========================
# ADMIN CHECK
# ===========================

def admin_required(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ===========================
# PLATFORM ANALYTICS ENDPOINTS
# ===========================

# ✅ 1. PLATFORM OVERVIEW DASHBOARD
@router.get("/analytics/overview", response_model=PlatformOverview)
async def get_platform_overview(
    current_user: dict = Depends(admin_required)
):
    """Get platform-wide overview statistics. Admin only."""

    db = get_db()

    # User statistics
    total_users = await db.users.count_documents({})
    total_jobseekers = await db.users.count_documents({"role": {"$in": ["user", "jobseeker"]}})
    total_recruiters = await db.users.count_documents({"role": "recruiter"})
    total_admins = await db.users.count_documents({"role": "admin"})

    # Active users (logged in last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_users = await db.users.count_documents({
        "last_login": {"$gte": thirty_days_ago}
    })

    suspended_users = await db.users.count_documents({"is_suspended": True})

    # Job statistics
    total_jobs = await db.jobs.count_documents({})
    active_jobs = await db.jobs.count_documents({"status": "active"})
    closed_jobs = await db.jobs.count_documents({"status": "closed"})
    filled_jobs = await db.jobs.count_documents({"status": "filled"})
    flagged_jobs = await db.jobs.count_documents({"is_flagged": True})

    # Application statistics
    total_applications = await db.applications.count_documents({})
    pending_applications = await db.applications.count_documents({"status": "Pending"})
    shortlisted_applications = await db.applications.count_documents({"status": "Shortlisted"})
    selected_applications = await db.applications.count_documents({"status": "Selected"})

    # Resume statistics
    total_resumes = await db.resumes.count_documents({})

    # Growth metrics (this month)
    first_day_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    new_users_this_month = await db.users.count_documents({
        "created_at": {"$gte": first_day_of_month}
    })

    new_jobs_this_month = await db.jobs.count_documents({
        "posted_date": {"$gte": first_day_of_month}
    })

    new_applications_this_month = await db.applications.count_documents({
        "applied_at": {"$gte": first_day_of_month}
    })

    return {
        "total_users": total_users,
        "total_jobseekers": total_jobseekers,
        "total_recruiters": total_recruiters,
        "total_admins": total_admins,
        "active_users": active_users,
        "suspended_users": suspended_users,

        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "closed_jobs": closed_jobs,
        "filled_jobs": filled_jobs,
        "flagged_jobs": flagged_jobs,

        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "shortlisted_applications": shortlisted_applications,
        "selected_applications": selected_applications,

        "total_resumes": total_resumes,

        "new_users_this_month": new_users_this_month,
        "new_jobs_this_month": new_jobs_this_month,
        "new_applications_this_month": new_applications_this_month
    }


# ✅ 2. USER GROWTH STATISTICS
@router.get("/analytics/users", response_model=UserGrowthStats)
async def get_user_growth_stats(
    period: str = Query("monthly", description="Period: daily, weekly, monthly"),
    months: int = Query(6, description="Number of months to analyze"),
    current_user: dict = Depends(admin_required)
):
    """Get user growth statistics over time. Admin only."""

    db = get_db()

    # Get all users with creation dates
    users = await db.users.find(
        {"created_at": {"$exists": True}},
        {"created_at": 1}
    ).to_list(10000)

    # Group by period
    growth_data = defaultdict(int)

    for user in users:
        created_at = user.get("created_at")
        if created_at:
            if period == "daily":
                key = created_at.strftime("%Y-%m-%d")
            elif period == "weekly":
                key = f"{created_at.year}-W{created_at.isocalendar()[1]}"
            else:  # monthly
                key = created_at.strftime("%Y-%m")

            growth_data[key] += 1

    # Convert to list format
    data = [{"date": k, "count": v} for k, v in sorted(growth_data.items())]

    # Calculate growth rate
    if len(data) >= 2:
        recent = sum([d["count"] for d in data[-2:]])
        previous = sum([d["count"] for d in data[-4:-2]]) if len(data) >= 4 else 1
        growth_rate = ((recent - previous) / previous * 100) if previous > 0 else 0
    else:
        growth_rate = 0.0

    return {
        "period": period,
        "data": data[-months*4:] if period == "weekly" else data[-months:],  # Show recent data
        "total_growth": len(users),
        "growth_rate": round(growth_rate, 2)
    }


# ✅ 3. JOB POSTING TRENDS
@router.get("/analytics/jobs", response_model=JobTrendStats)
async def get_job_trends(
    period: str = Query("monthly", description="Period: daily, weekly, monthly"),
    months: int = Query(6, description="Number of months to analyze"),
    current_user: dict = Depends(admin_required)
):
    """Get job posting trends over time. Admin only."""

    db = get_db()

    # Get all jobs
    jobs = await db.jobs.find({"posted_date": {"$exists": True}}).to_list(10000)

    # Group by period
    trend_data = defaultdict(int)
    location_counts = defaultdict(int)
    job_type_counts = defaultdict(int)

    for job in jobs:
        posted_date = job.get("posted_date")
        if posted_date:
            if period == "daily":
                key = posted_date.strftime("%Y-%m-%d")
            elif period == "weekly":
                key = f"{posted_date.year}-W{posted_date.isocalendar()[1]}"
            else:
                key = posted_date.strftime("%Y-%m")

            trend_data[key] += 1

        # Location stats
        location = job.get("location", "Unknown")
        location_counts[location] += 1

        # Job type stats
        job_type = job.get("job_type", "Unknown")
        job_type_counts[job_type] += 1

    # Convert to list format
    data = [{"date": k, "count": v} for k, v in sorted(trend_data.items())]

    # Top locations
    top_locations = [
        {"location": k, "count": v}
        for k, v in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # Top job types
    top_job_types = [
        {"job_type": k, "count": v}
        for k, v in sorted(job_type_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Calculate average applications per job
    total_apps = await db.applications.count_documents({})
    avg_apps = total_apps / len(jobs) if len(jobs) > 0 else 0

    return {
        "period": period,
        "data": data[-months*4:] if period == "weekly" else data[-months:],
        "top_locations": top_locations,
        "top_job_types": top_job_types,
        "average_applications_per_job": round(avg_apps, 2)
    }


# ✅ 4. APPLICATION STATISTICS
@router.get("/analytics/applications")
async def get_application_stats(
    current_user: dict = Depends(admin_required)
):
    """Get application statistics. Admin only."""

    db = get_db()

    # Status breakdown
    total = await db.applications.count_documents({})
    pending = await db.applications.count_documents({"status": "Pending"})
    shortlisted = await db.applications.count_documents({"status": "Shortlisted"})
    rejected = await db.applications.count_documents({"status": "Rejected"})
    selected = await db.applications.count_documents({"status": "Selected"})

    # Get applications with timestamps for time analysis
    applications = await db.applications.find(
        {"applied_at": {"$exists": True}, "status": {"$in": ["Shortlisted", "Selected"]}}
    ).to_list(1000)

    # Calculate average time to shortlist/select
    time_to_shortlist = []
    time_to_select = []

    for app in applications:
        applied_at = app.get("applied_at")
        status_updated_at = app.get("status_updated_at")

        if applied_at and status_updated_at:
            days = (status_updated_at - applied_at).days
            if app["status"] == "Shortlisted":
                time_to_shortlist.append(days)
            elif app["status"] == "Selected":
                time_to_select.append(days)

    avg_time_shortlist = sum(time_to_shortlist) / len(time_to_shortlist) if time_to_shortlist else 0
    avg_time_select = sum(time_to_select) / len(time_to_select) if time_to_select else 0

    return {
        "total_applications": total,
        "pending": pending,
        "shortlisted": shortlisted,
        "rejected": rejected,
        "selected": selected,
        "shortlisted_rate": round((shortlisted / total * 100), 2) if total > 0 else 0,
        "selected_rate": round((selected / total * 100), 2) if total > 0 else 0,
        "rejected_rate": round((rejected / total * 100), 2) if total > 0 else 0,
        "average_time_to_shortlist_days": round(avg_time_shortlist, 1),
        "average_time_to_selection_days": round(avg_time_select, 1)
    }


# ✅ 5. TOP RECRUITERS
@router.get("/analytics/top-recruiters", response_model=List[TopRecruiter])
async def get_top_recruiters(
    limit: int = Query(10, le=50),
    current_user: dict = Depends(admin_required)
):
    """Get top recruiters by activity. Admin only."""

    db = get_db()

    # Get all recruiters
    recruiters = await db.users.find({"role": "recruiter"}).to_list(1000)

    recruiter_stats = []

    for recruiter in recruiters:
        recruiter_id = str(recruiter["_id"])

        # Count jobs
        total_jobs = await db.jobs.count_documents({"recruiter_id": recruiter_id})
        active_jobs = await db.jobs.count_documents({"recruiter_id": recruiter_id, "status": "active"})

        # Count applications for recruiter's jobs
        jobs = await db.jobs.find({"recruiter_id": recruiter_id}).to_list(1000)
        job_ids = [str(job["_id"]) for job in jobs]

        total_applications = await db.applications.count_documents({"job_id": {"$in": job_ids}})

        avg_apps = total_applications / total_jobs if total_jobs > 0 else 0

        recruiter_stats.append({
            "recruiter_id": recruiter_id,
            "recruiter_name": recruiter.get("name", ""),
            "recruiter_email": recruiter.get("email", ""),
            "total_jobs_posted": total_jobs,
            "total_applications_received": total_applications,
            "active_jobs": active_jobs,
            "average_applications_per_job": round(avg_apps, 2)
        })

    # Sort by total applications
    recruiter_stats.sort(key=lambda x: x["total_applications_received"], reverse=True)

    return recruiter_stats[:limit]


# ✅ 6. GEOGRAPHIC DISTRIBUTION
@router.get("/analytics/geographic", response_model=List[GeographicDistribution])
async def get_geographic_distribution(
    limit: int = Query(20, le=100),
    current_user: dict = Depends(admin_required)
):
    """Get geographic distribution of jobs and users. Admin only."""

    db = get_db()

    # Get location data
    location_stats = defaultdict(lambda: {"jobs": 0, "users": 0, "applications": 0})

    # Jobs by location
    jobs = await db.jobs.find({}, {"location": 1}).to_list(10000)
    for job in jobs:
        location = job.get("location", "Unknown")
        location_stats[location]["jobs"] += 1

    # Users by location
    users = await db.users.find({"location": {"$exists": True}}, {"location": 1}).to_list(10000)
    for user in users:
        location = user.get("location", "Unknown")
        location_stats[location]["users"] += 1

    # Applications (count via jobs)
    for job in jobs:
        job_id = str(job["_id"])
        location = job.get("location", "Unknown")
        app_count = await db.applications.count_documents({"job_id": job_id})
        location_stats[location]["applications"] += app_count

    # Convert to list
    result = [
        {
            "location": location,
            "jobs_count": stats["jobs"],
            "users_count": stats["users"],
            "applications_count": stats["applications"]
        }
        for location, stats in location_stats.items()
    ]

    # Sort by job count
    result.sort(key=lambda x: x["jobs_count"], reverse=True)

    return result[:limit]


# ✅ 7. AUDIT LOGS
@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action type"),
    admin_id: Optional[str] = Query(None, description="Filter by admin"),
    limit: int = Query(100, le=500),
    current_user: dict = Depends(admin_required)
):
    """Get audit logs of admin actions. Admin only."""

    db = get_db()

    query = {}

    if action:
        query["action"] = action

    if admin_id:
        query["admin_id"] = admin_id

    logs = await db.audit_logs.find(query).sort("timestamp", -1).limit(limit).to_list(limit)

    return [
        {
            "id": str(log["_id"]),
            "action": log["action"],
            "admin_id": log["admin_id"],
            "admin_name": log["admin_name"],
            "target_type": log["target_type"],
            "target_id": log.get("target_id"),
            "details": log.get("details", {}),
            "timestamp": log["timestamp"],
            "ip_address": log.get("ip_address")
        }
        for log in logs
    ]


# ✅ 8. EXPORT COMPREHENSIVE REPORT
@router.get("/analytics/export")
async def export_analytics_report(
    current_user: dict = Depends(admin_required)
):
    """Export comprehensive analytics report as CSV. Admin only."""

    db = get_db()

    # Gather all statistics
    overview = await get_platform_overview(current_user)

    # Create CSV content
    csv_lines = [
        "Naukri Job Portal - Analytics Report",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "PLATFORM OVERVIEW",
        "=================",
        f"Total Users,{overview['total_users']}",
        f"Total Jobseekers,{overview['total_jobseekers']}",
        f"Total Recruiters,{overview['total_recruiters']}",
        f"Total Admins,{overview['total_admins']}",
        f"Active Users (30 days),{overview['active_users']}",
        f"Suspended Users,{overview['suspended_users']}",
        "",
        "JOB STATISTICS",
        "==============",
        f"Total Jobs,{overview['total_jobs']}",
        f"Active Jobs,{overview['active_jobs']}",
        f"Closed Jobs,{overview['closed_jobs']}",
        f"Filled Jobs,{overview['filled_jobs']}",
        f"Flagged Jobs,{overview['flagged_jobs']}",
        "",
        "APPLICATION STATISTICS",
        "======================",
        f"Total Applications,{overview['total_applications']}",
        f"Pending Applications,{overview['pending_applications']}",
        f"Shortlisted Applications,{overview['shortlisted_applications']}",
        f"Selected Applications,{overview['selected_applications']}",
        "",
        "GROWTH METRICS (This Month)",
        "===========================",
        f"New Users,{overview['new_users_this_month']}",
        f"New Jobs,{overview['new_jobs_this_month']}",
        f"New Applications,{overview['new_applications_this_month']}"
    ]

    csv_content = "\n".join(csv_lines)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=analytics_report_{datetime.utcnow().strftime('%Y%m%d')}.csv"
        }
    )