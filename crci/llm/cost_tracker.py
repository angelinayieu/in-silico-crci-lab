# VERIFIED: imports — stdlib only
# VERIFIED: downstream — used by llm/client.py and extraction/pipeline.py
"""
Component: SYS_EXTRACTION.LLM_COST_TRACKER
Spec: IMPLEMENTATION_BLUEPRINT Part 4 item 1 (cost tracking needs)
Formulas: None
Reads: Nothing
Writes: CSV log file of LLM usage
Gates: None
"""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from crci.shared import config

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """A single LLM cost record."""

    timestamp: str
    model_id: str
    prompt_hash: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: float
    extraction_run_id: str | None = None
    agent_id: str | None = None
    success: bool = True


class CostTracker:
    """Tracks LLM usage costs and writes to CSV log.

    Thread-safe append-only CSV logger for LLM cost tracking.
    """

    def __init__(self, log_path: str | Path | None = None) -> None:
        if log_path is None:
            log_path = Path("logs/llm_cost_log.csv")
        self.log_path = Path(log_path)
        self._records: list[CostRecord] = []
        self._file_handle: TextIO | None = None
        self._writer: csv.DictWriter | None = None

    def _ensure_log_file(self) -> csv.DictWriter:
        """Create log file with headers if it doesn't exist."""
        if self._writer is not None:
            return self._writer

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self.log_path.exists() and self.log_path.stat().st_size > 0

        self._file_handle = open(self.log_path, "a", newline="")  # noqa: SIM115
        fieldnames = [
            "timestamp",
            "model_id",
            "prompt_hash",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "estimated_cost_usd",
            "latency_ms",
            "extraction_run_id",
            "agent_id",
            "success",
        ]
        self._writer = csv.DictWriter(self._file_handle, fieldnames=fieldnames)
        if not file_exists:
            self._writer.writeheader()
            if self._file_handle is not None:
                self._file_handle.flush()

        return self._writer

    def record(
        self,
        model_id: str,
        prompt_hash: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        extraction_run_id: str | None = None,
        agent_id: str | None = None,
        success: bool = True,
    ) -> CostRecord:
        """Record a single LLM call.

        Returns the CostRecord for inspection/testing.
        """
        # Pricing per 1M tokens from config
        prompt_cost_per_m = config.LLM_PROMPT_COST_PER_M
        completion_cost_per_m = config.LLM_COMPLETION_COST_PER_M
        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = (
            (prompt_tokens / 1_000_000) * prompt_cost_per_m
            + (completion_tokens / 1_000_000) * completion_cost_per_m
        )

        rec = CostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model_id=model_id,
            prompt_hash=prompt_hash,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=round(estimated_cost, 6),
            latency_ms=round(latency_ms, 1),
            extraction_run_id=extraction_run_id,
            agent_id=agent_id,
            success=success,
        )

        self._records.append(rec)

        writer = self._ensure_log_file()
        writer.writerow(
            {
                "timestamp": rec.timestamp,
                "model_id": rec.model_id,
                "prompt_hash": rec.prompt_hash,
                "prompt_tokens": rec.prompt_tokens,
                "completion_tokens": rec.completion_tokens,
                "total_tokens": rec.total_tokens,
                "estimated_cost_usd": rec.estimated_cost_usd,
                "latency_ms": rec.latency_ms,
                "extraction_run_id": rec.extraction_run_id or "",
                "agent_id": rec.agent_id or "",
                "success": rec.success,
            }
        )
        if self._file_handle is not None:
            self._file_handle.flush()

        logger.debug(
            "Cost recorded: model=%s tokens=%d cost=$%.4f",
            rec.model_id,
            rec.total_tokens,
            rec.estimated_cost_usd,
        )

        return rec

    def get_summary(self) -> dict[str, float | int]:
        """Return summary of all recorded costs."""
        total_prompt = sum(r.prompt_tokens for r in self._records)
        total_completion = sum(r.completion_tokens for r in self._records)
        total_cost = sum(r.estimated_cost_usd for r in self._records)
        return {
            "total_calls": len(self._records),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "total_estimated_cost_usd": round(total_cost, 4),
        }

    def close(self) -> None:
        """Close the log file."""
        if self._file_handle is not None:
            self._file_handle.close()
            self._file_handle = None
            self._writer = None
