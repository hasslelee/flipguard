# Full Reproduction Boundaries

This readiness audit does not rerun the 700-candidate catalog, EVA 1,000-input evaluation, HEIR paired protocol, CoreLab 72-plan grid, or any other long encrypted experiment. Full scientific reproduction remains documented by the predecessor manifests and release archive. Reviewers should first verify SHA-256 dependencies and deterministic derived artifacts, then schedule encrypted reproduction only under the original frozen protocol and hardware constraints.

The authoritative source checkpoint is `98e5e4105c0b0597d6fb245b5718a00eb4828349`. Before the full Go test gate, run `python3 scripts/fetch_external_source_inputs.py --output results/source_datasets/fetch_manifest.json`; it fetches and validates MNIST (`fe4410...ab78`) and BSDS500 (`97e49d...af8e`) under their upstream licenses. Never use audit data for selection or policy repair.
