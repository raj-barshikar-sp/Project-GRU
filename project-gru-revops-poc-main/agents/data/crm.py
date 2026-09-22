"""In-memory CRM used by every mock tool.

Accounts, contacts, activities, and opportunities are hardcoded so agents
never call a live API. Lookups are case-insensitive and accept common aliases.
"""

from __future__ import annotations

from typing import Any

ACCOUNTS: dict[str, dict[str, Any]] = {
    "7-Eleven": {
        "account_id": "ACC-1007",
        "name": "7-Eleven",
        "legal_name": "7-Eleven, Inc.",
        "aliases": ["7 eleven", "seven eleven", "7-eleven inc", "7eleven"],
        "industry": "Convenience retail",
        "segment": "Enterprise",
        "hq": "Irving, TX",
        "employees": 145000,
        "annual_revenue": 89000000000,
        "website": "https://www.7-eleven.com",
        "owner": "Avery Cole",
        "health": "green",
        "open_pipeline": 2400000,
        "stage": "Proposal",
        "renewal_date": "2026-11-15",
        "products_in_use": ["StoreOps Analytics", "Inventory Sync"],
        "tech_stack": ["SAP", "NCR", "Microsoft 365"],
        "fiscal_year_end": "December",
        "notes": (
            "National convenience chain evaluating a POS + inventory modernization "
            "for corporate and franchise stores. Sensitive to franchisee rollout risk."
        ),
    },
    "Acme Corp": {
        "account_id": "ACC-2041",
        "name": "Acme Corp",
        "legal_name": "Acme Corporation",
        "aliases": ["acme", "acme corporation", "acme corp."],
        "industry": "Industrial manufacturing",
        "segment": "Mid-market",
        "hq": "Chicago, IL",
        "employees": 4200,
        "annual_revenue": 1800000000,
        "website": "https://www.acmecorp.example",
        "owner": "Jordan Patel",
        "health": "yellow",
        "open_pipeline": 640000,
        "stage": "Discovery",
        "renewal_date": "2027-03-01",
        "products_in_use": ["Quote-to-Cash"],
        "tech_stack": ["Oracle ERP", "Salesforce", "Okta"],
        "fiscal_year_end": "March",
        "notes": (
            "Discrete manufacturer consolidating quoting tools after a plant acquisition. "
            "CFO is the economic buyer; ops leaders are skeptical of another system."
        ),
    },
    "GlobalTech": {
        "account_id": "ACC-3318",
        "name": "GlobalTech",
        "legal_name": "GlobalTech Solutions LLC",
        "aliases": ["global tech", "globaltech solutions", "gt solutions"],
        "industry": "Enterprise software",
        "segment": "Enterprise",
        "hq": "Austin, TX",
        "employees": 8600,
        "annual_revenue": 2100000000,
        "website": "https://www.globaltech.example",
        "owner": "Sam Rivera",
        "health": "green",
        "open_pipeline": 1250000,
        "stage": "Negotiation",
        "renewal_date": "2026-09-30",
        "products_in_use": ["Partner Portal", "Revenue Insights"],
        "tech_stack": ["Workday", "Snowflake", "Slack"],
        "fiscal_year_end": "September",
        "notes": (
            "Closed a Series C last quarter. New CISO is rewriting vendor security "
            "questionnaires. Expansion into APAC partner portal seats is on the table."
        ),
    },
    "NovaPay": {
        "account_id": "ACC-4402",
        "name": "NovaPay",
        "legal_name": "NovaPay Financial, Inc.",
        "aliases": ["nova pay", "novapay financial"],
        "industry": "Fintech payments",
        "segment": "Mid-market",
        "hq": "San Francisco, CA",
        "employees": 980,
        "annual_revenue": 240000000,
        "website": "https://www.novapay.example",
        "owner": "Avery Cole",
        "health": "red",
        "open_pipeline": 180000,
        "stage": "Closed Lost recovery",
        "renewal_date": None,
        "products_in_use": [],
        "tech_stack": ["Stripe", "NetSuite", "Looker"],
        "fiscal_year_end": "December",
        "notes": (
            "Went dark after a failed Q4 evaluation. Controller changed. Last meaningful "
            "activity was 11 months ago. New Head of Partnerships just started."
        ),
    },
    "Meridian Health": {
        "account_id": "ACC-5570",
        "name": "Meridian Health",
        "legal_name": "Meridian Health System",
        "aliases": ["meridian", "meridian health system", "mhs"],
        "industry": "Healthcare",
        "segment": "Enterprise",
        "hq": "Cleveland, OH",
        "employees": 22000,
        "annual_revenue": 4700000000,
        "website": "https://www.meridianhealth.example",
        "owner": "Casey Nguyen",
        "health": "green",
        "open_pipeline": 3100000,
        "stage": "Technical validation",
        "renewal_date": "2026-12-01",
        "products_in_use": ["Care Coordination Hub"],
        "tech_stack": ["Epic", "Workday", "Azure"],
        "fiscal_year_end": "June",
        "notes": (
            "Regional health system running an EHR-adjacent analytics RFP. Privacy, BAA, "
            "and clinical workflow fit are the deal. CMIO is the champion."
        ),
    },
    "BrightLeaf Foods": {
        "account_id": "ACC-6611",
        "name": "BrightLeaf Foods",
        "legal_name": "BrightLeaf Foods Co.",
        "aliases": ["brightleaf", "bright leaf", "brightleaf foods co"],
        "industry": "Consumer packaged goods",
        "segment": "Mid-market",
        "hq": "Minneapolis, MN",
        "employees": 1900,
        "annual_revenue": 520000000,
        "website": "https://www.brightleaffoods.example",
        "owner": "Jordan Patel",
        "health": "yellow",
        "open_pipeline": 410000,
        "stage": "Evaluation",
        "renewal_date": "2027-01-12",
        "products_in_use": ["Trade Promotion"],
        "tech_stack": ["SAP", "Salesforce", "Tableau"],
        "fiscal_year_end": "January",
        "notes": (
            "CPG brand expanding club-store distribution. Trade spend visibility is the "
            "pain. Procurement wants a 3-year price lock."
        ),
    },
    "Helix Robotics": {
        "account_id": "ACC-7788",
        "name": "Helix Robotics",
        "legal_name": "Helix Robotics GmbH",
        "aliases": ["helix", "helix robotics gmbh"],
        "industry": "Industrial automation",
        "segment": "Growth",
        "hq": "Munich, Germany",
        "employees": 640,
        "annual_revenue": 110000000,
        "website": None,
        "owner": "Sam Rivera",
        "health": "yellow",
        "open_pipeline": 275000,
        "stage": "Qualification",
        "renewal_date": None,
        "products_in_use": [],
        "tech_stack": ["SAP B1", "HubSpot"],
        "fiscal_year_end": "December",
        "notes": (
            "German robotics OEM entering North America. Website field is blank in CRM. "
            "Two contact records exist for the same VP Sales."
        ),
    },
}

