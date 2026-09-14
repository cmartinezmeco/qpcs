"""tests/chaos/test_integration.py - tarea 3.9. El arco completo del modulo 3.

Cada pieza tiene ya sus tests (test_maps, test_lyapunov, test_keystream,
test_permutation, test_diffusion, test_cipher, test_metrics, test_baseline).
Lo que falta, y es lo que hay aqui, es el modulo recorrido de una vez:

    la CLAVE define una ORBITA, la orbita define un KEYSTREAM,
    y el keystream define completamente el CIFRADO

Esa cadena causal es la idea central del modulo, y no hay ninguna otra fuente
de aleatoriedad en ella: cero np.random en el camino. Si
alguna pieza se rompe al integrarse con otra -un contrato que cambia, una
longitud que se deriva de otra cosa, una permutacion que se aplica en el orden
equivocado-, es aqui donde se ve, y no en la demo.

Este fichero se ocupa ademas de dos criterios de cierre que NO son de ninguna
tarea en concreto porque son del modulo entero: que ninguna funcion
del camino del keystream use funciones trascendentes, y que no haya np.random
dentro de cipher.py. Los dos estaban escritos como "criterio de revision de
PR", es decir, confiados a que un humano se acuerde de mirarlos en cada PR.
Aqui pasan a comprobarse solos.
"""

import ast
from pathlib import Path

import numpy as np
import pytest
from chaos import (
    ClaveCaotica,
    chi2_histograma,
    cifrar_aes_gcm,
    cifrar_flujo_trivial,
    cifrar_imagen,
    correlacion_adyacente,
    descifrar_imagen,
    entropia_esperada,
    entropia_shannon,
    imagen_de_prueba,
    invertir_permutacion,
    keystream,
    lyapunov_logistico,
    medir_imagen,
    permutacion_desde_orbita,
)
from chaos.cipher import _valores_de_permutacion

from .tolerancias import (
    CHI2_MEDIA,
    sigma_chi2,
    sigma_correlacion,
    sigma_entropia,
)

CLAVE = ClaveCaotica("logistico", 0.4, r=3.99)
CLAVE_AES = bytes(range(32))

# Los ficheros por los que pasa un byte de keystream desde la orbita hasta la
# imagen cifrada. lyapunov.py NO esta en la lista y es deliberado: usa np.log
# a conciencia, pero lambda es un DIAGNOSTICO que decide si la clave sirve y
# no entra en el keystream, asi que puede diferir en el ultimo bit entre dos
# libm sin que nadie se entere. metrics.py tampoco:
# mide el resultado, no lo produce.
CAMINO_DEL_KEYSTREAM = (
    "maps.py",
    "keystream.py",
    "permutation.py",
    "diffusion.py",
    "cipher.py",
)

# exp, log, sin, cos y pow NO estan obligadas a ser correctamente redondeadas
# por IEEE-754: cada libm elige su compromiso entre precision y velocidad, y
# la misma llamada puede diferir en el ultimo bit entre dos versiones de glibc
# o entre x86 y ARM. En una orbita caotica ese ultimo bit se come la imagen
# entera en ~50 iteraciones.
#
# La lista incluye ademas sqrt y cbrt, y conviene explicar por que, porque
# no es por el mismo motivo:
#
#   - cbrt no esta garantizada por IEEE-754. Entra por la misma puerta que
#     exp y log.
#   - sqrt SI esta garantizada, asi que prohibirla es ser mas estricto de
#     lo que el determinismo exige. Se prohibe igual porque las dos
#     dinamicas del modulo son sumas, restas y multiplicaciones y nada mas:
#     una raiz cuadrada aparecida en el camino del keystream significa que
#     alguien ha cambiado la dinamica, y eso hay que mirarlo aunque el
#     resultado sea bit a bit reproducible.
#
# Es decir: la lista mezcla "esto rompe el determinismo" con "esto no
# deberia estar aqui de todas formas". Las dos razones valen para dejar la
# CI en rojo, y la segunda no es menos util que la primera.
TRASCENDENTES = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "arcsin",
        "arccos",
        "arctan",
        "arctan2",
        "sinh",
        "cosh",
        "tanh",
        "exp",
        "exp2",
        "expm1",
        "log",
        "log2",
        "log10",
        "log1p",
        "power",
        "float_power",
        "sqrt",
        "cbrt",
    }
)

