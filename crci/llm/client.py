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
    ) -> T:
        """Call Claude API and return validated response.

        Args:
            prompt: The user prompt string.
            response_schema: Pydantic model class to validate response against.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature (default 0 for determinism).

        Returns:
            Validated instance of response_schema.

        Raises:
            LLMResponseValidationError: If response fails schema validation.
            LLMAPIError: If API call fails after all retries.
        """
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        start_time = time.monotonic()

        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system_prompt is not None:
            kwargs["system"] = system_prompt

        response = self._call_with_retry(kwargs, prompt_hash)
        latency_ms = (time.monotonic() - start_time) * 1000

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
            self.model_id,
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

        Handles cases where JSON is embedded in markdown code blocks.
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

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseValidationError(
                f"Response is not valid JSON: {exc}\nRaw text: {raw_text[:500]}"
            ) from exc

        try:
            return schema.model_validate(data)
        except ValidationError as exc:
            raise LLMResponseValidationError(
                f"Response failed schema validation: {exc}\nData: {data}"
            ) from exc

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
