from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts/verify_independent_machine_replay.py"
SPEC = importlib.util.spec_from_file_location(
    "verify_independent_machine_replay",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class IndependentMachineReplayVerifierTest(unittest.TestCase):
    def test_checksum_verifier_rejects_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = root / "payload.txt"
            payload.write_text("original\n", encoding="ascii")
            digest = MODULE.sha256_path(payload)
            (root / "SHA256SUMS").write_text(
                f"{digest}  payload.txt\n",
                encoding="ascii",
            )
            MODULE.verify_checksums(root)
            payload.write_text("changed\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                MODULE.verify_checksums(root)

    def test_load_json_rejects_non_object(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "value.json"
            path.write_text(json.dumps([]), encoding="ascii")
            with self.assertRaisesRegex(ValueError, "expected JSON object"):
                MODULE.load_json(path)


if __name__ == "__main__":
    unittest.main()
