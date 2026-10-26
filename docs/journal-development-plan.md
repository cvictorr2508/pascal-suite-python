# Development plan for a SUSCOM journal submission

Prepared on 26 October 2026. Target: Sustainable Computing: Informatics and Systems, Elsevier, ISSN 2210-5379.

The next research contribution should establish when regional energy measurements around native optimization calls are reliable, what instrumentation costs, and how the measurements support a bounded energy and solution-quality comparison. The conference prototype supplies software and exploratory evidence. A journal submission requires a validated method and new evidence.

This document is a proposed research and development sequence. The current change records planning and the updated publication route. It does not approve experiments, HPC access, solver runs, scientific acceptance thresholds, releases, public deployment, or submission.

## Publication route and preserved baseline

The author supplied the WPADS 2026 decision on 26 October: submission 36682 was not accepted. The supplied notification includes review material. The correspondence and review text remain outside this public repository. The journal route should be planned as a new submission based on the research, subject to verification of any other publication or consideration. Do not describe the work as an accepted conference article or automatically apply conference-extension rules. Existing public manuscript pages and software/data deposits must be disclosed accurately.

Repository baseline inspected on 26 October:

- Integration branch: `develop`, commit `4216cf84e61fdb0c34e433f15836de0ba34c9865`.
- Public branch: `main`, commit `810317984e1b4050db05634ce7d30de64145fdba`.
- Campaign execution: `fbbf7d7178e022ff8cf759d8fd7568359b583cf8`, generation `corrected-minimize-300s-v2`.
- Software v0.2.0: `7e9735808b8ca5f45732d7254a20028d187493bd`.

These are different identities. Preserve the submitted WPADS PDF/HTML/LaTeX, old MAXIMIZE results, corrected results, retry records and published deposits. Start a separate journal manuscript and a new experimental generation when those stages are approved.

The prior portable M0 inspection executed the existing compact 31-test suite successfully on this computer. That result is neither a new full-suite run nor proof of physical reproducibility. The last recorded full-suite result remains 144 tests and 26 subtests from 11 October. Development uses the project's Python 3.13 requirement; compact standard-library checks running on Python 3.10 do not certify a full development environment.

## Research contribution and questions

Working title: *Auditable Regional Energy Measurement for Mathematical Optimization on HPC Systems*.

The proposed contribution combines a validated temporal attribution method, stable experimental provenance, and a small controlled study. It does not introduce a MILP algorithm or claim independent sensor calibration without suitable evidence.

| Question | Required evidence | Claim boundary |
| --- | --- | --- |
| RQ1: Under which phase durations, sampling conditions and proxy delays is regional attribution reliable? | Known-boundary traces, temporal fault injection, measured phase boundaries, sample counts, uncertainty and overhead experiments | Agreement of total RAPL paths alone cannot validate child regions |
| RQ2: Does workload identity and parameter equivalence survive filtering, reordering and retries? | Stable identity/seed contract, negative tests, immutable physical attempts and complete composition lineage | A valid telemetry observation may still violate the execution contract |
| RQ3: How do selected solver configurations trade energy against achieved quality? | Common workloads and budgets, terminal quality, timestamped progress, aligned energy, blocked analysis and non-attainment reporting | Scope is the tested instances/hardware; solver-native gaps alone do not define cross-solver quality |
| Optional RQ4: Does the supported measurement regime transfer? | A second machine or architecture and the same measurement protocol | Offline replay alone is software portability, not physical energy reproducibility |

A minimum journal candidate needs credible RQ1 evidence, demonstrated RQ2 behavior and a useful controlled case study for RQ3. Optional hardware, additional profiles and thread scaling enter only after these work. This is a contribution hypothesis to challenge against the literature, not a promise of novelty or acceptance.

## Evidence already available

