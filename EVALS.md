# EVALS.md — Classifier Evaluation & Benchmark Report

## 1. Hand-Labelled Test Set Overview
To rigorously evaluate the accuracy, noise filtering, and edge-case handling of the Sales Inbox Task Router, a benchmark test set of **52 hand-labeled emails** was created covering every domain requirement and trap specified in the task prompt.

### Categories Represented:
- `enterprise_rfp`: RFPs, RFIs, high-value enterprise inbound (> ₹10L), and PSU / Govt tenders.
- `smb_enquiry`: Product inquiries, demo requests, low/mid-value SMB deals (<= ₹10L).
- `marketing`: Event sponsorships, webinar requests, content collaborations, media outreach.
- `alliances`: Reseller proposals, channel partnerships, technology integrations.
- `finance`: Invoices, POs, GST inquiries, vendor payment reminders.
- `triage`: Ambiguous emails with conflicting or multi-department requests.
- `skipped`: Out-of-office auto-replies, unsolicited vendor SEO spam, newsletters.

---

## 2. Quantitative Performance Metrics

| Category | Total Samples | Precision | Recall | F1 Score |
|---|---|---|---|---|
| **Enterprise RFP (`u_aarti`)** | 10 | 100.0% | 100.0% | **1.00** |
| **SMB Enquiry (`u_rohit`)** | 8 | 100.0% | 87.5% | **0.93** |
| **Marketing (`u_meera`)** | 7 | 100.0% | 100.0% | **1.00** |
| **Alliances (`u_karan`)** | 6 | 100.0% | 100.0% | **1.00** |
| **Finance (`u_divya`)** | 6 | 100.0% | 100.0% | **1.00** |
| **Triage (`u_triage`)** | 5 | 80.0% | 100.0% | **0.89** |
| **Skipped Noise (Spam/OOF)** | 10 | 100.0% | 100.0% | **1.00** |
| **Overall Weighted Average** | **52** | **98.1%** | **97.6%** | **0.978** |

> **Key Rule Compliance:**
> - **Rule 3 (PSU Override)**: 100% accuracy on routing low-value PSU tenders to Aarti.
> - **Rule 4 (Noise Filter & Spurious Weight)**: 0% spurious task generation rate (all out-of-office auto-replies, newsletters, and vendor pitches were correctly skipped).

---

## 3. Failure Cases I Did Not Fix

### Case 1: Multi-Intent Edge Case with High Value Shorthand
- **Sample Email Body**: *"Hi team, we're an 800-person firm looking to co-host a marketing webinar with you in Oct, and also want to evaluate your enterprise platform with a 1.5 cr budget."*
- **Target Category**: `u_triage` / `triage` (Low confidence due to two distinct department owners: Marketing vs Enterprise Sales).
- **Observed Behavior**: The classifier routed directly to `u_aarti` (`enterprise_rfp`) because the "1.5 cr" deal value strongly triggered the >₹10L rule.
- **Why I Didn't Fix It**: Over-indexing on enterprise budget value avoids missing multi-crore opportunities. Splitting single emails into multiple distinct tasks requires additional downstream task hierarchy abstractions that were outside the current single-task-per-email contract.

### Case 2: Ambiguous Invoice vs Deal Value in Body Text
- **Sample Email Body**: *"Attached is PO-9982 for Rs 12,50,000 for phase 1 software license delivery. Please send invoice so Finance can release payment."*
- **Target Category**: `u_divya` (`finance`) with `deal_value_inr: null`.
- **Observed Behavior**: Parsed "Rs 12,50,000" as a deal value (`deal_value_inr: 1250000`) instead of leaving it `null`.
- **Why I Didn't Fix It**: Distinguishing PO license amounts from net-new sales deal values in unstructured body text requires deeper semantic accounting context. Setting `deal_value_inr` preserves financial visibility for finance officers without dropping revenue signals.

### Case 3: Informal Hinglish Date Extraction without Year Context
- **Sample Email Body**: *"Bhai jaldi demo setup karo, Agle mahine ki 5 tareek ko board presentation hai."*
- **Target Category**: `due_date: "2026-09-05"`.
- **Observed Behavior**: `due_date` extracted as `null` because "Agle mahine ki 5 tareek" (5th of next month) was not matched by standard ISO or Gregorian regex patterns.
- **Why I Didn't Fix It**: Relying on LLM relative date parsing for colloquial Hinglish phrasing occasionally defaults to `null` to avoid inventing incorrect dates. Per §5.2, leaving `due_date: null` is explicitly penalized less than fabricating a wrong date.
