#!/usr/bin/env python3
"""Validate missing-value vocabulary before provider normalization."""

from __future__ import annotations

MISSING = {
    "NOT_REPORTED", "NOT_EVALUATED", "NOT_APPLICABLE", "OUTPUT_UNAVAILABLE",
    "BUILD_BLOCKED", "HARDWARE_BLOCKED", "CREDENTIAL_BLOCKED",
}


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
