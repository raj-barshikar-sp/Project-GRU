"""Builds the sample dataset the whole system runs on.

This is deliberately not random filler. A demo is only convincing if the agents
find something worth saying, so several stories are planted on purpose:

  1. EMEA pipeline coverage sits below the 2x target while AMER and APJ are fine.
  2. Eight EMEA accounts with no opportunity are clustered in Munich and
     Frankfurt and all surging on Zero Trust keywords, so the events agent has
     an obvious city and topic to recommend. A weaker Singapore/SASE cluster
     exists too, so it has to pick rather than just report the only option.
  3. "Zero Trust Maturity Guide" correlates strongly with opportunity
     progression; "Company Overview Brochure" is consumed widely and correlates
     with nothing. The asset influence agent should separate them.
  4. Six large deals are stalled: over 60 days old and unmoved for a week.
  5. Paid Social has a terrible cost per opportunity and the Zero Trust webinar
     an excellent one, so the recommendation agent has a real budget shift to
     argue for.
  6. A Munich roundtable has attendees carrying genuine open pipeline.

Run: python scripts/generate_fixtures.py
"""

from __future__ import annotations

import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from mktg_core.contracts import AS_OF, CampaignType, OppStage, Region  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "dummy_data"
RNG = random.Random(7)

# The current operating user. Wherever the system needs "me", "my accounts" or a
# campaign owner, this is who it means.
ME = {
    "name": "Omkar",
    "full_name": "Omkar Patil",
    "title": "Senior Marketing Manager",
    "email": "omkar.patil@sailpoint.com",
    "region": "EMEA",
    "team": "Marketing",
}

CITIES = {
    Region.AMER: ["San Francisco", "New York", "Chicago", "Austin", "Boston", "Toronto"],
    Region.EMEA: ["London", "Munich", "Frankfurt", "Paris", "Amsterdam", "Dublin"],
    Region.APJ: ["Singapore", "Sydney", "Tokyo", "Bangalore"],
}
COUNTRY_OF_CITY = {
    "San Francisco": "United States", "New York": "United States",
    "Chicago": "United States", "Austin": "United States",
    "Boston": "United States", "Toronto": "Canada",
    "London": "United Kingdom", "Munich": "Germany", "Frankfurt": "Germany",
    "Paris": "France", "Amsterdam": "Netherlands", "Dublin": "Ireland",
    "Singapore": "Singapore", "Sydney": "Australia", "Tokyo": "Japan",
    "Bangalore": "India",
}
INDUSTRIES = [
    "Financial Services", "Technology", "Healthcare",
    "Manufacturing", "Retail", "Public Sector",
]
PREFIXES = [
    "Northwind", "Vertex", "Lumen", "Ardent", "Kestrel", "Bluepeak", "Ironwood",
    "Solstice", "Halcyon", "Meridian", "Cobalt", "Falcon", "Granite", "Harbour",
    "Juniper", "Larkspur", "Monarch", "Nimbus", "Orchid", "Pinnacle", "Quarry",
    "Redstone", "Sable", "Thorne", "Umbra", "Vantage", "Westfield", "Yarrow",
    "Zephyr", "Alder", "Brightwater", "Cinder", "Dovetail", "Ember", "Fairmont",
    "Glenmore", "Hollis", "Ivywood", "Jasper", "Kirkland", "Longview", "Mistral",
]
SUFFIX_BY_INDUSTRY = {
    "Financial Services": ["Capital", "Financial", "Bank Group", "Partners"],
    "Technology": ["Systems", "Labs", "Software", "Digital"],
    "Healthcare": ["Health", "Medical Group", "Care", "Biosciences"],
    "Manufacturing": ["Industries", "Manufacturing", "Works", "Components"],
    "Retail": ["Retail Group", "Stores", "Commerce", "Brands"],
    "Public Sector": ["Authority", "Council", "Agency", "Trust"],
}

FIRST = ["Anna", "Marcus", "Priya", "Tom", "Sofia", "Daniel", "Yuki", "Lena",
         "Omar", "Claire", "Raj", "Nina", "Peter", "Maya", "Felix", "Hannah",
         "Diego", "Ingrid", "Sam", "Elena", "Karl", "Wei", "Aisha", "Jonas"]
LAST = ["Keller", "Novak", "Sharma", "Bennett", "Rossi", "Hoffmann", "Tanaka",
        "Weber", "Haddad", "Dubois", "Patel", "Kowalski", "Andersen", "Silva",
        "Bauer", "Lindqvist", "Moreau", "Okafor", "Reyes", "Vogel", "Chen"]

TITLES = [
    ("Chief Information Security Officer", "C-Level", "Security"),
    ("Chief Information Officer", "C-Level", "IT"),
    ("VP of Information Security", "VP", "Security"),
    ("VP of Infrastructure", "VP", "IT"),
    ("Director of Security Operations", "Director", "Security"),
    ("Director of Cloud Platform", "Director", "Engineering"),
    ("Head of IT Risk", "Director", "Security"),
    ("Security Architect", "Manager", "Security"),
    ("Network Engineering Manager", "Manager", "IT"),
    ("Procurement Manager", "Manager", "Finance"),
    ("Security Analyst", "Practitioner", "Security"),
    ("Systems Administrator", "Practitioner", "IT"),
]

ZT_KEYWORDS = ["Zero Trust", "Zero Trust Architecture", "Microsegmentation",
               "Identity Aware Proxy", "Least Privilege Access"]
SASE_KEYWORDS = ["SASE", "Secure Web Gateway", "SD-WAN Security"]
OTHER_KEYWORDS = ["Cloud Workload Protection", "SIEM Replacement", "MDR Services",
                  "Data Loss Prevention", "Endpoint Detection", "Compliance Automation"]

ASSETS = [
    ("AS-01", "Zero Trust Maturity Guide", "Whitepaper"),
    ("AS-02", "Zero Trust Architecture Webinar", "Webinar"),
    ("AS-03", "Microsegmentation Technical Demo", "Demo"),
    ("AS-04", "Financial Services Security Case Study", "Case Study"),
    ("AS-05", "Company Overview Brochure", "Brochure"),
    ("AS-06", "Security Trends Blog Digest", "Blog"),
    ("AS-07", "SASE Buyers Guide", "Whitepaper"),
    ("AS-08", "Ransomware Readiness Checklist", "Checklist"),
]
# Assets that genuinely move deals, and the duds. Drives the attribution story.
HIGH_INFLUENCE = {"AS-01", "AS-03", "AS-04"}
LOW_INFLUENCE = {"AS-05", "AS-06"}

