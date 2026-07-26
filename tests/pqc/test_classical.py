"""tests/pqc/test_classical.py - tarea 2.4.

La linea base clasica (RSA-OAEP/PSS, X25519, Ed25519) contra la que se compara
la PQC. Se prueba por PROPIEDADES, nunca contra valores fijos: estas claves no
se pueden sembrar (ver el comentario de conftest.py), asi que lo que se afirma
tiene que valer para CUALQUIER clave que salga del CSPRNG.

Las propiedades son tres, y son las mismas para las cuatro primitivas:
  - round-trip:  descifrar deshace cifrar; una firma valida verifica.
  - rechazo:     un mensaje manipulado o una clave ajena NO verifican.
  - tamanos:     los artefactos miden lo que el estandar dice.

Los pares RSA van en fixtures de modulo porque generar 3072 bits cuesta del
orden de decimas de segundo y la propiedad no depende de que el par sea nuevo
en cada test.
"""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519 as _ed25519
from pqc.classical import (
    ed25519_firmar,
    ed25519_generar,
    ed25519_verificar,
    rsa_cifrar_oaep,
    rsa_descifrar_oaep,
    rsa_firmar_pss,
    rsa_generar,
    rsa_verificar_pss,
    x25519_generar,
    x25519_intercambio,
)

# Maximo que cabe en un OAEP-SHA256 sobre RSA-3072: k - 2*hLen - 2, con
# k = 384 bytes de modulo y hLen = 32. Es el limite duro que justifica que
# exista el patron hibrido (ver test_hybrid.py).
MAX_OAEP_3072 = 318


@pytest.fixture(scope="module")
def par_rsa() -> tuple[bytes, bytes]:
    """Par RSA-3072 (publica_pem, privada_pem) compartido por los tests."""
    return rsa_generar(3072)


@pytest.fixture(scope="module")
def par_rsa_ajeno() -> tuple[bytes, bytes]:
    """Un SEGUNDO par RSA, para los tests de rechazo con clave equivocada."""
    return rsa_generar(3072)


def test_rsa_oaep_roundtrip(par_rsa):
    """Descifrar deshace cifrar: la propiedad basica del cifrado asimetrico."""
    publica, privada = par_rsa
    mensaje = b"mensaje de prueba QPCS"
    assert rsa_descifrar_oaep(privada, rsa_cifrar_oaep(publica, mensaje)) == mensaje


def test_rsa_oaep_es_probabilistico(par_rsa):
    """Cifrar dos veces el mismo mensaje da textos DISTINTOS.

    Es la razon de ser de OAEP: con un relleno determinista, un atacante que
    sospecha el contenido lo confirma cifrandolo y comparando. Los dos textos
    distintos tienen que descifrar al mismo original.
    """
    publica, privada = par_rsa
    mensaje = b"mismo mensaje, dos cifrados"
    uno = rsa_cifrar_oaep(publica, mensaje)
    otro = rsa_cifrar_oaep(publica, mensaje)
    assert uno != otro
    assert rsa_descifrar_oaep(privada, uno) == rsa_descifrar_oaep(privada, otro)


def test_rsa_oaep_tiene_limite_de_tamano(par_rsa):
    """RSA cifra 318 bytes con OAEP-SHA256 sobre 3072 bits, y ni uno mas.

    El byte 319 levanta ValueError. Este test documenta POR QUE existen los
    KEM: la asimetrica no cifra mensajes largos, acuerda claves (ver kem.py).
    """
    publica, privada = par_rsa
    justo = b"A" * MAX_OAEP_3072
    assert rsa_descifrar_oaep(privada, rsa_cifrar_oaep(publica, justo)) == justo
    with pytest.raises(ValueError):
        rsa_cifrar_oaep(publica, b"A" * (MAX_OAEP_3072 + 1))


def test_rsa_pss_firma_valida_verifica(par_rsa):
    publica, privada = par_rsa
    mensaje = b"documento importante"
    assert rsa_verificar_pss(publica, mensaje, rsa_firmar_pss(privada, mensaje))


def test_rsa_pss_rechaza_mensaje_manipulado(par_rsa):
    """El test que de verdad prueba algo: alterar el mensaje invalida la firma.

    Un test que solo comprueba firmas validas no demuestra nada, porque lo
    pasaria igual una implementacion que devolviese True siempre.
    """
    publica, privada = par_rsa
    firma = rsa_firmar_pss(privada, b"transferir 100 euros")
    assert not rsa_verificar_pss(publica, b"transferir 900 euros", firma)


