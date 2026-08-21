"""src/chaos/testimg.py - imagen de prueba generada de forma determinista.

No se versiona ningun binario: la imagen se genera por codigo con semilla
fija, lo que hace reproducibles NPCR y UACI (guia Fase 3, cap. 1.2).
"""

from __future__ import annotations

import numpy as np

from .types import Imagen

# Valor del cuadrante plano. NO es 128 a proposito: un plano centrado en la
# media global no aporta nada a la correlacion entre pixeles adyacentes
# (su covarianza dentro de la region es cero y su distancia a la media
# tambien), y la comprobacion de cordura "correlacion horizontal > 0.9" se
# quedaria en ~0.72. Con el plano lejos de la media, la region aporta
# (valor - media)^2 al numerador de Pearson, que es justo lo que hace que
# una zona plana dispare la correlacion en una imagen natural.
_VALOR_PLANO = 40

# Ancho de las bandas de la region de bordes duros. Cada borde 0 <-> 255 es
# un par adyacente ANTIcorrelacionado, asi que la banda tiene que ser ancha
# comparada con 1: con bandas de 32 columnas solo 1 de cada 32 pares
# horizontales cae sobre un borde.
_ANCHO_BANDA = 32

# Lado del bloque de la region de textura. La textura de una imagen real
# esta correlacionada a corta distancia; ruido blanco puro no lo esta y
# bajaria la correlacion de partida justo en la metrica estrella del
# modulo. Replicar cada valor sorteado en un bloque de 8x8 da una textura
# con estructura local, que es lo que hay que ver desaparecer al cifrar.
# Medido sobre 256x256: H 0.954, V 0.977, D 0.934, entropia 5.45, que cae
# dentro de los rangos que la guia da para una imagen natural (cap. 6.2)
# y cumple la comprobacion de cordura (corr > 0.9, entropia < 7.5).
_LADO_BLOQUE = 8


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

    Reparto por cuadrantes (con alto//2 y ancho//2 como corte, de modo que
    formas impares, degeneradas o no cuadradas simplemente dejan cuadrantes
    vacios en vez de reventar):

        +----------------+----------------+
        | plano          | degradado      |
        +----------------+----------------+
        | bordes duros   | textura        |
        +----------------+----------------+

    Args:
        alto: filas de la imagen.
        ancho: columnas de la imagen.
        semilla: para la region de textura. Reproducible entre ejecuciones.

    Returns:
        Imagen uint8 de forma (alto, ancho).
    """
    if alto < 1 or ancho < 1:
        raise ValueError(f"la imagen necesita alto y ancho >= 1, dados {alto}x{ancho}")

    img = np.zeros((alto, ancho), dtype=np.uint8)
    mitad_alto = alto // 2
    mitad_ancho = ancho // 2

    # 1. Cuadrante plano: correlacion adyacente 1.0 dentro de la region.
    img[:mitad_alto, :mitad_ancho] = _VALOR_PLANO

    # 2. Degradado suave horizontal: histograma NO uniforme y correlacion
    #    alta. Se recorre 0..255 a lo largo de las columnas del cuadrante.
    columnas_grad = ancho - mitad_ancho
    if mitad_alto > 0 and columnas_grad > 0:
        if columnas_grad == 1:
            rampa = np.zeros(1, dtype=np.float64)
        else:
            rampa = np.arange(columnas_grad, dtype=np.float64) * (
                255.0 / (columnas_grad - 1)
            )
        img[:mitad_alto, mitad_ancho:] = rampa.astype(np.uint8)

    # 3. Bordes duros: bandas verticales alternas 0 / 255. Alta frecuencia
    #    espacial, que es lo que hace que un cifrado por permutacion sola
    #    siga siendo reconocible.
    filas_bajas = alto - mitad_alto
    if filas_bajas > 0 and mitad_ancho > 0:
        indices = np.arange(mitad_ancho)
        bandas = np.where((indices // _ANCHO_BANDA) % 2 == 0, 0, 255).astype(np.uint8)
        img[mitad_alto:, :mitad_ancho] = bandas

    # 4. Textura pseudoaleatoria SEMBRADA, en bloques de _LADO_BLOQUE.
    columnas_text = ancho - mitad_ancho
    if filas_bajas > 0 and columnas_text > 0:
        rng = np.random.default_rng(semilla)
        bloques_alto = (filas_bajas + _LADO_BLOQUE - 1) // _LADO_BLOQUE
        bloques_ancho = (columnas_text + _LADO_BLOQUE - 1) // _LADO_BLOQUE
        grano = rng.integers(0, 256, size=(bloques_alto, bloques_ancho), dtype=np.uint8)
        textura = np.repeat(
            np.repeat(grano, _LADO_BLOQUE, axis=0), _LADO_BLOQUE, axis=1
        )
        img[mitad_alto:, mitad_ancho:] = textura[:filas_bajas, :columnas_text]

    return img
