# VERIFIED: enums match 11_CONTROLLED_VOCABULARIES.md (all 7 parts)
# VERIFIED: imports — stdlib only (enum)
# VERIFIED: downstream — used by virtually every module
"""
Component: Layer 0 — Controlled Vocabularies
Spec: 11_CONTROLLED_VOCABULARIES.md (all parts)
      05_TABLE_SCHEMAS.md (inline enum constraints)
Purpose: Every constrained-value field as a Python StrEnum.
Reads: Nothing (root module)
Writes: Nothing (imported by all downstream modules)
"""
from __future__ import annotations

from enum import StrEnum, unique


# ═══════════════════════════════════════════════════════════════
#  PART 1: SYSTEM-WIDE ENUMS
# ═══════════════════════════════════════════════════════════════


@unique
class LifecycleClass(StrEnum):
    """Table lifecycle classification (A-E)."""
    A = "A"  # Knowledge
    B = "B"  # Evidence
    C = "C"  # Compiled
    D = "D"  # Policy
    E = "E"  # Output


@unique
class EvidenceGrade(StrEnum):
    """Evidence quality grading (A=strongest, E=weakest)."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


@unique
class EvidenceStrength(StrEnum):
    """3-level confidence classification."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


@unique
class EvidenceStrengthExtended(StrEnum):
    """Extended 4-level confidence with background for theoretical priors."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    BACKGROUND = "background"


@unique
class EvidenceBasis(StrEnum):
    """Provenance class for intervention inclusion."""
    DIRECT_INTERVENTION = "direct_intervention"
    MECHANISTIC_ONLY = "mechanistic_only"
    GUIDELINE_DERIVED = "guideline_derived"
    MIXED = "mixed"


@unique
class EvidenceBasisExtended(StrEnum):
    """Extended evidence basis for research provenance."""
    HUMAN_CLINICAL = "human_clinical"
    HUMAN_OBSERVATIONAL = "human_observational"
    HUMAN_EXPERIMENTAL = "human_experimental"
    IN_VITRO = "in_vitro"
    ANIMAL = "animal"
    MIXED = "mixed"
    THEORY = "theory"


@unique
class EvidenceLevel(StrEnum):
    """Study-level evidence hierarchy."""
    META = "meta"
    RCT = "RCT"
    OBS = "obs"
    MIXED = "mixed"


# ─── Cancer & Clinical Context ───────────────────────────────


@unique
class CancerType(StrEnum):
    """Standard cancer type classification (reconciled superset)."""
    BREAST = "breast"
    LUNG = "lung"
    COLORECTAL = "colorectal"
    HEMATOLOGICAL = "hematological"
    MIXED_SOLID = "mixed_solid"
    GENERAL_POPULATION = "general_population"
    ANY = "any"


@unique
class CancerTypeCompact(StrEnum):
    """Compact cancer type for scope fields."""
    BREAST = "breast"
    COLORECTAL = "colorectal"
    LUNG = "lung"
    MIXED = "mixed"
    ALL = "all"


@unique
class TreatmentPhase(StrEnum):
    """Full clinical treatment phase (6-value ENUM)."""
    PRE_TREATMENT = "pre_treatment"
    DURING_TREATMENT = "during_treatment"
    EARLY_POST = "early_post"
    LATE_POST = "late_post"
    SURVIVORSHIP = "survivorship"
    ANY = "any"


@unique
class TreatmentPhaseCompact(StrEnum):
    """Coarser operational treatment phase (TEXT fields)."""
    ACTIVE_CHEMO = "active_chemo"
    POST_TREATMENT = "post_treatment"
    MIXED = "mixed"
    ALL = "all"


@unique
class CancerValidationStatus(StrEnum):
    """Measurement invariance SE multiplier tier (§2.7)."""
    VALIDATED_CANCER = "validated_cancer"
    USED_CANCER = "used_cancer"
    GENERAL_POPULATION = "general_population"
    KNOWN_SOMATIC_CONFOUND = "known_somatic_confound"


# ─── Pipeline Identification ─────────────────────────────────


@unique
class PipelineStage(StrEnum):
    """Extraction pipeline stage identifiers."""
    P0_TRIAGE = "P0_triage"
    P1_EXTRACTION = "P1_extraction"
    TB_TRUST_BOUNDARY = "TB_trust_boundary"
    P2_HARMONIZATION = "P2_harmonization"
    P2E_EXTENDED = "P2E_extended"
    P3_ASSIMILATION = "P3_assimilation"
    P4_AGGREGATION = "P4_aggregation"
    P5_SUFFICIENCY = "P5_sufficiency"
    P6_DEPLOYMENT_VALIDATION = "P6_deployment_validation"
    P7_COMPILATION = "P7_compilation"


@unique
class PipelineStatus(StrEnum):
    """Pipeline stage outcome (4-value)."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


@unique
class StatusCompact(StrEnum):
    """Compact 3-value status."""
    OK = "ok"
    FAILED = "failed"
    PARTIAL = "partial"


# ─── Polymorphic FK Discriminators ───────────────────────────


@unique
class TargetEntityTypeNorm(StrEnum):
    """Polymorphic FK discriminator for normalization_refs_v1."""
    INSTRUMENT = "instrument"
    MEASURE = "measure"
    FEATURE = "feature"


@unique
class TargetEntityTypeNoise(StrEnum):
    """Polymorphic FK discriminator for observation_noise_v1 (4 targets)."""
    INSTRUMENT = "instrument"
    MEASURE = "measure"
    FEATURE = "feature"
    QUESTION = "question"


@unique
class MemberEntityType(StrEnum):
    """Polymorphic FK for triangulation_members_v1."""
    FEATURE = "feature"


# ═══════════════════════════════════════════════════════════════
#  PART 2: DOMAIN-SPECIFIC — KNOWLEDGE (Class A)
# ═══════════════════════════════════════════════════════════════

# ─── Node & Edge Ontology ────────────────────────────────────


