import os
import certifi
from typing import Dict, Any, List, Optional, Set
from pymongo import MongoClient

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://medharirakeshavs_db_user:JckjcRpVMbg1MiWy@cluster0.8zol7ke.mongodb.net/?appName=Cluster0")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "sales_router_db")

def get_mongo_db():
    try:
        client = MongoClient(
            MONGODB_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=10000
        )
        # Verify connection
        client.admin.command('ping')
        return client[MONGODB_DB_NAME]
    except Exception:
        # Fallback with invalid cert allowance if CAbundle mismatch on cloud containers
        client = MongoClient(
            MONGODB_URI,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=10000
        )
        return client[MONGODB_DB_NAME]

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
        print(f"Error initializing MongoDB Atlas: {e}")

# High-performance MongoDB Atlas DBAdapter
class DBAdapter:
    @staticmethod
    def is_already_processed(email_id: str, candidate_id: str) -> bool:
        db = get_mongo_db()
        return db.processed_emails.find_one({"email_id": email_id, "candidate_id": candidate_id}) is not None

    @staticmethod
    def get_processed_email_ids(candidate_id: str) -> Set[str]:
        db = get_mongo_db()
        docs = db.processed_emails.find({"candidate_id": candidate_id}, {"email_id": 1})
        return {d["email_id"] for d in docs}

    @staticmethod
    def get_tasks_by_candidate(candidate_id: str) -> Dict[str, Dict[str, Any]]:
        db = get_mongo_db()
        docs = list(db.tasks.find({"candidate_id": candidate_id}))
        thread_map = {}
        for doc in docs:
            if "_id" in doc:
                del doc["_id"]
            thread_map[doc["thread_id"]] = doc
        return thread_map

    @staticmethod
    def bulk_save_ingest(new_tasks: List[Dict[str, Any]], updated_tasks: List[Dict[str, Any]], processed_metas: List[Dict[str, Any]]):
        db = get_mongo_db()
        if new_tasks:
            db.tasks.insert_many(new_tasks, ordered=False)
        for u in updated_tasks:
            db.tasks.update_one({"task_id": u["task_id"]}, {"$set": u})
        if processed_metas:
            db.processed_emails.insert_many(processed_metas, ordered=False)

    @staticmethod
    def get_task_by_source_email(source_email_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        doc = db.tasks.find_one({"source_email_id": source_email_id})
        if doc and "_id" in doc:
            del doc["_id"]
        return doc

    @staticmethod
    def get_task_by_thread(thread_id: str, candidate_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        doc = db.tasks.find_one({"thread_id": thread_id, "candidate_id": candidate_id})
        if doc and "_id" in doc:
            del doc["_id"]
        return doc

    @staticmethod
    def get_task(task_id: str) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        doc = db.tasks.find_one({"task_id": task_id})
        if doc and "_id" in doc:
            del doc["_id"]
        return doc

    @staticmethod
    def insert_task(task_data: Dict[str, Any]):
        db = get_mongo_db()
        db.tasks.update_one(
            {"source_email_id": task_data["source_email_id"]},
            {"$set": task_data},
            upsert=True
        )

    @staticmethod
    def update_task_fields(task_id: str, fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        db = get_mongo_db()
        db.tasks.update_one({"task_id": task_id}, {"$set": fields})
        
        sync_fields = {}
        if "category" in fields:
            sync_fields["category"] = fields["category"]
        if "confidence" in fields:
            sync_fields["confidence"] = fields["confidence"]
        if sync_fields:
            db.processed_emails.update_many({"task_id": task_id}, {"$set": sync_fields})
            
        return DBAdapter.get_task(task_id)

    @staticmethod
    def list_tasks(candidate_id: str, thread_id: Optional[str] = None, source_email_id: Optional[str] = None, assignee_id: Optional[str] = None) -> List[Dict[str, Any]]:
        db = get_mongo_db()
        query = {"candidate_id": candidate_id}
        if thread_id:
            query["thread_id"] = thread_id
        if source_email_id:
            query["source_email_id"] = source_email_id
        if assignee_id:
            query["assignee_id"] = assignee_id
        
        docs = list(db.tasks.find(query).sort("created_at", -1))
        for doc in docs:
            if "_id" in doc:
                del doc["_id"]
        return docs

    @staticmethod
    def delete_task(task_id: str) -> bool:
        db = get_mongo_db()
        res = db.tasks.delete_one({"task_id": task_id})
        return res.deleted_count > 0

    @staticmethod
    def insert_processed_email(email_meta: Dict[str, Any]):
        db = get_mongo_db()
        db.processed_emails.update_one(
            {"email_id": email_meta["email_id"], "candidate_id": email_meta["candidate_id"]},
            {"$set": email_meta},
            upsert=True
        )

    @staticmethod
    def get_api_tasks(candidate_id: str) -> List[Dict[str, Any]]:
        db = get_mongo_db()
        docs = list(db.processed_emails.find({"candidate_id": candidate_id}).sort("ingested_at", -1))
        for doc in docs:
            if "_id" in doc:
                del doc["_id"]
        return docs

    @staticmethod
    def get_api_stats(candidate_id: str) -> Dict[str, Any]:
        db = get_mongo_db()
        total_processed = db.processed_emails.count_documents({"candidate_id": candidate_id})
        
        status_pipeline = [
            {"$match": {"candidate_id": candidate_id}},
            {"$group": {"_id": "$status", "cnt": {"$sum": 1}}}
        ]
        status_counts = {r["_id"]: r["cnt"] for r in db.processed_emails.aggregate(status_pipeline)}

        cat_pipeline = [
            {"$match": {"candidate_id": candidate_id}},
            {"$group": {"_id": "$category", "cnt": {"$sum": 1}}}
        ]
        category_counts = {r["_id"]: r["cnt"] for r in db.tasks.aggregate(cat_pipeline)}

        return {
            "processed": total_processed,
            "tasks_created": status_counts.get("created", 0),
            "tasks_updated": status_counts.get("updated", 0),
            "skipped": status_counts.get("skipped", 0),
            "by_category": category_counts
        }

    @staticmethod
    def reset_candidate_data(candidate_id: str) -> Dict[str, Any]:
        db = get_mongo_db()
        res_tasks = db.tasks.delete_many({"candidate_id": candidate_id})
        res_emails = db.processed_emails.delete_many({"candidate_id": candidate_id})
        return {
            "status": "cleared",
            "deleted_tasks": res_tasks.deleted_count,
            "deleted_emails": res_emails.deleted_count
        }
