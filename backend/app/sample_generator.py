import json
import random
import datetime

COMPANY_DOMAINS = [
    ("Meridian Steel Pvt Ltd", "meridiansteel.co.in"),
    ("Railyard Logistics", "railyardlogistics.in"),
    ("Bharat Heavy Electricals Limited", "bhel.in"),
    ("India SaaS Summit", "saassummit.in"),
    ("Vantage Cloud Services", "vantagecloud.com"),
    ("Zenith Cloud Partners", "zenithpartners.io"),
    ("Halcyon Retail", "halcyonretail.com"),
    ("Northbridge Solutions", "northbridge.in"),
    ("TechPulse Media", "techpulse.io"),
    ("Apex Dynamics", "apexdynamics.co.in")
]

FIRST_NAMES = ["Suresh", "Ankit", "Nandita", "Farhan", "Raghav", "Priya", "Amit", "Sneha", "Vikram", "Rohan", "Kavita", "Deepak"]
LAST_NAMES = ["Kulkarni", "Bose", "Reddy", "Qureshi", "Sharma", "Iyer", "Verma", "Mehta", "Patel", "Joshi", "Deshmukh", "Nair"]

def generate_sample_emails(count: int = 250) -> list:
    emails = []
    start_date = datetime.datetime(2026, 8, 1, 9, 0, 0)

    # Core templates representing each category and edge case
    templates = [
        # 1. Enterprise RFP
        {
            "category": "enterprise_rfp",
            "subject": "RFP - Enterprise Document Management System",
            "body": "Meridian Steel invites proposals for an enterprise DMS covering 4 plants and ~1,200 users. Indicative budget is Rs. 25 lakhs. Proposals must reach us by 12th August 2026.",
            "is_reply": False,
            "attachments": ["RFP_DMS_2026.pdf"]
        },
        # 2. SMB Demo
        {
            "category": "smb_enquiry",
            "subject": "Quick demo request",
            "body": "Hi, we're a 30-person logistics startup in Pune... can we get a demo sometime next week? Nothing urgent. — Ankit Bose, Founder, Railyard Logistics",
            "is_reply": False,
            "attachments": []
        },
        # 3. PSU Tender (Rule 3)
        {
            "category": "psu_tender",
            "subject": "Tender Notice BHEL/PROC/2026/0847",
            "body": "Tender Notice No. BHEL/PROC/2026/0847. Bharat Heavy Electricals Limited invites bids for supply of analytics software licences. Estimated value: Rs. 6,50,000. Last date for bid submission: 03-08-2026, 1700 hrs IST.",
            "is_reply": False,
            "attachments": ["Tender_BHEL_2026.pdf"]
        },
        # 4. Marketing Sponsorship
        {
            "category": "marketing",
            "subject": "Sponsorship confirmation needed",
            "body": "We're finalising sponsors for the India SaaS Summit in Bengaluru. Gold tier is ₹4,00,000 and includes a keynote slot. We need confirmation by tomorrow EOD as we're going to print. — Nandita Reddy, Sponsorship Lead",
            "is_reply": False,
            "attachments": ["Sponsorship_Deck.pdf"]
        },
        # 5. Finance / Invoice
        {
            "category": "finance",
            "subject": "Invoice INV-2026-0331 for processing",
            "body": "Please find attached invoice INV-2026-0331 for Rs. 1,18,000 (incl. 18% GST) against PO-88214. Kindly process — payment terms were Net 30 and this is now 12 days overdue. Also, our GSTIN has changed, updated details attached.",
            "is_reply": False,
            "attachments": ["INV-2026-0331.pdf"]
        },
        # 6. Alliances
        {
            "category": "alliances",
            "subject": "Partnership Exploration - Salesforce Partner",
            "body": "We're a Salesforce implementation partner across MEA with 40+ enterprise clients. We'd like to explore reselling your platform in the region, or a technical integration at minimum. Who handles partnerships?",
            "is_reply": False,
            "attachments": []
        },
        # 7. Out of office (Noise)
        {
            "category": "oof",
            "subject": "Out of Office: Limited access to email",
            "body": "I am out of office until 14th August with limited access to email. For urgent matters please contact my colleague at raghav@northbridge.in. — Sent from Outlook",
            "is_reply": False,
            "attachments": []
        },
        # 8. Vendor SEO Spam (Noise)
        {
            "category": "spam",
            "subject": "Organic Traffic Growth & SEO Audit",
            "body": "Hi, I noticed your website isn't ranking on page 1 for key terms. We've helped 200+ SaaS companies 3x their organic traffic. We do content marketing, PR outreach, and webinar promotion. Free audit attached — interested in a quick 15 min call?",
            "is_reply": False,
            "attachments": ["SEO_Audit_Report.pdf"]
        },
        # 9. Newsletter (Noise)
        {
            "category": "newsletter",
            "subject": "The B2B Growth Weekly — Issue #212",
            "body": "The B2B Growth Weekly — Issue #212. In this edition: why PLG is stalling, 5 pricing experiments that worked, and a teardown of Figma's onboarding. [Unsubscribe]",
            "is_reply": False,
            "attachments": []
        },
        # 10. Ambiguous / Triage
        {
            "category": "triage",
            "subject": "Meeting follow-up & potential collaboration",
            "body": "Hi — we met at your booth in Mumbai. Two things: (1) we'd like to evaluate your platform for our 800-person org, budget TBD but likely significant, and (2) our CMO wants to co-host a webinar with your team in September. Can you loop in the right people? — Farhan Qureshi, VP Strategy, Halcyon Retail",
            "is_reply": False,
            "attachments": []
        },
        # 11. Hinglish Shorthand
        {
            "category": "hinglish",
            "subject": "Product requirement for dealer network",
            "body": "Bhai, humko aapka product chahiye for our dealer network. Around 150 users honge. Budget approx 1.2 cr allocated hai for this FY. Kab connect kar sakte hain? Thoda jaldi, board review 20th ko hai.",
            "is_reply": False,
            "attachments": []
        }
    ]

    thread_counter = 1
    for i in range(count):
        tpl = random.choice(templates)
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        c_name, domain = random.choice(COMPANY_DOMAINS)
        
        email_id = f"em_{i+1:05d}"
        
        # Decide if this is a reply to a previous thread
        is_reply = (i > 15 and random.random() < 0.20)
        if is_reply:
            thread_id = f"th_{random.randint(1, thread_counter):04d}"
            subject = f"Re: {tpl['subject']}"
            body = f"Correction to our earlier note — please find updated details below.\n\nOn 2026-08-01, {fn} wrote:\n> {tpl['body']}"
            msg_idx = random.randint(1, 3)
        else:
            thread_counter += 1
            thread_id = f"th_{thread_counter:04d}"
            subject = tpl['subject']
            body = tpl['body']
            msg_idx = 0

        # Increment date
        rec_time = start_date + datetime.timedelta(hours=i*2, minutes=random.randint(0, 59))
        
        email_obj = {
            "email_id": email_id,
            "thread_id": thread_id,
            "message_index": msg_idx,
            "from_name": f"{fn} {ln}",
            "from_email": f"{fn.lower()}.{ln.lower()}@{domain}",
            "to": "sales@company.com",
            "cc": [f"info@{domain}"] if random.random() > 0.5 else [],
            "subject": subject,
            "body": body,
            "received_at": rec_time.isoformat() + "+05:30",
            "attachments": tpl["attachments"],
            "is_reply": is_reply
        }
        emails.append(email_obj)

    return emails
