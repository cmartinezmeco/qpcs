"""tests/chaos/tolerancias.py - las tolerancias de los tests, DERIVADAS.

Regla heredada de la Fase 1 y repetida en cada fase desde entonces: todo
umbral estadistico se escribe con su sigma calculada. Un
assert abs(x - 0.996) < 0.01 sin justificacion se devuelve en revision.

Este fichero existe para que esas sigmas se escriban UNA vez y no una por
cada fichero de test: cinco copias de la misma formula son cinco formulas
distintas en cuanto alguien toca una. No es un fichero de tests (no
empieza por test_ y pytest no lo recoge), es la hoja de calculo del
modulo.

Todas las funciones devuelven una sigma, no un umbral: el umbral es
4 * sigma en el punto donde se usa, para que en el test se vea el 4.
"""

from __future__ import annotations

import numpy as np

# Valor critico al 5% de una chi-cuadrado con 255 grados de libertad, y su
# media. El test es de DOS COLAS: un chi2 muy por debajo de la media es
# tan sospechoso como uno por encima del critico.
CHI2_CRITICO_5PCT = 293.25
CHI2_MEDIA = 255.0


def sigma_entropia(n_pixeles: int, k: int = 256) -> float:
    """Desviacion tipica del estimador de entropia para una fuente uniforme.

    El termino dominante de la varianza del estimador de maxima
    verosimilitud, (sum p_i log^2 p_i - H^2) / N, se ANULA exactamente
    cuando la fuente es uniforme (todos los log p_i valen lo mismo, asi
    que el segundo momento es el cuadrado del primero). Lo que queda es el
    termino siguiente, (K-1) / (2 N^2) en nats^2, que pasado a bits^2 se
    divide por (ln 2)^2:

        sigma_H = sqrt((K-1)/2) / (N * ln 2)

    Para K=256 y N=65536: sqrt(127.5) / (65536 * 0.6931) = 2.49e-4 bits.

    Comprobado contra 300 imagenes uniformes de 256x256 sembradas:
    sigma medida 2.55e-4 frente a 2.49e-4 derivada (3% de diferencia, que
    es lo que cabe esperar de quedarse en el primer termino no nulo).
    """
    return float(np.sqrt((k - 1) / 2.0) / (n_pixeles * np.log(2.0)))


def sigma_npcr(n_pixeles: int) -> float:
    """Sigma de NPCR en puntos porcentuales.

    NPCR es la media de n_pixeles Bernoullis con p = 255/256, asi que
    sigma = sqrt(p(1-p)/M) * 100. Para M = 65536:

        sqrt(0.99609 * 0.00391 / 65536) * 100 = 0.0244 puntos

    y un criterio de 4 sigma da el intervalo [99.512%, 99.707%], aqui
    derivado y no copiado de ningun sitio.
    """
    p = 255.0 / 256.0
    return float(np.sqrt(p * (1.0 - p) / n_pixeles) * 100.0)


def sigma_uaci(n_pixeles: int) -> float:
    """Sigma de UACI en puntos porcentuales.

    UACI es la media de M variables |X - Y| (X, Y uniformes e
    independientes en {0..255}) reescalada por 100/255. Su varianza:

        E[(X-Y)^2] = 2 Var(X) = 2 * (256^2 - 1)/12 = 10922.5
        E|X-Y|     = 255*257/(3*256) = 85.33203125
        Var|X-Y|   = 10922.5 - 85.33203125^2 = 3641.3
        sigma_UACI = sqrt(Var|X-Y| / M) / 255 * 100

    Para M = 65536 da 0.0924 puntos. Comprobado contra 300 pares de
    imagenes uniformes sembradas: sigma medida 0.0897.
    """
    esperanza_abs = 255.0 * 257.0 / (3.0 * 256.0)
    varianza_abs = 2.0 * (256.0**2 - 1.0) / 12.0 - esperanza_abs**2
    return float(np.sqrt(varianza_abs / n_pixeles) / 255.0 * 100.0)


def sigma_correlacion(n_muestras: int) -> float:
    """Sigma del coeficiente de Pearson muestral entre variables no
    correlacionadas: se distribuye aproximadamente como N(0, 1/sqrt(n)).

    Con n = 5000 pares, sigma = 0.0141 y un umbral de 4 sigma da
    |r| < 0.057. No un 0.05 redondo.
    """
    return float(1.0 / np.sqrt(n_muestras))


def sigma_chi2(grados_libertad: int = 255) -> float:
    """Sigma de una chi-cuadrado: sqrt(2 * grados de libertad).

    Con 255 grados de libertad, media 255 y sigma 22.58.
    """
    return float(np.sqrt(2.0 * grados_libertad))
