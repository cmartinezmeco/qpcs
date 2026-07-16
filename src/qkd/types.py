"""src/qkd/types.py - contratos del modulo QKD.

Este fichero es la frontera entre Gonzalo, Marco y yo. Nadie lo cambia sin
avisar al equipo: si alguien devuelve algo distinto de lo que hay aqui, el
codigo de los demas deja de compilar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
import numpy.typing as npt

# Un array 1-D de bits (0/1) en uint8. NO listas de Python: manejamos 10^5 fotones.
Bits: TypeAlias = npt.NDArray[np.uint8]
# Bases: 0 = Z (rectilinea), 1 = X (diagonal). Mismo dtype que los bits.
Bases: TypeAlias = npt.NDArray[np.uint8]

Basis = Literal[0, 1]
Z_BASIS: Basis = 0
X_BASIS: Basis = 1


@dataclass(frozen=True)
class SiftedKeys:
    """Resultado del sifting: lo que comparten Alice y Bob antes de corregir."""

    alice: Bits  # clave cribada de Alice
    bob: Bits  # clave cribada de Bob (puede diferir de la de Alice)
    indices: npt.NDArray[np.int64]  # posiciones originales conservadas
    n_sent: int  # fotones enviados (para calcular el rendimiento)

    def __post_init__(self) -> None:
        assert self.alice.shape == self.bob.shape


@dataclass(frozen=True)
class QberEstimate:
    """Salida de la estimacion de errores (tarea 1.4)."""

    qber: float  # fraccion de errores en la muestra
    n_sample: int  # bits sacrificados (ya publicos, descartados)
    sigma: float  # sqrt(q(1-q)/n_sample): la barra de error
    remaining: SiftedKeys  # claves SIN los bits sacrificados


@dataclass(frozen=True)
class ReconciliationResult:
    """Salida de Cascade (tarea 1.5). leak_ec es el campo critico."""

    alice: Bits
    bob: Bits  # tras el exito, bob == alice
    leak_ec: int  # bits publicados. LA CIFRA QUE IMPORTA
    n_passes: int
    corrected: int  # errores corregidos
    ok: bool  # True si las claves coinciden

    @property
    def efficiency(self) -> float:
        """f_EC = leak_ec / (n * h(Q)). Debe salir ~1.1-1.2."""
        raise NotImplementedError


@dataclass(frozen=True)
class ProtocolResult:
    """Salida de la cadena completa. Es lo que consume el dashboard (1.9)."""

    n_photons: int
    sifted_len: int
    qber: QberEstimate
    reconciliation: ReconciliationResult | None
    final_key: Bits | None  # None si el protocolo aborto
    aborted: bool
    abort_reason: str | None
    secret_fraction: float  # ell / n_photons
