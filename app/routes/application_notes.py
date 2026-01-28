# ========================================
# app/routes/application_notes.py - NEW FILE
# ========================================

from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime
from typing import List

from app.database import get_db
from app.schemas.application_note import (
    ApplicationNoteCreate,
    ApplicationNoteUpdate,
    ApplicationNoteResponse
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/applications", tags=["Application Notes"])


# ✅ 1. Add Note to Application
@router.post("/{application_id}/notes", response_model=ApplicationNoteResponse)
async def add_note_to_application(
    application_id: str,
    note_data: ApplicationNoteCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a note/comment to an application. Only recruiters/admins can add notes."""

    # Only recruiters and admins can add notes
    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can add notes to applications"
        )

    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID format")

    db = get_db()

    # Verify application exists
    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # If recruiter, verify they own the job
    if current_user["role"] == "recruiter":
        job = await db.jobs.find_one({"_id": ObjectId(application["job_id"])})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only add notes to applications for your own jobs"
            )

    # Create note document
    note_doc = {
        "application_id": application_id,
        "note": note_data.note,
        "is_private": note_data.is_private,
        "created_by": str(current_user["_id"]),
        "created_by_name": current_user["name"],
        "created_by_role": current_user["role"],
        "created_at": datetime.utcnow(),
        "updated_at": None
    }

    # Insert note
    result = await db.application_notes.insert_one(note_doc)

    # Update application to track that notes exist
    await db.applications.update_one(
        {"_id": ObjectId(application_id)},
        {"$set": {"has_notes": True, "notes_count": await db.application_notes.count_documents({"application_id": application_id})}}
    )

    return {
        "id": str(result.inserted_id),
        **note_doc
    }


# ✅ 2. Get All Notes for an Application
@router.get("/{application_id}/notes", response_model=List[ApplicationNoteResponse])
async def get_application_notes(
    application_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all notes for an application. Only recruiters/admins can view notes."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can view notes"
        )

    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="Invalid application ID format")

    db = get_db()

    # Verify application exists
    application = await db.applications.find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # If recruiter, verify they own the job
    if current_user["role"] == "recruiter":
        job = await db.jobs.find_one({"_id": ObjectId(application["job_id"])})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.get("recruiter_id") != str(current_user["_id"]):
            raise HTTPException(
                status_code=403,
                detail="You can only view notes for applications on your own jobs"
            )

    # Get all notes for this application
    notes = await db.application_notes.find(
        {"application_id": application_id}
    ).sort("created_at", -1).to_list(100)

    return [
        {
            "id": str(note["_id"]),
            "application_id": note["application_id"],
            "note": note["note"],
            "is_private": note["is_private"],
            "created_by": note["created_by"],
            "created_by_name": note["created_by_name"],
            "created_by_role": note["created_by_role"],
            "created_at": note["created_at"],
            "updated_at": note.get("updated_at")
        }
        for note in notes
    ]


# ✅ 3. Update a Note
@router.put("/{application_id}/notes/{note_id}", response_model=ApplicationNoteResponse)
async def update_note(
    application_id: str,
    note_id: str,
    note_update: ApplicationNoteUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update a note. Only the creator can update their own note."""

    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")

    db = get_db()

    # Find the note
    note = await db.application_notes.find_one({"_id": ObjectId(note_id)})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Verify note belongs to this application
    if note["application_id"] != application_id:
        raise HTTPException(status_code=400, detail="Note does not belong to this application")

    # Verify ownership (only creator or admin can update)
    if current_user["role"] != "admin" and note["created_by"] != str(current_user["_id"]):
        raise HTTPException(
            status_code=403,
            detail="You can only update your own notes"
        )

    # Prepare update data
    update_data = note_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_data["updated_at"] = datetime.utcnow()

    # Update the note
    await db.application_notes.update_one(
        {"_id": ObjectId(note_id)},
        {"$set": update_data}
    )

    # Fetch updated note
    updated_note = await db.application_notes.find_one({"_id": ObjectId(note_id)})

    return {
        "id": str(updated_note["_id"]),
        "application_id": updated_note["application_id"],
        "note": updated_note["note"],
        "is_private": updated_note["is_private"],
        "created_by": updated_note["created_by"],
        "created_by_name": updated_note["created_by_name"],
        "created_by_role": updated_note["created_by_role"],
        "created_at": updated_note["created_at"],
        "updated_at": updated_note.get("updated_at")
    }


# ✅ 4. Delete a Note
@router.delete("/{application_id}/notes/{note_id}")
async def delete_note(
    application_id: str,
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a note. Only the creator or admin can delete."""

    if not ObjectId.is_valid(note_id):
        raise HTTPException(status_code=400, detail="Invalid note ID format")

    db = get_db()

    # Find the note
    note = await db.application_notes.find_one({"_id": ObjectId(note_id)})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Verify note belongs to this application
    if note["application_id"] != application_id:
        raise HTTPException(status_code=400, detail="Note does not belong to this application")

    # Verify ownership (only creator or admin can delete)
    if current_user["role"] != "admin" and note["created_by"] != str(current_user["_id"]):
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own notes"
        )

    # Delete the note
    await db.application_notes.delete_one({"_id": ObjectId(note_id)})

    # Update application notes count
    notes_count = await db.application_notes.count_documents({"application_id": application_id})
    await db.applications.update_one(
        {"_id": ObjectId(application_id)},
        {"$set": {"has_notes": notes_count > 0, "notes_count": notes_count}}
    )

    return {
        "message": "Note deleted successfully",
        "deleted_note_id": note_id
    }


# ✅ 5. Get Notes Count for Application
@router.get("/{application_id}/notes/count")
async def get_notes_count(
    application_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get the count of notes for an application."""

    if current_user["role"] not in ["recruiter", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only recruiters and admins can view note counts"
        )

    db = get_db()

    count = await db.application_notes.count_documents({"application_id": application_id})

    return {
        "application_id": application_id,
        "notes_count": count
    }