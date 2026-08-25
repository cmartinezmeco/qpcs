"""src/chaos/maps.py - dinamicas caoticas: mapa logistico y sistema de Lorenz.

DETERMINISMO (guia Fase 3, cap. 4): las formulas de este fichero se
escriben EXACTAMENTE como aparecen aqui y no se "simplifican" de forma
algebraicamente equivalente. Solo se usan sumas, restas y multiplicaciones,
que IEEE-754 garantiza correctamente redondeadas en cualquier maquina.
Ninguna funcion trascendente (sin, cos, exp, log) en este fichero.
"""

from __future__ import annotations

import numpy as np

from .types import LORENZ_BETA, LORENZ_RHO, LORENZ_SIGMA, Orbita


def orbita_logistica(x0: float, r: float, n: int) -> Orbita:
    """Itera x_{n+1} = r * x_n * (1 - x_n) y devuelve la orbita completa.

    DETERMINISMO (cap. 4): la expresion se escribe EXACTAMENTE asi y no
    se "simplifica" a r*(x - x*x), que es identica en algebra y distinta
    en coma flotante. Solo hay multiplicaciones y una resta: todas
    correctamente redondeadas por IEEE-754, luego el resultado es igual
    en cualquier maquina que cumpla la norma.

    Args:
        x0: condicion inicial, debe estar en (0, 1).
        r: parametro de crecimiento, tipicamente en (0, 4].
        n: numero de iteraciones a generar.

    Returns:
        Array de longitud n con float64.

    Raises:
        ValueError: si x0 no esta en el intervalo ABIERTO (0, 1). Los dos
            extremos son puntos fijos: con x0 = 0 la orbita es 0 para
            siempre, y con x0 = 1 el primer paso la lleva a 0 y se queda
            ahi. En los dos casos el "keystream" seria un byte repetido.
            Es uno de los ocho casos borde de la tarea 3.9 (guia Fase 3,
            cap. 8.9), y aqui es un ValueError y no un assert porque con
            python -O los assert desaparecen y la validacion con ellos.
    """
    # Sin esta guarda, x0 = 0 se cuela hasta lyapunov_logistico y sale
    # DECLARADO CAOTICO: la derivada del mapa en x = 0 vale r, asi que el
    # promedio de ln|f'| da ln(4) = 1.386 > UMBRAL_LYAPUNOV para r = 4. Es
    # decir, el punto fijo mas degenerado del mapa pasaria la validacion de
    # la tarea 3.3 con nota. Medido antes de anadir esta linea.
    if not 0.0 < x0 < 1.0:
        raise ValueError(
            f"x0 = {x0} fuera de (0, 1): 0 y 1 son puntos fijos del mapa "
            f"logistico y la orbita se queda clavada en ellos"
        )
    orb = np.empty(n, dtype=np.float64)
    x = float(x0)
    for i in range(n):
        x = r * x * (1.0 - x)
        orb[i] = x
    return orb


def _campo_lorenz(u: Orbita) -> Orbita:
    """dx/dt = sigma(y-x); dy/dt = x(rho-z)-y; dz/dt = xy - beta z."""
    x, y, z = u[0], u[1], u[2]
    return np.array(
        [
            LORENZ_SIGMA * (y - x),
            x * (LORENZ_RHO - z) - y,
            x * y - LORENZ_BETA * z,
        ],
        dtype=np.float64,
    )


def orbita_lorenz(u0: Orbita, n: int, h: float) -> Orbita:
    """Integra el sistema de Lorenz con Runge-Kutta de orden 4, paso fijo.

    Devuelve un array de forma (n, 3): la trayectoria completa.

    Paso fijo y no adaptativo a proposito (cap. 3.3): un integrador
    adaptativo elige el paso segun una estimacion del error, y esa
    eleccion puede variar entre versiones de SciPy. Aqui el descifrado
    exige la MISMA secuencia de operaciones siempre.

    Args:
        u0: condicion inicial (x0, y0, z0).
        n: numero de pasos de integracion.
        h: paso de integracion. Fijo, nunca adaptativo (ver cap. 3.3).

    Returns:
        Array de forma (n, 3) con float64: la trayectoria completa.
    """
    orb = np.empty((n, 3), dtype=np.float64)
    u = np.asarray(u0, dtype=np.float64).copy()
    for i in range(n):
        k1 = _campo_lorenz(u)
        k2 = _campo_lorenz(u + (h / 2.0) * k1)
        k3 = _campo_lorenz(u + (h / 2.0) * k2)
        k4 = _campo_lorenz(u + h * k3)
        u = u + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        orb[i] = u
    return orb
