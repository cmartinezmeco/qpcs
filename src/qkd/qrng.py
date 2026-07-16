"""src/qkd/qrng.py — tarea 1.2 (Gonzalo). Generacion cuantica de bits."""

from __future__ import annotations

import numpy as np  # noqa: F401 - se usara al implementar random_bits (tarea 1.2)

from .types import Bits


class QRNG:
    """Generador de bits aleatorios por medida de |+> en la base Z."""

    def __init__(self, qubits_per_circuit: int = 16, seed: int | None = None) -> None:
        raise NotImplementedError

    def random_bits(self, n: int) -> Bits:
        """Devuelve n bits. Ver docs/theory/qkd.md."""
        raise NotImplementedError

    def random_bases(self, n: int) -> Bits:
        """Bases: 0 = Z, 1 = X."""
        raise NotImplementedError
