"""src/chaos/metrics.py - metricas de calidad del cifrado.

Cada valor esperado se deriva en su propio docstring, nunca se copia de
un articulo (guia Fase 3, cap. 6). Esa derivacion es criterio de revision
de PR: un numero sin derivacion se devuelve.

Lo que estas cinco metricas SI dicen y lo que NO: detectan defectos
groseros -un histograma sesgado, una permutacion que no permuta, una
difusion que no propaga- y nada mas. Que un esquema las pase significa
que no tiene errores obvios, no que sea seguro. La tarea 3.8 lo hace
visible pasandoselas tambien a AES-256-GCM y a un flujo trivial: las tres
columnas salen iguales (cap. 6.6).
"""

from __future__ import annotations

import numpy as np

from .keystream import histograma_chi2
from .types import Imagen, MetricasImagen

# Las tres direcciones en que se mide la correlacion entre pixeles
# adyacentes. Son tres y no una porque un cifrado puede romper la
# correlacion horizontal y dejar intacta la vertical (por ejemplo, uno
# que permutase solo dentro de cada fila).
DIRECCIONES = ("horizontal", "vertical", "diagonal")


def entropia_esperada(n_pixeles: int, k: int = 256) -> float:
    """Valor esperado del estimador de entropia de Shannon (sesgo de
    Miller-Madow): H - (K-1)/(2*N*ln 2). Ver guia Fase 3, cap. 6.1.

    Un test que exija H > 7.999 para 256x256 falla siempre: el valor
    esperado real es 7.99719, no 8.0.

    La derivacion: la entropia se estima a partir de FRECUENCIAS
    MUESTRALES, no de probabilidades verdaderas, y el estimador de maxima
    verosimilitud tiene un sesgo negativo conocido de (K-1)/(2 N ln 2).
    Con K = 256 y N = 65536 pixeles:

        8 - 255 / (2 * 65536 * 0.6931) = 8 - 0.00281 = 7.99719

    Es decir: el techo teorico (8.0) y el techo alcanzable (7.99719) no
    son el mismo numero, y comparar contra el primero hace fallar siempre
    a un cifrado perfecto.

    Args:
        n_pixeles: N, el numero de muestras del histograma.
        k: K, el numero de valores posibles. 256 para 8 bits.

    Returns:
        El valor esperado de la entropia estimada, en bits/pixel.
    """
    if n_pixeles < 1:
        raise ValueError("hace falta al menos 1 pixel para estimar la entropia")
    return float(np.log2(k) - (k - 1) / (2.0 * n_pixeles * np.log(2.0)))


def entropia_shannon(img: Imagen) -> float:
    """Entropia de Shannon del histograma de 256 valores, en bits/pixel.

    H = -sum(p_i * log2 p_i), con p_i la frecuencia relativa del valor i.
    El maximo se alcanza con la distribucion uniforme y vale log2(256) = 8
    bits/pixel; una imagen natural tipica da entre 7.2 y 7.6.

    Los terminos con p_i = 0 se excluyen de la suma en vez de calcularse:
    log2(0) es -inf y 0 * (-inf) es NaN, no 0.

    minlength=256 no es opcional en el bincount: sin el, los valores que
    no aparecen en la imagen desaparecen del histograma, la longitud del
    array cambia y el chi2 posterior falla por forma (guia Fase 3, ap. B).
    """
    h = np.bincount(np.ascontiguousarray(img).ravel(), minlength=256).astype(np.float64)
    p = h / h.sum()
    positivos = p > 0.0
    return float(-np.sum(p[positivos] * np.log2(p[positivos])))


