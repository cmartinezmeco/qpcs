"""tests/pqc/test_hybrid.py - tarea 2.5 (cifrado hibrido KEM + AES-GCM).

Aqui esta EL test del bloque PQC del criterio de cierre: se cifra un mensaje
real con criptografia post-cuantica y se recupera identico. Y su contrapartida,
que es la que de verdad prueba seguridad: manipular un solo byte del cifrado se
detecta con InvalidTag.

Sin semilla, como todo lo de cripto real: se validan propiedades (round-trip,
deteccion de manipulacion, frescura del nonce), nunca valores fijos.
"""

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# _clave_aes es privada a proposito; se importa SOLO aqui, y solo para poder
# abrir el sobre por el mismo sitio que lo abre el receptor y comprobar que el
# AAD esta atado al mecanismo. Ningun otro test depende de un nombre privado.
from pqc.hybrid import _clave_aes, cifrar_mensaje, descifrar_mensaje
from pqc.kem import kem_desencapsular, kem_generar
from pqc.types import MensajeCifrado

MENSAJE = b"La criptografia post-cuantica protege esto en 2035."


def _con_aead_alterado(sobre: MensajeCifrado) -> MensajeCifrado:
    """Devuelve el mismo sobre con un bit cambiado en el texto cifrado.

    Se reconstruye el dataclass en vez de mutarlo porque MensajeCifrado es
    frozen=True (contrato de types.py: un resultado no se muta).
    """
    alterado = bytes([sobre.aead_ciphertext[0] ^ 0x01]) + sobre.aead_ciphertext[1:]
    return MensajeCifrado(sobre.kem_ciphertext, sobre.nonce, alterado, sobre.mecanismo)


def test_cifrado_hibrido_roundtrip():
    """EL test del bloque PQC: se cifra un mensaje real y se recupera igual."""
    clave_publica, clave_privada = kem_generar("ML-KEM-768")
    sobre = cifrar_mensaje(clave_publica, MENSAJE, "ML-KEM-768")
    assert descifrar_mensaje(clave_privada, sobre) == MENSAJE


def test_el_sobre_lleva_lo_que_dice_el_contrato():
    """Forma del MensajeCifrado: ciphertext del KEM, nonce de 12 B, AEAD y el
    mecanismo con nomenclatura NIST. El nonce de 12 es el tamano nativo de GCM."""
    clave_publica, _ = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE)
    assert sobre.mecanismo == "ML-KEM-768"
    assert len(sobre.kem_ciphertext) == 1088
    assert len(sobre.nonce) == 12
    # AES-GCM anade 16 bytes de tag y no infla el texto: es un cifrado de flujo.
    assert len(sobre.aead_ciphertext) == len(MENSAJE) + 16


def test_manipular_el_cifrado_lo_detecta():
    """AES-GCM rechaza un cifrado alterado (autenticacion).

    Sin AEAD, cambiar un bit devolveria basura descifrada sin avisar. Con GCM
    el tag no cuadra y no sale ni un byte de texto en claro.
    """
    clave_publica, clave_privada = kem_generar()
    sobre = cifrar_mensaje(clave_publica, b"intacto")
    with pytest.raises(InvalidTag):
        descifrar_mensaje(clave_privada, _con_aead_alterado(sobre))


def test_manipular_el_kem_ciphertext_lo_detecta():
    """La otra via de manipulacion, la que ML-KEM no denuncia por si sola.

    Tocar el kem_ciphertext no hace fallar al KEM (rechazo implicito, ver
    test_kem.py): devuelve otro secreto, el HKDF da otra clave AES y es el tag
    de GCM el que acaba cazandolo. Misma InvalidTag por otro camino.
    """
    clave_publica, clave_privada = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE)
    roto = MensajeCifrado(
        bytes([sobre.kem_ciphertext[0] ^ 0x01]) + sobre.kem_ciphertext[1:],
        sobre.nonce,
        sobre.aead_ciphertext,
        sobre.mecanismo,
    )
    with pytest.raises(InvalidTag):
        descifrar_mensaje(clave_privada, roto)


def test_manipular_el_nonce_lo_detecta():
    """El nonce entra en el calculo del tag: cambiarlo tambien invalida."""
    clave_publica, clave_privada = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE)
    roto = MensajeCifrado(
        sobre.kem_ciphertext,
        bytes([sobre.nonce[0] ^ 0x01]) + sobre.nonce[1:],
        sobre.aead_ciphertext,
        sobre.mecanismo,
    )
    with pytest.raises(InvalidTag):
        descifrar_mensaje(clave_privada, roto)


