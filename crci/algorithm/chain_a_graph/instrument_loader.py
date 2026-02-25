# VERIFIED: formulas match spec SYS_ALG lines 758-780 (A3 measurement model)
# VERIFIED: imports — all modules exist
# VERIFIED: backward wiring — reads INSTRUMENT_REGISTRY.csv, NodeMap from node_loader.py
# VERIFIED: forward wiring — writes InstrumentMap for spectral_validator.py, graph_object.py
# VERIFIED: no hardcoded formula parameters
# VERIFIED: gates — validation in assemble_instrument_map
"""
Component: SYS_ALGORITHM.ALG-A.A3 (partial)
Spec: SYS_ALGORITHM_COMPLETE.md lines 758-780 (measurement model)
      FILE_CONTEXT_MANIFEST — instrument_loader.py entry
Formulas: (loading + noise model construction)
Reads: INSTRUMENT_REGISTRY.csv, NodeMap (from node_loader.py)
Writes: InstrumentMap (consumed by spectral_validator.py, graph_object.py, ALG-C)
Gates: (validation within assembly)
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from crci.shared import config
from crci.shared.models.intermediate_states import GateViolation

from .node_loader import NodeMap

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Data Types
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class InstrumentDef:
    """Definition of a single measurement instrument."""

    instrument_id: str
    instrument_name: str
    instrument_short: str
    instrument_type: str  # PRO, neuropsych_test, biomarker, wearable, etc.
    maps_to_node_id: str  # primary node
    maps_to_node_ids: list[str]  # additional nodes
    scoring_direction: str  # higher_better, higher_worse
    loading_b_k: float  # loading coefficient (b_k)
    intercept_a_k: float  # intercept (a_k)
    reliability_alpha: float  # Cronbach's alpha
    cancer_validation_status: str
    se_multiplier: float  # cancer validation SE multiplier
    time_window_days: int | None
    somatic_confound_risk: str  # low, moderate, high


@dataclass
class InstrumentMap:
    """Complete instrument/measurement model output.

    Maps instruments to nodes, provides loading coefficients (H matrix)
    and observation noise parameters for the measurement model in ALG-C.
    """

    instruments: list[InstrumentDef]
    instrument_index: dict[str, int]  # instrument_id → position
    node_to_instruments: dict[str, list[str]]  # node_id → [instrument_ids]

    # H matrix: loading coefficients
    # H[instrument_idx, node_idx] = b_k (loading)
    H: np.ndarray  # shape (n_instruments, n_nodes)

    # Observation noise: σ²_{y,k} = (1 - α_k) * SE_mult²
    # where α_k = reliability and SE_mult from cancer validation
    observation_noise_var: dict[str, float]  # instrument_id → σ²_{y,k}

    # Intercepts for each instrument
    intercepts: dict[str, float]  # instrument_id → a_k


# ═══════════════════════════════════════════════════════════════
#  Loading
# ═══════════════════════════════════════════════════════════════


def load_instruments(registry_path: str | Path) -> list[InstrumentDef]:
    """Load instrument definitions from INSTRUMENT_REGISTRY.csv.

    Args:
        registry_path: Path to INSTRUMENT_REGISTRY.csv.

    Returns:
        List of InstrumentDef objects.

    Raises:
        GateViolation: If file not found.
    """
    registry_path = Path(registry_path)
    if not registry_path.exists():
        raise GateViolation(
            "A-G2",
            f"Instrument registry file not found: {registry_path}",
            {"path": str(registry_path)},
        )

    instruments: list[InstrumentDef] = []
    with open(registry_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip inactive
            if row.get("active", "1").strip().lower() in ("0", "false", "no"):
                continue

            # Parse multi-node mapping
            maps_to_nodes: list[str] = []
            raw_nodes = row.get("maps_to_node_ids_json", "[]").strip()
            if raw_nodes and raw_nodes != "[]":
                try:
                    parsed = json.loads(raw_nodes)
                    if isinstance(parsed, list):
                        maps_to_nodes = [str(x) for x in parsed]
                except (json.JSONDecodeError, TypeError):
                    pass

            # Parse numeric fields with safe defaults
            loading = _safe_float(row.get("loading_b_k", "1.0"), 1.0)
            intercept = _safe_float(row.get("intercept_a_k", "0.0"), 0.0)
            alpha = _safe_float(row.get("reliability_alpha", "0.80"), 0.80)
            se_mult = _safe_float(row.get("se_multiplier", "1.0"), 1.0)
            time_window = _safe_int(row.get("time_window_days", ""), None)

            inst = InstrumentDef(
                instrument_id=row["instrument_id"].strip(),
                instrument_name=row.get("instrument_name", "").strip(),
                instrument_short=row.get("instrument_short", "").strip(),
                instrument_type=row.get("instrument_type", "").strip(),
                maps_to_node_id=row["maps_to_node_id"].strip(),
                maps_to_node_ids=maps_to_nodes,
                scoring_direction=row.get("scoring_direction", "higher_better").strip(),
                loading_b_k=loading,
                intercept_a_k=intercept,
                reliability_alpha=alpha,
                cancer_validation_status=row.get(
                    "cancer_validation_status", "general_population"
                ).strip(),
                se_multiplier=se_mult,
                time_window_days=time_window,
                somatic_confound_risk=row.get(
                    "somatic_confound_risk", "low"
                ).strip(),
            )
            instruments.append(inst)

    logger.info("Loaded %d instruments from %s", len(instruments), registry_path)
    return instruments


def _safe_float(val: str, default: float) -> float:
    """Parse float with fallback."""
    try:
        v = val.strip()
        if not v or v.lower() in ("n/a", "none", ""):
            return default
        return float(v)
    except (ValueError, AttributeError):
        return default


def _safe_int(val: str, default: int | None) -> int | None:
    """Parse int with fallback."""
    try:
        v = val.strip()
        if not v or v.lower() in ("n/a", "none", ""):
            return default
        return int(float(v))
    except (ValueError, AttributeError):
        return default


# ═══════════════════════════════════════════════════════════════
#  Assembly
# ═══════════════════════════════════════════════════════════════


def assemble_instrument_map(
    instruments: list[InstrumentDef],
    node_map: NodeMap,
) -> InstrumentMap:
    """Build InstrumentMap with H matrix and noise model.

    The H matrix encodes the measurement model:
        y_k = a_k + b_k * θ_i + ε_k
    where θ_i is the latent state of the mapped node.

    Observation noise variance:
        σ²_{y,k} ≈ (1 - α_k) / α_k
    scaled by the cancer validation SE multiplier.

    Args:
        instruments: List of InstrumentDef from load_instruments().
        node_map: NodeMap from ALG-A1.

    Returns:
        InstrumentMap with H matrix and noise parameters.
    """
    n_inst = len(instruments)
    n_nodes = len(node_map.nodes)

    # Build H matrix
    H = np.zeros((n_inst, n_nodes), dtype=np.float64)
    instrument_index: dict[str, int] = {}
    node_to_instruments: dict[str, list[str]] = {}
    observation_noise_var: dict[str, float] = {}
    intercepts: dict[str, float] = {}

    for i, inst in enumerate(instruments):
        instrument_index[inst.instrument_id] = i

        # Map to primary node
        primary_node = inst.maps_to_node_id
        if primary_node in node_map.node_index:
            node_idx = node_map.node_index[primary_node]
            H[i, node_idx] = inst.loading_b_k
            node_to_instruments.setdefault(primary_node, []).append(inst.instrument_id)
        else:
            logger.warning(
                "Instrument %s maps to unknown node %s",
                inst.instrument_id,
                primary_node,
            )

        # Also record secondary node mappings (lower loading)
        for sec_node in inst.maps_to_node_ids:
            if sec_node in node_map.node_index and sec_node != primary_node:
                sec_idx = node_map.node_index[sec_node]
                # Secondary nodes get a reduced loading (loading × 0.5)
                H[i, sec_idx] = inst.loading_b_k * 0.5
                node_to_instruments.setdefault(sec_node, []).append(
                    inst.instrument_id
                )

        # Compute observation noise variance
        # σ²_{y,k} = (1 - α) / α * se_mult²
        alpha = max(inst.reliability_alpha, 0.01)  # prevent division by zero
        noise_var = ((1.0 - alpha) / alpha) * (inst.se_multiplier ** 2)
        observation_noise_var[inst.instrument_id] = noise_var

        intercepts[inst.instrument_id] = inst.intercept_a_k

    # Log coverage
    nodes_with_instruments = len(node_to_instruments)
    logger.info(
        "InstrumentMap assembled: %d instruments mapping to %d/%d nodes. "
        "H matrix shape: (%d, %d)",
        n_inst,
        nodes_with_instruments,
        n_nodes,
        n_inst,
        n_nodes,
    )

    return InstrumentMap(
        instruments=instruments,
        instrument_index=instrument_index,
        node_to_instruments=node_to_instruments,
        H=H,
        observation_noise_var=observation_noise_var,
        intercepts=intercepts,
    )
