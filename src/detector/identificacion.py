"""src/detector/identificacion.py - identificar los 4 tipos de ruido.

Cada tipo tiene una firma distinta:
  - disparo: espectro plano, Fano = 1 (Poisson)
  - termico: espectro plano, Fano != 1 (gaussiano)
  - flicker (1/f): espectro decreciente, exponente alfa
  - interferencia: picos estrechos sobre el fondo
"""

from __future__ import annotations

import numpy as np
from scipy import signal, stats

from .types import Espectro, Senal, TipoRuido


def rango_alfa_en_hz(
    rango_fraccion_nyquist: tuple[float, float], fs: float
) -> tuple[float, float]:
    """Convierte RANGO_ALFA (fraccion de la frecuencia de Nyquist, tal
    como types.py lo documenta) a Hz reales, que es lo que ajustar_alfa
    espera recibir en su parametro 'rango'.

    BUG ENCONTRADO EN LA TAREA 4.8 (Marco) y ARREGLADO AQUI EN LA 4.9:
    types.py documenta RANGO_ALFA = (1e-4, 1e-2) como fraccion de
    Nyquist, pero ajustar_alfa() compara ese rango directamente contra
    las frecuencias en Hz que devuelve densidad_espectral(). Con
    fs=1000 Hz (los datos reales, convencion de la tarea 4.2),
    RANGO_ALFA interpretado como Hz no contiene ningun bin del
    espectro, y ajustar_alfa devuelve (0.0, 0.0) por su salida de
    seguridad de "menos de 3 puntos", no porque no haya componente 1/f.

    Esta funcion hace la conversion que faltaba: multiplica por la
    frecuencia de Nyquist (fs/2). Con fs=1000, RANGO_ALFA se convierte
    en (0.05, 5.0) Hz, que si contiene bins del espectro.

    No se ha cambiado la firma de ajustar_alfa() (fijada en la tarea
    4.1) ni RANGO_ALFA en types.py (fijada en la 4.1, y usar la unidad
    de fraccion de Nyquist en el contrato es razonable: hace que el
    mismo rango sirva para cualquier fs sin cambiar la constante).
    Se ha anadido esta funcion como el punto unico de conversion, para
    que cualquier consumidor (la tarea 4.9, el dashboard, o quien
    llame a ajustar_alfa en el futuro) no tenga que repetir la formula.
    """
    f_min_frac, f_max_frac = rango_fraccion_nyquist
    nyquist = fs / 2.0
    return f_min_frac * nyquist, f_max_frac * nyquist


def ajustar_alfa(
    f: Espectro, psd: Espectro, rango: tuple[float, float]
) -> tuple[float, float]:
    """Exponente de la ley de potencias S(f) ~ A / f^alfa.

    En log-log una ley de potencias es una recta: log S = log A - alfa*log f,
    asi que alfa sale de una regresion lineal y su error del error
    estandar de la pendiente.

    DOS COSAS QUE HAY QUE HACER BIEN:
    1. Ajustar SOLO en el rango de baja frecuencia donde domina el 1/f.
       A alta frecuencia manda el suelo blanco, que es plano, e incluirlo
       tira de alfa hacia abajo.
    2. EXCLUIR los picos de interferencia antes de ajustar: un pico
       dentro del rango desvia la recta.

    Args:
        f: frecuencias.
        psd: densidad espectral.
        rango: (f_min, f_max) en Hz, donde ajustar. RANGO_ALFA esta en
            fraccion de Nyquist: convertirlo con rango_alfa_en_hz.

    Returns:
        (alfa, error_estandar_de_alfa).
    """
    f_min, f_max = rango
    mascara_rango = (f >= f_min) & (f <= f_max) & (f > 0) & (psd > 0)
    f_sub = f[mascara_rango]
    psd_sub = psd[mascara_rango]

    if len(f_sub) < 3:
        return 0.0, 0.0

    fondo_local = signal.medfilt(psd_sub, kernel_size=11)
    mascara_picos = psd_sub <= 3.0 * fondo_local
    f_clean = f_sub[mascara_picos]
    psd_clean = psd_sub[mascara_picos]

    if len(f_clean) < 3:
        f_clean, psd_clean = f_sub, psd_sub

    slope, _, _, _, stderr = stats.linregress(np.log(f_clean), np.log(psd_clean))
    return float(-slope), float(stderr)


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
    if len(f) == 0 or len(psd) == 0:
        return tuple()

    kernel_size = min(31, len(psd) if len(psd) % 2 != 0 else len(psd) - 1)
    if kernel_size < 3:
        kernel_size = 3

    fondo_local = signal.medfilt(psd, kernel_size=kernel_size)
    picos_mask = psd > (umbral * fondo_local)

    picos_freqs: list[float] = []
    en_pico = False
    pico_actual_max_idx = -1

    for i, es_pico in enumerate(picos_mask):
        if es_pico:
            if not en_pico:
                en_pico = True
                pico_actual_max_idx = i
            else:
                if psd[i] > psd[pico_actual_max_idx]:
                    pico_actual_max_idx = i
        else:
            if en_pico:
                picos_freqs.append(float(f[pico_actual_max_idx]))
                en_pico = False

    if en_pico:
        picos_freqs.append(float(f[pico_actual_max_idx]))

    return tuple(picos_freqs)


def factor_fano(senal: Senal) -> float:
    """F = Var[k] / E[k]. Para Poisson puro, F = 1 exacto.

    Es lo UNICO que distingue ruido de disparo de ruido termico: los dos
    tienen espectro plano, y solo se diferencian por la distribucion
    de sus cuentas. Se calcula sobre la senal CON su pedestal,
    no sobre la version centrada: la media es el propio denominador.
    """
    if len(senal) == 0:
        return 0.0
    media = np.mean(senal)
    if media == 0:
        return 0.0
    varianza = np.var(senal, ddof=1)
    return float(varianza / media)


def identificar_tipo_dominante(alfa: float, fano: float) -> TipoRuido:
    """Clasifica el tipo de ruido dominante a partir de alfa y Fano.

    alfa cerca de 0 y Fano cerca de 1 -> disparo.
    alfa cerca de 0 y Fano lejos de 1 -> termico.
    alfa apreciablemente > 0 -> flicker.
    (las interferencias se detectan aparte, con detectar_picos)
    """
    if alfa > 0.2:
        return "flicker"
    elif abs(fano - 1.0) < 0.2:
        return "disparo"
    else:
        return "termico"
