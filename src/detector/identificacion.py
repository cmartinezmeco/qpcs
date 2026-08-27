"""src/detector/identificacion.py - identificar los 4 tipos de ruido.

Cada tipo tiene una firma distinta (guia Fase 4, cap. 3.4):
  - disparo: espectro plano, Fano = 1 (Poisson)
  - termico: espectro plano, Fano != 1 (gaussiano)
  - flicker (1/f): espectro decreciente, exponente alfa
  - interferencia: picos estrechos sobre el fondo
"""

from __future__ import annotations

from .types import Espectro, Senal, TipoRuido


def ajustar_alfa(
    f: Espectro, psd: Espectro, rango: tuple[float, float]
) -> tuple[float, float]:
    """Exponente de la ley de potencias S(f) ~ A / f^alfa.

    En log-log una ley de potencias es una recta: log S = log A - alfa*log f,
    asi que alfa sale de una regresion lineal y su error del error
    estandar de la pendiente.

    DOS COSAS QUE HAY QUE HACER BIEN (guia Fase 4, cap. 3.5.1):
    1. Ajustar SOLO en el rango de baja frecuencia donde domina el 1/f.
       A alta frecuencia manda el suelo blanco, que es plano, e incluirlo
       tira de alfa hacia abajo.
    2. EXCLUIR los picos de interferencia antes de ajustar: un pico
       dentro del rango desvia la recta.

    Args:
        f: frecuencias.
        psd: densidad espectral.
        rango: (f_min, f_max) como fraccion de Nyquist, donde ajustar.

    Returns:
        (alfa, error_estandar_de_alfa).
    """
    raise NotImplementedError


def detectar_picos(f: Espectro, psd: Espectro, umbral: float) -> tuple[float, ...]:
    """Frecuencias donde la PSD supera el fondo local suavizado por
    'umbral' veces. Es la firma de las interferencias deterministas
    (red electrica y sus armonicos, reloj de la electronica).

    Args:
        f: frecuencias.
        psd: densidad espectral.
        umbral: factor sobre el fondo local (ver UMBRAL_PICO en types.py
            y su derivacion).

    Returns:
        Las frecuencias de los picos detectados, en Hz.
    """
    raise NotImplementedError


def factor_fano(senal: Senal) -> float:
    """F = Var[k] / E[k]. Para Poisson puro, F = 1 exacto.

    Es lo UNICO que distingue ruido de disparo de ruido termico: los dos
    tienen espectro plano, y solo se diferencian por la distribucion
    (guia Fase 4, cap. 3.2.1). Se calcula sobre la senal CON su pedestal,
    no sobre la version centrada: la media es el propio denominador.
    """
    raise NotImplementedError


def identificar_tipo_dominante(alfa: float, fano: float) -> TipoRuido:
    """Clasifica el tipo de ruido dominante a partir de alfa y Fano.

    alfa cerca de 0 y Fano cerca de 1 -> disparo.
    alfa cerca de 0 y Fano lejos de 1 -> termico.
    alfa apreciablemente > 0 -> flicker.
    (las interferencias se detectan aparte, con detectar_picos)
    """
    raise NotImplementedError
