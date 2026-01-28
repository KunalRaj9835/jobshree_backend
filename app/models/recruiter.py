from pydantic import EmailStr
from .base import MongoBaseModel, PyObjectId

class Recruiter(MongoBaseModel):
    user_id: PyObjectId
    company_name: str
    company_email: EmailStr
    company_website: str
    location: str
