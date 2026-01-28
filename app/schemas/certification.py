from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import date

class CertificationCreate(BaseModel):
    name: str
    issuing_organization: str
    issue_date: date
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = None
    credential_url: Optional[HttpUrl] = None

class CertificationUpdate(BaseModel):
    name: Optional[str] = None
    issuing_organization: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = None
    credential_url: Optional[HttpUrl] = None

class CertificationResponse(BaseModel):
    id: str
    user_id: str
    name: str
    issuing_organization: str
    issue_date: date
    expiry_date: Optional[date] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None
    
    class Config:
        orm_mode = True
