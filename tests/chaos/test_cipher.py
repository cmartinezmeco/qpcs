"""tests/chaos/test_cipher.py - tarea 3.6, el cifrado completo.

El round-trip exacto es EL test del modulo. Lo demas de este fichero mide
lo que el esquema hace de verdad, no lo que se le supone: hay una
limitacion real y medible en la avalancha frente a un cambio en el texto
plano, y esta escrita aqui con su derivacion en vez de dejada fuera.
"""

import time

import numpy as np
import pytest
from chaos import (
    ClaveCaotica,
    calcular_npcr,
    calcular_uaci,
    cifrar_imagen,
    correlacion_adyacente,
    descifrar_imagen,
    entropia_esperada,
    entropia_shannon,
    imagen_de_prueba,
    invertir_permutacion,
    permutacion_desde_orbita,
)

# Helper privado de cipher.py. Se importa a proposito: el test de la
# avalancha compara la implementacion contra la PREDICCION TEORICA de
# cuantos pixeles deben cambiar, y para calcularla hace falta saber en que
# posicion del array permutado cae el pixel que se ha tocado.
from chaos.cipher import _valores_de_permutacion

from .tolerancias import sigma_correlacion, sigma_entropia, sigma_npcr, sigma_uaci

CLAVE = ClaveCaotica("logistico", 0.4, r=3.99)


@pytest.mark.parametrize(
    "alto,ancho",
    [(256, 256), (128, 64), (100, 37), (1, 50), (50, 1), (3, 3)],
)
def test_round_trip_sin_perdida(alto, ancho):
    """EL test del modulo. Bit a bit, no 'aproximadamente'."""

    img = imagen_de_prueba(alto, ancho)
    np.testing.assert_array_equal(
        descifrar_imagen(cifrar_imagen(img, CLAVE), CLAVE), img
    )


def test_round_trip_de_una_imagen_de_un_solo_pixel():
    """Caso degenerado de la tabla de casos borde: cifra y
    descifra, no lanza."""

    img = np.array([[42]], dtype=np.uint8)
    np.testing.assert_array_equal(
        descifrar_imagen(cifrar_imagen(img, CLAVE), CLAVE), img
    )


@pytest.mark.parametrize("valor", [0, 255])
def test_imagen_constante_se_cifra_a_algo_con_entropia_maxima(valor):
    """Una imagen toda a cero (o toda a 255) tiene entropia 0 y su cifrado
    tiene que llegar al valor ESPERADO del estimador, no a 8.0 exacto,
    que es inalcanzable. Tolerancia derivada, 4 sigma."""

    img = np.full((256, 256), valor, dtype=np.uint8)
    cifrada = cifrar_imagen(img, CLAVE)

    assert entropia_shannon(img) == 0.0
    medida = entropia_shannon(cifrada.datos)
    esperada = entropia_esperada(img.size)
    assert abs(medida - esperada) < 4 * sigma_entropia(img.size)
    np.testing.assert_array_equal(descifrar_imagen(cifrada, CLAVE), img)


def test_el_cifrado_rompe_la_correlacion_en_las_tres_direcciones():
    """De ~0.95 en el original a ~0 en el cifrado, con la tolerancia
    derivada de 1/sqrt(n) y no con un 0.05 redondo."""

    img = imagen_de_prueba()
    cifrada = cifrar_imagen(img, CLAVE).datos
    tolerancia = 4 * sigma_correlacion(5000)
    for direccion in ("horizontal", "vertical", "diagonal"):
        assert correlacion_adyacente(img, direccion) > 0.9
        assert abs(correlacion_adyacente(cifrada, direccion)) < tolerancia


def test_dos_cifrados_de_lo_mismo_son_IGUALES():
    """Propiedad incomoda pero real: el esquema es DETERMINISTA, sin
    nonce. Cifrar dos veces con la misma clave da el mismo resultado.
    Se documenta como limitacion: es lo que hace que la
    reutilizacion de clave sea catastrofica, igual que en un one-time
    pad reutilizado. AES-GCM del baseline SI lleva nonce fresco."""

    img = imagen_de_prueba(64, 64)
    primero = cifrar_imagen(img, CLAVE)
    segundo = cifrar_imagen(img, CLAVE)
    np.testing.assert_array_equal(primero.datos, segundo.datos)
    assert primero.iv == segundo.iv
    assert primero.hash_plano == segundo.hash_plano