# --- Grounding data for the four generative orchestrators -----------------
# These are hand-authored rather than randomised: a demo of content and
# messaging quality is only convincing if the source facts are coherent.

ICP = {
    "min_employee_count": 2000,
    "max_employee_count": 60000,
    "target_industries": [
        "Financial Services", "Healthcare", "Manufacturing",
        "Technology", "Public Sector",
    ],
    "industry_weights": {
        "Financial Services": 100, "Healthcare": 90, "Public Sector": 85,
        "Manufacturing": 75, "Technology": 70, "Retail": 55,
    },
    "priority_keywords": [
        "Zero Trust", "Zero Trust Architecture", "Least Privilege Access",
        "Microsegmentation", "Identity Aware Proxy", "Compliance Automation",
    ],
    # Composite account score = weighted sum of four 0-100 components.
    "weights": {
        "firmographic": 0.35,
        "intent": 0.35,
        "engagement": 0.15,
        "pipeline": 0.15,
    },
    "tier_thresholds": {"Tier 1": 72, "Tier 2": 52},
}

SAILPOINT_FEATURES = [
    {
        "id": "PF-01", "name": "Identity Security Cloud - Access Modeling",
        "category": "IGA",
        "summary": "AI-driven role discovery and automated access certifications.",
        "addresses_gap": "Manual, spreadsheet-driven access reviews on legacy or "
                         "homegrown IGA.",
        "value_lever": "access_review_automation",
        "competitor_gap": {
            "CyberArk": "PAM-led; shallow identity governance and certifications.",
            "Saviynt": "Governance depth exists but heavy to deploy and tune.",
            "One Identity": "Aging architecture, limited SaaS-native automation.",
        },
    },
    {
        "id": "PF-02", "name": "Cloud Infrastructure Entitlement Management",
        "category": "Cloud Governance",
        "summary": "Visibility and least-privilege enforcement across multi-cloud.",
        "addresses_gap": "Ungoverned cloud entitlements and standing privilege.",
        "value_lever": "breach_risk_reduction",
        "competitor_gap": {
            "CyberArk": "Strong vaulting, weaker on cloud entitlement governance.",
            "Saviynt": "Comparable ambition, slower time-to-value.",
        },
    },
    {
        "id": "PF-03", "name": "Non-Employee Risk Management",
        "category": "IGA",
        "summary": "Lifecycle governance for contractors, partners and third parties.",
        "addresses_gap": "No system of record for third-party identity risk.",
        "value_lever": "audit_readiness",
        "competitor_gap": {
            "One Identity": "Limited native third-party lifecycle coverage.",
        },
    },
    {
        "id": "PF-04", "name": "Automated Provisioning & Lifecycle",
        "category": "IGA",
        "summary": "Joiner-mover-leaver automation across the application estate.",
        "addresses_gap": "Slow, ticket-driven provisioning and orphaned accounts.",
        "value_lever": "provisioning_efficiency",
        "competitor_gap": {
            "CyberArk": "Not a lifecycle/provisioning platform.",
        },
    },
]

PERSONAS = [
    {
        "key": "CISO", "title": "Chief Information Security Officer",
        "priorities": ["Reduce breach risk", "Zero Trust program maturity",
                       "Board-level risk reporting"],
        "pains": ["Standing privilege and access sprawl",
                  "No unified view of who has access to what",
                  "Audit findings on access controls"],
        "messaging_angle": "Identity is the control plane for Zero Trust; "
                           "govern access to shrink the attack surface.",
        "proof_points": ["30% reduction in identity-related breach exposure",
                         "Continuous certification instead of point-in-time"],
        "common_objections": ["We already have PAM",
                              "This looks like a multi-year program"],
    },
    {
        "key": "CIO", "title": "Chief Information Officer",
        "priorities": ["Operational efficiency", "Cloud migration",
                       "IT cost control"],
        "pains": ["Manual provisioning drains the service desk",
                  "M&A integration of identity is slow"],
        "messaging_angle": "Automate the identity lifecycle to free IT capacity "
                           "and accelerate cloud and M&A.",
        "proof_points": ["70% less manual effort on access reviews",
                         "Faster onboarding of new hires and contractors"],
        "common_objections": ["We have budget pressure this year"],
    },
    {
        "key": "IAM_Director", "title": "Director of Identity & Access Management",
        "priorities": ["Consolidate identity tooling", "Reduce orphaned accounts",
                       "Prove control coverage"],
        "pains": ["Legacy IGA is end-of-life and brittle",
                  "Certifications are a quarterly fire drill"],
        "messaging_angle": "Replace brittle legacy IGA with SaaS-native automation "
                           "your team can actually operate.",
        "proof_points": ["Deploys in weeks, not quarters",
                         "Out-of-the-box connectors for the app estate"],
        "common_objections": ["Rip-and-replace is risky",
                              "My team is already stretched"],
    },
    {
        "key": "Compliance_Officer", "title": "Head of IT Risk & Compliance",
        "priorities": ["Audit readiness", "Regulatory evidence",
                       "Segregation of duties"],
        "pains": ["Evidence collection is manual and error-prone",
                  "SoD violations surface only at audit time"],
        "messaging_angle": "Turn access governance into always-on, audit-ready "
                           "evidence.",
        "proof_points": ["Continuous SoD monitoring",
                         "One-click audit evidence packs"],
        "common_objections": ["Our auditors accept our current process"],
    },
]