@unique
class Orientation(StrEnum):
    """Scoring direction for DAG nodes."""
    HIGHER_WORSE = "higher_worse"
    HIGHER_BETTER = "higher_better"
    NEUTRAL = "neutral"


@unique
class DirectionalityExtended(StrEnum):
    """Extended directionality with context."""
    HIGHER_WORSE = "higher_worse"
    HIGHER_BETTER = "higher_better"
    NEUTRAL = "neutral"
    CONTEXT = "context"


@unique
class DirectionalityPathway(StrEnum):
    """Pathway interaction direction."""
    BIDIRECTIONAL = "bidirectional"
    A_TO_B = "a_to_b"
    B_TO_A = "b_to_a"


@unique
class NodeRole(StrEnum):
    """Functional role of nodes in DAG."""
    CONTEXT = "context"
    EXPOSURE = "exposure"
    MEDIATOR = "mediator"
    SYMPTOM = "symptom"
    COGNITION = "cognition"
    OUTCOME = "outcome"
    COMPOSITE = "composite"


@unique
class DefaultStateSpace(StrEnum):
    """Allowed state spaces for node definitions."""
    Z = "z"
    RAW = "raw"
    PROBABILITY = "probability"
    ZERO_ONE = "0_1"


@unique
class StateUpdateScale(StrEnum):
    """Temporal update scales for node state estimation."""
    STATIC = "static"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    STUDY_WINDOW = "study_window"


@unique
class RelationType(StrEnum):
    """Edge causal status."""
    CAUSAL = "causal"
    ASSOCIATIONAL = "associational"
    MECHANISTIC = "mechanistic"
    HYPOTHESIZED = "hypothesized"


# ─── Instruments & Measures ──────────────────────────────────


@unique
class InstrumentKind(StrEnum):
    QUESTIONNAIRE = "questionnaire"
    DIARY = "diary"
    CLINICIAN_SCALE = "clinician_scale"
    COGNITIVE_TEST = "cognitive_test"
    OTHER = "other"


@unique
class InstrumentMethod(StrEnum):
    SELF_REPORT = "self_report"
    CLINICIAN_RATED = "clinician_rated"
    OBJECTIVELY_ADMINISTERED = "objectively_administered"
    HYBRID = "hybrid"


@unique
class AdministrationRole(StrEnum):
    SELF_ADMINISTERED = "self_administered"
    INTERVIEWER_ADMINISTERED = "interviewer_administered"
    CLINICIAN_ADMINISTERED = "clinician_administered"
    DEVICE_AUTO = "device_auto"
    UNKNOWN = "unknown"


@unique
class AdministrationSetting(StrEnum):
    CLINIC = "clinic"
    HOME = "home"
    LAB = "lab"
    REMOTE = "remote"
    UNKNOWN = "unknown"


@unique
class MeasureKind(StrEnum):
    BIOMARKER = "biomarker"
    WEARABLE = "wearable"
    CLINICAL_LAB = "clinical_lab"
    IMAGING = "imaging"
    OTHER = "other"


@unique
class ProxyType(StrEnum):
    """How this measure approximates the underlying construct (§2.7)."""
    LEVEL = "level"
    INTERCEPT = "intercept"
    SLOPE = "slope"
    QUADRATIC_SLOPE = "quadratic_slope"
    CAR = "CAR"
    AUC = "AUC"
    BEDTIME = "bedtime"
    AWAKENING = "awakening"
    COMPOSITE = "composite"
    OTHER = "other"


@unique
class SampleMatrix(StrEnum):
    """Biological sample type for biomarker interpretation."""
    PLASMA = "plasma"
    SERUM = "serum"
    CSF = "csf"
    SALIVA = "saliva"
    TISSUE = "tissue"
    STOOL = "stool"
    URINE = "urine"


@unique
class IndicatorType(StrEnum):
    """Biomarker-pathway relationship type."""
    DIRECT_MARKER = "direct_marker"
    PROXY_MARKER = "proxy_marker"
    FUNCTIONAL_READOUT = "functional_readout"


# ─── Pathways & Interactions ─────────────────────────────────


@unique
class PathwayTier(StrEnum):
    """Pathway evidence maturity (§2.3.1-2.3.2)."""
    MECHANISTIC_MODEL_IMPLIED = "mechanistic_model_implied"
    MECHANISTIC_EMERGING = "mechanistic_emerging"
    MECHANISTIC_PLACEHOLDER = "mechanistic_placeholder"
    CLINICAL_MEDIATOR = "clinical_mediator"


@unique
class CausalEvidenceLevel(StrEnum):
    CAUSAL_DEMONSTRATED = "causal_demonstrated"
    STRONG_ASSOCIATION = "strong_association"
    MODERATE_ASSOCIATION = "moderate_association"
    PLAUSIBLE = "plausible"


@unique
class PathwayInteractionType(StrEnum):
    """Cross-pathway interaction type."""
    FEED_FORWARD = "feed_forward"
    CONVERGENT = "convergent"
    ANTAGONISTIC = "antagonistic"
    INDEPENDENT = "independent"


@unique
class SynergyInteractionType(StrEnum):
    """Pairwise intervention interaction."""
    SYNERGISTIC = "synergistic"
    ADDITIVE = "additive"
    ANTAGONISTIC = "antagonistic"


@unique
class ValidationStatus(StrEnum):
    """Empirical confirmation status."""
    VALIDATED = "validated"
    PARTIALLY_VALIDATED = "partially_validated"
    NOT_TESTED = "not_tested"


# ─── Interventions & Actions ─────────────────────────────────


@unique
class ActionClass(StrEnum):
    """10-value coarse intervention taxonomy."""
    SLEEP = "sleep"
    PHYSICAL_ACTIVITY = "physical_activity"
    LIGHT_EXPOSURE = "light_exposure"
    STRESS_REGULATION = "stress_regulation"
    NUTRITION = "nutrition"
    MEDICATION_SUPPORT_NONRX = "medication_support_nonrx"
    COGNITIVE_TRAINING = "cognitive_training"
    SOCIAL_ENGAGEMENT = "social_engagement"
    CLINICAL_FOLLOWUP = "clinical_followup"
    OTHER = "other"


