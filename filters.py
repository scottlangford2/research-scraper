"""
Keyword matching and exclusion patterns for RFP classification.

Unlike the team scraper, these are used to *tag* RFPs (keyword_match column),
not to drop them.  Every scraped RFP is stored regardless of match status.
"""

import re

# ---------------------------------------------------------------------------
# Keywords — aligned with Texas State team research interests
# ---------------------------------------------------------------------------

KEYWORDS = [
    # --- Langford: economic resilience, shocks, entrepreneurship ---
    "economic analysis", "economic impact", "economic development",
    "economic study", "economic resilience", "economic recovery",
    "fiscal analysis", "fiscal impact",
    "financial analysis", "tax analysis", "tax study",
    "budget analysis", "impact study", "impact analysis",
    "cost-benefit", "cost benefit", "feasibility study",
    "feasibility analysis", "econometric",
    "community resilience", "disaster recovery", "disaster impact",
    "hurricane recovery", "extreme weather",
    "entrepreneurship", "small business resilience", "small firm",
    "regional economic", "local economic",
    # --- Langford: health policy, opioid, banking access ---
    "opioid", "substance abuse", "public health assessment",
    "health impact", "health policy", "epidemiolog",
    "banking access", "financial desert", "bank branch",
    "community development financial", "CDFI",
    "childhood adversity", "adverse childhood",
    # --- Langford: data / research ---
    "data analysis", "data analytics", "statistical analysis",
    "statistical services", "research services", "market research",
    "survey research", "evaluation services",
    "quantitative analysis", "qualitative analysis",
    "demographic analysis", "demographic study",
    "forecast", "benchmarking",
    # --- Langford: consulting ---
    "consulting services", "advisory services", "professional services",
    "management consulting", "technical assistance",
    # --- Lane: sustainable transportation, EVs, transit planning ---
    "transportation planning", "transportation study",
    "transportation analysis", "transit planning", "transit study",
    "transit analysis", "multimodal transportation",
    "sustainable transportation", "electric vehicle",
    "autonomous vehicle", "connected vehicle",
    "shared mobility", "ride-share", "rideshare",
    "travel behavior", "travel demand",
    "bicycle", "bike plan", "pedestrian plan",
    "traffic study", "traffic analysis",
    "transportation policy", "transportation infrastructure",
    # --- Rangarajan: public management, HR, workforce, evaluation ---
    "public management", "public administration",
    "program evaluation", "policy analysis", "policy evaluation",
    "strategic planning",
    "workforce analysis", "workforce development", "workforce study",
    "workforce planning", "human resources",
    "personnel management", "employee engagement",
    "organizational assessment", "organizational development",
    "performance management", "performance measurement",
    "public sector innovation", "government innovation",
    "diversity equity inclusion", "DEI assessment",
    "cultural competence", "employee survey",
    "training and development", "professional development",
    "compensation study", "classification study",
    # --- Fields: resilient communities, climate, green infrastructure ---
    "climate adaptation", "climate resilience", "climate action plan",
    "resilience planning", "resilience study", "resilience assessment",
    "hazard mitigation", "disaster planning",
    "green infrastructure", "blue infrastructure",
    "sustainability plan", "sustainability assessment",
    "environmental planning", "environmental assessment",
    "complete streets", "active transportation",
    "trail planning", "greenway", "pedestrian infrastructure",
    "urban planning",
    "stormwater management", "flood mitigation",
    "land use planning", "comprehensive plan",
    # --- Vindis: AI in government, behavioral economics, leadership ---
    "artificial intelligence", "machine learning",
    "AI strategy", "AI implementation",
    "gamification", "behavioral economics",
    "behavioral insights", "nudge",
    "leadership development", "leadership training",
    "scenario planning", "decision support",
    "change management", "organizational change",
    "process improvement", "digital transformation",
    "technology assessment", "innovation strategy",
    # --- Mora: public finance, administrative law, education policy ---
    "public finance", "public budgeting", "government finance",
    "revenue administration", "tax policy", "fiscal policy",
    "administrative law", "regulatory compliance", "rulemaking",
    "education policy", "education assessment", "school finance",
    "higher education", "education reform", "academic program review",
    "state government", "local government",
    "intergovernmental relations",
    # --- Balanoff: org theory, ethics, emergency mgmt, digital govt ---
    "organizational theory", "organizational behavior",
    "organizational design",
    "international administration", "comparative administration",
    "ethics in government", "government ethics", "ethics training",
    "transparency", "performance accountability",
    "performance audit", "government accountability",
    "emergency management", "emergency preparedness",
    "crisis management", "continuity of operations",
    "digital government", "e-government", "government technology",
    "smart city",
    # --- IGI: government consulting, GIS, data services ---
    "GIS services", "GIS analysis", "geospatial analysis",
    "geospatial services", "mapping services", "spatial analysis",
    "data digitization", "records digitization", "document digitization",
    "data collection services", "data cleanup", "data migration",
    "process documentation", "process analysis", "process mapping",
    "business process", "workflow analysis",
    "policy evaluation", "policy review", "regulatory review",
    "government staffing", "staff augmentation",
    "third-party assessment", "independent assessment",
    "program review", "operational assessment", "operational review",
    "agency modernization", "government modernization",
    # --- Stewart: nonprofit management, leadership, capacity building ---
    "nonprofit management", "nonprofit organization",
    "nonprofit capacity", "nonprofit performance",
    "nonprofit leadership", "nonprofit sector",
    "nonprofit governance", "nonprofit board",
    "board diversity", "board development",
    "executive transition", "leadership transition",
    "fund development", "fundraising",
    "grant writing", "grant management",
    "volunteer management", "volunteer engagement",
    "organizational capacity", "capacity building",
    "nonprofit workforce", "nonprofit professional",
    "nonprofit resilience", "sector resilience",
    "charitable organization", "philanthropic",
    # --- Coggburn: public HRM, civil service reform, personnel management ---
    "personnel administration", "civil service",
    "civil service reform", "merit system", "merit pay",
    "employee classification", "position classification",
    "pay equity", "public sector employment",
    "public workforce", "HR reform", "HR modernization",
    "labor relations", "collective bargaining",
    "employee retention", "employee recruitment",
    # --- Diebold: retirement policy, pension finance, income security, aging ---
    "retirement policy", "retirement security",
    "retirement planning", "pension",
    "public pension", "pension finance",
    "income security", "income support",
    "social security", "retirement benefit",
    "aging policy", "aging services",
    "older adults", "elderly",
    "Medicare", "health insurance",
    "health economics", "cost-related nonadherence",
    "prescription drug", "self-employment",
    "labor force participation", "retirement decision",
    "claim age", "survivor benefit",
    # --- Bodkin: local govt, HRM, social equity, community engagement ---
    "local government management", "community engagement",
    "community asset", "collective action",
    "contingency management", "public integrity",
    "race and gender", "gender equity",
    "mentoring", "career development",
    # --- Harper-Anderson: economic development, entrepreneurship, workforce ---
    "entrepreneurial ecosystem", "business incubation",
    "business incubator", "labor market",
    "urban labor", "community wealth",
    "inclusive economy", "economic equity",
    "housing policy", "housing program",
    "minority business", "economic transformation",
    "economic sustainability",
    # --- Fryar: higher education policy, accountability, regional colleges ---
    "postsecondary education", "college access",
    "student success", "student equity",
    "regional college", "rural education",
    "education accountability", "education performance",
    "institutional leadership", "education governance",
    "organizational dynamics", "state governance",
    # --- Carlson: education policy, school choice, data-driven reform ---
    "school choice", "school closure",
    "English learner", "desegregation",
    "school reassignment", "data-driven reform",
    "education evaluation", "education research",
    "student achievement", "student learning",
    "housing voucher", "K-12 education", "school district",
    # --- Steuart: opioid policy, cannabis policy, Medicaid, health services ---
    "opioid use disorder", "opioid policy",
    "opioid treatment", "substance use disorder",
    "cannabis policy", "cannabis legalization",
    "marijuana policy", "drug policy",
    "Medicaid managed care", "health care utilization",
    "prescribing behavior", "health services research",
    "adolescent health", "young adult health",
    "behavioral health",
    # --- Coupet: efficiency, performance measurement, nonprofit, strategic mgmt ---
    "efficiency measurement", "productivity measurement",
    "organizational efficiency", "organizational economics",
    "nonprofit efficiency", "strategic management",
    "strategic partnership", "management science",
    "policy implementation", "public revenue",
    "government efficiency", "social impact",
    # --- Miao: disaster policy, climate resilience, public finance ---
    "disaster policy", "disaster management",
    "disaster aid", "disaster finance",
    "flood insurance", "property tax",
    "tax administration", "managed retreat",
    "vulnerable population", "climate technology",
    "technology policy",
    # --- Mughan: local govt finance, criminal justice, policing ---
    "local government finance", "fiscal federalism", "fiscal stress",
    "criminal justice policy", "fines and fees",
    "asset forfeiture", "revenue-motivated policing",
    "traffic citations", "policing technology",
    "local government consolidation",
    "municipal courts", "law enforcement",
    "housing market", "foreign buyer tax",
    "state and local finance",
    # --- Singla: municipal debt, fiscal distress, procurement ---
    "municipal debt", "municipal bankruptcy",
    "local government financial health", "fiscal distress",
    "interest rate swaps", "debt derivatives",
    "policing for profit",
    "state takeover", "local government takeover",
    "government procurement", "public procurement",
    "voter responsiveness", "fiscal signals",
    "municipal government", "city government",
    "financial condition", "financial well-being",
]