COMPETITORS = [
    {
        "name": "CyberArk", "category": "PAM-led identity security",
        "strengths": ["Market-leading privileged access vaulting",
                      "Strong brand in security buying centers"],
        "weaknesses": ["Shallow identity governance and certifications",
                       "Weaker cloud entitlement governance",
                       "Not a provisioning/lifecycle platform"],
        "sailpoint_advantages": ["Deep IGA and continuous certification",
                                 "Unified governance across cloud and on-prem",
                                 "Lifecycle automation PAM cannot provide"],
        "displacement_angle": "PAM secures the few privileged accounts; SailPoint "
                              "governs access for everyone. You need both, and "
                              "governance is the gap.",
        "common_objections": ["We standardized on CyberArk for privileged access"],
    },
    {
        "name": "Saviynt", "category": "Converged identity governance",
        "strengths": ["Broad governance ambition", "Cloud-native positioning"],
        "weaknesses": ["Long, complex deployments",
                       "Higher tuning and admin burden",
                       "Inconsistent connector reliability"],
        "sailpoint_advantages": ["Faster time-to-value",
                                 "Proven at enterprise scale",
                                 "Lower operational overhead"],
        "displacement_angle": "Similar vision, but SailPoint gets you to value in "
                              "weeks with far less operational drag.",
        "common_objections": ["Saviynt quoted us a lower list price"],
    },
    {
        "name": "One Identity", "category": "Legacy IGA",
        "strengths": ["Installed base", "Bundled with broader Quest portfolio"],
        "weaknesses": ["Aging architecture", "Limited SaaS-native automation",
                       "Thin third-party/non-employee coverage"],
        "sailpoint_advantages": ["Modern SaaS platform",
                                 "AI-driven access modeling",
                                 "Non-employee risk management"],
        "displacement_angle": "Modernize off an end-of-life architecture before it "
                              "becomes an audit liability.",
        "common_objections": ["We're already invested in the Quest stack"],
    },
]

REGULATIONS = [
    {"code": "GDPR", "name": "General Data Protection Regulation",
     "region": "EMEA", "summary": "EU data protection; access controls and "
     "least privilege over personal data.", "industries": ["all"]},
    {"code": "NIS2", "name": "Network and Information Security Directive 2",
     "region": "EMEA", "summary": "EU cyber-resilience mandate raising access "
     "governance and accountability requirements.", "industries": ["all"]},
    {"code": "DORA", "name": "Digital Operational Resilience Act",
     "region": "EMEA", "summary": "EU financial-sector operational resilience, "
     "including ICT and access risk.", "industries": ["Financial Services"]},
    {"code": "SOX", "name": "Sarbanes-Oxley Act",
     "region": "AMER", "summary": "US controls over financial reporting; "
     "segregation of duties and access certification.",
     "industries": ["Financial Services", "all"]},
    {"code": "HIPAA", "name": "Health Insurance Portability and Accountability Act",
     "region": "AMER", "summary": "US healthcare data protection; minimum-necessary "
     "access to PHI.", "industries": ["Healthcare"]},
    {"code": "LGPD", "name": "Lei Geral de Protecao de Dados",
     "region": "LATAM", "summary": "Brazil's data protection law, close analogue "
     "to GDPR.", "industries": ["all"]},
]

BRAND_VOICE = {
    "tone": ["Confident", "Clear", "Credible", "Non-hyperbolic"],
    "style_rules": [
        "Lead with the customer outcome, not the product feature.",
        "Prefer plain language over jargon; explain acronyms on first use.",
        "Quantify claims wherever the data supports it.",
        "Never disparage a competitor by name in public-facing copy.",
    ],
    "banned_phrases": ["revolutionary", "game-changer", "silver bullet",
                       "best-in-class", "synergy"],
    "boilerplate": "SailPoint is the leader in identity security for the modern "
                   "enterprise, helping organizations see, control and govern "
                   "access across every identity, application and data source.",
}

EXECUTIVE_VOICES = [
    {"name": "Executive Spokesperson", "title": "Chief Product Officer",
     "themes": ["Identity as the Zero Trust control plane",
                "AI in access governance"],
     "sample_quote": "Every breach eventually traces back to access that should "
                     "not have existed. Governing identity is how you shrink that "
                     "surface."},
    {"name": "Field CISO", "title": "Field CISO",
     "themes": ["Audit readiness", "Third-party risk"],
     "sample_quote": "Continuous certification turns audit season from a fire "
                     "drill into a report you can already produce."},
]

# ROI models. The maths lives in metrics/value.py; these are its inputs.
VALUE_BENCHMARKS = {
    "levers": {
        "access_review_automation": {
            "metric": "annual hours saved on access certifications",
            "description": "Legacy access reviews consume large analyst effort; "
                           "automation removes most of it.",
            "params": {"hours_per_1k_employees_per_year": 240,
                       "reduction_pct": 0.7, "loaded_hourly_cost": 85},
        },
        "breach_risk_reduction": {
            "metric": "expected annual breach cost avoided",
            "description": "Reducing standing privilege lowers expected breach "
                           "impact.",
            "params": {"avg_breach_cost_usd": 4880000,
                       "annual_probability": 0.28, "reduction_pct": 0.30},
        },
        "audit_readiness": {
            "metric": "annual audit and evidence effort saved",
            "description": "Always-on evidence removes manual audit preparation.",
            "params": {"hours_per_1k_employees_per_year": 90,
                       "reduction_pct": 0.6, "loaded_hourly_cost": 95},
        },
        "provisioning_efficiency": {
            "metric": "annual service-desk effort saved on provisioning",
            "description": "Automated joiner-mover-leaver cuts ticket volume.",
            "params": {"hours_per_1k_employees_per_year": 320,
                       "reduction_pct": 0.65, "loaded_hourly_cost": 60},
        },
    },
    "industry_multipliers": {
        "Financial Services": 1.30, "Healthcare": 1.25, "Public Sector": 1.15,
        "Manufacturing": 1.05, "Technology": 1.10, "Retail": 1.00,
    },
}

# Technographic vendor pools by category. "Legacy/Homegrown" IGA is the gap
# story SailPoint displaces.
TECH_CATEGORIES = {
    "IGA": ["Legacy/Homegrown", "Saviynt", "One Identity", "Oracle Identity",
            "Microsoft Entra ID Governance"],
    "PAM": ["CyberArk", "BeyondTrust", "Delinea", "None"],
    "IAM/SSO": ["Okta", "Microsoft Entra ID", "Ping Identity"],
    "MFA": ["Duo", "Okta Verify", "Microsoft Authenticator"],
    "ITSM": ["ServiceNow", "Jira Service Management"],
}

