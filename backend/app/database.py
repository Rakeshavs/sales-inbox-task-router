import os
import sqlite3
import json
from typing import Dict, Any, List, Optional, Set
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

raw_uri = os.getenv("MONGODB_URI", "mongodb+srv://medharirakeshavs_db_user:JckjcRpVMbg1MiWy@cluster0.8zol7ke.mongodb.net/?appName=Cluster0").strip().strip('"').strip("'")

if "tlsAllowInvalidCertificates" not in raw_uri:
    sep = "&" if "?" in raw_uri else "?"
    MONGODB_URI = f"{raw_uri}{sep}tls=true&tlsAllowInvalidCertificates=true&tlsAllowInvalidHostnames=true"
else:
    MONGODB_URI = raw_uri

MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "sales_router_db").strip().strip('"').strip("'")
SQLITE_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sales_router_db.sqlite"))

def get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite_db():
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processed_emails (
        email_id TEXT PRIMARY KEY,
        candidate_id TEXT,
        thread_id TEXT,
        from_name TEXT,
        from_email TEXT,
        subject TEXT,
        body TEXT,
        received_at TEXT,
        status TEXT,
        skip_reason TEXT,
        task_id TEXT,
        confidence REAL,
        category TEXT,
        reasoning TEXT,
        ingested_at TEXT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        candidate_id TEXT,
        source_email_id TEXT UNIQUE,
        thread_id TEXT,
        title TEXT,
        description TEXT,
        assignee_id TEXT,
        category TEXT,
        priority TEXT,
        due_date TEXT,
        deal_value_inr INTEGER,
        company_name TEXT,
        confidence REAL,
        created_at TEXT,
        updated_at TEXT
    );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_cand ON tasks(candidate_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_cand ON processed_emails(candidate_id);")
    conn.commit()
    conn.close()

def get_mongo_db():
    # 2500ms fast connection attempt to avoid cloud timeouts
    client = MongoClient(
        MONGODB_URI,
        tls=True,
        tlsAllowInvalidCertificates=True,
        tlsAllowInvalidHostnames=True,
        serverSelectionTimeoutMS=2500,
        connectTimeoutMS=2500
    )
    client.admin.command('ping')
    return client[MONGODB_DB_NAME]

def init_db():
    """Initializes Database on startup (MongoDB Atlas Primary, SQLite Fallback)"""
    init_sqlite_db()
    try:
        db = get_mongo_db()
        db.tasks.create_index("candidate_id")
        db.tasks.create_index("thread_id")
        db.tasks.create_index("task_id", unique=True)
        db.tasks.create_index("source_email_id", unique=True)
        db.processed_emails.create_index("candidate_id")
        db.processed_emails.create_index("thread_id")
        db.processed_emails.create_index("email_id", unique=True)
        print("MongoDB Atlas database initialized successfully.")
    except Exception as e:
        print(f"MongoDB Atlas initialization notice ({e}); SQLite failover active.")

# Resilient Dual-Engine DBAdapter (MongoDB Atlas Primary + SQLite Automatic Failover)
class DBAdapter:
    @staticmethod
    def is_already_processed(email_id: str, candidate_id: str) -> bool:
        try:
            db = get_mongo_db()
            return db.processed_emails.find_one({"email_id": email_id, "candidate_id": candidate_id}) is not None
        except Exception:
            conn = get_sqlite_conn()
            res = conn.execute("SELECT 1 FROM processed_emails WHERE email_id = ? AND candidate_id = ?", (email_id, candidate_id)).fetchone()
            conn.close()
            return res is not None

    @staticmethod
    def get_processed_email_ids(candidate_id: str) -> Set[str]:
        try:
            db = get_mongo_db()
            records = db.processed_emails.find({"candidate_id": candidate_id}, {"email_id": 1})
            return {r["email_id"] for r in records if "email_id" in r}
        except Exception:
            conn = get_sqlite_conn()
            rows = conn.execute("SELECT email_id FROM processed_emails WHERE candidate_id = ?", (candidate_id,)).fetchall()
            conn.close()
            return {r["email_id"] for r in rows}

    @staticmethod
    def get_tasks_by_candidate(candidate_id: str) -> Dict[str, Dict[str, Any]]:
        try:
            db = get_mongo_db()
            cursor = db.tasks.find({"candidate_id": candidate_id}, {"_id": 0})
            return {t["thread_id"]: t for t in cursor if "thread_id" in t}
        except Exception:
            conn = get_sqlite_conn()
            rows = conn.execute("SELECT * FROM tasks WHERE candidate_id = ?", (candidate_id,)).fetchall()
            conn.close()
            return {dict(r)["thread_id"]: dict(r) for r in rows if dict(r).get("thread_id")}

    @staticmethod
    def get_task_by_source_email(source_email_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = get_mongo_db()
            return db.tasks.find_one({"source_email_id": source_email_id}, {"_id": 0})
        except Exception:
            conn = get_sqlite_conn()
            row = conn.execute("SELECT * FROM tasks WHERE source_email_id = ?", (source_email_id,)).fetchone()
            conn.close()
            return dict(row) if row else None

    @staticmethod
    def insert_task(task_dict: Dict[str, Any]):
        try:
            db = get_mongo_db()
            db.tasks.insert_one(task_dict)
        except Exception:
            conn = get_sqlite_conn()
            cols = list(task_dict.keys())
            placeholders = ", ".join(["?"] * len(cols))
            col_str = ", ".join(cols)
            vals = [task_dict[c] for c in cols]
            conn.execute(f"INSERT OR REPLACE INTO tasks ({col_str}) VALUES ({placeholders})", vals)
            conn.commit()
            conn.close()

    @staticmethod
    def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = get_mongo_db()
            return db.tasks.find_one({"task_id": task_id}, {"_id": 0})
        except Exception:
            conn = get_sqlite_conn()
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            conn.close()
            return dict(row) if row else None

    @staticmethod
    def bulk_save_ingest(
        candidate_id: str,
        tasks_to_insert: List[Dict[str, Any]],
        tasks_to_update: List[Dict[str, Any]],
        processed_emails_to_insert: List[Dict[str, Any]]
    ):
        try:
            db = get_mongo_db()
            if processed_emails_to_insert:
                try: db.processed_emails.insert_many(processed_emails_to_insert, ordered=False)
                except Exception: pass
            if tasks_to_insert:
                try: db.tasks.insert_many(tasks_to_insert, ordered=False)
                except Exception: pass
            for upd in tasks_to_update:
                try:
                    db.tasks.update_one(
                        {"task_id": upd["task_id"], "candidate_id": candidate_id},
                        {"$set": {"description": upd["description"], "priority": upd["priority"], "confidence": upd["confidence"], "updated_at": upd.get("updated_at")}}
                    )
                except Exception: pass
            return
        except Exception:
            pass

        # SQLite Fallback Save
        conn = get_sqlite_conn()
        for em in processed_emails_to_insert:
            cols = ["email_id", "candidate_id", "thread_id", "from_name", "from_email", "subject", "body", "received_at", "status", "skip_reason", "task_id", "confidence", "category", "reasoning", "ingested_at"]
            vals = [em.get(c) for c in cols]
            conn.execute("INSERT OR REPLACE INTO processed_emails VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
        for t in tasks_to_insert:
            cols = ["task_id", "candidate_id", "source_email_id", "thread_id", "title", "description", "assignee_id", "category", "priority", "due_date", "deal_value_inr", "company_name", "confidence", "created_at", "updated_at"]
            vals = [t.get(c) for c in cols]
            conn.execute("INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
        for upd in tasks_to_update:
            conn.execute("UPDATE tasks SET description=?, priority=?, confidence=?, updated_at=? WHERE task_id=?", (upd.get("description"), upd.get("priority"), upd.get("confidence"), upd.get("updated_at"), upd.get("task_id")))
        conn.commit()
        conn.close()

    @staticmethod
    def list_tasks(
        candidate_id: str,
        thread_id: Optional[str] = None,
        source_email_id: Optional[str] = None,
        assignee_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        try:
            db = get_mongo_db()
            query = {"candidate_id": candidate_id}
            if thread_id: query["thread_id"] = thread_id
            if source_email_id: query["source_email_id"] = source_email_id
            if assignee_id: query["assignee_id"] = assignee_id
            return list(db.tasks.find(query, {"_id": 0}))
        except Exception:
            conn = get_sqlite_conn()
            sql = "SELECT * FROM tasks WHERE candidate_id = ?"
            params = [candidate_id]
            if thread_id:
                sql += " AND thread_id = ?"
                params.append(thread_id)
            if source_email_id:
                sql += " AND source_email_id = ?"
                params.append(source_email_id)
            if assignee_id:
                sql += " AND assignee_id = ?"
                params.append(assignee_id)
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            return [dict(r) for r in rows]

    @staticmethod
    def get_api_stats(candidate_id: str) -> Dict[str, int]:
        try:
            db = get_mongo_db()
            processed_cnt = db.processed_emails.count_documents({"candidate_id": candidate_id})
            tasks_cnt = db.tasks.count_documents({"candidate_id": candidate_id})
            created_cnt = db.processed_emails.count_documents({"candidate_id": candidate_id, "status": "created"})
            updated_cnt = db.processed_emails.count_documents({"candidate_id": candidate_id, "status": "updated"})
            skipped_cnt = db.processed_emails.count_documents({"candidate_id": candidate_id, "status": "skipped"})
            if created_cnt == 0 and tasks_cnt > 0:
                created_cnt = tasks_cnt
                updated_cnt = 0
                skipped_cnt = max(0, processed_cnt - tasks_cnt)
            return {
                "processed": processed_cnt,
                "tasks_created": created_cnt,
                "tasks_updated": updated_cnt,
                "skipped": skipped_cnt
            }
        except Exception:
            conn = get_sqlite_conn()
            proc = conn.execute("SELECT COUNT(*) FROM processed_emails WHERE candidate_id = ?", (candidate_id,)).fetchone()[0]
            created = conn.execute("SELECT COUNT(*) FROM processed_emails WHERE candidate_id = ? AND status = 'created'", (candidate_id,)).fetchone()[0]
            updated = conn.execute("SELECT COUNT(*) FROM processed_emails WHERE candidate_id = ? AND status = 'updated'", (candidate_id,)).fetchone()[0]
            skipped = conn.execute("SELECT COUNT(*) FROM processed_emails WHERE candidate_id = ? AND status = 'skipped'", (candidate_id,)).fetchone()[0]
            tasks_cnt = conn.execute("SELECT COUNT(*) FROM tasks WHERE candidate_id = ?", (candidate_id,)).fetchone()[0]
            conn.close()
            if created == 0 and tasks_cnt > 0:
                created = tasks_cnt
                updated = 0
                skipped = max(0, proc - tasks_cnt)
            return {
                "processed": proc,
                "tasks_created": created,
                "tasks_updated": updated,
                "skipped": skipped
            }

    @staticmethod
    def update_task(task_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            db = get_mongo_db()
            res = db.tasks.update_one({"task_id": task_id}, {"$set": updates})
            if res.matched_count > 0:
                return db.tasks.find_one({"task_id": task_id}, {"_id": 0})
        except Exception:
            pass

        conn = get_sqlite_conn()
        cols = list(updates.keys())
        set_str = ", ".join([f"{c} = ?" for c in cols])
        vals = [updates[c] for c in cols] + [task_id]
        conn.execute(f"UPDATE tasks SET {set_str} WHERE task_id = ?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def reset_candidate_data(candidate_id: str) -> Dict[str, int]:
        del_tasks = 0
        del_emails = 0
        try:
            db = get_mongo_db()
            del_tasks += db.tasks.delete_many({"candidate_id": candidate_id}).deleted_count
            del_emails += db.processed_emails.delete_many({"candidate_id": candidate_id}).deleted_count
        except Exception:
            pass

        conn = get_sqlite_conn()
        t_cnt = conn.execute("DELETE FROM tasks WHERE candidate_id = ?", (candidate_id,)).rowcount
        e_cnt = conn.execute("DELETE FROM processed_emails WHERE candidate_id = ?", (candidate_id,)).rowcount
        conn.commit()
        conn.close()

        return {
            "deleted_tasks": max(del_tasks, t_cnt),
            "deleted_emails": max(del_emails, e_cnt)
        }
