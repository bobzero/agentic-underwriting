"""
Foundry-backed Fabric Data Agent helpers (Functions A–E).
Mirrors fabric_data_agent.py but routes calls through the Foundry agent client.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict

from app.services.agents.foundry_fabric_data_agent_client import (
    FoundryFabricDataAgentClient,
)

try:
    from dotenv import dotenv_values, load_dotenv
    load_dotenv()
except Exception:
    dotenv_values = None
    pass

logger = logging.getLogger(__name__)
_client: FoundryFabricDataAgentClient | None = None
_client_key: tuple[str | None, str | None] | None = None
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _read_env(name: str) -> str | None:
    """Prefer value from backend .env, then fall back to process env."""
    if dotenv_values is not None:
        try:
            value = dotenv_values(_ENV_PATH).get(name)
            if value:
                return value
        except Exception:
            pass

    value = os.getenv(name)
    return value if value else None


def _get_client() -> FoundryFabricDataAgentClient | None:
    """Create or refresh the Foundry client when env values change."""
    global _client
    global _client_key

    endpoint = _read_env("FOUNDRY_FABRIC_AGENT_ENDPOINT")
    agent_name = _read_env("FOUNDRY_FABRIC_AGENT_NAME")
    key = (endpoint, agent_name)

    if _client is not None and _client_key == key:
        return _client

    if not endpoint or not agent_name:
        logger.warning("Foundry Fabric client is not configured (missing endpoint and/or agent name)")
        _client = None
        _client_key = key
        return None

    try:
        _client = FoundryFabricDataAgentClient(endpoint=endpoint, agent_name=agent_name)
        _client_key = key
        logger.info("Foundry Fabric client (re)initialized with current env config")
        return _client
    except Exception as exc:
        logger.error(f"Failed to initialize Foundry Fabric client: {exc}")
        _client = None
        _client_key = key
        return None


# =============================================================================
# A) Property & Support Summary
# =============================================================================
def property_support_summary(top_n: int = 7, state: str = "TX", countyCode: str = "48229") -> Dict[str, Any]:
    """
    Summarize recent NFIP claims and flood exposure for UI summary highlights.
    Returns a structured dict identical to the legacy Fabric Data Agent.
    """
    client = _get_client()
    if client is None:
        print("[FABRIC ERROR] Client is None - initialization failed at startup", flush=True)
        return {"status": "error", "columns": 0, "rows": 0, "comments": "Client initialization failed", "summary": "", "response": []}
    prompt = (
        f"Summarize recent NFIP claims and flood exposure for 15 counties where paid amount is not $0 for {state} state;"
    )
    print(f"[FABRIC CALL] Function A: prompt={prompt[:150]}", flush=True)
    result = client.ask_structured(prompt)
    print(f"[FABRIC RESULT] Function A: status={result.status}, rows={result.rows}, comments={result.comments[:200] if result.comments else ''}", flush=True)
    return result.model_dump()


# =============================================================================
# B) Decisioning Intelligence
# =============================================================================
def decisioning_claim_freq_avg_loss_zip(zip_code: str = "48141", years: int = 10) -> Dict[str, Any]:
    """Claim frequency and average loss by ZIP over the past N years."""
    client = _get_client()
    if client is None:
        print("[FABRIC ERROR] Client is None - initialization failed at startup", flush=True)
        return {"status": "error", "columns": 0, "rows": 0, "comments": "Client initialization failed", "summary": "", "response": []}
    prompt = (
        "Return a table with columns zip, loss_year, claims_count, avg_loss "
        "where claims_count = COUNT(*) and avg_loss = AVG(total_paid) "
        f"from dbo.fema_nfip_claims_fact_gold where zip = '{zip_code}' "
        f"and loss_year >= YEAR(GETDATE()) - {years} "
        "group by zip, loss_year "
        "order by loss_year desc."
    )
    result = client.ask_structured(prompt)
    return result.model_dump()


# =============================================================================
# C) Risk Assessment
# =============================================================================
def risk_assessment_severity_and_large_losses(county_code: str = "26163", min_loss: int = 1) -> Dict[str, Any]:
    """Severity comparison and large-loss drilldown for the Risk Assessment tab."""
    client = _get_client()
    if client is None:
        print("[FABRIC ERROR] Client is None - initialization failed at startup", flush=True)
        return {"severity": {"status": "error"}, "large_losses": {"status": "error"}}
    prompt_severity = (
        f"show Average Claim Severity county vs state for county code {county_code} by year for the latest 10 years;"
    )
    prompt_large_losses = (
        f"list last 10 claims over {min_loss} for county code {county_code};"
    )

    severity_result = client.ask_structured(prompt_severity)
    large_losses_result = client.ask_structured(prompt_large_losses)
    return {
        "severity": severity_result.model_dump(),
        "large_losses": large_losses_result.model_dump(),
    }


# =============================================================================
# D) AI Explainability
# =============================================================================
def explainability_5yr_claim_count_by_county(state: str = "TX", county_code: str = "48157") -> Dict[str, Any]:
    """Five-year claim counts by county for a state (top 10 rows)."""
    client = _get_client()
    if client is None:
        print("[FABRIC ERROR] Client is None - initialization failed at startup", flush=True)
        return {"status": "error", "columns": 0, "rows": 0, "comments": "Client initialization failed", "summary": "", "response": []}

    prompt = (
        f"Fetch 5-year claim count by county code for {state} state. List top 10 rows only;"
    )
    result = client.ask_structured(prompt)
    return result.model_dump()


def explainability_avg_loss_rank_tx(state: str = "TX") -> Dict[str, Any]:
    """Average loss ranking across state counties (top 15)."""
    client = _get_client()
    if client is None:
        print("[FABRIC ERROR] Client is None - initialization failed at startup", flush=True)
        return {"status": "error", "columns": 0, "rows": 0, "comments": "Client initialization failed", "summary": "", "response": []}

    prompt = (
        f"provide average loss ranked across {state} counties. List top 15 rows only;"
    )
    result = client.ask_structured(prompt)
    return result.model_dump()


# =============================================================================
# E) Agentic AI Action Timeline (Enrichment Snapshot)
# =============================================================================
def action_timeline_enrichment_snapshot(state: str = "TX", county_code: str = "48157") -> Dict[str, Any]:
    """County-year risk features for timeline enrichment snapshot."""
    client = _get_client()
    if client is None:
        print("[FABRIC ERROR] Client is None - initialization failed at startup", flush=True)
        return {"status": "error", "columns": 0, "rows": 0, "comments": "Client initialization failed", "summary": "", "response": []}

    prompt = (
        "Return a table with columns state, county_code, loss_year, paid_total, claims_count, avg_paid_per_claim "
        "from dbo.fema_nfip_geo_year_gold "
        f"where state = '{state.upper()}' and county_code = '{county_code}' "
        "order by loss_year desc "
        "offset 0 rows fetch next 10 rows only;"
    )
    result = client.ask_structured(prompt)
    return result.model_dump()


if __name__ == "__main__":
    print("\n=== E) Action Timeline Enrichment Snapshot (TX, county 48157) ===")
    e_rows = action_timeline_enrichment_snapshot(state="TX", county_code="48157")
    print("Raw response: \n", e_rows)
