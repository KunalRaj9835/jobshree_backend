from pydantic import EmailStr
from typing import Literal
from datetime import datetime
from .base import MongoBaseModel

class User(MongoBaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["jobseeker", "recruiter", "admin"]
    created_at: datetime = datetime.utcnow()