def test_la_reutilizacion_de_clave_filtra_la_estructura():
    """La consecuencia directa de lo anterior, medida en vez de citada:
    con la misma clave, el keystream se cancela ENTERO al hacer el XOR de
    dos cifrados, y lo que queda depende solo de los dos planos.

    La cuenta, siguiendo las dos pasadas:

        ida:    delta_c = XOR acumulado por prefijos de delta_p
        vuelta: delta_d = XOR acumulado por sufijos de delta_c

    con delta_p el XOR de los dos planos ya permutados. Ni k_ad, ni
    k_atr, ni los IV aparecen: son iguales en los dos cifrados y se
    anulan. Un atacante con dos cifrados de la misma clave recupera esa
    funcion de los dos planos sin saber nada de la clave.

    Es el ataque de reutilizacion de clave, y esta aqui
    porque una limitacion que solo aparece en el README es una limitacion
    que nadie ha comprobado.
    """
    a = imagen_de_prueba(64, 64)
    b = np.zeros_like(a)
    m = a.size

    ca = cifrar_imagen(a, CLAVE).datos.ravel()
    cb = cifrar_imagen(b, CLAVE).datos.ravel()

    sigma = permutacion_desde_orbita(_valores_de_permutacion(CLAVE, m), m)
    delta_permutado = a.ravel()[sigma] ^ b.ravel()[sigma]
    por_prefijos = np.bitwise_xor.accumulate(delta_permutado)
    por_sufijos = np.bitwise_xor.accumulate(por_prefijos[::-1])[::-1]
    np.testing.assert_array_equal(ca ^ cb, por_sufijos)


def test_no_muta_la_imagen_de_entrada():
    """Mutar la entrada in place destruye el original que el test de
    round-trip necesita, y el fallo se manifiesta como un test que pasa
    cuando no deberia.

    Se comprueban las dos direcciones: que cifrar no toca la imagen que
    recibe, y que descifrar no consume el contenedor cifrado. La segunda
    importa porque el contenedor se guarda para volver a usarlo -el panel
    lo descifra dos veces, con la clave buena y con la equivocada- y un
    descifrado que escribiera sobre sus propios datos haria que la segunda
    pasada devolviese basura sin avisar de nada.
    """

    img = imagen_de_prueba(64, 64)
    copia = img.copy()
    cifrada = cifrar_imagen(img, CLAVE)
    np.testing.assert_array_equal(img, copia)

    # La copia se toma ANTES de descifrar. Comparar cifrada.datos consigo
    # mismo despues de la llamada no comprueba nada: pasa siempre, mute o
    # no mute descifrar_imagen.
    cifrada_antes = cifrada.datos.copy()
    descifrar_imagen(cifrada, CLAVE)
    np.testing.assert_array_equal(cifrada.datos, cifrada_antes)
    np.testing.assert_array_equal(img, copia)


def test_la_clave_equivocada_no_descifra():
    """Una clave que difiere en 1e-15 devuelve ruido, no una imagen
    parcialmente reconocible: el resultado difiere del original en el
    99.6% de los pixeles, dentro de su intervalo de 4 sigma."""

    img = imagen_de_prueba()
    cifrada = cifrar_imagen(img, CLAVE)
    otra_clave = ClaveCaotica("logistico", 0.4 + 1e-15, r=3.99)

    basura = descifrar_imagen(cifrada, otra_clave)
    assert not np.array_equal(basura, img)
    assert abs(calcular_npcr(basura, img) - 99.6094) < 4 * sigma_npcr(img.size)


def test_sensibilidad_a_la_clave_en_NPCR_y_UACI():
    """Criterio de cierre 8: cambiar un solo bit de la clave
    produce dos cifrados que difieren en ~99.6% de los pixeles, con UACI
    en su valor teorico. Aqui SI se alcanzan los dos valores ideales,
    porque los dos keystreams son independientes entre si.

    Y el motivo es fisico: 1e-15 se amplifica como e^(lambda*n) y tras el
    transitorio de 1000 iteraciones las dos orbitas no tienen ninguna
    relacion. El descarte del transitorio no es higiene numerica, es lo
    que produce la sensibilidad a la clave.
    """
    img = imagen_de_prueba()
    c1 = cifrar_imagen(img, CLAVE).datos
    c2 = cifrar_imagen(img, ClaveCaotica("logistico", 0.4 + 1e-15, r=3.99)).datos

    assert abs(calcular_npcr(c1, c2) - 99.6094) < 4 * sigma_npcr(img.size)
    assert abs(calcular_uaci(c1, c2) - 33.4635) < 4 * sigma_uaci(img.size)


