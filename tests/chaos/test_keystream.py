import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pytest
from chaos import (
    ClaveCaotica,
    chi2_histograma,
    detectar_ciclo,
    difundir_adelante,
    keystream,
    keystream_logistico,
    orbita_logistica,
)
from chaos.types import ESCALA_BITS


def test_vector_de_prueba():
    """EL test del modulo. Si esto falla en el contenedor y pasa en
    local, el determinismo esta roto y nada mas importa."""

    v = json.loads(Path("vectors/keystream_v1.json").read_text())
    ks = keystream_logistico(ClaveCaotica(**v["clave"], sistema="logistico"), 1_000_000)
    assert ks[:64].tobytes().hex() == v["primeros_64_bytes_hex"]
    assert hashlib.sha256(ks.tobytes()).hexdigest() == v["sha256_de_1e6_bytes"]


def test_la_cuantizacion_ingenua_falla_el_chi2():
    """Demuestra que la decision de diseno sirve. Sin este test, el
    codigo malo pasaria igual el test de arriba."""

    orb = orbita_logistica(0.4, 4.0, 100_000)
    ingenua = (orb * 256).astype(np.uint8)  # bits ALTOS
    buena = ((orb * ESCALA_BITS).astype(np.uint64) & 0xFF).astype(np.uint8)
    assert chi2_histograma(ingenua) > 293.25  # RECHAZA uniformidad
    assert chi2_histograma(buena) < 293.25  # no la rechaza


def test_sensibilidad_a_la_clave():
    """1e-15 en x0 => keystreams sin relacion. Es el Lyapunov en accion."""

    a = keystream_logistico(ClaveCaotica("logistico", 0.4, r=3.99), 10_000)
    b = keystream_logistico(ClaveCaotica("logistico", 0.4 + 1e-15, r=3.99), 10_000)
    coincidencias = np.count_nonzero(a == b)
    esperado = 10_000 / 256
    sigma = np.sqrt(esperado * (1 - 1 / 256))
    assert abs(coincidencias - esperado) < 4 * sigma


@pytest.mark.slow
def test_ciclo_medido_y_publicado():
    """Floyd sobre la orbita. No exige un minimo: MIDE y avisa.

    MARCADO `slow` EN LA TAREA 3.9: detectar_ciclo compara de uno en uno
    con np.allclose y recorrer dos millones de pasos asi cuesta 80 s, la
    segunda factura mas grande de la suite. La CI lo sigue ejecutando en
    los push a main. La comprobacion barata del mismo hecho -que el
    modulo AVISA cuando la orbita cicla- esta unas lineas mas abajo y
    corre en cada PR.
    """

    orb = orbita_logistica(0.4, 3.99, 2_000_000)
    ciclo = detectar_ciclo(orb)
    assert ciclo is None or ciclo > 1_000_000


@pytest.mark.parametrize("r,periodo", [(3.2, 2), (3.5, 4)])
def test_floyd_encuentra_un_ciclo_de_longitud_CONOCIDA(r, periodo):
    """El companero rapido de test_ciclo_medido_y_publicado (tarea 3.9).

    Aquel comprueba que una orbita caotica NO cicla en dos millones de
    pasos, que es lo que hay que publicar, pero cuesta 80 s y no verifica
    que detectar_ciclo sepa contar: un `return None` constante lo pasaria
    igual de bien. Este mide contra periodos que la teoria fija -r = 3.2 da
    periodo 2 y r = 3.5 periodo 4, las dos primeras duplicaciones de la
    cascada- y tarda un milisegundo.
    """
    assert detectar_ciclo(orbita_logistica(0.4, r, 3000)) == periodo


