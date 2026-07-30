# Step 7g9: EVA External Compiler Adapter Protocol

Status: `PREDECLARED_BEFORE_COMPILER_REPLAY_OR_ENCRYPTED_EXECUTION`

## Question

Can the parameter output of a real public CKKS compiler be treated as an
untrusted FlipGuard candidate, rebound to the frozen Lattigo runtime, and
certified or rejected without synthesis, repair, or post-hoc tuning?

## Pinned upstream

- Microsoft EVA `v1.0.1`, commit
  `4cd3254c9c51340ae30c451495ce5378135758c0`.
- Microsoft SEAL `v3.6.4`, commit
  `0b058d99b7f18a00e5ebb2b80caee593804b0500`.

The adapter runs the actual EVA compiler in isolated CI. It does not port the
selector formula into FlipGuard. The compiler output is then materialized by
the pinned `seal::CoeffModulus::Create` implementation.

## Fixed compiler input

- Development workload: seed 0, Iris binary, `linear_poly3`.
- EVA vector size: 1.
- Program: the exact scaled linear logit followed by
  `0.5 + 0.197*z - 0.004*z^3`.
- Input scale: 20 bits, fixed from the frozen Direct Policy V2 minimum.
- Output range: 1 bit, derived before execution from the frozen validation
  calibration.
- EVA defaults: balanced reductions, lazy-waterline rescaling, lazy
  relinearization, 128-bit classical security, non-quantum mode.

## Exact translation

EVA appends one key prime to its ordered coefficient-modulus bit sizes.
SEAL constructs a key context from every prime and a first ciphertext context
after removing the final prime. The adapter therefore maps:

- exact `first_context_data` moduli to Lattigo `Q`;
- the exact final key-context modulus to one Lattigo `P`;
- the EVA input scale to `LogDefaultScale`;
- the standard ring and rescale-aware FlipGuard path.

No prime may be padded, dropped, regenerated, or reordered. No scale or EVA
compiler option may be adjusted after the output is observed.

This is intentionally not a claim that the SEAL and Lattigo runtimes have
identical secret or error distributions. EVA's output is only a modulus
proposal. FlipGuard independently applies the frozen Security V2 policy to the
actual concrete `Q` and `QP`, and executes any admitted candidate using the
already frozen Lattigo Xs/Xe distributions.

## Fail-closed gates

Encrypted evaluation is allowed only if:

1. every pinned source digest matches;
2. actual EVA and SEAL commits match the contract;
3. the exact SEAL key/ciphertext modulus split is reproducible;
4. concrete `Q` and `QP` pass Security V2;
5. the chain provides at least the seven Q primes required by the frozen
   FlipGuard lowering; and
6. the slot requirement is met.

Security or graph incompatibility is a valid static result and blocks
encrypted execution. If eligible, exactly one provider trial with three fresh
keys is allowed. SAFE advances to a byte-identical locked audit; REJECTED or
FAILED becomes NO_SAFE. Nothing triggers repair or retuning.

## Claim boundary

An eligible result supports only a source-replayed public compiler parameter
proposal passing through FlipGuard's common decision-integrity gate. It does
not establish native EVA/SEAL execution equivalence, cross-backend performance
equivalence, universal compiler compatibility, or a general external
autotuner integration claim.