@pytest.mark.parametrize(
    "mecanismo_falso",
    [
        "Kyber768-inventado",  # no existe: liboqs levantaria MechanismNotSupported
        "ML-KEM-1024",  # existe y es MAYOR: los buffers de liboqs tragan
        "ML-KEM-512",  # existe y es MENOR: ctypes levantaria ValueError
    ],
)
def test_manipular_el_mecanismo_lo_detecta(mecanismo_falso):
    """La CUARTA via de manipulacion, y la unica que no es un byte cualquiera.

    `mecanismo` es el unico campo del sobre que el receptor tiene que
    INTERPRETAR antes de poder verificar nada: decide con que KEM se
    desencapsula. Sin proteccion, cada uno de estos tres valores fallaba de
    una forma DISTINTA -MechanismNotSupportedError, InvalidTag y ValueError de
    ctypes-, y dos de las tres se escapaban de descifrar_mensaje como
    excepciones que ningun llamador espera (el dashboard solo captura
    InvalidTag: se iba a traceback).

    Lo que este test fija es que las tres salen por la MISMA puerta que
    cualquier otra manipulacion del sobre. Un llamador solo tiene que conocer
    un modo de fallo.
    """
    clave_publica, clave_privada = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE)
    roto = MensajeCifrado(
        sobre.kem_ciphertext, sobre.nonce, sobre.aead_ciphertext, mecanismo_falso
    )
    with pytest.raises(InvalidTag):
        descifrar_mensaje(clave_privada, roto)


def test_el_mecanismo_esta_autenticado_como_aad():
    """El `mecanismo` entra en el calculo del tag, no solo en la lista blanca.

    Se comprueba abriendo el sobre a mano por donde lo abre el receptor
    (desencapsular -> HKDF) y descifrando el AEAD tres veces con la misma
    clave y el mismo nonce, cambiando SOLO los datos asociados: con el
    mecanismo bueno sale el mensaje, con otro mecanismo y con None (que es lo
    que se pasaba antes) salta InvalidTag. Si el AAD no estuviera atado al
    campo, las tres darian el mismo resultado.

    Con el catalogo ML-KEM de hoy la lista blanca ya ataja las tres
    sustituciones posibles, asi que el AAD es defensa en profundidad: existe
    para que el campo siga autenticado el dia que el catalogo tenga dos
    mecanismos con las mismas longitudes, donde la lista blanca no distingue y
    el tag si.
    """
    clave_publica, clave_privada = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE, "ML-KEM-768")

    secreto = kem_desencapsular(clave_privada, sobre.kem_ciphertext, sobre.mecanismo)
    aead = AESGCM(_clave_aes(secreto))

    assert aead.decrypt(sobre.nonce, sobre.aead_ciphertext, b"ML-KEM-768") == MENSAJE
    for aad_falso in (b"ML-KEM-1024", None):
        with pytest.raises(InvalidTag):
            aead.decrypt(sobre.nonce, sobre.aead_ciphertext, aad_falso)


def test_clave_privada_ajena_no_descifra():
    """Quien no tiene la privada del destinatario no lee el mensaje."""
    clave_publica, _ = kem_generar()
    _, privada_ajena = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE)
    with pytest.raises(InvalidTag):
        descifrar_mensaje(privada_ajena, sobre)


def test_nonce_y_cifrado_nunca_se_repiten():
    """Cifrar dos veces el mismo mensaje da nonce, kem_ciphertext y texto
    distintos. Reutilizar nonce con la misma clave rompe GCM por completo
    (permite falsificar tags), asi que esta es LA propiedad a vigilar."""
    clave_publica, clave_privada = kem_generar()
    uno = cifrar_mensaje(clave_publica, MENSAJE)
    otro = cifrar_mensaje(clave_publica, MENSAJE)
    assert uno.nonce != otro.nonce
    assert uno.kem_ciphertext != otro.kem_ciphertext
    assert uno.aead_ciphertext != otro.aead_ciphertext
    # Y los dos descifran al mismo original.
    assert descifrar_mensaje(clave_privada, uno) == MENSAJE
    assert descifrar_mensaje(clave_privada, otro) == MENSAJE


def test_mensaje_largo_y_mensaje_vacio():
    """El hibrido no tiene el limite de tamano de RSA-OAEP (318 bytes con
    3072 bits, ver test_classical.py): cifra AES, no la asimetrica. Ese es
    justamente el motivo de que exista el patron."""
    clave_publica, clave_privada = kem_generar()
    largo = b"quantum" * 10_000
    assert (
        descifrar_mensaje(clave_privada, cifrar_mensaje(clave_publica, largo)) == largo
    )
    vacio = cifrar_mensaje(clave_publica, b"")
    assert descifrar_mensaje(clave_privada, vacio) == b""
