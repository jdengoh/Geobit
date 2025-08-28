"""
Lightweight mapping from detected jargon -> semantic tags.

Why tags?
- The Planner emits both a natural-language query and machine-usable tags.
- Retrieval Agent can use tags to *filter* (must_tags) and *rerank* (nice_to_have_tags).
"""

from typing import Dict, Set

# Minimal taxonomy for hackathon; extend when needed
CANON = {
    "ASL": {"child_safety", "age_gating"},
    "SNOWCAP": {"child_safety", "policy_framework"},
    "PF": {"personalization", "recommendation"},
    "CUSTOMAPI": {"data_integration", "internal_api"},
    "XRAY": {"test_management", "qa_process"},
}

CRITICAL = {"child_safety", "age_gating", "personalization"}  # goes to must_tags

def jargon_to_tags(jargon_json: dict) -> Dict[str, Set[str]]:
    """
    Input: the Jargon Agent JSON dict you already have.
    Output: {"must": set(...), "nice": set(...)} for the Planner to include.

    Implementation notes:
    - We scan both detected_terms and searched_terms (covers DB and web-discovered jargon).
    - Unknown terms are ignored (Planner can still form generic queries).
    """
    tags: Set[str] = set()
    for bucket in ("detected_terms", "searched_terms"):
        for t in jargon_json.get(bucket, []):
            key = (t.get("term") or "").upper()
            tags |= CANON.get(key, set())

    must = {t for t in tags if t in CRITICAL}
    nice = tags - must
    return {"must": must, "nice": nice}