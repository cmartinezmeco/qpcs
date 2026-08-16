"""src/chaos/lyapunov.py - exponente de Lyapunov y validacion del caos.

El logaritmo SI es una funcion trascendente, pero eso aqui no rompe el
determinismo: lambda es un diagnostico que decide si una clave es valida,
y no entra en el keystream (guia Fase 3, cap. 4.2). Puede diferir en el
bit doce entre maquinas y no afecta a nada.
"""

from __future__ import annotations

from .types import DiagnosticoCaos, Orbita


def lyapunov_logistico(
    x0: float, r: float, n: int = 100_000, transitorio: int = 1000
) -> DiagnosticoCaos:
    """Exponente de Lyapunov del mapa logistico.

    lambda = (1/N) * sum ln|f'(x_n)|, con f'(x) = r * (1 - 2x).

    Para r=4 el valor exacto es ln(2) = 0.6931471805... (el mapa logistico
    con r=4 es conjugado con el mapa de la tienda, ver guia Fase 3 cap. 3.4).

    Args:
        x0: condicion inicial.
        r: parametro del mapa.
        n: iteraciones usadas para el promedio, tras el transitorio.
        transitorio: iteraciones descartadas antes de empezar a promediar.

    Returns:
        DiagnosticoCaos con lambda, su error estandar, y es_caotico
        decidido contra UMBRAL_LYAPUNOV.
    """
    raise NotImplementedError


def espectro_lyapunov_lorenz(
    u0: Orbita | None = None, n: int = 50_000, tau: float = 0.5
) -> tuple[float, float, float]:
    """Espectro completo de exponentes de Lyapunov de Lorenz (Benettin).

    Devuelve (lambda_1, lambda_2, lambda_3). Verificacion gratis: la suma
    de los tres debe igualar -(sigma + 1 + beta) = -13.6666..., que es la
    divergencia del campo vectorial (guia Fase 3, cap. 3.4).

    Args:
        u0: condicion inicial. Si None, se usa (1.0, 1.0, 1.0).
        n: numero de renormalizaciones del algoritmo de Benettin.
        tau: intervalo de tiempo entre renormalizaciones.

    Returns:
        Los tres exponentes, de mayor a menor.
    """
    raise NotImplementedError


def detectar_ciclo(orb: Orbita) -> int | None:
    """Longitud del ciclo de una orbita en precision finita, por Floyd.

    Cualquier orbita en float64 es periodica (espacio de estados finito).
    Esta funcion mide esa longitud en vez de ignorarla (guia Fase 3, cap. 4.5).

    Returns:
        La longitud del ciclo detectado, o None si no se detecta dentro
        del numero de pasos disponible en la orbita.
    """
    raise NotImplementedError
