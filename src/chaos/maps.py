"""src/chaos/maps.py - dinamicas caoticas: mapa logistico y sistema de Lorenz.

DETERMINISMO (guia Fase 3, cap. 4): las formulas de este fichero se
escriben EXACTAMENTE como aparecen aqui y no se "simplifican" de forma
algebraicamente equivalente. Solo se usan sumas, restas y multiplicaciones,
que IEEE-754 garantiza correctamente redondeadas en cualquier maquina.
Ninguna funcion trascendente (sin, cos, exp, log) en este fichero.
"""

from __future__ import annotations

from .types import Orbita


def orbita_logistica(x0: float, r: float, n: int) -> Orbita:
    """Itera x_{n+1} = r * x_n * (1 - x_n) y devuelve la orbita completa.

    Args:
        x0: condicion inicial, debe estar en (0, 1).
        r: parametro de crecimiento, tipicamente en (0, 4].
        n: numero de iteraciones a generar.

    Returns:
        Array de longitud n con float64.
    """
    raise NotImplementedError


def orbita_lorenz(u0: Orbita, n: int, h: float) -> Orbita:
    """Integra el sistema de Lorenz con Runge-Kutta de orden 4, paso fijo.

    Args:
        u0: condicion inicial (x0, y0, z0).
        n: numero de pasos de integracion.
        h: paso de integracion. Fijo, nunca adaptativo (ver cap. 3.3).

    Returns:
        Array de forma (n, 3) con float64: la trayectoria completa.
    """
    raise NotImplementedError
