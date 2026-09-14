"""tests/chaos/test_baseline.py - tarea 3.8, el contraste honesto.

La tesis del modulo en forma de test: el esquema caotico, AES-256-GCM y
un flujo trivial de SHA256(clave || contador) pasan EXACTAMENTE las
mismas metricas con los mismos margenes. Como el tercero es una
construccion que nadie defenderia como cifrado serio, la conclusion no
admite matices: las metricas miden ausencia de defectos groseros, no
seguridad.

La cripto real se prueba por PROPIEDADES y sin semilla, igual que en el
modulo 2: el nonce de AES-GCM sale de os.urandom por diseno y no se
siembra.
"""

import numpy as np
import pytest
from chaos import (
    ClaveCaotica,
    calcular_npcr,
    calcular_uaci,
    chi2_histograma,
    cifrar_aes_gcm,
    cifrar_flujo_trivial,
    cifrar_imagen,
    correlacion_adyacente,
    entropia_esperada,
    entropia_shannon,
    imagen_de_prueba,
    medir_imagen,
    npcr_esperado,
    uaci_esperado,
)
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .tolerancias import (
    CHI2_CRITICO_5PCT,
    CHI2_MEDIA,
    sigma_chi2,
    sigma_correlacion,
    sigma_entropia,
    sigma_npcr,
    sigma_uaci,
)

CLAVE_CAOTICA = ClaveCaotica("logistico", 0.4, r=3.99)
# Clave AES fija y visible: esto es un test, no un despliegue. Lo que NO
# se fija es el nonce, que tiene que ser fresco en cada llamada.
CLAVE_AES = bytes(range(32))


# --- AES-256-GCM -------------------------------------------------------


def test_aes_round_trip():
    """El cuerpo y el tag se devuelven troceados; volver a juntarlos tiene
    que descifrar. Si el troceo estuviera mal, esto lo caza."""

    img = imagen_de_prueba(64, 64)
    datos, nonce, tag = cifrar_aes_gcm(img, CLAVE_AES)
    recuperada = AESGCM(CLAVE_AES).decrypt(nonce, datos.tobytes() + tag, None)
    assert recuperada == img.tobytes()


def test_aes_conserva_la_forma_y_el_tipo():
    """El tag de 16 bytes va aparte y no dentro de la imagen: mezclarlo
    con los pixeles descuadraria la forma y contaminaria el histograma
    con 16 valores que no vienen del cifrado de la imagen."""

    img = imagen_de_prueba(100, 37)
    datos, nonce, tag = cifrar_aes_gcm(img, CLAVE_AES)
    assert datos.shape == img.shape
    assert datos.dtype == np.uint8
    assert len(nonce) == 12
    assert len(tag) == 16


def test_aes_usa_un_nonce_fresco_en_cada_llamada():
    """Es LA diferencia de comportamiento con el esquema caotico, que es
    determinista y sin nonce."""

    img = imagen_de_prueba(32, 32)
    primero, nonce1, _ = cifrar_aes_gcm(img, CLAVE_AES)
    segundo, nonce2, _ = cifrar_aes_gcm(img, CLAVE_AES)
    assert nonce1 != nonce2
    assert not np.array_equal(primero, segundo)


def test_aes_autentica_y_el_caotico_no():
    """La fila de la tabla que NO sale de ninguna medida estadistica:
    AES-GCM detecta la manipulacion (InvalidTag) y el esquema caotico,
    que no tiene etiqueta, descifra tan tranquilo a otra cosa."""

    img = imagen_de_prueba(32, 32)
    datos, nonce, tag = cifrar_aes_gcm(img, CLAVE_AES)
    manipulado = datos.copy().ravel()
    manipulado[0] ^= 1
    with pytest.raises(InvalidTag):
        AESGCM(CLAVE_AES).decrypt(nonce, manipulado.tobytes() + tag, None)


def test_aes_exige_una_clave_de_32_bytes():
    with pytest.raises(ValueError, match="32 bytes"):
        cifrar_aes_gcm(imagen_de_prueba(8, 8), b"corta")


@pytest.mark.parametrize("funcion", [cifrar_aes_gcm, cifrar_flujo_trivial])
def test_los_baselines_rechazan_lo_que_no_es_uint8(funcion):
    with pytest.raises(ValueError, match="uint8"):
        funcion(np.zeros((8, 8), dtype=np.float64), CLAVE_AES)


# --- El flujo trivial --------------------------------------------------


def test_el_flujo_trivial_es_involutivo_y_determinista():
    """XOR con un flujo fijo: aplicarlo dos veces devuelve el original, y
    la misma clave da siempre el mismo resultado. No hay nonce ni estado."""

    img = imagen_de_prueba(64, 64)
    cifrada = cifrar_flujo_trivial(img, CLAVE_AES)
    np.testing.assert_array_equal(cifrar_flujo_trivial(cifrada, CLAVE_AES), img)
    np.testing.assert_array_equal(cifrar_flujo_trivial(img, CLAVE_AES), cifrada)


def test_el_flujo_trivial_es_de_verdad_sha256_de_clave_y_contador():
    """El test no se fia de la implementacion: reconstruye el flujo a
    mano y comprueba el XOR."""

    import hashlib

    img = imagen_de_prueba(8, 8)
    flujo = b"".join(
        hashlib.sha256(CLAVE_AES + i.to_bytes(8, "big")).digest() for i in range(2)
    )
    esperado = img.ravel() ^ np.frombuffer(flujo, dtype=np.uint8)[: img.size]
    np.testing.assert_array_equal(
        cifrar_flujo_trivial(img, CLAVE_AES).ravel(), esperado
    )


