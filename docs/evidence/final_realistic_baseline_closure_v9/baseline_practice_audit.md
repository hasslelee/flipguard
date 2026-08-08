# FHE System Baseline-Practice Audit

## Reviewer concern

The number of externally executed systems should be justified by comparable systems-paper practice, not by accumulating tool names. This audit therefore examines eight official publication PDFs and separates external baselines from internal mechanism ablations.

## Literature precedent

The papers do not use one universal all-system panel. HECATE uses one external system (EVA) and two internal ablations across eight variants and 36 waterlines. ELASM uses two aligned external systems across ten variants and 12,000 sampled plans. DaCapo uses a manual baseline and two mechanism ablations across twelve DNN variants, while treating scale managers as complementary. Orion changes the baseline by sub-question. HECO centers a naive control and Porcupine where synthesis is feasible. AutoFHE, LOHEN, and SLOTHE separate incompatible schemes, runtimes, or comparison units into distinct panels. Exact locators and system-specific details are in `literature_baseline_practice.csv`.

## Implementation requirement

FlipGuard's final external comparison must prioritize exact graph/input/runtime equivalence and independently admissible pairwise claims. The main measured set may be smaller than the related-work census. Numerical-only CoreLab plans, native-runtime panels, common-executor exact arms, and paper-reported systems must remain separate evidence tiers.

## Falsification test

The baseline justification fails if it calls paper-reported systems measured, combines incompatible raw runtimes into a speed ranking, counts internal ablations as independent external systems, or claims that representative systems papers execute every related system.

## Answers to the audit questions

1. **Do top systems papers execute every related system?** No. They select baselines by the research sub-question and often discuss incompatible systems without a shared runtime experiment.
2. **How many direct baselines are typical?** The audited main panels use roughly one to three directly aligned external baselines; Orion is the exception only when its separate sub-question panels are aggregated.
3. **What is the external-to-ablation balance?** Mechanism-focused papers commonly pair one or two external references with one or more internal ablations that establish causality.
4. **What matters more, breadth or baseline count?** Exact workload breadth and a defensible comparison unit matter more than the raw number of tool names.
5. **How are different objectives or runtimes handled?** They are separated into dedicated panels, rerun on a common host when feasible, or left as paper-reported context.
6. **Is V8 categorically insufficient?** No. V8 already contains two external decision-bearing providers, a common Lattigo executor, and a 72-plan CoreLab grid. Its scientific weakness is the unclassified direct repeated flips and pairwise overblocking, not merely provider count.
7. **What is the marginal value of HECATE or Orion?** HECATE adds value only if the pinned artifact exposes an official mode on the same CoreLab graph. Orion has higher marginal breadth as a decision-bearing DNN provider, but only after an actual encrypted-logit preflight with bounded ETA.

## Sources

Only official proceedings, DOI landing pages, or author-hosted publication copies were used. No search snippet or blog was used as evidence.