@unique
class DoseType(StrEnum):
    CONTINUOUS = "continuous"
    ORDINAL = "ordinal"
    BINARY = "binary"


@unique
class DoseResponseFamily(StrEnum):
    LINEAR = "linear"
    SATURATING = "saturating"
    HILL = "hill"


@unique
class SchedulePattern(StrEnum):
    ONCE = "once"
    PER_VISIT = "per_visit"
    QD = "qd"
    BID = "bid"
    TID = "tid"
    FIVE_PER_DAY = "5_per_day"
    EVENT_BASED = "event_based"
    CUSTOM = "custom"


# ─── Temporal Dynamics ───────────────────────────────────────


@unique
class KernelFamily(StrEnum):
    """8 temporal kernel families (§2.11)."""
    DELTA = "delta"
    EXPONENTIAL = "exponential"
    STEP = "step"
    GAMMA = "gamma"
    BIEXPONENTIAL = "biexponential"
    SATURATION = "saturation"
    ADAPTATION = "adaptation"
    TRAPEZOIDAL = "trapezoidal"


@unique
class TemporalFamily(StrEnum):
    """Compact 2-value temporal family."""
    DELTA = "delta"
    EXPONENTIAL = "exponential"


@unique
class TimeStepUnit(StrEnum):
    DAY = "day"
    WEEK = "week"


@unique
class TimeAggregation(StrEnum):
    MOMENTARY = "momentary"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    STUDY_WINDOW = "study_window"
    OTHER = "other"


@unique
class TimeAggregationExtended(StrEnum):
    """With circadian-specific bins."""
    MOMENTARY = "momentary"
    DIURNAL = "diurnal"
    TWENTY_FOUR_H = "24h"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    STUDY_WINDOW = "study_window"
    OTHER = "other"


@unique
class TimepointType(StrEnum):
    ANCHOR = "anchor"
    OFFSET = "offset"
    CLOCK = "clock"
    BEDTIME = "bedtime"
    OTHER = "other"


# ─── Statistical Methodology ─────────────────────────────────


@unique
class StudyDesign(StrEnum):
    RCT = "RCT"
    LONGITUDINAL = "longitudinal"
    CROSS_SECTIONAL = "cross_sectional"
    META = "meta"
    INTENSIVE = "intensive"
    MECHANISTIC = "mechanistic"
    OTHER = "other"


@unique
class EffectTypeReported(StrEnum):
    """Extended 8-value set (canonical)."""
    STD_BETA = "std_beta"
    UNSTD_BETA = "unstd_beta"
    PERCENT_CHANGE = "percent_change"
    OR = "OR"
    RR = "RR"
    HR = "HR"
    GROUP_DIFF = "group_diff"
    F_STATISTIC = "f_statistic"
    OTHER = "other"


@unique
class EffectScale(StrEnum):
    """Harmonized output scale."""
    SD_SD = "SD_SD"
    PROXY_PER_SD = "PROXY_PER_SD"
    LOGOR_PER_SD = "LOGOR_PER_SD"
    RAW_PER_SD = "RAW_PER_SD"


@unique
class CanonicalScale(StrEnum):
    """Canonical pooling scale for P4 aggregation.

    P4 must only pool records with matching canonical_scale.
    This prevents nonsensical pooling of Cohen's d with log-OR.
    """
    SMD = "SMD"              # Standardized mean difference (Cohen's d, Hedges' g)
    LOG_OR = "LOG_OR"        # log odds ratio
    LOG_HR = "LOG_HR"        # log hazard ratio
    LOG_RR = "LOG_RR"        # log risk ratio
    FISHER_Z = "FISHER_Z"    # Fisher-z transformed correlation
    RAW = "RAW"              # Unstandardised beta, percent change, other


@unique
class ModelFamily(StrEnum):
    OLS = "OLS"
    LMM = "LMM"
    GLMM = "GLMM"
    GEE = "GEE"
    COX = "Cox"
    OTHER = "other"
    UNKNOWN = "unknown"


@unique
class SEType(StrEnum):
    MODEL_BASED = "model_based"
    ROBUST = "robust"
    CLUSTER_ROBUST = "cluster_robust"
    BOOTSTRAP = "bootstrap"
    UNKNOWN = "unknown"


@unique
class AggregationMethod(StrEnum):
    BLOCKED = "BLOCKED"
    DIRECT = "DIRECT"
    STRATIFIED = "STRATIFIED"
    IVW_FIXED = "IVW_fixed"
    IVW_RANDOM = "IVW_random"
    SINGLE_BEST = "single_best"
    EXPERT_PICK = "expert_pick"


@unique
class BetaDistFamily(StrEnum):
    NORMAL = "normal"
    STUDENT_T = "student_t"
    LOGNORMAL = "lognormal"
    EMPIRICAL = "empirical"
    UNKNOWN = "unknown"


# ─── Correlation & Noise ─────────────────────────────────────


@unique
class NoiseSource(StrEnum):
    PSYCHOMETRIC = "psychometric"
    TEST_RETEST = "test_retest"
    ICC = "icc"
    ESTIMATED = "estimated"
    DEFAULT = "default"


@unique
class DBlock(StrEnum):
    """Block-diagonal D matrix grouping (§2.17.2)."""
    INFLAMMATORY = "inflammatory"
    NEURO_STRESS = "neuro_stress"
    INDEPENDENT = "independent"


@unique
class AgreementMetric(StrEnum):
    PEARSON_R = "pearson_r"
    SPEARMAN_R = "spearman_r"
    ICC = "icc"
    KAPPA = "kappa"
    OTHER = "other"


@unique
class AgreementScope(StrEnum):
    PAIRWISE = "pairwise"
    OVERALL = "overall"


# ─── Derived Features & Variables ────────────────────────────


