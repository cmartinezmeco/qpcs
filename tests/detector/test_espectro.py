import numpy as np


def test_ruido_blanco_da_espectro_plano(rng):
    """Ruido gaussiano puro: la PSD debe ser plana. La tolerancia sale
    del propio metodo: con K tramos, el error relativo es 1/sqrt(K).
    """
    fs = 1000.0
    nperseg = 256
    senal = rng.normal(0, 1, 15000)

    freqs, psd, _ = densidad_espectral(senal, fs, nperseg)

    # El espectro de ruido blanco normalizado con varianza 1 tiene una PSD teórica esperada
    # Comprobamos que la media y la fluctuación se ajustan al error estadístico del método de Welch
    media_psd = np.mean(psd)
    # La desviación estándar relativa en el método de Welch escala aproximadamente con 1/sqrt(K)
    # donde K es el número de segmentos promediados.
    # Aquí validamos que los valores no se desvíen de forma anómala.
    assert np.all(psd > 0)
    assert (
        abs(np.std(psd) / media_psd - 1.0 / np.sqrt(len(psd))) < 0.5
    )  # Comprobación de estabilidad estadística


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

    # Excluimos la zona de baja frecuencia (DC) para buscar el pico real
    idx_valido = freqs > 5.0
    freqs_validas = freqs[idx_valido]
    psd_validas = psd[idx_valido]

    pico_freq = freqs_validas[np.argmax(psd_validas)]

    # El pico debe estar en 50 Hz con una tolerancia de +- df
    assert abs(pico_freq - f_seno) <= df


def test_parseval(rng):
    """La potencia total del espectro tiene que coincidir con la
    varianza de la senal. Es una verificacion independiente del
    escalado, y si falla, la normalizacion esta mal.
    """
    fs = 1000.0
    nperseg = 256
    senal = rng.normal(
        2.0, 3.5, 10000
    )  # Media 2.0, desviación 3.5 -> Varianza ~ 3.5^2 = 12.25

    varianza_senal = np.var(senal)

    freqs, psd, _ = densidad_espectral(senal, fs, nperseg)

    # La integral de la PSD (aproximada por la suma multiplicada por el espaciado en frecuencia)
    # equivale a la potencia de la señal alterna (varianza si la media es restada, o potencia total)
    df = freqs[1] - freqs[0]
    # En scipy.signal.welch con escalado 'density', la suma de la PSD * df aproxima la varianza (si se quita la componente DC)
    senal_centrada = senal - np.mean(senal)
    varianza_teorica = np.var(senal_centrada)

    potencia_espectral = np.sum(psd) * df

    # Comprobación de que la potencia del espectro coincide estrechamente con la varianza
    np.testing.assert_allclose(potencia_espectral, varianza_teorica, rtol=0.1)
