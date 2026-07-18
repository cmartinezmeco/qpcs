"""src/qkd/protocol.py — orquestador: ata la cadena entera de punta a punta."""

from __future__ import annotations

from typing import Literal

import numpy as np

from .bb84 import run_bb84
from .qber import estimate_qber
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
    Usa siempre el backend numpy: es el unico donde Eve (intercept-resend)
    esta modelada, y el unico viable en tiempo para los barridos de 40 000
    fotones que hacen estos tests (ver run_bb84 en bb84.py).
    """
    sifted = run_bb84(
        n_photons=n_photons,
        rng=rng,
        eve_rate=eve_rate,
        noise=noise,
        backend="numpy",
    )
    return estimate_qber(sifted, sample_fraction, rng)
