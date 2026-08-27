"""tests/detector/test_scaffold.py - el contrato de la API publica.

Si esto falla, alguien ha renombrado o quitado algo de __all__ sin
avisar al equipo. Lee los nombres desde detector.__all__ en vez de
repetirlos a mano: escribir la lista dos veces permitiria justo el
fallo que este test deberia cazar.
"""

from __future__ import annotations

import detector


def test_api_publica_existe():
    """Cada nombre declarado en __all__ debe ser accesible en el paquete."""
    for nombre in detector.__all__:
        assert hasattr(detector, nombre), f"falta {nombre} en la API publica"


def test_las_constantes_del_contrato_no_se_han_movido():
    """types.py no se exporta por __init__, pero sus constantes son el
    contrato mas importante del modulo (guia Fase 4, cap. 5.2). Este
    test fija sus valores para que un cambio accidental salte aqui.
    """
    from detector.types import (
        BITS_BAJOS,
        EPSILON_PA,
        NPERSEG,
        RANGO_ALFA,
        SOLAPAMIENTO,
        UMBRAL_PICO,
        VENTANA,
    )

    assert NPERSEG == 4096
    assert SOLAPAMIENTO == 0.5
    assert VENTANA == "hann"
    assert RANGO_ALFA == (1e-4, 1e-2)
    assert UMBRAL_PICO == 3.0
    assert EPSILON_PA == 1e-9
    assert BITS_BAJOS == 4
