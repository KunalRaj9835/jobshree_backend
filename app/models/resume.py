from datetime import datetime
from .base import MongoBaseModel, PyObjectId

class Resume(MongoBaseModel):
    jobseeker_id: PyObjectId
    file_url: str
    uploaded_at: datetime = datetime.utcnow()
