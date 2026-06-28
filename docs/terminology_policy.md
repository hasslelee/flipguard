# FlipGuard terminology policy

## Core terms

Use the following terms in papers, seminar slides, and research explanations.

- execution configuration
- execution configuration candidate
- parameter candidate
- rescale
- non-rescale
- selected safe execution configuration
- fastest rejected execution configuration

## Internal compatibility terms

The following internal terms may still appear in code, directory names, or old result files for compatibility.

- profile
- rescale_aware
- baseline_non_rescale
- naive

These names should not be used as main presentation terms.

## Candidate naming rule

Use explicit names in papers and seminar slides.

Examples:

- default -> chain7_scale45_N14_default
- scale42 -> chain7_scale42_N14
- scale40 -> chain7_scale40_N14
- scale38 -> chain7_scale38_N14
- deep_chain_8_scale45 -> chain8_scale45_N15
- deep_chain_9_scale45 -> chain9_scale45_N15
- short_chain_6_scale42 -> chain6_scale42_N14
- short_chain_6_scale40 -> chain6_scale40_N14
- short_chain_6_scale38 -> chain6_scale38_N14
- short_chain_5 -> chain5_scale40_N14
- short_chain_3 -> chain3_scale35_N14

## Baseline configuration

The default candidate is not a universal CKKS standard parameter set.

In this project, default means the baseline execution configuration used for comparison.

- chain length: 7
- scale: 45 bits
- log N: 14
- slots: 8192
- P primes: 1

It is used as a stable baseline for comparing reduced-chain, reduced-scale, and deep-chain candidates.
