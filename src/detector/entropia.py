"""src/detector/entropia.py - estimadores de min-entropia (NIST SP 800-90B).

La min-entropia H_inf = -log2(max_i p_i) mide el caso peor, no la media
(que es lo que mide Shannon). Es la que vale en criptografia: lo que
importa no es cuanto tendria que adivinar un atacante de media, sino
cuanto acierta con su mejor estrategia.

Se implementan tres estimadores y se toma el MINIMO, que es la regla de
SP 800-90B: cada estimador es ciego a cierto tipo de estructura, y el que
da el valor mas bajo es el que ha encontrado la que los demas no vieron.
Mismo espiritu que la postura paranoica del modulo 1 con el QBER.

UNA ACLARACION DE UNIDADES, QUE ES DONDE MAS FACIL ES EQUIVOCARSE
------------------------------------------------------------------
Los tres estimadores devuelven bits de entropia POR SIMBOLO, no por bit:
un simbolo aqui es una muestra digitalizada de BITS_BAJOS bits, asi que su
maximo es BITS_BAJOS (4 con el contrato), no 1. La formula de la tarea 4.7
esta escrita con la min-entropia por BIT, y la conversion es la identidad
n_bits * H_por_bit = n_simbolos * H_por_simbolo, que extraccion.py hace
explicita y documenta.

DONDE ESTE MODULO SE APARTA DEL ESTANDAR, DICHO SIN SUAVIZAR
-------------------------------------------------------------
SP 800-90B enuncia el estimador de colision (6.3.2) y el de Markov (6.3.3)
SOLO para fuentes binarias, y para alfabetos mayores manda aplicarlos
sobre una version binarizada de los datos. Aqui estan generalizados al
alfabeto de k simbolos que produce digitalizar(); con k = 2 se reducen
exactamente a lo que dice el estandar (hay un test que lo comprueba para
el de colision: con k = 2 el tiempo medio de colision vale 3 - p^2 - q^2,
que es la expresion binaria del estandar).

El motivo de generalizar en vez de binarizar: el estimador que importa
aqui es el de Markov, y lo que tiene que
cazar es la correlacion entre MUESTRAS consecutivas que deja el 1/f
residual. Binarizar primero reparte esa correlacion entre los bits de cada
muestra, y una cadena de Markov de orden 1 sobre bits ya no la ve.

Y una tercera cosa que hay que decir aqui y repetir en las limitaciones
(tarea 4.12): SP 800-90B define diez estimadores y pide del orden de 10^6
muestras para una evaluacion completa. Esto son tres estimadores sobre
una muestra, no una certificacion.
"""

from __future__ import annotations

import math

import numpy as np
import numpy.typing as npt
from scipy import stats

from .types import (
    ALFA_SP80090B,
    MUESTRAS_POR_CELDA,
    Bits,
    Espectro,
    EstimacionEntropia,
)

# Longitud de la secuencia sobre la que SP 800-90B (6.3.3) busca el camino
# mas probable de la cadena de Markov. La fija el estandar en 128 y no es un
# parametro de analisis elegible, por eso no vive en types.py.
_LONGITUD_CADENA_MARKOV = 128


def _cuantil_normal(alfa: float) -> float:
    """Cuantil 1 - alfa/2 de la normal estandar.

    Con alfa = 0.01 da 2.576, que es la constante que SP 800-90B escribe
    literalmente en 6.3.1. Se calcula en vez de copiarse para que el
    parametro `alfa` de h_min_mas_comun signifique algo de verdad.
    """
    if not 0.0 < alfa < 1.0:
        raise ValueError(f"alfa debe estar en (0, 1), recibido {alfa}")
    return float(stats.norm.ppf(1.0 - alfa / 2.0))


def _validar_simbolos(simbolos: Bits) -> npt.NDArray[np.int64]:
    """Comprobaciones comunes a los tres estimadores.

    Devuelve los simbolos como enteros con signo, que es lo que necesitan
    los bincount y los indices de la matriz de transicion.
    """
    datos = np.asarray(simbolos)
    if datos.ndim != 1:
        raise ValueError(f"los simbolos deben ser 1-D, recibido {datos.shape}")
    if datos.size < 2:
        raise ValueError(
            f"hacen falta al menos 2 simbolos para estimar nada, "
            f"recibidos {datos.size}"
        )
    if np.any(datos < 0):
        raise ValueError("los simbolos deben ser enteros no negativos")
    return np.asarray(datos, dtype=np.int64)


