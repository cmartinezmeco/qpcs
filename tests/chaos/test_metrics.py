"""tests/chaos/test_metrics.py - tarea 3.7, las metricas de calidad.

Cada valor esperado se comprueba contra su DERIVACION, no contra el
numero que sale del propio codigo: si la formula y el test salieran del
mismo sitio, el test no probaria nada.
"""

import numpy as np
import pytest
from chaos import (
    ClaveCaotica,
    calcular_npcr,
    calcular_uaci,
    chi2_histograma,
    cifrar_imagen,
    correlacion_adyacente,
    entropia_esperada,
    entropia_shannon,
    histograma_chi2,
    imagen_de_prueba,
    medir_imagen,
    npcr_esperado,
    orbita_logistica,
    uaci_esperado,
)
from chaos.types import ESCALA_BITS

from .tolerancias import (
    CHI2_CRITICO_5PCT,
    CHI2_MEDIA,
    sigma_chi2,
    sigma_correlacion,
    sigma_entropia,
    sigma_npcr,
    sigma_uaci,
)

CLAVE = ClaveCaotica("logistico", 0.4, r=3.99)


# --- La imagen de prueba: sin ella las metricas no significan nada -----


def test_la_imagen_de_prueba_pasa_su_comprobacion_de_cordura():
    """Un array de ruido tendria correlacion cero y entropia ~8 ANTES de
    cifrar, y la metrica estrella del modulo no demostraria nada. La
    imagen de prueba tiene que estar correlacionada y tener poca
    entropia; si no, no sirve de punto de partida."""

    img = imagen_de_prueba()
    assert correlacion_adyacente(img, "horizontal") > 0.9
    assert entropia_shannon(img) < 7.5


def test_la_imagen_de_prueba_es_determinista():
    """Las cifras de NPCR y UACI del README dependen del contenido exacto
    de la imagen: si no fuera reproducible, no serian verificables."""

    np.testing.assert_array_equal(imagen_de_prueba(), imagen_de_prueba())
    assert not np.array_equal(imagen_de_prueba(semilla=1), imagen_de_prueba(semilla=2))


# --- Entropia ----------------------------------------------------------


def test_entropia_esperada_es_la_de_miller_madow():
    """8 - 255/(2*65536*ln 2) = 7.99719, no 8.0. El numero se escribe
    aqui a mano: si la funcion cambia de formula, el test lo dice."""

    assert entropia_esperada(65536) == pytest.approx(7.997193, abs=1e-6)
    assert entropia_esperada(65536) < 8.0
    # Con mas pixeles el sesgo se encoge y el estimador se acerca a 8.
    assert entropia_esperada(1_000_000) > entropia_esperada(65536)


def test_un_test_que_exigiera_7_999_fallaria_siempre():
    """La consecuencia practica del sesgo, escrita como test para que no
    se le ocurra a nadie volver a poner 7.999 en un assert."""

    assert entropia_esperada(65536) < 7.999


def test_entropia_de_los_casos_extremos():
    """Una imagen constante tiene entropia 0 y una con dos valores a
    partes iguales, exactamente 1 bit/pixel."""

    assert entropia_shannon(np.full((16, 16), 7, dtype=np.uint8)) == 0.0
    mitad = np.array([0, 255] * 128, dtype=np.uint8).reshape(16, 16)
    assert entropia_shannon(mitad) == pytest.approx(1.0)


def test_entropia_de_una_fuente_uniforme_cae_en_su_banda(rng):
    """El estimador sobre datos uniformes sembrados tiene que dar el
    valor esperado con correccion de sesgo, dentro de 4 sigma."""

    img = rng.integers(0, 256, 65536, dtype=np.uint8).reshape(256, 256)
    desviacion = abs(entropia_shannon(img) - entropia_esperada(img.size))
    assert desviacion < 4 * sigma_entropia(img.size)


# --- Correlacion -------------------------------------------------------


def test_la_correlacion_cae_al_cifrar_en_las_tres_direcciones():
    """De >0.9 a ~0 con tolerancia derivada de 1/sqrt(5000) = 0.0141;
    4 sigma dan |r| < 0.057, no un 0.05 redondo."""

    img = imagen_de_prueba()
    cifrada = cifrar_imagen(img, CLAVE).datos
    tolerancia = 4 * sigma_correlacion(5000)
    assert tolerancia == pytest.approx(0.0566, abs=1e-3)
    for direccion in ("horizontal", "vertical", "diagonal"):
        assert correlacion_adyacente(img, direccion) > 0.9
        assert abs(correlacion_adyacente(cifrada, direccion)) < tolerancia