CONTACTS: dict[str, list[dict[str, Any]]] = {
    "7-Eleven": [
        {
            "contact_id": "CT-7001",
            "name": "Priya Nair",
            "title": "VP Procurement",
            "email": "priya.nair@7-eleven.example",
            "phone": "+1-972-555-0144",
            "role": "Economic buyer",
            "personality": "Direct, ROI-first, dislikes fluff",
            "linkedin": "linkedin.com/in/priya-nair-retail",
            "last_touch": "2026-08-02",
            "notes": "Asked for franchisee TCO model before any exec briefing.",
        },
        {
            "contact_id": "CT-7002",
            "name": "Marcus Chen",
            "title": "IT Director, Store Systems",
            "email": "marcus.chen@7-eleven.example",
            "phone": "+1-972-555-0190",
            "role": "Technical buyer",
            "personality": "Detail-oriented, worried about NCR coexistence",
            "linkedin": "linkedin.com/in/marcuschen-it",
            "last_touch": "2026-08-10",
            "notes": "Wants a sandbox against their inventory sync latency SLAs.",
        },
        {
            "contact_id": "CT-7003",
            "name": "Dana Lopez",
            "title": "Director of Store Operations",
            "email": "dana.lopez@7-eleven.example",
            "phone": "+1-972-555-0112",
            "role": "Champion",
            "personality": "Operator, story-driven, protective of store managers",
            "linkedin": "linkedin.com/in/dana-lopez-ops",
            "last_touch": "2026-07-28",
            "notes": "Shared a night-shift outage story; cares about training time.",
        },
        {
            "contact_id": "CT-7004",
            "name": "Bill Avery",
            "title": "Category Analyst",
            "email": "bill.avery@7-eleven.example",
            "phone": None,
            "role": "Influencer (stale)",
            "personality": "Unknown — record is old",
            "linkedin": None,
            "last_touch": "2022-11-04",
            "notes": "No activity since 2022. Title may be outdated.",
        },
    ],
    "Acme Corp": [
        {
            "contact_id": "CT-2041",
            "name": "Elena Vasquez",
            "title": "CFO",
            "email": "elena.vasquez@acmecorp.example",
            "phone": "+1-312-555-0108",
            "role": "Economic buyer",
            "personality": "Conservative, asks for payback in under 12 months",
            "linkedin": "linkedin.com/in/elena-vasquez-cfo",
            "last_touch": "2026-08-05",
            "notes": "Flagged integration cost as the reason the last vendor died.",
        },
        {
            "contact_id": "CT-2042",
            "name": "Rob Kim",
            "title": "Head of Sales Operations",
            "email": "rob.kim@acmecorp.example",
            "phone": "+1-312-555-0177",
            "role": "Champion",
            "personality": "Pragmatic, spreadsheet-native",
            "linkedin": "linkedin.com/in/robkim-salesops",
            "last_touch": "2026-08-12",
            "notes": "Sent their current CPQ export. Wants a side-by-side demo.",
        },
        {
            "contact_id": "CT-2043",
            "name": "Helen Cho",
            "title": "Plant Controller, Dayton",
            "email": "helen.cho@acmecorp.example",
            "phone": "+1-937-555-0160",
            "role": "User buyer",
            "personality": "Skeptical of HQ-led tools",
            "linkedin": "linkedin.com/in/helencho-finance",
            "last_touch": "2026-06-18",
            "notes": "Acquired plant still on a homegrown quoting workbook.",
        },
    ],
    "GlobalTech": [
        {
            "contact_id": "CT-3318",
            "name": "Amit Shah",
            "title": "CTO",
            "email": "amit.shah@globaltech.example",
            "phone": "+1-512-555-0133",
            "role": "Technical buyer",
            "personality": "Architecture-first, impatient with slides",
            "linkedin": "linkedin.com/in/amitshah-cto",
            "last_touch": "2026-08-08",
            "notes": "Requested SCIM + audit-log samples before legal review.",
        },
        {
            "contact_id": "CT-3319",
            "name": "Sarah Okonkwo",
            "title": "VP Partnerships",
            "email": "sarah.okonkwo@globaltech.example",
            "phone": "+1-512-555-0188",
            "role": "Champion / economic influencer",
            "personality": "Fast, expansion-minded, quota-driven",
            "linkedin": "linkedin.com/in/sarah-okonkwo",
            "last_touch": "2026-08-14",
            "notes": "Wants APAC partner seats live before Ignite in October.",
        },
        {
            "contact_id": "CT-3320",
            "name": "Nina Park",
            "title": "CISO",
            "email": "nina.park@globaltech.example",
            "phone": "+1-512-555-0121",
            "role": "Blocker / security",
            "personality": "New in seat, questionnaire-heavy",
            "linkedin": "linkedin.com/in/ninapark-ciso",
            "last_touch": "2026-07-30",
            "notes": "Joined after Series C. Rewrote the vendor security packet.",
        },
    ],
    "NovaPay": [
        {
            "contact_id": "CT-4402",
            "name": "Jordan Blake",
            "title": "Head of Partnerships",
            "email": "jordan.blake@novapay.example",
            "phone": "+1-415-555-0199",
            "role": "New champion",
            "personality": "Curious, not attached to prior evaluation",
            "linkedin": "linkedin.com/in/jordanblake-fintech",
            "last_touch": "2026-08-01",
            "notes": "Started 6 weeks ago. Asked for a 'clean slate' briefing.",
        },
        {
            "contact_id": "CT-4403",
            "name": "Mei Lin",
            "title": "Controller",
            "email": "mei.lin@novapay.example",
            "phone": "+1-415-555-0142",
            "role": "Finance",
            "personality": "Cautious, reconciliation-obsessed",
            "linkedin": "linkedin.com/in/meilin-finance",
            "last_touch": "2025-09-12",
            "notes": "Last evaluation stalled on payout reconciliation edge cases.",
        },
        {
            "contact_id": "CT-4404",
            "name": "Chris Dobbs",
            "title": "VP Product (former)",
            "email": "chris.dobbs@novapay.example",
            "phone": None,
            "role": "Stale",
            "personality": "Left the company",
            "linkedin": None,
            "last_touch": "2025-04-03",
            "notes": "Email bounces. Still marked active in CRM.",
        },
    ],
    "Meridian Health": [
        {
            "contact_id": "CT-5570",
            "name": "Dr. Alicia Grant",
            "title": "CMIO",
            "email": "alicia.grant@meridianhealth.example",
            "phone": "+1-216-555-0101",
            "role": "Champion",
            "personality": "Clinical, evidence-based, allergic to buzzwords",
            "linkedin": "linkedin.com/in/aliciagrant-md",
            "last_touch": "2026-08-11",
            "notes": "Wants a 30-minute workflow walkthrough with nursing informatics.",
        },
        {
            "contact_id": "CT-5571",
            "name": "Tom Bradley",
            "title": "Director, Supply Chain",
            "email": "tom.bradley@meridianhealth.example",
            "phone": "+1-216-555-0166",
            "role": "Economic influencer",
            "personality": "Contract-savvy, GPO-aware",
            "linkedin": "linkedin.com/in/tombradley-sc",
            "last_touch": "2026-08-06",
            "notes": "Asked whether pricing can ride their Vizient GPO.",
        },
        {
            "contact_id": "CT-5572",
            "name": "Keisha Ward",
            "title": "Privacy Officer",
            "email": "keisha.ward@meridianhealth.example",
            "phone": "+1-216-555-0180",
            "role": "Legal / privacy",
            "personality": "BAA-or-bust",
            "linkedin": "linkedin.com/in/keishaward-privacy",
            "last_touch": "2026-07-22",
            "notes": "Will block any demo environment that is not BAA-covered.",
        },
    ],
    "BrightLeaf Foods": [
        {
            "contact_id": "CT-6611",
            "name": "Luis Ortega",
            "title": "VP Revenue Growth Management",
            "email": "luis.ortega@brightleaf.example",
            "phone": "+1-612-555-0130",
            "role": "Champion",
            "personality": "Numbers-forward, retailer-relationship focused",
            "linkedin": "linkedin.com/in/luisortega-rgm",
            "last_touch": "2026-08-09",
            "notes": "Club-store expansion is the 2026 OKR. Needs lift vs. spend.",
        },
        {
            "contact_id": "CT-6612",
            "name": "Hannah Berg",
            "title": "Director of Procurement",
            "email": "hannah.berg@brightleaf.example",
            "phone": "+1-612-555-0171",
            "role": "Procurement",
            "personality": "Wants a 3-year lock and audit rights",
            "linkedin": "linkedin.com/in/hannahberg-proc",
            "last_touch": "2026-07-15",
            "notes": "Comparing three vendors. Price is her primary lever.",
        },
    ],
    "Helix Robotics": [
        {
            "contact_id": "CT-7788",
            "name": "Lena Vogt",
            "title": "VP Sales, Americas",
            "email": "lena.vogt@helix-robotics.example",
            "phone": "+49-89-555-010",
            "role": "Champion",
            "personality": "Builder, time-zone stretched, wants a US playbook",
            "linkedin": "linkedin.com/in/lenavogt",
            "last_touch": "2026-08-04",
            "notes": "Duplicate of CT-7789. Prefers email over calls before 15:00 CET.",
        },
        {
            "contact_id": "CT-7789",
            "name": "Lena Vogt",
            "title": "Vice President of Sales (Americas)",
            "email": "l.vogt@helixrobotics.example",
            "phone": "+1-617-555-0144",
            "role": "Duplicate of CT-7788",
            "personality": "Same person, US number",
            "linkedin": "linkedin.com/in/lenavogt",
            "last_touch": "2026-05-20",
            "notes": "Created by inbound form. Should be merged into CT-7788.",
        },
        {
            "contact_id": "CT-7790",
            "name": "Felix Krüger",
            "title": "CFO",
            "email": "felix.krueger@helix-robotics.example",
            "phone": "+49-89-555-022",
            "role": "Economic buyer",
            "personality": "Conservative, FX-aware, prefers EUR quotes",
            "linkedin": "linkedin.com/in/felix-krueger-cfo",
            "last_touch": "2026-06-02",
            "notes": "Asked for a EUR price list and data residency in Frankfurt.",
        },
    ],
}

