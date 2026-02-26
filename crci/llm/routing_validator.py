#!/usr/bin/env python3
"""
Model Routing Validation Harness

Purpose: Empirically test which Claude model (Haiku/Sonnet/Opus) performs
best for each extraction task, then document the rationale for routing decisions.

Usage:
    python -m crci.llm.routing_validator --task has_effect_size --samples 50
    python -m crci.llm.routing_validator --all --samples 20
    python -m crci.llm.routing_validator --report

The validation process:
1. For each task type, run N samples through both proposed model and gold model (Opus)
2. Compare accuracy: proposed_accuracy vs gold_accuracy
3. If proposed ≥95%, accept the routing; else reject and use higher tier
4. Generate a validation report documenting rationale for each routing decision

Output:
- data/routing_validation/{task_type}_results.json
- data/routing_validation/ROUTING_RATIONALE.md (summary document)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from crci.llm.model_router import (
    ModelTier,
    RoutingConfig,
    get_model_tier,
    get_routing_config,
    route_task,
)

logger = logging.getLogger(__name__)

# Output paths
VALIDATION_DIR = Path("data/routing_validation/")
RATIONALE_PATH = VALIDATION_DIR / "ROUTING_RATIONALE.md"


@dataclass
class ValidationSample:
    """A single validation test case."""
    
    text: str                    # Input text (abstract, excerpt, etc.)
    expected: Any                # Expected output
    source: str = "manual"       # Where the sample came from
    paper_id: str | None = None  # Optional paper reference


@dataclass
class ValidationResult:
    """Result of validating one task type."""
    
    task_type: str
    proposed_model: str
    gold_model: str
    n_samples: int
    proposed_correct: int
    gold_correct: int
    proposed_accuracy: float
    gold_accuracy: float
    accuracy_gap: float
    recommendation: str  # "ACCEPT", "ACCEPT_WITH_MONITORING", "REJECT"
    rationale: str
    timestamp: str
    sample_errors: list[dict]  # Examples where proposed model failed


class RoutingValidator:
    """Validate model routing decisions empirically."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.results_dir = VALIDATION_DIR
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
    
    def _get_client(self):
        """Lazily initialize LLM client."""
        if self._client is None:
            from crci.llm.client import LLMClient
            self._client = LLMClient()
        return self._client
    
    def validate_task(
        self,
        task_type: str,
        samples: list[ValidationSample],
        proposed_model: ModelTier | None = None,
        gold_model: ModelTier = ModelTier.OPUS,
    ) -> ValidationResult:
        """Validate a single task type.
        
        Runs each sample through both proposed and gold model,
        compares accuracy, and generates recommendation.
        
        Args:
            task_type: Task identifier
            samples: Test cases with expected outputs
            proposed_model: Model to test (default: from routing config)
            gold_model: Reference model (default: Opus)
        
        Returns:
            ValidationResult with accuracy comparison and recommendation
        """
        if proposed_model is None:
            proposed_tier = get_model_tier(task_type)
        else:
            proposed_tier = proposed_model
        
        logger.info(
            "Validating '%s': proposed=%s vs gold=%s with %d samples",
            task_type,
            proposed_tier.name,
            gold_model.name,
            len(samples),
        )
        
        proposed_correct = 0
        gold_correct = 0
        sample_errors = []
        
        for i, sample in enumerate(samples):
            if self.dry_run:
                # Simulate results for testing the harness
                proposed_result = sample.expected
                gold_result = sample.expected
            else:
                proposed_result = self._run_task(
                    task_type, sample.text, proposed_tier.value
                )
                gold_result = self._run_task(
                    task_type, sample.text, gold_model.value
                )
            
            proposed_match = self._compare(proposed_result, sample.expected)
            gold_match = self._compare(gold_result, sample.expected)
            
            if proposed_match:
                proposed_correct += 1
            if gold_match:
                gold_correct += 1
            
            # Track errors for analysis
            if not proposed_match:
                sample_errors.append({
                    "sample_idx": i,
                    "text_preview": sample.text[:200],
                    "expected": str(sample.expected),
                    "proposed_result": str(proposed_result),
                    "gold_result": str(gold_result),
                })
            
            if (i + 1) % 10 == 0:
                logger.info("Progress: %d/%d samples", i + 1, len(samples))
        
        n = len(samples)
        proposed_accuracy = proposed_correct / n if n > 0 else 0
        gold_accuracy = gold_correct / n if n > 0 else 0
        accuracy_gap = gold_accuracy - proposed_accuracy
        
        recommendation, rationale = self._generate_recommendation(
            task_type, proposed_tier, proposed_accuracy, gold_accuracy
        )
        
        result = ValidationResult(
            task_type=task_type,
            proposed_model=proposed_tier.value,
            gold_model=gold_model.value,
            n_samples=n,
            proposed_correct=proposed_correct,
            gold_correct=gold_correct,
            proposed_accuracy=proposed_accuracy,
            gold_accuracy=gold_accuracy,
            accuracy_gap=accuracy_gap,
            recommendation=recommendation,
            rationale=rationale,
            timestamp=datetime.now().isoformat(),
            sample_errors=sample_errors[:5],  # Keep first 5 errors
        )
        
        # Save results
        self._save_result(result)
        
        return result
    
    def _run_task(
        self, 
        task_type: str, 
        text: str, 
        model_id: str
    ) -> Any:
        """Run a single task with specified model."""
        # Map task types to their implementations
        task_runners = {
            "has_effect_size": self._run_binary_presence,
            "has_confidence_interval": self._run_binary_presence,
            "is_rct": self._run_binary_presence,
            "population_is_cancer": self._run_binary_presence,
            "is_longitudinal": self._run_binary_presence,
            "abstract_relevance_binary": self._run_binary_presence,
        }
        
        runner = task_runners.get(task_type, self._run_generic)
        return runner(task_type, text, model_id)
    
    def _run_binary_presence(
        self, 
        task_type: str, 
        text: str, 
        model_id: str
    ) -> bool:
        """Run a binary presence check task."""
        client = self._get_client()
        
        # Build prompt based on task type
        prompts = {
            "has_effect_size": (
                "Does this abstract report a quantitative effect size "
                "(e.g., Cohen's d, OR, RR, β, r, or similar)? "
                "Answer ONLY 'yes' or 'no'.\n\nAbstract:\n{text}"
            ),
            "has_confidence_interval": (
                "Does this abstract report a confidence interval (95% CI, CI)? "
                "Answer ONLY 'yes' or 'no'.\n\nAbstract:\n{text}"
            ),
            "is_rct": (
                "Is this a randomized controlled trial (RCT)? "
                "Answer ONLY 'yes' or 'no'.\n\nAbstract:\n{text}"
            ),
            "population_is_cancer": (
                "Is the study population cancer patients or cancer survivors? "
                "Answer ONLY 'yes' or 'no'.\n\nAbstract:\n{text}"
            ),
            "is_longitudinal": (
                "Is this a longitudinal study (following participants over time)? "
                "Answer ONLY 'yes' or 'no'.\n\nAbstract:\n{text}"
            ),
            "abstract_relevance_binary": (
                "Is this abstract relevant to cancer-related cognitive impairment (CRCI)? "
                "Answer ONLY 'yes' or 'no'.\n\nAbstract:\n{text}"
            ),
        }
        
        prompt = prompts.get(task_type, "").format(text=text)
        if not prompt:
            raise ValueError(f"No prompt defined for task: {task_type}")
        
        # Use simple schema for binary response
        from pydantic import BaseModel
        
        class BinaryResponse(BaseModel):
            answer: str
        
        # Call with specified model
        original_model = client.model_id
        client.model_id = model_id
        
        try:
            response = client.call(
                prompt=prompt,
                response_schema=BinaryResponse,
                system_prompt="You are a scientific abstract classifier. Answer only 'yes' or 'no' in JSON format.",
            )
            result = response.answer.lower().strip() in ("yes", "true", "1")
        finally:
            client.model_id = original_model
        
        return result
    
    def _run_generic(
        self, 
        task_type: str, 
        text: str, 
        model_id: str
    ) -> str:
        """Generic task runner for undefined tasks."""
        logger.warning("No specific runner for '%s', using generic", task_type)
        return "UNKNOWN"
    
    def _compare(self, result: Any, expected: Any) -> bool:
        """Compare task result to expected value."""
        if isinstance(expected, bool):
            return bool(result) == expected
        if isinstance(expected, str):
            return str(result).lower().strip() == expected.lower().strip()
        return result == expected
    
    def _generate_recommendation(
        self,
        task_type: str,
        proposed_tier: ModelTier,
        proposed_accuracy: float,
        gold_accuracy: float,
    ) -> tuple[str, str]:
        """Generate routing recommendation based on accuracy."""
        
        if proposed_accuracy >= 0.95:
            return (
                "ACCEPT",
                f"{proposed_tier.name} achieves {proposed_accuracy:.1%} accuracy, "
                f"exceeding 95% threshold. Safe for production use."
            )
        
        if proposed_accuracy >= 0.90 and proposed_accuracy >= gold_accuracy - 0.02:
            return (
                "ACCEPT_WITH_MONITORING",
                f"{proposed_tier.name} achieves {proposed_accuracy:.1%} accuracy "
                f"(gold: {gold_accuracy:.1%}). Acceptable with monitoring."
            )
        
        # Recommend upgrade
        if proposed_tier == ModelTier.HAIKU:
            upgrade = ModelTier.SONNET
        elif proposed_tier == ModelTier.SONNET:
            upgrade = ModelTier.OPUS
        else:
            upgrade = ModelTier.OPUS
        
        return (
            "REJECT",
            f"{proposed_tier.name} only achieves {proposed_accuracy:.1%} accuracy "
            f"(gold: {gold_accuracy:.1%}). Upgrade to {upgrade.name}."
        )
    
    def _save_result(self, result: ValidationResult) -> None:
        """Save validation result to JSON file."""
        output_path = self.results_dir / f"{result.task_type}_results.json"
        
        with open(output_path, "w") as f:
            json.dump(asdict(result), f, indent=2)
        
        logger.info("Saved validation results to %s", output_path)
    
    def generate_rationale_report(self) -> str:
        """Generate markdown report documenting routing rationale."""
        
        # Load all results
        results = []
        for result_file in self.results_dir.glob("*_results.json"):
            with open(result_file) as f:
                results.append(json.load(f))
        
        if not results:
            return "No validation results found. Run validation first."
        
        # Sort by task type
        results.sort(key=lambda r: r["task_type"])
        
        # Generate report
        lines = [
            "# Model Routing Validation Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Total tasks validated:** {len(results)}",
            "",
            "## Summary",
            "",
            "| Task | Proposed Model | Accuracy | Gold Accuracy | Recommendation |",
            "|------|---------------|----------|---------------|----------------|",
        ]
        
        for r in results:
            proposed_model = r["proposed_model"].split("-")[1] if "-" in r["proposed_model"] else r["proposed_model"]
            lines.append(
                f"| {r['task_type']} | {proposed_model.upper()} | "
                f"{r['proposed_accuracy']:.1%} | {r['gold_accuracy']:.1%} | "
                f"{r['recommendation']} |"
            )
        
        lines.extend([
            "",
            "## Detailed Rationale",
            "",
        ])
        
        for r in results:
            lines.extend([
                f"### {r['task_type']}",
                "",
                f"- **Proposed model:** {r['proposed_model']}",
                f"- **Samples tested:** {r['n_samples']}",
                f"- **Accuracy:** {r['proposed_correct']}/{r['n_samples']} ({r['proposed_accuracy']:.1%})",
                f"- **Gold accuracy:** {r['gold_accuracy']:.1%}",
                f"- **Recommendation:** {r['recommendation']}",
                f"- **Rationale:** {r['rationale']}",
                "",
            ])
            
            if r.get("sample_errors"):
                lines.append("**Example errors:**")
                for i, err in enumerate(r["sample_errors"][:3], 1):
                    lines.append(f"{i}. Expected: `{err['expected']}`, Got: `{err['proposed_result']}`")
                lines.append("")
        
        lines.extend([
            "## Routing Configuration",
            "",
            "Based on validation results, update `crci/llm/model_router.py`:",
            "",
            "```python",
            "# Tasks validated for Haiku (binary classification)",
            "haiku_tasks = frozenset({",
        ])
        
        accepted_haiku = [
            r["task_type"] for r in results 
            if r["recommendation"] in ("ACCEPT", "ACCEPT_WITH_MONITORING")
            and "haiku" in r["proposed_model"].lower()
        ]
        for task in accepted_haiku:
            lines.append(f'    "{task}",')
        
        lines.extend([
            "})",
            "```",
            "",
            "## Cost Impact",
            "",
            "Routing binary tasks to Haiku reduces cost by ~60-70% for those tasks.",
            "See `crci/llm/model_router.py:estimate_extraction_cost()` for details.",
        ])
        
        report = "\n".join(lines)
        
        # Save report
        with open(RATIONALE_PATH, "w") as f:
            f.write(report)
        
        logger.info("Generated rationale report at %s", RATIONALE_PATH)
        
        return report


