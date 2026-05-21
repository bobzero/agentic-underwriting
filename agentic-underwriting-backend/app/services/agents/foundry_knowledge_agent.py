"""
Foundry-backed knowledge agent wrapper.
Uses the Foundry knowledge agent to retrieve and summarize regulatory content.
Returns the same shape used by existing callers (question, answer, citations, generatedAt, relevanceScore).
"""
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from app.services.agents.foundry_knowledge_agent_client import FoundryKnowledgeAgentClient

try:
    from dotenv import dotenv_values
except Exception:
    dotenv_values = None

logger = logging.getLogger(__name__)

_client: FoundryKnowledgeAgentClient | None = None
_client_key: tuple[str | None, str | None] | None = None
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _read_env(name: str) -> str | None:
    if dotenv_values is not None:
        try:
            value = dotenv_values(_ENV_PATH).get(name)
            if value:
                return value
        except Exception:
            pass

    value = os.getenv(name)
    return value if value else None


def _get_client() -> FoundryKnowledgeAgentClient | None:
    global _client
    global _client_key

    endpoint = _read_env("FOUNDRY_KNOWLEDGE_AGENT_ENDPOINT")
    agent_name = _read_env("FOUNDRY_KNOWLEDGE_AGENT_NAME")
    key = (endpoint, agent_name)

    if _client is not None and _client_key == key:
        return _client

    try:
        _client = FoundryKnowledgeAgentClient()
        _client_key = key
        return _client
    except Exception as exc:
        logger.warning(f"Foundry knowledge agent is not configured: {exc}")
        _client = None
        _client_key = key
        return None


def get_knowledge_insight(question: str, case_id: str = None, top_k: int = 3) -> Optional[Dict]:
    """Service wrapper for knowledge queries via Foundry knowledge agent."""
    if not question or not question.strip():
        return None

    try:
        client = _get_client()
        if client is None:
            return None

        logger.info(f"Knowledge query for case {case_id}: {question[:100]}")
        # The Foundry agent handles search+summary; top_k can be included in prompt if needed
        result = client.ask(question)

        # If the agent returns an empty answer, surface None to caller
        if not result or not result.answer:
            return None

        return {
            "question": result.question,
            "answer": result.answer,
            "citations": result.citations,
            "generatedAt": result.generatedAt or datetime.now(timezone.utc).isoformat(),
            "relevanceScore": result.relevanceScore,
        }
    except Exception as exc:
        logger.error(f"Knowledge agent error for case {case_id}: {exc}")
        return None
