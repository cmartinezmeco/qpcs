"""src/detector/extraccion.py - destilar bits uniformes con Toeplitz.

Reutiliza qkd.privacy_amplify, el mismo extractor de la tarea 1.6. El
leftover hash lemma no sabe de donde viene la min-entropia, solo necesita
saber cuanta hay: por eso el mismo codigo sirve para destilar una clave
de BB84 y para destilar entropia de un detector (guia Fase 4, cap. 4.4).

ell = floor(n * H_min - 2 log2(1/eps))

Es la misma formula de la tarea 1.6 SIN el termino leak_ec: alli se
restaban los bits que Cascade publicaba por el canal, y aqui no hay canal
publico que filtre nada.

POR QUE NO SE LLAMA A qkd.secure_key_length
--------------------------------------------
Porque no calcula esta formula: la suya es ell = n(1 - h(Q)) - leak_ec -
2 log2(1/eps), con la entropia binaria de un QBER dentro. Para reutilizarla
habria que inventarse un QBER ficticio Q = h^-1(1 - H_min) y un leak_ec = 0,
es decir, mentir sobre el significado de los dos parametros para que la
aritmetica cuadrase. Lo que se reutiliza -y es lo que pide la guia- es
privacy_amplify, que es el extractor; el peaje del leftover hash lemma se
escribe aqui, en tres lineas, con su propio nombre.

LA CUENTA DE UNIDADES, QUE ES LA TRAMPA DE ESTA TAREA
------------------------------------------------------
Los estimadores de la 4.6 devuelven min-entropia por SIMBOLO (hasta 4 bits
con BITS_BAJOS = 4) y la formula de arriba esta escrita con la min-entropia
por BIT. Las dos son la misma cifra vista con distinta unidad:

    n_bits * H_por_bit = n_simbolos * H_por_simbolo

asi que ell no depende de en cual de las dos se piense. Se calcula con la
version por bit (que es como la escribe la guia) y se publica en
ResultadoExtraccion.h_min_por_bit, para que nadie confunda "4 bits
conservados por muestra" con "4 bits de entropia por muestra": el error
mas comun del campo (guia Fase 4, cap. 6.6).
"""

from __future__ import annotations

import math
import os

import numpy as np

# Se importa el MODULO, no la funcion suelta, y se llama
# qkd_privacy.privacy_amplify(...) mas abajo. Asi el test
# test_usa_el_extractor_del_modulo_1 puede parchear
# qkd.privacy.privacy_amplify y comprobar que el cambio se ve aqui, que es
# la unica forma de DEMOSTRAR que se reutiliza el extractor de la tarea 1.6
# y no una copia local con el mismo nombre.
from qkd import privacy as qkd_privacy

from .types import Bits, EstimacionEntropia, ResultadoExtraccion


def _bits_de_simbolos(simbolos: Bits) -> tuple[Bits, int]:
    """Despliega cada simbolo en sus bits, del menos al mas significativo.

    El ancho no se pasa como parametro: se toma el de los simbolos que hay
    de verdad (bit_length del maximo observado). Un bit que vale cero en
    TODAS las muestras no aporta ni un bit de entropia -es una constante-,
    asi que descartarlo no cambia la salida del extractor ni la longitud
    segura (que sale de n_simbolos * H_por_simbolo), y evita alargar la
    semilla de Toeplitz para nada. Con BITS_BAJOS = 4 y datos reales el
    ancho sale 4, que es lo esperado.

    Returns:
        (bits, ancho): los n * ancho bits y cuantos bits lleva un simbolo.
    """
    datos = np.asarray(simbolos, dtype=np.uint8)
    ancho = max(1, int(datos.max()).bit_length())
    desplazamientos = np.arange(ancho, dtype=np.uint8)
    bits = (datos[:, None] >> desplazamientos) & np.uint8(1)
    return np.asarray(bits, dtype=np.uint8).ravel(), ancho


def _longitud_segura(n_bits: int, h_min_por_bit: float, epsilon: float) -> int:
    """ell = floor(n * H_min - 2 log2(1/eps)), acotado por abajo en 0.

    El termino 2 log2(1/eps) es el peaje del leftover hash lemma: unos 60
    bits con eps = 1e-9, constante, ridiculo frente a un millon de bits de
    entrada, e imprescindible para poder decir "eps-seguro" con propiedad.
    Es literalmente el mismo peaje que paga la tarea 1.6.

    Devuelve 0 cuando la fuente no sostiene nada (H_min = 0, o tan poca
    entropia que no cubre ni el peaje): la extraccion tiene que quedarse
    sin bits, no inventarselos.
    """
    if not 0.0 < epsilon < 1.0:
        raise ValueError(f"epsilon debe estar en (0, 1), recibido {epsilon}")
    if h_min_por_bit < 0.0:
        raise ValueError(f"la min-entropia no puede ser negativa: {h_min_por_bit}")
    ell = n_bits * h_min_por_bit - 2.0 * math.log2(1.0 / epsilon)
    return max(0, int(math.floor(ell)))


