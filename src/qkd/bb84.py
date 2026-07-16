"""src/qkd/bb84.py — tarea 1.3 (Gonzalo). Nucleo BB84 sin Eve."""

from __future__ import annotations

from typing import Literal

import numpy as np

from .types import Bases, Bits, SiftedKeys


def run_bb84(
    n_photons: int,
    rng: np.random.Generator,
    eve_rate: float = 0.0,
    noise: float = 0.0,
    backend: Literal["qiskit", "numpy"] = "numpy",
) -> SiftedKeys:
    """Ejecuta BB84 y devuelve las claves cribadas. Ver docs/theory/qkd.md."""
    raise NotImplementedError


def sift(
    alice_bits: Bits, alice_bases: Bases, bob_bits: Bits, bob_bases: Bases
) -> SiftedKeys:
    """Descarta las posiciones con bases distintas. Sobrevive ~N/2."""
    raise NotImplementedError