The M0 archive inspection found 270 Gurobi and 90 SCIP logical metadata records. All record time-limit termination. Terminal objectives are present; Gurobi terminal bounds/gaps are finite in those records. SCIP records contain missing or sentinel gaps and many missing/sentinel bounds. Presence and a finite-value screen do not independently validate solutions or admissibility.

Analyzer records contain timestamped power samples and regional boundaries. The compact tables provide derived regional time, energy and EDP. The inspected material does not supply solver-progress trajectories sufficient to reconstruct energy-to-quality targets retrospectively.

Therefore:

1. Reuse the legacy data first to map terminal-quality availability, sample coverage and invalidity, with generation-aware lineage.
2. Do not infer temporal progress from final objectives, run start times or terminal runtimes.
3. Require raw/progress evidence before claiming that an energy-to-target curve is available.
4. Preserve the SCIP/default/instance-15 seed limitation: originals used 10002, the two replacements used 10000, and four original-valid observations remain below the historical minimum of five.
5. Keep incomplete physical retry provenance, the external PNG checksum mismatch and report sanitization as explicit archival issues. No correction to published records is part of this planning change.

## Work packages and proposed pull requests

The identifiers below are planning labels, not reserved GitHub PR numbers. Every implementation PR targets `develop`, includes focused validation and remains independent of any merge or publication decision.

| Stage and estimated active effort | Proposed changes and existing code anchors | Exit evidence and dependency |
| --- | --- | --- |
| S0, 2–3 working days | Planning/status documentation; private decision and evidence matrix; literature/novelty matrix; journal requirements register | Researchers agree on questions, claim boundaries, review responsibilities and the first implementation scope |
| S1, 1–2 weeks | P1: stable workload/replicate identity and explicit seed policy in `experiment_models.py`, `experiment_profiles.py`, adapters, CLI and both runners. P2: strict retry admission and physical-attempt lineage beside `audit_scip_retry_composition.py` and matrix/comparison scripts | Filtering/reordering cannot change effective parameters; seed or contract mismatch blocks admission; legacy records stay immutable. Depends on S0 |
| S2, about 1 week | P3: separate offline evidence audit/export and compact results; extend `export_research_evidence.py` and relevant tests only where needed | Per-run quality availability and telemetry validity are distinguished; manifests link original/distributed hashes; replay has a documented scope. Depends on S1 where new contracts are required |
| S3, 2–3 weeks | P4: proxy/boundary observability and hardware-domain provenance in native proxy, `pascalops.py`, `solver_regions.py` and validation. P5: synthetic temporal validation and controlled overhead protocol. P6: bounded progress capture in Gurobi/SCIP runners and an alignment schema | Timing error and sample coverage are observable; negative tests detect shifted regions; progress overhead and clock mapping are testable. No HPC run is implied by merging software |
| S4, about 1 week plus queue | P7: reviewed pilot contract and launch documentation, then a separately approved pilot | License/memory feasibility, measurement support, sampling, progress capture, cost and stop conditions pass. Requires S1–S3 and explicit resource authorization |
| S5, 2–3 weeks plus queue | P8: frozen confirmatory contract, then approved data collection; P9: derived statistics and figures in a new generation | Complete attempts, invalidity/retry accounting, uncertainty and bounded claims. Requires pilot go/no-go |
| S6, 2–3 weeks | P10: separate journal manuscript, sources and contribution matrix; P11 only if needed: reviewed software/data release preparation | Coauthor review, current journal requirements, verified artifacts and explicit submission/publication approval |

Total planning allowance is roughly 10–14 active weeks, excluding queueing, unavailable resources and coauthor turnaround. Responsibilities are proposed roles: corresponding author for scientific/resource decisions; software maintainer for contracts and tests; designated methodology reviewer for measurement/statistics; all coauthors for manuscript claims. Assign names and availability at S0.

### Stable identities and retries