DIR_FUENTE = Path(__file__).resolve().parents[2] / "src" / "chaos"


def _llamadas_con_prefijo(fuente: str, prefijos: frozenset[str]) -> list[str]:
    """Nombres llamados como `prefijo.algo(...)` en el codigo de `fuente`.

    Se recorre el AST y no el texto a proposito: buscar "np.log" con un grep
    encontraria tambien la palabra dentro de un docstring que EXPLICA por que
    no se usa np.log, que es precisamente lo que este modulo tiene en varios
    sitios. Solo cuentan las llamadas de verdad.
    """
    encontradas: list[str] = []
    for nodo in ast.walk(ast.parse(fuente)):
        if not isinstance(nodo, ast.Call):
            continue
        funcion = nodo.func
        if isinstance(funcion, ast.Attribute) and isinstance(funcion.value, ast.Name):
            if funcion.value.id in prefijos:
                encontradas.append(f"{funcion.value.id}.{funcion.attr}")
    return encontradas


def test_el_arco_completo_del_modulo():
    """La cadena entera del modulo, paso a paso y en un solo test.

    Clave -> validacion del caos -> keystream -> permutacion -> difusion ->
    imagen cifrada -> metricas -> descifrado exacto. Cada eslabon se
    comprueba donde se produce, para que un fallo diga QUE paso se rompio y
    no solo "el round-trip no cuadra".
    """
    # 1. La clave define una orbita, y la orbita es caotica: se MIDE, no se
    #    supone (tarea 3.3). Sin esto el resto del arco no deberia ocurrir.
    diagnostico = lyapunov_logistico(CLAVE.x0, CLAVE.r)
    assert diagnostico.es_caotico
    assert diagnostico.lyapunov > 0.0

    img = imagen_de_prueba()
    m = img.size

    # 2. La orbita define un keystream, y el keystream es plano: si el
    #    histograma estuviera sesgado (la cuantizacion ingenua con bits altos),
    #    el cifrado heredaria el sesgo y todo lo de abajo se hundiria.
    flujo = keystream(CLAVE, 2 * m + 2)
    assert flujo.size == 2 * m + 2
    assert abs(chi2_histograma(flujo) - CHI2_MEDIA) < 4 * sigma_chi2()

    # 3. La permutacion mueve pixeles sin tocar valores: rompe la correlacion
    #    espacial y deja el histograma INTACTO. Las dos mitades de la tesis.
    sigma = permutacion_desde_orbita(_valores_de_permutacion(CLAVE, m), m)
    permutada = img.ravel()[sigma]
    np.testing.assert_array_equal(
        np.bincount(img.ravel(), minlength=256),
        np.bincount(permutada, minlength=256),
    )
    np.testing.assert_array_equal(permutada[invertir_permutacion(sigma)], img.ravel())

    # 4. La difusion aplana el histograma, que es lo que la permutacion no
    #    puede hacer. Aqui ya es el cifrado completo del orquestador.
    cifrada = cifrar_imagen(img, CLAVE)
    assert cifrada.alto == img.shape[0] and cifrada.ancho == img.shape[1]
    assert cifrada.datos.dtype == np.uint8

    # 5. Las metricas: la imagen de partida tiene estructura y la cifrada no.
    assert entropia_shannon(img) < 7.5
    assert correlacion_adyacente(img, "horizontal") > 0.9
    fila = medir_imagen("caotico", img, cifrada.datos)
    assert abs(fila.entropia - entropia_esperada(m)) < 4 * sigma_entropia(m)
    tolerancia_r = 4 * sigma_correlacion(5000)
    assert abs(fila.corr_horizontal) < tolerancia_r
    assert abs(fila.corr_vertical) < tolerancia_r
    assert abs(fila.corr_diagonal) < tolerancia_r

    # 6. Y el cierre del arco: se recupera la imagen bit a bit. Sin esto lo
    #    anterior solo demuestra que el modulo destruye informacion, que es
    #    facil; lo dificil es destruirla de forma reversible.
    np.testing.assert_array_equal(descifrar_imagen(cifrada, CLAVE), img)


