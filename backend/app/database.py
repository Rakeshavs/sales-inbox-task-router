import os
from typing import Dict, Any, List, Optional, Set
from pymongo import MongoClient

raw_uri = os.getenv("MONGODB_URI", "mongodb+srv://medharirakeshavs_db_user:JckjcRpVMbg1MiWy@cluster0.8zol7ke.mongodb.net/?appName=Cluster0")
if "tlsAllowInvalidCertificates" not in raw_uri and "tlsInsecure" not in raw_uri:
    if "?" in raw_uri:
        MONGODB_URI = raw_uri + "&tlsAllowInvalidCertificates=true"
    else:
        MONGODB_URI = raw_uri + "?tlsAllowInvalidCertificates=true"
else:
    MONGODB_URI = raw_uri

MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "sales_router_db")

def get_mongo_db():
    return MongoClient(
        MONGODB_URI,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=10000
    )[MONGODB_DB_NAME]

def init_db():
    """Initializes MongoDB Atlas indexes on startup"""
    try:
        db = get_mongo_db()
        db.tasks.create_index("candidate_id")
        db.tasks.create_index("thread_id")
        db.tasks.create_index("task_id", unique=True)
        db.tasks.create_index("source_email_id", unique=True)
        db.processed_emails.create_index("candidate_id")
        db.processed_emails.create_index("thread_id")
        db.processed_emails.create_index("email_id", unique=True)
        print("MongoDB Atlas database and indexes initialized successfully.")
    except Exception as e:
        print(f"MongoDB Atlas initialization warning: {e}")

# High-performance MongoDB Atlas DBAdapter
class DBAdapter:
    @staticmethod
    def is_already_processed(email_id: str, candidate_id: str) -> bool:
        db = get_mongo_db()
        return db.processed_emails.find_one({"email_id": email_id, "candidate_id": candidate_id}) is not None

    @staticmethod
    def get_processed_email_ids(candidate_id: str) -> Set[str]:
        db = get_mongo_db()
        records = db.processed_emails.find({"candidate_id": candidate_id}, {"email_id": 1})
        return {r["email_id"] for r in records if "email_id" in r}

    @staticmethod
    def get_tasks_by_candidate(candidate_id: str) -> Dict[str, Dict[str, Any]]:
        db = get_mongo_db()
        cursor = db.tasks.find({"candidate_id": candidate_id}, {"_id": 0})
        return {t["thread_id"]: t for t in cursor if "thread_id" in t}

    @staticmethod
    def get_task_by_source_email(source_email_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        return db.tasks.find_one({"source_email_id": source_email_id}, {"_id": 0})

    @staticmethod
    def insert_task(task_dict: Dict[str, Any]):
        db = get_mongo_db()
        db.tasks.insert_one(task_dict)

    @staticmethod
    def get_task_by_id(task_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        return db.tasks.find_one({"task_id": task_id}, {"_id": 0})

    @staticmethod
    def bulk_save_ingest(
        candidate_id: str,
        tasks_to_insert: List[Dict[str, Any]],
        tasks_to_update: List[Dict[str, Any]],
        processed_emails_to_insert: List[Dict[str, Any]]
    ):
        db = get_mongo_db()

        # Insert new processed email logs
        if processed_emails_to_insert:
            try:
                db.processed_emails.insert_many(processed_emails_to_insert, ordered=False)
            except Exception:
                pass

        # Insert new tasks
        if tasks_to_insert:
            try:
                db.tasks.insert_many(tasks_to_insert, ordered=False)
            except Exception:
                pass

        # Update existing thread tasks
        for upd in tasks_to_update:
            try:
                db.tasks.update_one(
                    {"task_id": upd["task_id"], "candidate_id": candidate_id},
                    {
                        "$set": {
                            "description": upd["description"],
                            "priority": upd["priority"],
                            "confidence": upd["confidence"],
                            "updated_at": upd.get("updated_at")
                        }
                    }
                )
            except Exception:
                pass

    @staticmethod
    def list_tasks(candidate_id: str) -> List[Dict[str, Any]]:
        db = get_mongo_db()
        cursor = db.tasks.find({"candidate_id": candidate_id}, {"_id": 0})
        return list(cursor)

    @staticmethod
    def get_api_stats(candidate_id: str) -> Dict[str, int]:
        db = get_mongo_db()
        processed_cnt = db.processed_emails.count_documents({"candidate_id": candidate_id})
        tasks_cnt = db.tasks.count_documents({"candidate_id": candidate_id})
        
        # Estimate updated threads and skipped
        updated_cnt = db.tasks.count_documents({
            "candidate_id": candidate_id,
            "updated_at": {"$ne": None}
        })
        skipped_cnt = max(0, processed_cnt - tasks_cnt - updated_cnt)

        return {
            "processed": processed_cnt,
            "tasks_created": tasks_cnt,
            "tasks_updated": updated_cnt,
            "skipped": skipped_cnt
        }

    @staticmethod
    def update_task(task_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        res = db.tasks.update_one({"task_id": task_id}, {"$set": updates})
        if res.matched_count > 0:
            return db.tasks.find_one({"task_id": task_id}, {"_id": 0})
        return None

    @staticmethod
    def reset_candidate_data(candidate_id: str) -> Dict[str, int]:
        db = get_mongo_db()
        del_tasks = db.tasks.delete_many({"candidate_id": candidate_id}).deleted_count
        del_emails = db.processed_emails.delete_many({"candidate_id": candidate_id}).deleted_count
        return {
            "deleted_tasks": del_tasks,
            "deleted_emails": del_emails
        }
