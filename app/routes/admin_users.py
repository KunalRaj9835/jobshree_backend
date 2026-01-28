# ========================================
# app/routes/admin_users.py - NEW FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from datetime import datetime, timedelta
from typing import List, Optional

from app.database import get_db
from app.schemas.admin import (
    UserSuspend,
    UserRoleChange,
    PasswordReset,
    UserDetailResponse,
    AuditLogCreate
)
from app.utils.auth import get_current_user
from app.utils.security import get_password_hash

router = APIRouter(prefix="/admin", tags=["Admin - User Management"])


# ===========================
# HELPER FUNCTION: LOG AUDIT
# ===========================

async def log_admin_action(
    db,
    admin_id: str,
    admin_name: str,
    action: str,
    target_type: str,
    target_id: str = None,
    details: dict = None
):
    """Helper function to log admin actions"""
    audit_entry = {
        "action": action,
        "admin_id": admin_id,
        "admin_name": admin_name,
        "target_type": target_type,
        "target_id": target_id,
        "details": details or {},
        "timestamp": datetime.utcnow(),
        "ip_address": None  # Can be added from request
    }
    await db.audit_logs.insert_one(audit_entry)


# ===========================
# ADMIN CHECK DECORATOR
# ===========================

def admin_required(current_user: dict = Depends(get_current_user)):
    """Verify user is admin"""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return current_user


# ===========================
# USER MANAGEMENT ENDPOINTS
# ===========================

# ✅ 1. LIST ALL USERS WITH FILTERS
@router.get("/users", response_model=List[UserDetailResponse])
async def list_all_users(
    role: Optional[str] = Query(None, description="Filter by role"),
    is_suspended: Optional[bool] = Query(None, description="Filter by suspension status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    limit: int = Query(100, le=500),
    current_user: dict = Depends(admin_required)
):
    """List all users with advanced filtering. Admin only."""

    db = get_db()

    # Build query
    query = {}

    if role:
        query["role"] = role

    if is_suspended is not None:
        query["is_suspended"] = is_suspended

    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]

    # Get users
    users = await db.users.find(query, {"password": 0}).limit(limit).to_list(limit)

    # Enrich with statistics
    result = []
    for user in users:
        user_id = str(user["_id"])

        # Get stats based on role
        jobs_posted = 0
        applications_count = 0
        resumes_count = 0

        if user.get("role") in ["recruiter", "admin"]:
            jobs_posted = await db.jobs.count_documents({"recruiter_id": user_id})

        if user.get("role") in ["jobseeker", "user"]:
            applications_count = await db.applications.count_documents({"user_id": user_id})
            resumes_count = await db.resumes.count_documents({"jobseeker_id": ObjectId(user_id)})

        result.append({
            "id": user_id,
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "role": user.get("role", "user"),
            "is_suspended": user.get("is_suspended", False),
            "suspended_at": user.get("suspended_at"),
            "suspended_by": user.get("suspended_by"),
            "suspension_reason": user.get("suspension_reason"),
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login"),
            "login_count": user.get("login_count", 0),
            "total_jobs_posted": jobs_posted,
            "total_applications": applications_count,
            "total_resumes": resumes_count
        })

    return result


# ✅ 2. GET USER DETAILS WITH STATS
@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_details(
    user_id: str,
    current_user: dict = Depends(admin_required)
):
    """Get detailed information about a specific user. Admin only."""

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get statistics
    jobs_posted = 0
    applications_count = 0
    resumes_count = 0

    if user.get("role") in ["recruiter", "admin"]:
        jobs_posted = await db.jobs.count_documents({"recruiter_id": user_id})

    if user.get("role") in ["jobseeker", "user"]:
        applications_count = await db.applications.count_documents({"user_id": user_id})
        resumes_count = await db.resumes.count_documents({"jobseeker_id": ObjectId(user_id)})

    return {
        "id": str(user["_id"]),
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "role": user.get("role", "user"),
        "is_suspended": user.get("is_suspended", False),
        "suspended_at": user.get("suspended_at"),
        "suspended_by": user.get("suspended_by"),
        "suspension_reason": user.get("suspension_reason"),
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login"),
        "login_count": user.get("login_count", 0),
        "total_jobs_posted": jobs_posted,
        "total_applications": applications_count,
        "total_resumes": resumes_count
    }