def digitalizar(senal_filtrada: Espectro, n_bits: int) -> Bits:
    """Se queda con los n_bits de orden BAJO de cada muestra.

    Mismo motivo que la cuantizacion del modulo 3: los bits de orden
    alto llevan la forma de la distribucion (aqui, la
    campana gaussiana y lo que quede de deriva); los de orden bajo son,
    a efectos practicos, uniformes.

    OJO: quedarse con n_bits NO significa que haya n_bits de entropia por
    muestra. Eso lo dice estimar_entropia() de aqui abajo, y casi siempre
    da bastante menos.

    La senal filtrada es float64 y esta centrada en cero, asi que hay
    muestras negativas: se redondea al entero mas cercano y se toman los
    n_bits bajos de su complemento a dos (-3 -> 13 con n_bits = 4). No es
    un caso aparte: los bits bajos del complemento a dos son exactamente
    los del valor modulo 2^n_bits.

    Args:
        senal_filtrada: salida de filtrado.filtrar (float64, finita).
        n_bits: cuantos bits bajos conservar. Entre 1 y 8, porque la salida
            es uint8 (ver Bits en types.py).

    Returns:
        Un simbolo por muestra, con valores en [0, 2^n_bits).

    Raises:
        ValueError: si n_bits esta fuera de [1, 8], o si la senal tiene
            valores no finitos (un NaN daria un simbolo absurdo al
            redondear, en silencio y sin error).
    """
    if not 1 <= n_bits <= 8:
        raise ValueError(f"n_bits debe estar entre 1 y 8 (uint8), recibido {n_bits}")
    datos = np.asarray(senal_filtrada, dtype=np.float64)
    if datos.size and not bool(np.all(np.isfinite(datos))):
        raise ValueError(
            "la senal tiene valores no finitos (NaN o inf): redondearlos "
            "produciria simbolos sin sentido en vez de un error"
        )
    enteros = np.rint(datos).astype(np.int64)
    mascara = (1 << n_bits) - 1
    return np.asarray(enteros & mascara, dtype=np.uint8)


def h_min_mas_comun(simbolos: Bits, alfa: float = ALFA_SP80090B) -> float:
    """Estimador del valor mas comun (SP 800-90B, 6.3.1).

    p_max estimado = frecuencia del simbolo mas repetido / n. Se toma la
    COTA SUPERIOR del intervalo de confianza al 99%:
        p_sup = p_max + 2.576 * sqrt(p_max*(1-p_max) / (n-1))
    y H = -log2(min(1, p_sup)).

    Se usa la cota superior, no p_max, porque sobreestimar p_max
    INFRAESTIMA la entropia: es el error conservador y seguro. Asume
    muestras independientes.

    Args:
        simbolos: la secuencia digitalizada.
        alfa: nivel de significacion de la cota. 0.01 (99% bilateral) es el
            del estandar, y su cuantil normal es el 2.576 de la formula.

    Returns:
        Bits de min-entropia POR SIMBOLO.
    """
    datos = _validar_simbolos(simbolos)
    n = int(datos.size)
    cuentas = np.bincount(datos)
    p_max = float(cuentas.max()) / n
    p_sup = min(
        1.0,
        p_max + _cuantil_normal(alfa) * math.sqrt(p_max * (1.0 - p_max) / (n - 1)),
    )
    # max(0.0, ...) para que una fuente constante devuelva 0.0 y no -0.0:
    # -log2(1.0) es cero negativo en coma flotante, y un -0.0 en la cifra
    # publicada solo sirve para que alguien se pregunte que significa.
    return float(max(0.0, -math.log2(p_sup)))