KEYWORD_PATTERN = re.compile(
    "|".join(re.escape(kw) for kw in KEYWORDS), re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Exclusion pattern — irrelevant RFPs
# ---------------------------------------------------------------------------

EXCLUDE_PATTERN = re.compile(
    r"conference|forum|symposium|summit|seminar|workshop|expo|gala|banquet|luncheon"
    r"|construction|paving|roofing|hvac|plumbing|electrical services"
    r"|fencing|mowing|janitorial|custodial"
    r"|sewing|textile|fabric|lining|tape"
    r"|ambulance|fire truck|tractor|mower"
    r"|food service|catering|cheese|meat|produce"
    r"|engineering services|civil engineering|structural engineering"
    r"|mechanical engineering|geotechnical engineering|engineering design"
    r"|engineering firm|architecture and engineering|A/E services"
    r"|surveying services|land surveying|topographic survey"
    r"|inspection services|materials testing",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_rfp(rfp: dict) -> tuple[bool, list[str]]:
    """Classify an RFP against research keywords.

    Returns (matches, matched_keywords).  Excluded RFPs get (False, []).
    """
    text = " ".join([
        rfp.get("title", ""),
        rfp.get("description", ""),
        rfp.get("agency", ""),
    ])

    if EXCLUDE_PATTERN.search(text):
        return False, []

    found = KEYWORD_PATTERN.findall(text)
    unique = list(dict.fromkeys(kw.lower() for kw in found))
    return bool(unique), unique