@unique
class FeatureType(StrEnum):
    STATUS = "status"
    COMPOSITE = "composite"
    INTERACTION = "interaction"
    TREND = "trend"
    VARIABILITY = "variability"
    FLAG = "flag"
    QUALITY_METRIC = "quality_metric"
    CLUSTER_CODE = "cluster_code"
    OTHER = "other"


@unique
class FeatureDomain(StrEnum):
    DEMOGRAPHIC = "demographic"
    TREATMENT = "treatment"
    BEHAVIOR = "behavior"
    SYMPTOM = "symptom"
    PERCEPTION = "perception"
    PHYSIOLOGY = "physiology"
    IMMUNE = "immune"
    NEURO = "neuro"
    BIOMARKER = "biomarker"
    OUTCOME = "outcome"
    DIAGNOSTIC = "diagnostic"
    QA = "qa"
    OTHER = "other"


@unique
class FeatureSource(StrEnum):
    OBSERVED_ONLY = "observed_only"
    DERIVED_ONLY = "derived_only"
    HYBRID = "hybrid"


@unique
class ComputeStage(StrEnum):
    INTAKE = "intake"
    PREPROCESS = "preprocess"
    STATE_ESTIMATION = "state_estimation"
    POSTPROCESS = "postprocess"
    QA = "qa"


@unique
class VariableType(StrEnum):
    BINARY = "binary"
    ORDINAL = "ordinal"
    CONTINUOUS = "continuous"
    CATEGORICAL = "categorical"


@unique
class VariableDomain(StrEnum):
    DEMOGRAPHIC = "demographic"
    TREATMENT = "treatment"
    BEHAVIOR = "behavior"
    SYMPTOM = "symptom"
    PHYSIOLOGY = "physiology"
    OTHER = "other"


# ─── Questions ───────────────────────────────────────────────


@unique
class QuestionRole(StrEnum):
    SAFETY_GATE = "safety_gate"
    BASELINE_INTAKE = "baseline_intake"
    ADAPTIVE_PROFILE = "adaptive_profile"
    MONITORING = "monitoring"
    CALIBRATION = "calibration"


@unique
class AnswerType(StrEnum):
    BINARY = "binary"
    ORDINAL = "ordinal"
    INTEGER = "integer"
    REAL = "real"
    MULTI_SELECT = "multi_select"
    TEXT = "text"
    DATE = "date"
    TIME = "time"


@unique
class ResponseStatus(StrEnum):
    ANSWERED = "answered"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


@unique
class SelectionStage(StrEnum):
    SAFETY_PREREQ = "safety_prereq"
    IDENTIFIABILITY_PREREQ = "identifiability_prereq"
    VOI_RANKED = "voi_ranked"


@unique
class MissingAnswerPolicy(StrEnum):
    SKIP = "skip"
    RETRY = "retry"
    SET_UNKNOWN = "set_unknown"
    ESCALATE = "escalate"


# ═══════════════════════════════════════════════════════════════
#  PART 3: HARMONIZATION (Class B)
# ═══════════════════════════════════════════════════════════════


@unique
class HarmonizationStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    UNREVIEWED = "unreviewed"


@unique
class ConversionFamily(StrEnum):
    UNSTD_BETA_TO_PROXY_PER_SD = "unstd_beta_to_proxy_per_sd"
    STD_BETA_TO_SD_SD = "std_beta_to_sd_sd"
    OR_TO_LOGOR_PER_SD = "or_to_logor_per_sd"
    RR_TO_LOGRR_PER_SD = "rr_to_logrr_per_sd"
    GROUP_DIFF_TO_PROXY_PER_SD = "group_diff_to_proxy_per_sd"
    OTHER = "other"


@unique
class EffectOnPipeline(StrEnum):
    ALLOW = "allow"
    DOWNWEIGHT = "downweight"
    BLOCK = "block"
    FLIP_SIGN = "flip_sign"
    CAP_MAGNITUDE = "cap_magnitude"
    SET_LATENCY = "set_latency"
    SET_PHASE_SCOPE = "set_phase_scope"
    REQUIRE_STRATIFICATION = "require_stratification"


# ═══════════════════════════════════════════════════════════════
#  PART 4: POLICY (Class D)
# ═══════════════════════════════════════════════════════════════


@unique
class ContraindicationSeverity(StrEnum):
    HARD_BLOCK = "hard_block"
    SOFT_PENALTY = "soft_penalty"
    REQUIRE_QUESTION = "require_question"
    ESCALATE = "escalate"


@unique
class ActionTaken(StrEnum):
    BLOCKED_ACTION = "blocked_action"
    PENALIZED = "penalized"
    ASKED_QUESTION = "asked_question"
    ESCALATED = "escalated"
    NONE = "none"


@unique
class SystemBehavior(StrEnum):
    BLOCK_ALL_ACTIONS = "block_all_actions"
    BLOCK_ACTION_CLASSES = "block_action_classes"
    ALLOW_ONLY_LOW_BURDEN = "allow_only_low_burden"
    REQUIRE_CLINICIAN_REVIEW = "require_clinician_review"


@unique
class UnknownInputPolicy(StrEnum):
    TREAT_AS_FALSE = "treat_as_false"
    TREAT_AS_TRUE = "treat_as_true"
    TRIGGER_QUESTION = "trigger_question"
    ESCALATE = "escalate"


@unique
class SelectionRule(StrEnum):
    MAX_EXPECTED_UTILITY = "max_expected_utility"
    RISK_AVERSE_QUANTILE = "risk_averse_quantile"
    CVAR_MIN = "cvar_min"


@unique
class RiskMetric(StrEnum):
    EXPECTED = "expected"
    P10 = "p10"
    P25 = "p25"
    CVAR10 = "cvar10"
    WORST_CASE = "worst_case"


@unique
class OutputMode(StrEnum):
    INDEX_MODE = "index_mode"
    CALIBRATED_MODE = "calibrated_mode"


@unique
class ValidationRuleType(StrEnum):
    FK_INTEGRITY = "fk_integrity"
    RANGE_CHECK = "range_check"
    CROSS_COLUMN_CONSISTENCY = "cross_column_consistency"
    CROSS_TABLE_CONSISTENCY = "cross_table_consistency"
    ENUM_MEMBERSHIP = "enum_membership"
    JSON_SCHEMA = "json_schema"


