from pydantic import BaseModel
from typing import Optional

class EducationCreate(BaseModel):
    institution: str
    degree: str
    field_of_study: str
    start_year: int
    end_year: Optional[int] = None  # None if currently studying
    grade: Optional[str] = None
    description: Optional[str] = None

class EducationUpdate(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    grade: Optional[str] = None
    description: Optional[str] = None

class EducationResponse(BaseModel):
    id: str
    user_id: str
    institution: str
    degree: str
    field_of_study: str
    start_year: int
    end_year: Optional[int] = None
    grade: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        orm_mode = True
