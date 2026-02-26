# VERIFIED: imports — stdlib + config only
# VERIFIED: downstream — consumed by llm/client.py, extraction agents
"""
Component: LLM.MODEL_ROUTER
Spec: DRAMA_ADOPTION_REVISED.md Enhancement B (Cost-Aware Model Routing)
Purpose: Route extraction tasks to cost-appropriate Claude models.
         Haiku for simple binary tasks, Sonnet for extraction, Opus for complex reasoning.
Reads: Task type string
Writes: Model ID string
Gates: None (advisory routing, no hard failures)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crci.shared import config

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    """Claude model tiers by capability and cost."""
    
    HAIKU = "claude-3-5-haiku-20241022"      # Fast, cheap: binary classification
    SONNET = "claude-sonnet-4-20250514"       # Balanced: standard extraction
    OPUS = "claude-opus-4-20250514"           # Full: complex reasoning


# ═══════════════════════════════════════════════════════════════
#  ROUTING CONFIGURATION
# ═══════════════════════════════════════════════════════════════


@dataclass
class RoutingConfig:
    """Task-to-model routing configuration.
    
    IMPORTANT: Only add tasks to haiku_tasks after empirical validation
    shows ≥95% accuracy. Default to Sonnet for safety.
    """
    
    # Tasks validated for Haiku (binary classification only)
    # VALIDATED: These require simple yes/no answers
    haiku_tasks: frozenset[str] = field(default_factory=lambda: frozenset({
        # Binary presence checks (AG01/AG05 preprocessing)
        "has_effect_size",            # Binary: does abstract mention effect size?
        "has_confidence_interval",    # Binary: does abstract mention CI?
        "is_rct",                     # Binary: is this an RCT? (NOT the 27 subtypes)
        "population_is_cancer",       # Binary: is population cancer patients?
        "is_longitudinal",            # Binary: is this longitudinal?
        "abstract_relevance_binary",  # Binary: relevant to CRCI? (screening)
    }))
    
    # Tasks requiring Sonnet (standard extraction)
    # DEFAULT: Most extraction tasks go here
    sonnet_tasks: frozenset[str] = field(default_factory=lambda: frozenset({
        # Core extraction agents
        "AG01_metadata",              # Extract title, authors, DOI, year
        "AG02_design",                # Extract study design details
        "AG03_cohort",                # Extract cohort characteristics
        "AG04_outcome",               # Extract outcome measures
        "AG05_stats_label",           # Extract statistical values
        "AG06_exposure",              # Extract exposure/intervention
        "AG07_mediator",              # Extract mediator variables
        "AG08_temporal",              # Extract temporal design
        "AG10_strategic_intel",       # Extract research gaps
        "AG11_instrument_validation", # Extract instrument properties
        # Specific extraction tasks
        "effect_size_extract",        # Extract β, d, OR values
        "sample_size_extract",        # Extract N
        "ci_extract",                 # Extract confidence intervals
        "population_extract",         # Extract population details
        "intervention_extract",       # Extract intervention details
        "outcome_extract",            # Extract outcome details
    }))
    
    # Tasks requiring Opus (complex reasoning)
    # EXPENSIVE: Only for tasks requiring deep reasoning
    opus_tasks: frozenset[str] = field(default_factory=lambda: frozenset({
        # Complex classification (27 study subtypes)
        "study_design_classify_27",   # 27 subtypes - too nuanced for Haiku
        "paper_type_classify_27",     # Full subtype classification
        # Reconciliation and conflict resolution
        "AG09_reconciliation",        # Resolve conflicting extractions
        "ambiguity_resolve",          # Resolve ambiguous claims
        "conflation_detect",          # Detect overlapping cohorts
        # Deep reasoning
        "heterogeneity_assess",       # Assess study heterogeneity
        "mechanistic_pathway_infer",  # Infer causal mechanisms
        "trust_boundary_complex",     # Complex trust decisions
    }))


# Singleton config instance
_ROUTING_CONFIG: RoutingConfig | None = None


def get_routing_config() -> RoutingConfig:
    """Get or create the routing configuration singleton."""
    global _ROUTING_CONFIG
    if _ROUTING_CONFIG is None:
        _ROUTING_CONFIG = RoutingConfig()
    return _ROUTING_CONFIG


def set_routing_config(cfg: RoutingConfig) -> None:
    """Override routing config (for testing/experimentation)."""
    global _ROUTING_CONFIG
    _ROUTING_CONFIG = cfg
    logger.info("Model routing config updated")


# ═══════════════════════════════════════════════════════════════
#  ROUTING LOGIC
# ═══════════════════════════════════════════════════════════════


def route_task(task_type: str, allow_opus: bool = True) -> str:
    """Route a task to the appropriate model.
    
    Args:
        task_type: Task identifier (e.g., "AG01_metadata", "has_effect_size")
        allow_opus: If False, downgrade Opus tasks to Sonnet (for cost control)
    
    Returns:
        Model ID string for Claude API
    """
    cfg = get_routing_config()
    
    if task_type in cfg.haiku_tasks:
        model_id = ModelTier.HAIKU.value
        logger.debug("Routing '%s' → Haiku (binary classification)", task_type)
        return model_id
    
    if task_type in cfg.opus_tasks:
        if allow_opus:
            model_id = ModelTier.OPUS.value
            logger.debug("Routing '%s' → Opus (complex reasoning)", task_type)
        else:
            model_id = ModelTier.SONNET.value
            logger.debug("Routing '%s' → Sonnet (Opus disabled)", task_type)
        return model_id
    
    if task_type in cfg.sonnet_tasks:
        model_id = ModelTier.SONNET.value
        logger.debug("Routing '%s' → Sonnet (standard extraction)", task_type)
        return model_id
    
    # Unknown task: default to Sonnet (safe)
    logger.warning(
        "Unknown task type '%s', defaulting to Sonnet. "
        "Consider adding to RoutingConfig.",
        task_type,
    )
    return ModelTier.SONNET.value


def get_model_tier(task_type: str) -> ModelTier:
    """Get the ModelTier enum for a task (for cost estimation)."""
    cfg = get_routing_config()
    
    if task_type in cfg.haiku_tasks:
        return ModelTier.HAIKU
    if task_type in cfg.opus_tasks:
        return ModelTier.OPUS
    return ModelTier.SONNET


# ═══════════════════════════════════════════════════════════════
#  COST ESTIMATION
# ═══════════════════════════════════════════════════════════════


# Approximate costs per 1M tokens (input + output blend)
MODEL_COSTS_PER_M: dict[ModelTier, dict[str, float]] = {
    ModelTier.HAIKU: {
        "prompt": 0.80,      # $0.80 per 1M input tokens
        "completion": 4.00,  # $4.00 per 1M output tokens
    },
    ModelTier.SONNET: {
        "prompt": 3.00,      # $3.00 per 1M input tokens (current default)
        "completion": 15.00, # $15.00 per 1M output tokens
    },
    ModelTier.OPUS: {
        "prompt": 15.00,     # $15.00 per 1M input tokens
        "completion": 75.00, # $75.00 per 1M output tokens
    },
}


def estimate_task_cost(
    task_type: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate cost in USD for a task.
    
    Args:
        task_type: Task identifier
        prompt_tokens: Estimated input tokens
        completion_tokens: Estimated output tokens
    
    Returns:
        Estimated cost in USD
    """
    tier = get_model_tier(task_type)
    costs = MODEL_COSTS_PER_M[tier]
    
    prompt_cost = (prompt_tokens / 1_000_000) * costs["prompt"]
    completion_cost = (completion_tokens / 1_000_000) * costs["completion"]
    
    return prompt_cost + completion_cost


