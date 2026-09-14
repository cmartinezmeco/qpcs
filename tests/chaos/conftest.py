"""tests/chaos/conftest.py - fixtures compartidas del modulo de caos.

Semilla fija siempre, nunca np.random.default_rng() a pelo. Regla
heredada de la Fase 1.
"""

from __future__ import annotations

import numpy as np
import pytest
from chaos.types import ClaveCaotica

SEMILLA = 42


@pytest.fixture
def rng() -> np.random.Generator:
    """Generador determinista para los tests que lo necesiten (p.ej. el
    testigo de que test_scaffold no oculta un import roto en otro sitio).
    """
    return np.random.default_rng(SEMILLA)


@pytest.fixture
def clave_logistica() -> ClaveCaotica:
    """Clave de referencia para el mapa logistico. r=3.99, caotica sin
    ambiguedad (lejos de la ventana de periodo 3 en r=3.83)."""
    return ClaveCaotica(sistema="logistico", x0=0.4, r=3.99)


@pytest.fixture
def clave_lorenz() -> ClaveCaotica:
    """Clave de referencia para Lorenz, parametros clasicos via types.py."""
    return ClaveCaotica(sistema="lorenz", x0=1.0, y0=1.0, z0=1.0)
