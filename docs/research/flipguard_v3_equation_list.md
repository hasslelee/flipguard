# FlipGuard V3 Equation List

Status: publication-input specification only.

1. Plaintext decision:
   `d_plain(x) = 1[f_plain(x) >= tau]`.
2. CKKS decision:
   `d_c(x) = 1[f_c(x) >= tau]`.
3. Decision margin:
   `m(x) = |f_plain(x) - tau|`.
4. Absolute CKKS error:
   `e_c(x) = |f_c(x) - f_plain(x)|`.
5. Sufficient decision-preservation condition:
   `e_c(x) < m(x) => d_c(x) = d_plain(x)`.
6. Operational reserve policy:
   `e_c(x) < rho*m(x)`.
7. Primary policy:
   `rho=0.5`; margin utilization cap `rho`; reserved fraction `1-rho`.
8. Certifiable and ambiguous sets:
   `V_cert={x:m(x)>delta}`, `V_amb={x:m(x)<=delta}`.
9. Margin utilization:
   `u(x)=e_c(x)/m(x)` for `m(x)>0`.
10. Formal trial reduction:
    `1-direct_trials/security_admitted_catalog_candidates`.
11. Clustered latency ratio:
    geometric mean of dataset-model-cluster ratios; repeated partitions stay
    within clusters.

The equation list must not introduce an instantiated analytical CKKS bound.
`rho=0.5` must not be described as derived or optimal.