def estimate_extraction_cost(
    agents: list[str] | None = None,
    avg_prompt_tokens: int = 2000,
    avg_completion_tokens: int = 500,
) -> dict[str, Any]:
    """Estimate total extraction cost per paper.
    
    Args:
        agents: List of agent IDs to include (default: all)
        avg_prompt_tokens: Average prompt tokens per agent call
        avg_completion_tokens: Average completion tokens per agent call
    
    Returns:
        Cost breakdown by model tier and total
    """
    if agents is None:
        agents = [
            "AG01_metadata", "AG02_design", "AG03_cohort", "AG04_outcome",
            "AG05_stats_label", "AG06_exposure", "AG07_mediator",
            "AG08_temporal", "AG09_reconciliation", "AG10_strategic_intel",
            "AG11_instrument_validation",
        ]
    
    costs_by_tier = {tier: 0.0 for tier in ModelTier}
    task_breakdown = {}
    
    for agent in agents:
        cost = estimate_task_cost(agent, avg_prompt_tokens, avg_completion_tokens)
        tier = get_model_tier(agent)
        costs_by_tier[tier] += cost
        task_breakdown[agent] = {"tier": tier.name, "cost_usd": cost}
    
    total = sum(costs_by_tier.values())
    
    return {
        "total_cost_usd": total,
        "by_tier": {tier.name: cost for tier, cost in costs_by_tier.items()},
        "tasks": task_breakdown,
        "savings_vs_all_sonnet": _estimate_savings(agents, avg_prompt_tokens, avg_completion_tokens),
    }


def _estimate_savings(
    agents: list[str],
    avg_prompt_tokens: int,
    avg_completion_tokens: int,
) -> dict[str, float]:
    """Estimate savings vs. all-Sonnet baseline."""
    sonnet_costs = MODEL_COSTS_PER_M[ModelTier.SONNET]
    sonnet_total = len(agents) * (
        (avg_prompt_tokens / 1_000_000) * sonnet_costs["prompt"] +
        (avg_completion_tokens / 1_000_000) * sonnet_costs["completion"]
    )
    
    routed_total = sum(
        estimate_task_cost(agent, avg_prompt_tokens, avg_completion_tokens)
        for agent in agents
    )
    
    savings = sonnet_total - routed_total
    savings_pct = (savings / sonnet_total * 100) if sonnet_total > 0 else 0
    
    return {
        "sonnet_baseline_usd": sonnet_total,
        "routed_usd": routed_total,
        "savings_usd": savings,
        "savings_pct": savings_pct,
    }