def correlacion_adyacente(
    img: Imagen, direccion: str = "horizontal", n_muestras: int = 5000
) -> float:
    """Coeficiente de Pearson entre pixeles adyacentes.

    Args:
        direccion: "horizontal", "vertical" o "diagonal".
        n_muestras: pares a muestrear. La tolerancia de 4*sigma se deriva
            de este numero como 1/sqrt(n_muestras) (ver guia Fase 3, cap. 6.2).

    Returns:
        El coeficiente en [-1, 1], o NaN si no es medible (menos de dos
        pares, o una de las dos series constante: en ese caso la varianza
        es cero y Pearson no esta definido). Se devuelve NaN y no 0.0 a
        proposito: un 0.0 se leeria en la tabla como "correlacion nula",
        que es justo lo que el cifrado quiere demostrar, y seria mentira.

    Por que se SUBMUESTREA y no se usan todos los pares: la tolerancia
    publicada, sigma_r = 1/sqrt(n), supone pares INDEPENDIENTES. Todos los
    pares adyacentes de una fila se solapan entre si (el pixel i aparece
    en el par (i-1,i) y en el (i,i+1)), asi que usarlos todos daria una
    n efectiva menor que la nominal y una tolerancia demasiado estrecha.
    Tomando uno de cada `paso` pares, con paso >= 2, los pares del
    muestreo no comparten pixeles.

    El muestreo es por PASO FIJO y no aleatorio: asi no hace falta un
    np.random.Generator sembrado, la medida es reproducible sin discutir
    semillas, y los pares quedan repartidos por toda la imagen en vez de
    concentrados donde caiga el sorteo.
    """
    if direccion == "horizontal":
        a, b = img[:, :-1], img[:, 1:]
    elif direccion == "vertical":
        a, b = img[:-1, :], img[1:, :]
    elif direccion == "diagonal":
        a, b = img[:-1, :-1], img[1:, 1:]
    else:
        raise ValueError(
            f"direccion {direccion!r} desconocida: se esperaba una de "
            f"{list(DIRECCIONES)}"
        )

    x = a.ravel().astype(np.float64)
    y = b.ravel().astype(np.float64)
    if x.size < 2:
        return float("nan")

    if 0 < n_muestras < x.size:
        paso = x.size // n_muestras
        indices = np.arange(n_muestras, dtype=np.int64) * paso
        x, y = x[indices], y[indices]

    if x.std() == 0.0 or y.std() == 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def npcr_esperado() -> float:
    """(1 - 1/256) * 100 = 99.6094%. Derivado, no copiado (cap. 6.3).

    Si los dos cifrados fueran independientes y uniformes, cada pixel
    coincidiria con probabilidad 1/256, luego cambiaria con probabilidad
    255/256.

    OJO: no es "cuanto mas alto mejor". Un 100% seria PEOR, no mejor:
    significaria que NINGUN pixel coincide, lo cual es estadisticamente
    imposible entre dos secuencias uniformes independientes y delataria
    una estructura. El objetivo es exactamente 99.6094%, con su intervalo.

    El intervalo se deriva de la binomial: sigma = sqrt(p(1-p)/M). Para
    M = 65536 pixeles, sigma = sqrt(0.9961*0.0039/65536) = 2.44e-4, o sea
    0.0244 puntos porcentuales, y 4 sigma dan [99.512%, 99.707%].
    """
    return (1.0 - 1.0 / 256.0) * 100.0


def uaci_esperado() -> float:
    """255*257/(3*256) / 255 * 100 = 33.4635%. Derivado (cap. 6.3).

    La cuenta completa, que casi todos los articulos citan y casi ninguno
    deriva: para X, Y uniformes e independientes en {0..255},

        E|X - Y| = (1/256^2) * sum_i sum_j |i - j| = 255*257/(3*256) = 85.33

    y UACI = 85.33 / 255 * 100 = 33.4635%.
    """
    return (255.0 * 257.0 / (3.0 * 256.0)) / 255.0 * 100.0


def _misma_forma(c1: Imagen, c2: Imagen) -> None:
    """Guarda comun de NPCR y UACI: comparar dos formas distintas no es
    una metrica, es un bug."""
    if c1.shape != c2.shape:
        raise ValueError(
            f"las dos imagenes deben tener la misma forma y son "
            f"{c1.shape} y {c2.shape}"
        )
    if c1.size == 0:
        raise ValueError("no hay nada que comparar: imagenes vacias")


def calcular_npcr(c1: Imagen, c2: Imagen) -> float:
    """Number of Pixels Change Rate entre dos cifrados, en porcentaje.

    NPCR = (1/M) * sum(C1(i) != C2(i)) * 100. Se compara con
    npcr_esperado() = 99.6094%, no con el 100%.

    Los dos argumentos son dos CIFRADOS, no un plano y un cifrado: la
    metrica mide la sensibilidad del cifrado a un cambio minimo en la
    entrada, asi que C1 y C2 salen de cifrar dos imagenes que difieren en
    UN SOLO pixel (o de cifrar la misma con dos claves que difieren en un
    bit, que es el test de sensibilidad a la clave del cap. 6.5).
    """
    _misma_forma(c1, c2)
    distintos = int(np.count_nonzero(c1 != c2))
    return 100.0 * distintos / c1.size