# ✅ 3. SUSPEND USER
@router.put("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    suspend_data: UserSuspend,
    current_user: dict = Depends(admin_required)
):
    """Suspend a user account. Admin only."""

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-suspension
    if str(user["_id"]) == str(current_user["_id"]):
        raise HTTPException(status_code=400, detail="Cannot suspend your own account")

    # Prevent suspending other admins (optional safety)
    if user.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Cannot suspend admin accounts")

    # Update user
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_suspended": True,
            "suspended_at": datetime.utcnow(),
            "suspended_by": str(current_user["_id"]),
            "suspension_reason": suspend_data.reason,
            "suspension_expires": datetime.utcnow() + timedelta(days=suspend_data.duration_days) if suspend_data.duration_days else None
        }}
    )

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="user_suspended",
        target_type="user",
        target_id=user_id,
        details={
            "reason": suspend_data.reason,
            "duration_days": suspend_data.duration_days,
            "suspended_user_email": user["email"]
        }
    )

    return {
        "message": "User suspended successfully",
        "user_id": user_id,
        "user_email": user["email"],
        "suspension_reason": suspend_data.reason
    }


# ✅ 4. ACTIVATE USER
@router.put("/users/{user_id}/activate")
async def activate_user(
    user_id: str,
    current_user: dict = Depends(admin_required)
):
    """Activate a suspended user account. Admin only."""

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update user
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_suspended": False,
            "suspended_at": None,
            "suspended_by": None,
            "suspension_reason": None,
            "suspension_expires": None,
            "activated_at": datetime.utcnow(),
            "activated_by": str(current_user["_id"])
        }}
    )

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="user_activated",
        target_type="user",
        target_id=user_id,
        details={"activated_user_email": user["email"]}
    )

    return {
        "message": "User activated successfully",
        "user_id": user_id,
        "user_email": user["email"]
    }


# ✅ 5. DELETE USER
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    permanent: bool = Query(False, description="Permanently delete all user data"),
    current_user: dict = Depends(admin_required)
):
    """Delete a user account. Admin only."""

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deletion
    if str(user["_id"]) == str(current_user["_id"]):
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # Prevent deleting other admins
    if user.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin accounts")

    deleted_data = {}

    if permanent:
        # Delete all associated data

        # Delete applications
        apps_deleted = await db.applications.delete_many({"user_id": user_id})
        deleted_data["applications"] = apps_deleted.deleted_count

        # Delete jobs (if recruiter)
        if user.get("role") in ["recruiter", "admin"]:
            jobs_deleted = await db.jobs.delete_many({"recruiter_id": user_id})
            deleted_data["jobs"] = jobs_deleted.deleted_count

        # Delete resumes
        resumes_deleted = await db.resumes.delete_many({"jobseeker_id": ObjectId(user_id)})
        deleted_data["resumes"] = resumes_deleted.deleted_count

        # Delete saved jobs
        saved_deleted = await db.saved_jobs.delete_many({"user_id": user_id})
        deleted_data["saved_jobs"] = saved_deleted.deleted_count

        # Delete profile data
        await db.work_experience.delete_many({"user_id": user_id})
        await db.education.delete_many({"user_id": user_id})
        await db.certifications.delete_many({"user_id": user_id})

    # Delete user account
    await db.users.delete_one({"_id": ObjectId(user_id)})

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="user_deleted",
        target_type="user",
        target_id=user_id,
        details={
            "deleted_user_email": user["email"],
            "permanent": permanent,
            "deleted_data": deleted_data
        }
    )

    return {
        "message": "User deleted successfully",
        "user_id": user_id,
        "user_email": user["email"],
        "permanent_deletion": permanent,
        "deleted_data": deleted_data
    }


