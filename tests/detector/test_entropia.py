"""tests/detector/test_entropia.py - tarea 4.6 (min-entropia, SP 800-90B).

Todo se compara contra la TEORIA, no contra otra implementacion: la
entropia de una fuente cuya distribucion se conoce se sabe de antemano, y
es ese numero el que aparece en los asserts. Las tolerancias se derivan
del tamano de muestra y de la cota de confianza del estandar, nunca se
eligen a ojo (regla heredada de la Fase 1).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from detector.entropia import (
    _tiempo_medio_de_colision,
    digitalizar,
    estimar_entropia,
    h_min_colision,
    h_min_markov,
    h_min_mas_comun,
)
from detector.types import ALFA_SP80090B, BITS_BAJOS, MUESTRAS_POR_CELDA

Z_99 = 2.5758293035489004  # cuantil 0.995 de la normal: el 2.576 del estandar


def _deficit(p: float, cuentas: float, sigmas: float = 4.0) -> float:
    """Cuanto baja un estimador por debajo de -log2(p) por usar la cota
    superior de p.

    La cota sustituye p por p + z*sqrt(p(1-p)/(c-1)), asi que la entropia
    baja en log2(1 + z*sqrt((1-p)/(p(c-1)))). A z se le suman `sigmas`
    desviaciones mas para cubrir la fluctuacion de la propia frecuencia
    medida en una muestra concreta. Es una tolerancia DERIVADA: depende
    solo de p y del numero de observaciones que sostienen esa frecuencia.
    """
    relativo = (Z_99 + sigmas) * math.sqrt((1.0 - p) / (p * (cuentas - 1.0)))
    return math.log2(1.0 + relativo)


def _shannon(simbolos: np.ndarray) -> float:
    """H = -sum p log2 p, para el test que compara las dos entropias."""
    p = np.bincount(simbolos).astype(np.float64) / simbolos.size
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


# --- digitalizar --------------------------------------------------------


def test_digitalizar_se_queda_con_los_bits_bajos():
    """Valores calculados a mano, incluidos negativos: la senal filtrada
    esta centrada en cero y los tiene. -3 en complemento a dos tiene los
    4 bits bajos a 1101 = 13, que es -3 modulo 16."""
    senal = np.array([0.0, 1.0, 15.0, 16.0, 17.6, -1.0, -3.0], dtype=np.float64)
    esperado = np.array([0, 1, 15, 0, 2, 15, 13], dtype=np.uint8)
    np.testing.assert_array_equal(digitalizar(senal, 4), esperado)


def test_digitalizar_conserva_solo_los_n_bits_pedidos():
    """El contrato del alfabeto: nada por encima de 2^n_bits - 1."""
    rng = np.random.default_rng(0)
    senal = rng.normal(0.0, 500.0, 10_000)
    for n_bits in (1, 4, 8):
        simbolos = digitalizar(senal, n_bits)
        assert simbolos.dtype == np.uint8
        assert simbolos.max() < 2**n_bits


def test_digitalizar_rechaza_un_ancho_imposible():
    """La salida es uint8: 0 o 9 bits por muestra no cabrian, y truncar en
    silencio seria peor que fallar."""
    with pytest.raises(ValueError, match="entre 1 y 8"):
        digitalizar(np.zeros(10), 9)
    with pytest.raises(ValueError, match="entre 1 y 8"):
        digitalizar(np.zeros(10), 0)


def test_digitalizar_rechaza_valores_no_finitos():
    """Un NaN redondeado se convierte en un entero cualquiera sin avisar:
    ese simbolo entraria en la estimacion como si fuera una medida."""
    senal = np.array([1.0, np.nan, 3.0])
    with pytest.raises(ValueError, match="no finitos"):
        digitalizar(senal, BITS_BAJOS)


# --- los tres estimadores ------------------------------------------------


def test_fuente_uniforme_da_la_entropia_maxima(rng):
    """Simbolos de 4 bits uniformes: H_min ~ 4. No exactamente 4, porque
    los estimadores usan la cota SUPERIOR de las probabilidades, asi que
    salen un poco por debajo; la tolerancia se deriva del tamano de
    muestra con _deficit.
    """
    n = 200_000
    simbolos = rng.integers(0, 16, n, dtype=np.uint8)
    est = estimar_entropia(simbolos)

    p = 1.0 / 16.0
    # El del valor mas comun se apoya en las n muestras.
    tol_comun = _deficit(p, n)
    assert 4.0 - tol_comun <= est.h_mas_comun <= 4.0
    # El de Markov se apoya en las ~n/16 transiciones que salen de cada
    # simbolo, asi que su cota es mas ancha por el mismo motivo.
    tol_markov = _deficit(p, n / 16.0)
    assert 4.0 - tol_markov <= est.h_markov <= 4.0
    # El de colision se queda mas abajo (~3.4 aqui) y NO es un fallo: cerca
    # de la uniformidad E[T] es estacionaria y restarle la cota de
    # confianza mueve p como sqrt(delta) (ver su docstring). Aqui solo se
    # le exige que siga viendo una fuente de mas de 3 bits por simbolo;
    # donde se le comprueba contra la teoria es en el test de la fuente
    # concentrada, que es donde su inversion no esta en un maximo.
    assert 3.0 < est.h_colision <= 4.0
    assert est.h_min == min(est.h_mas_comun, est.h_colision, est.h_markov)


def test_fuente_sesgada_da_lo_que_dice_la_teoria(rng):
    """Fuente con p_max = 0.5 conocido: H_min = -log2(0.5) = 1 bit exacto.
    Se compara contra ese numero, no contra otra implementacion."""
    n = 200_000
    probabilidades = [0.5, 0.25, 0.15, 0.10]
    simbolos = rng.choice(4, size=n, p=probabilidades).astype(np.uint8)

    h = h_min_mas_comun(simbolos)
    tol = _deficit(0.5, n)
    assert 1.0 - tol <= h <= 1.0 + tol
    # Y el minimo de los tres nunca puede quedar por encima del estimador
    # cuya teoria es exacta: si lo hiciera, no se estaria tomando el minimo.
    assert estimar_entropia(simbolos).h_min <= h


def test_min_entropia_es_MENOR_que_shannon(rng):
    """Propiedad matematica: H_min <= H_shannon siempre. Si un test
    encuentra lo contrario, hay un bug de signo o de base del logaritmo."""
    for p_sesgo in (0.5, 0.7, 0.9):
        bits = (rng.random(50_000) < p_sesgo).astype(np.uint8)
        est = estimar_entropia(bits)
        assert est.h_min <= _shannon(bits)
        assert est.h_mas_comun <= _shannon(bits) + _deficit(p_sesgo, 50_000)


def test_markov_caza_lo_que_los_otros_no(rng):
    """EL test de la tarea. Se construye una fuente CORRELACIONADA cuya
    distribucion marginal es uniforme: el estimador del valor mas comun
    dira que tiene entropia maxima, y el de Markov dira la verdad.

    La fuente avanza un simbolo (mod 16) con probabilidad 0.9 y salta a
    uno uniforme con probabilidad 0.1, asi que la probabilidad de la
    transicion mas probable es 0.9 + 0.1/16 = 0.90625 y la min-entropia
    real es -log2(0.90625) = 0.142 bits por simbolo, no 4.
    """
    n = 100_000
    salto = rng.random(n) < 0.9
    uniforme = rng.integers(0, 16, n, dtype=np.uint8)
    simbolos = np.empty(n, dtype=np.uint8)
    simbolos[0] = uniforme[0]
    for i in range(1, n):
        simbolos[i] = (simbolos[i - 1] + 1) % 16 if salto[i] else uniforme[i]

    est = estimar_entropia(simbolos)

    # La marginal es uniforme, asi que el estimador simple la declara casi
    # perfecta: mismo valor que en el test de la fuente uniforme de verdad.
    assert est.h_mas_comun >= 4.0 - _deficit(1.0 / 16.0, n)

    # Y el de Markov la caza. El valor esperado sale de la teoria: 127
    # transiciones de probabilidad 0.90625 (mas su cota superior) y un
    # estado inicial de probabilidad ~1/16, todo repartido entre los 128
    # pasos de la cadena que define SP 800-90B 6.3.3.
    p_trans = 0.90625
    p_cota = p_trans + Z_99 * math.sqrt(p_trans * (1 - p_trans) / (n / 16.0 - 1))
    esperado = (-math.log2(1 / 16.0) - 127 * math.log2(p_cota)) / 128
    assert est.h_markov == pytest.approx(esperado, abs=0.05)
    assert est.h_min == est.h_markov
    # Sin el de Markov, este modulo publicaria 4 bits por simbolo de una
    # fuente que tiene 0.15: un factor 25.
    assert est.h_mas_comun > 20 * est.h_markov


def test_colision_recupera_la_teoria_en_una_fuente_concentrada(rng):
    """Donde el estimador de colision si es exacto: una binaria con
    p_max = 0.9 conocido, H_min = -log2(0.9) = 0.152.

    Tolerancia derivada: el estandar resta z*sigma/sqrt(v) a la media de
    los tiempos de colision, y con p = 0.9 la pendiente de E[T] es
    -2p + 2q = -1.6, asi que ese desplazamiento se traduce en
    dp = z*sigma/(1.6*sqrt(v)) ~ 0.002 y dH = dp/(p ln2) ~ 0.0033. Se
    admiten 3 veces eso.
    """
    n = 200_000
    simbolos = (rng.random(n) < 0.9).astype(np.uint8)
    teoria = -math.log2(0.9)

    p_colision = 0.9**2 + 0.1**2
    sigma_t = math.sqrt(p_colision * (1 - p_colision))
    v = n / (3.0 - p_colision)
    desplazamiento = Z_99 * sigma_t / (1.6 * math.sqrt(v)) / (0.9 * math.log(2))

    assert h_min_colision(simbolos) == pytest.approx(teoria, abs=3 * desplazamiento)


def test_el_tiempo_medio_de_colision_binario_es_el_del_estandar():
    """La generalizacion a k simbolos tiene que reducirse a la formula
    binaria del estandar, E[T] = 3 - p^2 - q^2, para k = 2. Es lo que
    permite decir que el estimador generalizado no se ha inventado otra
    cosa (ver la cabecera de entropia.py)."""
    for p in (0.5, 0.6, 0.75, 0.9, 0.99):
        esperado = 3.0 - p**2 - (1.0 - p) ** 2
        assert _tiempo_medio_de_colision(p, 2) == pytest.approx(esperado, rel=1e-12)
    # Con un solo simbolo posible la segunda muestra ya repite, siempre.
    assert _tiempo_medio_de_colision(1.0, 1) == 2.0
    # Y con 16 simbolos uniformes salen 5.70 muestras de media, que es el
    # valor con el que se compara la media medida en los datos reales.
    assert _tiempo_medio_de_colision(1.0 / 16.0, 16) == pytest.approx(5.7043, abs=1e-4)


def test_se_devuelve_el_minimo(rng):
    """h_min tiene que ser exactamente min(los tres), no una media ni el
    que mejor quede."""
    simbolos = rng.integers(0, 16, 20_000, dtype=np.uint8)
    est = estimar_entropia(simbolos)
    assert est.h_min == min(est.h_mas_comun, est.h_colision, est.h_markov)
    assert est.h_min == pytest.approx(
        min(
            h_min_mas_comun(simbolos),
            h_min_colision(simbolos),
            h_min_markov(simbolos),
        )
    )
    assert est.n_muestras == simbolos.size
    assert est.intervalo_confianza == 1.0 - ALFA_SP80090B


# --- casos borde (tarea 4.8) --------------------------------------------


def test_una_senal_de_diez_muestras_da_un_error_claro():
    """Caso borde de la tarea 4.8: no se puede estimar entropia con eso, y
    el mensaje tiene que decir cuantas muestras harian falta."""
    simbolos = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=np.uint8)
    with pytest.raises(ValueError, match="no se puede estimar min-entropia"):
        estimar_entropia(simbolos)


def test_el_minimo_de_muestras_sale_del_alfabeto():
    """El umbral no es un numero magico: son MUESTRAS_POR_CELDA por celda
    de la matriz de transicion, k^2 celdas. Con 16 simbolos, 1280."""
    rng = np.random.default_rng(3)
    k = 16
    minimo = MUESTRAS_POR_CELDA * k * k
    assert minimo == 1280

    justo_por_debajo = rng.integers(0, k, minimo - 1, dtype=np.uint8)
    with pytest.raises(ValueError, match=f"al menos {minimo} muestras"):
        estimar_entropia(justo_por_debajo)

    justo_encima = rng.integers(0, k, minimo, dtype=np.uint8)
    assert 0.0 < estimar_entropia(justo_encima).h_min <= 4.0


def test_una_fuente_constante_tiene_entropia_cero():
    """Caso borde: sin variacion no hay nada que adivinar. Los tres
    estimadores tienen que decir 0.0 exacto, no un residuo negativo."""
    simbolos = np.zeros(5_000, dtype=np.uint8)
    est = estimar_entropia(simbolos)
    assert est.h_mas_comun == 0.0
    assert est.h_colision == 0.0
    assert est.h_markov == 0.0
    assert est.h_min == 0.0
    assert math.copysign(1.0, est.h_min) > 0  # 0.0, no -0.0


def test_una_fuente_uniforme_perfecta_conserva_casi_toda_la_capacidad(rng):
    """Caso borde de la tarea 4.8: con una fuente uniforme perfecta la
    estimacion tiene que quedarse cerca del maximo del alfabeto. Lo que se
    pierde despues en la extraccion (el peaje de 60 bits) se comprueba en
    test_extraccion.py."""
    simbolos = rng.integers(0, 2**BITS_BAJOS, 100_000, dtype=np.uint8)
    est = estimar_entropia(simbolos)
    assert est.h_min > 0.75 * BITS_BAJOS
    assert est.h_min <= BITS_BAJOS


def test_una_secuencia_ciclica_enfrenta_a_los_dos_estimadores():
    """0,1,2,...,15,0,1,2,... es DETERMINISTA: min-entropia real, cero.

    El estimador de colision la ve mas uniforme de lo que ninguna fuente
    sin memoria puede ser (todos los tramos duran exactamente 17), asi que
    devuelve el maximo del alfabeto; el de Markov ve que cada simbolo
    determina al siguiente y devuelve ~0. Es el mismo argumento del test
    de Markov, llevado al extremo, y la razon de que el modulo implemente
    tres estimadores y se quede con el minimo.
    """
    simbolos = np.tile(np.arange(16, dtype=np.uint8), 500)
    est = estimar_entropia(simbolos)
    assert est.h_colision == pytest.approx(4.0)
    assert est.h_markov < 0.05
    assert est.h_min == est.h_markov


def test_los_estimadores_rechazan_entradas_imposibles():
    """Las guardas comunes: nada de matrices, ni de secuencias de una
    muestra, ni de simbolos negativos (los indices de la matriz de
    transicion son posiciones, no valores con signo)."""
    with pytest.raises(ValueError, match="1-D"):
        h_min_mas_comun(np.zeros((4, 4), dtype=np.uint8))
    with pytest.raises(ValueError, match="al menos 2 simbolos"):
        h_min_markov(np.zeros(1, dtype=np.uint8))
    with pytest.raises(ValueError, match="no negativos"):
        h_min_colision(np.array([-1, 0, 1], dtype=np.int64))
    with pytest.raises(ValueError, match="alfa debe estar"):
        h_min_mas_comun(np.zeros(10, dtype=np.uint8), alfa=0.0)


def test_sin_colisiones_no_hay_nada_que_estimar():
    """256 simbolos todos distintos: ni un solo tramo se cierra, asi que
    no hay tiempos que promediar. Mejor un error que una media de un
    conjunto vacio."""
    todos_distintos = np.arange(256, dtype=np.uint8)
    with pytest.raises(ValueError, match="tiempo\\(s\\) de colision"):
        h_min_colision(todos_distintos)


def test_markov_es_conservador_cuando_no_hay_con_que_acotar():
    """Con una sola observacion saliendo de un simbolo no se puede acotar
    su fila de transiciones, asi que se supone lo peor (probabilidad 1) y
    la estimacion se va a cero. Es fail-safe -nunca sobreestima, solo hace
    tirar bits- y es la otra razon del minimo de muestras por celda."""
    assert h_min_markov(np.array([0, 1], dtype=np.uint8)) == 0.0
    assert math.copysign(1.0, h_min_markov(np.array([0, 1], dtype=np.uint8))) > 0


def test_las_constantes_de_la_46_son_parte_del_contrato():
    """Mismo motivo que test_scaffold con las siete de la tarea 4.1: si
    alguien las cambia, cambian todas las cifras de min-entropia
    publicadas, y tiene que saltar aqui."""
    assert ALFA_SP80090B == 0.01
    assert MUESTRAS_POR_CELDA == 5
