import uuid
import datetime
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.models import (
    TaskCreate, TaskUpdate, TaskCreateResponse, TaskRecord,
    AssigneeIdEnum, CategoryEnum, PriorityEnum
)
from app.database import DBAdapter

router = APIRouter()

ALLOWED_ASSIGNEES = [e.value for e in AssigneeIdEnum]
ALLOWED_CATEGORIES = [e.value for e in CategoryEnum]
ALLOWED_PRIORITIES = [e.value for e in PriorityEnum]

def normalize_candidate_id(cand_id: str) -> str:
    if not cand_id:
        return ""
    cleaned = cand_id.strip().lower()
    if "@" in cleaned:
        user_part, domain_part = cleaned.split("@", 1)
        if "+" in user_part:
            user_part = user_part.split("+")[0]
        cleaned = f"{user_part}@{domain_part}"
    return cleaned

def validate_task_enums(data: dict):
    if "assignee_id" in data and data["assignee_id"] is not None:
        if data["assignee_id"] not in ALLOWED_ASSIGNEES:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_enum_value",
                    "field": "assignee_id",
                    "received": str(data["assignee_id"]),
                    "allowed": ALLOWED_ASSIGNEES
                }
            )
    if "category" in data and data["category"] is not None:
        if data["category"] not in ALLOWED_CATEGORIES:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_enum_value",
                    "field": "category",
                    "received": str(data["category"]),
                    "allowed": ALLOWED_CATEGORIES
                }
            )
    if "priority" in data and data["priority"] is not None:
        if data["priority"] not in ALLOWED_PRIORITIES:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_enum_value",
                    "field": "priority",
                    "received": str(data["priority"]),
                    "allowed": ALLOWED_PRIORITIES
                }
            )
    return None

@router.post("/tasks", status_code=201)
def create_task(payload: dict):
    validation_err = validate_task_enums(payload)
    if validation_err:
        return validation_err
    
    try:
        task_data = TaskCreate(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    cand_id = normalize_candidate_id(task_data.candidate_id)
    
    # Check if source_email_id already exists (Idempotency)
    existing = DBAdapter.get_task_by_source_email(task_data.source_email_id)
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    if existing:
        return JSONResponse(
            status_code=200,
            content={
                "task_id": existing["task_id"],
                "candidate_id": cand_id,
                "source_email_id": task_data.source_email_id,
                "created_at": existing.get("created_at", now_str)
            }
        )

    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    
    task_dict = {
        "task_id": task_id,
        "candidate_id": cand_id,
        "source_email_id": task_data.source_email_id,
        "thread_id": task_data.thread_id,
        "title": task_data.title,
        "description": task_data.description or "",
        "assignee_id": task_data.assignee_id,
        "category": task_data.category,
        "priority": task_data.priority,
        "due_date": task_data.due_date,
        "deal_value_inr": task_data.deal_value_inr,
        "company_name": task_data.company_name,
        "confidence": task_data.confidence,
        "created_at": now_str,
        "updated_at": now_str
    }
    
    DBAdapter.insert_task(task_dict)

    return {
        "task_id": task_id,
        "candidate_id": cand_id,
        "source_email_id": task_data.source_email_id,
        "created_at": now_str
    }

@router.patch("/tasks/{task_id}")
def update_task(task_id: str, payload: dict):
    validation_err = validate_task_enums(payload)
    if validation_err:
        return validation_err

    task = DBAdapter.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    fields_to_update = {"updated_at": now_str}
    
    for key in ["title", "description", "assignee_id", "category", "priority", "due_date", "deal_value_inr", "company_name", "confidence"]:
        if key in payload and payload[key] is not None:
            fields_to_update[key] = payload[key]

    updated_record = DBAdapter.update_task_fields(task_id, fields_to_update)
    return updated_record

@router.get("/tasks")
def list_tasks(
    candidate_id: str = Query(..., description="Mandatory candidate_id"),
    thread_id: Optional[str] = Query(None),
    source_email_id: Optional[str] = Query(None),
    assignee_id: Optional[str] = Query(None)
):
    norm_cand = normalize_candidate_id(candidate_id)
    return DBAdapter.list_tasks(norm_cand, thread_id, source_email_id, assignee_id)

@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    deleted = DBAdapter.delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully", "task_id": task_id}

@router.get("/users")
def get_team_roster():
    roster_path = "data/team_roster.json"
    try:
        with open(roster_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "team": [
                {"user_id": "u_aarti", "name": "Aarti Menon", "department": "Sales — Enterprise", "scope": "RFPs, RFIs, tenders, and inbound deals above ₹10,00,000"},
                {"user_id": "u_rohit", "name": "Rohit Sharma", "department": "Sales — SMB", "scope": "Product enquiries, demo requests, deals at or below ₹10,00,000"},
                {"user_id": "u_meera", "name": "Meera Iyer", "department": "Marketing", "scope": "Webinars, event and conference sponsorships, content collaborations, PR and media"},
                {"user_id": "u_karan", "name": "Karan Doshi", "department": "Alliances", "scope": "Reseller, channel partner, and technology integration proposals"},
                {"user_id": "u_divya", "name": "Divya Rao", "department": "Finance", "scope": "Invoices, purchase orders, payment reminders, GST and vendor billing"},
                {"user_id": "u_triage", "name": "Triage Queue", "department": "Operations", "scope": "Ambiguous items requiring human review"}
            ]
        }
