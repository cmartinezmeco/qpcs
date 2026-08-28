import numpy as np
from detector.filtrado import filtrar
from scipy import signal


def test_el_filtro_no_ensucia_ruido_blanco(rng):
    """EL test de esta tarea. Ruido blanco filtrado sigue siendo blanco:
    su autocorrelacion a desplazamiento 1 tiene que quedar dentro de
    4/sqrt(n). Si falla, el filtro esta metiendo la correlacion que
    veniamos a quitar.
    """
    fs = 1000.0
    n = 10000
    ruido_blanco = rng.normal(0, 1, n)

    # Supongamos que no hay picos de interferencia para limpiar en ruido blanco puro
    picos_hz = ()
    senal_filtrada = filtrar(ruido_blanco, fs, picos_hz)

    # Calcular la autocorrelación a desplazamiento (lag) 1
    # Normalizada para que la autocorrelación en lag 0 sea 1.0
    media = np.mean(senal_filtrada)
    v = senal_filtrada - media
    autocorr_1 = np.sum(v[:-1] * v[1:]) / np.sum(v**2)

    limite = 4.0 / np.sqrt(n)
    assert abs(autocorr_1) < limite


def test_el_pico_desaparece(senal_sintetica):
    """La potencia en 50 Hz tras filtrar cae al menos un factor 100."""
    # senal_sintetica es (senal, verdad), no un dict: la fixture de la
    # tarea 4.1 fija fs=40_000.0 dentro de la propia funcion, no como
    # clave de verdad. picos_hz sale de verdad["pico_hz"].
    datos, verdad = senal_sintetica
    fs = 40_000.0
    picos_hz = (verdad["pico_hz"],)

    # Medir la potencia en 50 Hz antes de filtrar
    # nperseg=1024 daba df=39 Hz, mas ancho que la banda que este test
    # intenta medir: el bin "mas cercano a 50 Hz" en realidad caia a
    # decenas de Hz de distancia real, y arrastraba potencia del propio
    # pico por fuga espectral. Con nperseg=16384, df~2.4 Hz, suficiente
    # para aislar el pico sin comerse resolucion excesiva (siguen
    # saliendo >60 tramos de Welch con la senal de 2**20 muestras).
    nperseg = 16384
    freqs, psd_antes = signal.welch(datos, fs=fs, nperseg=nperseg)
    idx_50 = np.argmin(np.abs(freqs - verdad["pico_hz"]))
    potencia_antes = psd_antes[idx_50]

    # Filtrar
    senal_filtrada = filtrar(datos, fs, picos_hz)

    _, psd_despues = signal.welch(senal_filtrada, fs=fs, nperseg=nperseg)
    potencia_despues = psd_despues[idx_50]

    # La potencia debe caer al menos un factor 100
    assert potencia_despues <= potencia_antes / 100.0


def test_el_resto_del_espectro_sobrevive(senal_sintetica):
    """La contraparte: la potencia FUERA de la banda del notch no cambia
    mas de un 5%. Sin este test, un filtro que lo borrara todo pasaria
    el de arriba con nota.
    """
    datos, verdad = senal_sintetica
    fs = 40_000.0
    picos_hz = (verdad["pico_hz"],)

    # nperseg=1024 daba df=39 Hz, mas ancho que la banda que este test
    # intenta medir: el bin "mas cercano a 50 Hz" en realidad caia a
    # decenas de Hz de distancia real, y arrastraba potencia del propio
    # pico por fuga espectral. Con nperseg=16384, df~2.4 Hz, suficiente
    # para aislar el pico sin comerse resolucion excesiva (siguen
    # saliendo >60 tramos de Welch con la senal de 2**20 muestras).
    nperseg = 16384
    freqs, psd_antes = signal.welch(datos, fs=fs, nperseg=nperseg)

    senal_filtrada = filtrar(datos, fs, picos_hz)
    _, psd_despues = signal.welch(senal_filtrada, fs=fs, nperseg=nperseg)

    # Excluir la zona cercana al pico (banda de +-3 Hz)
    mascara_fuera = np.abs(freqs - verdad["pico_hz"]) > 3.0

    psd_antes_fuera = np.mean(psd_antes[mascara_fuera])
    psd_despues_fuera = np.mean(psd_despues[mascara_fuera])

    # La potencia media fuera del notch no debe cambiar más de un 5% (relativo)
    cambio_relativo = np.abs(psd_despues_fuera - psd_antes_fuera) / psd_antes_fuera
    assert cambio_relativo < 0.05


def test_la_varianza_baja_pero_no_se_desploma(senal_sintetica):
    """Quitar interferencias y deriva reduce la varianza; si la reduce en
    mas de un orden de magnitud, se esta llevando tambien el ruido
    fundamental.
    """
    datos, verdad = senal_sintetica
    fs = 40_000.0
    picos_hz = (verdad["pico_hz"],)

    var_antes = np.var(datos)
    senal_filtrada = filtrar(datos, fs, picos_hz)
    var_despues = np.var(senal_filtrada)

    # La varianza debe bajar (por quitar deriva y picos de potencia fuerte)
    assert var_despues < var_antes
    # Pero no debe reducirse en más de un orden de magnitud (factor 10)
    assert var_despues >= var_antes / 10.0
