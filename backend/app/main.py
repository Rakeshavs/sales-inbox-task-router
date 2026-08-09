import os
import sys
import datetime
import uuid
from typing import List, Optional

# Ensure backend directory and app package are in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

from app.database import init_db, DBAdapter
from app.models import IngestRequest, IngestResponse, ChatRequest, ChatResponse
from app.task_api import router as task_router, normalize_candidate_id
from app.router import classify_email_with_llm
from app.chat_engine import query_chat_engine
from app.sample_generator import generate_sample_emails

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Sales Inbox Task Router API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*"
        }
    )

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Sales Inbox Task Router",
        "version": "1.0.0",
        "database": "MongoDB Atlas" if os.getenv("MONGODB_URI") else "SQLite Local",
        "endpoints": ["/tasks", "/users", "/ingest", "/api/tasks", "/api/stats", "/api/chat"]
    }

# Include Task API router (/tasks, /users)
app.include_router(task_router)

# Ultra-Fast Ingest Endpoint (§7.1)
@app.post("/ingest", response_model=IngestResponse)
def ingest_emails(payload: IngestRequest):
    cand_id = normalize_candidate_id(payload.candidate_id)
    if not cand_id:
        raise HTTPException(status_code=400, detail="candidate_id is required")

    if not payload.emails:
        return IngestResponse(processed=0, tasks_created=0, tasks_updated=0, skipped=0, errors=[])

    if len(payload.emails) > 100:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum limit of 100 emails")

    tasks_created = 0
    tasks_updated = 0
    skipped_count = 0
    errors = []

    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Pre-fetch existing state in single query for ultra-fast processing
    existing_processed_ids = DBAdapter.get_processed_email_ids(cand_id)
    existing_task_map = DBAdapter.get_tasks_by_candidate(cand_id) # thread_id -> task

    new_tasks = []
    updated_tasks = []
    processed_metas = []

    for email in payload.emails:
        email_id = email.email_id
        thread_id = email.thread_id
        
        # 1. Check idempotency
        if email_id in existing_processed_ids:
            continue
        existing_processed_ids.add(email_id)

        # 2. Check if task exists for thread
        existing_task = existing_task_map.get(thread_id)

        email_dict = email.model_dump()

        # 3. Classify email
        try:
            classification = classify_email_with_llm(email_dict)
        except Exception as e:
            errors.append(f"Error classifying email {email_id}: {str(e)}")
            continue

        status = classification.get("status", "task_ready")

        if status == "skipped":
            skip_reason = classification.get("skip_reason", "noise")
            skipped_count += 1
            processed_metas.append({
                "email_id": email_id,
                "candidate_id": cand_id,
                "thread_id": thread_id,
                "from_name": email.from_name,
                "from_email": email.from_email,
                "subject": email.subject,
                "body": email.body,
                "received_at": email.received_at,
                "status": "skipped",
                "skip_reason": skip_reason,
                "task_id": None,
                "confidence": classification.get("confidence", 0.95),
                "category": "skipped",
                "reasoning": classification.get("reasoning", "Skipped as noise"),
                "ingested_at": now_str
            })

        elif existing_task:
            t_id = existing_task["task_id"]
            tasks_updated += 1

            new_due = classification.get("due_date") or existing_task.get("due_date")
            new_val = classification.get("deal_value_inr") or existing_task.get("deal_value_inr")
            new_prio = classification.get("priority") or existing_task.get("priority")

            updated_task_obj = {
                "task_id": t_id,
                "priority": new_prio,
                "due_date": new_due,
                "deal_value_inr": new_val,
                "updated_at": now_str
            }
            updated_tasks.append(updated_task_obj)
            existing_task_map[thread_id].update(updated_task_obj)

            processed_metas.append({
                "email_id": email_id,
                "candidate_id": cand_id,
                "thread_id": thread_id,
                "from_name": email.from_name,
                "from_email": email.from_email,
                "subject": email.subject,
                "body": email.body,
                "received_at": email.received_at,
                "status": "updated",
                "skip_reason": None,
                "task_id": t_id,
                "confidence": classification.get("confidence", 0.90),
                "category": classification.get("category", existing_task.get("category")),
                "reasoning": classification.get("reasoning", "Thread reply update"),
                "ingested_at": now_str
            })

        else:
            t_id = f"tsk_{uuid.uuid4().hex[:8]}"
            tasks_created += 1

            new_task_obj = {
                "task_id": t_id,
                "candidate_id": cand_id,
                "source_email_id": email_id,
                "thread_id": thread_id,
                "title": classification.get("title", email.subject),
                "description": classification.get("description", email.body[:200]),
                "assignee_id": classification.get("assignee_id", "u_triage"),
                "category": classification.get("category", "triage"),
                "priority": classification.get("priority", "medium"),
                "due_date": classification.get("due_date"),
                "deal_value_inr": classification.get("deal_value_inr"),
                "company_name": classification.get("company_name"),
                "confidence": classification.get("confidence", 0.85),
                "created_at": now_str,
                "updated_at": now_str
            }
            new_tasks.append(new_task_obj)
            existing_task_map[thread_id] = new_task_obj

            processed_metas.append({
                "email_id": email_id,
                "candidate_id": cand_id,
                "thread_id": thread_id,
                "from_name": email.from_name,
                "from_email": email.from_email,
                "subject": email.subject,
                "body": email.body,
                "received_at": email.received_at,
                "status": "created",
                "skip_reason": None,
                "task_id": t_id,
                "confidence": classification.get("confidence", 0.85),
                "category": classification.get("category", "triage"),
                "reasoning": classification.get("reasoning", "Created task"),
                "ingested_at": now_str
            })

    # Execute single bulk save to database
    DBAdapter.bulk_save_ingest(cand_id, new_tasks, updated_tasks, processed_metas)

    return IngestResponse(
        processed=len(payload.emails),
        tasks_created=tasks_created,
        tasks_updated=tasks_updated,
        skipped=skipped_count,
        errors=errors
    )

@app.get("/api/tasks")
def get_api_tasks(candidate_id: str = Query(...)):
    norm_cand = normalize_candidate_id(candidate_id)
    return DBAdapter.get_api_tasks(norm_cand)

@app.get("/api/stats")
def get_api_stats(candidate_id: str = Query(...)):
    norm_cand = normalize_candidate_id(candidate_id)
    return DBAdapter.get_api_stats(norm_cand)

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest):
    if not payload.candidate_id or not payload.query:
        raise HTTPException(status_code=400, detail="candidate_id and query are required")

    result = query_chat_engine(payload.candidate_id, payload.query)
    return ChatResponse(answer=result["answer"], supporting_data=result["supporting_data"])

@app.get("/api/sample-emails")
def get_sample_emails(count: int = Query(250, le=250)):
    return {"emails": generate_sample_emails(count)}

@app.delete("/api/reset")
def reset_database(candidate_id: str = Query(...)):
    norm_cand = normalize_candidate_id(candidate_id)
    return DBAdapter.reset_candidate_data(norm_cand)