@unique
class ValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@unique
class EnforcementPoint(StrEnum):
    ETL_COMMIT = "etl_commit"
    RUNTIME_READ = "runtime_read"
    UNIT_TEST = "unit_test"
    ALL = "all"


# ═══════════════════════════════════════════════════════════════
#  PART 5: OUTPUT (Class E)
# ═══════════════════════════════════════════════════════════════


@unique
class ScenarioType(StrEnum):
    STATUS_QUO = "status_quo"
    CANDIDATE = "candidate"


@unique
class PlanType(StrEnum):
    PRIMARY = "primary"
    ALTERNATIVE = "alternative"


@unique
class SourceTag(StrEnum):
    STATUS_QUO_INFERRED = "status_quo_inferred"
    CANDIDATE_GENERATED = "candidate_generated"


@unique
class EvaluationResult(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@unique
class ParameterizationMode(StrEnum):
    MULTIPLICATIVE = "multiplicative"
    ADDITIVE = "additive"
    SET_TO = "set_to"
    DELTA_STEPS = "delta_steps"


# ═══════════════════════════════════════════════════════════════
#  PART 6: IN-MEMORY PIPELINE ENUMS (not persisted)
# ═══════════════════════════════════════════════════════════════

# ─── EX-P0: Triage ───────────────────────────────────────────


@unique
class TriageDecision(StrEnum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


@unique
class ExtractionMode(StrEnum):
    SHALLOW = "SHALLOW"
    STANDARD = "STANDARD"
    DEEP = "DEEP"


# ─── EX-TB: Trust Boundary ───────────────────────────────────


@unique
class ParseStatus(StrEnum):
    CLEAN = "CLEAN"
    AMBIGUOUS = "AMBIGUOUS"
    FAILED = "FAILED"


@unique
class BoundType(StrEnum):
    EXACT = "EXACT"
    UPPER = "UPPER"
    LOWER = "LOWER"


# ─── EX-P2: Harmonization (in-memory) ────────────────────────


@unique
class PlausibilityStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


@unique
class TargetScale(StrEnum):
    SD_SD = "SD_SD"
    LOGHR = "LOGHR"
    LOGOR = "LOGOR"
    PROXY = "PROXY"
    RAW_UNSTD = "RAW_UNSTD"
    RAW_ORIGINAL = "RAW_ORIGINAL"


@unique
class ConversionGateResult(StrEnum):
    PROCEED = "PROCEED"
    SIGN_ONLY = "SIGN_ONLY"
    MAGNITUDE_ONLY = "MAGNITUDE_ONLY"
    BLOCKED = "BLOCKED"


@unique
class SESource(StrEnum):
    SE_DIRECT = "SE_DIRECT"
    SE_FROM_CI = "SE_FROM_CI"
    SE_FROM_P = "SE_FROM_P"
    SE_MISSING = "SE_MISSING"


@unique
class SEDerivationLevel(StrEnum):
    """SE derivation cascade level (CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4).

    6 levels, tried in order L1→L6. First level where all required
    fields are available is used. Each level has an associated inflation factor.
    """
    L1 = "L1"        # SE reported directly — inflation 1.00×
    L2A = "L2a"      # 95% CI — inflation 1.00×
    L2B = "L2b"      # 99% CI — inflation 1.00×
    L2C = "L2c"      # 90% CI — inflation 1.00×
    L3A = "L3a"      # Exact p-value + effect — inflation 1.05×
    L3B = "L3b"      # Bounded p (e.g. p<0.05) — inflation 1.10×
    L4A = "L4a"      # N per group + d — inflation 1.15×
    L4B = "L4b"      # Total N only + d — inflation 1.20×
    L5 = "L5"        # SD borrowed + N — inflation tier-dependent (1.15-1.50×)
    L6 = "L6"        # Direction only, no numeric SE — qualitative


@unique
class SEQualityTag(StrEnum):
    """Quality tag for SE derivation (CONVERSION_VALIDITY_AND_HARDENING.md Module 1.4)."""
    DIRECT = "DIRECT"
    DERIVED_EXACT = "DERIVED_EXACT"
    DERIVED_PVAL = "DERIVED_PVAL"
    DERIVED_PBOUND = "DERIVED_PBOUND"
    ESTIMATED_N = "ESTIMATED_N"
    ESTIMATED_N_EQUAL_ASSUMED = "ESTIMATED_N_EQUAL_ASSUMED"
    SD_BORROWED = "SD_BORROWED"
    QUALITATIVE = "QUALITATIVE"


@unique
class ConversionBiasRisk(StrEnum):
    """Bias risk level for effect-size conversion (CONVERSION_VALIDITY_AND_HARDENING.md Module 1)."""
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
    BLOCKED = "BLOCKED"


@unique
class HarmonizationStatusInMem(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


# ─── EX-P4: Aggregation ──────────────────────────────────────


@unique
class DCRDecision(StrEnum):
    """Double-counting resolution decision (SYS_EX lines 1102-1225)."""
    USE_MA_POOLED = "USE_MA_POOLED"
    USE_PRIMARIES = "USE_PRIMARIES"
    USE_MA_EXCLUDE_OVERLAPPING = "USE_MA_EXCLUDE_OVERLAPPING"
    AMBIGUOUS = "AMBIGUOUS"
    N_A = "N_A"


@unique
class PriorSource(StrEnum):
    EMPIRICAL = "EMPIRICAL"
    LITERARY = "LITERARY"
    UNINFORMATIVE = "UNINFORMATIVE"
    SKEPTICAL = "SKEPTICAL"


@unique
class PriorTypePaper(StrEnum):
    """§2.10 prior selection framework."""
    ROBUST_MAP = "RobustMAP"
    COMMENSURATE = "Commensurate"
    POWER_PRIOR = "PowerPrior"
    MECHANISTIC_SYNTHESIS = "MechanisticSynthesis"
    STRUCTURAL_PLACEHOLDER = "StructuralPlaceholder"


# ─── EX-P4B: Publication Bias ─────────────────────────────────


@unique
class BiasRisk(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    INSUFFICIENT_K = "INSUFFICIENT_K"


# ─── EX-P5: Sufficiency & Coherence ──────────────────────────


@unique
class SufficiencyRecommendation(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    MARGINAL = "MARGINAL"
    INSUFFICIENT = "INSUFFICIENT"


@unique
class TriageTier(StrEnum):
    """§2.13 chain-vs-direct triage."""
    PASS = "PASS"
    MONITOR = "MONITOR"
    INVESTIGATE = "INVESTIGATE"
    ALARM = "ALARM"
    UNTESTABLE = "UNTESTABLE"


@unique
class FailureMode(StrEnum):
    """§2.13.2 discrepancy classification."""
    NONE = "NONE"
    MEDIATION_LEAK = "MEDIATION_LEAK"
    COLLIDER_BIAS = "COLLIDER_BIAS"
    TEMPORAL_MISMATCH = "TEMPORAL_MISMATCH"
    SCALE_INCOMPATIBILITY = "SCALE_INCOMPATIBILITY"
    POPULATION_DRIFT = "POPULATION_DRIFT"
    MISSING_MODERATOR = "MISSING_MODERATOR"


# ─── ALG-A: Intake ───────────────────────────────────────────


@unique
class ProxyValidity(StrEnum):
    DIRECT = "DIRECT"
    PROXY = "PROXY"
    INDIRECT = "INDIRECT"
    NONE = "NONE"


@unique
class ObservationTier(StrEnum):
    """Observation priority tier (C2a).

    TIER_0: Required — abort if missing (cancer_type, treatment, ≥1 cognitive).
    TIER_1: Major gain (PSQI, PHQ-9, FACIT-F, age, IL-6/CRP, activity).
    TIER_2: Pathway (BDNF, cortisol, GAD-7, glucose, APOE, ISI, NfL, etc.).
    """

    TIER_0 = "TIER_0"
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"


# ─── RUNTIME-G: Optimization ─────────────────────────────────


@unique
class SafeMode(StrEnum):
    """Mode A: E[Δz]/uncertainty. Mode B: SAFE·burden·adherence."""
    A = "A"
    B = "B"


@unique
class StabilityClass(StrEnum):
    STABLE = "STABLE"
    SOFT = "SOFT"
    UNSTABLE = "UNSTABLE"


# ─── RUNTIME-I: Reporting ────────────────────────────────────


@unique
class ReportOutputMode(StrEnum):
    CLINICAL = "CLINICAL"
    POPULATION = "POPULATION"
    RESEARCH = "RESEARCH"


@unique
class SeverityTier(StrEnum):
    """6-tier z-score mapping (§2.20)."""
    EXCELLENT = "Excellent"
    GOOD = "Good"
    MILD_CONCERN = "Mild Concern"
    MODERATE = "Moderate"
    POOR = "Poor"
    SEVERE = "Severe"


@unique
class AnchorMethod(StrEnum):
    DISTRIBUTION_BASED = "distribution_based"
    ANCHOR_BASED = "anchor_based"
    EXPERT_CONSENSUS = "expert_consensus"


# ─── VAL-01: Offline Validation ──────────────────────────────


@unique
class HorizontalLevel(StrEnum):
    FULL = "FULL"
    DROP_E = "DROP_E"
    DROP_DE = "DROP_DE"
    DROP_CDE = "DROP_CDE"


@unique
class VerticalLevel(StrEnum):
    FULL_7LAYER = "FULL_7LAYER"
    REDUCED_3LAYER = "REDUCED_3LAYER"
    MINIMAL_1LAYER = "MINIMAL_1LAYER"


# ─── Annotation-specific enums from FILE_CONTEXT_MANIFEST ────


@unique
class AnnotationCategory(StrEnum):
    """22 annotation categories from SYS_EX lines 430-445."""
    LIMITATION_UNMEASURED_CONFOUNDER = "limitation_unmeasured_confounder"
    RESEARCH_GAP = "research_gap"
    ADHERENCE_DATA = "adherence_data"
    ADVERSE_EVENT = "adverse_event"
    MECHANISM_HYPOTHESIS = "mechanism_hypothesis"
    NULL_FINDING_CONTEXT = "null_finding_context"
    TEMPORAL_ONSET = "temporal_onset"
    DOSE_RESPONSE_EVIDENCE = "dose_response_evidence"
    POPULATION_SPECIFICITY = "population_specificity"
    MEASUREMENT_LIMITATION = "measurement_limitation"
    CONFOUNDER_STRUCTURE = "confounder_structure"
    BIOLOGICAL_PLAUSIBILITY = "biological_plausibility"
    CLINICAL_SIGNIFICANCE = "clinical_significance"
    GENERALIZABILITY_CONCERN = "generalizability_concern"
    REPLICATION_STATUS = "replication_status"
    EFFECT_MODIFICATION = "effect_modification"
    SELECTION_BIAS = "selection_bias"
    ATTRITION_BIAS = "attrition_bias"
    DETECTION_BIAS = "detection_bias"
    REPORTING_BIAS = "reporting_bias"
    THEORY_SUPPORT = "theory_support"
    CROSS_VALIDATION = "cross_validation"


@unique
class AnnotationMaturity(StrEnum):
    """Annotation lifecycle maturity (v2.0 Engineering Appendix §A.3).

    Original: raw, reconciled, validated, integrated.
    v2.0: raw, reviewed, promoted, archived.
    Both sets retained for compatibility.
    """
    RAW = "raw"
    RECONCILED = "reconciled"
    VALIDATED = "validated"
    INTEGRATED = "integrated"
    # v2.0 additions
    REVIEWED = "reviewed"
    PROMOTED = "promoted"
    ARCHIVED = "archived"


@unique
class AdjudicationStatus(StrEnum):
    """Annotation adjudication status (v2.0 Engineering Appendix §A.3)."""
    UNREVIEWED = "unreviewed"
    AUTO_MERGED = "auto_merged"
    CONFLICT = "conflict"
    HUMAN_REVIEWED = "human_reviewed"
    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"
    # Retained for backward compatibility with existing reconciliation code
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MERGED = "merged"


@unique
class OverlapDecision(StrEnum):
    """Overlap resolution decisions from SYS_EX lines 1190-1230."""
    KEEP_BOTH = "KEEP_BOTH"
    KEEP_SPECIFIC = "KEEP_SPECIFIC"
    MERGE = "MERGE"
    DROP_DUPLICATE = "DROP_DUPLICATE"


@unique
class GradeLevel(StrEnum):
    """4-level evidence grade for GRADE scoring."""
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


@unique
class ContraindicationStatus(StrEnum):
    """Contraindication evaluation result."""
    CLEAR = "clear"
    FLAGGED = "flagged"
    BLOCKED = "blocked"


# ─── ROB / Causal Identification enums from B6 schema ────────


@unique
class ROBTool(StrEnum):
    ROB2 = "RoB2"
    ROBINS_I = "ROBINS-I"
    NOS = "NOS"
    JBI = "JBI"
    OTHER = "other"


@unique
class ROBOverall(StrEnum):
    LOW = "low"
    SOME_CONCERNS = "some_concerns"
    HIGH = "high"
    CRITICAL = "critical"
    UNCLEAR = "unclear"


@unique
class EstimandClass(StrEnum):
    ATE = "ATE"
    ATT = "ATT"
    CACE = "CACE"
    ITT = "ITT"
    PP = "PP"
    OTHER = "other"


@unique
class IdentificationStatus(StrEnum):
    IDENTIFIED = "identified"
    PARTIALLY_IDENTIFIED = "partially_identified"
    NOT_IDENTIFIED = "not_identified"


# ─── Paper Subtype from SYS_EX ───────────────────────────────


@unique
class PaperSubtype(StrEnum):
    """27 paper subtypes for extraction mode selection.

    Original 23 subtypes + 4 from SYS_EXTRACTION_ADDENDUM Part 2.
    """
    RCT_EXERCISE = "RCT_exercise"
    RCT_COGNITIVE = "RCT_cognitive"
    RCT_PHARMACOLOGICAL = "RCT_pharmacological"
    RCT_MULTIMODAL = "RCT_multimodal"
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    LONGITUDINAL_COHORT = "longitudinal_cohort"
    CROSS_SECTIONAL = "cross_sectional"
    INTENSIVE_LONGITUDINAL = "intensive_longitudinal"
    MECHANISTIC_ANIMAL = "mechanistic_animal"
    MECHANISTIC_HUMAN = "mechanistic_human"
    IMAGING_STRUCTURAL = "imaging_structural"
    IMAGING_FUNCTIONAL = "imaging_functional"
    BIOMARKER_DISCOVERY = "biomarker_discovery"
    DOSE_RESPONSE = "dose_response"
    SAFETY_REPORT = "safety_report"
    GUIDELINE = "guideline"
    CASE_REPORT = "case_report"
    EDITORIAL = "editorial"
    REVIEW_NARRATIVE = "review_narrative"
    PROTOCOL = "protocol"
    QUALITATIVE = "qualitative"
    # ─── 4 new subtypes (SYS_EXTRACTION_ADDENDUM Part 2) ─────
    PSYCHOMETRIC_VALIDATION = "psychometric_validation"
    NORMATIVE_COHORT = "normative_cohort"
    DOSE_RESPONSE_STUDY = "dose_response_study"
    LONGITUDINAL_FOLLOWUP = "longitudinal_followup"
    OTHER = "other"


# ─── Modality & Capture enums from B3 schema ─────────────────


@unique
class ModalityType(StrEnum):
    SELF_REPORT_QUESTIONNAIRE = "self_report_questionnaire"
    SELF_REPORT_DIARY = "self_report_diary"
    BIOSPECIMEN_ASSAY = "biospecimen_assay"
    MEDICAL_RECORD_ABSTRACTION = "medical_record_abstraction"
    COGNITIVE_TESTING = "cognitive_testing"
    WEARABLE_SENSOR = "wearable_sensor"
    OTHER = "other"


@unique
class CaptureMethod(StrEnum):
    PAPER = "paper"
    WEB = "web"
    APP = "app"
    INTERVIEW = "interview"
    PHONE = "phone"
    DEVICE_AUTO = "device_auto"
    LAB_ASSAY = "lab_assay"
    CHART_REVIEW = "chart_review"
    OTHER = "other"
    UNKNOWN = "unknown"


# ═══════════════════════════════════════════════════════════════
#  PART 8: v2.0 EXTRACTION PIPELINE ENUMS
#  Engineering Appendix v2.0 §A.2
# ═══════════════════════════════════════════════════════════════


@unique
class RetrievalStatus(StrEnum):
    """Acquisition queue retrieval state machine.

    Engineering Appendix §A.2: tracks each candidate through the
    retrieval lifecycle. Updated by retriever.py on each attempt.
    """
    PENDING = "PENDING"
    FULL_TEXT_PDF = "FULL_TEXT_PDF"
    FULL_TEXT_XML = "FULL_TEXT_XML"
    ABSTRACT_ONLY = "ABSTRACT_ONLY"
    HUMAN_NEEDED = "HUMAN_NEEDED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"


@unique
class AbstractRelevance(StrEnum):
    """Pre-retrieval abstract screening result.

    Engineering Appendix §A.2: set by abstract_screener.py per
    Master Spec §9.2.1. Only HIGH and MODERATE proceed to retrieval.
    """
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    IRRELEVANT = "IRRELEVANT"


@unique
class MetaSourceFlag(StrEnum):
    """Meta-analysis source classification for edge_evidence_v1.

    Engineering Appendix §A.2: tags entries extracted from
    meta-analyses or special multi-paper compilations.
    """
    POOLED_ESTIMATE = "POOLED_ESTIMATE"
    SUBGROUP_ESTIMATE = "SUBGROUP_ESTIMATE"
    NMA_MIXED = "NMA_MIXED"
    NMA_DIRECT = "NMA_DIRECT"
    FOREST_PLOT_ENTRY = "FOREST_PLOT_ENTRY"
    DOSE_RESPONSE_POINT = "DOSE_RESPONSE_POINT"


@unique
class EffectSizeType(StrEnum):
    """Effect size measurement class.

    Engineering Appendix §A.2: distinguishes between-group,
    within-group, and pre-post change effect sizes.
    Required by Trust Boundary gate TB-G1 (INV-12).
    """
    BETWEEN_GROUP = "BETWEEN_GROUP"
    WITHIN_GROUP = "WITHIN_GROUP"
    PRE_POST_CHANGE = "PRE_POST_CHANGE"


@unique
class FileType(StrEnum):
    """Source file type for study_registry_v1.

    Engineering Appendix §A.2: written by EX-INGEST PDFProcessor.
    """
    PDF = "pdf"
    XML = "xml"
    ABSTRACT_ONLY = "abstract_only"


@unique
class ParseQuality(StrEnum):
    """PDF parse quality assessment.

    Engineering Appendix §A.2: written by EX-INGEST PDFProcessor.
    PARSE_FAILURE blocks entry to EX-P0.
    """
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    SCAN = "SCAN"
    PARSE_FAILURE = "PARSE_FAILURE"


@unique
class ExtractionModeStr(StrEnum):
    """Annotation extraction mode for study_annotations_v1.

    Engineering Appendix §A.3: how the annotation was derived.
    """
    EXPLICIT_AUTHOR_STATEMENT = "explicit_author_statement"
    EXTRACTOR_INFERENCE = "extractor_inference"
    COMPUTED_FROM_CONTEXT = "computed_from_context"


# ═══════════════════════════════════════════════════════════════
#  PART 9: CONVERSION VALIDITY & HARDENING ENUMS
#  CONVERSION_VALIDITY_AND_HARDENING.md Modules 2-5
# ═══════════════════════════════════════════════════════════════


@unique
class ParameterFamily(StrEnum):
    """Parameter family for freshness decay policies (Module 5).

    Each family has its own decay rate and floor.
    """
    PSYCHOMETRICS = "psychometrics"               # α, b_k — 0.0%/yr, floor 1.00
    NORMATIVE_DATA = "normative_data"             # Population norms — 0.5%/yr, floor 0.90
    BIOLOGICAL_CORRELATIONS = "biological_correlations"  # Molecular — 0.5%/yr, floor 0.90
    EDGE_INTERVENTION = "edge_intervention"       # Intervention→outcome — 1.5%/yr, floor 0.70
    EDGE_MECHANISM = "edge_mechanism"             # Mechanism→mechanism — 1.0%/yr, floor 0.80
    INTERVENTION_KERNELS = "intervention_kernels" # Temporal data — 2.0%/yr, floor 0.70
    CONTEXT_PRIORS = "context_priors"             # Baseline levels — 1.0%/yr, floor 0.80
    META_ANALYSIS_POOLED = "meta_analysis_pooled" # MA estimates — 1.5%/yr, floor 0.70
    RECOVERY_CURVES = "recovery_curves"           # Recovery trajectories — 1.0%/yr, floor 0.80


@unique
class EndpointVsChange(StrEnum):
    """Whether a study reports endpoint or change-from-baseline scores (Module 4.3)."""
    ENDPOINT = "ENDPOINT"
    CHANGE = "CHANGE"
    UNCLEAR = "UNCLEAR"


@unique
class LineageRole(StrEnum):
    """Role within a cohort lineage group (Module 4.2)."""
    PRIMARY = "PRIMARY"
    SUPPLEMENTARY = "SUPPLEMENTARY"
    FOLLOW_UP = "FOLLOW_UP"


@unique
class VerificationTier(StrEnum):
    """Verification intensity tier (Module 2)."""
    TIER_1 = "TIER_1"  # 100% human verification
    TIER_2 = "TIER_2"  # 25-30% spot-check
    TIER_3 = "TIER_3"  # 10-15% sample verification


@unique
class EscalationRule(StrEnum):
    """Which escalation rule triggered Tier 1 verification (Module 2.1)."""
    E1_MAJORITY_WEIGHT = "E1"       # w_i > 0.50
    E2_LOW_K = "E2"                 # k < 3
    E3_SIGN_FLIP = "E3"             # removing record flips β̂ sign
    E4_SOLE_CANCER_MATCH = "E4"     # only cancer-matched study + k ≤ 5
    E5_SOFT_SE_HIGH_WEIGHT = "E5"   # se_derivation_level ≥ L4 + w_i > 0.30
    E6_FOREST_PLOT = "E6"           # meta_source_flag = FOREST_PLOT_ENTRY


@unique
class VerificationStatus(StrEnum):
    """Verification lifecycle status for evidence records (Module 2.2)."""
    UNVERIFIED = "UNVERIFIED"
    ESCALATED_TO_TIER1 = "ESCALATED_TO_TIER1"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_CORRECTIONS = "VERIFIED_WITH_CORRECTIONS"


@unique
class MissingnessCode(StrEnum):
    """Why a component is missing from extraction (Module 3.2)."""
    PRESENT = "PRESENT"
    ABSENT_IN_PAPER = "ABSENT_IN_PAPER"
    PARSE_FAILURE = "PARSE_FAILURE"
    AGENT_MISS = "AGENT_MISS"
    GUARDED_REJECTION = "GUARDED_REJECTION"
    TB_REJECTION = "TB_REJECTION"
    PARTIAL = "PARTIAL"


@unique
class CorrectiveAction(StrEnum):
    """Corrective action for missing components (Module 3.3)."""
    SEARCH = "search"
    REPARSE = "reparse"
    RERUN_AGENT = "rerun_agent"
    MANUAL = "manual"
    ACCEPT = "accept"
    REVIEW_RULE = "review_rule"


