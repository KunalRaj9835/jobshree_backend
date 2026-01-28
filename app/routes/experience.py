
# ========================================
# app/routes/experience.py - COMPLETE FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List

from app.database import get_db
from app.schemas.experience import ExperienceCreate, ExperienceUpdate, ExperienceResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/experience", tags=["Work Experience"])
from datetime import datetime, date

@router.post("/", response_model=ExperienceResponse)
async def add_experience(
    experience: ExperienceCreate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(status_code=403, detail="Only jobseekers can add experience")
    
    db = get_db()
    
    # Validate dates
    if experience.end_date and experience.end_date < experience.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    
    # ✅ FIX: Convert dates to datetime
    exp_data = experience.dict()
    exp_data["user_id"] = str(current_user["_id"])
    exp_data["created_at"] = datetime.utcnow()
    exp_data["updated_at"] = datetime.utcnow()
    
    # Convert date to datetime
    if isinstance(exp_data.get("start_date"), date):
        exp_data["start_date"] = datetime.combine(exp_data["start_date"], datetime.min.time())
    
    if exp_data.get("end_date") and isinstance(exp_data["end_date"], date):
        exp_data["end_date"] = datetime.combine(exp_data["end_date"], datetime.min.time())
    
    result = await db.work_experience.insert_one(exp_data)
    
    return {"id": str(result.inserted_id), **exp_data}



# ✅ 2. Get All My Work Experiences
@router.get("/", response_model=List[ExperienceResponse])
async def get_my_experiences(current_user: dict = Depends(get_current_user)):
    """Get all work experiences for the current user, sorted by start date (newest first)."""

    db = get_db()

    # Find all experiences for current user
    experiences = await db.work_experience.find(
        {"user_id": str(current_user["_id"])}
    ).sort("start_date", -1).to_list(100)

    # Convert ObjectId to string for response
    return [
        {
            "id": str(exp["_id"]),
            "user_id": exp["user_id"],
            "company": exp["company"],
            "job_title": exp["job_title"],
            "start_date": exp["start_date"],
            "end_date": exp.get("end_date"),
            "is_current": exp.get("is_current", False),
            "description": exp.get("description"),
            "location": exp.get("location")
        }
        for exp in experiences
    ]


# ✅ 3. Get Single Work Experience by ID
@router.get("/{experience_id}", response_model=ExperienceResponse)
async def get_experience_by_id(
    experience_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific work experience."""

    if not ObjectId.is_valid(experience_id):
        raise HTTPException(status_code=400, detail="Invalid experience ID format")

    db = get_db()

    # Find the experience
    experience = await db.work_experience.find_one({"_id": ObjectId(experience_id)})

    if not experience:
        raise HTTPException(status_code=404, detail="Work experience not found")

    # Check ownership
    if experience["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to view this experience")

    return {
        "id": str(experience["_id"]),
        **experience
    }


# 4. UPDATE WORK EXPERIENCE
@router.put("/{experience_id}", response_model=ExperienceResponse)
async def update_experience(
    experience_id: str,
    experience_update: ExperienceUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing work experience. Only the owner can update."""
    
    if not ObjectId.is_valid(experience_id):
        raise HTTPException(status_code=400, detail="Invalid experience ID format")
    
    db = get_db()
    
    # Check if experience exists
    existing = await db.work_experience.find_one({"_id": ObjectId(experience_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Work experience not found")
    
    # Verify ownership
    if existing["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to update this experience")
    
    # Prepare update data (only include fields that were provided)
    update_data = experience_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # ✅ FIX: Convert date to datetime for any date fields in the update
    if "start_date" in update_data and isinstance(update_data["start_date"], date) and not isinstance(update_data["start_date"], datetime):
        update_data["start_date"] = datetime.combine(update_data["start_date"], datetime.min.time())
    
    if "end_date" in update_data and update_data["end_date"] and isinstance(update_data["end_date"], date) and not isinstance(update_data["end_date"], datetime):
        update_data["end_date"] = datetime.combine(update_data["end_date"], datetime.min.time())
    
    # Validate dates if both are provided
    if "start_date" in update_data or "end_date" in update_data:
        start = update_data.get("start_date", existing.get("start_date"))
        end = update_data.get("end_date", existing.get("end_date"))
        
        if end and start and end < start:
            raise HTTPException(status_code=400, detail="End date cannot be before start date")
    
    # Add updated timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update in MongoDB
    await db.work_experience.update_one(
        {"_id": ObjectId(experience_id)},
        {"$set": update_data}
    )
    
    # Fetch and return updated document
    updated_exp = await db.work_experience.find_one({"_id": ObjectId(experience_id)})
    
    return {"id": str(updated_exp["_id"]), **updated_exp}


# ✅ 5. Delete Work Experience
@router.delete("/{experience_id}")
async def delete_experience(
    experience_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a work experience. Only the owner can delete."""

    if not ObjectId.is_valid(experience_id):
        raise HTTPException(status_code=400, detail="Invalid experience ID format")

    db = get_db()

    # Check if experience exists
    existing = await db.work_experience.find_one({"_id": ObjectId(experience_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Work experience not found")

    # Verify ownership
    if existing["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to delete this experience")

    # Delete from MongoDB
    await db.work_experience.delete_one({"_id": ObjectId(experience_id)})

    return {
        "message": "Work experience deleted successfully",
        "deleted_id": experience_id
    }