NEWS = [
    {"id": "NEWS-01", "date": "2026-09-02", "source": "Dark Reading",
     "headline": "Saviynt discloses breach exposing customer configuration data",
     "summary": "A competitor in identity governance confirmed a security "
                "incident affecting a subset of cloud customers.",
     "topic": "Competitor breach", "sentiment": "negative",
     "competitor_mentioned": "Saviynt", "is_trigger": True},
    {"id": "NEWS-02", "date": "2026-08-28", "source": "SC Magazine",
     "headline": "EU NIS2 enforcement begins; access governance in scope",
     "summary": "Regulators signal active enforcement of NIS2, raising the bar "
                "on identity and access accountability.",
     "topic": "Regulation", "sentiment": "neutral",
     "competitor_mentioned": None, "is_trigger": True},
    {"id": "NEWS-03", "date": "2026-08-20", "source": "Gartner",
     "headline": "Gartner: identity-first security remains top 2026 priority",
     "summary": "Analyst commentary reinforces identity as the primary control "
                "plane for modern security programs.",
     "topic": "Analyst view", "sentiment": "positive",
     "competitor_mentioned": None, "is_trigger": False},
    {"id": "NEWS-04", "date": "2026-08-15", "source": "CyberScoop",
     "headline": "CyberArk expands into cloud entitlement management",
     "summary": "CyberArk announced new CIEM capabilities, moving further into "
                "governance-adjacent territory.",
     "topic": "Competitor move", "sentiment": "neutral",
     "competitor_mentioned": "CyberArk", "is_trigger": False},
    {"id": "NEWS-05", "date": "2026-08-10", "source": "CRN",
     "headline": "SailPoint named a leader in identity governance",
     "summary": "SailPoint recognized for governance depth and enterprise scale.",
     "topic": "SailPoint win", "sentiment": "positive",
     "competitor_mentioned": None, "is_trigger": False},
]

SOCIAL = [
    {"id": "SOC-01", "platform": "LinkedIn", "author": "iam_architect",
     "date": "2026-09-03",
     "text": "SailPoint's access modeling saved our team weeks on the last "
             "certification cycle. Genuinely impressed.",
     "url": "https://linkedin.com/posts/soc-01", "is_question": False,
     "seed_sentiment": "positive"},
    {"id": "SOC-02", "platform": "X", "author": "@ciso_notes",
     "date": "2026-09-03",
     "text": "Frustrated with how long our SailPoint connectors took to configure. "
             "Support has been slow to respond.",
     "url": "https://x.com/soc-02", "is_question": False,
     "seed_sentiment": "negative"},
    {"id": "SOC-03", "platform": "Reddit", "author": "u/sysadmin_throwaway",
     "date": "2026-09-02",
     "text": "Anyone compared SailPoint vs Saviynt for a healthcare org? "
             "Trying to shortlist.",
     "url": "https://reddit.com/r/cybersecurity/soc-03", "is_question": True,
     "seed_sentiment": "neutral"},
    {"id": "SOC-04", "platform": "YouTube", "author": "SecurityWeekly",
     "date": "2026-09-01",
     "text": "Great walkthrough of identity governance trends featuring SailPoint. "
             "Worth a watch.",
     "url": "https://youtube.com/watch?v=soc-04", "is_question": False,
     "seed_sentiment": "positive"},
    {"id": "SOC-05", "platform": "X", "author": "@identitygeek",
     "date": "2026-08-31",
     "text": "Is SailPoint's non-employee risk module GA yet? Docs are unclear.",
     "url": "https://x.com/soc-05", "is_question": True,
     "seed_sentiment": "neutral"},
    {"id": "SOC-06", "platform": "LinkedIn", "author": "grc_lead",
     "date": "2026-08-30",
     "text": "Switched off One Identity to SailPoint and audit prep is night and "
             "day. Should have done it sooner.",
     "url": "https://linkedin.com/posts/soc-06", "is_question": False,
     "seed_sentiment": "positive"},
]

# Share of voice: SailPoint trails CyberArk overall, the planted brand story.
SHARE_OF_VOICE = {
    "period": "Last 30 days",
    "mentions": {
        "CyberArk": 4200, "SailPoint": 3100, "Saviynt": 1600,
        "One Identity": 900,
    },
    "by_channel": {
        "LinkedIn": {"CyberArk": 1500, "SailPoint": 1400, "Saviynt": 520,
                     "One Identity": 300},
        "X": {"CyberArk": 1200, "SailPoint": 700, "Saviynt": 480,
              "One Identity": 240},
        "Reddit": {"CyberArk": 900, "SailPoint": 600, "Saviynt": 360,
                   "One Identity": 200},
        "YouTube": {"CyberArk": 600, "SailPoint": 400, "Saviynt": 240,
                    "One Identity": 160},
    },
}

REVIEWS = [
    {"source": "G2", "product": "SailPoint", "rating": 4.5,
     "reviewer_role": "IAM Director",
     "pros": "Deep governance, strong certifications, scales well.",
     "cons": "Initial connector setup takes planning."},
    {"source": "G2", "product": "CyberArk", "rating": 4.4,
     "reviewer_role": "Security Engineer",
     "pros": "Best-in-market privileged vaulting.",
     "cons": "Governance and certification features are thin."},
    {"source": "Gartner Peer Insights", "product": "Saviynt", "rating": 4.2,
     "reviewer_role": "Enterprise Architect",
     "pros": "Broad feature set, cloud-native.",
     "cons": "Deployment was long and required heavy tuning."},
    {"source": "Gartner Peer Insights", "product": "One Identity", "rating": 3.8,
     "reviewer_role": "IT Risk Manager",
     "pros": "Stable for on-prem use cases.",
     "cons": "Architecture feels dated; limited SaaS automation."},
]

# Section outlines the campaign/content agents fill in.
TEMPLATES = {
    "campaign_brief": ["Goal", "Target Audience", "Key Messages", "Channels",
                       "Budget", "Timeline", "Success KPIs", "Dependencies"],
    "battlecard": ["Positioning Statement", "Why We Win", "Their Strengths",
                   "Competitive Landmines", "Objection Handlers",
                   "Displacement CTA"],
    "sales_playbook": ["Account Summary", "Key Stakeholders", "Pain Points",
                       "Recommended Talk Tracks", "Competitive Landmines",
                       "Suggested Assets"],
    "anchor_asset": ["Executive Summary", "The Problem", "Why Now",
                     "The SailPoint Approach", "Proof and Outcomes",
                     "Getting Started"],
}


def d(days_ago: int) -> str:
    return (AS_OF - timedelta(days=days_ago)).isoformat()


