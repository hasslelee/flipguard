#!/usr/bin/env python3
"""Precision-safe numeric serialization for lattice-estimator outputs."""

from __future__ import annotations

import math
from typing import Any


def format_53bit_real(value: Any) -> str:
    """Serialize an existing binary64-compatible value without promotion."""
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("estimator cost must be finite")
    return format(numeric, ".15g")
