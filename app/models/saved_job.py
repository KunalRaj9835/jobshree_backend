from datetime import datetime
from .base import MongoBaseModel, PyObjectId

class SavedJob(MongoBaseModel):
    job_id: PyObjectId
    jobseeker_id: PyObjectId
    saved_at: datetime = datetime.utcnow()