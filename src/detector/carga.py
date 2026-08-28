"""src/detector/carga.py - lectura de la senal de ruido de detector.

El subconjunto versionado en data/muestra_pedestal.npz permite ejecutar
todo el modulo sin descargar nada (guia Fase 4, cap. 5.1). El conjunto
completo, si hace falta, se trae con scripts/descargar_datos.py.
"""

from __future__ import annotations

from pathlib import Path

from .types import Senal


def cargar_muestra(
    ruta: Path | str = "data/muestra_pedestal.npz",
) -> tuple[Senal, float]:
    """Carga el subconjunto versionado de la senal de ruido.

    Args:
        ruta: fichero .npz con el array de la senal y la frecuencia de
            muestreo. Por defecto, el subconjunto del repositorio.

    Returns:
        (senal, fs): la senal en cuentas ADC (int32) y la frecuencia de
        muestreo en Hz.

    Raises:
        FileNotFoundError: con un mensaje que dice como obtener los
            datos, no solo que faltan.
    """
    raise NotImplementedError


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
