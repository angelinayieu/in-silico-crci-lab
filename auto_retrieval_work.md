Rigorous Breakdown: What's Preventing Scaling
THE DATA REALITY
Metric	Current	Needed for VS-1	Full System
Studies in DB	16	~30-40	200+
Evidence rows	33	~70	1000+
Compiled edges	25	14 (VS-1)	141
Edges with sane SE	6 of 25	14	141
VS-1 edges with evidence	4 of 14	14	—
Papers discovered via System 1	0	any	all
BLOCK 1: SE Calibration Catastrophe (Data Corruption)
Severity: CRITICAL — this breaks ALL downstream algorithm outputs

19 of 25 compiled edges have SE values ranging from 35,000 to 6 TRILLION. A Cohen's d effect size of 0.86 gets a CI of [-62,712,302 — +62,712,304]. The Bayesian update treats every edge as having infinite uncertainty, making the model output meaningless.

Root cause: load_evidence_into_db.py runs Step 4c (harmonize to Cohen's d) then Step 4d (7-layer P3-8 SE calibration in se_eff_assembly.py). When raw mean-difference SE (e.g., 5.28) enters the P3-8 formula before being properly scaled to Cohen's d units, the multiplier chain m_design × m_scale × m_GRADE on an already-large base produces astronomical values. The se_inflation_applied metadata claims ~2x inflation but actual ratios are 100,000x+.

Actual SE values in DB:

5 HPA edges: SE > 100 billion
4 cognitive activity edges: SE ~ 30-60 million
6 activity edges: SE ~ 400K-640K
2 fatigue edges: SE ~ 58-61K
Only 6 edges are sane (SE < 36): ER_OIC_PROCSPEED, ER_OIC_ATTNSUST, ER_OIC_EPISODIC, ER_OIC_WORKMEM, ER_OIC_COGCOMPLAINTS, ER_NEUROPLAST_EPISODIC
BLOCK 2: Retrieval System (System 1) — Never Operated
Severity: HIGH — zero automated paper discovery has ever run

2a. Missing glue script
run_triage_sweep.py — referenced 8 times across docs as the connector between System 1 (discovery) and System 2 (extraction). Does not exist. There is no way to take scored acquisition candidates and feed them into the extraction pipeline automatically.

2b. Dead code / unwired modules
Module	Lines	Status
pathway_evidence_auditor.py	331	DEAD CODE — never imported by anything
config.py load_retrieval_config()	98	DEAD CODE — function never called; adapters read env vars directly
run_extraction_demo.py	148	DEAD CODE — hardcoded to cherrier2013.pdf, raw API call, bypasses pipeline
2c. Missing API keys (4 of 6 retrieval sources degraded/broken)
Variable	Status	Impact
ANTHROPIC_API_KEY	Configured	LLM extraction works
NCBI_API_KEY	NOT SET	PubMed rate-limited to 3 req/s (vs 10)
OPENALEX_EMAIL	NOT SET	Excluded from "polite pool" — may be throttled
UNPAYWALL_EMAIL	NOT SET	BROKEN — adapter requires email, fails silently
CORE_API_KEY	NOT SET	CORE source completely non-functional
S2_API_KEY	NOT SET	Semantic Scholar rate-limited
2d. Security issue
.env. (note trailing dot in filename) contains a plaintext ANTHROPIC_API_KEY. Accidental file, likely committed to git.

2e. Empty outputs
retrieval_candidates contains only a README — zero candidates ever stored. The 8 retrieval adapters (PubMed, OpenAlex, Europe PMC, Crossref, Unpaywall, arXiv, CORE, Semantic Scholar) are all real implementations with HTTP calls, but they've never been run against live APIs in a discovery capacity.

BLOCK 3: Extraction System — Wired but Bottlenecked
3a. Model router is COMPLETELY DISCONNECTED from the pipeline
This is the key finding about the new LLM APIs.

The model_router.py defines 3 model tiers with dollar-optimized routing:

Haiku ($0.25/M): binary triage tasks (has_effect_size, is_rct, abstract_relevance)
Sonnet ($3/M): standard extraction (AG01-AG11)
Opus ($15/M): complex reasoning
But the actual extraction pipeline in runner.py:62 does this:

Every single agent (AG01-AG11) gets the same Sonnet-tier client. The model router's haiku_tasks and opus_tasks mappings are never consulted. The LLMClient.complete() method accepts a model_id override parameter (and even documents it as "Use with model_router.route_task()") but no caller ever passes it.

Who imports model_router?

run_local_extraction_test.py — only prints model names
routing_validator.py — only for validation testing
Not imported by: pipeline.py, runner.py, p0_triage/, any agent.

Cost impact: Sending binary yes/no triage questions to Sonnet instead of Haiku costs 12x more per call. At scale (200+ papers × 11 agents per paper), this adds up fast.

3b. Abstract screener doesn't use LLM
abstract_screener.py uses simple substring keyword matching (cancer keywords + cognitive keywords → score). The model router defines abstract_relevance_binary as a Haiku task, but the screener never calls the LLM. At scale, keyword matching will miss semantically relevant papers and include irrelevant ones.

Similarly, p0_triage/relevance_screening.py uses keyword-density scoring, not the LLM.

3c. 7 PDFs sitting unextracted
In data/manual_uploads/neuroinflammation/round 2/: 7 PDFs from the neuroinflammation workstream have been uploaded but never processed through extraction. These would add evidence to currently-empty VS-1 edges.

3d. Manual-only ingestion path
All 16 studies entered via load_evidence_into_db.py (manual CSV uploads). The automated path (PDF → P0 triage → P1 agents → P2 harmonization → ... → P7 compilation → DB) has the code but has only been tested on 1 paper (run_extraction.py → pipeline.py). The two paths produce data in different formats and there's no reconciliation between them.

BLOCK 4: Vertical Slice Gap
VS-1 defines 14 frozen edges. Current evidence coverage:

Edge	Evidence Rows	Status
ER_OIC_PROCSPEED	4	Has data
ER_OIC_EPISODIC	3	Has data
ER_OIC_ATTNSUST	3	Has data
ER_NEUROPLAST_EPISODIC	1	Has data
ER_OIC_WORKMEM	1	Has data
ER_OIC_COGCOMPLAINTS	1	Has data
OIC→Global_composite	0	EMPTY
OIC indicator loadings (×3)	0	EMPTY
ER_NEUROPLAST_* (other)	0	EMPTY
Remaining edges	0	EMPTY
10 of 14 VS-1 edges have zero evidence. The system cannot produce a meaningful patient recommendation from VS-1 until these gaps are filled.

HOW TO INCORPORATE THE NEW LLM APIS — Action Plan
Phase 1: Fix the data (Days 1-2)
Fix SE calibration in load_evidence_into_db.py:

Step 4c must convert both mean_effect AND se_effect to Cohen's d scale simultaneously
Step 4d's P3-8 formula should receive SE already in Cohen's d units
Re-run the entire load pipeline to rebuild all 25 compiled edges
Delete security leak: Remove .env. and rotate the Anthropic key

Phase 2: Wire the model router (Day 3)
Connect model_router to runner.py:

Import route_task from model_router
For each agent, call route_task(agent_task_name) to get the optimal model
Pass model_id=routed_model to LLMClient.complete() calls
This gives you: AG01-AG08 on Sonnet, triage on Haiku, complex reasoning on Opus
Connect model_router to p0_triage:

Replace keyword-only relevance screening with an LLM-assisted screen
Route abstract_relevance_binary → Haiku (cheap binary classification)
Keep keyword matching as a fast pre-filter, use LLM for borderline cases
Connect model_router to abstract_screener:

Add an LLM fallback for candidates that score MODERATE on keywords
Route to Haiku tier for binary relevance check
Phase 3: Operationalize System 1 (Days 4-5)
Set API keys: Add NCBI_API_KEY, OPENALEX_EMAIL, UNPAYWALL_EMAIL, CORE_API_KEY, S2_API_KEY to .env

Create run_triage_sweep.py: The missing glue script that:

Reads scored candidates from acquisition_queue
Retrieves fulltexts via fulltext_retriever
Stages PDFs for extraction via stage_for_extraction()
Calls run_extraction_pipeline() on each
Loads results into DB
Wire pathway_evidence_auditor.py: Connect it to acquisition_scheduler so gap-priority edges get targeted queries

Phase 4: Extract queued papers (Days 5-7)
Extract the 7 Round 2 neuroinflammation PDFs using the now-wired pipeline
Run acquisition cycle for VS-1 gap edges (the 10 with zero evidence)
Verify end-to-end: Single paper from discovery → extraction → compiled edge → sane SE → algorithm input
Priority Order
#	Action	Blocks	Effort
1	Fix SE calibration	Everything downstream	4h
2	Delete .env.	Security	5min
3	Wire model_router → runner.py	Cost optimization at scale	2h
4	Set retrieval API keys	System 1 operation	30min
5	Create run_triage_sweep.py	Automated discovery→extraction	4h
6	Wire pathway_evidence_auditor	Targeted gap-filling	2h
7	Extract 7 Round 2 PDFs	VS-1 evidence gaps	1h
8	LLM-assist abstract_screener	Screening quality	3h
9	LLM-assist p0_triage relevance	Triage quality	3h
10	Run acquisition cycle for VS-1	Edge coverage	2h
The single most impactful action is #1 (fix SE). Until that's done, every compiled edge is garbage and the algorithm produces meaningless outputs regardless of how many papers you add.