Gap Map: What's Actually Broken and Where
There are 4 real gaps (from 7 issues). I've consolidated overlapping issues into coherent slices. Each slice is atomic — it can be committed and tested independently.
Dependency Graph:

  S1 (PathwayDef consolidation)
   ├──→ S2 (config constants)
   │     └──→ S3 (pathway_evidence_scorer.py — new module)
   │           ├──→ S4 (FrozenModelState extension + hash fix)
   │           │     └──→ S5 (run_chain_b wiring + backward compat)
   │           │           └──→ S6 (MC sampler pathway mask — future, deferred)
   │           └──→ S7 (tests)
   └──→ (C4d, pathway_profiler — consumers of shared type, updated in S1)
Slice 1: Consolidate PathwayDef Into Shared Location
Gap addressed: Issue #5 — three independent PathwayDef types exist in three files, each loading PATHWAY_REGISTRY.csv independently.

Current state (horizontal scan)
Location	Type Name	Fields	Loads from CSV?
graph_object.py:44-55	PathwayDef	pathway_id, pathway_label, tier, entry/exit/intermediate_node_ids, component_nodes, edge_ids, is_complete	Yes — load_pathway_registry() line 153
modifier_application.py:408-414	PathwayDef	pathway_id, pathway_label, component_node_ids, activation_threshold, is_sensitive	Yes — load_pathway_registry() line 418
chain_validator.py:49-53	PathwayDefinition	pathway_id, edge_sequence, direct_edge_id	No (constructed internally)
pathway_profiler.py:48-53	PathwayInput	pathway_id, pathway_label, component_node_ids, edge_ids	No (expects pre-loaded)
What to build
Create crci/shared/models/pathway_types.py with:@dataclass(frozen=True)
class PathwayDef:
    """Canonical pathway definition — single source of truth.
    
    Superset of all fields needed by chain_a (graph assembly),
    chain_b (evidence scoring), chain_c (activation detection),
    and runtime (profiling).
    """
    pathway_id: str
    pathway_label: str
    tier: str
    entry_node_ids: list[str]
    exit_node_ids: list[str]
    intermediate_node_ids: list[str]
    component_nodes: list[str]
    edge_ids: list[str]  # populated by chain_a from BSkeleton
    is_complete: bool = True
    # C4d fields
    activation_threshold: float = 0.5
    is_sensitive: bool = False
    # B6.5 fields (new)
    se_multiplier: float = 1.0
    edge_count_registry: int = 0  # from PATHWAY_REGISTRY.csv "edge_count"
    status: str = "connected"  # connected, edgeless

Vertical changes (within each module)
graph_object.py: Delete local PathwayDef, import from shared.models.pathway_types. Extend load_pathway_registry() to parse the additional fields (activation_threshold, is_sensitive, se_multiplier, edge_count, status) from CSV. This function becomes the single canonical loader.

modifier_application.py: Delete local PathwayDef and local load_pathway_registry(). Import the shared type. _detect_pathway_activations() already only reads pathway_id, pathway_label, component_node_ids, activation_threshold, is_sensitive — all present in the shared type.

