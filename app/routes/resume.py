# ========================================
# COMPLETE REPLACEMENT FOR: app/routes/resume.py
# ========================================

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.utils.auth import get_current_user
from app.database import get_db, get_fs_bucket
from datetime import datetime
from bson import ObjectId
import io

router = APIRouter()

# ✅ 1. UPLOAD RESUME TO MONGODB GRIDFS
@router.post("/upload-resume")
async def upload_resume(
    file: UploadFile = File(...), 
    current_user: dict = Depends(get_current_user)
):
    # Security: Only jobseekers can upload
    if current_user["role"] not in ["jobseeker", "user"]:
        raise HTTPException(status_code=403, detail="Only jobseekers can upload resumes")
    
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    # Read file contents
    contents = await file.read()
    
    # Validate file size (5MB limit)
    if len(contents) > 5 * 1024 * 1024:  # 5MB in bytes
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    db = get_db()
    fs_bucket = get_fs_bucket()
    
    try:
        # Upload to GridFS
        file_id = await fs_bucket.upload_from_stream(
            filename=f"{current_user['email']}_{file.filename}",
            source=io.BytesIO(contents),
            metadata={
                "user_id": str(current_user["_id"]),
                "email": current_user["email"],
                "content_type": file.content_type,
                "original_filename": file.filename,
                "uploaded_at": datetime.utcnow()
            }
        )
        
        # Save resume metadata to 'resumes' collection
        resume_doc = {
            "jobseeker_id": current_user["_id"],
            "file_id": file_id,  # GridFS file ID
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": len(contents),
            "uploaded_at": datetime.utcnow()
        }
        
        result = await db.resumes.insert_one(resume_doc)
        
        return {
            "message": "Resume uploaded successfully!",
            "resume_id": str(result.inserted_id),
            "file_id": str(file_id),
            "filename": file.filename,
            "size_kb": round(len(contents) / 1024, 2)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ✅ 2. GET USER'S RESUMES
@router.get("/my-resumes")
async def get_my_resumes(current_user: dict = Depends(get_current_user)):
    db = get_db()
    
    resumes = await db.resumes.find(
        {"jobseeker_id": current_user["_id"]}
    ).sort("uploaded_at", -1).to_list(100)
    
    return [
        {
            "id": str(resume["_id"]),
            "filename": resume["filename"],
            "size_kb": round(resume.get("file_size", 0) / 1024, 2),
            "uploaded_at": resume["uploaded_at"]
        }
        for resume in resumes
    ]


# ✅ 3. DOWNLOAD/VIEW RESUME FROM GRIDFS
@router.get("/download-resume/{resume_id}")
async def download_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_db()
    fs_bucket = get_fs_bucket()
    
    # Get resume metadata
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    
    resume = await db.resumes.find_one({"_id": ObjectId(resume_id)})
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Security: Users can only download their own resumes
    # Recruiters/admins can download any resume
    if current_user["role"] not in ["recruiter", "admin"]:
        if str(resume["jobseeker_id"]) != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        # Download from GridFS
        grid_out = await fs_bucket.open_download_stream(resume["file_id"])
        contents = await grid_out.read()
        
        return StreamingResponse(
            io.BytesIO(contents),
            media_type=resume["content_type"],
            headers={
                "Content-Disposition": f'attachment; filename="{resume["filename"]}"'
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


# ✅ 4. DELETE RESUME
@router.delete("/delete-resume/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_db()
    fs_bucket = get_fs_bucket()
    
    if not ObjectId.is_valid(resume_id):
        raise HTTPException(status_code=400, detail="Invalid resume ID")
    
    resume = await db.resumes.find_one({"_id": ObjectId(resume_id)})
    
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    
    # Security check
    if str(resume["jobseeker_id"]) != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="Can only delete your own resumes")
    
    try:
        # Delete from GridFS
        await fs_bucket.delete(resume["file_id"])
        
        # Delete metadata
        await db.resumes.delete_one({"_id": ObjectId(resume_id)})
        
        return {"message": "Resume deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")



