from __future__ import annotations
from pathlib import Path
from copy import deepcopy
import json
from typing import Any, Optional
from app.config import settings

root = Path(settings.data_root)

_SAMPLE_CASES: dict[str, dict[str, Any]] = {
    "C-123": {
        "id": "C-123",
        "title": "123 Maple St, Springfield, TX",
        "lob": "Homeowners",
        "property": {
            "address": "123 Maple St, Springfield, TX",
            "yearBuilt": 2015,
            "sqft": 2200,
            "floodZone": "AE",
            "countyCode": "48201",
            "zipCode": "77002",
        },
        "coverage": {
            "type": "NFIP Flood",
            "limit": 350000,
            "deductible": 2500,
        },
        "summary": "Well-maintained single-family property in a known flood zone with complete documentation and no material underwriting blockers.",
        "support_bullets": [
            "Property details are complete and internally consistent.",
            "Requested coverage aligns with profile and occupancy.",
            "No disqualifying guideline flags detected.",
        ],
    },
    "C-456": {
        "id": "C-456",
        "title": "456 Oak Ave, Austin, TX",
        "lob": "Homeowners",
        "property": {
            "address": "456 Oak Ave, Austin, TX",
            "yearBuilt": 1998,
            "sqft": 2800,
            "floodZone": "A",
            "countyCode": "48453",
            "zipCode": "78701",
        },
        "coverage": {
            "type": "NFIP Flood",
            "limit": 500000,
            "deductible": 5000,
        },
        "summary": "Risk indicators are elevated due to prior-claim context and location, so manual underwriting review is recommended.",
        "support_bullets": [
            "Higher hazard profile requires closer review.",
            "Coverage request is above baseline limits.",
            "Additional supporting documentation is recommended.",
        ],
    },
    "C-789": {
        "id": "C-789",
        "title": "789 Pine Rd, Dallas, TX",
        "lob": "Homeowners",
        "property": {
            "address": "789 Pine Rd, Dallas, TX",
            "yearBuilt": 2008,
            "sqft": 1950,
            "floodZone": "X",
            "countyCode": "48113",
            "zipCode": "75201",
        },
        "coverage": {
            "type": "Homeowners Property",
            "limit": 300000,
            "deductible": 2000,
        },
        "summary": "Standard homeowners risk profile with moderate exposure and no immediate appetite conflicts.",
        "support_bullets": [
            "Property age and size are within expected ranges.",
            "Requested coverage is proportional to risk profile.",
            "No blocking compliance issues identified.",
        ],
    },
    "C-321": {
        "id": "C-321",
        "title": "Case C-321 - Auto-Bind",
        "decisionType": "AI_APPROVED",
        "lob": "Homeowners",
        "property": {
            "address": "321 River View Dr, Houston, TX",
            "yearBuilt": 2019,
            "sqft": 1800,
            "floodZone": "AE",
            "countyCode": "48201",
            "zipCode": "77003",
        },
        "coverage": {
            "type": "NFIP Flood",
            "limit": 250000,
            "deductible": 2000,
        },
        "summary": "AI decision qualifies this case for auto-bind based on favorable risk profile and clean controls.",
        "support_bullets": [
            "AI confidence exceeds auto-bind threshold.",
            "No critical guideline or compliance flags.",
            "Timeline and evidence trail are complete.",
        ],
        "aiDecision": {
            "outcome": "AUTO_BIND",
            "confidence": 0.93,
            "riskScore": 0.31,
            "decisionTimeSeconds": 54,
            "justification": "Low modeled risk with complete underwriting inputs and no policy conflicts.",
            "rulesVersion": "2026.05",
            "modelVersion": "risk-v2.3",
            "validatedAt": "2026-05-18T12:00:00Z",
            "complianceCheck": "PASSED",
            "timeline": [
                {
                    "id": "t1",
                    "step": "PREFILL",
                    "title": "Data prefill",
                    "description": "Collected property and policy inputs.",
                    "startedAt": "2026-05-18T12:00:00Z",
                    "completedAt": "2026-05-18T12:00:10Z"
                },
                {
                    "id": "t2",
                    "step": "ENRICH",
                    "title": "Risk enrichment",
                    "description": "Loaded geospatial and claims context.",
                    "startedAt": "2026-05-18T12:00:10Z",
                    "completedAt": "2026-05-18T12:00:24Z"
                },
                {
                    "id": "t3",
                    "step": "SCORE",
                    "title": "Risk scoring",
                    "description": "Calculated risk score and confidence.",
                    "startedAt": "2026-05-18T12:00:24Z",
                    "completedAt": "2026-05-18T12:00:40Z"
                },
                {
                    "id": "t4",
                    "step": "DECIDE",
                    "title": "Decision",
                    "description": "Applied rules and generated bind recommendation.",
                    "startedAt": "2026-05-18T12:00:40Z",
                    "completedAt": "2026-05-18T12:00:54Z"
                }
            ],
            "featureContributions": [
                {"name": "Elevation certificate", "impact": -0.22},
                {"name": "Claims-free history", "impact": -0.18},
                {"name": "Flood zone", "impact": 0.11}
            ],
            "auditRef": {
                "id": "AUD-C-321",
                "href": "/api/cases/C-321/ai-audit",
                "hash": "sha256:sample-c321"
            }
        }
    },
    "C-654": {
        "id": "C-654",
        "title": "Case C-654 - Auto-Bind",
        "decisionType": "AI_APPROVED",
        "lob": "Homeowners",
        "property": {
            "address": "654 Cedar Bend, San Antonio, TX",
            "yearBuilt": 2020,
            "sqft": 2050,
            "floodZone": "X",
            "countyCode": "48029",
            "zipCode": "78205",
        },
        "coverage": {
            "type": "Homeowners Property",
            "limit": 275000,
            "deductible": 2500,
        },
        "summary": "Case meets auto-bind criteria with strong confidence and no unresolved underwriting controls.",
        "support_bullets": [
            "Risk score is below auto-bind threshold.",
            "Guideline checks passed without escalation.",
            "Audit artifacts are available for review.",
        ],
        "aiDecision": {
            "outcome": "AUTO_BIND",
            "confidence": 0.9,
            "riskScore": 0.28,
            "decisionTimeSeconds": 61,
            "justification": "Property and coverage attributes are within appetite with no adverse indicators.",
            "rulesVersion": "2026.05",
            "modelVersion": "risk-v2.3",
            "validatedAt": "2026-05-18T12:05:00Z",
            "complianceCheck": "PASSED",
            "timeline": [
                {
                    "id": "u1",
                    "step": "PREFILL",
                    "title": "Data prefill",
                    "description": "Collected property and policy inputs.",
                    "startedAt": "2026-05-18T12:05:00Z",
                    "completedAt": "2026-05-18T12:05:12Z"
                },
                {
                    "id": "u2",
                    "step": "ENRICH",
                    "title": "Risk enrichment",
                    "description": "Loaded risk context and history.",
                    "startedAt": "2026-05-18T12:05:12Z",
                    "completedAt": "2026-05-18T12:05:28Z"
                },
                {
                    "id": "u3",
                    "step": "SCORE",
                    "title": "Risk scoring",
                    "description": "Calculated risk score and confidence.",
                    "startedAt": "2026-05-18T12:05:28Z",
                    "completedAt": "2026-05-18T12:05:46Z"
                },
                {
                    "id": "u4",
                    "step": "DECIDE",
                    "title": "Decision",
                    "description": "Applied rules and produced bind decision.",
                    "startedAt": "2026-05-18T12:05:46Z",
                    "completedAt": "2026-05-18T12:06:01Z"
                }
            ],
            "featureContributions": [
                {"name": "New construction", "impact": -0.2},
                {"name": "Low hazard zone", "impact": -0.19},
                {"name": "Coverage ratio", "impact": 0.08}
            ],
            "auditRef": {
                "id": "AUD-C-654",
                "href": "/api/cases/C-654/ai-audit",
                "hash": "sha256:sample-c654"
            }
        }
    },
}

