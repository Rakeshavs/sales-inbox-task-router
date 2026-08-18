# Sales Inbox → Task Router

### Candidate & Deployment Information
- **`candidate_id`**: `medharirakeshavs@gmail.com`
- **Backend API URL**: `https://sales-inbox-task-router-qgl7.onrender.com`
- **Frontend App URL**: `https://sales-router-frontend.vercel.app`
- **Chat Endpoint**: `https://sales-inbox-task-router-qgl7.onrender.com/api/chat`

---

## Quickstart (Setup in 3 Commands)

```bash
# 1. Install backend dependencies
pip install -r backend/requirements.txt

# 2. Run backend server
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Start frontend dev server
cd frontend && npm install && npm run dev
```

---

## Architecture Overview

```
[ React Frontend ] (Port 3000)
       |
       v (RESTful API / JSON)
[ FastAPI Backend ] (Port 8000) <---> [ MongoDB Atlas Cloud Database ]
       |
       v (Structured JSON Output)
[ Gemini API (Flash 1.5) ]
```

- **Task API (`/tasks`, `/users`)**: Implements strict §5 schema validation with exact HTTP 400 Bad Request enum error formatting.
- **Ingestion Pipeline (`/ingest`)**: High-speed batch processing engine that classifies emails, reconciles thread replies (`PATCH`), and filters out noise (OOF, newsletters, vendor spam).
- **Grounded Chat (`/api/chat`)**: Translates natural language queries into exact MongoDB Atlas aggregation queries to return `answer` and `supporting_data` with zero hallucinations.
- **Persistence**: Connected directly to cloud MongoDB Atlas (`cluster0.8zol7ke.mongodb.net`) ensuring high-availability data persistence.

---

## Testing & Verification

Run the automated pytest test suite covering enum validation, idempotency, thread updates, and chat traps:

```bash
pytest backend/tests
```

Run the 52-email benchmark evaluation suite:

```bash
python backend/tests/eval_benchmark.py
```

---

## Repository Structure
- `backend/app/`: FastAPI application, Task API endpoints, Router & Grounded Chat Engine.
- `backend/tests/`: Automated pytest unit tests & benchmark evaluation script.
- `frontend/`: React + Vite conversational interface with team queue tabs, pre-routing data table & chat panel.
- `data/team_roster.json`: Team assignment roster.
- `EVALS.md`: Benchmark evaluation report on 50+ hand-labelled emails & failure analysis.
- `DECISIONS.md`: 5 core engineering tradeoffs & architectural choices.