INTERACTIONS: dict[str, list[dict[str, Any]]] = {
    "7-Eleven": [
        {
            "date": "2026-08-10",
            "type": "call",
            "who": "Marcus Chen",
            "summary": "Technical deep-dive on inventory sync latency and NCR coexistence.",
        },
        {
            "date": "2026-08-02",
            "type": "email",
            "who": "Priya Nair",
            "summary": "Requested franchisee TCO model and a 50-store pilot scope.",
        },
        {
            "date": "2026-07-28",
            "type": "meeting",
            "who": "Dana Lopez",
            "summary": "Store ops working session. Night-shift outage story. Training time is a hard constraint.",
        },
        {
            "date": "2026-06-12",
            "type": "qbr",
            "who": "Priya Nair, Dana Lopez",
            "summary": "QBR on StoreOps Analytics. Renewal healthy. Expansion flagged for POS.",
        },
        {
            "date": "2026-05-03",
            "type": "support",
            "who": "Marcus Chen",
            "summary": "P2 ticket: inventory sync delayed 14 minutes during a promo weekend. Resolved.",
        },
    ],
    "Acme Corp": [
        {
            "date": "2026-08-12",
            "type": "email",
            "who": "Rob Kim",
            "summary": "Sent CPQ export and asked for a side-by-side quoting demo.",
        },
        {
            "date": "2026-08-05",
            "type": "call",
            "who": "Elena Vasquez",
            "summary": "CFO wants 12-month payback. Integration cost killed the last vendor.",
        },
        {
            "date": "2026-06-18",
            "type": "site visit",
            "who": "Helen Cho",
            "summary": "Dayton plant still quoting in a shared workbook. Data quality is uneven.",
        },
    ],
    "GlobalTech": [
        {
            "date": "2026-08-14",
            "type": "call",
            "who": "Sarah Okonkwo",
            "summary": "APAC partner seats needed before October Ignite. Commercial paper in flight.",
        },
        {
            "date": "2026-08-08",
            "type": "email",
            "who": "Amit Shah",
            "summary": "Asked for SCIM examples, audit logs, and a 99.9% SLA redline.",
        },
        {
            "date": "2026-07-30",
            "type": "meeting",
            "who": "Nina Park",
            "summary": "New CISO kicked off a full security questionnaire rewrite.",
        },
        {
            "date": "2026-04-18",
            "type": "news",
            "who": "Company",
            "summary": "Series C announced. Hiring freeze lifted for GTM and security.",
        },
    ],
    "NovaPay": [
        {
            "date": "2026-08-01",
            "type": "email",
            "who": "Jordan Blake",
            "summary": "New Head of Partnerships asked for a clean-slate briefing. No commitment yet.",
        },
        {
            "date": "2025-09-12",
            "type": "demo",
            "who": "Mei Lin",
            "summary": "Evaluation stalled on payout reconciliation edge cases. No follow-up since.",
        },
        {
            "date": "2025-04-03",
            "type": "email",
            "who": "Chris Dobbs",
            "summary": "Last note from former VP Product. Email now bounces.",
        },
    ],
    "Meridian Health": [
        {
            "date": "2026-08-11",
            "type": "meeting",
            "who": "Dr. Alicia Grant",
            "summary": "CMIO requested a nursing-informatics workflow walkthrough next week.",
        },
        {
            "date": "2026-08-06",
            "type": "call",
            "who": "Tom Bradley",
            "summary": "Supply chain asked if pricing can ride the Vizient GPO.",
        },
        {
            "date": "2026-07-22",
            "type": "email",
            "who": "Keisha Ward",
            "summary": "Privacy: demo environment must be BAA-covered. No PHI in logs.",
        },
        {
            "date": "2026-07-01",
            "type": "rfp",
            "who": "Procurement",
            "summary": "EHR-adjacent analytics RFP released. Responses due 2026-09-05.",
        },
    ],
    "BrightLeaf Foods": [
        {
            "date": "2026-08-09",
            "type": "call",
            "who": "Luis Ortega",
            "summary": "Club-store expansion OKR. Needs lift vs. trade spend in one view.",
        },
        {
            "date": "2026-07-15",
            "type": "meeting",
            "who": "Hannah Berg",
            "summary": "Procurement bake-off. Three vendors. Asked for 3-year price lock.",
        },
        {
            "date": "2026-05-21",
            "type": "webinar",
            "who": "Luis Ortega",
            "summary": "Attended CPG trade-promotion webinar. Downloaded ROI calculator.",
        },
    ],
    "Helix Robotics": [
        {
            "date": "2026-08-04",
            "type": "email",
            "who": "Lena Vogt",
            "summary": "Asked for a North America sales playbook and a EUR quote for finance.",
        },
        {
            "date": "2026-06-02",
            "type": "call",
            "who": "Felix Krüger",
            "summary": "CFO wants Frankfurt data residency and EUR list pricing.",
        },
        {
            "date": "2026-05-20",
            "type": "inbound",
            "who": "Lena Vogt",
            "summary": "Website form created duplicate contact CT-7789.",
        },
    ],
}

