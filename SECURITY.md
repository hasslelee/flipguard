# Security Policy

FlipGuard is research software for CKKS configuration synthesis and decision-integrity evaluation. Security reports are welcome, but documented research limitations are not automatically implementation vulnerabilities.

## Supported Versions

The public project currently tracks the latest pushed research branch and the frozen `flipguard-thesis-v1.0.0-rc2` core artifact. Historical checkpoints and preliminary evidence are preserved for provenance and are not independently maintained as supported software releases.

## Private Reporting

Do not disclose a suspected vulnerability, credential, secret key, private dataset content, or exploit in a public issue.

Use GitHub's **Private vulnerability reporting** control on the repository Security tab when it is available. Repository maintainers can also create a private draft Security Advisory and invite the reporter. If neither private channel is visible, contact the maintainer through a verified private contact method on the GitHub profile before sharing technical details.

Include:

- affected commit, tag, command, and component;
- threat model and expected security property;
- minimal reproduction without real secrets or private data;
- impact on confidentiality, integrity, availability, or evidence provenance;
- whether the issue concerns runtime code, policy admission, estimator mapping, or artifact verification.

Please allow maintainers time to reproduce, classify, and coordinate a fix before public disclosure.

## Vulnerability or Research Limitation?

Examples of implementation vulnerabilities include secret-key exposure, unsafe serialization, command injection, bypass of fail-closed identity checks, or admission of a policy-inadmissible candidate as formal evidence.

Documented limitations include finite empirical validation, absence of distribution-wide guarantees, estimator-model caveats, unsupported graphs, one-host performance measurements, and `NO_SAFE` within a bounded search. A report may still reveal that an implementation violates its documented scope; provide evidence of that mismatch.

## Cryptographic Claims

Do not infer security solely from a successful encrypted run. FlipGuard reports Security Policy V2 admission and lattice-estimator model sensitivity separately. See [`docs/CLAIM_SCOPE.md`](docs/CLAIM_SCOPE.md) and the versioned security evidence before deploying or extending the system.