@pytest.mark.parametrize("posicion", ["primero", "ultimo", "medio"])
def test_avalancha_ante_un_cambio_en_el_plano(posicion):
    """LIMITACION MEDIDA, no supuesta. Leer entero antes de tocar nada.

    Lo que la literatura del campo espera es que cambiar un pixel del
    plano de NPCR ~99.6%. Con la difusion de este esquema, c_i = p_i XOR
    k_i XOR c_{i-1}, eso NO ocurre, y el motivo es algebraico:

      - El esquema completo (permutacion fija + XOR con un keystream que
        no depende del plano + encadenado XOR) es AFIN sobre GF(2). Por
        tanto C1 XOR C2 depende solo de P1 XOR P2, no de la clave ni de
        los valores de los pixeles.
      - En la pasada de ida, un delta en la posicion j se propaga
        IDENTICO a todas las posiciones t >= j: delta_c_t = delta.
      - En la pasada de vuelta, delta_d_t = delta_c_t XOR delta_d_{t+1},
        que sobre una cola constante alterna delta, 0, delta, 0...

    De ahi sale la formula exacta que este test compara contra la
    medicion: cambian las posiciones de la cola con (M-1-t) par, mas la
    cabeza entera si delta_d_j resulta ser delta. NPCR queda entre 0% y
    100% segun DONDE caiga el pixel tocado en el array permutado, con
    ~50% de media, y no en el 99.6094% del criterio de cierre.

    La consecuencia sobre UACI es aun mas dura y esta en el test
    siguiente.

    Este test NO es un test relajado para que pase el codigo: valida la
    implementacion contra la teoria del esquema tal y como esta
    especificado. Si alguien cambia la difusion para mezclar suma modular
    con XOR (que es lo que hace falta para alcanzar el 99.6%), este test
    fallara, y debe fallar: sera otro esquema.
    """
    img = imagen_de_prueba()
    m = img.size
    indice = {"primero": 0, "ultimo": m - 1, "medio": m // 2}[posicion]

    plano = img.ravel().copy()
    plano[indice] ^= 1
    otra = plano.reshape(img.shape)

    c1 = cifrar_imagen(img, CLAVE).datos
    c2 = cifrar_imagen(otra, CLAVE).datos

    sigma = permutacion_desde_orbita(_valores_de_permutacion(CLAVE, m), m)
    j = int(invertir_permutacion(sigma)[indice])
    cola = (m - 1 - j) // 2 + 1
    cabeza = j if (m - 1 - j) % 2 == 0 else 0
    npcr_predicho = 100.0 * (cola + cabeza) / m

    assert calcular_npcr(c1, c2) == pytest.approx(npcr_predicho, abs=1e-9)

    # Y la mitad que si cumple lo que se le pide a la pasada de vuelta:
    # con una sola pasada, tocar el ultimo pixel cambiaria UN byte. Con
    # las dos, cambian decenas de miles.
    assert calcular_npcr(c1, c2) > 100.0 / m


def test_uaci_diferencial_esta_acotada_por_la_linealidad_del_XOR():
    """La otra cara de lo anterior, y la mas concluyente.

    Como el esquema es afin sobre GF(2), C1 XOR C2 = delta en todas las
    posiciones afectadas, con delta = 1 si el cambio del plano fue un
    bit. Y |x - (x XOR 1)| = 1 para cualquier x. Por tanto toda
    diferencia de intensidad vale exactamente 1 y

        UACI = (fraccion de pixeles cambiados) * 1 / 255 * 100 <= 0.392%

    frente al 33.4635% del criterio de cierre. No es una cuestion de
    tolerancias: es un techo estructural del esquema especificado, y
    ninguna cantidad de pasadas XOR lo levanta. Alcanzar el 33.46%
    requiere que la difusion mezcle dos operaciones de grupo distintas
    (suma modular y XOR), que es lo que hace la literatura del campo.
    """
    img = imagen_de_prueba()
    plano = img.ravel().copy()
    plano[-1] ^= 1

    c1 = cifrar_imagen(img, CLAVE).datos
    c2 = cifrar_imagen(plano.reshape(img.shape), CLAVE).datos

    diferencias = np.abs(c1.astype(np.int16) - c2.astype(np.int16))
    assert set(np.unique(diferencias).tolist()) <= {0, 1}
    assert calcular_uaci(c1, c2) <= 100.0 / 255.0


def test_rechaza_una_clave_no_caotica():
    """r = 3.83 esta DENTRO del rango caotico nominal (3.57, 4] y sin
    embargo tiene periodo 3: el keystream serian tres bytes repetidos.
    El modulo calcula lambda y se niega, con un motivo legible."""

    img = imagen_de_prueba(32, 32)
    with pytest.raises(ValueError, match="no caotica"):
        cifrar_imagen(img, ClaveCaotica("logistico", 0.4, r=3.83))
    with pytest.raises(ValueError, match="no caotica"):
        cifrar_imagen(img, ClaveCaotica("logistico", 0.4, r=2.5))


def test_rechaza_entradas_que_no_son_una_imagen_de_8_bits():
    """uint8 siempre: un float en el camino del XOR es una conversion
    silenciosa."""

    with pytest.raises(ValueError, match="uint8"):
        cifrar_imagen(np.zeros((8, 8), dtype=np.float64), CLAVE)
    with pytest.raises(ValueError, match="bidimensional"):
        cifrar_imagen(np.zeros(64, dtype=np.uint8), CLAVE)


def test_el_sistema_del_contenedor_tiene_que_coincidir():
    """Descifrar un contenedor logistico con una clave de Lorenz no es un
    'no descifra': es un error de uso y se dice."""

    cifrada = cifrar_imagen(imagen_de_prueba(16, 16), CLAVE)
    lorenz = ClaveCaotica("lorenz", 1.0, y0=1.0, z0=1.0)
    with pytest.raises(ValueError, match="sistema"):
        descifrar_imagen(cifrada, lorenz)


def test_lorenz_tambien_cifra_y_descifra():
    """El segundo sistema del modulo, en una imagen pequena porque RK4 es
    caro: 88.000 pasos por segundo frente a los 13 millones de
    iteraciones por segundo del mapa logistico."""

    img = imagen_de_prueba(32, 32)
    clave = ClaveCaotica("lorenz", 1.0, y0=1.0, z0=1.0)
    cifrada = cifrar_imagen(img, clave)
    assert cifrada.sistema == "lorenz"
    np.testing.assert_array_equal(descifrar_imagen(cifrada, clave), img)
    assert not np.array_equal(cifrada.datos, img)


def test_lorenz_rechaza_un_rho_que_no_haria_nada():
    """clave.rho no lo lee nadie: keystream_lorenz integra con
    LORENZ_RHO, la constante del contrato. Aceptar un rho distinto seria
    tener un campo de la clave que no cambia el cifrado, es decir, un
    espacio de claves mas pequeno de lo que la clave aparenta."""

    img = imagen_de_prueba(8, 8)
    with pytest.raises(ValueError, match="rho"):
        cifrar_imagen(img, ClaveCaotica("lorenz", 1.0, y0=1.0, z0=1.0, rho=40.0))


def test_el_hash_del_plano_permite_verificar_el_descifrado():
    """hash_plano existe para que el dashboard pueda decir 'descifrado
    correcto' con fundamento. Filtra informacion y va documentado como
    limitacion, pero funciona."""

    import hashlib

    img = imagen_de_prueba(64, 64)
    cifrada = cifrar_imagen(img, CLAVE)
    recuperada = descifrar_imagen(cifrada, CLAVE)
    assert hashlib.sha256(recuperada.tobytes()).hexdigest() == cifrada.hash_plano


def test_cifra_512x512_en_menos_de_dos_segundos():
    """Criterio de cierre de la tarea 3.6. La cota es del enunciado; el
    tiempo real en el venv de referencia esta en torno a 0.4 s, asi que
    hay margen de sobra para el contenedor."""

    img = imagen_de_prueba(512, 512)
    inicio = time.perf_counter()
    cifrada = cifrar_imagen(img, CLAVE)
    transcurrido = time.perf_counter() - inicio
    assert transcurrido < 2.0, f"cifrar 512x512 tardo {transcurrido:.2f} s"
    np.testing.assert_array_equal(descifrar_imagen(cifrada, CLAVE), img)
