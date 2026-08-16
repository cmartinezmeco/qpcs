"""src/chaos/metrics.py - metricas de calidad del cifrado.

Cada valor esperado se deriva en su propio docstring, nunca se copia de
un articulo (guia Fase 3, cap. 6). Esa derivacion es criterio de revision
de PR: un numero sin derivacion se devuelve.
"""

from __future__ import annotations

from .types import Imagen, MetricasImagen


def entropia_esperada(n_pixeles: int, k: int = 256) -> float:
    """Valor esperado del estimador de entropia de Shannon (sesgo de
    Miller-Madow): H - (K-1)/(2*N*ln 2). Ver guia Fase 3, cap. 6.1.

    Un test que exija H > 7.999 para 256x256 falla siempre: el valor
    esperado real es 7.99719, no 8.0.
    """
    raise NotImplementedError


def entropia_shannon(img: Imagen) -> float:
    """Entropia de Shannon del histograma de 256 valores, en bits/pixel."""
    raise NotImplementedError


def correlacion_adyacente(
    img: Imagen, direccion: str = "horizontal", n_muestras: int = 5000
) -> float:
    """Coeficiente de Pearson entre pixeles adyacentes.

    Args:
        direccion: "horizontal", "vertical" o "diagonal".
        n_muestras: pares a muestrear. La tolerancia de 4*sigma se deriva
            de este numero como 1/sqrt(n_muestras) (ver guia Fase 3, cap. 6.2).
    """
    raise NotImplementedError


def npcr_esperado() -> float:
    """(1 - 1/256) * 100 = 99.6094%. Derivado, no copiado (cap. 6.3)."""
    raise NotImplementedError


def uaci_esperado() -> float:
    """255*257/(3*256) / 255 * 100 = 33.4635%. Derivado (cap. 6.3)."""
    raise NotImplementedError


def calcular_npcr(c1: Imagen, c2: Imagen) -> float:
    """Number of Pixels Change Rate entre dos cifrados, en porcentaje."""
    raise NotImplementedError


def calcular_uaci(c1: Imagen, c2: Imagen) -> float:
    """Unified Average Changing Intensity entre dos cifrados, en porcentaje."""
    raise NotImplementedError


def chi2_histograma(img: Imagen) -> float:
    """Estadistico chi-cuadrado del histograma contra la uniforme.

    255 grados de libertad. Es un test de DOS COLAS: un valor
    sospechosamente bajo tambien es señal de alarma (cap. 6.4).
    """
    raise NotImplementedError


def medir_imagen(etiqueta: str, plano: Imagen, cifrada: Imagen) -> MetricasImagen:
    """Calcula todas las metricas de una vez y las empaqueta."""
    raise NotImplementedError
