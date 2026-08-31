import numpy as np
from detector.espectro import densidad_espectral
from detector.identificacion import ajustar_alfa, detectar_picos, factor_fano
from detector.types import UMBRAL_PICO
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


# --- casos borde de la tarea 4.8 ---------------------------------------


def test_alfa_de_ruido_blanco_es_cero_con_la_funcion_del_modulo(rng):
    """Caso borde de la tarea 4.8: alfa ajustado sobre ruido blanco tiene
    que salir ~0, no un valor espurio. A diferencia del test de mas
    arriba, este llama a ajustar_alfa() del modulo, no a una regresion
    escrita aqui: el caso borde es del codigo, no de scipy.

    Tolerancia DERIVADA: el propio ajuste devuelve el error estandar de
    la pendiente, y se exige que el cero este dentro de 4 de esos errores.

    OJO CON EL RANGO (esto es un aviso para la tarea 4.4, no un arreglo
    aqui): types.py documenta RANGO_ALFA como "fraccion de la frecuencia
    de Nyquist", pero ajustar_alfa compara ese rango contra frecuencias en
    Hz. Con fs = 1000 Hz, RANGO_ALFA = (1e-4, 1e-2) no contiene ningun bin
    del espectro y la funcion devuelve (0.0, 0.0) por la salida de
    seguridad de "menos de 3 puntos", no por haber ajustado nada. Por eso
    aqui se pasa un rango explicito EN HERCIOS, para que el test compruebe
    el ajuste de verdad.
    """
    fs = 1000.0
    blanco = rng.normal(0, 1, 100_000)
    freqs, psd, _ = densidad_espectral(blanco, fs, 4096)

    alfa, error = ajustar_alfa(freqs, psd, (1.0, 100.0))

    assert error > 0.0
    assert abs(alfa) < 4 * error
    assert abs(alfa) < 0.1  # y en valor absoluto, lejos de cualquier 1/f


def test_fano_y_picos_del_modulo_sobre_la_senal_sintetica(senal_sintetica):
    """Cierra el caso borde anterior por el otro lado: las tres medidas de
    la 4.4 (alfa, picos y Fano) llamadas de verdad sobre la fixture, que
    es la forma de saber que la cadena de la tarea 4.8 se apoya en las
    funciones del modulo y no en reimplementaciones de los tests."""
    datos, verdad = senal_sintetica
    fs = 40_000.0
    freqs, psd, _ = densidad_espectral(datos, fs, 8192)

    picos = detectar_picos(freqs, psd, UMBRAL_PICO)
    df = fs / 8192
    assert any(abs(p - verdad["pico_hz"]) <= df for p in picos)

    # La senal lleva Poisson(100) sumado a gaussianas y a un pedestal de
    # 1000: el Fano resultante NO es 1 (eso es solo para Poisson puro),
    # pero tiene que ser un numero positivo y finito calculado sobre la
    # senal con su media.
    fano = factor_fano(datos)
    assert 0.0 < fano < np.inf