pathway_profiler.py: Keep PathwayInput as-is (it's a runtime-specific subset, not a registry type) or accept PathwayDef directly — minor refactor, doesn't affect semantics.

Horizontal changes (cross-module)
GraphObject.pathway_map type hint changes from local PathwayDef to shared.models.pathway_types.PathwayDef. Since the fields are a superset, all existing consumers work — but tests that construct PathwayDef directly need the import path updated.

apply_modifiers() in modifier_application.py:648 takes pathways: list[PathwayDef] — callers (e.g., run_session.py) pass what graph_object.load_pathway_registry() returns, so this wires up cleanly.

Test impact
Existing tests that construct PathwayDef(...) (in test_chain_b.py the mini graph uses primary_pathway="" which is fine — it never constructs a PathwayDef directly). Test files for chain_c would need import path updates.
Deliverables
 Create crci/shared/models/pathway_types.py
 Refactor graph_object.py load_pathway_registry() to parse all fields, import shared type
 Refactor modifier_application.py — delete local type + loader, import shared
 Grep for all from.*PathwayDef and update imports
 Run pytest crci/tests/ -v — all 720 pass
Slice 2: Add Config Constants
Gap addressed: Issue #3 — novel formula constants need explicit config.py placement and # EXTENSION: labeling.

What to add
In config.py before the CRCIConfig dataclass (line ~1181), add:
# ═══════════════════════════════════════════════════════════════
#  EXTENSION: ALG-B6.5 — PATHWAY EVIDENCE SCORING
#  NOTE: These formulas (ED-1, DS-1) are extensions not in the
#  original SYS_ALGORITHM spec. They address the pathway evidence
#  density gap identified in system review.
# ═══════════════════════════════════════════════════════════════

# ED-1 quality weights by study count (fractional credit for sparse evidence)
ED_QUALITY_WEIGHT_K3_PLUS: float = 1.0
ED_QUALITY_WEIGHT_K2: float = 0.7
ED_QUALITY_WEIGHT_K1: float = 0.4

# Minimum evidence density to include pathway in active set
MIN_PATHWAY_EVIDENCE_DENSITY: float = 0.15

# Minimum edge coverage for distinction score computation
MIN_EDGE_COVERAGE_FOR_DS: float = 0.6

# Minimum active pathways for model validity (Gate B-G6.5)
MIN_ACTIVE_PATHWAYS: int = 3
Vertical: CRCIConfig update
The CRCIConfig frozen dataclass at the bottom of config.py should receive corresponding fields. Not strictly required (most code imports module-level constants directly), but keeps the aggregated config object complete.

Horizontal: No impact
New constants don't affect any existing code until consumed by Slice 3.

Deliverables
 Add constants to config.py
 Add corresponding fields to CRCIConfig dataclass
 pytest crci/tests/ -v — all 720 pass (no consumers yet)
Slice 3: Create pathway_evidence_scorer.py
Gap addressed: Issue #1, #2, #3, #4 — the core new module, designed correctly.

Critical design decisions (from review findings)
Decision 1 (Issue #1): Do NOT touch build_b_hat_matrix. The scorer produces an active_pathway_ids list. Filtering happens in consumers (Slice 5 for MC sampler, future), not by mutating B̂. The B̂ matrix stays complete.

Decision 2 (Issue #2): No double-counting. The ED formula uses uniform weights across edges (no 1/se_multiplier). The se_multiplier is already applied to SE_eff in B7d (frozen_state.py:397-405). Using it again in ED would double-penalize low-evidence pathways. Instead, se_multiplier is stored in the report for informational purposes only.

Decision 3 (Issue #3): Label as extension. All formulas carry # EXTENSION: ED-1 comments, not spec formula IDs.

Decision 4 (Issue #4): DS returns None for all pathways today. This is acceptable. DS computation is gated by MIN_EDGE_COVERAGE_FOR_DS = 0.6. Current extraction has very few edges with both chain and direct evidence. The function is implemented for correctness but will return None until extraction density increases.

What to build
File: crci/algorithm/chain_b_evidence/pathway_evidence_scorer.py

Types (use dataclasses, frozen):
PathwayEvidenceDensity:
  pathway_id, n_edges_total, n_edges_with_evidence, n_edges_with_rct,
  mean_k, mean_se_eff, se_multiplier (informational), evidence_density, is_active

PathwayDistinctionScore:
  pathway_id, ds_value (float|None), n_testable_edges, coverage_fraction, sufficient_data

PathwayEvidenceReport:
  pathway_densities, pathway_scores, active_pathway_ids, excluded_pathway_ids,
  total_pathways, n_active, n_excluded
Functions:

Function	Reads	Writes	Formula
compute_evidence_density()	PathwayDef (from S1), PooledEdge dict	PathwayEvidenceDensity	ED(P) = Σ(w_k × 𝟙[k≥1]) / n_edges_total where w_k from config
compute_distinction_score()	ChainDirectResult dict, pathway edge_ids	PathwayDistinctionScore	DS-1: RMSE_without − RMSE_with
score_all_pathways()	GraphObject.pathway_map, pooled_edges, chain_direct_results	PathwayEvidenceReport	Orchestrates above two
_validate_gate_b_g6_5()	PathwayEvidenceReport	raises GateViolation	n_active >= MIN_ACTIVE_PATHWAYS
Vertical: Input/output wiring
Reads PooledEdge from evidence_compiler.py:92-105: Uses pooled_edge.k to determine study count per edge. Uses pooled_edge.contributing_studies to check for RCTs (via join to EvidenceRecord.has_rct_component).

Reads ChainDirectResult from evidence_compiler.py:159-174: Uses has_chain_evidence, has_direct_evidence, beta_chain, beta_direct, se_chain, se_direct for DS computation.

Reads PathwayDef (from S1 shared type): Uses pathway_id, edge_ids, se_multiplier, status, edge_count_registry.

Edge-to-pathway mapping: Uses GraphObject.pathway_map (already populated in graph_object.py:187-192) which contains edge_ids per pathway. Also uses EdgeDef.primary_pathway and EdgeDef.secondary_pathways for edges with multi-pathway membership.

Horizontal: What consumes this
assemble_frozen_state() (Slice 4) — receives PathwayEvidenceReport, stores active_pathway_ids in FrozenModelState.
run_chain_b() (Slice 5) — calls score_all_pathways() between B1-B6 and B7.
MC sampler / Chain C (Slice 6, deferred) — reads frozen.active_pathway_ids to filter.
Deliverables
 Create crci/algorithm/chain_b_evidence/pathway_evidence_scorer.py
 All imports resolve (evidence_compiler types, shared config, shared pathway type)
 No float literals — all weights from config.*
 Docstring header with # EXTENSION: labels
Slice 4: Extend FrozenModelState + Fix Hash
Gap addressed: Issue #7 (hash determinism) and Issue #6 (gate placement).

Vertical changes to frozen_state.py
4a. New fields on FrozenModelState:
# B6.5 output: Pathway evidence scoring (EXTENSION)
active_pathway_ids: list[str] = field(default_factory=list)
pathway_evidence_densities: dict[str, float] = field(default_factory=dict)
pathway_distinction_scores: dict[str, float | None] = field(default_factory=dict)
All use field(default_factory=...) → zero breakage for existing constructors.

4b. Fix _compute_frozen_hash():

Currently hashes only B_hat, Sigma_eff, P_inclusion. Must add active_pathway_ids:
def _compute_frozen_hash(
    B_hat: np.ndarray,
    Sigma_eff: dict[str, float],
    P_inclusion: dict[str, float],
    active_pathway_ids: list[str] | None = None,  # NEW — optional for backward compat
) -> str:
Add after P_inclusion hashing:

if active_pathway_ids:
    for pid in sorted(active_pathway_ids):
        hasher.update(pid.encode())

The optional parameter ensures existing callers (existing tests that call _compute_frozen_hash(B, S, P) directly) still work.

4c. Extend assemble_frozen_state():

Add optional parameter:
pathway_evidence_report: PathwayEvidenceReport | None = None,
If provided, populate the three new fields before building hash:
active_pw_ids = []
pw_densities = {}
pw_ds = {}
if pathway_evidence_report is not None:
    active_pw_ids = pathway_evidence_report.active_pathway_ids
    pw_densities = {d.pathway_id: d.evidence_density for d in pathway_evidence_report.pathway_densities}
    pw_ds = {s.pathway_id: s.ds_value for s in pathway_evidence_report.pathway_scores}
    for excl in pathway_evidence_report.excluded_pathway_ids:
        logger.info("B6.5: Pathway %s excluded — ED below threshold", excl)
Pass active_pathway_ids to _compute_frozen_hash().

Horizontal impact
__init__.py exports: Add PathwayEvidenceReport to __all__ in chain_b_evidence/init.py.

All 12 downstream consumers of FrozenModelState (listed below) are unaffected because the new fields have defaults:

Consumer	File	Reads new fields?
prior_loader.py	chain_c	No
modifier_application.py	chain_c	No
mc_sampler.py	chain_d	Not yet (Slice 6)
effect_propagation.py	chain_d	No
intervention_loader.py	chain_d	No
ranker.py	chain_d	No
run_build.py	scripts	No
test_chain_b.py	tests	No
test_chain_d_d2.py	tests	No
Test impact
test_chain_b.py TestReviewRegressions.test_b6_se_multiplier_applied_to_sigma_eff (line ~863): Calls assemble_frozen_state() with explicit keyword args. Since pathway_evidence_report is optional with default None, this test passes unchanged.

test_full_pipeline_with_evidence (line ~815): Calls run_chain_b(). This is affected by Slice 5 — see below.

Deliverables
 Add 3 fields to FrozenModelState
 Update _compute_frozen_hash() with optional active_pathway_ids param
 Update assemble_frozen_state() with optional pathway_evidence_report param
 Update __init__.py exports
 pytest [test_chain_b.py](http://_vscodecontentref_/152) -v — all pass
Slice 5: Wire Into run_chain_b() + Backward Compatibility
Gap addressed: Issue #6 (gate placement), backward compat concern from minor issues.

Vertical change to run_chain_b()
The orchestrator in frozen_state.py:558-616 currently does:
B1-B6 → load_synergy_registry → assemble_frozen_state → return
New flow:
B1-B6 → score_all_pathways (B6.5) → load_synergy_registry → assemble_frozen_state → return
Critical: score_all_pathways must be None-safe. The function needs graph.pathway_map, which requires pathway_registry_path to have been passed to run_chain_a(). If graph.pathway_map is empty (as in test fixtures), scoring is skipped:
# B6.5: Pathway evidence scoring (EXTENSION)
pathway_evidence_report: PathwayEvidenceReport | None = None
if graph.pathway_map:
    pathway_evidence_report = score_all_pathways(
        pathway_map=graph.pathway_map,
        pooled_edges=pooled_edges,
        chain_direct_results=chain_direct_results,
    )
else:
    logger.info("B6.5: No pathway_map — skipping pathway evidence scoring")
This is the key to backward compatibility: the mini graph in test_chain_b.py:64 has pathway_map=[] (default), so scoring is skipped entirely in existing tests.

Horizontal: Gate B-G6.5 enforcement
The gate fires inside score_all_pathways(), not in run_chain_b(). If graph.pathway_map is empty, the gate doesn't fire. This is correct — you can't validate pathway counts without pathway data.

When pathway data IS present but n_active < 3, the gate raises GateViolation("B-G6.5", ...). This is a new failure mode for run_chain_b() that callers (run_build.py) need to be aware of. But since the gate lives inside the scorer module (Slice 3), and run_chain_b() already documents GateViolation in its docstring, no caller changes are needed.

Deliverables
 Modify run_chain_b() to call score_all_pathways() conditionally
 Pass pathway_evidence_report to assemble_frozen_state()
 pytest [test_chain_b.py](http://_vscodecontentref_/172) -v — all pass (mini graph has no pathway_map)
 pytest crci/tests/ -v — all 720 pass
Slice 6: MC Sampler Pathway Mask (DEFERRED — Do Not Implement Now)
Gap addressed: Issue #1 — the original proposal's approach of filtering B̂ is wrong, but the correct alternative (filtering in MC sampler) isn't needed yet.

Why defer
Today, edgeless pathways (M11, M14) have zero edges in the skeleton, so their B̂ entries are already 0. Low-evidence pathways (M08, M12, M17) have edges with StructuralPlaceholder priors (β ~ N(0, 10²)), which means μ_e ≈ 0 in B̂. The practical impact of filtering is near-zero today.

What it would look like (documented for future)
In mc_sampler.py:305-340 _build_edge_map():
def _build_edge_map(
    frozen: FrozenModelState,
) -> tuple[dict[str, tuple[int, int]], dict[str, float]]:
    # ... existing code ...
    for edge in frozen.graph.b_skeleton.edges:
        # FUTURE: Skip edges in inactive pathways
        # if frozen.active_pathway_ids:
        #     if (edge.primary_pathway not in frozen.active_pathway_ids and
        #         not any(sp in frozen.active_pathway_ids for sp in edge.secondary_pathways)):
        #         logger.debug("D1: Skipping edge %s — pathway %s inactive", 
        #                      edge.edge_id, edge.primary_pathway)
        #         continue
Trigger condition
Implement when extraction populates ≥50 edges with real betas AND at least one pathway has ED > 0.15 but poor DS.

Slice 7: Tests for pathway_evidence_scorer.py
Gap addressed: Ensures Slices 1-5 work correctly.

Test cases (with hand-computed expected values)
Test	Setup	Expected	Validates
test_ed_all_zero	Pathway with 6 edges, all k=0	ED=0.0, is_active=False	Zero-evidence floor
test_ed_all_populated_k3	6 edges, all k≥3	ED=1.0, is_active=True	Full-coverage ceiling
test_ed_partial_k1	6 edges, 3 have k=1, 3 have k=0 → ED = (3×0.4)/(6) = 0.2	ED=0.2, is_active=True (0.2 ≥ 0.15)	Quality weighting + threshold
test_ed_below_threshold	6 edges, 1 has k=1 → ED = 0.4/6 ≈ 0.067	is_active=False	Below MIN_PATHWAY_EVIDENCE_DENSITY
test_ds_insufficient_coverage	Pathway with 6 edges, only 2 have chain+direct	ds_value=None, sufficient_data=False	Coverage gate
test_ds_positive	Pathway where RMSE_without > RMSE_with	ds_value > 0	Positive distinction
test_ds_negative	Pathway where RMSE_without < RMSE_with	ds_value < 0	Noise detection
test_gate_b_g6_5_raises	Only 2 pathways active	GateViolation("B-G6.5")	Gate enforcement
test_gate_b_g6_5_passes	5 pathways active	No exception	Gate pass
test_multi_pathway_edges	Edge with primary=PW_M01, secondary=[PW_M09]	Edge counted in BOTH pathways' ED	Multi-membership
test_config_constants_used	Introspect module source	No float literals matching config values	Hardcode scan
test_edgeless_pathway_excluded	Pathway with status="edgeless", 0 edges	ED=0.0, excluded	Edgeless handling
test_empty_pathway_map_skips	graph.pathway_map = []	PathwayEvidenceReport is None	Backward compat
Deliverables
 Create crci/tests/test_algorithm/test_pathway_evidence_scorer.py
 All 13 tests pass
 Full suite: pytest crci/tests/ -v — 720 + 13 = 733 pass
Execution Order (with checkpoints)
Each slice has a single commit message pattern: feat(alg-b6.5): S{N} — {description}.

Summary of Deviations from Original Proposal
Original Proposal	This Plan	Reason
Modify build_b_hat_matrix() to filter edges	Don't touch it — filtering deferred to consumers	Mutating B̂ corrupts Λ_prior computation and hash semantics
w_e = 1/se_multiplier in ED formula	Uniform weights — se_multiplier informational only	Avoids double-counting with B7d SE inflation
Label formulas as "ED-1", "DS-1"	Label as # EXTENSION: ED-1	No spec basis — project rules require explicit extension labeling
Create new PathwayDef locally	Consolidate into shared/models/	Three copies already exist — DRY violation
Hash unchanged	Hash updated to include active_pathway_ids	Two FrozenModelStates with different active sets must hash differently
Gate fires "between B6 and B7" (unspecified)	Gate fires inside score_all_pathways(), called conditionally	Clean integration with existing test fixtures that lack pathway data