# ═══════════════════════════════════════════════════════════════
#  SAMPLE DATA GENERATORS
# ═══════════════════════════════════════════════════════════════


def generate_test_samples(task_type: str, n: int = 20) -> list[ValidationSample]:
    """Generate test samples for a task type.
    
    In production, these would come from manually labeled data.
    This provides example samples for demonstration.
    """
    
    # Example samples for binary tasks
    samples_db = {
        "has_effect_size": [
            ValidationSample(
                text="Treatment group showed improvement with Cohen's d = 0.45 (95% CI: 0.12-0.78).",
                expected=True,
            ),
            ValidationSample(
                text="Patients reported subjective improvements in memory.",
                expected=False,
            ),
            ValidationSample(
                text="The odds ratio was 2.3 (p < 0.05) for cognitive decline.",
                expected=True,
            ),
            ValidationSample(
                text="This study describes a case series of 5 patients.",
                expected=False,
            ),
            ValidationSample(
                text="Effect size was medium (d = 0.6) for attention outcomes.",
                expected=True,
            ),
        ],
        "is_rct": [
            ValidationSample(
                text="Participants were randomly assigned to intervention (n=50) or control (n=48).",
                expected=True,
            ),
            ValidationSample(
                text="This prospective cohort followed patients for 2 years.",
                expected=False,
            ),
            ValidationSample(
                text="A randomized, double-blind, placebo-controlled trial was conducted.",
                expected=True,
            ),
            ValidationSample(
                text="We performed a systematic review and meta-analysis.",
                expected=False,
            ),
            ValidationSample(
                text="Patients were randomized 1:1 using computer-generated sequences.",
                expected=True,
            ),
        ],
        "population_is_cancer": [
            ValidationSample(
                text="Breast cancer survivors (n=120) were recruited from oncology clinics.",
                expected=True,
            ),
            ValidationSample(
                text="Healthy adults aged 40-60 participated in this study.",
                expected=False,
            ),
            ValidationSample(
                text="Patients receiving chemotherapy for various malignancies.",
                expected=True,
            ),
            ValidationSample(
                text="The study included patients with type 2 diabetes.",
                expected=False,
            ),
            ValidationSample(
                text="Colorectal cancer patients post-surgery were assessed.",
                expected=True,
            ),
        ],
    }
    
    base_samples = samples_db.get(task_type, [])
    
    # Repeat/augment to reach n samples
    if len(base_samples) < n:
        factor = (n // len(base_samples)) + 1 if base_samples else 0
        samples = (base_samples * factor)[:n]
    else:
        samples = base_samples[:n]
    
    return samples


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Validate model routing decisions empirically"
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Task type to validate (e.g., 'has_effect_size')",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all haiku-routed tasks",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=20,
        help="Number of samples per task (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate validation without calling LLM",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate rationale report from existing results",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging",
    )
    
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    validator = RoutingValidator(dry_run=args.dry_run)
    
    if args.report:
        report = validator.generate_rationale_report()
        print(report)
        return
    
    if args.all:
        cfg = get_routing_config()
        tasks = list(cfg.haiku_tasks)
    elif args.task:
        tasks = [args.task]
    else:
        parser.print_help()
        sys.exit(1)
    
    for task in tasks:
        print(f"\n{'='*60}")
        print(f"Validating: {task}")
        print('='*60)
        
        samples = generate_test_samples(task, args.samples)
        if not samples:
            print(f"No test samples available for '{task}'")
            continue
        
        result = validator.validate_task(task, samples)
        
        print(f"\nResults for {task}:")
        print(f"  Proposed accuracy: {result.proposed_accuracy:.1%}")
        print(f"  Gold accuracy:     {result.gold_accuracy:.1%}")
        print(f"  Recommendation:    {result.recommendation}")
        print(f"  Rationale:         {result.rationale}")
    
    print("\n" + "="*60)
    print("Validation complete. Run with --report to generate summary.")


if __name__ == "__main__":
    main()