def test_correlacion_perfecta_y_perfectamente_negativa():
    """Dos casos con respuesta conocida, para fijar la magnitud y el
    SIGNO: un degradado da correlacion ~+1 (cada pixel vale casi lo mismo
    que su vecino) y un damero de columnas 0/255 da ~-1 (cada pixel vale
    lo contrario que su vecino)."""

    rampa = np.tile(np.arange(256, dtype=np.uint8), (256, 1))
    assert correlacion_adyacente(rampa, "horizontal") > 0.99
    # Las filas son identicas entre si: verticalmente cada pixel es igual
    # a su vecino de abajo, luego la correlacion vertical es exactamente 1.
    assert correlacion_adyacente(rampa, "vertical") == pytest.approx(1.0)

    damero = np.tile(np.array([0, 255] * 128, dtype=np.uint8), (256, 1))
    assert correlacion_adyacente(damero, "horizontal") == pytest.approx(-1.0)


def test_correlacion_no_medible_devuelve_nan_y_no_cero():
    """Devolver 0.0 se leeria en la tabla como 'correlacion nula', que es
    justo lo que el cifrado quiere demostrar. Seria mentira."""

    assert np.isnan(correlacion_adyacente(np.zeros((8, 8), dtype=np.uint8)))
    assert np.isnan(correlacion_adyacente(np.array([[5]], dtype=np.uint8)))
    fila = imagen_de_prueba(1, 50)
    assert np.isnan(correlacion_adyacente(fila, "vertical"))


def test_direccion_desconocida_es_un_error():
    with pytest.raises(ValueError, match="direccion"):
        correlacion_adyacente(imagen_de_prueba(8, 8), "en_diagonal_inversa")


# --- NPCR y UACI -------------------------------------------------------


def test_npcr_esperado_es_255_entre_256():
    """(1 - 1/256) * 100 = 99.6094%. Y no es 'cuanto mas alto mejor':
    un 100% seria estadisticamente imposible entre dos secuencias
    uniformes independientes y delataria estructura."""

    assert npcr_esperado() == pytest.approx(99.6094, abs=1e-4)
    assert npcr_esperado() < 100.0


def test_uaci_esperado_sale_de_la_doble_suma():
    """33.4635%, derivado y no copiado. Se comprueba contra la doble suma
    explicita sobre los 256x256 pares posibles, que es de donde sale."""

    valores = np.arange(256)
    esperanza = np.abs(valores[:, None] - valores[None, :]).mean()
    assert esperanza == pytest.approx(255 * 257 / (3 * 256))
    assert uaci_esperado() == pytest.approx(esperanza / 255 * 100)
    assert uaci_esperado() == pytest.approx(33.4635, abs=1e-4)


def test_npcr_y_uaci_de_dos_fuentes_uniformes_independientes(rng):
    """Los dos estimadores contra sus valores teoricos, con las sigmas
    derivadas de la binomial y de Var|X-Y|."""

    a = rng.integers(0, 256, 65536, dtype=np.uint8).reshape(256, 256)
    b = rng.integers(0, 256, 65536, dtype=np.uint8).reshape(256, 256)
    assert abs(calcular_npcr(a, b) - npcr_esperado()) < 4 * sigma_npcr(a.size)
    assert abs(calcular_uaci(a, b) - uaci_esperado()) < 4 * sigma_uaci(a.size)


def test_npcr_de_los_extremos():
    """Dos imagenes identicas dan 0% y dos que difieren en todos los
    pixeles dan 100%."""

    a = imagen_de_prueba(32, 32)
    assert calcular_npcr(a, a) == 0.0
    assert calcular_npcr(a, (a + 1).astype(np.uint8)) == 100.0


def test_uaci_no_envuelve_al_restar_uint8():
    """250 - 10 = 240 pero 10 - 250 = 16 en uint8. Restar sin ampliar el
    tipo da diferencias envueltas y una UACI silenciosamente
    equivocada."""

    a = np.array([[250, 10]], dtype=np.uint8)
    b = np.array([[10, 250]], dtype=np.uint8)
    assert calcular_uaci(a, b) == pytest.approx(240 / 255 * 100)