def make_accounts() -> list[dict]:
    accounts: list[dict] = []
    used_names: set[str] = set()
    counter = 1

    def add(region: Region, city: str, industry: str, *, target: bool,
            employees: int | None = None) -> dict:
        nonlocal counter
        while True:
            name = (f"{RNG.choice(PREFIXES)} "
                    f"{RNG.choice(SUFFIX_BY_INDUSTRY[industry])}")
            if name not in used_names:
                used_names.add(name)
                break
        emp = employees or RNG.choice([450, 900, 1800, 3200, 6500, 12000, 24000])
        acct = {
            "id": f"ACC-{counter:03d}",
            "name": name,
            "industry": industry,
            "region": region.value,
            "country": COUNTRY_OF_CITY[city],
            "city": city,
            "employee_count": emp,
            "annual_revenue_usd": emp * RNG.choice([180_000, 240_000, 320_000]),
            "is_target_account": target,
            "health_score": RNG.choice([None, None, 62, 71, 78, 84, 45, 55]),
        }
        counter += 1
        accounts.append(acct)
        return acct

    # Story 2a: the Munich/Frankfurt cluster. Large financial services and
    # manufacturing firms, all target accounts, none of which will get an opp.
    for city, n in (("Munich", 5), ("Frankfurt", 3)):
        for _ in range(n):
            add(Region.EMEA, city,
                RNG.choice(["Financial Services", "Manufacturing"]),
                target=True, employees=RNG.choice([4200, 7800, 11000, 16000]))

    # Story 2b: a weaker competing cluster in Singapore around SASE.
    for _ in range(4):
        add(Region.APJ, "Singapore", RNG.choice(["Technology", "Financial Services"]),
            target=True, employees=RNG.choice([1500, 3000, 5200]))

    # Everyone else.
    for region, n in ((Region.AMER, 26), (Region.EMEA, 14), (Region.APJ, 9)):
        for _ in range(n):
            add(region, RNG.choice(CITIES[region]), RNG.choice(INDUSTRIES),
                target=RNG.random() < 0.45)

    return accounts


def make_contacts(accounts: list[dict]) -> list[dict]:
    contacts: list[dict] = []
    counter = 1
    for acct in accounts:
        domain = acct["name"].lower().replace(" ", "") + ".com"
        for title, seniority, function in RNG.sample(TITLES, RNG.choice([2, 3, 3, 4])):
            first, last = RNG.choice(FIRST), RNG.choice(LAST)
            contacts.append({
                "id": f"CON-{counter:04d}",
                "account_id": acct["id"],
                "full_name": f"{first} {last}",
                "email": f"{first.lower()}.{last.lower()}@{domain}",
                "title": title,
                "seniority": seniority,
                "function": function,
                "country": acct["country"],
                "email_opt_in": RNG.random() > 0.08,
            })
            counter += 1
    return contacts


def make_campaigns() -> list[dict]:
    """Twelve campaigns, two of them planted to make the budget story obvious."""
    campaigns = [
        # Story 5: the money pit. High spend, almost no opportunities.
        {"id": "CMP-001", "name": "Paid Social - Cloud Security Always On",
         "type": CampaignType.PAID_SOCIAL, "region": Region.AMER,
         "spend_usd": 86_000, "impressions": 2_400_000, "clicks": 18_400,
         "leads": 620, "mqls": 96, "sqls": 14, "opps_created": 2,
         "leads_1w": 580, "mqls_1w": 91, "opps_1w": 2, "days_ago": 120},
        # Story 5: the winner. Low spend, strong opportunity creation.
        {"id": "CMP-002", "name": "Webinar - Zero Trust Maturity",
         "type": CampaignType.WEBINAR, "region": Region.EMEA,
         "spend_usd": 22_000, "impressions": 210_000, "clicks": 9_800,
         "leads": 410, "mqls": 188, "sqls": 74, "opps_created": 11,
         "leads_1w": 352, "mqls_1w": 151, "opps_1w": 8, "days_ago": 75},
        {"id": "CMP-003", "name": "Content Syndication - CISO Priorities",
         "type": CampaignType.CONTENT_SYNDICATION, "region": Region.AMER,
         "spend_usd": 48_000, "impressions": 0, "clicks": 0,
         "leads": 940, "mqls": 141, "sqls": 32, "opps_created": 6,
         "leads_1w": 880, "mqls_1w": 130, "opps_1w": 5, "days_ago": 95},
        {"id": "CMP-004", "name": "Paid Search - Zero Trust Terms",
         "type": CampaignType.PAID_SEARCH, "region": Region.AMER,
         "spend_usd": 61_000, "impressions": 890_000, "clicks": 24_500,
         "leads": 510, "mqls": 172, "sqls": 58, "opps_created": 9,
         "leads_1w": 470, "mqls_1w": 158, "opps_1w": 8, "days_ago": 130},
        {"id": "CMP-005", "name": "Field Event - Munich CISO Roundtable",
         "type": CampaignType.FIELD_EVENT, "region": Region.EMEA,
         "spend_usd": 34_000, "impressions": 0, "clicks": 0,
         "leads": 78, "mqls": 61, "sqls": 28, "opps_created": 5,
         "leads_1w": 52, "mqls_1w": 40, "opps_1w": 3, "days_ago": 40},
        {"id": "CMP-006", "name": "Email Nurture - Security Modernisation",
         "type": CampaignType.EMAIL_NURTURE, "region": Region.AMER,
         "spend_usd": 9_000, "impressions": 0, "clicks": 6_200,
         "leads": 240, "mqls": 88, "sqls": 21, "opps_created": 4,
         "leads_1w": 232, "mqls_1w": 84, "opps_1w": 4, "days_ago": 160},
        {"id": "CMP-007", "name": "Tradeshow - Infosec Europe",
         "type": CampaignType.TRADESHOW, "region": Region.EMEA,
         "spend_usd": 120_000, "impressions": 0, "clicks": 0,
         "leads": 1_240, "mqls": 210, "sqls": 44, "opps_created": 7,
         "leads_1w": 1_240, "mqls_1w": 198, "opps_1w": 6, "days_ago": 88},
        {"id": "CMP-008", "name": "Webinar - Microsegmentation in Practice",
         "type": CampaignType.WEBINAR, "region": Region.APJ,
         "spend_usd": 17_000, "impressions": 96_000, "clicks": 4_100,
         "leads": 196, "mqls": 79, "sqls": 26, "opps_created": 5,
         "leads_1w": 171, "mqls_1w": 68, "opps_1w": 4, "days_ago": 55},
        {"id": "CMP-009", "name": "Paid Social - Retargeting APJ",
         "type": CampaignType.PAID_SOCIAL, "region": Region.APJ,
         "spend_usd": 29_000, "impressions": 740_000, "clicks": 5_900,
         "leads": 148, "mqls": 22, "sqls": 4, "opps_created": 1,
         "leads_1w": 141, "mqls_1w": 21, "opps_1w": 1, "days_ago": 70},
        {"id": "CMP-010", "name": "Content Syndication - Ransomware Readiness",
         "type": CampaignType.CONTENT_SYNDICATION, "region": Region.EMEA,
         "spend_usd": 38_000, "impressions": 0, "clicks": 0,
         "leads": 720, "mqls": 104, "sqls": 19, "opps_created": 3,
         "leads_1w": 690, "mqls_1w": 99, "opps_1w": 3, "days_ago": 110},
        {"id": "CMP-011", "name": "Paid Search - Competitor Terms",
         "type": CampaignType.PAID_SEARCH, "region": Region.EMEA,
         "spend_usd": 44_000, "impressions": 520_000, "clicks": 11_200,
         "leads": 288, "mqls": 61, "sqls": 12, "opps_created": 2,
         "leads_1w": 268, "mqls_1w": 57, "opps_1w": 2, "days_ago": 100},
        {"id": "CMP-012", "name": "Field Event - Singapore Security Breakfast",
         "type": CampaignType.FIELD_EVENT, "region": Region.APJ,
         "spend_usd": 21_000, "impressions": 0, "clicks": 0,
         "leads": 54, "mqls": 39, "sqls": 15, "opps_created": 3,
         "leads_1w": 41, "mqls_1w": 30, "opps_1w": 2, "days_ago": 35},
    ]
    out = []
    for c in campaigns:
        out.append({
            "id": c["id"], "name": c["name"], "type": c["type"].value,
            "region": c["region"].value,
            "start_date": d(c["days_ago"]), "end_date": d(-30),
            "spend_usd": c["spend_usd"], "impressions": c["impressions"],
            "clicks": c["clicks"], "leads": c["leads"], "mqls": c["mqls"],
            "sqls": c["sqls"], "opps_created": c["opps_created"],
            "leads_one_week_ago": c["leads_1w"],
            "mqls_one_week_ago": c["mqls_1w"],
            "opps_created_one_week_ago": c["opps_1w"],
        })
    return out


