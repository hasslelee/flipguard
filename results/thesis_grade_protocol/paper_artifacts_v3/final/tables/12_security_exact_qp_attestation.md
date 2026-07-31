# Security and exact-Q/P attestation

The estimator matches declared objects but not Lattigo's explicit Xe truncation exactly.

| Check | PASS/admitted | FAIL/excluded | Caveat |
| --- | --- | --- | --- |
| direct selected static re-attestation | 50 | 0 | minimum headroom 13 bits |
| catalog profiles | 7 | 4 | Q and QP checked separately |
| estimator model objects | 17 | 1 | 2 models; excluded object remains sub-128 |