# ✅ 6. CHANGE USER ROLE
@router.put("/users/{user_id}/role")
async def change_user_role(
    user_id: str,
    role_change: UserRoleChange,
    current_user: dict = Depends(admin_required)
):
    """Change a user's role. Admin only."""

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = user.get("role")

    # Prevent changing own role
    if str(user["_id"]) == str(current_user["_id"]):
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    # Update role
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "role": role_change.new_role,
            "role_changed_at": datetime.utcnow(),
            "role_changed_by": str(current_user["_id"]),
            "role_change_reason": role_change.reason
        }}
    )

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="user_role_changed",
        target_type="user",
        target_id=user_id,
        details={
            "user_email": user["email"],
            "old_role": old_role,
            "new_role": role_change.new_role,
            "reason": role_change.reason
        }
    )

    return {
        "message": "User role changed successfully",
        "user_id": user_id,
        "user_email": user["email"],
        "old_role": old_role,
        "new_role": role_change.new_role
    }


# ✅ 7. RESET USER PASSWORD
@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    password_reset: PasswordReset,
    current_user: dict = Depends(admin_required)
):
    """Reset a user's password. Admin only."""

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Hash new password
    hashed_password = get_password_hash(password_reset.new_password)

    # Update password
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "password": hashed_password,
            "password_reset_at": datetime.utcnow(),
            "password_reset_by": str(current_user["_id"]),
            "must_change_password": True  # Force password change on next login
        }}
    )

    # Log action
    await log_admin_action(
        db,
        admin_id=str(current_user["_id"]),
        admin_name=current_user["name"],
        action="user_password_reset",
        target_type="user",
        target_id=user_id,
        details={
            "user_email": user["email"],
            "notify_user": password_reset.notify_user
        }
    )

    return {
        "message": "Password reset successfully",
        "user_id": user_id,
        "user_email": user["email"],
        "notification_sent": password_reset.notify_user
    }


# ✅ 8. GET USER ACTIVITY
@router.get("/users/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    limit: int = Query(50, le=200),
    current_user: dict = Depends(admin_required)
):
    """Get user activity logs. Admin only."""

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get recent applications
    applications = await db.applications.find(
        {"user_id": user_id}
    ).sort("applied_at", -1).limit(limit).to_list(limit)

    # Get recent jobs (if recruiter)
    jobs = []
    if user.get("role") in ["recruiter", "admin"]:
        jobs = await db.jobs.find(
            {"recruiter_id": user_id}
        ).sort("posted_date", -1).limit(limit).to_list(limit)

    return {
        "user_id": user_id,
        "user_email": user["email"],
        "user_role": user.get("role"),
        "last_login": user.get("last_login"),
        "login_count": user.get("login_count", 0),
        "recent_applications": [
            {
                "application_id": str(app["_id"]),
                "job_id": app["job_id"],
                "status": app["status"],
                "applied_at": app["applied_at"]
            }
            for app in applications
        ],
        "recent_jobs": [
            {
                "job_id": str(job["_id"]),
                "title": job.get("title"),
                "status": job.get("status", "active"),
                "posted_date": job.get("posted_date")
            }
            for job in jobs
        ]
    }


# ✅ 9. SEARCH USERS
@router.get("/users/search")
async def search_users(
    query: str = Query(..., description="Search query"),
    limit: int = Query(50, le=200),
    current_user: dict = Depends(admin_required)
):
    """Advanced user search. Admin only."""

    db = get_db()

    # Search across multiple fields
    users = await db.users.find(
        {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}},
                {"phone": {"$regex": query, "$options": "i"}},
                {"location": {"$regex": query, "$options": "i"}}
            ]
        },
        {"password": 0}
    ).limit(limit).to_list(limit)

    return [
        {
            "id": str(user["_id"]),
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role"),
            "is_suspended": user.get("is_suspended", False)
        }
        for user in users
    ]