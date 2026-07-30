# Step 7F.4 Decision-Contract Activation Control Results

Status: finite-domain static and encrypted control `SUPPORTED`; natural-data
candidate-synthesis effect remains `BLOCKED`. `paper_claim_allowed=false`.

## Static Activation

Both regimes use the same `linear_poly3` model, graph, input extrema,
maximum output magnitude, and graph-derived aggregate sensitivity
`120.803`.

| Regime | Protected margin | Decision budget | Graph-fixed initial | Full initial |
|---|---:|---:|---:|---:|
| Narrow | 0.0012016991 | 0.0006008495 | S20 | S21 |
| Wide | 0.0118191360 | 0.0059095680 | S20 | S20 |

All static literals pass Security Policy V2. The narrow decision contract
crosses the frozen precision threshold by one bit. The wide contract remains
at the backend-feasibility floor.

## Encrypted Validation

Each arm uses 32 configuration-validation samples and three fresh keys per
trial. Frozen `+4`-bit numerical repair and the four-trial maximum are
unchanged.

| Regime / arm | Initial | Selected | Trials | Repairs | Final validation |
|---|---:|---:|---:|---:|---|
| Narrow / decision contract | S21 | S33 | 4 | 3 | SAFE |
| Narrow / graph fixed | S20 | S32 | 4 | 3 | SAFE |
| Wide / decision contract | S20 | S28 | 3 | 2 | SAFE |
| Wide / graph fixed | S20 | S28 | 3 | 2 | SAFE |

The narrow one-bit difference persists through the identical monotone repair
sequence. The wide arms remain identical. Across the four arms:

- selection trials: 14;
- numerical repairs: 10;
- selection fresh-key runs: 42;
- selection encrypted sample evaluations: 1,344;
- final validation flips and violations: 0 and 0 for every selected arm.

Rejected intermediate trials, including their flips and violations, remain
in the raw ledgers. Aggregate counts over those rejected candidates are not
reported as selected-candidate failures.

## Locked Audit

Each selected literal is replayed on 32 disjoint audit rows with three fresh
keys:

- locked-audit PASS: 4/4;
- flips: 0;
- violations: 0;
- retuning: 0;
- audit key runs: 12;
- audit encrypted sample evaluations: 384.

## Recovery Record

Two earlier attempts failed before encryption:

1. non-numeric row IDs were accepted by the contract parser but rejected by
   the backend integer identity parser;
2. numeric IDs then exposed missing canonical `label` and `scaled_logit`
   columns.

Both attempts completed zero key runs. Their artifacts are preserved as
`SUPERSEDED_IMPLEMENTATION_RECOVERY`. Before the successful attempt, a Go
smoke test was added that executes one actual CKKS key run over generated
control data and rejects any backend `FAILED` status.

## Claim Boundary

Supported:

> In the predeclared high-sensitivity finite domain, changing only the
> minimum certifiable decision margin changes the directly synthesized CKKS
> literal, and the resulting selected literals replay SAFE without retuning.

Still blocked:

> Decision margins change synthesized configurations on the ten natural
> seed-0 workloads.

This control is explanatory and synthetic. It does not justify a universal
autotuning, natural-data, global-optimum, or analytical certification claim.