Use content-based workload identity, a persistent replicate identifier, and an explicit recorded seed policy. Avoid a seed derived from the workload's position in a filtered list, unstable language hashes or basename alone. A retry of a failed physical execution must preserve its intended replicate seed and execution contract; a new replicate gets a new explicit identity. Equal seed numbers across different solvers do not imply identical random streams.

Record requested and effective parameters, model direction, source/configuration/workload hashes, resource treatment and relevant allocation/software identities. Keep physical-attempt IDs distinct from logical replicate slots. Admission validates contract equivalence separately from telemetry validity and selects permitted replacements chronologically. Missing metadata fails closed. Never select attempts by objective, status, energy, duration or EDP.

Acceptance tests must include list filtering, reordering, moved files, duplicate basenames, seed drift, missing effective parameters, hash tampering and complete retained/replaced lineage. Historical readers must continue to report legacy records without inventing new fields or silently recertifying them.

### Regional validation and instrumentation overhead

Retain the historical semantics: region 0 is the instrumented pipeline, 0.1 is native model import, and 0.2 is optimization; configuration and starts remain in 0 outside its child regions.

The measurement study needs three distinct layers:

1. **Algorithmic attribution:** integrate synthetic traces with known analytical energy and phase boundaries. Exercise shifted boundaries, jitter, gaps, out-of-order timestamps, overlapping domains and counter wraparound. Include a case where whole-run agreement holds while child-region attribution is wrong.
2. **Temporal implementation:** record region request, native handling and acknowledgement times, clock source/units, calibration or mapping between clocks, sample timestamps and gaps. Measure synchronization delay and uncertainty for each boundary. An acknowledgement alone does not establish alignment to an energy sample.
3. **Hardware observation:** record CPU model, sockets, topology, cpuset/affinity, kernel, software versions, governors/turbo where observable, domain names/units and non-overlapping aggregation. Measure actual rather than requested sample intervals, counts per phase, endpoint coverage and invalidity by duration.

Compare feasible ablation modes under an equivalent mathematical workload: native solver baseline; proxy/marking only where separable; sampler without child marking; full instrumentation; full instrumentation plus progress capture. Verify which modes the existing architecture can support before fixing the design. Measure energy overhead with the same reference acquisition in every arm, including the baseline; an unmeasured baseline cannot be assigned zero joules. Account for the reference acquisition's own overhead.

Use a controlled short-to-long phase study rather than artificial delays inside scientific solves. Report error and coverage versus phase duration/sample interval, and how boundary uncertainty propagates into energy. Two samples alone are not a scientifically justified regional acceptance criterion. Derive and freeze temporal/energy tolerances from the intended use and pilot evidence before confirmation; do not silently reuse the old whole-program 5% criterion as a regional guarantee.

A synchronized wattmeter/PDU is an optional independent reference, subject to availability and compatible resolution. It measures a different domain unless reconciled with RAPL. Without it, limit physical claims to observed RAPL-domain behavior and validated temporal attribution. Node exclusivity does not make all package energy exclusively attributable to one process or the requested cores.

### Quality capture and energy alignment

Gurobi callbacks expose incumbent/bound and runtime/work information; PySCIPOpt supports solver event handlers. Implement a small versioned progress record containing attempt/replicate identity, event type, monotonic timestamp or explicit clock mapping, incumbent/bound availability, termination and relevant native solver time.

Bound event logging and buffering. Preserve the original solver behavior; do not change stopping rules, heuristic decisions or profiling semantics to improve plots. Record observation staleness and callback availability. Measure the overhead of enabling progress capture independently.

Choose a common quality reference and targets before confirmatory data collection. Best-known values are not certified optima; a solver's own relative gap is not automatically a cross-solver quality scale. Record missing incumbents, invalid/sentinel bounds and targets never reached. Restrict energy-to-target estimates to adequately covered time intervals and report timing uncertainty. Do not interpolate improvement events that were not observed.

## Small staged experiment and cost proposal