def _semilla_urandom(n_bits: int) -> Bits:
    """n_bits de semilla del CSPRNG del sistema. NO se siembra, nunca.

    La semilla de Toeplitz tiene que ser independiente de la fuente: si
    saliera del propio ruido, el leftover hash lemma dejaria de aplicar
    (guia Fase 4, cap. 4.4.1). Por eso no hay parametro `semilla` en toda
    esta cadena, al reves que en la senal sintetica de los tests. Mismo
    criterio que las claves de ML-KEM de la fase 2.

    La semilla es PUBLICA: el lema vale aunque el atacante conozca la
    funcion hash. Lo que no puede conocer es la entrada.
    """
    if n_bits <= 0:
        return np.empty(0, dtype=np.uint8)
    crudo = np.frombuffer(os.urandom((n_bits + 7) // 8), dtype=np.uint8)
    return np.asarray(np.unpackbits(crudo)[:n_bits], dtype=np.uint8)


def _z_monobit(bits: Bits) -> float:
    """z = |2 sum(b) - n| / sqrt(n), el test monobit del modulo 1.

    Bajo la hipotesis de bits uniformes e independientes z ~ N(0,1), y el
    umbral del proyecto es |z| < 4 (probabilidad de fallo espurio 6e-5:
    laxo para que la CI no parpadee, estricto para pillar un sesgo real).

    Devuelve NaN si no hay bits, que es lo que pasa cuando H_min = 0: el
    estadistico no esta definido y un 0.0 se leeria como "perfecto".
    Mismo criterio que ReconciliationResult.efficiency en el modulo 1.
    """
    n = int(bits.size)
    if n == 0:
        return float("nan")
    return float(abs(2 * int(bits.sum()) - n) / math.sqrt(n))


def _chi2_de_bytes(bits: Bits) -> float:
    """Chi-cuadrado del histograma de los bytes que forman los bits.

    255 grados de libertad, media 255 y critico al 5% en 293.25. Es el
    MISMO estadistico que chaos.histograma_chi2 del modulo 3 (hay un test
    que comprueba que los dos dan el mismo numero sobre los mismos datos);
    no se importa de alli para no atar el modulo 4 al 3 por cuatro lineas
    de bincount, cuando lo unico que la guia manda reutilizar es el
    extractor del modulo 1.

    Se usan solo los bytes COMPLETOS: np.packbits rellenaria el ultimo con
    ceros y ese byte inventado sesgaria el histograma.

    Como en el modulo 3, la lectura es de DOS COLAS: un valor muy por
    encima de 293.25 delata sesgo, y uno sospechosamente bajo tambien es
    alarma. Y hace falta del orden de 1280 bytes para que el critico
    signifique algo (>= 5 cuentas esperadas por bin, regla de Cochran).
    Devuelve NaN si no hay ni un byte completo.
    """
    completos = (int(bits.size) // 8) * 8
    if completos == 0:
        return float("nan")
    octetos = np.packbits(np.asarray(bits[:completos], dtype=np.uint8))
    observado = np.bincount(octetos, minlength=256).astype(np.float64)
    esperado = octetos.size / 256.0
    return float(np.sum((observado - esperado) ** 2 / esperado))


def extraer(
    simbolos: Bits, estimacion: EstimacionEntropia, epsilon: float
) -> ResultadoExtraccion:
    """Comprime los simbolos digitalizados hasta la longitud que la
    min-entropia sostiene, con el extractor de Toeplitz del modulo 1.

    La semilla de Toeplitz se genera con os.urandom y NO se siembra: tiene
    que ser independiente de la fuente, o el leftover hash lemma deja de
    aplicar. Mismo criterio que las claves de ML-KEM en la fase 2.

    La cadena completa es: los simbolos se despliegan en bits, la longitud
    segura sale de ell = floor(n * H_min - 2 log2(1/eps)), y esos n bits se
    comprimen a ell con la matriz de Toeplitz de n + ell - 1 bits de
    semilla. Los dos estadisticos de validacion (monobit y chi2 de bytes)
    se calculan sobre la salida y viajan en el resultado: son condiciones
    NECESARIAS, no suficientes (guia Fase 4, cap. 4.5). Lo que garantiza
    que la salida sea buena es la estimacion conservadora de la 4.6 mas el
    leftover hash lemma, no que estos dos numeros salgan bonitos.

    Args:
        simbolos: los bits digitalizados (salida de entropia.digitalizar).
        estimacion: el resultado de entropia.estimar_entropia sobre esos
            mismos simbolos.
        epsilon: parametro de seguridad. El mismo 1e-9 que la tarea 1.6.

    Returns:
        ResultadoExtraccion con los bits finales y su validacion.

    Raises:
        ValueError: si los simbolos estan vacios o no son 1-D, o si la
            estimacion no es de ESTOS simbolos (n_muestras distinto). Lo
            segundo no es una formalidad: extraer con la min-entropia
            medida sobre otros datos es exactamente como se produce una
            salida que parece aleatoria y no lo es.
    """
    datos = np.asarray(simbolos, dtype=np.uint8)
    if datos.ndim != 1 or datos.size == 0:
        raise ValueError(f"se esperaba una secuencia 1-D no vacia, {datos.shape}")
    if estimacion.n_muestras != datos.size:
        raise ValueError(
            f"la estimacion es de {estimacion.n_muestras} muestras y aqui "
            f"vienen {datos.size}: la min-entropia tiene que estar medida "
            f"sobre estos mismos simbolos"
        )

    bits_fuente, ancho = _bits_de_simbolos(datos)
    n_entrada = int(bits_fuente.size)
    h_min_por_bit = estimacion.h_min / ancho
    ell = _longitud_segura(n_entrada, h_min_por_bit, epsilon)

    semilla = _semilla_urandom(n_entrada + ell - 1 if ell > 0 else 0)
    bits = qkd_privacy.privacy_amplify(bits_fuente, ell, semilla)

    return ResultadoExtraccion(
        bits=bits,
        n_entrada=n_entrada,
        h_min_por_bit=h_min_por_bit,
        longitud_segura=ell,
        z_monobit=_z_monobit(bits),
        chi2=_chi2_de_bytes(bits),
    )
