# Step 8c: KIISC Competitiveness Review

## Reviewer concern

Artifact volume alone does not make a strong KIISC paper. Reviewers can reject
a large system if the proposition is vague, the experiment unit is inflated,
or the standard benchmark is missing. Conversely, focused primitive papers
can be competitive with a small evaluation when the mathematical statement
and implementation comparison are exceptionally clear.

## Literature precedent

The comparison uses four archetypes rather than a claimed award probability:

- recent JKIISC CKKS/FHE papers such as *Precise Max-Pooling on Fully
  Homomorphic Encryption* combine a focused approximation construction,
  analysis, and implementation timing;
- the CISC-S 2025 excellent-paper program lists *Implementing MultiMax under
  CKKS: A Comparative Study of Recent Homomorphic Softmax*, showing the value
  of a focused primitive plus current baselines;
- HECATE/ELASM are implementation-framework papers with several benchmark
  programs and explicit error/latency search spaces;
- Application-Aware Approximate HE is primarily a formal-definition paper and
  is judged on theorem scope rather than dataset count.

The scores below are reviewer-quality diagnostics, not acceptance or award
probabilities.

## Implementation requirement

Scale: 0-10 per category.

| Category | Current RC2 | Expected after mandatory extension | Evidence for current score | Reviewer objection | Required response |
|---|---:|---:|---|---|---|
| Problem/novelty | 8.0 | 8.3 | candidate-source-independent decision gate, NO_SAFE, locked audit | direct synthesis and repair have close prior art | lead with decision-integrity layer and avoid firstness |
| Formal clarity | 7.4 | 8.8 | binary `e<m` theorem and reserve-policy split | threshold-only definition looks narrow | add proved multiclass argmax proposition and strict boundary |
| Implementation | 8.8 | 9.1 | Go/Lattigo direct execution, immutable policies, verifiers | primary adapters are scalar/tabular | add generic ten-logit and convolution adapters without policy retuning |
| Experimental rigor | 9.2 | 9.3 | frozen roles, security filtering, locked audit, paired protocol | deterministic partitions can be overread | preserve units and add class/gap-bin audit |
| Breadth | 6.8 | 8.5 | polynomial, Sobel/Harris, CNN-lite, training-seed overlays | main evidence still centered on two simple scalar graphs | complete MLP-100 and LeNet-5-small encrypted evidence |
| Reproducibility | 9.5 | 9.5 | RC2, V3/V10, source replay, SHA/verifiers | extension could become an unbound add-on | freeze new protocol, source/model/split digest, resume ledger |
| Communication | 8.0 | 8.8 | authoritative thesis and claim registry | experiment scale is hard to explain quickly | use the non-expert hierarchy and compact standard-benchmark tables |

Aggregate diagnostic: current `57.7/70`; expected after a complete, honest
mandatory extension `62.3/70`. The expected score drops rather than being
silently retained if either standard model is only simulated, security
inadmissible, or not audited.

Readiness interpretation:

- JKIISC journal readiness: current core is viable; multiclass extension would
  materially strengthen breadth and formal clarity.
- CISC excellent-paper range: plausible only with a concise proposition,
  standard benchmark, and a clear demonstration; no award prediction is made.
- CISC top-award range: not asserted; presentation, reviewer mix, novelty
  perception, and competing submissions are unknown.
- International workshop: artifact rigor is strong; model breadth and direct
  comparison to compiler/autotuner baselines remain the main constraints.

## Falsification test

The competitiveness estimate must be lowered if the extension changes frozen
policy constants, tunes on locked audit, labels a custom reduced CNN as full
LeNet without disclosure, lacks a standard baseline denominator, or cannot
rebuild exact model/input evidence. A negative multiclass result may lower
breadth support but is more credible than a post-hoc successful graph.

