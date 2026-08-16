"""src/chaos/testimg.py - imagen de prueba generada de forma determinista.

No se versiona ningun binario: la imagen se genera por codigo con semilla
fija, lo que hace reproducibles NPCR y UACI (guia Fase 3, cap. 1.2).
"""

from __future__ import annotations

from .types import Imagen


def imagen_de_prueba(alto: int = 256, ancho: int = 256, semilla: int = 42) -> Imagen:
    """Imagen sintetica determinista con las estructuras que las metricas
    necesitan ver desaparecer tras cifrar:
      - un cuadrante plano (correlacion adyacente ~ 0.99)
      - un degradado suave (histograma no uniforme)
      - bordes duros (alta frecuencia)
      - una region de textura pseudoaleatoria SEMBRADA

    Sin estas estructuras, un cifrado que no hiciera nada podria pasar
    las metricas por casualidad: una imagen de ruido puro ya tiene
    correlacion y entropia cercanas a las de un buen cifrado.

    Args:
        alto: filas de la imagen.
        ancho: columnas de la imagen.
        semilla: para la region de textura. Reproducible entre ejecuciones.

    Returns:
        Imagen uint8 de forma (alto, ancho).
    """
    raise NotImplementedError