def test_comparar_formas_distintas_es_un_error():
    with pytest.raises(ValueError, match="misma forma"):
        calcular_npcr(imagen_de_prueba(8, 8), imagen_de_prueba(8, 9))
    with pytest.raises(ValueError, match="misma forma"):
        calcular_uaci(imagen_de_prueba(8, 8), imagen_de_prueba(9, 8))


# --- chi2 --------------------------------------------------------------


def test_chi2_de_una_fuente_uniforme_ronda_255(rng):
    """Media 255 y sigma sqrt(2*255) = 22.58, con 255 grados de
    libertad."""

    img = rng.integers(0, 256, 65536, dtype=np.uint8).reshape(256, 256)
    assert abs(chi2_histograma(img) - CHI2_MEDIA) < 4 * sigma_chi2()


def test_chi2_dispara_con_un_histograma_sesgado():
    """La imagen de prueba tiene un cuadrante plano y bandas de dos
    valores: su histograma esta lejisimos de la uniforme."""

    assert chi2_histograma(imagen_de_prueba()) > CHI2_CRITICO_5PCT


def test_chi2_del_cifrado_no_rechaza_la_uniformidad_por_ninguna_cola():
    """El test es de DOS COLAS y hay que decirlo: un chi2 por encima del
    critico rechaza la uniformidad, y uno sospechosamente bajo indica que
    algo esta forzando el histograma a ser demasiado uniforme para ser
    aleatorio."""

    cifrada = cifrar_imagen(imagen_de_prueba(), CLAVE).datos
    medido = chi2_histograma(cifrada)
    assert medido < CHI2_CRITICO_5PCT
    assert medido > CHI2_MEDIA - 4 * sigma_chi2()


def test_chi2_de_metrics_y_de_keystream_son_el_mismo_estadistico():
    """chi2_histograma (3.7, sobre imagenes) delega en histograma_chi2
    (3.4, sobre keystreams). Si alguien duplica la formula, este test lo
    caza en cuanto las dos versiones se separen."""

    cifrada = cifrar_imagen(imagen_de_prueba(64, 64), CLAVE).datos
    assert chi2_histograma(cifrada) == histograma_chi2(cifrada.ravel())


def test_la_cuantizacion_ingenua_falla_el_chi2_y_la_buena_no():
    """El gemelo del test de la tarea 3.4, desde el lado de las metricas:
    int(x*256) hereda el sesgo de la densidad invariante
    rho(x) = 1/(pi sqrt(x(1-x))) y su histograma es rechazado por goleada;
    quedarse con los bits bajos no."""

    orb = orbita_logistica(0.4, 4.0, 100_000)
    ingenua = (orb * 256).astype(np.uint8)
    buena = ((orb * ESCALA_BITS).astype(np.uint64) & 0xFF).astype(np.uint8)
    assert chi2_histograma(ingenua) > CHI2_CRITICO_5PCT
    assert chi2_histograma(buena) < CHI2_CRITICO_5PCT


# --- La fila de la tabla -----------------------------------------------


def test_medir_imagen_devuelve_la_fila_completa():
    img = imagen_de_prueba()
    cifrada = cifrar_imagen(img, CLAVE).datos
    fila = medir_imagen("caotico", img, cifrada)

    assert fila.etiqueta == "caotico"
    assert fila.entropia == entropia_shannon(cifrada)
    assert fila.entropia_esperada == entropia_esperada(img.size)
    assert abs(fila.entropia - fila.entropia_esperada) < 4 * sigma_entropia(img.size)
    assert fila.chi2 == chi2_histograma(cifrada)
    tolerancia = 4 * sigma_correlacion(5000)
    assert abs(fila.corr_horizontal) < tolerancia
    assert abs(fila.corr_vertical) < tolerancia
    assert abs(fila.corr_diagonal) < tolerancia


def test_medir_imagen_no_se_inventa_npcr_ni_uaci():
    """NPCR y UACI comparan DOS CIFRADOS de imagenes que difieren en un
    pixel, no un plano con su cifrado. Rellenarlos aqui daria un numero
    de aspecto correcto que no mide sensibilidad diferencial ninguna."""

    img = imagen_de_prueba(32, 32)
    fila = medir_imagen("caotico", img, cifrar_imagen(img, CLAVE).datos)
    assert fila.npcr is None
    assert fila.uaci is None


def test_medir_imagen_exige_que_sean_la_misma_imagen():
    with pytest.raises(ValueError, match="misma forma"):
        medir_imagen("x", imagen_de_prueba(8, 8), imagen_de_prueba(16, 16))