def _tiempos_de_colision(simbolos: npt.NDArray[np.int64]) -> npt.NDArray[np.int64]:
    """Longitudes de los tramos consecutivos hasta la primera repeticion.

    SP 800-90B (6.3.2) recorre la secuencia tomando muestras hasta que una
    se repite dentro del tramo, anota cuantas ha necesitado y vuelve a
    empezar en la siguiente. El tramo que queda a medias al final se
    descarta: su longitud no es un tiempo de colision, es donde se acabaron
    los datos.

    No hace falta recorrer la secuencia muestra a muestra. Si sig[i] es el
    indice de la siguiente aparicion del simbolo que hay en i, la primera
    colision a partir de la posicion s ocurre en J(s) = min_{i >= s} sig[i]:
    el minimo se alcanza en algun i >= s con sig[i] = J(s) >= i, luego las
    dos muestras del par caen dentro del tramo; y no puede haber colision
    antes, porque un par (a, b) con s <= a < b < J(s) exigiria
    sig[a] <= b < J(s). Ese minimo por sufijos es un minimum.accumulate
    sobre el array invertido, y despues solo queda un salto por tramo (del
    orden de n/5 con 16 simbolos).
    """
    n = int(simbolos.size)
    # sig[i]: siguiente indice con el mismo simbolo, o n si no lo hay.
    siguiente = np.full(n, n, dtype=np.int64)
    orden = np.argsort(simbolos, kind="stable")
    ordenados = simbolos[orden]
    mismo = ordenados[:-1] == ordenados[1:]
    siguiente[orden[:-1][mismo]] = orden[1:][mismo]
    primera_colision = np.minimum.accumulate(siguiente[::-1])[::-1]

    tiempos: list[int] = []
    inicio = 0
    while inicio < n:
        fin = int(primera_colision[inicio])
        if fin >= n:  # el ultimo tramo no llega a repetir: se descarta
            break
        tiempos.append(fin - inicio + 1)
        inicio = fin + 1
    return np.asarray(tiempos, dtype=np.int64)


def _tiempo_medio_de_colision(p: float, k: int) -> float:
    """Tiempo medio hasta la primera repeticion de una fuente casi uniforme.

    "Casi uniforme" es la familia con la que SP 800-90B resuelve el
    estimador de colision: un simbolo con probabilidad p y los otros k-1
    con q = (1-p)/(k-1). Con T = numero de muestras hasta la primera
    repeticion,

        E[T] = suma_{m=0}^{k} P(las m primeras son todas distintas)

    y, separando segun si el simbolo pesado esta entre esas m o no,

        P(m distintas) = perm(k-1, m) q^m + m p q^(m-1) perm(k-1, m-1)

    con perm(a, m) = a!/(a-m)!. Para k = 2 esto vale 2 + 2pq = 3 - p^2 - q^2,
    que es la expresion binaria del estandar.

    E[T] decrece con p (cuanto mas concentrada esta la fuente, antes se
    repite), y por eso se puede invertir por biseccion.
    """
    if k <= 1:
        return 2.0
    q = (1.0 - p) / (k - 1)
    esperado = 0.0
    perm_anterior = 1.0  # perm(k-1, m-1)
    for m in range(k + 1):
        perm = perm_anterior * (k - m) if m >= 1 else 1.0
        termino = perm * q**m
        if m >= 1:
            termino += m * p * q ** (m - 1) * perm_anterior
        esperado += termino
        perm_anterior = perm
    return esperado


