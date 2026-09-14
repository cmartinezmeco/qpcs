"""tests/detector/test_extraccion.py - tarea 4.7 (Toeplitz del modulo 1).

Lo que hay que demostrar aqui es que NO se ha reimplementado nada: la
compresion la hace privacy_amplify de la tarea 1.6, y la longitud sale de
la formula del leftover hash lemma, comprobada a mano.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import qkd.privacy
from chaos import histograma_chi2
from detector.entropia import digitalizar, estimar_entropia
from detector.extraccion import _bits_de_simbolos, _longitud_segura, extraer
from detector.types import BITS_BAJOS, EPSILON_PA, EstimacionEntropia

PEAJE = 2 * math.log2(1.0 / EPSILON_PA)  # ~59.79 bits con eps = 1e-9

# chi2 de 255 grados de libertad: media 255, sigma = sqrt(2*255) = 22.58.
# Se lee a DOS COLAS, como en el modulo 3: un valor
# sospechosamente bajo tambien es alarma.
CHI2_MEDIA = 255.0
CHI2_SIGMA = math.sqrt(2 * 255.0)


def _simbolos_uniformes(n: int, semilla: int = 5) -> np.ndarray:
    """Fuente ideal de 4 bits: la que mas bits deja destilar."""
    return np.random.default_rng(semilla).integers(0, 2**BITS_BAJOS, n, dtype=np.uint8)


# --- que se reutiliza el extractor del modulo 1 --------------------------


def test_usa_el_extractor_del_modulo_1(monkeypatch):
    """Que la funcion de qkd.privacy se llama de verdad, no que se haya
    reimplementado aqui una copia. Se comprueba parcheandola y viendo que
    el resultado cambia: si extraccion.py tuviera su propio Toeplitz, el
    parche no se notaria."""
    simbolos = _simbolos_uniformes(4_000)
    estimacion = estimar_entropia(simbolos)

    llamadas: list[tuple[int, int]] = []

    def falso(key, ell, seed):
        llamadas.append((key.size, ell))
        return np.zeros(ell, dtype=np.uint8)

    monkeypatch.setattr(qkd.privacy, "privacy_amplify", falso)
    resultado = extraer(simbolos, estimacion, EPSILON_PA)

    assert len(llamadas) == 1
    assert llamadas[0] == (resultado.n_entrada, resultado.longitud_segura)
    assert not resultado.bits.any()  # los ceros del parche, no bits reales


def test_la_semilla_sale_de_urandom_y_no_se_siembra():
    """Dos extracciones de la MISMA entrada tienen que dar bits distintos:
    la semilla de Toeplitz se genera con os.urandom en cada llamada y no
    se siembra nunca. Si coincidieran, alguien
    habria puesto una semilla fija y el leftover hash lemma dejaria de
    aplicar."""
    simbolos = _simbolos_uniformes(4_000)
    estimacion = estimar_entropia(simbolos)
    primera = extraer(simbolos, estimacion, EPSILON_PA).bits
    segunda = extraer(simbolos, estimacion, EPSILON_PA).bits
    assert primera.size == segunda.size > 0
    assert not np.array_equal(primera, segunda)


# --- la longitud segura --------------------------------------------------


def test_la_longitud_sale_de_la_formula():
    """ell = floor(n * H_min - 2 log2(1/eps)), comprobado a mano con
    numeros concretos: con n = 1000 bits, H = 0.5 bits/bit y eps = 1e-9,
    2 log2(1/eps) = 59.7947 y ell = floor(500 - 59.7947) = 440."""
    assert _longitud_segura(1000, 0.5, 1e-9) == 440
    # El peaje es lo unico que separa ell de n*H, y es constante.
    assert _longitud_segura(10_000, 0.5, 1e-9) == 4940
    # Sin entropia no hay bits, ni siquiera negativos.
    assert _longitud_segura(1000, 0.0, 1e-9) == 0
    # Y con tan poca que no cubre el peaje, tampoco.
    assert _longitud_segura(100, 0.5, 1e-9) == 0


def test_la_formula_rechaza_parametros_sin_sentido():
    """epsilon fuera de (0,1) no es un parametro de seguridad, y una
    min-entropia negativa solo puede venir de un bug aguas arriba: en los
    dos casos es mejor parar que devolver una longitud."""
    with pytest.raises(ValueError, match="epsilon"):
        _longitud_segura(1000, 0.5, 0.0)
    with pytest.raises(ValueError, match="epsilon"):
        _longitud_segura(1000, 0.5, 1.0)
    with pytest.raises(ValueError, match="no puede ser negativa"):
        _longitud_segura(1000, -0.1, 1e-9)


def test_la_longitud_publicada_es_la_de_la_formula():
    """La misma comprobacion sobre el resultado real: ell tiene que salir
    de los campos que el propio ResultadoExtraccion publica."""
    simbolos = _simbolos_uniformes(20_000)
    resultado = extraer(simbolos, estimar_entropia(simbolos), EPSILON_PA)
    esperado = math.floor(resultado.n_entrada * resultado.h_min_por_bit - PEAJE)
    assert resultado.longitud_segura == esperado
    assert resultado.bits.size == resultado.longitud_segura


def test_h_min_baja_implica_menos_bits():
    """Propiedad: con la mitad de min-entropia salen aproximadamente la
    mitad de bits. Si no, la formula esta mal cableada."""
    simbolos = _simbolos_uniformes(20_000)
    completa = estimar_entropia(simbolos)
    mitad = EstimacionEntropia(
        h_mas_comun=completa.h_mas_comun,
        h_colision=completa.h_colision,
        h_markov=completa.h_markov,
        h_min=completa.h_min / 2.0,
        n_muestras=completa.n_muestras,
        intervalo_confianza=completa.intervalo_confianza,
    )
    bits_completa = extraer(simbolos, completa, EPSILON_PA).longitud_segura
    bits_mitad = extraer(simbolos, mitad, EPSILON_PA).longitud_segura
    # La diferencia con la mitad exacta es el peaje, que solo se paga una
    # vez: bits_completa/2 - bits_mitad ~ PEAJE/2, unos 30 bits.
    assert abs(bits_mitad - bits_completa / 2) < PEAJE


def test_la_estimacion_tiene_que_ser_de_estos_simbolos():
    """Extraer con la min-entropia medida sobre OTROS datos es como se
    produce una salida que parece aleatoria y no lo es: se rechaza."""
    simbolos = _simbolos_uniformes(20_000)
    otra = estimar_entropia(_simbolos_uniformes(10_000, semilla=6))
    with pytest.raises(ValueError, match="estos mismos simbolos"):
        extraer(simbolos, otra, EPSILON_PA)


def test_el_ancho_de_simbolo_sale_de_los_datos():
    """_bits_de_simbolos despliega cada simbolo en sus bits reales y no
    inventa ceros de relleno: con simbolos de 4 bits salen 4 bits por
    muestra, y volver a montarlos devuelve los simbolos originales."""
    simbolos = _simbolos_uniformes(1_000)
    bits, ancho = _bits_de_simbolos(simbolos)
    assert ancho == BITS_BAJOS
    assert bits.size == simbolos.size * BITS_BAJOS
    assert set(np.unique(bits)) <= {0, 1}
    pesos = 2 ** np.arange(ancho)
    np.testing.assert_array_equal(bits.reshape(-1, ancho) @ pesos, simbolos)


# --- validacion de la salida ---------------------------------------------


def test_los_bits_extraidos_pasan_el_monobit():
    """z = |2 sum(b) - n| / sqrt(n) < 4. Umbral derivado de la binomial,
    igual que en el QRNG del modulo 1."""
    simbolos = _simbolos_uniformes(50_000)
    resultado = extraer(simbolos, estimar_entropia(simbolos), EPSILON_PA)
    assert resultado.z_monobit < 4.0


def test_los_bits_extraidos_pasan_el_chi2_por_las_dos_colas():
    """chi2 de bytes con 255 grados de libertad. Se lee a dos colas, como
    en el modulo 3: por encima delata sesgo y por debajo delata una
    uniformidad demasiado perfecta para ser azar."""
    simbolos = _simbolos_uniformes(50_000)
    resultado = extraer(simbolos, estimar_entropia(simbolos), EPSILON_PA)
    assert abs(resultado.chi2 - CHI2_MEDIA) < 4 * CHI2_SIGMA


def test_el_chi2_es_el_mismo_estadistico_que_el_del_modulo_3():
    """extraccion.py calcula el chi2 del histograma de bytes en cuatro
    lineas en vez de importar chaos.histograma_chi2, para no atar el
    modulo 4 al 3. Este test comprueba que son el MISMO numero, que es lo
    que hace legitima esa decision."""
    simbolos = _simbolos_uniformes(50_000)
    resultado = extraer(simbolos, estimar_entropia(simbolos), EPSILON_PA)
    completos = (resultado.bits.size // 8) * 8
    octetos = np.packbits(resultado.bits[:completos])
    assert resultado.chi2 == pytest.approx(histograma_chi2(octetos))


def test_h_min_cero_no_produce_bits():
    """Caso borde: una fuente constante tiene H_min = 0 y la extraccion
    tiene que devolver un array vacio, no fallar ni inventarse bits."""
    simbolos = np.zeros(5_000, dtype=np.uint8)
    resultado = extraer(simbolos, estimar_entropia(simbolos), EPSILON_PA)
    assert resultado.longitud_segura == 0
    assert resultado.bits.size == 0
    assert resultado.h_min_por_bit == 0.0
    # Los estadisticos no estan definidos sin bits: NaN, no 0.0, que se
    # leeria como "perfecto" (mismo criterio que efficiency en el modulo 1).
    assert math.isnan(resultado.z_monobit)
    assert math.isnan(resultado.chi2)


def test_la_fuente_uniforme_se_extrae_casi_sin_perdida():
    """Caso borde de la tarea 4.8: con una fuente uniforme perfecta lo
    unico que se pierde respecto a la entropia estimada es el peaje del
    lema, unos 60 bits sobre cientos de miles."""
    simbolos = _simbolos_uniformes(50_000)
    resultado = extraer(simbolos, estimar_entropia(simbolos), EPSILON_PA)
    entropia_disponible = resultado.n_entrada * resultado.h_min_por_bit
    assert 0.0 <= entropia_disponible - resultado.longitud_segura < PEAJE + 1.0


def test_la_senal_vacia_se_rechaza():
    """Sin muestras no hay nada que extraer, y devolver un array vacio en
    silencio esconderia un error del llamante."""
    vacia = np.empty(0, dtype=np.uint8)
    estimacion = EstimacionEntropia(4.0, 4.0, 4.0, 4.0, 0, 0.99)
    with pytest.raises(ValueError, match="no vacia"):
        extraer(vacia, estimacion, EPSILON_PA)


def test_la_digitalizacion_encaja_con_la_extraccion():
    """La cadena corta 4.6 -> 4.7 sobre una senal filtrada sintetica: los
    tipos y los tamanos tienen que encajar sin conversiones a mano."""
    rng = np.random.default_rng(9)
    filtrada = rng.normal(0.0, 400.0, 20_000)
    simbolos = digitalizar(filtrada, BITS_BAJOS)
    resultado = extraer(simbolos, estimar_entropia(simbolos), EPSILON_PA)
    assert resultado.n_entrada == simbolos.size * BITS_BAJOS
    assert resultado.bits.dtype == np.uint8
    assert resultado.z_monobit < 4.0


@pytest.mark.slow
def test_el_toeplitz_sigue_siendo_exacto_al_tamano_real():
    """privacy_amplify documenta que con n < 2^20 las sumas parciales de
    la FFT caben exactas en float64. La senal real da n ~ 2*10^6 bits de
    entrada, por encima de ese numero, asi que la exactitud a ESE tamano
    hay que comprobarla en vez de suponerla.

    Se comparan unas filas del producto contra la definicion de la matriz
    de Toeplitz: T[i,j] = seed[i-j] si i >= j, y seed[ell-1+j-i] si no.
    """
    rng = np.random.default_rng(11)
    n, ell = 1_982_248, 1_809_946  # los tamanos de la cadena con datos reales
    clave = rng.integers(0, 2, n, dtype=np.uint8)
    semilla = rng.integers(0, 2, n + ell - 1, dtype=np.uint8)
    salida = qkd.privacy.privacy_amplify(clave, ell, semilla)

    columnas = np.arange(n)
    for fila in (0, 1, n // 3, ell - 1):
        pesos = np.where(
            fila >= columnas,
            semilla[np.abs(fila - columnas)],
            semilla[ell - 1 + np.abs(columnas - fila)],
        )
        esperado = int(np.dot(pesos.astype(np.int64), clave.astype(np.int64)) % 2)
        assert int(salida[fila]) == esperado
