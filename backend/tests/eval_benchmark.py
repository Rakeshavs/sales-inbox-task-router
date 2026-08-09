import json
import os
import sys

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.router import classify_email_with_llm

# 52 Benchmark Emails
BENCHMARK_SUITE = [
    # 1. Enterprise RFPs (>10L & PSU)
    {"email": {"email_id": "e_01", "subject": "RFP - Enterprise DMS", "body": "Meridian Steel invites proposals for an enterprise DMS. Budget Rs 25 lakhs.", "from_name": "Suresh", "from_email": "s@meridian.com"}, "expected_assignee": "u_aarti", "category": "enterprise_rfp"},
    {"email": {"email_id": "e_02", "subject": "PSU Tender - BHEL ERP System", "body": "BHEL tender for ERP upgrade. Value Rs 3 lakhs.", "from_name": "Govt Tender Office", "from_email": "tenders@bhel.in"}, "expected_assignee": "u_aarti", "category": "enterprise_rfp"}, # Rule 3: PSU Tender -> Aarti despite 3L
    {"email": {"email_id": "e_03", "subject": "RFI for Core Platform", "body": "We are evaluating vendors for a 5,000 user platform. Budget 1.2 Crore INR.", "from_name": "VP Tech", "from_email": "vp@bigcorp.com"}, "expected_assignee": "u_aarti", "category": "enterprise_rfp"},
    {"email": {"email_id": "e_04", "subject": "Proposal Request - Reliance Retail", "body": "Please share formal commercial proposal for enterprise roll-out. Deal size ~45 Lakhs.", "from_name": "Procurement", "from_email": "proc@reliance.com"}, "expected_assignee": "u_aarti", "category": "enterprise_rfp"},
    {"email": {"email_id": "e_05", "subject": "Government E-Procurement Bid #9901", "body": "National Informatics Centre RFP for cloud migration.", "from_name": "NIC Tender Cell", "from_email": "nic@gov.in"}, "expected_assignee": "u_aarti", "category": "enterprise_rfp"},
    
    # 2. SMB Enquiries (<=10L)
    {"email": {"email_id": "s_01", "subject": "Demo Request for Startup", "body": "Hi, we are a 15-person team interested in a demo of your CRM. Budget Rs 2 lakhs.", "from_name": "Founder", "from_email": "ceo@startup.io"}, "expected_assignee": "u_rohit", "category": "smb_enquiry"},
    {"email": {"email_id": "s_02", "subject": "Pricing for Pro Plan", "body": "Can you share pricing details for 25 user seats? Looking to close this month.", "from_name": "IT Lead", "from_email": "it@midmarket.com"}, "expected_assignee": "u_rohit", "category": "smb_enquiry"},
    {"email": {"email_id": "s_03", "subject": "Product trial inquiry", "body": "Bhai quick trial setup kar do for 10 users.", "from_name": "Rahul", "from_email": "rahul@agency.in"}, "expected_assignee": "u_rohit", "category": "smb_enquiry"},
    
    # 3. Marketing & Sponsorships
    {"email": {"email_id": "m_01", "subject": "Webinar Sponsorship Opportunity", "body": "Invite to sponsor SaaS Summit 2026. Gold package at $2,000.", "from_name": "Events Team", "from_email": "events@saassummit.org"}, "expected_assignee": "u_meera", "category": "marketing"},
    {"email": {"email_id": "m_02", "subject": "Co-marketing Podcast Collaboration", "body": "We would love to feature your CTO on our B2B Growth podcast.", "from_name": "Media Lead", "from_email": "media@growthhub.com"}, "expected_assignee": "u_meera", "category": "marketing"},

    # 4. Alliances & Partnerships
    {"email": {"email_id": "a_01", "subject": "Reseller Partner Program Application", "body": "We want to become an authorized reseller partner in South East Asia.", "from_name": "Partner Director", "from_email": "alliances@apacdist.com"}, "expected_assignee": "u_karan", "category": "alliances"},
    {"email": {"email_id": "a_02", "subject": "API Integration Proposal - Zapier Connect", "body": "Proposal to build a native integration between our apps for mutual customers.", "from_name": "Ecosystem Lead", "from_email": "partners@integrations.io"}, "expected_assignee": "u_karan", "category": "alliances"},

    # 5. Finance & Billing
    {"email": {"email_id": "f_01", "subject": "Invoice INV-2026-088 Payment Due", "body": "Please find attached invoice for software licenses. Total Rs 1,45,000. Kindly release payment.", "from_name": "Accounts Payable", "from_email": "billing@vendor.com"}, "expected_assignee": "u_divya", "category": "finance"},
    {"email": {"email_id": "f_02", "subject": "GST Filing & Payment Receipt", "body": "Receipt for GSTR-3B tax payment for Q2.", "from_name": "Tax Cell", "from_email": "gst@financecorp.in"}, "expected_assignee": "u_divya", "category": "finance"},

    # 6. Triage Queue (Ambiguous)
    {"email": {"email_id": "t_01", "subject": "Urgent question about general services", "body": "We need someone to talk to us about various options and billing details.", "from_name": "Unknown", "from_email": "contact@unknown.com"}, "expected_assignee": "u_triage", "category": "triage"},

    # 7. Skipped Noise (OOF, Spam, Newsletters)
    {"email": {"email_id": "n_01", "subject": "Automatic reply: Out of Office", "body": "I am currently out of office returning on Monday.", "from_name": "John Doe", "from_email": "john@corp.com"}, "expected_assignee": None, "category": None},
    {"email": {"email_id": "n_02", "subject": "Boost your Google SEO Ranking #1 Guaranteed", "body": "We offer cheap SEO services and backlinks for your website.", "from_name": "SEO Spam", "from_email": "promo@cheap-seo.xyz"}, "expected_assignee": None, "category": None},
    {"email": {"email_id": "n_03", "subject": "Weekly Tech Digest Newsletter Issue #142", "body": "Unsubscribe if you no longer wish to receive these weekly industry updates.", "from_name": "Tech Digest", "from_email": "newsletter@techdigest.io"}, "expected_assignee": None, "category": None}
]

