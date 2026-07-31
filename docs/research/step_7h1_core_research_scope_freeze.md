# Step 7H1: Core Research Scope Freeze

Status: FROZEN for the core-closure window that began on 2026-07-31.

## Reviewer concern

FlipGuard accumulated core decision-integrity evidence together with external
provider and cross-runtime investigations. Treating every unfinished auxiliary
direction as a paper blocker would obscure the evaluated contribution, while
promoting those investigations into broad interoperability claims would exceed
the evidence. The paper therefore needs an explicit, falsifiable boundary
between its core result, appendix-only evidence, and future work.

The frozen core contribution is:

> FlipGuard directly synthesizes a CKKS configuration from a supported
> computation graph and a threshold decision-integrity contract, validates
> the candidate with a bounded number of encrypted trials, applies bounded
> failure-aware repairs, abstains when no SAFE candidate can be established,
> and replays the selected literal without retuning on a disjoint locked
> audit.

## Literature precedent

CHET, EVA, HECATE, ELASM, HECO, DaCapo, HEIR, Orbit, Rotom, and Libra establish
substantial prior art in encrypted-program compilation, CKKS scale and level
management, parameter selection, packing, bootstrapping placement, and
hardware scheduling. AutoPrivacy and AutoFHE establish model/HE co-design.
FHE-Agent establishes encrypted calibration and failure-guided CKKS repair
over broader neural-network graphs. Application-Aware Approximate Homomorphic
Encryption establishes the importance of binding an approximate-HE circuit,
input domain, parameter generation, and validation.

FlipGuard does not replace these systems or claim priority over their
optimization mechanisms. Its paper boundary is the downstream
decision-integrity admission, explicit abstention, literal replay, and
no-retuning audit contract for the declared finite workloads. Exact citations
and comparison details remain in
`docs/research/flipguard_v2_related_work.md`.

## Implementation requirement

The following evidence is core paper evidence:

- direct synthesis;
- bounded adaptive repair;
- finite-scope decision-integrity admission;
- `NO_SAFE` abstention;
- no-retuning locked audit;
- Security-V2-compliant bounded-catalog comparison;
- paired latency on frozen arms;
- the deeper polynomial structural holdout, including its negative result;
- scoped Sobel, Harris, and CNN-lite holdouts;
- the independent training/data-seed extension;
- security attestation; and
- artifact reproducibility.

The following evidence is auxiliary and appendix-only:

- synthetic provider-format interoperability;
- fail-closed Orion import;
- AWS HIT rejection;
- EVA native scale sensitivity;
- EVA scale-30 native locked audit; and
- exact EVA Q/P materialization.

The following items are non-blocking future work:

- an EVA scale-30 Lattigo adapter;
- a matched Lattigo-SEAL numerical study;
- runtime-specific equivalent-security analysis;
- general external-autotuner behavior;
- arbitrary packed CNN or full LeNet support; and
- an instantiated CKKS analytical certificate.

Independent external-autotuner candidates, cross-runtime adapters, matched
cross-runtime numerical studies, and EVA runtime-specific security
equivalence are not core paper-admission blockers. Their claim states remain
`NOT_EVALUATED` or `PARTIALLY_SUPPORTED` as appropriate.

The following novelty claims are prohibited:

- first CKKS autotuner;
- first direct CKKS configuration synthesizer;
- first application-aware CKKS configuration;
- first repair-based selector;
- universal graph support;
- global optimality; and
- general external-autotuner support.

No new encrypted experiment, EVA cross-runtime implementation, policy
retuning, or thesis prose is authorized by this scope freeze. The paper may
use only claims admitted by the canonical paper-claim registry created after
this document.

## Falsification test

The core boundary fails closed if any paper-facing claim:

1. depends on an auxiliary or future-work item that lacks its own admitted
   finite-scope evidence;
2. omits a scientific negative result from a required core pack;
3. describes observed finite-set admission as distribution-wide correctness;
4. describes the bounded Security-V2 catalog as a global optimum;
5. describes scoped scalar-replicated adapters as universal graph or packed
   CNN support;
6. treats an external runtime literal as having equivalent Lattigo security or
   numerical behavior without a matched study; or
7. cannot be traced to a frozen input digest, policy digest, source commit, and
   deterministic verifier.

Any such claim remains blocked even when the rest of the core paper is
admissible.