OPPORTUNITIES: dict[str, list[dict[str, Any]]] = {
    "7-Eleven": [
        {
            "opp_id": "OPP-711",
            "name": "POS + inventory modernization",
            "amount": 2400000,
            "stage": "Proposal",
            "close_date": "2026-10-30",
            "type": "Expansion",
        }
    ],
    "Acme Corp": [
        {
            "opp_id": "OPP-241",
            "name": "Quote-to-Cash consolidation",
            "amount": 640000,
            "stage": "Discovery",
            "close_date": "2026-12-15",
            "type": "New",
        }
    ],
    "GlobalTech": [
        {
            "opp_id": "OPP-318",
            "name": "APAC partner portal seats",
            "amount": 1250000,
            "stage": "Negotiation",
            "close_date": "2026-09-20",
            "type": "Expansion",
        }
    ],
    "NovaPay": [
        {
            "opp_id": "OPP-402",
            "name": "Payout ops restart",
            "amount": 180000,
            "stage": "Closed Lost recovery",
            "close_date": "2026-11-01",
            "type": "New",
        }
    ],
    "Meridian Health": [
        {
            "opp_id": "OPP-570",
            "name": "Care analytics RFP",
            "amount": 3100000,
            "stage": "Technical validation",
            "close_date": "2026-11-15",
            "type": "Expansion",
        }
    ],
    "BrightLeaf Foods": [
        {
            "opp_id": "OPP-611",
            "name": "Trade promotion intelligence",
            "amount": 410000,
            "stage": "Evaluation",
            "close_date": "2026-10-15",
            "type": "Expansion",
        }
    ],
    "Helix Robotics": [
        {
            "opp_id": "OPP-788",
            "name": "Americas GTM system",
            "amount": 275000,
            "stage": "Qualification",
            "close_date": "2026-12-01",
            "type": "New",
        }
    ],
}