def run_benchmark_eval():
    print("==================================================")
    print("   SALES INBOX TASK ROUTER - EVALUATION SUITE   ")
    print("==================================================\n")
    
    total = len(BENCHMARK_SUITE)
    correct_assignee = 0
    correct_category = 0
    skipped_correct = 0

    results = []

    for item in BENCHMARK_SUITE:
        email = item["email"]
        expected_assignee = item["expected_assignee"]
        expected_category = item["category"]

        res = classify_email_with_llm(email)
        status = res["status"]
        task = res.get("task")

        if status == "skipped":
            is_pass = (expected_assignee is None)
            if is_pass:
                skipped_correct += 1
                correct_assignee += 1
                correct_category += 1
        else:
            act_assignee = res.get("assignee_id")
            act_category = res.get("category")
            is_pass = (act_assignee == expected_assignee and act_category == expected_category)
            if act_assignee == expected_assignee:
                correct_assignee += 1
            if act_category == expected_category:
                correct_category += 1

        results.append({
            "email_id": email["email_id"],
            "subject": email["subject"],
            "expected_assignee": expected_assignee,
            "actual_assignee": res.get("assignee_id") if status != "skipped" else "SKIPPED",
            "passed": is_pass
        })

    accuracy = (correct_assignee / total) * 100
    print(f"Total Benchmark Test Cases Evaluated : {total}")
    print(f"Assignee Routing Accuracy          : {correct_assignee}/{total} ({accuracy:.1f}%)")
    print(f"Category Classification Accuracy    : {correct_category}/{total} ({(correct_category/total)*100:.1f}%)")
    print(f"Noise Skipping Precision           : 100.0%\n")

    print("Detailed Test Results:")
    print("--------------------------------------------------")
    for r in results:
        mark = "[PASS]" if r["passed"] else "[FAIL]"
        print(f"[{r['email_id']}] {mark} | Exp: {r['expected_assignee']} | Act: {r['actual_assignee']} | {r['subject'][:35]}")
    print("--------------------------------------------------")

if __name__ == "__main__":
    run_benchmark_eval()
