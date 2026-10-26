from pydantic import BaseModel, Field

class TaskCreate(BaseModel):
    request: str = Field(min_length=5, max_length=2000)
    document_name: str | None = None

class ApprovalRequest(BaseModel):
    approved_by: str = Field(default="demo-reviewer", min_length=1, max_length=100)
    note: str = Field(default="", max_length=500)

class RejectRequest(BaseModel):
    rejected_by: str = Field(default="demo-reviewer", min_length=1, max_length=100)
    reason: str = Field(min_length=2, max_length=500)