def make_opportunities(accounts: list[dict], campaigns: list[dict]) -> list[dict]:
    """One or two opps for most accounts. The planted clusters get none."""
    no_opp_cities = {"Munich", "Frankfurt"}
    eligible = [
        a for a in accounts
        if not (a["city"] in no_opp_cities and a["is_target_account"])
        and not (a["city"] == "Singapore" and a["is_target_account"])
    ]

    stages = list(OppStage)
    open_stages = stages[:5]
    opps: list[dict] = []
    counter = 1

    # Story 1: EMEA deal sizes are deliberately smaller so its coverage lands
    # under target while the other two regions clear it.
    size_by_region = {
        Region.AMER.value: (400_000, 2_200_000),
        Region.EMEA.value: (250_000, 900_000),
        Region.APJ.value: (300_000, 1_200_000),
    }

    for acct in eligible:
        for _ in range(RNG.choice([1, 1, 2, 2, 3])):
            stage = RNG.choices(
                open_stages + [OppStage.CLOSED_WON, OppStage.CLOSED_LOST],
                weights=[18, 20, 18, 12, 8, 14, 10],
            )[0]
            lo, hi = size_by_region[acct["region"]]
            created = RNG.randint(15, 210)
            # Most open deals moved recently; a minority did not.
            moved = RNG.random() < 0.55
            prev = stage
            if moved and stage in open_stages:
                idx = open_stages.index(stage)
                prev = open_stages[max(0, idx - 1)]
            opps.append({
                "id": f"OPP-{counter:04d}",
                "account_id": acct["id"],
                "name": f"{acct['name']} - Security Platform",
                "stage": stage.value,
                "amount_usd": RNG.randint(lo, hi) // 1000 * 1000,
                "created_date": d(created),
                "close_date": d(-RNG.randint(10, 120)),
                "stage_one_week_ago": prev.value,
                "source_campaign_id": RNG.choice(campaigns)["id"],
                "owner_region": acct["region"],
            })
            counter += 1

    # Story 4: six large deals frozen in place. Old, unmoved, and expensive
    # enough that pipeline health should call them out by name.
    big = [o for o in opps
           if o["stage"] in {s.value for s in open_stages}][:6]
    for i, opp in enumerate(big):
        opp["created_date"] = d(95 + i * 14)
        opp["stage_one_week_ago"] = opp["stage"]
        opp["amount_usd"] = max(opp["amount_usd"], RNG.randint(900_000, 2_600_000))

    return opps


def make_intent(accounts: list[dict]) -> list[dict]:
    """6sense-style signals. The planted clusters surge on one theme each."""
    signals: list[dict] = []

    for acct in accounts:
        in_zt_cluster = acct["city"] in {"Munich", "Frankfurt"} and acct["is_target_account"]
        in_sase_cluster = acct["city"] == "Singapore" and acct["is_target_account"]

        if in_zt_cluster:
            # Always anchor on the literal "Zero Trust" plus two related terms.
            # The variation is deliberate: the agent has to recognise that
            # microsegmentation and least-privilege are the same conversation.
            for kw in [ZT_KEYWORDS[0]] + RNG.sample(ZT_KEYWORDS[1:], 2):
                signals.append({
                    "account_id": acct["id"], "keyword": kw,
                    "intent_score": RNG.randint(82, 97),
                    "buying_stage": RNG.choice(["Consideration", "Decision"]),
                    "trending": True,
                })
        elif in_sase_cluster:
            for kw in RNG.sample(SASE_KEYWORDS, 2):
                signals.append({
                    "account_id": acct["id"], "keyword": kw,
                    "intent_score": RNG.randint(68, 84),
                    "buying_stage": RNG.choice(["Awareness", "Consideration"]),
                    "trending": True,
                })
        else:
            for kw in RNG.sample(ZT_KEYWORDS + SASE_KEYWORDS + OTHER_KEYWORDS,
                                 RNG.choice([1, 2, 2, 3])):
                signals.append({
                    "account_id": acct["id"], "keyword": kw,
                    "intent_score": RNG.randint(25, 74),
                    "buying_stage": RNG.choice(
                        ["None", "Awareness", "Awareness", "Consideration"]),
                    "trending": RNG.random() < 0.2,
                })
    return signals


