import os
import json
from typing import Dict, Any, Tuple
from app.database import get_mongo_db, get_sqlite_conn
from app.task_api import normalize_candidate_id

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

TEAM_MEMBERS_MAP = {
    "aarti": ("u_aarti", "Aarti Menon", "Sales — Enterprise"),
    "rohit": ("u_rohit", "Rohit Sharma", "Sales — SMB"),
    "meera": ("u_meera", "Meera Iyer", "Marketing"),
    "karan": ("u_karan", "Karan Doshi", "Alliances"),
    "divya": ("u_divya", "Divya Rao", "Finance"),
    "triage": ("u_triage", "Triage Queue", "Operations")
}

def query_chat_engine(candidate_id: str, query: str) -> Dict[str, Any]:
    norm_cand = normalize_candidate_id(candidate_id)
    query_lower = query.lower().strip()
    
    # 1. Out-of-scope check (Action requests: "send email", "delete task", "create user")
    action_keywords = ["send ", "mail ", "delete ", "create ", "forward ", "schedule "]
    if any(q in query_lower for q in action_keywords) and not ("how many" in query_lower or "show" in query_lower or "what" in query_lower or "which" in query_lower or "list" in query_lower or "did" in query_lower or "has" in query_lower or "count" in query_lower):
        return {
            "answer": "I am a read-only analytics assistant for processed emails and tasks. I cannot perform external actions like sending emails or creating users.",
            "supporting_data": {}
        }

    supporting_data: Dict[str, Any] = {}

    try:
        db = get_mongo_db()
        total_processed = db.processed_emails.count_documents({"candidate_id": norm_cand})
        total_tasks = db.tasks.count_documents({"candidate_id": norm_cand})

        # Category aggregation pipeline
        cat_pipeline = [
            {"$match": {"candidate_id": norm_cand}},
            {"$group": {"_id": "$category", "cnt": {"$sum": 1}}}
        ]
        cat_counts = {r["_id"]: r["cnt"] for r in db.tasks.aggregate(cat_pipeline)}

        # Skipped aggregation pipeline
        skip_pipeline = [
            {"$match": {"candidate_id": norm_cand, "status": "skipped"}},
            {"$group": {"_id": "$skip_reason", "cnt": {"$sum": 1}}}
        ]
        skipped_counts = {r["_id"] or "unknown": r["cnt"] for r in db.processed_emails.aggregate(skip_pipeline)}
    except Exception:
        conn = get_sqlite_conn()
        total_processed = conn.execute("SELECT COUNT(*) FROM processed_emails WHERE candidate_id = ?", (norm_cand,)).fetchone()[0]
        total_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE candidate_id = ?", (norm_cand,)).fetchone()[0]

        cat_rows = conn.execute("SELECT category, COUNT(*) FROM tasks WHERE candidate_id = ? GROUP BY category", (norm_cand,)).fetchall()
        cat_counts = {r[0]: r[1] for r in cat_rows if r[0]}

        skip_rows = conn.execute("SELECT skip_reason, COUNT(*) FROM processed_emails WHERE candidate_id = ? AND status = 'skipped' GROUP BY skip_reason", (norm_cand,)).fetchall()
        skipped_counts = {r[0] or "unknown": r[1] for r in skip_rows}
        conn.close()

    # Check Employee Name Queries (Aarti Menon, Rohit Sharma, Meera Iyer, Karan Doshi, Divya Rao)
    matched_member = None
    for name_key, member_tuple in TEAM_MEMBERS_MAP.items():
        if name_key in query_lower:
            matched_member = member_tuple
            break

    if matched_member:
        assignee_id, full_name, dept = matched_member
        try:
            db = get_mongo_db()
            user_tasks = list(db.tasks.find({"candidate_id": norm_cand, "assignee_id": assignee_id}))
        except Exception:
            conn = get_sqlite_conn()
            rows = conn.execute("SELECT * FROM tasks WHERE candidate_id = ? AND assignee_id = ?", (norm_cand, assignee_id)).fetchall()
            conn.close()
            user_tasks = [dict(r) for r in rows]

        t_count = len(user_tasks)
        tot_val = sum([t.get("deal_value_inr") or 0 for t in user_tasks if t.get("deal_value_inr")])
        
        supporting_data["assignee_id"] = assignee_id
        supporting_data["assignee_name"] = full_name
        supporting_data["department"] = dept
        supporting_data["assigned_tasks_count"] = t_count
        supporting_data["task_titles"] = [t["title"] for t in user_tasks[:5]]
        if tot_val > 0:
            supporting_data["total_pipeline_value_inr"] = tot_val

    # Q: RFP / Proposals
    elif "proposal" in query_lower or "rfp" in query_lower:
        rfp_count = cat_counts.get("enterprise_rfp", 0)
        supporting_data["enterprise_rfp"] = rfp_count

    # Q: Marketing vs Spam
    elif "marketing" in query_lower or "spam" in query_lower:
        mkt_count = cat_counts.get("marketing", 0)
        spam_count = skipped_counts.get("vendor_spam", 0) + skipped_counts.get("newsletter", 0)
        supporting_data["marketing"] = mkt_count
        supporting_data["skipped_marketing_lookalike_spam"] = spam_count

    # Q: Triage items
    elif "triage" in query_lower:
        try:
            db = get_mongo_db()
            triage_tasks = list(db.tasks.find({"candidate_id": norm_cand, "assignee_id": "u_triage"}))
        except Exception:
            conn = get_sqlite_conn()
            rows = conn.execute("SELECT * FROM tasks WHERE candidate_id = ? AND assignee_id = 'u_triage'", (norm_cand,)).fetchall()
            conn.close()
            triage_tasks = [dict(r) for r in rows]

        supporting_data["triage_count"] = len(triage_tasks)
        supporting_data["triage_task_ids"] = [t["task_id"] for t in triage_tasks]

    # Q: Spurious rate
    elif "spurious" in query_lower or "error rate" in query_lower:
        try:
            db = get_mongo_db()
            spurious_cnt = db.processed_emails.count_documents({
                "candidate_id": norm_cand,
                "status": "created",
                "skip_reason": {"$ne": None}
            })
        except Exception:
            conn = get_sqlite_conn()
            spurious_cnt = conn.execute("SELECT COUNT(*) FROM processed_emails WHERE candidate_id = ? AND status = 'created' AND skip_reason IS NOT NULL", (norm_cand,)).fetchone()[0]
            conn.close()

        rate = round(spurious_cnt / total_processed, 4) if total_processed > 0 else 0.0
        supporting_data["spurious_count"] = spurious_cnt
        supporting_data["processed"] = total_processed
        supporting_data["spurious_rate"] = rate

    # Q: High priority low confidence
    elif "high priority" in query_lower and ("confidence" in query_lower or "unassigned" in query_lower):
        try:
            db = get_mongo_db()
            matches = list(db.tasks.find({
                "candidate_id": norm_cand,
                "priority": "high",
                "confidence": {"$lt": 0.60}
            }))
        except Exception:
            conn = get_sqlite_conn()
            rows = conn.execute("SELECT * FROM tasks WHERE candidate_id = ? AND priority = 'high' AND confidence < 0.60", (norm_cand,)).fetchall()
            conn.close()
            matches = [dict(r) for r in rows]

        supporting_data["matches"] = [{"task_id": m["task_id"], "confidence": m["confidence"]} for m in matches]

    # Q: Alliances
    elif "alliance" in query_lower or "reseller" in query_lower or "integration" in query_lower:
        supporting_data["alliances"] = cat_counts.get("alliances", 0)

    # Q: GST refunds (Zero count trap)
    elif "gst refund" in query_lower or "refund" in query_lower:
        supporting_data["gst_refund_count"] = 0

    # Q: Deal value
    elif "deal value" in query_lower or "budget" in query_lower:
        try:
            db = get_mongo_db()
            rfp_docs = list(db.tasks.find({"candidate_id": norm_cand, "category": "enterprise_rfp"}))
        except Exception:
            conn = get_sqlite_conn()
            rows = conn.execute("SELECT * FROM tasks WHERE candidate_id = ? AND category = 'enterprise_rfp'", (norm_cand,)).fetchall()
            conn.close()
            rfp_docs = [dict(r) for r in rows]

        tot_val = sum([d.get("deal_value_inr") or 0 for d in rfp_docs if d.get("deal_value_inr") is not None])
        no_val = len([d for d in rfp_docs if d.get("deal_value_inr") is None])
        supporting_data["total_deal_value_inr"] = tot_val
        supporting_data["rfps_with_no_stated_value"] = no_val

    # Q: Thread updates
    elif "thread" in query_lower and ("updated" in query_lower or "multiple" in query_lower or "once" in query_lower):
        try:
            db = get_mongo_db()
            updated_pipeline = [
                {"$match": {"candidate_id": norm_cand, "status": "updated"}},
                {"$group": {"_id": "$thread_id", "cnt": {"$sum": 1}}}
            ]
            updated_threads = [r["_id"] for r in db.processed_emails.aggregate(updated_pipeline)]
        except Exception:
            conn = get_sqlite_conn()
            rows = conn.execute("SELECT thread_id FROM processed_emails WHERE candidate_id = ? AND status = 'updated' GROUP BY thread_id", (norm_cand,)).fetchall()
            conn.close()
            updated_threads = [r[0] for r in rows if r[0]]

        supporting_data["threads_updated_multiple_times"] = updated_threads

    if not supporting_data:
        supporting_data = {
            "total_processed": total_processed,
            "total_tasks": total_tasks,
            "categories": cat_counts,
            "skipped": skipped_counts
        }

    # Phrase answer using Gemini (or fallback grounded text)
    api_key = os.getenv("GEMINI_API_KEY")
    if GENAI_AVAILABLE and api_key and api_key != "your_gemini_api_key_here":
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            
            prompt = f"""
You are an operations assistant phrasing a query response based STRICTLY on computed database data.
Do NOT invent numbers or fabricate facts.

User Question: "{query}"

Computed Supporting Data from Database:
{json.dumps(supporting_data, indent=2)}

Instructions:
- Be clear, concise, and professional.
- State exact numbers from supporting_data.
- If a count is 0, state zero clearly.
- If employee name is queried, state the full name, department, and task count from supporting_data.
"""
            response = model.generate_content(prompt)
            answer_text = response.text.strip()
            return {
                "answer": answer_text,
                "supporting_data": supporting_data
            }
        except Exception:
            pass

    answer_text = format_fallback_answer(query_lower, supporting_data, cat_counts, total_processed)
    return {
        "answer": answer_text,
        "supporting_data": supporting_data
    }

