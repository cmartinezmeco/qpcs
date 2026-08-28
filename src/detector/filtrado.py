"""src/detector/filtrado.py - quitar interferencias y deriva.

OJO (guia Fase 4, cap. 6.5): un filtro tiene memoria y por tanto PUEDE
INTRODUCIR correlacion, aunque la entrada no la tuviera. Es una trampa
perfecta aqui: se filtra para quitar la correlacion del 1/f y el filtro
mete correlacion propia. Por eso el orden se mantiene bajo a proposito y
hay un test obligatorio: filtrar ruido blanco tiene que dejarlo blanco.
"""

from __future__ import annotations

from .types import Espectro, Senal


def filtrar(senal: Senal, fs: float, picos_hz: tuple[float, ...]) -> Espectro:
    """Quita interferencias (notch) y deriva de baja frecuencia (paso alto).

    Filtros de fase cero (filtfilt): se aplica hacia adelante y hacia
    atras, de modo que el desfase que introduce en un sentido se cancela
    en el otro. Importa porque un desfase dependiente de la
    frecuencia deformaria la senal de una manera que el espectro no ve
    pero el factor de Fano si.

    OJO (guia Fase 4, cap. 6.5): un filtro tiene memoria y por tanto
    INTRODUCE correlacion. El orden se mantiene bajo a proposito, y hay
    un test que comprueba que filtrar ruido blanco lo deja blanco.

    Args:
        senal: la senal cruda.
        fs: frecuencia de muestreo en Hz.
        picos_hz: las frecuencias de interferencia detectadas en 4.4,
            a eliminar con notch.

    Returns:
        La senal filtrada, en float64 (ya no son cuentas ADC enteras).
    """

    # Convertir a float64 obligatoriamente
    datos = np.asarray(senal, dtype=np.float64)
    
    if len(datos) == 0:
        return datos

    nyq = fs / 2.0

    # 1. Filtro paso alto de orden bajo para eliminar la deriva de baja frecuencia
    # Se elige un corte muy bajo (ej. 1.0 Hz o adaptativo) para afectar lo menos posible al espectro útil
    cutoff_hp = max(0.5, fs / 1000.0)
    if cutoff_hp < nyq:
        b_hp, a_hp = signal.butter(2, cutoff_hp / nyq, btype='high')
        datos = signal.filtfilt(b_hp, a_hp, datos)

    # 2. Filtros notch sucesivos para cada frecuencia de interferencia detectada
    for pico in picos_hz:
        if 0 < pico < nyq:
            # Frecuencia normalizada (0 a 1, donde 1 es Nyquist)
            w0 = pico / nyq
            # Factor de calidad Q moderadamente alto para un notch estrecho que no destruya el fondo
            Q = 30.0
            b_notch, a_notch = signal.iirnotch(w0, Q)
            datos = signal.filtfilt(b_notch, a_notch, datos)

    return datos
