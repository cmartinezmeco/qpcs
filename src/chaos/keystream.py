"""src/chaos/keystream.py - de la orbita a los bytes.

Cuantizacion con bits BAJOS, no altos (guia Fase 3, cap. 4.4): la densidad
invariante del mapa logistico con r=4 es rho(x) = 1/(pi*sqrt(x(1-x))), no
uniforme. Los bits de orden alto de x heredan ese sesgo; los de orden bajo
(en torno a la posicion 32) son, a efectos practicos, uniformes.
"""

from __future__ import annotations

from .types import ClaveCaotica, Keystream


def keystream_logistico(clave: ClaveCaotica, n_bytes: int) -> Keystream:
    """Genera n_bytes deterministas a partir de la clave logistica.

    Receta (ver guia Fase 3, cap. 4.4):
      1. Iterar TRANSITORIO pasos y descartarlos. Es lo que produce la
         sensibilidad a la clave.
      2. Tomar una muestra cada SUBMUESTREO pasos.
      3. Cuantizar con bits bajos: x * ESCALA_BITS, luego mod 256.

    Args:
        clave: debe ser de sistema "logistico".
        n_bytes: cuantos bytes generar.

    Returns:
        Array uint8 de longitud n_bytes.
    """
    raise NotImplementedError


def keystream_lorenz(clave: ClaveCaotica, n_bytes: int) -> Keystream:
    """Genera n_bytes deterministas a partir de la clave de Lorenz.

    Integra con RK4, descarta el transitorio, normaliza cada coordenada
    con los rangos DECLARADOS en LORENZ_RANGOS (nunca medidos: ver guia
    Fase 3, cap. 4.4), y cuantiza igual que en el caso logistico.

    Args:
        clave: debe ser de sistema "lorenz".
        n_bytes: cuantos bytes generar.

    Returns:
        Array uint8 de longitud n_bytes.
    """
    raise NotImplementedError


def keystream(clave: ClaveCaotica, n_bytes: int) -> Keystream:
    """Punto de entrada unico: despacha segun clave.sistema."""
    raise NotImplementedError


def histograma_chi2(datos: Keystream) -> float:
    """Estadistico chi-cuadrado del histograma de 256 valores.

    Bajo la hipotesis de uniformidad, sigue una chi2 con 255 grados de
    libertad (media 255, critico al 5% = 293.25). Ver guia Fase 3, cap. 6.4.
    """
    raise NotImplementedError