def h_min_colision(simbolos: Bits) -> float:
    """Estimador de colision (SP 800-90B, 6.3.2).

    Se basa en cuantas muestras hay que tomar, de media, hasta encontrar
    una repeticion. Detecta sesgos que el estimador del valor mas comun
    no ve.

    Receta del estandar:
      1. Trocear la secuencia en tramos que terminan en la primera
         repeticion y quedarse con sus longitudes (_tiempos_de_colision).
      2. Tomar la cota INFERIOR al 99% de su media,
         X' = media - 2.576 * sigma / sqrt(v). Menos tiempo hasta la
         colision significa fuente mas concentrada, asi que la cota
         inferior de la media es la conservadora para la entropia.
      3. Invertir E[T](p) sobre la familia casi uniforme y devolver
         H = -log2(p).

    Como en el estandar, si la media medida es tan alta que ninguna
    p >= 1/k la reproduce, se toma p = 1/k (entropia maxima): no hay
    evidencia de concentracion.

    UN SESGO QUE HAY QUE CONOCER Y NO ESCONDER
    ------------------------------------------
    Cerca de la uniformidad este estimador es conservador POR
    CONSTRUCCION, no porque haya encontrado estructura: E[T] alcanza su
    maximo justo en p = 1/k, asi que su derivada ahi es cero y restarle la
    cota de confianza (un delta pequeno) mueve la p que la reproduce como
    sqrt(delta), no como delta. Con simbolos de 4 bits perfectamente
    uniformes y 2*10^5 muestras devuelve 3.38 bits en vez de 4, mientras
    que el del valor mas comun devuelve 3.95 y el de Markov 3.75.

    Como en esta fuente los simbolos salen casi uniformes, este suele ser
    el estimador que da el MINIMO, y conviene saber por que: el minimo se
    toma igual (es la regla de SP 800-90B y equivocarse por conservador
    solo cuesta bits), pero decir que "el de colision encontro estructura"
    seria falso. Donde si es exacto es en fuentes concentradas, que es
    donde importa: con una binaria de p_max = 0.9 devuelve 0.1493 frente
    al 0.1520 de la teoria, y hay un test que lo comprueba.

    Returns:
        Bits de min-entropia POR SIMBOLO.

    Raises:
        ValueError: si la secuencia no da al menos dos tiempos de colision,
            porque entonces no hay ni media ni error que estimar.
    """
    datos = _validar_simbolos(simbolos)
    k = int(np.unique(datos).size)
    if k <= 1:
        return 0.0  # fuente constante: no hay nada que destilar

    tiempos = _tiempos_de_colision(datos)
    v = int(tiempos.size)
    if v < 2:
        raise ValueError(
            f"solo {v} tiempo(s) de colision en {datos.size} muestras: no hay "
            f"con que estimar la media ni su error"
        )

    media = float(tiempos.mean())
    sigma = float(tiempos.std(ddof=1))
    media_inf = media - _cuantil_normal(ALFA_SP80090B) * sigma / math.sqrt(v)

    if media_inf >= _tiempo_medio_de_colision(1.0 / k, k):
        return float(math.log2(k))  # nada mas uniforme es posible
    if media_inf <= _tiempo_medio_de_colision(1.0, k):
        return 0.0

    bajo, alto = 1.0 / k, 1.0
    for _ in range(60):  # 60 bisecciones: precision muy por debajo de 1e-15
        medio = 0.5 * (bajo + alto)
        if _tiempo_medio_de_colision(medio, k) > media_inf:
            bajo = medio
        else:
            alto = medio
    return float(-math.log2(0.5 * (bajo + alto)))


def _cota_superior_de_p(
    p: npt.NDArray[np.float64], cuentas: npt.NDArray[np.float64], z: float
) -> npt.NDArray[np.float64]:
    """min(1, p + z sqrt(p(1-p)/(c-1))), la misma construccion normal que
    usa 6.3.1 para p_max.

    Con c <= 1 no hay con que acotar nada y se supone lo peor (p = 1), que
    es lo conservador: sobreestimar probabilidades infraestima la entropia.

    Consecuencia que conviene conocer: si un simbolo aparece una sola vez,
    su fila entera queda en 1 y la estimacion de Markov se va a cero. Es
    fail-safe -nunca sobreestima, solo hace tirar bits- y es otra razon
    para el minimo de muestras por celda que exige estimar_entropia. Con
    los 4 bits del contrato y datos reales no pasa: los 16 simbolos
    aparecen decenas de miles de veces.
    """
    margen = np.where(
        cuentas > 1.0,
        z * np.sqrt(p * (1.0 - p) / np.maximum(cuentas - 1.0, 1.0)),
        1.0,
    )
    return np.asarray(np.minimum(1.0, p + margen), dtype=np.float64)