def make_engagement(accounts: list[dict], contacts: list[dict],
                    opps: list[dict]) -> list[dict]:
    """Story 3: influential assets land at accounts whose deals progressed."""
    by_account: dict[str, list[dict]] = {}
    for c in contacts:
        by_account.setdefault(c["account_id"], []).append(c)

    progressed_accounts = {
        o["account_id"] for o in opps
        if o["stage"] in {OppStage.STAGE_3_VALIDATE.value,
                          OppStage.STAGE_4_PROPOSE.value,
                          OppStage.STAGE_5_NEGOTIATE.value,
                          OppStage.CLOSED_WON.value}
    }

    events: list[dict] = []
    for acct in accounts:
        acct_contacts = by_account.get(acct["id"], [])
        if not acct_contacts:
            continue
        progressed = acct["id"] in progressed_accounts

        for asset_id, asset_name, asset_type in ASSETS:
            if asset_id in HIGH_INFLUENCE:
                # Strongly skewed towards accounts that moved forward.
                chance = 0.72 if progressed else 0.12
            elif asset_id in LOW_INFLUENCE:
                # Everybody reads these and they predict nothing.
                chance = 0.55
            else:
                chance = 0.30
            if RNG.random() > chance:
                continue
            for contact in RNG.sample(acct_contacts,
                                      min(len(acct_contacts), RNG.choice([1, 1, 2]))):
                events.append({
                    "contact_id": contact["id"],
                    "account_id": acct["id"],
                    "asset_id": asset_id,
                    "asset_name": asset_name,
                    "asset_type": asset_type,
                    "occurred_on": d(RNG.randint(5, 150)),
                    "campaign_id": None,
                })
    return events


def make_events_and_attendees(accounts: list[dict], contacts: list[dict],
                              opps: list[dict]) -> tuple[list[dict], list[dict]]:
    """Story 6: a Munich roundtable with real pipeline in the room."""
    field_events = [
        {"id": "EVT-001", "name": "CISO Roundtable Munich", "city": "Munich",
         "region": Region.EMEA.value, "event_date": d(-41),
         "topic": "Zero Trust Architecture"},
        {"id": "EVT-002", "name": "Security Breakfast Singapore", "city": "Singapore",
         "region": Region.APJ.value, "event_date": d(-62), "topic": "SASE"},
    ]

    accounts_with_open_opp = {
        o["account_id"] for o in opps
        if o["stage"] not in {OppStage.CLOSED_WON.value, OppStage.CLOSED_LOST.value}
    }
    by_account: dict[str, list[dict]] = {}
    for c in contacts:
        by_account.setdefault(c["account_id"], []).append(c)

    attendees: list[dict] = []

    # Munich: the whole no-opp cluster plus some EMEA accounts that do have
    # pipeline, so "pipeline in the room" is a mix of new logo and existing.
    munich_pool = [a for a in accounts if a["region"] == Region.EMEA.value and (
        a["city"] in {"Munich", "Frankfurt"}
        or a["id"] in accounts_with_open_opp
    )][:16]
    for acct in munich_pool:
        for contact in RNG.sample(by_account.get(acct["id"], []),
                                  min(len(by_account.get(acct["id"], [])),
                                      RNG.choice([1, 1, 2]))):
            attendees.append({
                "event_id": "EVT-001",
                "contact_id": contact["id"],
                "account_id": acct["id"],
                "status": RNG.choices(
                    ["Confirmed", "Registered", "Attended", "No Show"],
                    weights=[45, 30, 20, 5])[0],
            })

    sg_pool = [a for a in accounts if a["city"] == "Singapore"][:8]
    for acct in sg_pool:
        for contact in RNG.sample(by_account.get(acct["id"], []),
                                  min(len(by_account.get(acct["id"], [])), 1)):
            attendees.append({
                "event_id": "EVT-002",
                "contact_id": contact["id"],
                "account_id": acct["id"],
                "status": RNG.choice(["Confirmed", "Registered"]),
            })

    return field_events, attendees


def make_targets(opps: list[dict]) -> dict:
    """Set quarterly targets so the coverage story is exact, not approximate.

    Coverage is open pipeline divided by target. We pick targets that put EMEA
    below the 2x bar and the other two comfortably above it.
    """
    desired = {Region.AMER.value: 2.4, Region.EMEA.value: 1.45, Region.APJ.value: 2.6}
    open_by_region: dict[str, int] = {}
    for o in opps:
        if o["stage"] in {OppStage.CLOSED_WON.value, OppStage.CLOSED_LOST.value}:
            continue
        open_by_region[o["owner_region"]] = (
            open_by_region.get(o["owner_region"], 0) + o["amount_usd"]
        )
    return {
        "coverage_target_multiple": 2.0,
        "quarterly_pipeline_target_usd": {
            region: round(total / desired[region], -5)
            for region, total in open_by_region.items()
        },
    }


def make_list_load_csv() -> list[dict]:
    """A messy event lead list, with the exact problems the SOP checks for.

    Planted issues: a blank email, a malformed email, ISO country codes instead
    of names, a duplicate row, leading/trailing whitespace, a missing last name
    and an internal address that should be suppressed.
    """
    return [
        {"First Name": "Anna", "Last Name": "Keller", "Email": "anna.keller@northwindcapital.com",
         "Company": "Northwind Capital", "Country": "DE", "Job Title": "CISO"},
        {"First Name": " Marcus ", "Last Name": "Novak", "Email": "marcus.novak@vertexsystems.com",
         "Company": "Vertex Systems", "Country": "Germany", "Job Title": "VP Infrastructure"},
        {"First Name": "Priya", "Last Name": "Sharma", "Email": "",
         "Company": "Lumen Industries", "Country": "DE", "Job Title": "Director of Security"},
        {"First Name": "Tom", "Last Name": "Bennett", "Email": "tom.bennett[at]ardentworks.com",
         "Company": "Ardent Works", "Country": "FR", "Job Title": "Security Architect"},
        {"First Name": "Anna", "Last Name": "Keller", "Email": "anna.keller@northwindcapital.com",
         "Company": "Northwind Capital", "Country": "DE", "Job Title": "CISO"},
        {"First Name": "Sofia", "Last Name": "Rossi", "Email": "sofia.rossi@kestrelbankgroup.com",
         "Company": "Kestrel Bank Group", "Country": "IT", "Job Title": "Head of IT Risk"},
        {"First Name": "Daniel", "Last Name": "", "Email": "daniel@bluepeakhealth.com",
         "Company": "Bluepeak Health", "Country": "NL", "Job Title": "CIO"},
        {"First Name": "Lena", "Last Name": "Hoffmann", "Email": "lena.hoffmann@ironwoodmanufacturing.com",
         "Company": "Ironwood Manufacturing", "Country": "Germany", "Job Title": "Security Analyst"},
        {"First Name": "Felix", "Last Name": "Bauer", "Email": "felix.bauer@gru-internal.com",
         "Company": "GRU", "Country": "DE", "Job Title": "Field Marketing"},
        {"First Name": "Hannah", "Last Name": "Weber", "Email": "HANNAH.WEBER@SOLSTICECAPITAL.COM",
         "Company": "Solstice Capital", "Country": "AT", "Job Title": "VP Security"},
    ]


