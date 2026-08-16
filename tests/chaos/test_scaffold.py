"""tests/chaos/test_scaffold.py - el contrato de la API publica.

Si esto falla, alguien ha renombrado o quitado algo de __all__ sin
avisar al equipo. Lee los nombres desde chaos.__all__ en vez de
repetirlos a mano: escribir la lista dos veces permitiria justo el
fallo que este test deberia cazar.
"""

from __future__ import annotations

import chaos


def test_api_publica_existe():
    """Cada nombre declarado en __all__ debe ser accesible en el paquete."""
    for nombre in chaos.__all__:
        assert hasattr(chaos, nombre), f"falta {nombre} en la API publica"


def test_las_constantes_del_contrato_no_se_han_movido():
    """types.py no se exporta por __init__, pero sus constantes son el
    contrato mas importante del modulo (guia Fase 3, cap. 7.2). Este
    test fija sus valores para que un cambio accidental salte aqui.
    """
    from chaos.types import (
        ESCALA_BITS,
        PASO_RK4,
        SUBMUESTREO,
        TRANSITORIO,
        UMBRAL_LYAPUNOV,
    )

    assert TRANSITORIO == 1000
    assert SUBMUESTREO == 3
    assert PASO_RK4 == 0.01
    assert ESCALA_BITS == 4294967296.0
    assert UMBRAL_LYAPUNOV == 0.01
