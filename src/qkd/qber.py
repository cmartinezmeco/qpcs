"""src/qkd/qber.py — tarea 1.4 (Gonzalo). Estimacion de QBER sobre muestra."""

from __future__ import annotations

import numpy as np

from .types import QberEstimate, SiftedKeys


def estimate_qber(
    keys: SiftedKeys, sample_fraction: float, rng: np.random.Generator
) -> QberEstimate:
    """Estima el QBER sacrificando una muestra aleatoria de la clave cribada."""
    raise NotImplementedError