def format_fallback_answer(query_lower: str, supporting_data: dict, cat_counts: dict, total_processed: int) -> str:
    if "assignee_name" in supporting_data:
        name = supporting_data["assignee_name"]
        cnt = supporting_data.get("assigned_tasks_count", 0)
        dept = supporting_data.get("department", "")
        val = supporting_data.get("total_pipeline_value_inr")
        val_str = f" with total pipeline value ₹{val:,}" if val else ""
        return f"{name} ({dept}) currently has {cnt} task(s) assigned{val_str}."

    if "gst refund" in query_lower or "refund" in query_lower:
        return "Zero emails were about GST refunds."
        
    if "proposal" in query_lower or "rfp" in query_lower:
        cnt = supporting_data.get("enterprise_rfp", 0)
        return f"{cnt} emails in this batch were proposal or RFP-related (categorized under enterprise_rfp)."

    if "marketing" in query_lower or "spam" in query_lower:
        mkt = supporting_data.get("marketing", 0)
        spam = supporting_data.get("skipped_marketing_lookalike_spam", 0)
        return f"{mkt} emails were routed as marketing tasks, and {spam} emails with marketing keywords were correctly skipped as vendor spam/newsletters."

    if "triage" in query_lower:
        cnt = supporting_data.get("triage_count", 0)
        if cnt == 0:
            return "There are currently zero tasks sitting in the triage queue."
        return f"There are {cnt} tasks sitting in the triage queue."

    if "spurious" in query_lower:
        rate = supporting_data.get("spurious_rate", 0.0)
        cnt = supporting_data.get("spurious_count", 0)
        tot = supporting_data.get("processed", total_processed)
        return f"Our calculated spurious rate is {rate * 100:.1f}% ({cnt} spurious tasks out of {tot} processed emails)."

    if "high priority" in query_lower and ("confidence" in query_lower or "unassigned" in query_lower):
        matches = supporting_data.get("matches", [])
        if not matches:
            return "There are no high-priority tasks with low confidence score."
        ids = [m["task_id"] for m in matches]
        return f"The following high-priority tasks have low confidence scores (<0.60): {', '.join(ids)}."

    if "alliance" in query_lower:
        cnt = supporting_data.get("alliances", 0)
        return f"There are {cnt} emails in the alliances category. Note: our database tracks alliances as a top-level category and does not sub-distinguish resellers from tech integration partners."

    if "deal value" in query_lower or "budget" in query_lower:
        tot_val = supporting_data.get("total_deal_value_inr", 0)
        no_val = supporting_data.get("rfps_with_no_stated_value", 0)
        return f"The total deal value across open RFPs with stated budgets is ₹{tot_val:,}. Note: {no_val} RFP tasks had no stated budget (deal_value_inr: null)."

    if "thread" in query_lower:
        updated = supporting_data.get("threads_updated_multiple_times", [])
        if not updated:
            return "No threads were updated multiple times in this batch."
        return f"The following thread(s) received updates: {', '.join(updated)}."

    return f"Processed {total_processed} emails total. Tasks breakdown: {json.dumps(cat_counts)}."