First use the old data for offline evidence mapping. The new pilot and confirmation use only default profile and one core initially. Choose a small diverse set by documented structural and feasibility criteria rather than by which solver wins. Keep pilot exploration separate from confirmatory inference; changes after the pilot must be frozen before confirmation.

| Proposed work | Design | Nominal solve budget | Planning provision |
| --- | --- | --- | --- |
| Measurement/overhead pilot | Small known-phase and ablation study; exact matrix fixed after feasibility review | Separate from solver-budget accounting | Proposed ceiling of 2 node-hours, to approve and enforce |
| Solver/progress pilot | 2 solvers × 3 candidate instances × 3 attempts, up to 300 s each | 18 attempts, 1.5 solver-hours | 2.25 node-hours if 50% allowance covers startup/read/cleanup |
| Initial confirmation | 2 solvers × 6 preselected instances × 6 replicates, up to 300 s each | 72 attempts, 6 solver-hours | 9 node-hours under the same illustrative allowance |
| Optional scaling | Gurobi × 2 additional thread settings × 3 instances × 6 replicates | 36 attempts, 3 solver-hours | Additional 4.5 node-hours; a new decision |

The initial planning sum is 13.25 node-hours including the proposed 2-hour measurement allowance; optional scaling raises it to 17.75. These are conditional provisions, not established runtimes or approved allocations. Include reference instrumentation, failed attempts and retries within an explicitly approved ceiling. Native time limits can overrun, so budget control also needs scheduler walltime and stop rules.

Reserved CPU-hours equal allocated CPUs per node multiplied by exclusive node-hours; active solver threads are not the allocation charge. Confirm the actual allocation topology and accounting rather than inferring it from `intel-128`. Set memory, storage, job count, retry count and total reservation limits before launch. If costs exceed the approved ceiling, stop and return to the researchers.

Six replicates is a starting design, not a power calculation. Pilot variability and the desired precision determine the frozen sample size within a stated maximum. Do not stop when results become favorable or expand the matrix automatically. Presolve-off, warm-start, more families and a second architecture are optional extensions requiring a question and budget.

## Analysis and publication criteria

Use instance and execution block as scientific units; repeated attempts are nested observations, not additional independent benchmark problems. Randomize/balance order where operationally feasible, block node/date and retain actual execution order. Keep a fixed-seed repeatability question distinct from variation across an explicit seed schedule.

Report paired effects, per-instance results, failure/non-attainment rates and uncertainty. Resampling or models must respect instance/block clustering. With only six instances, broad population inference is limited. Hypothesis tests are needed only for a prespecified scientific hypothesis; absence of significance does not establish equivalence. Declare any equivalence margins before collection.

Keep telemetry validity, same-contract admission, solver completion and solution quality as separate axes. Report missingness by treatment and phase; do not assume that objective-independent telemetry rejection guarantees unbiased comparisons. Compare terminal quality and energy jointly. EDP is secondary where nearly fixed duration makes it redundant.

Minimum submission evidence:

- An architecture and timing diagram understandable without reading source code.
- A region-validity and overhead study, including negative cases and a supported operating regime.
- Complete versioned contracts and provenance with tested retry admission.
- A useful, bounded energy/quality case study with uncertainty and limitations.
- Reproducible tables/figures and a portable offline replay with declared verification scope.
- A clear novelty comparison with existing RAPL mechanisms/workflow measurement and PaScal work.

Write from a concrete motivating example, then problem, contribution, method and evidence. Define terms when introduced. Use numbered tables/captions according to the verified journal guide. Distinguish sensor accuracy from numerical/internal consistency. Remove TRL claims unless an explicit appropriate assessment substantiates them. Human coauthors must revise argument, language and claims; an AI declaration should describe actual use under the current applicable policy.

Suggested manuscript sequence: introduction and contributions; related work; system/clock/domain model; validation and overhead; experimental protocol; energy/quality results; threats and limitations; artifact availability. Draft the introduction early, but do not write results before evidence exists.

