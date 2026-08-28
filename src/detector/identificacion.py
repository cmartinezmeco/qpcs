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

    f_min, f_max = rango
    # Filtrar estrictamente dentro del rango de frecuencias especificado
    mascara_rango = (f >= f_min) & (f <= f_max) & (f > 0) & (psd > 0)

    f_sub = f[mascara_rango]
    psd_sub = psd[mascara_rango]

    if len(f_sub) < 3:
        return 0.0, 0.0

    # Excluir picos de interferencia locales comparando con una envolvente suave (mediana)
    fondo_local = signal.medfilt(psd_sub, kernel_size=11)
    # Si un punto supera significativamente el fondo local, se considera un pico y se excluye
    mascara_picos = psd_sub <= 3.0 * fondo_local

    f_clean = f_sub[mascara_picos]
    psd_clean = psd_sub[mascara_picos]

    if len(f_clean) < 3:
        f_clean, psd_clean = f_sub, ps_sub = f_sub, psd_sub

    log_f = np.log(f_clean)
    log_psd = np.log(psd_clean)

    slope, _, _, _, stderr = stats.linregress(log_f, log_psd)
    alfa = -slope

    return float(alfa), float(stderr)


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

    # Calcular el fondo local mediante un filtro de mediana para suavizar picos
    # Se ajusta el tamaño del kernel según la longitud del array
    kernel_size = min(31, len(psd) if len(psd) % 2 != 0 else len(psd) - 1)
    if kernel_size < 3:
        kernel_size = 3

    fondo_local = signal.medfilt(psd, kernel_size=kernel_size)

    # Identificar puntos donde la PSD supera al fondo por el factor de umbral
    picos_mask = psd > (umbral * fondo_local)

    # Filtrar para quedarse con los máximos locales de los grupos contiguos de picos
    picos_freqs = []
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
    (guia Fase 4, cap. 3.2.1). Se calcula sobre la senal CON su pedestal,
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

    # Umbrales basados en la descripción teórica de la guía
    if alfa > 0.2:
        return TipoRuido.FLICKER
    elif abs(fano - 1.0) < 0.2:
        return TipoRuido.DISPARO
    else:
        return TipoRuido.TERMICO
