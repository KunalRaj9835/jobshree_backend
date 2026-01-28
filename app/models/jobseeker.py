from typing import List
from .base import MongoBaseModel, PyObjectId

class JobSeeker(MongoBaseModel):
    user_id: PyObjectId
    skills: List[str]
    experience: int
    education: str
    location: str