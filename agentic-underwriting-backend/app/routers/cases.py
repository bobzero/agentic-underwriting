from datetime import datetime, timezone
from copy import deepcopy

from fastapi import APIRouter, HTTPException

from app.models.schemas import AiDecision, CaseContext, CaseQueueResponse, CaseViewModel
from app.services.data_access.local_repo import get_case, get_ai_audit, list_case_queue_items
from app.services.conductor import build_case_view

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=CaseQueueResponse)
def list_case_queues():
    queue_items = list_case_queue_items()
    submission = [
        item for item in queue_items if item.get("status") in {"Pending", "Needs Review"}
    ]
    ai_approved = [item for item in queue_items if item.get("status") == "AI Approved"]

    submission.sort(key=lambda item: item.get("submissionDate", ""), reverse=True)
    ai_approved.sort(key=lambda item: item.get("submissionDate", ""), reverse=True)

    return CaseQueueResponse(submissionQueue=submission, aiApprovedQueue=ai_approved)

@router.get("/{case_id}/view", response_model=CaseViewModel)
def get_case_view(case_id: str):
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    ctx = CaseContext(case_id=case_id, lob=case.get("lob","Homeowners"))
    return build_case_view(ctx)


@router.get("/{case_id}/ai-audit")
def get_case_ai_audit(case_id: str):
    audit = get_ai_audit(case_id)
    if not audit:
        raise HTTPException(status_code=404, detail="AI audit not available")
    return audit


@router.post("/{case_id}/ai/rerun", response_model=AiDecision)
def rerun_ai_decision(case_id: str):
    case = get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    ai_decision = case.get("aiDecision")
    if not ai_decision:
        raise HTTPException(status_code=400, detail="AI decision not available for this case")

    updated = deepcopy(ai_decision)
    now_iso = datetime.now(timezone.utc).isoformat()
    updated["validatedAt"] = now_iso
    updated["decisionTimeSeconds"] = max(30, int(updated.get("decisionTimeSeconds", 180)))
    return updated
