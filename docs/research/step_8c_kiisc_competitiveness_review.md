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

| Category | Current RC2 | Actual after mandatory extension | Evidence for extension score | Remaining reviewer objection | Required response |
|---|---:|---:|---|---|---|
| Problem/novelty | 8.0 | 8.3 | provider-independent gate plus one observed natural-gap literal effect | direct synthesis and repair have close prior art | lead with the combined decision-integrity workflow and avoid firstness |
| Formal clarity | 7.4 | 8.8 | proved strict multiclass argmax proposition, tie/NaN/Inf semantics, reserve split | empirical error is not an instantiated analytical CKKS bound | separate theorem, operational policy, and finite observation |
| Implementation | 8.8 | 9.1 | MLP-100 and convolution/average-pool LeNet execute in Lattigo without policy retuning | feature-ciphertext sample slots are not packed production inference | disclose adapter and packing scope exactly |
| Experimental rigor | 9.2 | 9.3 | frozen 500/500 split, three fresh keys, 0 overlap, 0 retuning, class/gap bins | one dataset and one training seed in the new benchmark | retain finite-scope wording and preserve RC2 seed extension separately |
| Breadth | 6.8 | 8.4 | both mandatory standard models selected and audit SAFE; graph scale reaches depth 4 | LeNet catalog coverage is 0/7 and no packed/deeper modern CNN | report static unsupported result and limit the extension claim |
| Reproducibility | 9.5 | 9.5 | exact model/source/split/binary digests, resumable key ledgers, deterministic freeze | large raw ledgers increase artifact cost | retain verifier and manifest-only navigation |
| Communication | 8.0 | 8.8 | experiment hierarchy, exact unit table, negative-result taxonomy | many accounting units remain easy to conflate | lead with proposition, two model rows, and 14-versus-6 distinction |

Aggregate diagnostic: RC2 `57.7/70`; actual journal extension `62.2/70`.
The one-tenth gap from the predeclared `62.3/70` target reflects the valid but
important negative result that no Security-V2 bounded-catalog profile has
enough levels for the frozen LeNet graph. These are reviewer-quality scores,
not acceptance or award probabilities.

Readiness interpretation:

- JKIISC journal readiness: the extension materially strengthens formal
  clarity and standard-model breadth; concise presentation remains necessary.
- CISC excellent-paper range: the artifact is competitively scoped when led by
  the proposition and standard benchmarks; no award prediction is made.
- CISC top-award range: not asserted; presentation, reviewer mix, novelty
  perception, and competing submissions are unknown.
- International workshop: artifact rigor is strong; model breadth and direct
  comparison to compiler/autotuner baselines remain the main constraints.

## Falsification test

The score is falsified if any frozen policy constant changed, audit informed
selection, the disclosed adapter is relabeled as full/packed LeNet, the
14-candidate formal denominator is presented as 14 encrypted executions, or
the exact model/input evidence cannot be rebuilt. The LeNet 0/7 executable
catalog result must remain visible; deleting it would invalidate the score.