@pytest.mark.parametrize("sistema", ["logistico", "lorenz"])
@pytest.mark.parametrize("n_bytes", [1, 2, 3, 4, 100, 1021])
def test_el_keystream_mide_exactamente_lo_que_se_le_pide(sistema, n_bytes):
    """Caso borde de la tarea 3.9, primera mitad: un
    keystream mas corto que la imagen no se puede truncar en silencio.

    La primera linea de defensa es que no ocurra: `keystream` devuelve
    EXACTAMENTE los bytes pedidos o ninguno. Se prueban tamanos que no son
    multiplo de nada (1021) y los cuatro primeros, porque Lorenz saca TRES
    bytes por paso y redondea hacia arriba el numero de pasos: si el
    recorte final se hiciera mal, un n_bytes no multiplo de 3 devolveria
    uno o dos bytes de mas, y el desalineamiento apareceria en el
    descifrado y no aqui.
    """
    clave = (
        ClaveCaotica("logistico", 0.4, r=3.99)
        if sistema == "logistico"
        else ClaveCaotica("lorenz", 1.0, y0=1.0, z0=1.0)
    )
    ks = keystream(clave, n_bytes)
    assert ks.size == n_bytes
    assert ks.dtype == np.uint8


def test_un_keystream_corto_da_error_y_no_cifra_a_medias():
    """Segunda mitad del mismo caso borde: si a pesar de todo llega a la
    difusion un keystream mas corto que los datos, tiene que ser un error
    CLARO y no un cifrado truncado.

    Es el tercero de los errores tipicos de la tarea 3.6: un
    keystream regenerado con otra longitud desalinea el flujo desde el
    primer byte, y el sintoma -ruido- es identico al de un descifrado
    correcto de datos cifrados. Silencio aqui es el fallo silencioso del
    determinismo otra vez.
    """
    clave = ClaveCaotica("logistico", 0.4, r=3.99)
    datos = np.zeros(1000, dtype=np.uint8)
    corto = keystream(clave, 999)

    with pytest.raises(ValueError, match="longitudes") as error:
        difundir_adelante(datos, corto, 0)
    # El mensaje dice los DOS numeros: sin ellos hay que instrumentar el
    # codigo para saber cual de las dos longitudes es la equivocada.
    assert "999" in str(error.value) and "1000" in str(error.value)


def test_el_modulo_avisa_si_la_orbita_cicla(caplog):
    """Caso borde de la tarea 3.9: ciclo mas corto que
    la imagen, aviso explicito.

    Cualquier orbita en float64 es periodica, y eso no se puede resolver:
    lo que el modulo hace es MEDIRLO y avisar. r = 3.2 da periodo 2,
    asi que el keystream son dos bytes repetidos hasta el final: el caso
    extremo del que hay que enterarse.

    El aviso es logging.WARNING y no una excepcion a proposito: un ciclo
    corto no rompe la reversibilidad (la imagen se sigue descifrando bien),
    rompe la SEGURIDAD, y quien llama tiene que poder distinguir las dos
    cosas. Convencion del equipo: logging, nunca print.
    """
    clave_ciclica = ClaveCaotica("logistico", 0.4, r=3.2)
    with caplog.at_level(logging.WARNING, logger="chaos.keystream"):
        ks = keystream(clave_ciclica, 300)

    assert "CICLA" in caplog.text
    assert "300" in caplog.text
    # Y el motivo del aviso, medido: el flujo tiene dos valores distintos.
    assert len(set(ks.tolist())) <= 2

    # La contraparte, que es la que evita un test que "pasa" siempre: con
    # una clave caotica de verdad el modulo NO avisa de nada.
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="chaos.keystream"):
        keystream(ClaveCaotica("logistico", 0.4, r=3.99), 300)
    assert caplog.text == ""


def test_el_aviso_de_ciclo_tambien_vigila_a_lorenz(caplog):
    """La misma vigilancia para el segundo sistema. Aqui el estado es el
    vector (x, y, z) entero, no un escalar: un valor de x repetido es
    condicion necesaria pero NO suficiente para que la orbita cicle (dos
    pasos distintos pueden compartir la x y diferir en z), asi que el
    modulo compara las filas completas antes de avisar.

    Con los parametros clasicos Lorenz no cicla, y eso es lo que se
    comprueba: que la criba barata no produce un aviso falso.
    """
    with caplog.at_level(logging.WARNING, logger="chaos.keystream"):
        keystream(ClaveCaotica("lorenz", 1.0, y0=1.0, z0=1.0), 3000)
    assert caplog.text == ""