def calcular_uaci(c1: Imagen, c2: Imagen) -> float:
    """Unified Average Changing Intensity entre dos cifrados, en porcentaje.

    UACI = (1/M) * sum(|C1(i) - C2(i)|) / 255 * 100. Se compara con
    uaci_esperado() = 33.4635%.

    La resta se hace en int16 y no en uint8 a proposito: en uint8,
    250 - 10 = 240 pero 10 - 250 = 16, no -240. Restar dos uint8 sin
    ampliar el tipo da diferencias envueltas y una UACI silenciosamente
    equivocada (guia Fase 3, ap. B).
    """
    _misma_forma(c1, c2)
    diferencia = np.abs(c1.astype(np.int16) - c2.astype(np.int16))
    return float(diferencia.mean()) / 255.0 * 100.0


def chi2_histograma(img: Imagen) -> float:
    """Estadistico chi-cuadrado del histograma contra la uniforme.

    255 grados de libertad. Es un test de DOS COLAS: un valor
    sospechosamente bajo tambien es señal de alarma (cap. 6.4).

    chi2 = sum((o_i - e_i)^2 / e_i) con e_i = M/256. Bajo la hipotesis de
    uniformidad sigue una chi-cuadrado con 255 grados de libertad, cuya
    media es 255 y cuyo valor critico al 5% es 293.25.

    El error de interpretacion mas comun del campo es escribir "chi2 =
    251.3, luego el cifrado es seguro": eso confunde NO RECHAZAR la
    hipotesis nula con ACEPTARLA. Lo unico que dice un chi2 por debajo del
    critico es que no hay evidencia de desviacion de la uniformidad con
    esa muestra. Y un chi2 muy por debajo de 255 (digamos, menos de 200)
    es tambien sospechoso: un histograma demasiado uniforme para ser
    aleatorio indica que algo lo esta forzando.

    Comparte implementacion con keystream.histograma_chi2 en vez de
    repetir la formula: el mismo estadistico calculado dos veces en dos
    ficheros es el mismo estadistico hasta que uno de los dos se toca.
    Aqui solo se aplana la imagen, porque np.bincount exige un array de
    una sola dimension.
    """
    return histograma_chi2(np.ascontiguousarray(img).ravel())


def medir_imagen(etiqueta: str, plano: Imagen, cifrada: Imagen) -> MetricasImagen:
    """Calcula todas las metricas de una vez y las empaqueta.

    Devuelve una fila de la tabla comparativa del cap. 6.6: las metricas
    se miden sobre la imagen CIFRADA, que es la que tiene que parecer
    ruido. `plano` esta para dejar constancia de contra que original se
    ha medido y para comprobar que las dos formas coinciden.

    npcr y uaci se quedan a None a proposito, y esto es una decision, no
    un hueco: NPCR y UACI comparan DOS CIFRADOS de imagenes que difieren
    en un solo pixel, no un plano con su cifrado. Rellenarlos aqui con
    calcular_npcr(plano, cifrada) daria un numero de aspecto correcto
    (~99.6%) que no mide sensibilidad diferencial ninguna: mediria
    simplemente que el cifrado no se parece al original, que es lo minimo
    exigible. Quien tenga los dos cifrados los anade con
    dataclasses.replace sobre el resultado de esta funcion.

    Args:
        etiqueta: nombre de la fila ("caotico", "AES-256-GCM", "contador").
        plano: la imagen original.
        cifrada: su cifrado, misma forma.

    Returns:
        MetricasImagen con entropia (y su valor esperado corregido por
        sesgo), las tres correlaciones, y el chi2.
    """
    if plano.shape != cifrada.shape:
        raise ValueError(
            f"el plano {plano.shape} y el cifrado {cifrada.shape} no tienen "
            f"la misma forma: no son la misma imagen"
        )
    return MetricasImagen(
        etiqueta=etiqueta,
        entropia=entropia_shannon(cifrada),
        entropia_esperada=entropia_esperada(cifrada.size),
        corr_horizontal=correlacion_adyacente(cifrada, "horizontal"),
        corr_vertical=correlacion_adyacente(cifrada, "vertical"),
        corr_diagonal=correlacion_adyacente(cifrada, "diagonal"),
        chi2=chi2_histograma(cifrada),
        npcr=None,
        uaci=None,
    )
