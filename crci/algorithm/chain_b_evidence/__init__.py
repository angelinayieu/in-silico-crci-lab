"""ALG-B: Edge Parameterization — Chain B of the CRCI Algorithm.

Transforms raw evidence records into parameterized edge weights with
calibrated effective standard errors, prior distributions, structural
inclusion probabilities, and chain-vs-direct validation.

Produces the FrozenModelState that crosses the cut boundary to runtime.
"""
from .evidence_compiler import (
    ChainDirectResult,
    EdgePriorSpec,
    EvidenceRecord,
    HeterogeneityAdjustedEdge,
    InclusionProbEdge,
    PooledEdge,
    TauSquaredPrior,
    run_b1_through_b6,
)
from .frozen_state import (
    ContextPriorSpec,
    FrozenModelState,
    SynergyRecord,
    run_chain_b,
)

__all__ = [
    "ChainDirectResult",
    "ContextPriorSpec",
    "EdgePriorSpec",
    "EvidenceRecord",
    "FrozenModelState",
    "HeterogeneityAdjustedEdge",
    "InclusionProbEdge",
    "PooledEdge",
    "SynergyRecord",
    "TauSquaredPrior",
    "run_b1_through_b6",
    "run_chain_b",
]
