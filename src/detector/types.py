"""src/detector/types.py - contratos del modulo de ruido de detector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
import numpy.typing as npt

# Senal cruda: cuentas ADC. Enteros, porque eso es lo que da un ADC.
Senal: TypeAlias = npt.NDArray[np.int32]
# Todo lo que sea analisis va en float64, como en el modulo 3.
Espectro: TypeAlias = npt.NDArray[np.float64]
Bits: TypeAlias = npt.NDArray[np.uint8]

TipoRuido = Literal["disparo", "termico", "flicker", "interferencia"]

# --- CONSTANTES DEL CONTRATO -------------------------------------------
# Cambiarlas cambia todos los resultados publicados. No se tocan sin
# decirlo en el PR y regenerar las figuras.

NPERSEG: int = 4096  # tramo de Welch (guia Fase 4, cap. 3.5)
SOLAPAMIENTO: float = 0.5  # 50%, el estandar
VENTANA: str = "hann"

# Rango de ajuste del exponente alfa, en fraccion de la frecuencia de
# Nyquist. Se ajusta SOLO donde domina el 1/f, no en todo el espectro
# (guia Fase 4, cap. 3.5.1: a alta frecuencia manda el suelo blanco y
# tira de alfa hacia abajo).
RANGO_ALFA: tuple[float, float] = (1e-4, 1e-2)

# Un pico cuenta como interferencia si supera el fondo suave por este
# factor. Derivado: con Welch de K~487 tramos el error relativo del
# fondo es ~4.5%, asi que 5 sigma son ~1.22x. Se usa 3x por margen.
UMBRAL_PICO: float = 3.0

EPSILON_PA: float = 1e-9  # el mismo epsilon que la tarea 1.6
BITS_BAJOS: int = 4  # cuantos bits por muestra se conservan al digitalizar


@dataclass(frozen=True)
class AnalisisEspectral:
    """Salida de las tareas 4.3 y 4.4."""

    frecuencias: Espectro
    psd: Espectro
    alfa: float  # exponente del 1/f
    alfa_error: float  # error estandar del ajuste
    suelo_blanco: float  # nivel plano a alta frecuencia
    picos_hz: tuple[float, ...]  # interferencias detectadas
    fano: float  # varianza / media
    n_tramos: int  # K de Welch, para el error relativo


@dataclass(frozen=True)
class EstimacionEntropia:
    """Salida de la tarea 4.6. Se toma el MINIMO de los tres (guia cap. 4.3)."""

    h_mas_comun: float  # estimador del valor mas comun
    h_colision: float  # estimador de colision
    h_markov: float  # estimador de Markov (no asume independencia)
    h_min: float  # el MINIMO de los tres. Es el que se usa.
    n_muestras: int
    intervalo_confianza: float  # 0.99, el de SP 800-90B


@dataclass(frozen=True)
class ResultadoExtraccion:
    """Salida de la tarea 4.7."""

    bits: Bits
    n_entrada: int  # bits que entraron
    h_min_por_bit: float  # la estimacion usada
    longitud_segura: int  # ell = n*H_min - 2 log2(1/eps)
    z_monobit: float  # validacion
    chi2: float