DATA_QUALITY: dict[str, dict[str, Any]] = {
    "7-Eleven": {
        "duplicates": [
            {
                "records": ["7-Eleven, Inc.", "7 Eleven"],
                "type": "account",
                "confidence": 0.94,
                "reason": "Same EIN hint, different punctuation and legal suffix.",
            }
        ],
        "missing_fields": ["billing_street", "parent_account", "franchise_count"],
        "stale_records": [
            {
                "record": "Bill Avery — Category Analyst",
                "last_activity": "2022-11-04",
                "reason": "No activity in 1,000+ days; phone blank.",
            }
        ],
        "issues": ["Duplicate account name variants", "Stale influencer contact"],
    },
    "Acme Corp": {
        "duplicates": [],
        "missing_fields": ["sic_code"],
        "stale_records": [],
        "issues": ["SIC code blank — otherwise clean"],
    },
    "GlobalTech": {
        "duplicates": [
            {
                "records": ["GlobalTech", "Global Tech Solutions"],
                "type": "account",
                "confidence": 0.91,
                "reason": "Matching domain and HQ city; extra 'Solutions' legal name.",
            }
        ],
        "missing_fields": ["duns_number"],
        "stale_records": [],
        "issues": ["Account duplicate from a list import after Series C"],
    },
    "NovaPay": {
        "duplicates": [],
        "missing_fields": ["renewal_date", "website_verified", "champion_status"],
        "stale_records": [
            {
                "record": "Chris Dobbs — VP Product",
                "last_activity": "2025-04-03",
                "reason": "Email bounces; still Active.",
            },
            {
                "record": "Account activity",
                "last_activity": "2025-09-12",
                "reason": "No opportunity movement in 11 months before the August restart.",
            },
        ],
        "issues": ["Bounced executive still active", "Long inactivity window"],
    },
    "Meridian Health": {
        "duplicates": [],
        "missing_fields": ["npi_organization", "baa_signed_date"],
        "stale_records": [],
        "issues": ["Healthcare identifiers incomplete; BAA date not stamped"],
    },
    "BrightLeaf Foods": {
        "duplicates": [],
        "missing_fields": ["parent_account", "naics"],
        "stale_records": [
            {
                "record": "Legacy trade-spend spreadsheet link",
                "last_activity": "2024-12-02",
                "reason": "Attachment URL 404s.",
            }
        ],
        "issues": ["Broken artifact link on the account"],
    },
    "Helix Robotics": {
        "duplicates": [
            {
                "records": ["Lena Vogt CT-7788", "Lena Vogt CT-7789"],
                "type": "contact",
                "confidence": 0.97,
                "reason": "Same LinkedIn, two emails, DE + US phone.",
            }
        ],
        "missing_fields": ["website", "billing_country", "employees_verified"],
        "stale_records": [],
        "issues": ["Website blank", "Duplicate VP Sales contact"],
    },
}

