from typing import Literal
from datetime import datetime
from .base import MongoBaseModel, PyObjectId

class Application(MongoBaseModel):
    job_id: PyObjectId
    jobseeker_id: PyObjectId
    resume_id: PyObjectId
    status: Literal["applied", "shortlisted", "rejected", "selected"] = "applied"
    applied_date: datetime = datetime.utcnow()
