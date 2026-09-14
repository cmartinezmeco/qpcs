"""tests/detector/test_integration.py - tarea 4.8, la cadena entera.

Los tests de cada tarea vienen con su PR; aqui va el de integracion -de la
senal cargada a bits validados- y las comprobaciones que solo tienen
sentido con la cadena montada. Los ocho casos borde viven en el fichero de
la tarea a la que pertenecen (test_carga, test_espectro,
test_filtrado, test_identificacion, test_entropia y test_extraccion), que
es donde alguien los va a buscar cuando toque esa parte.

Lo que NO demuestra este fichero, y conviene tenerlo claro: que los bits
pasen monobit y chi2 no prueba que la fuente sea buena. Un contador
cifrado con AES los pasa igual. Lo que sostiene la
salida es la estimacion conservadora de la 4.6 mas el leftover hash lemma;
estos dos estadisticos solo confirman que no hay un fallo grosero por el
camino.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from detector.carga import cargar_muestra, senal_de_prueba
from detector.entropia import digitalizar, estimar_entropia
from detector.espectro import densidad_espectral
from detector.extraccion import extraer
from detector.filtrado import filtrar
from detector.identificacion import ajustar_alfa, detectar_picos, factor_fano
from detector.types import (
    BITS_BAJOS,
    EPSILON_PA,
    NPERSEG,
    RANGO_ALFA,
    UMBRAL_PICO,
    AnalisisEspectral,
    ResultadoExtraccion,
)

PEAJE = 2 * math.log2(1.0 / EPSILON_PA)  # ~59.79 bits, el del leftover hash
CHI2_MEDIA = 255.0
CHI2_SIGMA = math.sqrt(2 * 255.0)


def _cadena(
    senal: np.ndarray, fs: float
) -> tuple[AnalisisEspectral, ResultadoExtraccion]:
    """cargar -> espectro -> identificar -> filtrar -> estimar -> extraer.

    Es la cadena completa del modulo, con los parametros del
    contrato (types.py) y sin ningun ajuste local: si alguien cambia
    NPERSEG o UMBRAL_PICO, este test se entera.
    """
    frecuencias, psd, n_tramos = densidad_espectral(senal, fs, NPERSEG)
    picos = detectar_picos(frecuencias, psd, UMBRAL_PICO)
    # NOTA (tarea 4.8): RANGO_ALFA se pasa tal cual, que es lo que hace un
    # consumidor del modulo. Con los datos reales (fs = 1000 Hz) ese rango
    # no contiene ningun bin del espectro y ajustar_alfa devuelve
    # (0.0, 0.0) por su salida de seguridad: types.py lo documenta como
    # fraccion de Nyquist y identificacion.py lo interpreta en hercios.
    # Esta anotado como discrepancia de la tarea 4.4 y por eso aqui no se
    # afirma nada sobre el VALOR de alfa, solo que la cadena lo produce.
    alfa, alfa_error = ajustar_alfa(frecuencias, psd, RANGO_ALFA)
    analisis = AnalisisEspectral(
        frecuencias=frecuencias,
        psd=psd,
        alfa=alfa,
        alfa_error=alfa_error,
        suelo_blanco=float(np.median(psd[len(psd) // 2 :])),
        picos_hz=picos,
        fano=factor_fano(senal),
        n_tramos=n_tramos,
    )

    filtrada = filtrar(senal, fs, picos)
    simbolos = digitalizar(filtrada, BITS_BAJOS)
    estimacion = estimar_entropia(simbolos)
    return analisis, extraer(simbolos, estimacion, EPSILON_PA)


def _comprobar_bits(resultado: ResultadoExtraccion) -> None:
    """Las validaciones comunes a las dos senales."""
    assert resultado.bits.dtype == np.uint8
    assert set(np.unique(resultado.bits)) <= {0, 1}
    assert resultado.bits.size == resultado.longitud_segura
    # La longitud es la de la formula aplicada a la H_min medida.
    assert resultado.longitud_segura == math.floor(
        resultado.n_entrada * resultado.h_min_por_bit - PEAJE
    )
    # Monobit, umbral 4 sigma.
    assert resultado.z_monobit < 4.0
    # chi2 de bytes a dos colas, como en el modulo 3.
    assert abs(resultado.chi2 - CHI2_MEDIA) < 4 * CHI2_SIGMA


def test_la_cadena_completa():
    """De la senal cargada a bits validados. EL test del modulo.

    cargar -> espectro -> identificar -> filtrar -> estimar -> extraer
    y al final: los bits pasan monobit y chi2, y su numero coincide con
    la formula aplicada a la H_min medida.
    """
    senal, fs = cargar_muestra()
    analisis, resultado = _cadena(senal, fs)

    # El analisis espectral se rellena entero (contrato de la tarea 4.4).
    assert analisis.frecuencias.size == analisis.psd.size == NPERSEG // 2 + 1
    # NOTA (discrepancia de la tarea 4.8, ARREGLADA en la 4.9): types.py
    # documenta n_tramos como "K de Welch, para el error relativo", y
    # densidad_espectral devolvia el propio nperseg (4096) en esa tercera
    # posicion en vez del K real. Ya devuelve el K real -240 con 495.562
    # muestras y tramos de 4096 al 50%, ver el comentario de espectro.py-,
    # y aqui se sigue exigiendo solo que el campo venga relleno y positivo.
    assert analisis.n_tramos > 0
    assert analisis.suelo_blanco > 0.0
    assert analisis.fano > 0.0
    assert isinstance(analisis.picos_hz, tuple)

    # La min-entropia por bit es una fraccion de 1, y la de la muestra real
    # sale alta pero NO maxima: si diera exactamente BITS_BAJOS habria que
    # sospechar de la digitalizacion antes que celebrarlo.
    assert 0.0 < resultado.h_min_por_bit < 1.0
    assert resultado.n_entrada == senal.size * BITS_BAJOS
    _comprobar_bits(resultado)


def test_la_cadena_completa_sobre_la_senal_sintetica():
    """La misma cadena sobre la senal de composicion conocida.

    Aqui si se sabe que hay dentro (ruido blanco + 1/f con alfa = 1 + una
    interferencia de 50 Hz + Poisson), asi que se puede exigir que la
    interferencia se detecte y desaparezca, cosa que con datos reales no
    se puede comprobar porque no se conoce su composicion.
    """
    senal, fs = senal_de_prueba(n=2**17, semilla=3)
    frecuencias, psd, _ = densidad_espectral(senal, fs, NPERSEG)
    picos = detectar_picos(frecuencias, psd, UMBRAL_PICO)
    df = fs / NPERSEG
    assert any(abs(p - 50.0) <= df for p in picos), f"picos detectados: {picos}"

    _, resultado = _cadena(senal, fs)
    assert resultado.n_entrada == senal.size * BITS_BAJOS
    _comprobar_bits(resultado)


def test_el_analisis_es_determinista_y_solo_los_bits_cambian():
    """Dos pasadas sobre la misma senal tienen que medir exactamente lo
    mismo -el analisis no tiene azar- y devolver bits DISTINTOS, porque la
    semilla de Toeplitz sale de os.urandom en cada extraccion.

    Es una distincion que conviene no perder de vista: en este modulo hay
    azar en dos sitios y son de naturaleza distinta. El
    de los tests se siembra; el de la semilla no puede sembrarse nunca.
    """
    senal, fs = senal_de_prueba(n=2**16, semilla=4)
    primera_analisis, primera = _cadena(senal, fs)
    segunda_analisis, segunda = _cadena(senal, fs)

    assert primera_analisis.picos_hz == segunda_analisis.picos_hz
    assert primera_analisis.fano == segunda_analisis.fano
    assert primera.h_min_por_bit == segunda.h_min_por_bit
    assert primera.longitud_segura == segunda.longitud_segura
    assert not np.array_equal(primera.bits, segunda.bits)


def test_el_embudo_de_bits_solo_encoge():
    """El equivalente al embudo del modulo 1: muestras -> bits conservados
    -> bits de min-entropia -> bits extraidos. Cada paso tiene que ser
    menor o igual que el anterior, y el ultimo salto es exactamente el
    peaje del lema.

    Es la comprobacion que impide el error mas comun del campo: confundir
    "4 bits conservados por muestra" con "4 bits de entropia por muestra"
    produciria mas bits extraidos que entropia disponible.
    """
    senal, fs = cargar_muestra()
    _, resultado = _cadena(senal, fs)

    conservados = resultado.n_entrada
    de_entropia = resultado.n_entrada * resultado.h_min_por_bit
    extraidos = resultado.bits.size

    assert senal.size * BITS_BAJOS == conservados
    assert de_entropia < conservados  # la fuente no es uniforme perfecta
    assert extraidos <= de_entropia
    assert de_entropia - extraidos == pytest.approx(PEAJE, abs=1.0)
