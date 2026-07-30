# Step 7G.3: AWS HIT External Parameter Selector Replay

## Objective

Test one CKKS candidate derived from the public automatic parameter-selection
formula in AWS Homomorphic Implementor's Toolkit (HIT) through FlipGuard's
provider-neutral decision-integrity gate.

This is not a claim that HIT is a search-based autotuner. HIT derives
parameters from circuit depth, an estimated scale, slot count, and key-switch
prime count.

## Pinned Source

The protocol pins:

- AWS HIT `lattigo-backend` commit
  `902e87e0b96a2d270f4cc010ab1742aa062aa198`;
- AWS Lattigo C++ wrapper tag `v0.0.1`, commit
  `826c9d1f33594b790c40d578a5ec3b2268fe762c`;
- Lattigo v2.2.0 tag commit
  `c629f0c9518f6117141f54e441d6ca5d765f8868`;
- official Lattigo v6.2.0 tag commit
  `c1fd095f08602e2d4ef571db015fc553fdd2d845`.

Every source file used to establish the formula, prime generation, and
distribution semantics is bound by SHA-256 in
`experiments/hit_external_adapter_v1/contract.json`.

## Candidate

The predeclared HIT input is:

- `num_slots=8192`;
- `max_ct_level=6`;
- `log_scale=20`;
- `num_ks_primes=1`.

The pinned HIT formula must produce:

- `LogN=14`;
- `LogQ=[60,20,20,20,20,20,20]`;
- `LogP=[61]`;
- `LogDefaultScale=20`.

The larger slot request is part of the external candidate and is not reduced
by FlipGuard. This intentionally preserves the external tool's literal even
when it is not latency-optimal for the development workload.

## Exact Translation Gate

Before CKKS validation, the isolated materializer instantiates the declared
log-moduli in Lattigo v2.2.0, then imports those ordered concrete primes into
Lattigo v6.2.0. It also records native v6 log-modulus materialization as a
diagnostic; native regeneration is not allowed to replace or reorder the
external literal. Execution is permitted only if all of the following are
identical:

1. ordered concrete Q primes;
2. ordered concrete P primes;
3. scale;
4. standard-ring semantics;
5. uniform ternary secret distribution `[1/3,1/3,1/3]`;
6. discrete Gaussian error with `sigma=3.2`, bound `19.2`.

Security Policy V2 then independently checks ciphertext Q and evaluation-key
QP. The HIT-declared bit-size sum is 241, while conservative admission from
the concrete modulus product uses `ceil(log2(QP))=242`. The `LogN=14` cap is
430, leaving 188 bits of concrete-product headroom.

Any translation mismatch or Security V2 failure blocks encrypted execution.

## Development Evaluation

The single source-replayed candidate is evaluated on seed 0,
`iris_binary/linear_poly3`:

- 14 configuration-validation rows;
- three fresh-key validation repeats;
- one candidate trial;
- no synthesis;
- no repair;
- locked replay on 16 disjoint audit rows only if validation is SAFE;
- three fresh-key audit repeats;
- retuning prohibited.

SAFE, REJECTED, FAILED, or NO_SAFE are all publishable scientific outcomes.
No outcome changes Direct Policy V2 or Security Policy V2.

## Claim Boundary

This experiment can support a limited claim that FlipGuard accepts a candidate
source-replayed from one public external automatic parameter selector and
applies the same certify-or-reject gate. It cannot support:

- native execution of the complete HIT C++ binary;
- a general third-party autotuner integration claim;
- HIT quality or optimality;
- a broad cross-version equivalence claim;
- a latency advantage.

The candidate lineage must always be described as
`SOURCE_REPLAYED_PUBLIC_PARAMETER_SELECTOR`, not as native HIT output.
