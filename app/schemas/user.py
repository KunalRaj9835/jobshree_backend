from pydantic import BaseModel, EmailStr
from typing import Optional, List

# 1. For Registration (Input)
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str  # user / recruiter / admin

# 2. For Login (Input)
class UserLogin(BaseModel):
    email: str
    password: str

# 3. For Responses (Output)
class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    # We make these optional because a new user might not have them yet
    class Config:
        from_attributes = True
    headline: Optional[str] = None
    skills: Optional[List[str]] = None
    location: Optional[str] = None
    experience_years: Optional[int] = None
    phone: Optional[str] = None  # ✅ Make sure this is here
    about: Optional[str] = None 

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

# 4. ✅ NEW: For Updating Profile (Input)
class UserProfileUpdate(BaseModel):
    headline: Optional[str] = None
    skills: Optional[List[str]] = None
    location: Optional[str] = None
    phone: Optional[str] = None  
    experience_years: Optional[int] = None
    about: Optional[str] = None
