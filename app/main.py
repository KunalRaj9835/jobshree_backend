# ========================================
# app/main.py - UPDATED VERSION WITH ADMIN ROUTES
# ========================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import connect_to_mongo, close_mongo_connection

# ===========================
# IMPORT ALL ROUTERS
# ===========================

# User & Auth
from app.routes.user import router as user_router

# Jobs
from app.routes.job import router as job_router

# Resumes
from app.routes.resume import router as resume_router

# Applications
from app.routes.application import router as application_router

# Saved Jobs
from app.routes.saved_job import router as saved_job_router

# Jobseeker Profile Features
from app.routes.experience import router as experience_router
from app.routes.education import router as education_router
from app.routes.certification import router as certification_router

# Recruiter Features
from app.routes.recruiter_dashboard import router as recruiter_dashboard_router
from app.routes.application_notes import router as application_notes_router

# Admin Features (NEW!)
from app.routes.admin_users import router as admin_users_router
from app.routes.admin_content import router as admin_content_router
from app.routes.admin_analytics import router as admin_analytics_router
import os
from dotenv import load_dotenv

load_dotenv()
# ===========================
# CREATE FASTAPI APP
# ===========================

app = FastAPI(
    title="Naukri Job Portal API",
    description="Complete job portal backend with jobseeker, recruiter, and admin features",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ===========================
# CORS MIDDLEWARE
# ===========================
raw_origins = os.getenv("ALLOWED_ORIGINS", "")
origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ===========================
# DATABASE EVENTS
# ===========================

@app.on_event("startup")
async def start_db():
    """Connect to MongoDB on startup"""
    await connect_to_mongo()

@app.on_event("shutdown")
async def stop_db():
    """Close MongoDB connection on shutdown"""
    await close_mongo_connection()

# ===========================
# REGISTER ROUTERS
# ===========================

# User & Authentication
app.include_router(user_router, tags=["Users"])

# Jobs
app.include_router(job_router, tags=["Jobs"])

# Resumes
app.include_router(resume_router, tags=["Resumes"])

# Applications
app.include_router(application_router, tags=["Applications"])

# Saved Jobs
app.include_router(saved_job_router, tags=["Saved Jobs"])

# Jobseeker Profile Features
app.include_router(experience_router, tags=["Work Experience"])
app.include_router(education_router, tags=["Education"])
app.include_router(certification_router, tags=["Certifications"])

# Recruiter Features
app.include_router(recruiter_dashboard_router, tags=["Recruiter Dashboard"])
app.include_router(application_notes_router, tags=["Application Notes"])

# Admin Features (NEW!)
app.include_router(admin_users_router, tags=["Admin - User Management"])
app.include_router(admin_content_router, tags=["Admin - Content Moderation"])
app.include_router(admin_analytics_router, tags=["Admin - Analytics"])

# ===========================
# ROOT ENDPOINTS
# ===========================

@app.get("/")
async def root():
    """API root endpoint with feature summary"""
    return {
        "status": "✅ Naukri Job Portal API Running",
        "version": "4.0.0",
        "documentation": "/docs",
        "features": {
            "jobseeker": [
                "✅ Complete profile management with social links",
                "✅ Resume upload/download with GridFS storage",
                "✅ Multiple resumes with primary selection",
                "✅ Work experience tracking",
                "✅ Education history",
                "✅ Certifications management",
                "✅ Advanced job search with filters",
                "✅ Save/unsave jobs",
                "✅ Apply to jobs with resume",
                "✅ View application history",
                "✅ Withdraw pending applications"
            ],
            "recruiter": [
                "✅ Post new jobs",
                "✅ Edit posted jobs",
                "✅ Delete/close jobs",
                "✅ Mark jobs as filled",
                "✅ View only own posted jobs",
                "✅ View applications for own jobs",
                "✅ Filter applications by status",
                "✅ Add notes/comments to applications",
                "✅ View full candidate profiles",
                "✅ Bulk update application statuses",
                "✅ Export applications to CSV",
                "✅ Dashboard with analytics",
                "✅ Job-specific statistics"
            ],
            "admin": [
                "✅ Full system access",
                "✅ User management (suspend/activate/delete/role change)",
                "✅ Content moderation (flag/unflag jobs)",
                "✅ Bulk delete operations",
                "✅ Platform-wide analytics",
                "✅ User growth statistics",
                "✅ Job posting trends",
                "✅ Top recruiters analysis",
                "✅ Geographic distribution",
                "✅ Audit logs",
                "✅ Export comprehensive reports"
            ]
        },
        "endpoints": {
            "authentication": ["/users/register", "/users/login"],
            "jobseeker": [
                "/users/profile",
                "/experience",
                "/education",
                "/certifications",
                "/upload-resume",
                "/my-resumes",
                "/jobs",
                "/saved-jobs",
                "/applications",
                "/my-applications"
            ],
            "recruiter": [
                "/jobs (POST/PUT/DELETE)",
                "/recruiter/dashboard",
                "/recruiter/my-jobs",
                "/recruiter/applications",
                "/recruiter/jobs/{id}/analytics",
                "/applications/{id}/notes",
                "/applications/bulk-update",
                "/recruiter/applications/export"
            ],
            "admin": [
                "/admin/users",
                "/admin/users/{id}/suspend",
                "/admin/users/{id}/activate",
                "/admin/users/{id}/role",
                "/admin/users/{id}/reset-password",
                "/admin/jobs/bulk-delete",
                "/admin/jobs/{id}/flag",
                "/admin/flagged-content",
                "/admin/analytics/overview",
                "/admin/analytics/users",
                "/admin/analytics/jobs",
                "/admin/analytics/top-recruiters",
                "/admin/audit-logs"
            ],
            "public": [
                "/jobs (GET with filters)",
                "/jobs/{job_id}"
            ]
        },
        "database": {
            "collections": [
                "users",
                "jobs",
                "applications",
                "resumes (GridFS)",
                "saved_jobs",
                "work_experience",
                "education",
                "certifications",
                "application_notes",
                "content_flags",
                "audit_logs"
            ]
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "version": "4.0.0"
    }


@app.get("/api/stats")
async def api_stats():
    """Get API statistics"""
    from app.database import get_db

    db = get_db()

    try:
        users_count = await db.users.count_documents({})
        jobs_count = await db.jobs.count_documents({})
        applications_count = await db.applications.count_documents({})

        return {
            "total_users": users_count,
            "total_jobs": jobs_count,
            "total_applications": applications_count,
            "active_jobs": await db.jobs.count_documents({"status": "active"}),
            "flagged_jobs": await db.jobs.count_documents({"is_flagged": True}),
            "suspended_users": await db.users.count_documents({"is_suspended": True})
        }
    except Exception as e:
        return {
            "error": "Could not fetch stats",
            "message": str(e)
        }


from app.routes.password_reset import router as password_reset_router
# Password Reset Feature
app.include_router(password_reset_router, tags=["Password Reset"])
