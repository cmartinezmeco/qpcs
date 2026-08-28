"""src/detector/carga.py - lectura de la senal de ruido de detector.

El subconjunto versionado en data/muestra_pedestal.npz permite ejecutar
todo el modulo sin descargar nada (guia Fase 4, cap. 5.1). El conjunto
completo, si hace falta, se trae con scripts/descargar_datos.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .types import Senal


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


def senal_de_prueba(
    n: int = 2**20, fs: float = 40_000.0, semilla: int = 42
) -> tuple[Senal, float]:
    """Genera una senal sintetica con composicion conocida, para tests
    y para el desarrollo en paralelo mientras 4.2 trae los datos reales.

    Mezcla ruido blanco gaussiano, ruido 1/f, una interferencia senoidal
    de 50 Hz y ruido de disparo (Poisson), sobre un pedestal de 1000
    cuentas. Ver guia Fase 4, cap. 6.1.

    Returns:
        (senal, fs).
    """
    raise NotImplementedError
