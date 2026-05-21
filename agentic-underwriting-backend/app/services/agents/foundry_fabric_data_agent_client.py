"""
Foundry-backed client for Fabric-style Data Agent calls.
Returns the same structured schema as the legacy Fabric client.
"""
import json
import logging
import os
from pathlib import Path
import re
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from openai import AzureOpenAI

try:
    from dotenv import dotenv_values, load_dotenv
    load_dotenv()
except Exception:
    dotenv_values = None
    pass

logger = logging.getLogger(__name__)
# Ensure INFO-level logs surface for this client
logger.setLevel(logging.INFO)

# Prefer attaching to uvicorn.error handlers if they exist; otherwise add a simple stdout handler
_uvicorn_err = logging.getLogger("uvicorn.error")
if _uvicorn_err.handlers:
    for _h in _uvicorn_err.handlers:
        logger.addHandler(_h)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

# Prevent double logging; we directly attach handlers
logger.propagate = False
_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _read_env(name: str, default: str | None = None) -> str | None:
    """Prefer backend .env value, then process env, then default."""
    if dotenv_values is not None:
        try:
            value = dotenv_values(_ENV_PATH).get(name)
            if value:
                return value
        except Exception:
            pass

    value = os.getenv(name)
    if value:
        return value
    return default


class FabricAgentResponse(BaseModel):
    """Structured response model compatible with the legacy Fabric Data Agent."""

    status: str = Field(..., description="Response status: success, no_data, or error")
    columns: int = Field(..., description="Number of columns in the response")
    rows: int = Field(..., description="Number of rows in the response")
    comments: str = Field(default="", description="Agent's reasoning or context")
    summary: str = Field(default="", description="Human-readable narrative insight")
    response: List[Dict[str, Any]] = Field(default_factory=list, description="Array of data rows")


