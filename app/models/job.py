from typing import List, Literal
from datetime import datetime
from .base import MongoBaseModel, PyObjectId

class Job(MongoBaseModel):
    recruiter_id: PyObjectId
    title: str
    skills_required: List[str]
    experience: str
    salary: str
    location: str
    job_type: Literal["Full-time", "Part-time", "Internship"]
    status: str = "active"
    posted_date: datetime = datetime.utcnow()