_SAMPLE_AI_AUDITS: dict[str, dict[str, Any]] = {
    "C-321": {
        "caseId": "C-321",
        "generatedAt": "2026-05-18T12:00:54Z",
        "rulesVersion": "2026.05",
        "modelVersion": "risk-v2.3",
        "steps": [
            {"step": "PREFILL", "status": "done"},
            {"step": "ENRICH", "status": "done"},
            {"step": "SCORE", "status": "done"},
            {"step": "DECIDE", "status": "done"}
        ],
        "controls": {"compliance": "PASSED"}
    },
    "C-654": {
        "caseId": "C-654",
        "generatedAt": "2026-05-18T12:06:01Z",
        "rulesVersion": "2026.05",
        "modelVersion": "risk-v2.3",
        "steps": [
            {"step": "PREFILL", "status": "done"},
            {"step": "ENRICH", "status": "done"},
            {"step": "SCORE", "status": "done"},
            {"step": "DECIDE", "status": "done"}
        ],
        "controls": {"compliance": "PASSED"}
    }
}

def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_case(case_id: str) -> Optional[dict]:
    file_case = _load_json(root / "cases" / f"{case_id}.json")
    if file_case:
        return file_case
    return None

def list_cases() -> list[dict]:
    cases_dir = root / "cases"
    if not cases_dir.exists():
        return []
    items: list[dict] = []
    for path in cases_dir.glob("*.json"):
        data = _load_json(path)
        if data:
            items.append(data)
    return items


def list_case_queue_items() -> list[dict]:
    items: list[dict] = []
    for case in list_cases():
        case_id = case.get("id")
        if not case_id:
            continue

        title = case.get("title") or case.get("property", {}).get("address") or f"Case {case_id}"
        status = case.get("status")
        if status not in {"Pending", "Needs Review", "AI Approved"}:
            status = "AI Approved" if case.get("decisionType") == "AI_APPROVED" else "Pending"

        submission_date = case.get("submissionDate") or "1970-01-01T00:00:00Z"
        risk_flags = case.get("riskFlags") or []

        items.append(
            {
                "id": case_id,
                "name": f"Case {case_id} - {title}",
                "status": status,
                "submissionDate": submission_date,
                "riskFlags": risk_flags,
            }
        )

    return items

def get_memories(case_id: str) -> list[dict]:
    data = _load_json(root / "memories" / f"{case_id}.json")
    return data or []

def get_decisions(case_id: str) -> list[dict]:
    # In sprint 1, a single decision example is stored in one file; listify
    d = _load_json(root / "decisions" / f"D-987.json")
    return [d] if d else []


def get_ai_audit(case_id: str) -> Optional[dict]:
    file_audit = _load_json(root / "ai_audits" / f"{case_id}.json")
    if file_audit:
        return file_audit
    return None
