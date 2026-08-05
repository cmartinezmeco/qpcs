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
    # MEJORA D1 (cierra I2/I4): el QBER con el que se ejecuto la
    # reconciliacion. Faltaba, y por eso efficiency no era implementable.
    # cascade() ya lo recibe como parametro y ya lo usaba para su log, asi
    # que aqui solo se propaga un valor que ya estaba en el ambito. Sin valor
    # por defecto a proposito: es obligatorio, para que no se pueda construir
    # un resultado cuya eficiencia salga indefinida por descuido.
    qber: float

    @property
    def efficiency(self) -> float:
        """f_EC = leak_ec / (n * h(Q)). Debe salir ~1.1-1.2.

        MEJORA D1: implementada (antes lanzaba NotImplementedError y los dos
        consumidores -dashboard y script de graficas- la calculaban por su
        cuenta, cada uno con su copia de la formula).

        Devuelve NaN cuando h(Q) = 0 (Q = 0 o Q = 1) o n = 0: la eficiencia
        no esta definida ahi. NO se devuelve 0.0 a proposito, porque un f_EC
        por debajo de 1 violaria el limite de Shannon y el proyecto usa
        justamente esa condicion como detector de bugs.
        """
        # Import local: privacy.py no importa types.py a nivel de modulo, pero
        # hacerlo al reves a nivel de fichero crearia un ciclo de imports.
        from .privacy import binary_entropy

        n = self.bob.size
        h = binary_entropy(self.qber)
        if n == 0 or h <= 0.0:
            return float("nan")
        return self.leak_ec / (n * h)


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
