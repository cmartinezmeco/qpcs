"""tests/pqc/test_kem.py - tarea 2.5 (ML-KEM en crudo).

El KEM pelado: generar par, encapsular, desencapsular. El sobre completo
(KEM + HKDF + AES-GCM sobre un mensaje real) se prueba en test_hybrid.py.

Como toda la cripto real del modulo, se valida por propiedades y no con
semilla: la propiedad de CORRECCION de un KEM es que emisor y receptor
obtienen el mismo secreto, y eso vale para cualquier par de claves.
"""

import oqs
import pytest
from pqc.kem import abrir_kem, kem_desencapsular, kem_encapsular, kem_generar

# Tamanos de ML-KEM-768 fijados por FIPS 203. No son un detalle de liboqs: si
# alguno cambia, o estamos hablando con otro mecanismo o la build esta mal.
PK_768 = 1184
SK_768 = 2400
CT_768 = 1088
SECRETO = 32


def test_kem_secretos_coinciden():
    """LA propiedad del KEM: emisor y receptor obtienen el mismo secreto.

    El emisor solo necesita la clave publica; el receptor desencapsula con la
    privada. Si esto falla, el cifrado hibrido no puede funcionar.
    """
    clave_publica, clave_privada = kem_generar("ML-KEM-768")
    kem_ciphertext, secreto_emisor = kem_encapsular(clave_publica, "ML-KEM-768")
    secreto_receptor = kem_desencapsular(clave_privada, kem_ciphertext, "ML-KEM-768")
    assert secreto_emisor == secreto_receptor
    assert len(secreto_emisor) == SECRETO


def test_kem_tamanos_fips_203():
    """Los artefactos miden lo que dice FIPS 203 para ML-KEM-768."""
    clave_publica, clave_privada = kem_generar()
    kem_ciphertext, secreto = kem_encapsular(clave_publica)
    assert len(clave_publica) == PK_768
    assert len(clave_privada) == SK_768
    assert len(kem_ciphertext) == CT_768
    assert len(secreto) == SECRETO


def test_kem_todo_es_bytes():
    """Nada de str: las claves son binarias y meterlas en str invita a bugs de
    codificacion. Ademas comprueba que el bytes(...) que sella la frontera de
    liboqs (Any para mypy) devuelve bytes de verdad, no un buffer prestado."""
    clave_publica, clave_privada = kem_generar()
    kem_ciphertext, secreto = kem_encapsular(clave_publica)
    for artefacto in (clave_publica, clave_privada, kem_ciphertext, secreto):
        assert isinstance(artefacto, bytes)


def test_dos_encapsulamientos_dan_secretos_distintos():
    """Cada encapsulamiento genera un secreto FRESCO aunque la clave publica
    sea la misma: el secreto lo crea el encapsulamiento, no un acuerdo entre
    claves fijas. Si se repitiese, se repetiria la clave AES de hybrid.py."""
    clave_publica, clave_privada = kem_generar()
    ct_uno, secreto_uno = kem_encapsular(clave_publica)
    ct_otro, secreto_otro = kem_encapsular(clave_publica)
    assert ct_uno != ct_otro
    assert secreto_uno != secreto_otro
    # ...y aun asi el receptor recupera cada uno con la misma clave privada.
    assert kem_desencapsular(clave_privada, ct_uno) == secreto_uno
    assert kem_desencapsular(clave_privada, ct_otro) == secreto_otro


def test_ciphertext_manipulado_da_otro_secreto_sin_lanzar():
    """El rechazo IMPLICITO de ML-KEM, que sorprende la primera vez.

    Alterar el ciphertext no produce ningun error: devuelve otros 32 bytes.
    Es deliberado (Fujisaki-Okamoto / IND-CCA): fallar de forma distinguible
    le daria al atacante un oraculo. La manipulacion se detecta arriba, con el
    tag de AES-GCM (ver test_hybrid.py).
    """
    clave_publica, clave_privada = kem_generar()
    kem_ciphertext, secreto = kem_encapsular(clave_publica)
    roto = bytes([kem_ciphertext[0] ^ 0x01]) + kem_ciphertext[1:]
    secreto_roto = kem_desencapsular(clave_privada, roto)
    assert len(secreto_roto) == SECRETO
    assert secreto_roto != secreto


def test_clave_privada_ajena_no_recupera_el_secreto():
    """Desencapsular con la privada de otro par da un secreto que no sirve."""
    clave_publica, _ = kem_generar()
    _, privada_ajena = kem_generar()
    kem_ciphertext, secreto = kem_encapsular(clave_publica)
    assert kem_desencapsular(privada_ajena, kem_ciphertext) != secreto


def test_mecanismo_inexistente_falla_ruidosamente():
    """Un nombre mal escrito (nomenclatura pre-NIST, un typo) revienta en el
    acto con el error de liboqs, no con un fallo silencioso mas abajo."""
    with pytest.raises(oqs.MechanismNotSupportedError):
        kem_generar("Kyber768-inventado")


def test_abrir_kem_es_context_manager():
    """El objeto de liboqs envuelve memoria C y SIEMPRE va bajo `with`.

    Regla dura del modulo: sin cerrar, cada KeyEncapsulation deja memoria sin
    liberar; con 10 llamadas no se nota, con las cientos del benchmark (2.7)
    si. Este test fija que `abrir_kem` soporta el patron.
    """
    with abrir_kem("ML-KEM-768") as kem:
        assert len(kem.generate_keypair()) == PK_768
