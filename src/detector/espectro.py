"""src/detector/espectro.py - densidad espectral de potencia por Welch.

El periodograma simple es un estimador INCONSISTENTE: su varianza no baja
al aumentar N (guia Fase 4, cap. 3.5). Welch parte la senal en tramos
solapados, aplica ventana y promedia los periodogramas: la varianza baja
por un factor K (numero de tramos) a cambio de resolucion en frecuencia.
"""

from __future__ import annotations

import numpy as np
from scipy import signal

from .types import Espectro, Senal


def densidad_espectral(
    senal: Senal, fs: float, nperseg: int
) -> tuple[Espectro, Espectro, int]:
    """Densidad espectral de potencia por el metodo de Welch.

    Se resta la media ANTES de transformar: un pedestal de cientos o
    miles de cuentas mete un pico enorme en f=0 que domina la escala y
    no deja ver nada (guia Fase 4, cap. 6.3, la caja roja).

    Con N muestras y tramos de longitud nperseg al 50% de solapamiento,
    K ~ 2N/nperseg - 1 tramos, y el error relativo de cada punto de la
    PSD es ~1/sqrt(K). Con N = 2^20 y L = 4096: K ~ 511, error ~4.4%.

    Args:
        senal: la senal cruda, con su pedestal.
        fs: frecuencia de muestreo en Hz.
        nperseg: longitud de cada tramo de Welch.

    Returns:
        (frecuencias, psd, n_tramos): frecuencias en Hz, la densidad
        espectral, y K para poder reportar el error relativo.

    Raises:
        ValueError: si nperseg no cabe en la senal. Anadido como caso
            borde en la tarea 4.8: scipy.signal.welch, en ese caso, avisa
            por warnings y RECORTA nperseg a la longitud de la senal, de
            modo que la resolucion en frecuencia del resultado no es la
            que dice el contrato y el K devuelto seria mentira. Mejor
            parar que publicar un espectro calculado con otros parametros.
    """
    if nperseg <= 0:
        raise ValueError(f"nperseg debe ser positivo, recibido {nperseg}")
    if nperseg > len(senal):
        raise ValueError(
            f"nperseg ({nperseg}) es mayor que la senal ({len(senal)} "
            f"muestras): Welch no puede partirla en tramos de esa longitud"
        )

    freqs, psd = signal.welch(senal, fs=fs, nperseg=nperseg)
    return (
        np.asarray(freqs, dtype=np.float64),
        np.asarray(psd, dtype=np.float64),
        int(nperseg),
    )
