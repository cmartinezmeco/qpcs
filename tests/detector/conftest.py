"""tests/detector/conftest.py - fixtures compartidas del modulo detector.

La senal sintetica es la pieza mas importante de esta tarea: sin ella, las
tareas 4.3 a 4.7 no pueden escribir un solo test
hasta que la 4.2 traiga datos reales. Con ella, Gonzalo y Marco pueden
desarrollarse en paralelo desde el primer dia.

Semilla fija siempre, nunca np.random.default_rng() a pelo (regla
heredada de la Fase 1).
"""

from __future__ import annotations

import numpy as np
import pytest

SEMILLA = 42


@pytest.fixture
def rng() -> np.random.Generator:
    """Generador determinista para los tests que lo necesiten."""
    return np.random.default_rng(SEMILLA)


@pytest.fixture
def senal_sintetica() -> tuple[np.ndarray, dict[str, float]]:
    """Senal con composicion CONOCIDA, para poder verificar que el
    analisis RECUPERA lo que se puso dentro. Misma idea que el test de
    RK4 del modulo 3: se valida contra la teoria, no contra otra
    implementacion.

    Mezcla ruido blanco gaussiano, una interferencia senoidal de 50 Hz y
    ruido de disparo (Poisson), sobre un pedestal de 1000 cuentas (los
    datos reales tampoco estan centrados en cero).
    """
    rng = np.random.default_rng(SEMILLA)
    n, fs = 2**20, 40_000.0  # ~1e6 muestras a 40 kHz

    verdad = {"alfa": 1.0, "pico_hz": 50.0, "sigma_blanco": 10.0}
    # Esta senal NO lleva componente 1/f, y se queda asi. Generar 1/f
    # exige filtrar ruido blanco en el dominio de la frecuencia, y esa
    # pieza acabo viviendo en detector.carga.senal_de_prueba, que es la
    # que usan los tests que necesitan el espectro completo. Lo que hace
    # falta aqui es una senal de composicion conocida y barata, con un
    # pico de interferencia identificable: para eso sobra con blanco mas
    # seno mas Poisson.
    t = np.arange(n) / fs
    blanco = rng.normal(0.0, verdad["sigma_blanco"], n)
    interferencia = 5.0 * np.sin(2 * np.pi * verdad["pico_hz"] * t)
    disparo = rng.poisson(100.0, n) - 100.0

    senal = blanco + interferencia + disparo + 1000.0
    return senal.astype(np.int32), verdad
