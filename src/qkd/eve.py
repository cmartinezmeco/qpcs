"""src/qkd/eve.py — tarea 1.4 (Gonzalo). Espia intercept-resend."""

from __future__ import annotations

import numpy as np

from .types import Bases, Bits


def intercept_resend(
    alice_bits: Bits, alice_bases: Bases, rate: float, rng: np.random.Generator
) -> tuple[Bits, Bases, Bits]:
    """Ataque intercept-resend sobre una fraccion `rate` de los fotones."""
    raise NotImplementedError
