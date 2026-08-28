"""src/detector/carga.py - lectura de la senal de ruido de detector.

El subconjunto versionado en data/muestra_pedestal.npz permite ejecutar
todo el modulo sin descargar nada (guia Fase 4, cap. 5.1). El conjunto
completo, si hace falta, se trae con scripts/descargar_datos.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .types import Espectro, Senal


def cargar_muestra(
    ruta: Path | str = "data/muestra_pedestal.npz",
) -> tuple[Senal, float]:
    """Carga el subconjunto versionado de la senal de ruido.

    El subconjunto es nPFCands (numero de candidatos de Particle Flow por
    evento) de un fichero del dataset publico CMS ZeroBias en formato
    NanoAOD (record 31316 del CERN Open Data Portal). NO es una lectura
    directa de un ADC: ver data/FUENTE.md para la justificacion completa
    de por que esta variable, que otras 4 colecciones se probaron primero
    y fallaron (limitaciones de uproot frente a clases custom de CMSSW),
    y por que fs=1000.0 es una convencion y no una medida fisica.

    Args:
        ruta: fichero .npz con las claves 'senal' (int32) y 'fs' (float64).
            Por defecto, el subconjunto del repositorio.

    Returns:
        (senal, fs): la senal en cuentas (int32, aqui numero de candidatos
        por evento) y la frecuencia de muestreo nominal en Hz.

    Raises:
        FileNotFoundError: con un mensaje que dice como obtener los datos
            si el fichero no esta (ver data/FUENTE.md).
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encuentra {ruta}. El subconjunto de datos deberia estar "
            f"versionado en el repositorio; si falta, ver data/FUENTE.md "
            f"para el procedimiento completo de regeneracion desde "
            f"opendata.cern.ch/record/31316."
        )
    datos = np.load(ruta)
    senal = datos["senal"].astype(np.int32)
    fs = float(datos["fs"])
    return senal, fs


def _ruido_potencia(n: int, alfa: float, rng: np.random.Generator) -> Espectro:
    """Genera ruido con densidad espectral S(f) ~ 1/f^alfa, por filtrado
    en el dominio de la frecuencia (guia Fase 4, cap. 3.5 y 6.1).

    Metodo: ruido blanco -> FFT -> escalar cada componente de frecuencia
    por 1/sqrt(f^alfa) (raiz porque se escalan AMPLITUDES, la densidad de
    POTENCIA escala como el cuadrado) -> FFT inversa. Determinista con
    la semilla del rng.

    alfa=0 devuelve ruido blanco sin modificar (division por f^0 = 1).
    La componente f=0 (continua) se deja sin escalar para evitar
    division por cero; no afecta al analisis porque la media se resta
    antes de calcular el espectro (ver espectro.py).
    """
    blanco = rng.normal(0.0, 1.0, n)
    espectro = np.fft.rfft(blanco)
    frecuencias = np.fft.rfftfreq(n)
    factor = np.ones_like(frecuencias)
    # frecuencias[0] == 0.0 (continua): se deja el factor en 1 para no
    # dividir por cero. El resto se escala por 1/sqrt(f^alfa).
    factor[1:] = 1.0 / np.sqrt(frecuencias[1:] ** alfa)
    espectro_coloreado = espectro * factor
    resultado = np.fft.irfft(espectro_coloreado, n=n)
    # Normalizar a varianza unidad, para que el sigma_blanco del llamante
    # controle la escala final de forma predecible.
    normalizado: Espectro = resultado / resultado.std()
    return normalizado


def senal_de_prueba(
    n: int = 2**20, fs: float = 40_000.0, semilla: int = 42
) -> tuple[Senal, float]:
    """Genera una senal sintetica con composicion CONOCIDA, para tests
    y para verificar que el analisis espectral RECUPERA lo que se puso
    dentro. Misma idea que el test de RK4 del modulo 3: se valida contra
    la teoria, no contra otra implementacion (guia Fase 4, cap. 6.1).

    Mezcla ruido blanco gaussiano, ruido 1/f (alfa=1.0, por filtrado
    espectral), una interferencia senoidal de 50 Hz, y ruido de disparo
    (Poisson), sobre un pedestal de 1000 cuentas (los datos reales
    tampoco estan centrados en cero: ver data/muestra_pedestal.npz,
    con pedestal ~1435).

    A diferencia de cargar_muestra(), esta funcion NO sustituye a los
    datos reales: es la referencia teorica que permite comprobar en la
    tarea 4.4 que ajustar_alfa() recupera alfa=1.0 cuando se le da una
    senal donde alfa=1.0 de verdad, cosa que con datos reales no se
    puede verificar porque no se conoce su composicion exacta.

    Args:
        n: numero de muestras a generar.
        fs: frecuencia de muestreo nominal, en Hz.
        semilla: para reproducibilidad.

    Returns:
        (senal, fs).
    """
    rng = np.random.default_rng(semilla)
    sigma_blanco = 10.0
    pico_hz = 50.0

    t = np.arange(n) / fs
    blanco = rng.normal(0.0, sigma_blanco, n)
    flicker = _ruido_potencia(n, alfa=1.0, rng=rng) * sigma_blanco
    interferencia = 5.0 * np.sin(2 * np.pi * pico_hz * t)
    disparo = rng.poisson(100.0, n).astype(np.float64) - 100.0

    senal = blanco + flicker + interferencia + disparo + 1000.0
    return senal.astype(np.int32), fs