def test_el_flujo_trivial_se_rompe_con_dos_imagenes_y_la_misma_clave():
    """El remate del argumento: esta construccion pasa las cinco metricas
    y sin embargo el XOR de dos cifrados con la misma clave es
    EXACTAMENTE el XOR de los dos planos. Un atacante ve la estructura de
    las dos imagenes a simple vista, sin tocar la clave.

    Ninguna de las metricas del campo detecta esto. Esa es la leccion."""

    a = imagen_de_prueba(64, 64)
    b = np.zeros_like(a)
    ca = cifrar_flujo_trivial(a, CLAVE_AES)
    cb = cifrar_flujo_trivial(b, CLAVE_AES)
    np.testing.assert_array_equal(ca ^ cb, a ^ b)


# --- La tabla de las tres columnas -------------------------------------


def _tres_columnas(img):
    """Las tres filas de la tabla comparativa, medidas sobre la MISMA
    imagen y con las MISMAS funciones."""
    caotico = cifrar_imagen(img, CLAVE_CAOTICA).datos
    aes, _, _ = cifrar_aes_gcm(img, CLAVE_AES)
    trivial = cifrar_flujo_trivial(img, CLAVE_AES)
    return {
        "caotico": medir_imagen("caotico", img, caotico),
        "AES-256-GCM": medir_imagen("AES-256-GCM", img, aes),
        "contador": medir_imagen("contador", img, trivial),
    }


def test_las_tres_columnas_salen_indistinguibles():
    """El resultado que hay que anticipar porque es el corazon del modulo:
    las tres pasan entropia, correlacion y chi2 con los mismos margenes
    derivados.

    Que AES las pase se puede leer como "AES es bueno". Que las pase
    tambien SHA256(clave || contador) cierra esa escapatoria.

    El chi2 se comprueba contra la banda de 4 sigma en torno a su media
    (255 +/- 90.3), no contra el valor critico al 5% (293.25). El motivo
    es estadistico y merece quedar escrito: un contraste al 5% rechaza
    por definicion el 5% de las muestras buenas, asi que exigirlo a tres
    esquemas correctos fallaria una de cada siete ejecuciones. Medido
    aqui: el flujo trivial da chi2 = 306, que son 2.26 sigma, es decir
    una fluctuacion normal y no un defecto. Y la banda es de DOS COLAS
    porque un chi2 demasiado bajo tambien es sospechoso.
    """
    img = imagen_de_prueba()
    n = img.size
    tolerancia_h = 4 * sigma_entropia(n)
    tolerancia_r = 4 * sigma_correlacion(5000)
    tolerancia_chi2 = 4 * sigma_chi2()

    for etiqueta, fila in _tres_columnas(img).items():
        assert abs(fila.entropia - entropia_esperada(n)) < tolerancia_h, etiqueta
        assert abs(fila.corr_horizontal) < tolerancia_r, etiqueta
        assert abs(fila.corr_vertical) < tolerancia_r, etiqueta
        assert abs(fila.corr_diagonal) < tolerancia_r, etiqueta
        assert abs(fila.chi2 - CHI2_MEDIA) < tolerancia_chi2, etiqueta


def test_npcr_y_uaci_tambien_salen_iguales_en_las_tres():
    """La segunda mitad de la tabla. Se miden entre dos cifrados
    INDEPENDIENTES (dos claves distintas, o dos nonces distintos), que es
    la unica lectura en la que los tres esquemas son comparables: el
    contador trivial con la misma clave daria NPCR = 1/M por definicion."""

    img = imagen_de_prueba()
    n = img.size
    otra_caotica = ClaveCaotica("logistico", 0.4 + 1e-15, r=3.99)
    otra_aes = bytes(range(1, 33))

    parejas = {
        "caotico": (
            cifrar_imagen(img, CLAVE_CAOTICA).datos,
            cifrar_imagen(img, otra_caotica).datos,
        ),
        "AES-256-GCM": (
            cifrar_aes_gcm(img, CLAVE_AES)[0],
            cifrar_aes_gcm(img, CLAVE_AES)[0],
        ),
        "contador": (
            cifrar_flujo_trivial(img, CLAVE_AES),
            cifrar_flujo_trivial(img, otra_aes),
        ),
    }
    for etiqueta, (c1, c2) in parejas.items():
        assert abs(calcular_npcr(c1, c2) - npcr_esperado()) < 4 * sigma_npcr(
            n
        ), etiqueta
        assert abs(calcular_uaci(c1, c2) - uaci_esperado()) < 4 * sigma_uaci(
            n
        ), etiqueta


def test_la_leccion_en_una_linea():
    """Las metricas no distinguen un esquema de otro, y una propiedad de
    seguridad elemental si. El flujo trivial pasa la entropia con nota y
    se rompe con un XOR; AES ni siquiera deja repetir el cifrado."""

    img = imagen_de_prueba(64, 64)
    trivial = cifrar_flujo_trivial(img, CLAVE_AES)

    # Pasa la metrica...
    assert abs(
        entropia_shannon(trivial) - entropia_esperada(img.size)
    ) < 4 * sigma_entropia(img.size)
    assert abs(correlacion_adyacente(trivial, "horizontal")) < 4 * sigma_correlacion(
        5000
    )
    assert chi2_histograma(trivial) < CHI2_CRITICO_5PCT

    # ...y se rompe entera con una sola operacion.
    otra = imagen_de_prueba(64, 64, semilla=7)
    np.testing.assert_array_equal(
        trivial ^ cifrar_flujo_trivial(otra, CLAVE_AES), img ^ otra
    )
