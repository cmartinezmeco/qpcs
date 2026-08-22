"""tests/chaos/test_permutation.py - tarea 3.5, la permutacion.

La permutacion mueve pixeles y NO altera valores: eso es lo que la hace
util (rompe la correlacion espacial) y lo que la hace insuficiente por si
sola (deja el histograma intacto). Los dos hechos se comprueban aqui.
"""

import hashlib

import numpy as np
import pytest
from chaos import (
    correlacion_adyacente,
    imagen_de_prueba,
    invertir_permutacion,
    orbita_logistica,
    permutacion_desde_orbita,
)

from .tolerancias import sigma_correlacion


def _sigma(m=4096, x0=0.4, r=3.99):
    """La permutacion de referencia del fichero, siempre la misma."""
    return permutacion_desde_orbita(orbita_logistica(x0, r, m + 1000), m)


def test_es_una_biyeccion():
    """Lo minimo: cada indice aparece exactamente una vez. Si no, hay
    pixeles duplicados y otros perdidos, y el cifrado no es invertible."""

    sigma = _sigma(4096)
    np.testing.assert_array_equal(np.sort(sigma), np.arange(4096))
    assert sigma.dtype == np.int64


@pytest.mark.parametrize("m", [1, 2, 3, 37, 100, 3700, 4093])
def test_es_biyeccion_para_tamanos_raros(m):
    """Incluidos primos (4093) y no cuadrados: la permutacion por
    ordenamiento no depende de la geometria de la imagen, que es una de
    las dos razones de no usar el mapa del gato de Arnold (cap. 5.2)."""

    sigma = _sigma(m)
    np.testing.assert_array_equal(np.sort(sigma), np.arange(m))


def test_la_inversa_deshace():
    """sigma_inv[sigma[i]] == i, y aplicada sobre una imagen permutada la
    devuelve exactamente igual."""

    sigma = _sigma(4096)
    inversa = invertir_permutacion(sigma)
    np.testing.assert_array_equal(inversa[sigma], np.arange(4096))

    img = imagen_de_prueba(64, 64).ravel()
    np.testing.assert_array_equal(img[sigma][inversa], img)


def test_el_histograma_NO_cambia():
    """Propiedad definitoria: permutar mueve pixeles, no los altera.
    Si el histograma cambia, la permutacion esta corrompiendo datos."""

    img = imagen_de_prueba(64, 64)
    sigma = _sigma(img.size)
    permutada = img.ravel()[sigma].reshape(img.shape)
    np.testing.assert_array_equal(
        np.bincount(img.ravel(), minlength=256),
        np.bincount(permutada.ravel(), minlength=256),
    )


def test_rompe_la_correlacion_espacial():
    """Y la contraparte: aunque el histograma no cambie, la correlacion
    entre pixeles adyacentes debe caer de ~0.95 a ~0.

    Las dos mitades de este test juntas son el argumento del cap. 5.1:
    la permutacion sola no basta (histograma intacto) pero hace falta
    (correlacion rota).
    """
    img = imagen_de_prueba()
    sigma = _sigma(img.size)
    permutada = img.ravel()[sigma].reshape(img.shape)

    assert correlacion_adyacente(img, "horizontal") > 0.9
    tolerancia = 4 * sigma_correlacion(5000)
    for direccion in ("horizontal", "vertical", "diagonal"):
        assert abs(correlacion_adyacente(permutada, direccion)) < tolerancia


def test_permutacion_no_cuadrada():
    """Caso borde: 100x37. El mapa del gato de Arnold no podria; esta
    implementacion si, y es una de las razones de elegirla (cap. 5.2)."""

    img = imagen_de_prueba(100, 37)
    sigma = _sigma(img.size)
    permutada = img.ravel()[sigma]
    np.testing.assert_array_equal(
        permutada[invertir_permutacion(sigma)].reshape(img.shape), img
    )


def test_el_argsort_es_estable():
    """kind="stable" no es una preferencia estetica: ante dos valores
    EXACTAMENTE iguales, el introsort por defecto de NumPy resuelve el
    empate de una forma que depende del algoritmo interno y puede cambiar
    entre versiones. Un solo empate resuelto al reves hace el cifrado
    irreversible en otra maquina (cap. 5.2).

    Aqui se fuerzan empates a proposito -en una orbita real son
    improbables, ~5e-7 por imagen de 256x256- y se exige el unico
    resultado que un orden estable puede dar: los empatados conservan su
    orden de aparicion.
    """
    valores = np.array([0.5, 0.1, 0.5, 0.1, 0.3], dtype=np.float64)
    np.testing.assert_array_equal(
        permutacion_desde_orbita(valores, 5), np.array([1, 3, 4, 0, 2])
    )


def test_permutacion_de_referencia_almacenada():
    """Detecta un cambio de comportamiento de NumPy o del generador de
    orbitas. El valor no se "arregla" regenerandolo: si esto falla, o ha
    cambiado orbita_logistica o ha cambiado argsort, y las dos cosas son
    noticia (misma logica que el vector de keystream de la tarea 3.4).

    El hash se toma sobre "<i8" explicito y no sobre el dtype nativo:
    int64 nativo es little-endian en x86 y big-endian en otras
    arquitecturas, y el test debe fallar por un cambio de comportamiento,
    no por el orden de los bytes de la maquina.
    """
    sigma = _sigma(4096, x0=0.4, r=3.99)
    assert sigma[:12].tolist() == [
        3865,
        1687,
        1166,
        3005,
        2614,
        2682,
        1246,
        563,
        3133,
        2287,
        3079,
        2480,
    ]
    digest = hashlib.sha256(sigma.astype("<i8").tobytes()).hexdigest()
    assert digest == "be7e1ca550c3314adc2b2ccf96fbc6b247299f6faf6740aae145996c2a3e97e7"


def test_orbita_corta_no_trunca_en_silencio():
    """Si la orbita no llega para m elementos, hay que dar un error, no
    una permutacion mas corta: una permutacion de menos elementos que la
    imagen deja pixeles fuera y el fallo seria silencioso."""

    orb = orbita_logistica(0.4, 3.99, 100)
    with pytest.raises(ValueError, match="100 valores"):
        permutacion_desde_orbita(orb, 4096)
