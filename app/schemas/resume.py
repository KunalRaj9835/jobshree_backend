from pydantic import BaseModel
from datetime import datetime

class ResumeResponse(BaseModel):
    id: str
    user_id: str
    file_name: str
    file_type: str
    resume_url: str
    uploaded_at: datetime