def make_technographics(accounts: list[dict]) -> list[dict]:
    """Installed tools per account. The ZT cluster carries the gap story.

    Every Munich/Frankfurt target account runs a Legacy/Homegrown IGA that is
    end-of-life and CyberArk for PAM but nothing for governance, so the Gap &
    Value agent has an unambiguous displacement story to tell.
    """
    rows: list[dict] = []
    for acct in accounts:
        in_zt_cluster = (acct["city"] in {"Munich", "Frankfurt"}
                         and acct["is_target_account"])
        if in_zt_cluster:
            iga = "Legacy/Homegrown"
            iga_status = "end-of-life"
            pam = "CyberArk"
        else:
            iga = RNG.choice(TECH_CATEGORIES["IGA"])
            iga_status = ("end-of-life" if iga == "Legacy/Homegrown"
                          else RNG.choice(["deployed", "deployed", "evaluating"]))
            pam = RNG.choice(TECH_CATEGORIES["PAM"])

        rows.append({"account_id": acct["id"], "category": "IGA",
                     "vendor": iga,
                     "status": "homegrown" if iga == "Legacy/Homegrown"
                     else iga_status})
        if pam != "None":
            rows.append({"account_id": acct["id"], "category": "PAM",
                         "vendor": pam, "status": "deployed"})
        rows.append({"account_id": acct["id"], "category": "IAM/SSO",
                     "vendor": RNG.choice(TECH_CATEGORIES["IAM/SSO"]),
                     "status": "deployed"})
        rows.append({"account_id": acct["id"], "category": "ITSM",
                     "vendor": RNG.choice(TECH_CATEGORIES["ITSM"]),
                     "status": "deployed"})
    return rows


def make_company_facts(accounts: list[dict]) -> list[dict]:
    """Business context per account for intel briefs."""
    news_pool = [
        "Announced a multi-year cloud migration to consolidate data centers.",
        "Reported strong quarterly results and flagged security investment.",
        "Disclosed an audit finding on access controls in its annual report.",
        "Expanding into new regional markets via acquisition.",
        "Named to an industry list for digital transformation.",
    ]
    leadership_pool = [
        "New CISO appointed this quarter.",
        "Promoted a VP of Infrastructure to lead identity modernization.",
        "Hired a Head of IT Risk from a regulated peer.",
        "",
    ]
    rows: list[dict] = []
    for acct in accounts:
        in_zt_cluster = (acct["city"] in {"Munich", "Frankfurt"}
                         and acct["is_target_account"])
        if in_zt_cluster:
            rows.append({
                "account_id": acct["id"],
                "recent_news": "Publicly committed to a Zero Trust program "
                               "following a regional regulatory push.",
                "leadership_change": "New CISO appointed this quarter.",
                "fiscal_note": "Security budget increased year over year.",
                "priorities": ["Zero Trust", "Audit readiness",
                               "Access governance modernization"],
            })
        else:
            rows.append({
                "account_id": acct["id"],
                "recent_news": RNG.choice(news_pool),
                "leadership_change": RNG.choice(leadership_pool),
                "fiscal_note": RNG.choice(
                    ["Stable revenue.", "Cost-optimization program under way.",
                     "Investing in cloud and security."]),
                "priorities": RNG.sample(
                    ["Cloud migration", "Cost control", "Audit readiness",
                     "M&A integration", "Operational efficiency"],
                    RNG.choice([2, 3])),
            })
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    accounts = make_accounts()
    contacts = make_contacts(accounts)
    campaigns = make_campaigns()
    opportunities = make_opportunities(accounts, campaigns)
    intent = make_intent(accounts)
    engagement = make_engagement(accounts, contacts, opportunities)
    field_events, attendees = make_events_and_attendees(accounts, contacts, opportunities)
    targets = make_targets(opportunities)
    technographics = make_technographics(accounts)
    company_facts = make_company_facts(accounts)

    files = {
        "accounts.json": accounts,
        "contacts.json": contacts,
        "campaigns.json": campaigns,
        "opportunities.json": opportunities,
        "intent_signals.json": intent,
        "engagement_events.json": engagement,
        "field_events.json": field_events,
        "event_attendees.json": attendees,
        "targets.json": targets,
        # The current operating user ("me").
        "me.json": ME,
        # Enrichment (ZoomInfo / BuiltWith stand-in).
        "technographics.json": technographics,
        "company_facts.json": company_facts,
        # Knowledge base (Confluence / Rovo stand-in).
        "icp.json": ICP,
        "product_features.json": SAILPOINT_FEATURES,
        "personas.json": PERSONAS,
        "competitors.json": COMPETITORS,
        "regulatory_glossary.json": REGULATIONS,
        "brand_voice.json": BRAND_VOICE,
        "executive_voices.json": EXECUTIVE_VOICES,
        "value_benchmarks.json": VALUE_BENCHMARKS,
        "templates.json": TEMPLATES,
        # Market intelligence (Brandwatch / Meltwater / G2 stand-in).
        "news_articles.json": NEWS,
        "social_mentions.json": SOCIAL,
        "share_of_voice.json": SHARE_OF_VOICE,
        "reviews.json": REVIEWS,
    }
    for filename, payload in files.items():
        (OUT / filename).write_text(json.dumps(payload, indent=2) + "\n")
        count = len(payload) if isinstance(payload, list) else 1
        print(f"  {filename:<26} {count:>5} records")

    csv_rows = make_list_load_csv()
    csv_path = OUT / "event_leads_munich.csv"
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"  {'event_leads_munich.csv':<26} {len(csv_rows):>5} rows")

    print(f"\nFixtures written to {OUT}")
    print(f"Pipeline targets: {targets['quarterly_pipeline_target_usd']}")


if __name__ == "__main__":
    main()
