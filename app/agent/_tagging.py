from typing import Dict, List, Set, Any
import re

# Canonical mappings
CANON = {
    "ASL": {"child_safety", "age_gating"},
    "SNOWCAP": {"child_safety", "policy_framework"},
    "PF": {"personalization", "recommendation"},
    "CUSTOMAPI": {"data_integration", "internal_api"},
    "XRAY": {"test_management", "qa_process"},
    "GH": {"geo_enforcement", "jurisdiction"},
    "ECHOTRACE": {"audit_logging", "traceability"},
    "SHADOWMODE": {"silent_rollout", "analytics_only"},
    "UTAH SOCIAL MEDIA REGULATION ACT": {"jurisdiction_ut", "state_law", "minor_protection"},
}
CRITICAL = {"child_safety", "age_gating", "personalization", "jurisdiction_ut"}

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

def _iter_terms(jargon: object) -> List[str]:
    """
    Duck-type over either:
      - a Pydantic model with .detected_terms / .searched_terms (JargonQueryResult), or
      - a dict shaped like {'detected_terms': [...], 'searched_terms': [...]}, or
      - None.
    """
    out: List[str] = []
    if jargon is None:
        return out

    # Pydantic model case
    if hasattr(jargon, "detected_terms") and hasattr(jargon, "searched_terms"):
        for t in getattr(jargon, "detected_terms") or []:
            out.append(getattr(t, "term", "") or "")
        for t in getattr(jargon, "searched_terms") or []:
            out.append(getattr(t, "term", "") or "")

    # Dict case
    elif isinstance(jargon, dict):
        for t in (jargon.get("detected_terms") or []):
            out.append((t.get("term") or ""))
        for t in (jargon.get("searched_terms") or []):
            # searched terms may be richer objects (term/definition/sources)
            out.append((t.get("term") or ""))

    return [s for s in out if s]  # drop empties

def jargon_to_tags(jargon: object) -> Dict[str, List[str]]:
    tags: Set[str] = set()
    for term in _iter_terms(jargon):
        tags |= CANON.get(_norm(term), set())
    must = {t for t in tags if t in CRITICAL}
    nice = tags - must
    return {"must": _sorted(must), "nice": _sorted(nice)}

def derive_text_tags(text: str) -> Dict[str, List[str]]:
    tags: Set[str] = set()
    t = (text or "").lower()
    for rx, add in PATTERNS:
        if re.search(rx, t):
            tags |= add
    must = {t for t in tags if t in CRITICAL}
    nice = tags - must
    return {"must": _sorted(must), "nice": _sorted(nice)}

def merge_tag_sets(a: Dict[str, List[str]], b: Dict[str, List[str]]) -> Dict[str, List[str]]:
    am, an = set(a.get("must", [])), set(a.get("nice", []))
    bm, bn = set(b.get("must", [])), set(b.get("nice", []))
    must = am | bm
    nice = (an | bn) - must
    return {"must": sorted(must), "nice": sorted(nice)}