"""src/qkd/privacy.py — tarea 1.6 (Marco). Toeplitz + longitud segura."""

from __future__ import annotations

import numpy as np  # noqa: F401 - se usara al implementar (tarea 1.6)

from .types import Bits


def binary_entropy(q: float) -> float:
    """h(q) = -q log2 q - (1-q) log2 (1-q)."""
    raise NotImplementedError


def secure_key_length(n: int, qber: float, leak_ec: int, epsilon: float = 1e-9) -> int:
    """Longitud de clave segura (Devetak-Winter + leftover hash lemma)."""
    raise NotImplementedError


def privacy_amplify(key: Bits, ell: int, seed: Bits) -> Bits:
    """Comprime `key` a `ell` bits con una matriz de Toeplitz."""
    raise NotImplementedError
