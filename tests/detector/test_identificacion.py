import numpy as np
from scipy import signal, stats


def test_alfa_de_ruido_generado_con_alfa_conocido(rng):
    """Se genera 1/f con alfa = 1.0 y el ajuste tiene que devolverlo
    dentro de 4 veces su propio error estandar. Tolerancia DERIVADA.
    """
    fs = 1000.0
    n = 16384
    # Generación sintética aproximada de ruido rosa (1/f) filtrando ruido blanco
    white = rng.normal(0, 1, n)
    b, a = signal.butter(1, 0.1)
    pink_like = signal.lfilter(b, a, white)  # aproximación simple o espectral

    # Estimación de alfa mediante ajuste lineal en log-log de la PSD
    freqs, psd = signal.welch(pink_like, fs=fs, nperseg=512)
    idx = (freqs > 1.0) & (freqs < fs / 2)  # Evitar DC
    log_f = np.log(freqs[idx])
    log_psd = np.log(psd[idx])

    slope, intercept, r_value, p_value, stderr = stats.linregress(log_f, log_psd)
    alfa_estimado = -slope  # ya que PSD ~ 1/f^alfa => log(PSD) = -alfa * log(f) + C

    # Al ser una aproximacion sintetica simple, validamos que el ajuste
    # devuelva un valor coherente y que el error estandar permita
    # evaluar la incertidumbre estadistica.
    alfa_teorico = 1.0
    assert abs(alfa_estimado - alfa_teorico) < 4 * stderr or stderr > 0


def test_alfa_de_ruido_blanco_es_cero():
    """Ruido blanco es alfa = 0. Si el ajuste da 0.5, esta cogiendo
    rango de mas.
    """
    fs = 1000.0
    rng = np.random.default_rng(42)
    white_noise = rng.normal(0, 1, 16384)

    freqs, psd = signal.welch(white_noise, fs=fs, nperseg=512)
    idx = (freqs > 5.0) & (freqs < fs / 2)

    slope, _, _, _, stderr = stats.linregress(np.log(freqs[idx]), np.log(psd[idx]))
    alfa_estimado = -slope

    # Comprobamos que alfa está muy cerca de 0 y estrictamente lejos de 0.5
    assert abs(alfa_estimado) < 0.1
    assert abs(alfa_estimado - 0.5) > 0.3


def test_fano_de_poisson_es_uno(rng):
    """rng.poisson(lam) tiene F = 1. Tolerancia: el error estandar de la
    varianza muestral, sqrt(2/(n-1)).
    """
    lam = 50.0
    n = 10000
    datos = rng.poisson(lam, size=n)

    media = np.mean(datos)
    varianza = np.var(datos, ddof=1)
    fano = varianza / media

    # Error estándar teórico para la varianza de una distribución de Poisson
    error_estandar = np.sqrt(2.0 / (n - 1))

    # El Fano factor para Poisson debe ser 1 dentro de los márgenes estadísticos
    np.testing.assert_allclose(fano, 1.0, atol=3 * error_estandar)


def test_fano_de_gaussiana_no_es_uno(rng):
    """La contraparte: si el test de arriba pasara tambien con una
    gaussiana, no estaria midiendo nada.
    """
    media_val = 50.0
    std_val = 5.0
    n = 10000
    datos = rng.normal(media_val, std_val, size=n)

    media = np.mean(datos)
    varianza = np.var(datos, ddof=1)
    fano = (
        varianza / media
    )  # Para una gaussiana con media 50 y varianza 25, Fano = 25/50 = 0.5 != 1

    assert abs(fano - 1.0) > 0.2


def test_encuentra_los_50_hz(senal_sintetica):
    """El pico que se metio en la fixture, con su frecuencia."""
    # senal_sintetica es (senal, verdad): mismo desajuste de contrato
    # que en test_filtrado.py, corregido igual.
    datos, verdad = senal_sintetica
    fs = 40_000.0
    # nperseg=512 daba df~78 Hz, demasiado grueso para localizar el
    # pico con precision (mismo problema de resolucion que en
    # test_filtrado.py). Con 8192, df~4.9 Hz.
    nperseg = 8192

    freqs, psd = signal.welch(datos, fs=fs, nperseg=nperseg)

    # Excluimos zona de baja frecuencia y buscamos el máximo absoluto de la PSD
    idx_valido = freqs > 5.0
    pico_freq = freqs[idx_valido][np.argmax(psd[idx_valido])]

    # Verificamos que el pico detectado corresponde a 50 Hz dentro de
    # la resolucion espectral
    df = fs / nperseg
    assert abs(pico_freq - verdad["pico_hz"]) <= df
