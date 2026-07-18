# tests/qkd/conftest.py
#
# Fixtures compartidas de la suite QKD (tarea 1.7). Politica contra los tests
# que parpadean (seccion 5.7.4 de la guia):
#   1. Semilla fija SIEMPRE: np.random.default_rng(42), nunca default_rng()
#      sin argumento.
#   2. Tolerancias derivadas de sigma, nunca inventadas.
#   3. n suficiente (un QBER con 100 fotones es ruido; con 40 000 es medida).
#   4. Prohibido el retry: si un test parpadea, se arregla o se borra.

from collections.abc import Callable

import numpy as np
import pytest

SEMILLA = 42


@pytest.fixture
def rng() -> np.random.Generator:
    """RNG determinista para todos los tests. Nunca default_rng() sin semilla."""
    return np.random.default_rng(SEMILLA)


@pytest.fixture(scope="session")
def sigma_qber() -> Callable[[float, int], float]:
    """Sigma de la estimacion del QBER: sqrt(q(1-q)/m).

    Para derivar tolerancias en los tests estadisticos (umbral tipico: 4
    sigma, que da una probabilidad de fallo espurio de ~6e-5: la CI no
    parpadea y un sesgo real si se detecta).
    """
    return lambda q, m: float(np.sqrt(max(q * (1 - q), 1e-12) / m))
