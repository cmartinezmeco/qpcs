"""src/qkd/protocol.py — orquestador: ata la cadena entera de punta a punta."""

from __future__ import annotations

from typing import Literal

import numpy as np

from .types import ProtocolResult, QberEstimate


def run_protocol(
    n_photons: int,
    rng: np.random.Generator,
    eve_rate: float = 0.0,
    noise: float = 0.0,
    sample_fraction: float = 0.2,
    backend: Literal["qiskit", "numpy"] = "numpy",
) -> ProtocolResult:
    """Recorre la cadena completa: QRNG -> BB84 -> QBER -> Cascade -> privacidad."""
    raise NotImplementedError


def run_until_qber(
    n_photons: int,
    rng: np.random.Generator,
    eve_rate: float = 0.0,
    noise: float = 0.0,
    sample_fraction: float = 0.2,
) -> QberEstimate:
    """Version corta de la cadena, solo hasta la estimacion del QBER.

    La usan los tests de la tarea 1.4, que no necesitan llegar hasta Cascade.
    """
    raise NotImplementedError
