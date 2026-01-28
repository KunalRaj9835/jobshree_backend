# ========================================
# app/routes/user.py - UPDATED VERSION (COMPLETE REPLACEMENT)
# ========================================

from fastapi import APIRouter, HTTPException, Depends, status
from bson import ObjectId

from app.schemas.user import UserCreate, UserResponse, UserLogin, TokenResponse, UserProfileUpdate
from app.database import get_db
from app.utils.security import get_password_hash, verify_password
from app.utils.auth import create_access_token, get_current_user

from datetime import timedelta

router = APIRouter(prefix="/users", tags=["Users"])

# ===========================
# PUBLIC ENDPOINTS
# ===========================

# ✅ 1. REGISTER
@router.post("/register", response_model=UserResponse)
async def register_user(user: UserCreate):
    """Register a new user (jobseeker, recruiter, or admin)."""
    db = get_db()
    
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash the password
    hashed_password = get_password_hash(user.password)
    
    # Create user dictionary
    user_dict = user.dict()
    user_dict["password"] = hashed_password
    user_dict["role"] = user.role  # user = recruiter | admin
    
    # Save to MongoDB
    result = await db.users.insert_one(user_dict)
    return {
        "id": str(result.inserted_id),
        "name": user.name,
        "email": user.email,
        "role": user.role
    }


# ✅ 2. LOGIN
@router.post("/login", response_model=TokenResponse)
async def login(user_credentials: UserLogin):
    """Login and get JWT access token."""

    db = get_db()

    # Find user by email
    user = await db.users.find_one({"email": user_credentials.email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not verify_password(user_credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate Token
    access_token = create_access_token(data={"sub": user["email"]})

    return {"access_token": access_token, "token_type": "bearer"}


# ===========================
# AUTHENTICATED USER ENDPOINTS
# ===========================

# ✅ 3. GET MY PROFILE
@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get the current user's profile."""

    current_user["id"] = str(current_user["_id"])
    return current_user


# ✅ 4. UPDATE MY PROFILE
@router.put("/profile")
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update the current user's profile."""

    db = get_db()

    update_data = profile_data.dict(exclude_unset=True)

    if not update_data:
        return {"message": "No changes provided"}

    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": update_data}
    )

    return {"message": "Profile updated successfully", "updated_fields": update_data}


# ===========================
# RECRUITER/ADMIN ENDPOINTS (NEW!)
# ===========================

# ✅ 5. VIEW USER PROFILE (Recruiter/Admin - NEW!)
@router.get("/{user_id}/profile", response_model=UserResponse)
async def get_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get another user's profile. 
    Recruiters can view jobseeker profiles.
    Admins can view any profile.
    """

    # Only recruiters and admins can view other profiles
    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can view user profiles"
        )

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    # Get the user
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Recruiters can only view jobseeker profiles
    if current_user["role"] == "recruiter" and user.get("role") not in ["jobseeker", "user"]:
        raise HTTPException(
            status_code=403,
            detail="Recruiters can only view jobseeker profiles"
        )

    # Return user profile (without password)
    user["id"] = str(user["_id"])
    user.pop("password", None)  # Remove password from response

    return user


# ✅ 6. VIEW FULL USER PROFILE WITH DETAILS (Recruiter/Admin - NEW!)
@router.get("/{user_id}/full-profile")
async def get_full_user_profile(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get complete user profile including experience, education, and certifications.
    Only recruiters and admins can access.
    """

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can view full profiles"
        )

    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID")

    db = get_db()

    # Get the user
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Recruiters can only view jobseeker profiles
    if current_user["role"] == "recruiter" and user.get("role") not in ["jobseeker", "user"]:
        raise HTTPException(
            status_code=403,
            detail="Recruiters can only view jobseeker profiles"
        )

    # Get work experience
    experiences = await db.work_experience.find(
        {"user_id": user_id}
    ).sort("start_date", -1).to_list(100)

    # Get education
    education = await db.education.find(
        {"user_id": user_id}
    ).sort("end_year", -1).to_list(100)

    # Get certifications
    certifications = await db.certifications.find(
        {"user_id": user_id}
    ).sort("issue_date", -1).to_list(100)

    # Get resumes count
    resumes_count = await db.resumes.count_documents({"jobseeker_id": ObjectId(user_id)})

    # Build response
    profile = {
        "id": str(user["_id"]),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "headline": user.get("headline"),
        "skills": user.get("skills", []),
        "location": user.get("location"),
        "experience_years": user.get("experience_years"),
        "about": user.get("about"),
        "phone": user.get("phone"),

        # Social links
        "linkedin_url": user.get("linkedin_url"),
        "github_url": user.get("github_url"),
        "portfolio_url": user.get("portfolio_url"),

        # Work experience
        "work_experience": [
            {
                "id": str(exp["_id"]),
                "company": exp.get("company"),
                "job_title": exp.get("job_title"),
                "start_date": exp.get("start_date"),
                "end_date": exp.get("end_date"),
                "is_current": exp.get("is_current", False),
                "description": exp.get("description"),
                "location": exp.get("location")
            }
            for exp in experiences
        ],

        # Education
        "education": [
            {
                "id": str(edu["_id"]),
                "institution": edu.get("institution"),
                "degree": edu.get("degree"),
                "field_of_study": edu.get("field_of_study"),
                "start_year": edu.get("start_year"),
                "end_year": edu.get("end_year"),
                "grade": edu.get("grade"),
                "description": edu.get("description")
            }
            for edu in education
        ],

        # Certifications
        "certifications": [
            {
                "id": str(cert["_id"]),
                "name": cert.get("name"),
                "issuing_organization": cert.get("issuing_organization"),
                "issue_date": cert.get("issue_date"),
                "expiry_date": cert.get("expiry_date"),
                "credential_id": cert.get("credential_id"),
                "credential_url": str(cert.get("credential_url")) if cert.get("credential_url") else None
            }
            for cert in certifications
        ],

        # Metadata
        "resumes_count": resumes_count,
        "experience_count": len(experiences),
        "education_count": len(education),
        "certifications_count": len(certifications)
    }

    return profile


# ===========================
# ADMIN ENDPOINTS
# ===========================

# ✅ 7. LIST ALL USERS (Admin - NEW!)
@router.get("/")
async def list_all_users(
    role: str = None,
    current_user: dict = Depends(get_current_user)
):
    """
    List all users in the system. Admin only.
    Optionally filter by role.
    """

    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admins can list all users"
        )

    db = get_db()

    # Build query
    query = {}
    if role:
        query["role"] = role

    # Get users (exclude passwords)
    users = await db.users.find(query, {"password": 0}).to_list(1000)

    return [
        {
            "id": str(user["_id"]),
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role"),
            "created_at": user.get("created_at")
        }
        for user in users
    ]