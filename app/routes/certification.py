 # ========================================
# app/routes/certification.py - COMPLETE FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime, date
from typing import List

from app.database import get_db
from app.schemas.certification import CertificationCreate, CertificationUpdate, CertificationResponse
from app.utils.auth import get_current_user

router = APIRouter(prefix="/certifications", tags=["Certifications"])


from datetime import datetime, date
@router.post("/", response_model=CertificationResponse)
async def add_certification(
    certification: CertificationCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add certification to user profile. Only jobseekers can add certifications."""
    
    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(status_code=403, detail="Only jobseekers can add certifications")
    
    db = get_db()
    
    # Validate dates
    if certification.expiry_date and certification.expiry_date < certification.issue_date:
        raise HTTPException(status_code=400, detail="Expiry date cannot be before issue date")
    
    # Create certification document
    cert_data = certification.dict()
    cert_data["user_id"] = str(current_user["_id"])
    cert_data["created_at"] = datetime.utcnow()
    cert_data["updated_at"] = datetime.utcnow()
    
    # ✅ FIX: Convert HttpUrl to string for MongoDB
    if cert_data.get("credential_url"):
        cert_data["credential_url"] = str(cert_data["credential_url"])
    
    # Convert date to datetime if needed (from previous fix)
    if isinstance(cert_data.get("issue_date"), date) and not isinstance(cert_data["issue_date"], datetime):
        cert_data["issue_date"] = datetime.combine(cert_data["issue_date"], datetime.min.time())
    
    if cert_data.get("expiry_date") and isinstance(cert_data["expiry_date"], date) and not isinstance(cert_data["expiry_date"], datetime):
        cert_data["expiry_date"] = datetime.combine(cert_data["expiry_date"], datetime.min.time())
    
    # Insert into MongoDB
    result = await db.certifications.insert_one(cert_data)
    
    # Return response with generated ID
    return {"id": str(result.inserted_id), **cert_data}




# ✅ 2. Get All My Certifications
@router.get("/", response_model=List[CertificationResponse])
async def get_my_certifications(current_user: dict = Depends(get_current_user)):
    """Get all certifications for the current user, sorted by issue date (newest first)."""

    db = get_db()

    # Find all certifications for current user
    certifications = await db.certifications.find(
        {"user_id": str(current_user["_id"])}
    ).sort("issue_date", -1).to_list(100)

    # Convert ObjectId to string for response
    return [
        {
            "id": str(cert["_id"]),
            "user_id": cert["user_id"],
            "name": cert["name"],
            "issuing_organization": cert["issuing_organization"],
            "issue_date": cert["issue_date"],
            "expiry_date": cert.get("expiry_date"),
            "credential_id": cert.get("credential_id"),
            "credential_url": str(cert["credential_url"]) if cert.get("credential_url") else None
        }
        for cert in certifications
    ]


# ✅ 3. Get Single Certification by ID
@router.get("/{certification_id}", response_model=CertificationResponse)
async def get_certification_by_id(
    certification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific certification."""

    if not ObjectId.is_valid(certification_id):
        raise HTTPException(status_code=400, detail="Invalid certification ID format")

    db = get_db()

    # Find the certification
    certification = await db.certifications.find_one({"_id": ObjectId(certification_id)})

    if not certification:
        raise HTTPException(status_code=404, detail="Certification not found")

    # Check ownership
    if certification["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to view this certification")

    return {
        "id": str(certification["_id"]),
        "user_id": certification["user_id"],
        "name": certification["name"],
        "issuing_organization": certification["issuing_organization"],
        "issue_date": certification["issue_date"],
        "expiry_date": certification.get("expiry_date"),
        "credential_id": certification.get("credential_id"),
        "credential_url": str(certification["credential_url"]) if certification.get("credential_url") else None
    }

@router.put("/{certification_id}", response_model=CertificationResponse)
async def update_certification(
    certification_id: str,
    cert_update: CertificationUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing certification. Only the owner can update."""
    
    if not ObjectId.is_valid(certification_id):
        raise HTTPException(status_code=400, detail="Invalid certification ID format")
    
    db = get_db()
    
    # Check if certification exists
    existing = await db.certifications.find_one({"_id": ObjectId(certification_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Certification not found")
    
    # Verify ownership
    if existing["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to update this certification")
    
    # Prepare update data (only include fields that were provided)
    update_data = cert_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # ✅ FIX: Convert HttpUrl to string
    if "credential_url" in update_data and update_data["credential_url"]:
        update_data["credential_url"] = str(update_data["credential_url"])
    
    # Convert dates to datetime if needed
    if "issue_date" in update_data and isinstance(update_data["issue_date"], date) and not isinstance(update_data["issue_date"], datetime):
        update_data["issue_date"] = datetime.combine(update_data["issue_date"], datetime.min.time())
    
    if "expiry_date" in update_data and update_data["expiry_date"] and isinstance(update_data["expiry_date"], date) and not isinstance(update_data["expiry_date"], datetime):
        update_data["expiry_date"] = datetime.combine(update_data["expiry_date"], datetime.min.time())
    
    # Validate dates if both are provided
    if "issue_date" in update_data or "expiry_date" in update_data:
        issue = update_data.get("issue_date", existing.get("issue_date"))
        expiry = update_data.get("expiry_date", existing.get("expiry_date"))
        
        if expiry and issue and expiry < issue:
            raise HTTPException(status_code=400, detail="Expiry date cannot be before issue date")
    
    # Add updated timestamp
    update_data["updated_at"] = datetime.utcnow()
    
    # Update in MongoDB
    await db.certifications.update_one(
        {"_id": ObjectId(certification_id)},
        {"$set": update_data}
    )
    
    # Fetch and return updated document
    updated_cert = await db.certifications.find_one({"_id": ObjectId(certification_id)})
    
    return {
        "id": str(updated_cert["_id"]),
        "user_id": updated_cert["user_id"],
        "name": updated_cert["name"],
        "issuing_organization": updated_cert["issuing_organization"],
        "issue_date": updated_cert["issue_date"],
        "expiry_date": updated_cert.get("expiry_date"),
        "credential_id": updated_cert.get("credential_id"),
        "credential_url": str(updated_cert["credential_url"]) if updated_cert.get("credential_url") else None
    }



# ✅ 5. Delete Certification
@router.delete("/{certification_id}")
async def delete_certification(
    certification_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a certification. Only the owner can delete."""

    if not ObjectId.is_valid(certification_id):
        raise HTTPException(status_code=400, detail="Invalid certification ID format")

    db = get_db()

    # Check if certification exists
    existing = await db.certifications.find_one({"_id": ObjectId(certification_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Certification not found")

    # Verify ownership
    if existing["user_id"] != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to delete this certification")

    # Delete from MongoDB
    await db.certifications.delete_one({"_id": ObjectId(certification_id)})

    return {
        "message": "Certification deleted successfully",
        "deleted_id": certification_id
    }

@router.get("/active/list", response_model=List[CertificationResponse])
async def get_active_certifications(current_user: dict = Depends(get_current_user)):
    """Get all non-expired certifications for the current user."""
    
    db = get_db()
    
    # ✅ FIX: Use datetime.utcnow() instead of date.today()
    today = datetime.utcnow()  # Changed from date.today()
    
    # Find certifications that either have no expiry or haven't expired yet
    certifications = await db.certifications.find({
        "user_id": str(current_user["_id"]),
        "$or": [
            {"expiry_date": None},
            {"expiry_date": {"$gte": today}}
        ]
    }).sort("issue_date", -1).to_list(100)
    
    return [
        {
            "id": str(cert["_id"]),
            "user_id": cert["user_id"],
            "name": cert["name"],
            "issuing_organization": cert["issuing_organization"],
            "issue_date": cert["issue_date"],
            "expiry_date": cert.get("expiry_date"),
            "credential_id": cert.get("credential_id"),
            "credential_url": str(cert["credential_url"]) if cert.get("credential_url") else None
        }
        for cert in certifications
    ]
