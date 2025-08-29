"""
Lightweight mapping from detected jargon -> semantic tags.

Why tags?
- The Planner emits both a natural-language query and machine-usable tags.
- Retrieval Agent can use tags to *filter* (must_tags) and *rerank* (nice_to_have_tags).
"""

from typing import Dict, Set, List 
import re


"""
Tag derivation used by the Analysis Planner.
- Maps jargon terms -> semantic tags
- Derives extra tags from free text (jurisdiction, curfew, minors, etc.)
- Returns *sorted lists* to keep prompts stable across runs
"""

# Extend taxonomy
CANON = {
    "ASL": {"child_safety", "age_gating"},
    "SNOWCAP": {"child_safety", "policy_framework"},
    "PF": {"personalization", "recommendation"},
    "CUSTOMAPI": {"data_integration", "internal_api"},
    "XRAY": {"test_management", "qa_process"},
    # new:
    "GH": {"geo_enforcement", "jurisdiction"},
    "ECHOTRACE": {"audit_logging", "traceability"},
    "SHADOWMODE": {"silent_rollout", "analytics_only"},
    # laws (bucket via searched_terms)
    "UTAH SOCIAL MEDIA REGULATION ACT": {"jurisdiction_ut", "state_law", "minor_protection"},
}

CRITICAL = {"child_safety", "age_gating", "personalization", "jurisdiction_ut"}

# naive text tagger (fast + good enough for hackathon)
PATTERNS = [
    (r"\butah\b", {"jurisdiction_ut", "state_law"}),
    (r"\bcurfew\b", {"curfew"}),
    (r"\bunder[-\s]?18\b|\bminor[s]?\b", {"minor_protection"}),
    (r"\blogin restriction\b|\blogin\b", {"login_restriction"}),
]

def _norm(s: str) -> str:
    return (s or "").strip().upper()

def _sorted(xs: Set[str]) -> List[str]:
    return sorted(xs)

def jargon_to_tags(jargon_json: dict) -> Dict[str, List[str]]:
    """
    Scan detected_terms + searched_terms and map to tags.
    Return stable (sorted) lists for must/nice to reduce LLM variance.
    """
    tags: Set[str] = set()
    for bucket in ("detected_terms", "searched_terms"):
        for t in jargon_json.get(bucket, []):
            key = _norm(t.get("term"))
            tags |= CANON.get(key, set())

    must = {t for t in tags if t in CRITICAL}
    nice = tags - must
    return {"must": _sorted(must), "nice": _sorted(nice)}

def derive_text_tags(text: str) -> Dict[str, List[str]]:
    """
    Pull additional tags directly from standardized_name/description text.
    """
    tags: Set[str] = set()
    t = (text or "").lower()
    for rx, add in PATTERNS:
        if re.search(rx, t):
            tags |= add
    must = {t for t in tags if t in CRITICAL}
    nice = tags - must
    return {"must": _sorted(must), "nice": _sorted(nice)}
def merge_tag_sets(a, b):
    am, an = set(a.get("must", [])), set(a.get("nice", []))
    bm, bn = set(b.get("must", [])), set(b.get("nice", []))
    must = am | bm
    nice = (an | bn) - must
    return {"must": sorted(must), "nice": sorted(nice)}
