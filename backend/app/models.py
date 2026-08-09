from enum import Enum
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, EmailStr

class AssigneeIdEnum(str, Enum):
    u_aarti = "u_aarti"
    u_rohit = "u_rohit"
    u_meera = "u_meera"
    u_karan = "u_karan"
    u_divya = "u_divya"
    u_triage = "u_triage"

class CategoryEnum(str, Enum):
    enterprise_rfp = "enterprise_rfp"
    smb_enquiry = "smb_enquiry"
    marketing = "marketing"
    alliances = "alliances"
    finance = "finance"
    triage = "triage"

class PriorityEnum(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

# Email Input Schema matching inbox.json
class EmailInput(BaseModel):
    email_id: str
    thread_id: str
    message_index: Optional[int] = 0
    from_name: Optional[str] = ""
    from_email: Optional[str] = ""
    to: Optional[str] = ""
    cc: Optional[List[str]] = []
    subject: Optional[str] = ""
    body: Optional[str] = ""
    received_at: str
    attachments: Optional[List[str]] = []
    is_reply: Optional[bool] = False

# Task Creation Payload (§5.1)
class TaskCreate(BaseModel):
    candidate_id: str
    source_email_id: str
    thread_id: str
    title: str
    description: Optional[str] = ""
    assignee_id: str
    category: str
    priority: str
    due_date: Optional[str] = None
    deal_value_inr: Optional[int] = None
    company_name: Optional[str] = None
    confidence: float

# Response for POST /tasks (§5.1)
class TaskCreateResponse(BaseModel):
    task_id: str
    candidate_id: str
    source_email_id: str
    created_at: str

# Task Update Payload (§5.3)
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    deal_value_inr: Optional[int] = None
    company_name: Optional[str] = None
    confidence: Optional[float] = None

# Full Task Schema
class TaskRecord(BaseModel):
    task_id: str
    candidate_id: str
    source_email_id: str
    thread_id: str
    title: str
    description: Optional[str] = ""
    assignee_id: str
    category: str
    priority: str
    due_date: Optional[str] = None
    deal_value_inr: Optional[int] = None
    company_name: Optional[str] = None
    confidence: float
    created_at: str
    updated_at: str

# Ingest Payload (§7.1)
class IngestRequest(BaseModel):
    candidate_id: str
    emails: List[EmailInput]

class IngestResponse(BaseModel):
    processed: int
    tasks_created: int
    tasks_updated: int
    skipped: int
    errors: List[str] = []

# Chat Endpoint Payload (§7.3)
class ChatRequest(BaseModel):
    candidate_id: str
    query: str

class ChatResponse(BaseModel):
    answer: str
    supporting_data: Dict[str, Any] = {}
