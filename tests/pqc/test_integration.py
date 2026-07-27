"""tests/pqc/test_integration.py - tarea 2.8. Las dos vias, en un solo test.

Cada pieza del modulo ya tiene sus tests (test_shor, test_kem, test_hybrid,
test_sig, test_classical, test_benchmark). Lo que falta, y es lo que hay aqui,
es el arco completo del modulo 2 recorrido de una vez:

    la AMENAZA  - Shor factoriza 15 por busqueda de orden (juguete, simulado)
    la DEFENSA  - ML-KEM cifra y ML-DSA firma un mensaje real (no simulado)

Si alguna de las dos mitades se rompe al integrarse con la otra (un import
circular, un contrato que cambia, una clave que no sobrevive a su `with`), es
aqui donde se ve, y no en la demo.

Politica de semillas, que es distinta en cada mitad y por eso conviven en el
mismo fichero: Shor recibe un np.random.Generator explicito y es reproducible;
la cripto real NO se siembra y se valida por propiedades (ver conftest.py).
"""

import numpy as np
import pytest
from cryptography.exceptions import InvalidTag
from pqc.hybrid import cifrar_mensaje, descifrar_mensaje
from pqc.kem import kem_generar
from pqc.shor import factorizar_15
from pqc.sig import firmar, verificar
from pqc.types import MensajeCifrado, ResultadoFirma

MENSAJE = b"secreto que debe sobrevivir al ordenador cuantico"


def test_amenaza_y_defensa_en_un_solo_test(rng):
    """El arco del modulo: Shor rompe (juguete), la PQC protege (real)."""
    # Amenaza: Shor factoriza 15 = 3 x 5 recuperando el orden.
    factorizacion = factorizar_15(rng)
    assert factorizacion.ok
    assert factorizacion.factores[0] * factorizacion.factores[1] == 15

    # Defensa: se cifra y se firma un mensaje real, y las dos cosas verifican.
    clave_publica, clave_privada = kem_generar("ML-KEM-768")
    sobre = cifrar_mensaje(clave_publica, MENSAJE, "ML-KEM-768")
    assert descifrar_mensaje(clave_privada, sobre) == MENSAJE
    assert verificar(firmar(MENSAJE, "ML-DSA-65"))


def test_canal_completo_confidencialidad_mas_autenticidad():
    """El uso realista: cifrar CON ML-KEM y firmar el sobre CON ML-DSA.

    Ni el KEM ni la firma bastan por separado. El cifrado hibrido oculta el
    mensaje pero no dice quien lo mando; la firma dice quien lo mando pero no
    lo oculta (ver test_sig.test_firmar_no_oculta_el_mensaje). El patron real
    es este: se cifra el mensaje y se firma el sobre cifrado.

    Aqui se firman los tres campos del sobre concatenados, que es lo que viaja
    por el canal. Bob verifica ANTES de descifrar y solo entonces descifra.
    """
    clave_publica, clave_privada = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE)
    en_el_canal = sobre.kem_ciphertext + sobre.nonce + sobre.aead_ciphertext

    firma = firmar(en_el_canal, "ML-DSA-65")
    assert verificar(firma)
    assert descifrar_mensaje(clave_privada, sobre) == MENSAJE


def test_manipular_el_canal_lo_cazan_las_dos_capas():
    """Un byte alterado en el canal: lo detectan la firma Y el AEAD.

    Son dos defensas independientes y las dos tienen que saltar, cada una con
    su forma de fallar: la firma devuelve False (caso negativo legitimo) y el
    AES-GCM lanza InvalidTag (no devuelve texto en claro ni por descuido).
    """
    clave_publica, clave_privada = kem_generar()
    sobre = cifrar_mensaje(clave_publica, MENSAJE)
    en_el_canal = sobre.kem_ciphertext + sobre.nonce + sobre.aead_ciphertext
    firma = firmar(en_el_canal, "ML-DSA-65")

    # El atacante cambia un bit del texto cifrado en transito.
    alterado = bytes([sobre.aead_ciphertext[0] ^ 0x01]) + sobre.aead_ciphertext[1:]
    sobre_roto = MensajeCifrado(
        sobre.kem_ciphertext, sobre.nonce, alterado, sobre.mecanismo
    )
    canal_roto = (
        sobre_roto.kem_ciphertext + sobre_roto.nonce + sobre_roto.aead_ciphertext
    )

    # Capa 1: la firma del sobre ya no cuadra.
    assert not verificar(
        ResultadoFirma(canal_roto, firma.firma, firma.clave_publica, firma.mecanismo)
    )
    # Capa 2: aunque alguien se salte la verificacion, el tag de GCM no cuela.
    with pytest.raises(InvalidTag):
        descifrar_mensaje(clave_privada, sobre_roto)


def test_shor_es_reproducible_y_la_cripto_real_no():
    """La politica de semillas del proyecto, escrita como test.

    Es la diferencia que mas confunde al llegar a la Fase 2: la mitad de Shor
    es una simulacion determinista y se siembra (misma semilla, misma
    factorizacion, mismo camino); la mitad de cripto real NO se puede sembrar
    porque una clave reproducible seria una clave insegura. Que las dos
    propiedades convivan es correcto, no una inconsistencia.
    """
    uno = factorizar_15(np.random.default_rng(42))
    otro = factorizar_15(np.random.default_rng(42))
    assert (uno.a, uno.orden, uno.intentos, uno.fase_medida) == (
        otro.a,
        otro.orden,
        otro.intentos,
        otro.fase_medida,
    )

    # Sin semilla posible: dos pares ML-KEM y dos firmas ML-DSA del MISMO
    # mensaje salen distintos, y eso es exactamente lo que se quiere.
    assert kem_generar()[0] != kem_generar()[0]
    assert firmar(MENSAJE).firma != firmar(MENSAJE).firma