LEAD_SCORES: dict[str, dict[str, Any]] = {
    "7-Eleven": {
        "fit_score": 90,
        "engagement_score": 78,
        "trigger_score": 72,
        "score": 82,
        "tier": "A",
        "territory": "central",
        "reasoning": (
            "Enterprise convenience retailer with a live $2.4M expansion, an operator "
            "champion, and a defined pilot. Fit is excellent; engagement is strong after "
            "the August technical call."
        ),
        "trigger_events": [
            {
                "event": "Franchise POS RFP language circulating internally",
                "date": "2026-08-02",
                "impact": "high",
            },
            {
                "event": "EV charging partnership announced — more store systems load",
                "date": "2026-07-09",
                "impact": "medium",
            },
        ],
    },
    "Acme Corp": {
        "fit_score": 74,
        "engagement_score": 55,
        "trigger_score": 48,
        "score": 61,
        "tier": "B",
        "territory": "central",
        "reasoning": (
            "Solid manufacturing fit and a CFO conversation, but still early discovery "
            "with a skeptical plant controller. Payback pressure keeps the score mid-pack."
        ),
        "trigger_events": [
            {
                "event": "Dayton plant acquisition integration (quoting still on workbooks)",
                "date": "2026-03-01",
                "impact": "high",
            }
        ],
    },
    "GlobalTech": {
        "fit_score": 88,
        "engagement_score": 81,
        "trigger_score": 85,
        "score": 84,
        "tier": "A",
        "territory": "south",
        "reasoning": (
            "Late-stage expansion with a date-driven event (Ignite) and fresh capital. "
            "New CISO adds friction but also a forcing function to finish security review."
        ),
        "trigger_events": [
            {"event": "Series C closed", "date": "2026-04-18", "impact": "high"},
            {"event": "New CISO hired", "date": "2026-07-01", "impact": "high"},
            {"event": "Ignite conference in October", "date": "2026-10-12", "impact": "medium"},
        ],
    },
    "NovaPay": {
        "fit_score": 62,
        "engagement_score": 28,
        "trigger_score": 54,
        "score": 45,
        "tier": "C",
        "territory": "west",
        "reasoning": (
            "Fintech fit is real, but eleven months of silence and a bounced exec keep "
            "engagement low. The new Head of Partnerships is the only positive trigger."
        ),
        "trigger_events": [
            {
                "event": "New Head of Partnerships started",
                "date": "2026-06-20",
                "impact": "high",
            }
        ],
    },
    "Meridian Health": {
        "fit_score": 92,
        "engagement_score": 80,
        "trigger_score": 90,
        "score": 88,
        "tier": "A",
        "territory": "central",
        "reasoning": (
            "Live RFP, CMIO champion, and a $3.1M expansion. Healthcare compliance is a "
            "hurdle, not a fit gap. Highest-priority account in the book."
        ),
        "trigger_events": [
            {
                "event": "EHR-adjacent analytics RFP released",
                "date": "2026-07-01",
                "impact": "high",
            },
            {
                "event": "Board-level digital quality initiative",
                "date": "2026-05-15",
                "impact": "medium",
            },
        ],
    },
    "BrightLeaf Foods": {
        "fit_score": 76,
        "engagement_score": 64,
        "trigger_score": 70,
        "score": 70,
        "tier": "B",
        "territory": "central",
        "reasoning": (
            "CPG trade-spend use case matches the product. Competitive bake-off and a "
            "procurement-led 3-year lock request cap the score below A."
        ),
        "trigger_events": [
            {
                "event": "Club-store distribution expansion OKR",
                "date": "2026-01-10",
                "impact": "high",
            }
        ],
    },
    "Helix Robotics": {
        "fit_score": 58,
        "engagement_score": 50,
        "trigger_score": 66,
        "score": 55,
        "tier": "B",
        "territory": "east",
        "reasoning": (
            "Growth-stage OEM entering North America is a classic land-and-expand, but "
            "CRM hygiene is weak and the deal is still in qualification. Data residency "
            "in Frankfurt is a must-win technical item."
        ),
        "trigger_events": [
            {
                "event": "Americas market entry / VP Sales hired",
                "date": "2026-04-01",
                "impact": "high",
            }
        ],
    },
}

