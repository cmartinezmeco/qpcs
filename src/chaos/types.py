"""src/chaos/types.py - contratos del modulo de caos determinista."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
import numpy.typing as npt

# Imagen en escala de grises, 8 bits. SIEMPRE uint8, nunca float.
Imagen: TypeAlias = npt.NDArray[np.uint8]
# Orbita y keystream: float64 obligatorio, por determinismo.
Orbita: TypeAlias = npt.NDArray[np.float64]
Keystream: TypeAlias = npt.NDArray[np.uint8]
# Permutacion: indices int64.
Permutacion: TypeAlias = npt.NDArray[np.int64]

Sistema = Literal["logistico", "lorenz"]

# --- CONSTANTES DEL CONTRATO -------------------------------------------
# Cambiar cualquiera de estas rompe la compatibilidad con imagenes ya
# cifradas y con vectors/keystream_v1.json. No se tocan sin cambiar de
# version del vector y decirlo explicitamente en el PR.

TRANSITORIO: int = 1000  # iteraciones descartadas antes de generar bytes
SUBMUESTREO: int = 3  # una muestra cada k pasos de la orbita
PASO_RK4: float = 0.01  # h de Lorenz. Fijo, nunca adaptativo.
ESCALA_BITS: float = 4294967296.0  # 2**32, para la cuantizacion en bits bajos

# Rangos DECLARADOS de Lorenz para normalizar. NO se miden en ejecucion:
# medirlos haria depender el keystream de la longitud de la orbita.
LORENZ_RANGOS: dict[str, tuple[float, float]] = {
    "x": (-25.0, 25.0),
    "y": (-30.0, 30.0),
    "z": (0.0, 55.0),
}

# Parametros clasicos de Lorenz. sigma + 1 + beta = 13.666...
# (la suma de los tres exponentes de Lyapunov debe dar -13.666...,
# es una verificacion numerica gratis del integrador)
LORENZ_SIGMA: float = 10.0
LORENZ_RHO: float = 28.0
LORENZ_BETA: float = 8.0 / 3.0

UMBRAL_LYAPUNOV: float = 0.01  # lambda por debajo de esto => se rechaza la clave


@dataclass(frozen=True)
class ClaveCaotica:
    """La clave. Es lo unico secreto de todo el modulo.

    Para "logistico" se usan x0 y r; para "lorenz", x0, y0, z0 y opcionalmente
    rho. Los campos que no aplican quedan a None y se validan en __post_init__.
    """

    sistema: Sistema
    x0: float
    r: float | None = None  # solo logistico
    y0: float | None = None  # solo lorenz
    z0: float | None = None  # solo lorenz
    rho: float | None = None  # solo lorenz

    def __post_init__(self) -> None:
        if self.sistema == "logistico":
            assert self.r is not None, "el mapa logistico necesita r"
            assert 0.0 < self.x0 < 1.0, "x0 debe estar en (0, 1)"
        else:
            assert (
                self.y0 is not None and self.z0 is not None
            ), "lorenz necesita y0 y z0"


@dataclass(frozen=True)
class DiagnosticoCaos:
    """Salida de la tarea 3.3. Es lo que decide si la clave sirve."""

    lyapunov: float  # exponente medido
    n_iteraciones: int  # con cuantas se midio
    sigma: float  # error estandar de la media
    es_caotico: bool  # lyapunov > UMBRAL_LYAPUNOV
    ciclo_detectado: int | None  # longitud del ciclo, None si no se hallo


@dataclass(frozen=True)
class ImagenCifrada:
    """Lo que viaja. hash_plano filtra informacion: ver docs/limitaciones.md."""

    datos: Imagen
    alto: int
    ancho: int
    sistema: Sistema
    iv: int
    hash_plano: str  # SHA-256 hex del texto plano

    def __post_init__(self) -> None:
        assert self.datos.dtype == np.uint8
        assert self.datos.size == self.alto * self.ancho


@dataclass(frozen=True)
class MetricasImagen:
    """Salida de la tarea 3.7. Una fila de la tabla comparativa."""

    etiqueta: str  # "caotico", "AES-256-GCM", "contador"
    entropia: float
    entropia_esperada: float  # con correccion de sesgo de Miller-Madow
    corr_horizontal: float
    corr_vertical: float
    corr_diagonal: float
    chi2: float
    npcr: float | None = None  # None si no aplica (p.ej. solo una imagen)
    uaci: float | None = None