class FoundryFabricDataAgentClient:
    """Client that calls a Foundry Agent acting as a pass-through to Fabric Data Agent."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        agent_name: Optional[str] = None,
        credential: Optional[Any] = None,
    ) -> None:
        # Use agent-specific env vars so multiple Foundry agents can coexist
        self.endpoint = endpoint or os.getenv("FOUNDRY_FABRIC_AGENT_ENDPOINT")
        self.agent_name = agent_name or os.getenv("FOUNDRY_FABRIC_AGENT_NAME")
        if not self.endpoint:
            raise ValueError("FOUNDRY_FABRIC_AGENT_ENDPOINT is required")
        if not self.agent_name:
            raise ValueError("FOUNDRY_FABRIC_AGENT_NAME is required")

        # self.credential = credential or DefaultAzureCredential()
        # Exclude interactive browser credential for App Service compatibility
        self.credential = credential or DefaultAzureCredential(
            exclude_interactive_browser_credential=True,
            exclude_shared_token_cache_credential=True,
            exclude_visual_studio_code_credential=True
        )
        
        self.project_client = AIProjectClient(
            endpoint=self.endpoint,
            credential=self.credential,
        )
        self.agent = self._resolve_agent(self.agent_name)

        cache_enabled_value = (_read_env("FOUNDRY_FABRIC_PROMPT_CACHE_ENABLED", "true") or "true").strip().lower()
        self.prompt_cache_enabled = cache_enabled_value in {"1", "true", "yes", "on"}

        ttl_value = _read_env("FOUNDRY_FABRIC_PROMPT_CACHE_TTL_SECONDS", "432000") or "432000"
        try:
            self.prompt_cache_ttl_seconds = max(0, int(ttl_value))
        except ValueError:
            self.prompt_cache_ttl_seconds = 432000

        cache_dir_value = _read_env("FOUNDRY_FABRIC_PROMPT_CACHE_DIR", "data/foundry_prompt_cache") or "data/foundry_prompt_cache"
        self.prompt_cache_dir = Path(cache_dir_value)
        if self.prompt_cache_enabled:
            self.prompt_cache_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_agent(self, agent_name: str):
        try:
            agent = self.project_client.agents.get(agent_name=agent_name)
            logger.info(f"Foundry Fabric agent resolved: {agent.name}")
            return agent
        except Exception as exc:
            logger.error(f"Unable to resolve Foundry Fabric agent '{agent_name}': {exc}")
            raise

    # def _get_openai_client(self):
    #     try:
    #         return self.project_client.get_openai_client()
    #     except Exception as exc:
    #         logger.error(f"Failed to obtain Foundry OpenAI client: {exc}")
    #         raise

    def _get_openai_client(self):
        openai_api_version = _read_env("OPENAI_API_VERSION")

        # Prefer the SDK-provided OpenAI client for project-scoped endpoints.
        # If this fails (older environment/package mismatch), fall back to explicit token flow.
        try:
            return self.project_client.get_openai_client(api_version=openai_api_version)
        except Exception as exc:
            logger.warning(f"Falling back to manual AzureOpenAI client creation: {exc}")

        foundry_openai_scope = _read_env("FOUNDRY_OPENAI_SCOPE", "https://ai.azure.com/.default")

        def token_provider() -> str:
            return self.credential.get_token(foundry_openai_scope).token

        base_url = self.endpoint.rstrip("/") + "/openai"
        return AzureOpenAI(
            azure_ad_token_provider=token_provider,
            base_url=base_url,
            api_version=openai_api_version,
        )

    def ask_structured(self, question: str, timeout: int = 120) -> FabricAgentResponse:
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        cached = self._get_cached_prompt_response(question)
        if cached is not None:
            return cached

        try:
            client = self._get_openai_client()
            start = time.perf_counter()
            response = client.responses.create(
                input=[{"role": "user", "content": question}],
                extra_body={"agent": {"name": self.agent.name, "type": "agent_reference"}},
                timeout=timeout,
            )
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            output_text = getattr(response, "output_text", None)
            if not output_text:
                print(f"[FABRIC ERROR] Foundry agent returned empty output_text for question: {question[:200]}", flush=True)
                logger.error("Foundry agent returned empty output_text")
                return FabricAgentResponse(
                    status="error",
                    columns=0,
                    rows=0,
                    comments="Empty response from Foundry agent",
                    summary="",
                    response=[],
                )

            try:
                parsed = json.loads(output_text)
            except json.JSONDecodeError as exc:
                print(f"[FABRIC ERROR] Failed to parse JSON from Foundry agent: {exc}. Raw: {output_text[:500]}", flush=True)
                logger.error(f"Failed to parse JSON from Foundry agent: {exc}. Raw: {output_text}")
                return FabricAgentResponse(
                    status="error",
                    columns=0,
                    rows=0,
                    comments=f"Invalid JSON from agent: {exc}",
                    summary="",
                    response=[],
                )

            try:
                # Log success with basic call metadata
                response_id = getattr(response, "id", None)
                model = FabricAgentResponse(**parsed)
                logger.info(
                    "Foundry agent call succeeded: agent=%s response_id=%s duration_ms=%s columns=%s rows=%s",
                    self.agent.name,
                    response_id,
                    elapsed_ms,
                    model.columns,
                    model.rows,
                )
                self._set_cached_prompt_response(question, model)
                return model
            except Exception as exc:
                print(f"[FABRIC ERROR] Parsed JSON did not match schema: {exc}. Parsed: {str(parsed)[:500]}", flush=True)
                logger.error(f"Parsed JSON did not match schema: {exc}. Parsed: {parsed}")
                return FabricAgentResponse(
                    status="error",
                    columns=0,
                    rows=0,
                    comments=f"Schema validation failed: {exc}",
                    summary="",
                    response=[],
                )

        except Exception as exc:
            details = _format_exception_details(exc)
            request_id = _extract_request_id(details)
            log_suffix = f" request_id={request_id}" if request_id else ""
            print(
                f"[FABRIC ERROR] Foundry agent call failed:{log_suffix} endpoint={self.endpoint} "
                f"agent={self.agent.name} | {details}",
                flush=True,
            )
            logger.error(
                f"Foundry agent call failed:{log_suffix} endpoint={self.endpoint} agent={self.agent.name} | {details}"
            )
            return FabricAgentResponse(
                status="error",
                columns=0,
                rows=0,
                comments=f"Error: {exc}",
                summary="",
                response=[],
            )

    def get_raw_response(self, question: str, timeout: int = 120) -> Dict[str, Any]:
        client = self._get_openai_client()
        response = client.responses.create(
            input=[{"role": "user", "content": question}],
            extra_body={"agent": {"name": self.agent.name, "type": "agent_reference"}},
            timeout=timeout,
        )
        return response.model_dump() if hasattr(response, "model_dump") else dict(response)

    def _prompt_cache_key(self, question: str) -> str:
        normalized = question.strip()
        raw_key = f"{self.endpoint}|{self.agent.name}|{normalized}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _prompt_cache_file(self, question: str) -> Path:
        return self.prompt_cache_dir / f"{self._prompt_cache_key(question)}.json"

    def _get_cached_prompt_response(self, question: str) -> Optional[FabricAgentResponse]:
        if not self.prompt_cache_enabled or self.prompt_cache_ttl_seconds <= 0:
            return None

        cache_file = self._prompt_cache_file(question)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)

            expires_at_raw = payload.get("expires_at")
            if not isinstance(expires_at_raw, str):
                return None

            expires_at = datetime.fromisoformat(expires_at_raw)
            if datetime.now(timezone.utc) > expires_at:
                cache_file.unlink(missing_ok=True)
                return None

            response_data = payload.get("response_data")
            if not isinstance(response_data, dict):
                return None

            model = FabricAgentResponse(**response_data)
            logger.info("Foundry prompt cache hit: agent=%s key=%s", self.agent.name, cache_file.stem[:12])
            return model
        except Exception as exc:
            logger.warning("Foundry prompt cache read failed: %s", exc)
            return None

    def _set_cached_prompt_response(self, question: str, response: FabricAgentResponse) -> None:
        if not self.prompt_cache_enabled or self.prompt_cache_ttl_seconds <= 0:
            return

        if response.status not in {"success", "no_data"}:
            return

        cache_file = self._prompt_cache_file(question)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self.prompt_cache_ttl_seconds)
        payload = {
            "cached_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "response_data": response.model_dump(),
        }

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            logger.info("Foundry prompt cache write: agent=%s key=%s ttl_s=%s", self.agent.name, cache_file.stem[:12], self.prompt_cache_ttl_seconds)
        except Exception as exc:
            logger.warning("Foundry prompt cache write failed: %s", exc)


def _extract_request_id(message: str) -> Optional[str]:
    """Attempt to pull requestId out of an error message."""
    if not message:
        return None
    match = re.search(r'"requestId"\s*:\s*"([^"]+)"', message)
    return match.group(1) if match else None


def _format_exception_details(exc: Exception) -> str:
    """Best-effort extraction of full error details from SDK/OpenAI exceptions."""
    parts: List[str] = [str(exc)]

    code = getattr(exc, "code", None)
    if code:
        parts.append(f"code={code}")

    status_code = getattr(exc, "status_code", None)
    if status_code:
        parts.append(f"status_code={status_code}")

    response = getattr(exc, "response", None)
    if response is not None:
        req_id = getattr(response, "request_id", None) or getattr(response, "x_ms_request_id", None)
        if req_id:
            parts.append(f"response_request_id={req_id}")

    body = getattr(exc, "body", None)
    if body:
        parts.append(f"body={body}")

    return " | ".join(parts)
