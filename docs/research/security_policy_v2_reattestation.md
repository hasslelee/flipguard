# Security Policy V2 Re-attestation

Policy ID:
`security_guidelines_cic2025_table5_2_ternary_128_v2`.

The policy uses Table 5.2 of *Security Guidelines for Implementing
Homomorphic Encryption*, IACR Communications in Cryptology 1(4), published
2025-01-13, DOI `10.62056/anxra69p1`. The Category-128 uniform-ternary caps
are 106, 214, 430, and 868 bits for LogN 12, 13, 14, and 15.

## Runtime Semantics

- Module: `github.com/tuneinsight/lattigo/v6`, version `v6.2.0`.
- Xs: `ring.Ternary{P: 2/3}`.
- Xe: `ring.DiscreteGaussian{Sigma: 3.2, Bound: 19.2}`.
- Table model: Gaussian error sigma 3.19.
- Interpretation: conservative admission reference, not an
  identical-distribution security proof.
- Ciphertext admission checks Q.
- Evaluation, relinearization, and key-switching admission checks QP.
- Final admission passes only when every required object passes.

QP is decisive when P is nonempty because Q is a strict subset of QP, but
both checks and both headrooms remain machine-readable.

## Static Replay

`scripts/build_security_v2_static_artifacts.py` performs no encryption. It
materializes exact Lattigo Q/P primes and re-attests:

- 50 direct-selected rows;
- deduplicated direct literal signatures;
- 11 catalog profiles;
- 22 profile/path identities per workload;
- the legacy reference candidate;
- paired-latency arms.

It writes `security_reattestation_v2.csv`,
`security_reattestation_v2.json`, and
`lattice_estimator_inputs_v2.json`. Exact estimator inputs are exported; an
exact estimator run is currently `NOT_RUN`.

The completed static replay admits all 50 direct selected rows with minimum
QP headroom 13 bits and no identity change. It admits seven catalog profiles
and excludes `default`, `scale38`, `scale40`, and `scale42`, each five bits
over the V2 LogN14 cap.

## Security-Compliant Bounded Oracle

The original 1,100 encrypted executions remain immutable and classified
`PRE_SECURITY_V2`. Filtering removes inadmissible profile identities and
re-summarizes the same records over 14 admitted identities per
workload-partition instance. No encrypted candidate is rerun.

The filter changes 125 of 250 workload-alpha selections, including 25 of 50
at primary alpha 0.5. All changes are linear workloads whose prior
`default__rescale_aware` selection becomes
`deep_chain_8_scale45__rescale_aware`.

The legacy reference `default__rescale_aware` is inadmissible. The V2
reference is pre-frozen as `deep_chain_8_scale45__rescale_aware`: the smaller
of the admitted deep-chain rescale profiles that is SAFE in all 50 existing
primary-alpha records. This choice does not authorize a latency claim.

## Falsification

- A V2-inadmissible direct row is excluded from final evidence and must be
  resynthesized under V2.
- An inadmissible catalog arm is excluded from the bounded oracle.
- An inadmissible paired arm cannot be reused in final paired latency.
- Missing source commit, policy digest, or input digest makes an evidence pack
  ineligible for final use.
