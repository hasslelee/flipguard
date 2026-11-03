# Reproduction and read-only verification

All commands use `/home/ckks2/deciprotect` or its independent
`research/fashion_extension` module. Never execute in the predecessor workspace.
The original PDF and completed runs are inputs, not output targets. The Python
scripts use exclusive creation or checkpoint reuse, not replacement of completed
evidence. A new scientific execution requires a new run/protocol ID and output
location. Do not rerun the completed experiment merely to reproduce its report.

## Verify existing results without encryption

From the DeciProtect repository with the locked Python environment:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/analyze_fg_expand_v1.py --check
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/analyze_external_fg_expand_v2.py --check
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/analyze_fg_expand_v2.py --check
```

The second-expansion checker independently rebuilds plaintext logits from the
fixed model weights and input pixels, verifies identifiers and labels, recomputes
all-competitor margin/error conditions, decisions, unique-input and key-event
counts, role aliases, and descriptive time ratios. Hashes bind raw bytes; tiny
floating-point tolerance applies only to independently recomputed derived
quantities, not to raw hashes, event counts, or selection conditions.

`MAIN_SOURCE_LOCK.json` followed by `MAIN_SOURCE_AMENDMENT_01.json` and `02.json`
is the executable-source chain. The initial and intermediate Python runner
snapshots are saved. The last amendment corrects a JSON reader field, not an
encryption or acceptance rule. CI deliberately does not rebuild or execute CKKS
experiments; absent ignored local binaries are explicitly reported as not
reverified there. The local final verification checks their original hashes.

With the four original local IDX gzip files present, also run:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/verify_fg_expand_v2_inputs.py --check
```

This checks original MD5/SHA-256, exact pixel and label bytes, deterministic
train roles, every test index, and all class-balanced batch assignments. Those
raw source gzip files are ignored by Git. `DATA_SOURCE.json` records their
official URLs and checksums; no archive or predecessor environment is needed.

## Actual preparation and execution path

Preparation protocol: `protocols/FG_EXPAND_V2_PREP.json`.
Main protocol: `protocols/FG_EXPAND_V2_MAIN.json`.
External protocol: `protocols/FG_EXPAND_V2_EVA_NATIVE.json`.
All use `results/fg_expand_v2_20260905_run01` for this completed bounded run.

The actual entry points were:

```bash
.venv/bin/python scripts/prepare_fg_expand_v2.py
go -C research/fashion_extension build -o bin/fashion-train ./cmd/fashion-train
go -C research/fashion_extension build -o bin/fashion-case ./cmd/fashion-case
go -C research/fashion_extension build -o bin/external-one ./cmd/external-one
```

`fashion-train` was called serially with `--raw data/raw/fashion_mnist`,
`--run results/fg_expand_v2_20260905_run01`, `--seed 0`, then `1`, then `2`, and
the parent checkpoint as `--source-commit`. `SOURCE_ID_CORRECTION.json` records
the literal typo in the seed 1 descriptive source field. The model was not
rewritten or retrained; trainer/optimizer hashes identify the actual execution.
The native commands used `/usr/bin/time -v`, `GOMAXPROCS=4`, and the declared
memory budget. Epoch and resource logs are preserved for all seeds.

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_fg_expand_v2.py --quality
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_fg_expand_v2.py
```

This is documentation of executed commands, not an instruction to start another
run. `commands/*.attemptNN.json` contains the exact absolute arguments, working
directory, binary SHA, timestamps, environment snapshots, exit code, and wall
time for each main native call. Matching `.log` files retain key checkpoints and
`time -v` output. The fixed runner orders all three seeds' selection before the
first test evaluation. `AUDIT_JOB_PLAN.json` records role hashes and the full
evaluation order before the first audit command.

The 6-hour main budget sums native command wall times including failed attempts;
it excludes literature work, data download, training, and external comparison.
The budget is checked before each native job. The initial invocation timestamp
and final invocation elapsed time are not substitutes for this summed budget.
The single-job timeout is 1,800 seconds; memory and disk bounds are in the
protocol. Incomplete work remains explicitly incomplete.

## Official EVA native execution

The provider was Microsoft EVA commit
`4cd3254c9c51340ae30c451495ce5378135758c0`, using the already built official
module copied to `work/fg_expand_v2_20260905/eva_python`. This module and Docker
image are local, ignored assets; they are not a new implementation of EVA.
`EXTERNAL_SOURCE_BINDINGS.json` records all copied runtime/source hashes, the
image SHA, and the only host mount (`/home/ckks2/deciprotect:/work`). The original
workspace was not mounted. Connection succeeded on the first attempt.

The driver is `scripts/run_eva_fg_expand_v2.py`. It imports the byte-identical
V8 helper from `work/fg_expand_v2_20260905/run_eva_shared_polynomial_v8.py`.
For a fresh checkout, the exact helper source is also published at
`research/fashion_extension/external/run_eva_shared_polynomial_v8.py` and bound
by `EXTERNAL_REPRODUCTION_BINDING.json`. Copy that file into the documented
ignored work location if preparing a new separately identified run. Rebuild
the official provider from its pinned source using its own build instructions
when the recorded local module/image is unavailable; a new build is not
asserted to be byte-identical to the saved binary.

The native container was run with network disabled, four CPUs, the DeciProtect
mount, `PYTHONPATH=/work/work/fg_expand_v2_20260905/eva_python`, and
`python3 /work/scripts/run_eva_fg_expand_v2.py`. It called the official
`CKKSCompiler.compile` at inherited scale 30/range 20, generated three fresh
native contexts for each 500-input phase, and saved the compiled graph and all
input scores. It did not impose the proposal's decision condition on EVA's
configuration selection. `external-one` independently ran the original direct
selector and fixed-configuration audit on the same stored polynomial/inputs.

The common polynomial inputs are previously exposed V8 synthetic data. Native
EVA/SEAL and Lattigo have different packing, scheduling and security assessment;
the results do not identify a causal speed effect of acceptance conditions.
The source-binding image hash, driver, native output metadata and logs establish
this executed path; rebuilding from scratch is separate work.

## Reporting and preservation

`scripts/analyze_fg_expand_v2.py` without `--check` creates new derived JSON/CSV
once, and `scripts/report_fg_expand_v2.py` creates the report, cost tables and
training figures once. Existing outputs are refused. The immutable raw and
derived manifests cover the new run and report package only. No full archive
hash pass was repeated. `scripts/build_handoff.py` updates only the mutable
current sync package, retaining the prior handoff under this report's history.

The final PDF, original refs and pre-existing original `AGENTS.md` modification,
baseline, completed protocols, and the first expansion are verified separately
in `PRESERVATION.json`. New code, source identities, tests and limitations are in
`VALIDATION.json` and `CHANGED_FILES.txt`. Neither test success nor hash agreement
is a performance improvement or future-input risk guarantee.
