# VERIFIED: imports — anthropic + stdlib
# VERIFIED: downstream — called by all agents in extraction/p1_extraction/agents/
# VERIFIED: config constants — LLM_MAX_RETRIES, LLM_RETRY_BASE_DELAY_SECONDS, LLM_DEFAULT_MODEL, LLM_DEFAULT_MAX_TOKENS
"""
Component: SYS_EXTRACTION.LLM_CLIENT
Spec: SYS_EXTRACTION_COMPLETE.md lines 292-310 (agent architecture overview)
      IMPLEMENTATION_BLUEPRINT Part 4 item 1 (LLM wrapper needs)
Formulas: None
Reads: Nothing (external API wrapper)
Writes: Nothing (returns validated JSON)
Gates: None
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from crci.shared import config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClientError(Exception):
    """Base exception for LLM client errors."""


class LLMResponseValidationError(LLMClientError):
    """Raised when response fails schema validation."""


class LLMAPIError(LLMClientError):
    """Raised when API call fails after all retries."""


class LLMClient:
    """Single-provider Claude API wrapper.

    Calls Anthropic API with pinned model ID, validates responses
    against Pydantic schemas, retries on transient errors, and
    tracks token usage / cost.
    """

    # HTTP status codes that trigger retry
    _RETRYABLE_STATUS_CODES = {429, 502, 503, 529}

    def __init__(
        self,
        model_id: str = config.LLM_DEFAULT_MODEL,
        max_tokens: int = config.LLM_DEFAULT_MAX_TOKENS,
        max_retries: int = config.LLM_MAX_RETRIES,
        retry_base_delay: float = config.LLM_RETRY_BASE_DELAY_SECONDS,
        api_key: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._api_key = api_key
        self._client: Any | None = None
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_calls = 0

    def _get_client(self) -> Any:
        """Lazily initialize the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise LLMClientError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                ) from exc
            kwargs: dict[str, Any] = {}
            if self._api_key is not None:
                kwargs["api_key"] = self._api_key
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def call(
        self,
        prompt: str,
        response_schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.0,
        model_id: str | None = None,
    ) -> T:
        """Call Claude API and return validated response.

        Args:
            prompt: The user prompt string.
            response_schema: Pydantic model class to validate response against.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature (default 0 for determinism).
            model_id: Optional model override. If None, uses self.model_id.
                     Use with model_router.route_task() for cost optimization.

        Returns:
            Validated instance of response_schema.

        Raises:
            LLMResponseValidationError: If response fails schema validation.
            LLMAPIError: If API call fails after all retries.
        """
        effective_model = model_id if model_id is not None else self.model_id
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        start_time = time.monotonic()

        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": effective_model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system_prompt is not None:
            kwargs["system"] = system_prompt

        response = self._call_with_retry(kwargs, prompt_hash)
        latency_ms = (time.monotonic() - start_time) * 1000

        # Check for output truncation
        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "max_tokens":
            logger.warning(
                "LLM response TRUNCATED (max_tokens=%d reached): "
                "model=%s prompt_hash=%s — increase LLM_DEFAULT_MAX_TOKENS",
                self.max_tokens,
                effective_model,
                prompt_hash,
            )

        # Extract text content from response
        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text += block.text

        # Count tokens
        prompt_tokens = response.usage.input_tokens
        completion_tokens = response.usage.output_tokens
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_calls += 1

        logger.info(
            "LLM call completed: model=%s prompt_hash=%s "
            "prompt_tokens=%d completion_tokens=%d latency_ms=%.0f",
            effective_model,
            prompt_hash,
            prompt_tokens,
            completion_tokens,
            latency_ms,
        )

        # Parse and validate JSON response
        validated = self._parse_and_validate(raw_text, response_schema)
        return validated

    def _call_with_retry(self, kwargs: dict[str, Any], prompt_hash: str) -> Any:
        """Execute API call with exponential backoff retry on transient errors."""
        try:
            import anthropic
        except ImportError as exc:
            raise LLMClientError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            ) from exc

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                client = self._get_client()
                return client.messages.create(**kwargs)
            except anthropic.RateLimitError as exc:
                last_error = exc
                logger.warning(
                    "Rate limited (attempt %d/%d) prompt_hash=%s: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    prompt_hash,
                    exc,
                )
            except anthropic.InternalServerError as exc:
                last_error = exc
                logger.warning(
                    "Server error (attempt %d/%d) prompt_hash=%s: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    prompt_hash,
                    exc,
                )
            except anthropic.APITimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Timeout (attempt %d/%d) prompt_hash=%s: %s",
                    attempt + 1,
                    self.max_retries + 1,
                    prompt_hash,
                    exc,
                )
            except anthropic.APIError as exc:
                # Non-retryable API error
                raise LLMAPIError(
                    f"Non-retryable API error: {exc}"
                ) from exc

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** attempt)
                logger.info("Retrying in %.1f seconds...", delay)
                time.sleep(delay)

        raise LLMAPIError(
            f"API call failed after {self.max_retries + 1} attempts. "
            f"Last error: {last_error}"
        )

    def _parse_and_validate(self, raw_text: str, schema: type[T]) -> T:
        """Parse JSON from response text and validate against schema.

        Handles cases where JSON is embedded in markdown code blocks,
        even when preamble text precedes the code fence.
        Includes automatic JSON repair for common LLM output errors
        (trailing commas, truncated responses, unescaped control chars).
        """
        text = raw_text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        elif "```json" in text or "```\n{" in text:
            # Handle preamble text before code fence
            # e.g. "Here are the results:\n```json\n{...}\n```"
            fence_start = text.find("```json")
            if fence_start == -1:
                fence_start = text.find("```\n{")
            if fence_start >= 0:
                after_fence = text[fence_start:]
                lines = after_fence.split("\n")
                lines = lines[1:]  # Remove ```json line
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as first_exc:
            # ── JSON Repair: attempt to fix common LLM output errors ──
            repaired = self._repair_json(text)
            if repaired is not None:
                try:
                    data = json.loads(repaired)
                    logger.warning(
                        "JSON repair succeeded (original error: %s). "
                        "Repaired %d chars → %d chars.",
                        first_exc,
                        len(text),
                        len(repaired),
                    )
                except json.JSONDecodeError:
                    raise LLMResponseValidationError(
                        f"Response is not valid JSON (repair also failed): "
                        f"{first_exc}\nRaw text: {raw_text[:500]}"
                    ) from first_exc
            else:
                raise LLMResponseValidationError(
                    f"Response is not valid JSON: {first_exc}\n"
                    f"Raw text: {raw_text[:500]}"
                ) from first_exc

        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise LLMResponseValidationError(
                f"Response failed schema validation: {exc}\nData: {data}"
            ) from exc

    @staticmethod
    def _repair_json(text: str) -> str | None:
        """Attempt to repair common JSON errors from LLM output.

        Handles:
        1. Trailing commas before } or ] (most common LLM error)
        2. Truncated JSON (unclosed brackets/braces) — closes them
        3. Truncated arrays of objects — finds last complete object
        4. Unescaped newlines inside string values

        Returns:
            Repaired JSON string, or None if repair is not attempted
            (e.g., text is empty or not JSON-like).
        """
        if not text or (not text.lstrip().startswith("{") and
                        not text.lstrip().startswith("[")):
            return None

        repaired = text

        # 1. Remove trailing commas before } or ]
        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

        # Quick check: already valid?
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            pass

        # 2. Truncated array of objects — find the last complete object
        #    This handles the common case where LLM max_tokens cuts off
        #    mid-JSON while generating an array of span objects.
        #    Strategy: walk backwards from the end to find the last "},"
        #    that closes a complete array element, then close the array.
        open_braces = repaired.count("{") - repaired.count("}")
        open_brackets = repaired.count("[") - repaired.count("]")

        if open_braces > 0 or open_brackets > 0:
            # Try to find the last complete object in the outermost array
            # by searching backwards for "},\n" or "}\n" patterns
            # that indicate a complete array element boundary
            last_complete = -1
            depth = 0
            in_str = False
            i = 0
            while i < len(repaired):
                ch = repaired[i]
                if ch == "\\" and in_str:
                    i += 2
                    continue
                if ch == '"':
                    in_str = not in_str
                if not in_str:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        # depth==1 means we just closed an object at
                        # the top-level array (inside outer {spans:[...]})
                        # depth==0 means we closed the outermost object
                        if depth <= 1 and i > 0:
                            last_complete = i
                i += 1

            if last_complete > 0:
                # Truncate at the last complete object
                candidate = repaired[:last_complete + 1]
                # Remove any trailing comma
                candidate = candidate.rstrip().rstrip(",")
                # Close remaining open brackets and braces
                remaining_brackets = candidate.count("[") - candidate.count("]")
                remaining_braces = candidate.count("{") - candidate.count("}")
                candidate += "]" * remaining_brackets + "}" * remaining_braces
                try:
                    json.loads(candidate)
                    logger.info(
                        "JSON truncation repair: salvaged %d/%d chars "
                        "by finding last complete object",
                        last_complete + 1, len(repaired),
                    )
                    return candidate
                except json.JSONDecodeError:
                    pass

            # Fallback: close any open strings, then brackets/braces
            stripped = repaired.rstrip()
            in_string = False
            i = 0
            while i < len(stripped):
                ch = stripped[i]
                if ch == "\\" and in_string:
                    i += 2
                    continue
                if ch == '"':
                    in_string = not in_string
                i += 1

            if in_string:
                repaired = stripped + '"'
                pre = repaired[:-1].rstrip()
                if pre and pre[-1] in ("{", ","):
                    repaired = repaired + ": null"

            repaired = repaired.rstrip().rstrip(",")
            open_braces = repaired.count("{") - repaired.count("}")
            open_brackets = repaired.count("[") - repaired.count("]")
            repaired += "]" * open_brackets + "}" * open_braces

        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            pass

        # 3. Last resort: extract the largest valid JSON object
        if repaired.lstrip().startswith("{"):
            brace_depth = 0
            last_valid_end = -1
            in_str = False
            for i, ch in enumerate(repaired):
                if ch == "\\" and in_str:
                    continue
                if ch == '"' and (i == 0 or repaired[i - 1] != "\\"):
                    in_str = not in_str
                if not in_str:
                    if ch == "{":
                        brace_depth += 1
                    elif ch == "}":
                        brace_depth -= 1
                        if brace_depth == 0:
                            last_valid_end = i + 1
                            break
            if last_valid_end > 0:
                candidate = repaired[:last_valid_end]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    pass

        return repaired

    @property
    def total_prompt_tokens(self) -> int:
        """Total prompt tokens used across all calls."""
        return self._total_prompt_tokens

    @property
    def total_completion_tokens(self) -> int:
        """Total completion tokens used across all calls."""
        return self._total_completion_tokens

    @property
    def total_calls(self) -> int:
        """Total number of API calls made."""
        return self._total_calls

    def estimate_cost(self) -> float:
        """Estimate total cost in USD based on token usage.

        Uses approximate Claude Sonnet pricing.
        """
        # Pricing per 1M tokens from config
        prompt_cost_per_m = config.LLM_PROMPT_COST_PER_M
        completion_cost_per_m = config.LLM_COMPLETION_COST_PER_M
        prompt_cost = (self._total_prompt_tokens / 1_000_000) * prompt_cost_per_m
        completion_cost = (self._total_completion_tokens / 1_000_000) * completion_cost_per_m
        return prompt_cost + completion_cost
