# Quick Start

This path verifies frozen evidence; it creates no scientific result.

```bash
git checkout 98e5e4105c0b0597d6fb245b5718a00eb4828349
go test ./...
go vet ./...
scripts/verify_frozen_evidence.sh
scripts/reproduce_quick_demo.sh
```

Expected: tests pass, predecessor digests verify, and the demo prints scoped SAFE, REJECTED, and NO_SAFE examples. It must not write below any frozen results/evidence directory.