TALKING_POINTS: dict[str, dict[str, Any]] = {
    "7-Eleven": {
        "talking_points": [
            "Open with Dana's night-shift outage: frame POS + inventory as store-manager time back, not another console.",
            "Walk Priya through a 50-store franchisee TCO, including training hours and a rollback plan.",
            "Show Marcus a coexistence diagram with NCR and the 14-minute sync incident as the before/after.",
            "Propose a Labor Day weekend tabletop for promo-spike latency.",
        ],
        "objections": [
            {
                "objection": "Franchisees will not sit through a long training.",
                "response": "Offer a 20-minute shift-huddle module and a store-champion model.",
            },
            {
                "objection": "We cannot rip out NCR.",
                "response": "Position as a sidecar with a 90-day coexistence SLA, not a rip-and-replace.",
            },
        ],
        "recommended_content": [
            "Franchise TCO one-pager",
            "Inventory sync incident postmortem (anonymized)",
            "50-store pilot statement of work",
        ],
    },
    "Acme Corp": {
        "talking_points": [
            "Lead with 12-month payback using Rob's CPQ export, not a platform tour.",
            "Call out Dayton's workbook risk: dual quoting after the acquisition.",
            "Offer a plant-level sandbox so Helen is not asked to trust HQ blindly.",
        ],
        "objections": [
            {
                "objection": "Last vendor died on integration cost.",
                "response": "Fixed-price Oracle connector, capped professional services, written in the proposal.",
            },
            {
                "objection": "Plant teams will ignore another system.",
                "response": "Start with Dayton only; success metric is quote cycle time, not licenses.",
            },
        ],
        "recommended_content": [
            "Manufacturing quote-cycle benchmark",
            "Oracle ERP connector architecture brief",
            "12-month payback model template",
        ],
    },
    "GlobalTech": {
        "talking_points": [
            "Anchor on Ignite: APAC seats live or they demo a gap on stage.",
            "Hand Amit SCIM + audit-log samples in the first five minutes.",
            "Treat Nina as a co-owner: offer a security working session, not a sales deck.",
        ],
        "objections": [
            {
                "objection": "New CISO will slow everything down.",
                "response": "Pre-filled questionnaire plus a 48-hour architecture review with our CISO.",
            },
            {
                "objection": "APAC data residency.",
                "response": "Singapore region is already in the expansion SKU; put it in the order form.",
            },
        ],
        "recommended_content": [
            "SCIM implementation notes",
            "APAC order-form addendum",
            "Ignite launch checklist",
        ],
    },
    "NovaPay": {
        "talking_points": [
            "Do not relitigate 2025. Jordan was not in the room — give a clean-slate 20-minute briefing.",
            "Name the payout reconciliation edge cases unprompted; show the fix in product.",
            "Ask who owns the bounced Chris Dobbs record so the book is trustworthy.",
        ],
        "objections": [
            {
                "objection": "We already evaluated you and it failed.",
                "response": "Acknowledge it. Show the reconciliation release notes from 2026 and a reference in payments ops.",
            },
            {
                "objection": "We have no budget this quarter.",
                "response": "Propose a paid diagnostic on one payout rail, not a platform buy.",
            },
        ],
        "recommended_content": [
            "2026 reconciliation release notes",
            "Fintech payout reference story",
            "Paid diagnostic one-pager",
        ],
    },
    "Meridian Health": {
        "talking_points": [
            "Open with the RFP date (Sep 5) and the nursing-informatics walkthrough Alicia asked for.",
            "Lead with BAA-covered demo environments before any screenshot of a patient list.",
            "Have GPO/Vizient language ready for Tom — do not improvise discounting.",
        ],
        "objections": [
            {
                "objection": "PHI cannot touch a vendor cloud.",
                "response": "BAA, Azure US regions, no PHI in logs, and a documented data-flow diagram.",
            },
            {
                "objection": "Clinicians will not change workflow.",
                "response": "Epic-adjacent, not Epic-replacing. Show the two-click in-basket path.",
            },
        ],
        "recommended_content": [
            "BAA template and data-flow diagram",
            "Nursing informatics workflow script",
            "RFP response outline mapped to their sections",
        ],
    },
    "BrightLeaf Foods": {
        "talking_points": [
            "Connect club-store OKRs to lift vs. spend in one view — Luis's exact ask.",
            "Give Hannah a 3-year commercial option and a 12-month opt-out so she can close internally.",
            "Bring a retailer-ready promo calendar sample, not a generic dashboard.",
        ],
        "objections": [
            {
                "objection": "Three vendors already in a bake-off.",
                "response": "Win on time-to-first-insight using their last quarter's promo file, not feature count.",
            },
            {
                "objection": "We need a 3-year price lock.",
                "response": "Offer it with a usage collar; put the collar in writing before procurement asks.",
            },
        ],
        "recommended_content": [
            "CPG lift-vs-spend sample pack",
            "3-year commercial option sheet",
            "Club-store promo calendar template",
        ],
    },
    "Helix Robotics": {
        "talking_points": [
            "Help Lena with a 90-day Americas playbook: territories, CRM hygiene, and a first logo motion.",
            "Quote Felix in EUR and put Frankfurt residency on page one.",
            "Ask to merge the duplicate Lena records live — it builds trust.",
        ],
        "objections": [
            {
                "objection": "We need EU data residency.",
                "response": "Frankfurt region is available; add it as a contractual exhibit.",
            },
            {
                "objection": "We are too early for a full platform.",
                "response": "Land on CRM hygiene + pipeline for Americas, expand after the first three logos.",
            },
        ],
        "recommended_content": [
            "EUR price list",
            "Frankfurt residency exhibit",
            "90-day Americas GTM checklist",
        ],
    },
}

def _territories() -> dict[str, list[str]]:
    """Build geo → account lists from dummy_data/account.json."""
    from agents.data.dummy_store import dummy_tables_ready, load_accounts

    if dummy_tables_ready():
        by_geo: dict[str, list[str]] = {}
        names: list[str] = []
        for row in load_accounts():
            geo = str(row["geo"]).strip().lower()
            name = str(row["account"])
            by_geo.setdefault(geo, []).append(name)
            names.append(name)
        by_geo["all"] = names
        return by_geo
    names = list(ACCOUNTS)
    return {"all": names}


TERRITORIES: dict[str, list[str]] = _territories()


def _normalize(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def resolve_account(account_name: str) -> str | None:
    """Return the canonical account name, or None if unknown."""
    needle = _normalize(account_name)
    if not needle:
        return None
    for canonical, record in ACCOUNTS.items():
        candidates = [canonical, record.get("legal_name", ""), *record.get("aliases", [])]
        if any(_normalize(str(candidate)) == needle for candidate in candidates if candidate):
            return canonical
        if len(needle) >= 4 and needle in _normalize(canonical):
            return canonical
    return None


def list_accounts() -> list[str]:
    return list(ACCOUNTS.keys())
