# Quick Start

This path verifies frozen evidence; it creates no scientific result.

```bash
git checkout 98e5e4105c0b0597d6fb245b5718a00eb4828349
python3 scripts/fetch_external_source_inputs.py --output results/source_datasets/fetch_manifest.json
go test ./...
go vet ./...
scripts/verify_frozen_evidence.sh
scripts/reproduce_quick_demo.sh
```

The fetch step restores byte-pinned MNIST and BSDS500 source archives required by four graph-contract tests; it is not an encrypted experiment. Expected: tests pass, predecessor digests verify, and the demo prints scoped SAFE, REJECTED, and NO_SAFE examples. The demo must not write below any frozen results/evidence directory.
