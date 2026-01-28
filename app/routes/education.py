
# ========================================
# app/routes/education.py - COMPLETE FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List

from app.database import get_db
from app.schemas.education import EducationCreate, EducationUpdate, EducationResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/education", tags=["Education"])


# ✅ 1. Add Education
@router.post("/", response_model=EducationResponse)
async def add_education(
    education: EducationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add education record to user profile. Only jobseekers can add education."""

    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(
            status_code=403, 
            detail="Only jobseekers can add education records"
        )

    db = get_db()

    # Validate years
    if education.end_year and education.end_year < education.start_year:
        raise HTTPException(
            status_code=400,
            detail="End year cannot be before start year"
        )

    # Create education document
    education_data = {
        **education.dict(),
        "user_id": str(current_user["_id"]),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    # Insert into MongoDB
    result = await db.education.insert_one(education_data)

    # Return response with generated ID
    return {
        "id": str(result.inserted_id),
        **education_data
    }


# ✅ 2. Get All My Education Records
@router.get("/", response_model=List[EducationResponse])
async def get_my_education(current_user: dict = Depends(get_current_user)):
    """Get all education records for the current user, sorted by end year (newest first)."""

    db = get_db()

    # Find all education records for current user
    education_list = await db.education.find(
        {"user_id": str(current_user["_id"])}
    ).sort("end_year", -1).to_list(100)

    # Convert ObjectId to string for response
    return [
        {
            "id": str(edu["_id"]),
            "user_id": edu["user_id"],
            "institution": edu["institution"],
            "degree": edu["degree"],
            "field_of_study": edu["field_of_study"],
            "start_year": edu["start_year"],
            "end_year": edu.get("end_year"),
            "grade": edu.get("grade"),
            "description": edu.get("description")
        }
        for edu in education_list
    ]


# ✅ 3. Get Single Education Record by ID
@router.get("/{education_id}", response_model=EducationResponse)
async def get_education_by_id(
    education_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific education record."""

    if not ObjectId.is_valid(education_id):
        raise HTTPException(status_code=400, detail="Invalid education ID format")

    db = get_db()

    # Find the education record
    education = await db.education.find_one({"_id": ObjectId(education_id)})

    if not education:
        raise HTTPException(status_code=404, detail="Education record not found")

    # Check ownership
    if education["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to view this education record")

    return {
        "id": str(education["_id"]),
        **education
    }


# ✅ 4. Update Education Record
@router.put("/{education_id}", response_model=EducationResponse)
async def update_education(
    education_id: str,
    education_update: EducationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing education record. Only the owner can update."""

    if not ObjectId.is_valid(education_id):
        raise HTTPException(status_code=400, detail="Invalid education ID format")

    db = get_db()

    # Check if education record exists
    existing = await db.education.find_one({"_id": ObjectId(education_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Education record not found")

    # Verify ownership
    if existing["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to update this education record")

    # Prepare update data (only include fields that were provided)
    update_data = education_update.dict(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Validate years if both are provided
    if "start_year" in update_data or "end_year" in update_data:
        start = update_data.get("start_year", existing.get("start_year"))
        end = update_data.get("end_year", existing.get("end_year"))
        if end and start and end < start:
            raise HTTPException(
                status_code=400,
                detail="End year cannot be before start year"
            )

    # Add updated timestamp
    update_data["updated_at"] = datetime.utcnow()

    # Update in MongoDB
    await db.education.update_one(
        {"_id": ObjectId(education_id)},
        {"$set": update_data}
    )

    # Fetch and return updated document
    updated_edu = await db.education.find_one({"_id": ObjectId(education_id)})

    return {
        "id": str(updated_edu["_id"]),
        **updated_edu
    }


# ✅ 5. Delete Education Record
@router.delete("/{education_id}")
async def delete_education(
    education_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete an education record. Only the owner can delete."""

    if not ObjectId.is_valid(education_id):
        raise HTTPException(status_code=400, detail="Invalid education ID format")

    db = get_db()

    # Check if education record exists
    existing = await db.education.find_one({"_id": ObjectId(education_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Education record not found")

    # Verify ownership
    if existing["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to delete this education record")

    # Delete from MongoDB
    await db.education.delete_one({"_id": ObjectId(education_id)})

    return {
        "message": "Education record deleted successfully",
        "deleted_id": education_id
    }