def h_min_markov(simbolos: Bits) -> float:
    """Estimador de Markov (SP 800-90B, 6.3.3). EL IMPORTANTE aqui.

    No asume independencia: modela la fuente como cadena de Markov,
    estimando la matriz de transicion entre simbolos consecutivos. Es el
    unico de los tres que ve la correlacion que deja el 1/f residual tras
    el filtrado, y por eso suele ser el que da el minimo en esta fuente.

    Receta del estandar, generalizada de 2 a k simbolos (ver la cabecera
    del modulo):
      1. Frecuencias iniciales P_i y de transicion P_ij, cada una
         sustituida por su COTA SUPERIOR al 99% con la construccion normal
         de 6.3.1.
      2. Probabilidad del camino MAS probable de 128 pasos,
         p_max = max sobre secuencias de P_s1 * prod P_si,si+1, por
         programacion dinamica en log2 (128 factores de ~0.06 se irian a
         1e-155 multiplicados directamente).
      3. H = min(-log2(p_max)/128, log2(k)): la entropia por muestra, con
         el tope trivial del alfabeto que el estandar escribe como
         min(..., 1) para el caso binario.

    Returns:
        Bits de min-entropia POR SIMBOLO.
    """
    datos = _validar_simbolos(simbolos)
    _, inverso = np.unique(datos, return_inverse=True)
    indices = np.asarray(inverso, dtype=np.int64).ravel()
    k = int(indices.max()) + 1
    if k <= 1:
        return 0.0  # una sola cadena posible: p_max = 1
    n = int(indices.size)
    z = _cuantil_normal(ALFA_SP80090B)

    cuentas_inicial = np.bincount(indices, minlength=k).astype(np.float64)
    p_inicial = _cota_superior_de_p(
        cuentas_inicial / n, np.full(k, float(n), dtype=np.float64), z
    )

    transiciones = (
        np.bincount(indices[:-1] * k + indices[1:], minlength=k * k)
        .reshape(k, k)
        .astype(np.float64)
    )
    desde = transiciones.sum(axis=1)
    con_salida = desde > 0.0
    p_transicion = np.zeros((k, k), dtype=np.float64)
    if bool(np.any(con_salida)):
        p_transicion[con_salida] = _cota_superior_de_p(
            transiciones[con_salida] / desde[con_salida, None],
            np.repeat(desde[con_salida, None], k, axis=1),
            z,
        )

    with np.errstate(divide="ignore"):
        log_inicial = np.log2(p_inicial)
        log_transicion = np.log2(p_transicion)

    # Programacion dinamica: mejor[j] es el log2 de la probabilidad del
    # camino mas probable, de la longitud recorrida, que termina en j.
    mejor = log_inicial
    for _ in range(_LONGITUD_CADENA_MARKOV - 1):
        mejor = np.max(mejor[:, None] + log_transicion, axis=0)

    log_p_max = float(np.max(mejor))
    if not math.isfinite(log_p_max):
        # Rama defensiva: significaria que ningun camino de 128 pasos es
        # posible con las cuentas observadas. Con las cotas superiores de
        # arriba no deberia ocurrir (una fila sin datos se satura a 1 y el
        # camino sobrevive), pero si ocurriera no habria evidencia para
        # bajar del tope trivial del alfabeto, y devolver -inf o un cero
        # inventado seria peor que decirlo.
        return float(math.log2(k))
    # max(0.0, ...) por el mismo motivo que en h_min_mas_comun: -log2(1.0)
    # es -0.0 y esa cifra acaba publicada.
    return float(max(0.0, min(-log_p_max / _LONGITUD_CADENA_MARKOV, math.log2(k))))


def estimar_entropia(simbolos: Bits) -> EstimacionEntropia:
    """Aplica los tres estimadores y devuelve el MINIMO.

    No es "elegir el que mejor sale": es la regla de SP 800-90B.

    El minimo de muestras exigido esta DERIVADO, no elegido a ojo: la
    matriz de transicion del estimador de Markov tiene k^2 celdas con un
    alfabeto de k simbolos, y por debajo de MUESTRAS_POR_CELDA
    observaciones esperadas por celda las frecuencias no estiman nada
    (regla de Cochran, la misma que pide >= 5 cuentas esperadas por bin en
    un chi2). Con los 4 bits bajos del contrato, k = 16 y el minimo son
    5 * 256 = 1280 muestras.

    Args:
        simbolos: la secuencia digitalizada (salida de digitalizar).

    Returns:
        EstimacionEntropia con los tres estimadores, su minimo (que es el
        que se usa), el numero de muestras y el nivel de confianza.

    Raises:
        ValueError: si hay menos muestras de las que el alfabeto observado
            necesita, con el numero exacto en el mensaje.
    """
    datos = _validar_simbolos(simbolos)
    n = int(datos.size)
    k = int(np.unique(datos).size)
    minimo = MUESTRAS_POR_CELDA * k * k
    if n < minimo:
        raise ValueError(
            f"no se puede estimar min-entropia con {n} muestras y un alfabeto "
            f"de {k} simbolos: la matriz de transicion tiene {k * k} celdas y "
            f"hacen falta al menos {minimo} muestras ({MUESTRAS_POR_CELDA} por "
            f"celda)"
        )

    h_mas_comun = h_min_mas_comun(simbolos)
    h_colision = h_min_colision(simbolos)
    h_markov = h_min_markov(simbolos)
    return EstimacionEntropia(
        h_mas_comun=h_mas_comun,
        h_colision=h_colision,
        h_markov=h_markov,
        h_min=min(h_mas_comun, h_colision, h_markov),
        n_muestras=n,
        intervalo_confianza=1.0 - ALFA_SP80090B,
    )
