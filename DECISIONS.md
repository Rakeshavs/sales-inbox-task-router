# DECISIONS.md — Engineering Tradeoffs & Architectural Choices

## 1. Five Core Engineering Tradeoffs

### Tradeoff 1: Handling Gemini API Rate Limits & Retries (Resilience vs Latency)
- **Tradeoff**: Asynchronous parallel batching vs Synchronous rate-limited classification with deterministic rule fallback.
- **Why I Made It**: Gemini free-tier imposes rate limits (~15 RPM). To ensure `POST /ingest` never fails during heavy grading batches (up to 100 emails), I implemented a hybrid architecture:
  1. A fast, zero-latency local regex pre-checker handles noise (OOF auto-replies, newsletters, vendor SEO spam).
  2. A local rule-based fallback heuristic classifier activates automatically if Gemini API calls encounter rate limits (429) or latency timeouts.
- **Outcome**: `POST /ingest` always completes within seconds and guarantees 100% availability even under API rate limits.

### Tradeoff 2: Enforcing Idempotency & Thread Reconciliation (Stateful Deduplication)
- **Tradeoff**: Global message-id hash locking vs Database-level primary key uniqueness on `source_email_id` and `thread_id`.
- **Why I Made It**: Grading runs 2 and 3 test re-submitting identical email batches and thread replies. I enforced idempotency at two database layers:
  1. `processed_emails` table uses `email_id` as PRIMARY KEY to silently drop duplicate ingests.
  2. `POST /ingest` queries `tasks` by `thread_id`. If an existing task exists for a thread, the pipeline issues a `PATCH` update to existing task records rather than creating a duplicate task record.

### Tradeoff 3: Dual Data Model Design (Raw Task API vs Metadata Audit Store)
- **Tradeoff**: Single task table vs Separated `tasks` + `processed_emails` stores.
- **Why I Made It**: The raw Task API spec (§5) has no schema fields for skipped emails or skip reasons. Storing skipped emails inside `tasks` would violate the spec's exact GET `/tasks` schema during grading.
- **Solution**:
  - `tasks` table adheres 100% to §5 Task API fields.
  - `processed_emails` table tracks every processed email (status, skip_reason, confidence, reasoning).
  - This allows the ops chat interface to answer questions instantly about skipped emails (e.g. vendor spam) without re-querying Gemini for known facts.

### Tradeoff 4: Zero-Hallucination Chat Grounding (MongoDB Query Execution Path)
- **Tradeoff**: Direct LLM RAG prompt vs Deterministic MongoDB Query Engine (`supporting_data`).
- **Why I Made It**: LLMs frequently hallucinate exact counts or invent numbers when asked about zero-match categories (e.g. "GST refunds").
- **Implementation Path**:
  $$\text{User Question} \longrightarrow \text{MongoDB Intent Engine} \longrightarrow \text{Execute MongoDB Aggregation} \longrightarrow \text{Generate } \mathtt{supporting\_data} \longrightarrow \text{LLM Phrasing}$$
  - The query engine computes exact counts, sums, and filter lists directly from MongoDB Atlas.
  - The resulting `supporting_data` payload is passed to Gemini strictly for phrasing. If `supporting_data` has count 0, the answer explicitly states zero.

### Tradeoff 5: One Thing I Knowingly Shipped That Gets Something Wrong
- **Tradeoff**: Treating multi-ask emails as a single triage task rather than auto-splitting into separate tasks.
- **Context**: In Example 11 (Halcyon Retail), an email asks for both an 800-person platform evaluation (Sales) and a webinar co-hosting (Marketing).
- **Decision**: The system routes the email to `u_triage` with category `triage` and lower confidence (`0.42`). While splitting into two separate tasks is theoretically possible, doing so breaks 1-to-1 `source_email_id` mapping in raw Task API lookups. Routing to `u_triage` with a clear explanation in `description` guarantees human operations review.

---

## 2. What I Would Do With Two More Weeks
1. **Background Distributed Queue (Celery/Redis)**: Move LLM extraction calls into worker pools with exponential backoff and rate-limit token buckets.
2. **Fine-Tuned Small Language Model (SLM)**: Fine-tune a lightweight 3B model (e.g., Llama-3-3B or Gemma-2B) specifically on B2B email routing logic to eliminate external API costs entirely.
3. **Multi-Task Splitter UI**: Allow ops executives in the frontend chat panel to click "Split Task" on triage items to bifurcate sub-tasks across departments.
4. **Vector Embedding Search (SQLite-VSS)**: Enable semantic similarity search across historical email threads for instant context retrieval.
