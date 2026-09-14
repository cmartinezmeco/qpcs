import numpy as np
import pytest
from chaos import (
    ClaveCaotica,
    cifrar_imagen,
    espectro_lyapunov_lorenz,
    imagen_de_prueba,
    lyapunov_logistico,
)
from chaos.types import LORENZ_BETA, LORENZ_SIGMA, UMBRAL_LYAPUNOV


def test_lyapunov_de_r4_es_ln2():
    """El valor exacto, no una referencia. Tolerancia DERIVADA del
    error estandar que devuelve el propio diagnostico."""

    d = lyapunov_logistico(0.4, 4.0, n=200_000)
    assert abs(d.lyapunov - np.log(2.0)) < 4 * d.sigma


@pytest.mark.parametrize(
    "r,esperado_caotico",
    [
        (2.5, False),  # punto fijo
        (3.2, False),  # periodo 2
        (3.5, False),  # periodo 4
        (3.83, False),  # LA VENTANA DE PERIODO 3 dentro del caos
        (3.9, True),
        (4.0, True),
    ],
)
def test_detecta_el_regimen(r, esperado_caotico):
    """El test que justifica la existencia de esta tarea: r = 3.83 esta
    DENTRO del rango caotico nominal (3.57, 4] y sin embargo NO es
    caotico. Un modulo que solo comprobara el rango lo aceptaria."""

    d = lyapunov_logistico(0.4, r)
    assert d.es_caotico == esperado_caotico


@pytest.mark.slow
def test_lorenz_espectro_suma_la_divergencia():
    """lambda_1 + lambda_2 + lambda_3 = -(sigma + 1 + beta) = -13.667.
    Verificacion independiente y gratis del integrador.

    MARCADO `slow` EN LA TAREA 3.9, y merece la explicacion porque es un
    test de fisica de los que el criterio de cierre exige: tarda 179 s el
    solo (50 000 renormalizaciones x 50 pasos de RK4 x 4 trayectorias en
    bucles de Python) y la suite rapida tiene que quedarse por debajo de
    los 60 segundos. Gratis en operaciones no significa gratis en reloj.

    No deja de ejecutarse: la CI corre `-m "slow"` en los push a main
    (.github/workflows/ci.yml), asi que sigue siendo una garantia
    continua, solo que no en cada PR. La comprobacion barata de que el
    algoritmo no se ha roto -signo de lambda_1, orden del espectro- se
    queda en la suite rapida, en el test de aqui abajo.
    """

    l1, l2, l3 = espectro_lyapunov_lorenz()
    divergencia = LORENZ_SIGMA + 1 + LORENZ_BETA
    assert abs((l1 + l2 + l3) + divergencia) < 0.5
    assert abs(l1 - 0.906) < 0.05
    assert abs(l2) < 0.05


def test_lorenz_espectro_tiene_la_forma_correcta_en_pocos_pasos():
    """El companero rapido del test de arriba: con 400 renormalizaciones no
    hay precision para exigir 0.906 +/- 0.05, pero SI para exigir la FORMA
    del espectro, que es lo que se rompe cuando alguien toca Benettin:

      - lambda_1 > 0 (la firma del caos),
      - lambda_2 ~ 0 (la direccion del propio flujo),
      - lambda_3 muy negativo (la contraccion del atractor disipativo),
      - y la suma, negativa, porque el sistema contrae volumen.

    Los dos bugs que la tarea 3.4 encontro en esta funcion (el desfase
    temporal de un tau y la ortogonalizacion en el orden equivocado) daban
    lambda_1 ~ 42 y tres exponentes iguales respectivamente: los dos habrian
    caido aqui, en dos segundos, sin esperar a los tres minutos del test
    completo. Las tolerancias son deliberadamente anchas: este test valida
    la ESTRUCTURA, y el valor exacto lo valida el `slow`.
    """
    l1, l2, l3 = espectro_lyapunov_lorenz(n=400)
    assert l1 > 0.5, "lambda_1 tiene que ser claramente positivo: es el caos"
    assert abs(l2) < 0.5, "lambda_2 es la direccion del flujo, tiene que ser ~0"
    assert l3 < -5.0, "lambda_3 es la contraccion fuerte del atractor"
    assert l1 + l2 + l3 < 0.0, "un sistema disipativo contrae volumen"


def test_la_ventana_periodica_se_diagnostica_Y_se_rechaza():
    """Caso borde de la tarea 3.9: con r en una ventana
    periodica el modulo NO cifra, lanza ValueError.

    Este test existe aparte del parametrico de arriba porque comprueba otra
    cosa: alli se mide que lambda sale negativo, aqui que ese diagnostico
    LLEGA HASTA EL CIFRADO. Son dos fallos distintos -calcular mal lambda y
    calcularlo bien pero no mirarlo- y el segundo es el que dejaria cifrar
    con una secuencia de periodo 3 sin que nadie se entere.

    r = 3.83 es la trampa del modulo: esta DENTRO del rango caotico nominal
    (3.57, 4], asi que un modulo que solo comprobara el rango lo aceptaria.
    """
    diagnostico = lyapunov_logistico(0.4, 3.83)
    assert not diagnostico.es_caotico
    assert diagnostico.lyapunov < UMBRAL_LYAPUNOV

    with pytest.raises(ValueError, match="no caotica") as error:
        cifrar_imagen(imagen_de_prueba(16, 16), ClaveCaotica("logistico", 0.4, r=3.83))
    # "Explicito" del enunciado significa que el mensaje diga el numero y el
    # motivo, no un "clave invalida" que obligue a leer el codigo fuente.
    assert "lambda" in str(error.value)
    assert "3.83" in str(error.value)
