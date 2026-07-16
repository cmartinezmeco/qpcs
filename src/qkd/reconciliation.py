"""src/qkd/reconciliation.py — tarea 1.5 (Marco). Cascade + contador de fugas."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from .types import Bits, ReconciliationResult


class ParityOracle:
    """Canal publico de Alice hacia Bob. La UNICA forma de mirar su clave."""

    def __init__(self, alice_key: Bits) -> None:
        raise NotImplementedError

    def parity(self, idx: npt.NDArray[np.int64]) -> int:
        """Paridad de alice[idx]. Cuesta exactamente 1 bit de fuga."""
        raise NotImplementedError


def cascade(
    alice: Bits, bob: Bits, qber: float, rng: np.random.Generator, n_passes: int = 4
) -> ReconciliationResult:
    """Reconciliacion Cascade (Brassard & Salvail, 1993)."""
    raise NotImplementedError