## Journal requirements and literature

The official Elsevier journal description explicitly includes power-aware software, profiling, and monitoring of parallel/distributed systems. This supports thematic fit, not sufficient novelty or likely acceptance. [Elsevier journal description](https://shop.elsevier.com/journals/sustainable-computing-informatics-and-systems/2210-5379).

The journal-specific [Guide for Authors](https://www.sciencedirect.com/journal/sustainable-computing-informatics-and-systems/publish/guide-for-authors) returned HTTP 403 on 26 October. Keep article type, length, abstract, anonymization, highlights/graphical abstract, data/code statements, template, AI policy, fees and institutional agreements pending until verified from the current official guide. Do not inherit the conference page limit or invent a percentage of required new material. General Elsevier guidance makes original reporting, attribution and publication overlap relevant; journal-specific requirements still govern. [Elsevier publishing ethics](https://www.elsevier.com/about/policies-and-standards/publishing-ethics).

Build a focused literature matrix covering measurement boundary, sampling, overhead, attribution, fault handling, provenance and quality. Initial primary sources include:

- Raffin and Trystram, [Dissecting the software-based measurement of CPU energy consumption](https://arxiv.org/html/2401.15985v2): mechanisms, domain boundaries, sampling and overhead. Cite this as a preprint version unless the final publication metadata are separately verified.
- Thamm and Leser, [Strategies to Measure Energy Consumption Using RAPL During Workflow Execution on Commodity Clusters](https://arxiv.org/html/2505.09375v2): workflow granularity, fault tolerance and managed-cluster measurement.
- [Gurobi callback reference](https://docs.gurobi.com/projects/optimizer/en/current/reference/numericcodes/callbacks.html) and [PySCIPOpt 6.2.1 event handlers](https://pyscipopt.readthedocs.io/en/v6.2.1/tutorials/eventhandler.html): implementation feasibility, not evidence that this project already captures progress.

This initial source set is not a systematic review. Include recent closely related journal articles and the existing PaScal bibliography before fixing the novelty claim. Do not cite the target journal merely to increase its citation count.

## Storage and delivery

Use GitHub PRs as the primary reviewed development record. Local development artifacts, when needed, belong under the user's `C:\Users\cvict\.codex` area. The OneDrive `Temp Codex/pascal-suite-python` directory is temporary input/staging, never a source checkout or development output root. An existing source clone need not be edited.

Keep source, tests, contracts, documentation, compact processed tables and checksums in Git. Keep raw traces, benchmark files, starts, licenses and private correspondence outside Git in authorized evidence storage. Codex local storage is working storage, not a long-term scientific archive. Authorized future deposits need reviewed immutable versions and stable references. No new release or deposit is part of this plan.

Protect the existing WPADS manuscript and public `main`/Pages state. Future journal sources should live in a separate manuscript directory and must not overwrite `index.qmd` as a migration shortcut. English remains the language of repository documentation and PRs.

## Decisions and next bounded task

The next recommended implementation is P1: stable workload and replicate identity with an explicit seed contract, followed by P2 strict retry admission. It removes a known scientific failure mode before investment in new measurement. Do not repeat the closed legacy NPAD audit.

Before authorizing that task, settle only the decisions that affect its behavior: preserve fixed-seed repeatability or introduce a versioned per-replicate seed schedule; required identity fields; and backward-compatible handling of old records. Resource availability and experimental ceilings can be decided later, before the pilot.

A future P1 instruction should name the base commit/branch, exact schema/adapter/runner/CLI scope, negative tests, backward-compatibility expectations and stop condition. It must exclude solvers, HPC, retrospective metadata repair, manuscript edits, release and deployment. This planning PR does not start P1.

Before a pilot, the researchers must also approve the dual-solver scope, reference-measurement availability, hardware/resource limits, measurement tolerances and statistical protocol. Merge, resource execution and publication remain separate decisions.
