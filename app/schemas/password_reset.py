from pydantic import BaseModel, EmailStr, validator
from typing import Optional

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    
    @validator('otp')
    def validate_otp(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('OTP must be a 6-digit number')
        return v

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class ForgotPasswordResponse(BaseModel):
    message: str
    email: str

class VerifyOTPResponse(BaseModel):
    message: str
    verified: bool