@pytest.mark.parametrize("sistema", ["logistico", "lorenz"])
def test_los_dos_sistemas_recorren_la_misma_cadena(sistema):
    """El modulo tiene DOS dinamicas y una sola cadena de cifrado.

    Es el test que caza que Lorenz funcione "por su cuenta" con un camino
    distinto: misma API, mismo contenedor, mismo round-trip exacto y misma
    entropia de salida. La imagen es pequena porque RK4 evalua el campo
    cuatro veces por paso y va dos ordenes de magnitud mas lento por muestra
    que el mapa logistico.
    """
    clave = (
        CLAVE if sistema == "logistico" else ClaveCaotica("lorenz", 1.0, y0=1.0, z0=1.0)
    )
    img = imagen_de_prueba(48, 48)
    cifrada = cifrar_imagen(img, clave)

    assert cifrada.sistema == sistema
    assert not np.array_equal(cifrada.datos, img)
    medida = entropia_shannon(cifrada.datos)
    assert abs(medida - entropia_esperada(img.size)) < 4 * sigma_entropia(img.size)
    np.testing.assert_array_equal(descifrar_imagen(cifrada, clave), img)


def test_ninguna_de_las_dos_etapas_basta_sola():
    """El argumento del modulo, medido de punta a punta en vez de citado.

    - Solo permutacion: el histograma de la "cifrada" es IDENTICO al del
      original, asi que el chi2 la delata inmediatamente. Un atacante que
      vea el histograma sabe que imagen es de un conjunto conocido.
    - Solo difusion sin encadenar: las zonas planas del original producen
      zonas del cifrado que son literalmente el keystream, asi que dos
      cifrados de la misma clave se restan y dejan el XOR de los planos.

    Las dos juntas se cubren los flancos, y por eso el esquema tiene las
    dos. Lo que NO arreglan es la reutilizacion de clave, que sigue en
    "Limitaciones conocidas".
    """
    img = imagen_de_prueba()
    m = img.size
    sigma = permutacion_desde_orbita(_valores_de_permutacion(CLAVE, m), m)

    solo_permutada = img.ravel()[sigma].reshape(img.shape)
    chi2_original = chi2_histograma(img)
    assert chi2_histograma(solo_permutada) == pytest.approx(chi2_original)
    assert chi2_original > 293.25  # el histograma delata la imagen de partida

    # XOR simple con el flujo, sin encadenar y sin permutar: la zona plana
    # de la imagen de prueba se convierte en keystream puro.
    flujo = keystream(CLAVE, m)
    solo_difundida = (img.ravel() ^ flujo).reshape(img.shape)
    plano = img.ravel()[:64]
    assert len(set(plano.tolist())) == 1, "la esquina de la imagen es plana"
    np.testing.assert_array_equal(
        solo_difundida.ravel()[:64] ^ int(plano[0]), flujo[:64]
    )

    # Y la cadena completa, que si aplana el histograma.
    cifrada = cifrar_imagen(img, CLAVE)
    assert abs(chi2_histograma(cifrada.datos) - CHI2_MEDIA) < 4 * sigma_chi2()


