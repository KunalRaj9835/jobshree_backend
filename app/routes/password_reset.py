from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from bson import ObjectId
import secrets

from app.database import get_db
from app.schemas.password_reset import (
    ForgotPasswordRequest,
    VerifyOTPRequest,
    ResetPasswordRequest,
    ForgotPasswordResponse,
    VerifyOTPResponse
)
from app.utils.email import send_otp_email
from app.utils.security import get_password_hash

router = APIRouter(prefix="/auth", tags=["Password Reset"])

def generate_otp():
    """Generate a 6-digit OTP"""
    return str(secrets.randbelow(999999)).zfill(6)

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(request: ForgotPasswordRequest):
    """
    Step 1: Request password reset - Send OTP to email
    Works for both jobseekers and recruiters
    """
    db = get_db()
    
    # Check if user exists
    user = await db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email address"
        )
    
    # Generate OTP
    otp = generate_otp()
    
    # Store OTP in database with expiration (10 minutes)
    otp_data = {
        "email": request.email,
        "otp": otp,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "verified": False,
        "attempts": 0
    }
    
    # Remove any existing OTPs for this email
    await db.password_resets.delete_many({"email": request.email})
    
    # Insert new OTP
    await db.password_resets.insert_one(otp_data)
    
    # Send email
    try:
        await send_otp_email(
            email=request.email,
            otp=otp,
            name=user.get("name", "User")
        )
    except Exception as e:
        print(f"Error sending email: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Please try again later."
        )
    
    return ForgotPasswordResponse(
        message="OTP sent successfully to your email",
        email=request.email
    )

@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(request: VerifyOTPRequest):
    """
    Step 2: Verify OTP
    """
    db = get_db()
    
    # Find OTP record
    otp_record = await db.password_resets.find_one({
        "email": request.email,
        "verified": False
    })
    
    if not otp_record:
        raise HTTPException(
            status_code=404,
            detail="No pending OTP found for this email"
        )
    
    # Check if OTP is expired
    if datetime.utcnow() > otp_record["expires_at"]:
        await db.password_resets.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(
            status_code=400,
            detail="OTP has expired. Please request a new one."
        )
    
    # Check attempts (max 5 attempts)
    if otp_record["attempts"] >= 5:
        await db.password_resets.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(
            status_code=429,
            detail="Too many failed attempts. Please request a new OTP."
        )
    
    # Verify OTP
    if otp_record["otp"] != request.otp:
        # Increment attempts
        await db.password_resets.update_one(
            {"_id": otp_record["_id"]},
            {"$inc": {"attempts": 1}}
        )
        remaining = 5 - (otp_record["attempts"] + 1)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. {remaining} attempts remaining."
        )
    
    # Mark as verified
    await db.password_resets.update_one(
        {"_id": otp_record["_id"]},
        {"$set": {"verified": True, "verified_at": datetime.utcnow()}}
    )
    
    return VerifyOTPResponse(
        message="OTP verified successfully",
        verified=True
    )

@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    Step 3: Reset password after OTP verification
    """
    db = get_db()
    
    # Check if OTP is verified
    otp_record = await db.password_resets.find_one({
        "email": request.email,
        "otp": request.otp,
        "verified": True
    })
    
    if not otp_record:
        raise HTTPException(
            status_code=400,
            detail="OTP not verified or invalid"
        )
    
    # Check if OTP is still valid
    if datetime.utcnow() > otp_record["expires_at"]:
        await db.password_resets.delete_one({"_id": otp_record["_id"]})
        raise HTTPException(
            status_code=400,
            detail="OTP has expired. Please start the process again."
        )
    
    # Update user password
    hashed_password = get_password_hash(request.new_password)
    
    result = await db.users.update_one(
        {"email": request.email},
        {
            "$set": {
                "password": hashed_password,
                "password_reset_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    # Delete OTP record
    await db.password_resets.delete_one({"_id": otp_record["_id"]})
    
    return {
        "message": "Password reset successfully. You can now login with your new password.",
        "email": request.email
    }

@router.post("/resend-otp")
async def resend_otp(request: ForgotPasswordRequest):
    """
    Resend OTP - sends same OTP if valid, or generates new if expired
    """
    db = get_db()
    
    user = await db.users.find_one({"email": request.email})
    if not user:
        raise HTTPException(
            status_code=404,
            detail="No account found with this email address"
        )
    
    # Check existing OTP
    existing_otp = await db.password_resets.find_one({
        "email": request.email,
        "verified": False
    })
    
    if existing_otp and datetime.utcnow() < existing_otp["expires_at"]:
        # Resend same OTP
        try:
            await send_otp_email(
                email=request.email,
                otp=existing_otp["otp"],
                name=user.get("name", "User")
            )
            remaining_time = existing_otp["expires_at"] - datetime.utcnow()
            remaining_minutes = int(remaining_time.total_seconds() / 60)
            return {
                "message": "OTP resent successfully",
                "email": request.email,
                "expires_in_minutes": remaining_minutes
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to resend email")
    
    # Generate new OTP if expired or doesn't exist
    return await forgot_password(request)