def test_rsa_pss_rechaza_clave_publica_ajena(par_rsa, par_rsa_ajeno):
    """Una firma valida, pero verificada con la publica de OTRO, no cuela."""
    _, privada = par_rsa
    publica_ajena, _ = par_rsa_ajeno
    mensaje = b"mismo mensaje"
    assert not rsa_verificar_pss(
        publica_ajena, mensaje, rsa_firmar_pss(privada, mensaje)
    )


def test_rsa_pss_devuelve_false_y_no_lanza(par_rsa):
    """Ante una firma basura devuelve False; la InvalidSignature no escapa.

    El contrato de la funcion es bool, igual que `sig.verificar` de la 2.6,
    para que el benchmark (2.7) cronometre las dos con el mismo codigo.
    """
    publica, _ = par_rsa
    resultado = rsa_verificar_pss(publica, b"lo que sea", b"\x00" * 384)
    assert resultado is False


def test_rsa_pss_es_probabilistico(par_rsa):
    """PSS lleva salt aleatorio: dos firmas del mismo mensaje difieren y ambas
    verifican. Con PKCS#1 v1.5 (el modo que NO usamos) serian identicas."""
    publica, privada = par_rsa
    mensaje = b"firmado dos veces"
    una = rsa_firmar_pss(privada, mensaje)
    otra = rsa_firmar_pss(privada, mensaje)
    assert una != otra
    assert rsa_verificar_pss(publica, mensaje, una)
    assert rsa_verificar_pss(publica, mensaje, otra)


def test_rsa_rechaza_una_clave_que_no_es_rsa():
    """Pasar una clave Ed25519 en PEM donde se espera RSA da TypeError legible.

    Sin el isinstance de `_cargar_rsa_publica` esto reventaria mas abajo con
    un AttributeError incomprensible.
    """
    ajena = (
        _ed25519.Ed25519PrivateKey.generate()
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    with pytest.raises(TypeError):
        rsa_cifrar_oaep(ajena, b"hola")


def test_x25519_ambos_lados_derivan_el_mismo_secreto():
    """La propiedad central de Diffie-Hellman, y el analogo clasico del KEM:
    intercambio(priv_a, pub_b) == intercambio(priv_b, pub_a)."""
    publica_a, privada_a = x25519_generar()
    publica_b, privada_b = x25519_generar()
    secreto_a = x25519_intercambio(privada_a, publica_b)
    secreto_b = x25519_intercambio(privada_b, publica_a)
    assert secreto_a == secreto_b
    assert len(secreto_a) == 32


def test_x25519_pares_distintos_dan_secretos_distintos():
    """Un tercero con su propio par no llega al secreto de los otros dos."""
    publica_a, privada_a = x25519_generar()
    _, privada_b = x25519_generar()
    _, privada_intruso = x25519_generar()
    assert x25519_intercambio(privada_b, publica_a) != x25519_intercambio(
        privada_intruso, publica_a
    )


def test_x25519_tamanos_raw():
    """32 bytes por clave (RFC 7748). Contrastar con los 1184 de ML-KEM-768:
    ese salto es el coste en bytes que mide el benchmark de la tarea 2.7."""
    publica, privada = x25519_generar()
    assert len(publica) == 32
    assert len(privada) == 32


def test_ed25519_firma_valida_verifica():
    publica, privada = ed25519_generar()
    mensaje = b"comunicado oficial QPCS"
    assert ed25519_verificar(publica, mensaje, ed25519_firmar(privada, mensaje))


def test_ed25519_rechaza_mensaje_manipulado():
    publica, privada = ed25519_generar()
    firma = ed25519_firmar(privada, b"transferir 100 euros")
    assert not ed25519_verificar(publica, b"transferir 900 euros", firma)


def test_ed25519_rechaza_clave_publica_ajena():
    """Round-trip cruzado: la firma es valida, pero no para esa clave."""
    _, privada = ed25519_generar()
    publica_ajena, _ = ed25519_generar()
    mensaje = b"mismo mensaje"
    assert not ed25519_verificar(
        publica_ajena, mensaje, ed25519_firmar(privada, mensaje)
    )


def test_ed25519_tamanos_raw():
    """Clave publica de 32 bytes y firma de 64: la referencia clasica frente a
    los 1952 + 3309 de ML-DSA-65 (ver test_sig.py)."""
    publica, privada = ed25519_generar()
    assert len(publica) == 32
    assert len(ed25519_firmar(privada, b"x")) == 64