def test_las_tres_columnas_se_miden_con_las_mismas_funciones():
    """La tesis del modulo, integrada: el esquema caotico, AES-256-GCM y el
    flujo trivial pasan por medir_imagen y salen indistinguibles.

    Aqui no se repiten los margenes de test_baseline (alli estan al
    detalle): lo que se comprueba es que las tres columnas se pueden medir
    con la MISMA funcion sobre la MISMA imagen, que es lo que hace que la
    tabla del README sea una comparacion y no tres medidas sueltas.
    """
    img = imagen_de_prueba(128, 128)
    n = img.size
    columnas = {
        "caotico": cifrar_imagen(img, CLAVE).datos,
        "AES-256-GCM": cifrar_aes_gcm(img, CLAVE_AES)[0],
        "contador": cifrar_flujo_trivial(img, CLAVE_AES),
    }
    tolerancia_h = 4 * sigma_entropia(n)
    for etiqueta, datos in columnas.items():
        fila = medir_imagen(etiqueta, img, datos)
        assert fila.etiqueta == etiqueta
        assert abs(fila.entropia - entropia_esperada(n)) < tolerancia_h, etiqueta
        # npcr y uaci se quedan a None a proposito: comparan DOS cifrados,
        # no un plano con su cifrado (ver el docstring de medir_imagen).
        assert fila.npcr is None and fila.uaci is None


@pytest.mark.parametrize("fichero", CAMINO_DEL_KEYSTREAM)
def test_el_camino_del_keystream_no_usa_funciones_trascendentes(fichero):
    """Criterio de cierre del modulo, automatizado.

    Nacio como "criterio de revision de PR", es decir, confiado a que
    alguien se acuerde de mirarlo. Un test no se olvida.

    El motivo: IEEE-754 garantiza que suma, resta, multiplicacion,
    division y raiz cuadrada estan correctamente redondeadas, y NO
    garantiza nada de exp, log, sin, cos o pow. Las dos dinamicas del
    modulo caen enteras dentro de lo garantizado -son solo sumas, restas y
    multiplicaciones- y por eso el determinismo entre plataformas es
    alcanzable. Un np.sin colado aqui para "mejorar la mezcla" lo perderia
    sin dar ningun sintoma hasta que una imagen cifrada en una maquina no
    se descifra en otra.

    La lista prohibe ademas sqrt, que si esta garantizada por la norma. No
    es un descuido: el comentario de TRASCENDENTES explica que ahi la lista
    va a proposito mas alla del determinismo, porque una raiz cuadrada en
    el camino del keystream delata un cambio de dinamica que hay que
    revisar aunque sea reproducible.
    """
    fuente = (DIR_FUENTE / fichero).read_text(encoding="utf-8")
    llamadas = _llamadas_con_prefijo(fuente, frozenset({"np", "numpy", "math"}))
    prohibidas = [
        llamada for llamada in llamadas if llamada.split(".")[1] in TRASCENDENTES
    ]
    assert not prohibidas, (
        f"{fichero} llama a {prohibidas} en el camino del keystream: IEEE-754 "
        f"no garantiza esas funciones bit a bit entre libm distintas"
    )


def test_no_hay_azar_en_el_camino_de_cifrado():
    """El otro criterio de cierre del modulo: ni un np.random en cipher.py.

    El modulo entero se apoya en que la clave sea la UNICA fuente de
    aleatoriedad. Un np.random en el camino de cifrado no
    rompe ningun test de round-trip -si el mismo proceso cifra y descifra,
    el estado global del generador podria hasta cuadrar- pero hace que la
    imagen no se descifre en otra ejecucion. Silencioso otra vez.

    testimg.py SI usa un Generator sembrado y esta bien: genera la imagen
    de PRUEBA, que es una entrada del cifrado, no parte de el.
    """
    for fichero in CAMINO_DEL_KEYSTREAM:
        fuente = (DIR_FUENTE / fichero).read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        usos = [
            nodo
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Attribute) and nodo.attr == "random"
        ]
        assert not usos, f"{fichero} toca np.random en el camino de cifrado"
