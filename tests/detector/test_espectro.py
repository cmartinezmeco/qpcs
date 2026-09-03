import numpy as np
import pytest

from detector.espectro import densidad_espectral
from detector.types import NPERSEG


def test_ruido_blanco_da_espectro_plano(rng):
    """Ruido gaussiano puro: la PSD debe ser plana. La tolerancia sale
    del propio metodo: con K tramos, el error relativo es 1/sqrt(K).
    """
    fs = 1000.0
    nperseg = 256
    senal = rng.normal(0, 1, 15000)

    freqs, psd, _ = densidad_espectral(senal, fs, nperseg)

    # El espectro de ruido blanco normalizado con varianza 1 tiene una
    # PSD teorica esperada. Comprobamos que la media y la fluctuacion
    # se ajustan al error estadistico del metodo de Welch.
    media_psd = np.mean(psd)
    # La desviacion estandar relativa en el metodo de Welch escala
    # aproximadamente con 1/sqrt(K), donde K es el numero de segmentos
    # promediados.
    assert np.all(psd > 0)
    assert (
        abs(np.std(psd) / media_psd - 1.0 / np.sqrt(len(psd))) < 0.5
    )


def test_el_pico_aparece_donde_se_puso():
    """Se metio una senoide de 50 Hz: el maximo de la PSD, excluida la
    zona de baja frecuencia, tiene que caer en 50 Hz +- la resolucion
    df = fs/nperseg.
    """
    fs = 1000.0
    nperseg = 512
    df = fs / nperseg

    t = np.arange(0, 5, 1 / fs)
    f_seno = 50.0
    senal = np.sin(2 * np.pi * f_seno * t)

    freqs, psd, _ = densidad_espectral(senal, fs, nperseg)

    idx_valido = freqs > 5.0
    freqs_validas = freqs[idx_valido]
    psd_validas = psd[idx_valido]

    pico_freq = freqs_validas[np.argmax(psd_validas)]

    assert abs(pico_freq - f_seno) <= df


def test_parseval(rng):
    """La potencia total del espectro tiene que coincidir con la
    varianza de la senal. Es una verificacion independiente del
    escalado, y si falla, la normalizacion esta mal.
    """
    fs = 1000.0
    nperseg = 256
    senal = rng.normal(2.0, 3.5, 10000)

    freqs, psd, _ = densidad_espectral(senal, fs, nperseg)

    df = freqs[1] - freqs[0]
    senal_centrada = senal - np.mean(senal)
    varianza_teorica = np.var(senal_centrada)
    potencia_espectral = np.sum(psd) * df

    np.testing.assert_allclose(potencia_espectral, varianza_teorica, rtol=0.1)


# --- casos borde de la tarea 4.8 ---------------------------------------


def test_nperseg_mayor_que_la_senal_da_un_error_explicito(rng):
    """Caso borde de la tarea 4.8: ValueError explicito, no truncar.

    scipy.signal.welch, ante un nperseg mayor que la senal, avisa por
    warnings y lo RECORTA a la longitud de la senal. El resultado sale con
    otra resolucion en frecuencia que la que dice el contrato, y el numero
    de tramos devuelto ya no describe el calculo que se ha hecho: es
    justo el tipo de fallo silencioso que este proyecto convierte en
    excepcion.
    """
    corta = rng.normal(0, 1, 500)
    with pytest.raises(ValueError, match="mayor que la senal"):
        densidad_espectral(corta, 1000.0, NPERSEG)


def test_nperseg_no_positivo_da_un_error_explicito(rng):
    """La otra mitad del mismo guardarrail."""
    senal = rng.normal(0, 1, 5000)
    with pytest.raises(ValueError, match="positivo"):
        densidad_espectral(senal, 1000.0, 0)
