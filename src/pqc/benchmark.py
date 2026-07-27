"""src/pqc/benchmark.py - tarea 2.7 (Carlos). Medidas de tiempo y tamano.

El entregable del modulo 2 es la comparacion cuantitativa clasico vs
post-cuantico: cuanto tarda cada operacion y cuanto ocupan claves, ciphertexts
y firmas. Este modulo produce esas cifras como `Medida` y `Tamanos` (ver
`types.py`), que luego consumen las figuras y el dashboard.

Reglas de medida (para que las cifras sean defendibles):
  - Reloj: SIEMPRE time.perf_counter, NUNCA time.time. perf_counter es
    monotono y de alta resolucion; time.time puede saltar hacia atras (ajuste
    de NTP) y arruinar una medida.
  - Se reportan media, sigma (desviacion tipica de las repeticiones) y p50
    (mediana). La barra de error es sigma DERIVADA de las muestras, nunca un
    numero inventado a ojo: misma disciplina que el QBER del modulo 1.
  - Conviene un calentamiento (unas pocas repeticiones descartadas) antes de
    cronometrar, para no medir el coste de importar/compilar en frio.

Aqui no hay np.random.Generator: la cripto real genera sus claves con su propio
CSPRNG y no se siembra.

QUE SE CRONOMETRA EXACTAMENTE (la decision que define este benchmark)
---------------------------------------------------------------------
Medir "una operacion" es ambiguo en cuanto las claves cruzan una frontera de
serializacion, y en este proyecto la diferencia no es cosmetica: el modulo
`classical.py` recibe las claves RSA como PEM y las deserializa en cada
llamada, y OpenSSL 3 VALIDA la clave privada al cargarla. Medido en esta
maquina: descifrar con RSA-3072 cuesta 2.7 ms, pero cargar su PEM cuesta
157 ms. Cronometrar solo `rsa_descifrar_oaep` diria que RSA es ~60 veces mas
lento de lo que es, y la comparacion contra ML-KEM seria una mentira de dos
ordenes de magnitud.

Asi que cada operacion se mide en DOS capas (ver el tipo `Capa`):

  - "primitiva": la operacion criptografica con el material de clave ya en la
    forma nativa que espera la primitiva (objeto de `cryptography` cargado,
    objeto de liboqs abierto). Es la capa que compara ALGORITMOS y la que va
    a la tabla y al panel principal de la figura de tiempos.
  - "api": la funcion publica del modulo tal cual la llama el resto de QPCS,
    que ademas (de)serializa la clave en cada llamada. Es lo que el proyecto
    paga de verdad hoy, y su resta con la capa "primitiva" es el coste de la
    serializacion.

Las dos capas conviven en la misma tabla porque el `Operacion` de `types.py`
es un Literal cerrado y no se toca: la capa viaja en el `mecanismo`, que si es
string libre, con el sufijo `SUFIJO_CAPA_API` (p. ej. "RSA-3072 +carga").
"""

from __future__ import annotations

import json
import platform
import statistics
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast, get_args

import oqs
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa, x25519

# _OAEP y _PSS se importan de classical.py (y no se redeclaran aqui) para que
# la capa "primitiva" cifre y firme con EXACTAMENTE los mismos parametros que
# la capa "api": si divergiesen, las dos filas del benchmark no serian
# comparables y la resta no mediria la serializacion, mediria otro relleno.
from .classical import (
    _OAEP,
    _PSS,
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
from .kem import abrir_kem, kem_desencapsular, kem_encapsular, kem_generar
from .sig import abrir_firma, firmar, verificar
from .types import Familia, Medida, Operacion, Tamanos

# Las dos capas de medida (ver el docstring del modulo).
Capa = Literal["primitiva", "api"]

# Sufijo que marca la capa "api" dentro del campo `mecanismo`. Es el unico
# sitio donde cabe: `Operacion` es un Literal cerrado del contrato compartido
# (types.py) y ampliarlo requiere acuerdo del equipo.
SUFIJO_CAPA_API = " +carga"

# Repeticiones por defecto, diferenciadas por familia porque los tiempos por
# iteracion se llevan cuatro ordenes de magnitud:
#   - PQC y ECC estan en decenas de microsegundos: 200 repeticiones cuestan
#     milisegundos y dan una sigma estable.
#   - Un keygen de RSA-3072 cuesta ~250 ms y ademas es MUY disperso (busca
#     primos al azar: sigma ~120 ms, casi la mitad de la media). Con 200
#     repeticiones seria un minuto solo esa fila; con 50 son ~12 s y la sigma
#     ya esta bien estimada. 50 es tambien el minimo razonable para que la
#     media de algo tan disperso signifique algo.
REPETICIONES_PQC = 200
REPETICIONES_CLASICO = 50

# Repeticiones descartadas antes de empezar a cronometrar. La primera llamada
# a una primitiva paga cosas que no son la operacion (cargar la libreria C,
# rellenar cachés de OpenSSL, resolver el mecanismo en liboqs) y contaminaria
# la media. Tres bastan y no encarecen notablemente ni el keygen de RSA.
CALENTAMIENTO = 3

# Mensaje unico para todo lo que cifra o firma. Corto y fijo a proposito: el
# coste de firmar lo domina el esquema y no el hash del mensaje, y que sea el
# MISMO en todas las familias es lo que hace comparables las filas. Cabe de
# sobra en el limite de RSA-OAEP con 3072 bits (318 bytes).
MENSAJE = b"QPCS fase 2 - mensaje de referencia del benchmark"

# Mecanismos de la tabla completa. RSA-3072 y no RSA-2048: ~128 bits de
# seguridad clasica es el comparable justo de ML-KEM-768 / ML-DSA-65 (nivel
# NIST 3). Comparar contra RSA-2048 (~112 bits) le regalaria ventaja a RSA.
MECANISMO_RSA = "RSA-3072"
MECANISMO_KEM = "ML-KEM-768"
MECANISMO_SIG = "ML-DSA-65"

# Operaciones que tiene sentido pedir a cada bloque. Sirven para validar la
# entrada ANTES de montar el material de clave (que en RSA cuesta 250 ms) y
# para que la tabla completa no tenga que repetir estas listas.
OPS_KEM: tuple[Operacion, ...] = ("keygen", "encaps", "decaps")
OPS_FIRMA: tuple[Operacion, ...] = ("keygen", "sign", "verify")
OPS_RSA: tuple[Operacion, ...] = ("keygen", "encrypt", "decrypt", "sign", "verify")
# X25519 no firma ni cifra: genera par y deriva un secreto compartido. Ese
# "derivar el secreto con mi clave privada" se etiqueta "decaps", que es su
# analogo exacto en un KEM (ver `medir_classical`).
OPS_X25519: tuple[Operacion, ...] = ("keygen", "decaps")
OPS_ED25519: tuple[Operacion, ...] = ("keygen", "sign", "verify")

# Fichero de resultados versionado. JSON y no CSV: los dataclasses del
# contrato mapean directos a diccionarios, se preservan los tipos (float vs
# str) sin ambiguedad y no hay que pelearse con el separador decimal del
# locale espanol. Vive en docs/ (junto a docs/img/, la salida de las figuras)
# porque es un artefacto de presentacion: las figuras de la tarea 2.9 leen de
# aqui y no vuelven a medir cada vez que se regenera un PNG.
RUTA_JSON = Path(__file__).resolve().parents[2] / "docs" / "benchmark_pqc.json"


def _cronometrar(
    fn: Callable[[], object], repeticiones: int, calentamiento: int = CALENTAMIENTO
) -> tuple[float, float, float]:
    """Ejecuta `fn` y devuelve (media, sigma, p50) en milisegundos.

    time.perf_counter alrededor de cada llamada, nada de time.time. El
    calentamiento se ejecuta y se TIRA: no entra en la muestra.

    La sigma es la de la muestra (statistics.stdev, con n-1 en el
    denominador), es decir una cifra DERIVADA de estas mismas medidas. Con una
    sola repeticion no hay dispersion que medir y devuelve 0.0, que es
    honesto: significa "sin barra de error", no "error cero".

    La mediana va aparte porque aguanta los picos del planificador del sistema
    operativo que si contaminan la media: si media y p50 se separan mucho, la
    medida esta sucia y hay que desconfiar de ella.
    """
    if repeticiones < 1:
        raise ValueError("repeticiones debe ser >= 1")

    for _ in range(calentamiento):
        fn()

    muestras: list[float] = []
    for _ in range(repeticiones):
        t0 = time.perf_counter()
        fn()
        muestras.append((time.perf_counter() - t0) * 1000.0)

    media = statistics.fmean(muestras)
    sigma = statistics.stdev(muestras) if len(muestras) > 1 else 0.0
    return media, sigma, statistics.median(muestras)


def _etiqueta(mecanismo: str, capa: Capa) -> str:
    """Nombre del mecanismo tal y como aparece en la tabla, segun la capa."""
    return mecanismo if capa == "primitiva" else mecanismo + SUFIJO_CAPA_API


def _medir(
    familia: Familia,
    mecanismo: str,
    operacion: Operacion,
    capa: Capa,
    repeticiones: int,
    acciones: dict[Operacion, Callable[[], object]],
) -> Medida:
    """Cronometra `acciones[operacion]` y la empaqueta en una `Medida`.

    Centraliza el unico sitio donde se construye una `Medida`, para que ni la
    etiqueta de la capa ni el numero de repeticiones puedan salir distintos
    segun la familia.
    """
    if operacion not in acciones:
        raise ValueError(
            f"operacion {operacion!r} no aplica a {mecanismo} en la capa {capa!r}: "
            f"disponibles {sorted(acciones)}"
        )
    media, sigma, p50 = _cronometrar(acciones[operacion], repeticiones)
    return Medida(
        familia=familia,
        mecanismo=_etiqueta(mecanismo, capa),
        operacion=operacion,
        repeticiones=repeticiones,
        media_ms=media,
        sigma_ms=sigma,
        p50_ms=p50,
    )


def _validar(operacion: Operacion, permitidas: tuple[Operacion, ...], que: str) -> None:
    """Rechaza una operacion que no aplica, ANTES de generar claves.

    Generar el material de clave para medir cuesta desde microsegundos
    (ML-KEM) hasta un cuarto de segundo (RSA-3072): validar primero convierte
    un error del llamador en un fallo inmediato y legible.
    """
    if operacion not in permitidas:
        raise ValueError(
            f"operacion {operacion!r} no aplica a {que}: usa una de {list(permitidas)}"
        )


def medir_kem(
    mecanismo: str = MECANISMO_KEM,
    operacion: Operacion = "encaps",
    repeticiones: int = REPETICIONES_PQC,
    capa: Capa = "primitiva",
) -> Medida:
    """Cronometra una `operacion` de un KEM (keygen / encaps / decaps).

    Repite `repeticiones` veces con time.perf_counter y devuelve una `Medida`
    con familia="ML-KEM", media, sigma y p50 en milisegundos.

    capa="primitiva" abre UN solo objeto de liboqs bajo `with` y cronometra el
    metodo nativo: es el coste del algoritmo. capa="api" cronometra las
    funciones publicas de `kem.py`, que abren y cierran su propio objeto y
    copian las claves a bytes en cada llamada (la diferencia, unos 7 us por
    llamada medidos aqui, es lo que cuesta esa frontera limpia).

    En las dos capas los objetos de liboqs van SIEMPRE bajo `with`: con las
    cientos de repeticiones de un benchmark, uno sin cerrar es una fuga de
    memoria que si se nota.
    """
    _validar(operacion, OPS_KEM, f"un KEM ({mecanismo})")

    if capa == "api":
        clave_publica, clave_privada = kem_generar(mecanismo)
        kem_ciphertext, _ = kem_encapsular(clave_publica, mecanismo)
        acciones: dict[Operacion, Callable[[], object]] = {
            "keygen": lambda: kem_generar(mecanismo),
            "encaps": lambda: kem_encapsular(clave_publica, mecanismo),
            "decaps": lambda: kem_desencapsular(
                clave_privada, kem_ciphertext, mecanismo
            ),
        }
        return _medir("ML-KEM", mecanismo, operacion, capa, repeticiones, acciones)

    with abrir_kem(mecanismo) as kem:
        # El objeto se queda con su clave secreta dentro, asi que puede
        # desencapsular el ciphertext que se acaba de encapsular contra su
        # propia publica.
        clave_publica_viva = kem.generate_keypair()
        ciphertext_vivo, _ = kem.encap_secret(clave_publica_viva)
        acciones = {
            "keygen": lambda: kem.generate_keypair(),
            "encaps": lambda: kem.encap_secret(clave_publica_viva),
            "decaps": lambda: kem.decap_secret(ciphertext_vivo),
        }
        return _medir("ML-KEM", mecanismo, operacion, capa, repeticiones, acciones)


def medir_sig(
    mecanismo: str = MECANISMO_SIG,
    operacion: Operacion = "sign",
    repeticiones: int = REPETICIONES_PQC,
    capa: Capa = "primitiva",
) -> Medida:
    """Cronometra una `operacion` de firma (keygen / sign / verify).

    Devuelve una `Medida` con familia="ML-DSA". Mismo protocolo de medida que
    `medir_kem`.

    OJO con la capa "api": `sig.firmar` genera un par NUEVO y lo consume en el
    acto (la clave privada nunca sale de la funcion, que es justo lo que se
    quiere de una clave de firma), asi que no hay forma de cronometrar "sign"
    sin meter dentro el keygen. Medirlo como "sign" atribuiria a la firma un
    coste que no es suyo -- ML-DSA-65 parece el doble de lento --, asi que la
    capa "api" solo admite "verify", que si es una funcion publica limpia
    (`sig.verificar`). El keygen y la firma de ML-DSA se miden por separado en
    la capa "primitiva", que es la que compara algoritmos.
    """
    if capa == "api":
        _validar(operacion, ("verify",), f"la capa api de {mecanismo}")
        # `firmar` genera el par y firma; aqui solo hace falta un resultado
        # verificable, su coste no se cronometra.
        resultado = firmar(MENSAJE, mecanismo)
        acciones: dict[Operacion, Callable[[], object]] = {
            "verify": lambda: verificar(resultado)
        }
        return _medir("ML-DSA", mecanismo, operacion, capa, repeticiones, acciones)

    _validar(operacion, OPS_FIRMA, f"un esquema de firma ({mecanismo})")
    with abrir_firma(mecanismo) as firmante:
        clave_publica = firmante.generate_keypair()
        firma = firmante.sign(MENSAJE)
        # Verificar necesita su propio objeto: el verificador solo usa la
        # clave publica, que se le pasa como argumento (ver sig.verificar).
        with abrir_firma(mecanismo) as verificador:
            acciones = {
                "keygen": lambda: firmante.generate_keypair(),
                "sign": lambda: firmante.sign(MENSAJE),
                "verify": lambda: verificador.verify(MENSAJE, firma, clave_publica),
            }
            return _medir("ML-DSA", mecanismo, operacion, capa, repeticiones, acciones)


def medir_classical(
    familia: Familia,
    mecanismo: str,
    operacion: Operacion,
    repeticiones: int = REPETICIONES_CLASICO,
    capa: Capa = "primitiva",
) -> Medida:
    """Cronometra una `operacion` clasica (RSA o ECC) de `classical.py`.

    `familia` debe ser "RSA" o "ECC" (las post-cuanticas van por `medir_kem` /
    `medir_sig`). Devuelve la `Medida` con esa familia para que las tablas del
    benchmark comparen manzanas con manzanas.

    Mecanismos soportados: "RSA-<bits>" (con familia="RSA") y "X25519" o
    "Ed25519" (con familia="ECC"). La familia "ECC" del Literal cubre las dos
    curvas; es el `mecanismo` el que las distingue.

    Sobre la etiqueta de X25519: un intercambio Diffie-Hellman es simetrico y
    no es literalmente ni un encaps ni un decaps, pero se reporta como
    "decaps" porque es la fila COMPARABLE con `ML-KEM decaps`: en los dos
    casos una parte deriva el secreto compartido usando su clave privada. La
    diferencia conceptual (en el DH las dos partes aportan clave; en el KEM el
    emisor solo necesita la publica del receptor) esta documentada en
    `classical.x25519_intercambio` y en `kem.kem_encapsular`.

    capa="api" cronometra las funciones publicas de `classical.py` tal cual,
    con la clave viajando como PEM (RSA) o raw (curvas) y deserializandose en
    cada llamada; capa="primitiva" carga la clave UNA vez fuera del bucle y
    cronometra solo la operacion criptografica. En RSA la diferencia es
    brutal y es la razon de que existan las dos capas: OpenSSL 3 valida la
    clave privada al cargar el PEM y eso cuesta ~157 ms, sesenta veces mas
    que el descifrado en si.
    """
    if familia == "RSA":
        if not mecanismo.startswith("RSA-"):
            raise ValueError(
                f"familia RSA con mecanismo {mecanismo!r}: se esperaba RSA-<bits>"
            )
        _validar(operacion, OPS_RSA, mecanismo)
        return _medir_rsa(mecanismo, operacion, capa, repeticiones)
    if familia == "ECC":
        if mecanismo == "X25519":
            _validar(operacion, OPS_X25519, mecanismo)
            return _medir_x25519(operacion, capa, repeticiones)
        if mecanismo == "Ed25519":
            _validar(operacion, OPS_ED25519, mecanismo)
            return _medir_ed25519(operacion, capa, repeticiones)
        raise ValueError(
            f"mecanismo ECC no soportado: {mecanismo!r} (X25519 / Ed25519)"
        )
    raise ValueError(
        f"familia {familia!r} no es clasica: ML-KEM se mide con medir_kem y "
        "ML-DSA con medir_sig"
    )


def _bits_rsa(mecanismo: str) -> int:
    """Extrae los bits del nombre: "RSA-3072" -> 3072."""
    try:
        return int(mecanismo.split("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"no se leen los bits de {mecanismo!r}: usa RSA-3072") from exc


def _medir_rsa(
    mecanismo: str, operacion: Operacion, capa: Capa, repeticiones: int
) -> Medida:
    """Las cinco operaciones de RSA en las dos capas. Ver `medir_classical`."""
    bits = _bits_rsa(mecanismo)

    if capa == "api":
        publica_pem, privada_pem = rsa_generar(bits)
        texto_cifrado = rsa_cifrar_oaep(publica_pem, MENSAJE)
        firma = rsa_firmar_pss(privada_pem, MENSAJE)
        acciones: dict[Operacion, Callable[[], object]] = {
            "keygen": lambda: rsa_generar(bits),
            "encrypt": lambda: rsa_cifrar_oaep(publica_pem, MENSAJE),
            "decrypt": lambda: rsa_descifrar_oaep(privada_pem, texto_cifrado),
            "sign": lambda: rsa_firmar_pss(privada_pem, MENSAJE),
            "verify": lambda: rsa_verificar_pss(publica_pem, MENSAJE, firma),
        }
        return _medir("RSA", mecanismo, operacion, capa, repeticiones, acciones)

    # Capa primitiva: los objetos de `cryptography` ya cargados. El keygen se
    # mide sin exportar a PEM (exportar es serializacion, no generacion) y las
    # otras cuatro reutilizan el mismo par.
    privada = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    publica = privada.public_key()
    texto = publica.encrypt(MENSAJE, _OAEP)
    firma_viva = privada.sign(MENSAJE, _PSS, hashes.SHA256())
    acciones = {
        "keygen": lambda: rsa.generate_private_key(
            public_exponent=65537, key_size=bits
        ),
        "encrypt": lambda: publica.encrypt(MENSAJE, _OAEP),
        "decrypt": lambda: privada.decrypt(texto, _OAEP),
        "sign": lambda: privada.sign(MENSAJE, _PSS, hashes.SHA256()),
        "verify": lambda: publica.verify(firma_viva, MENSAJE, _PSS, hashes.SHA256()),
    }
    return _medir("RSA", mecanismo, operacion, capa, repeticiones, acciones)


def _medir_x25519(operacion: Operacion, capa: Capa, repeticiones: int) -> Medida:
    """Keygen e intercambio de X25519 (etiquetado "decaps", ver arriba)."""
    if capa == "api":
        _, privada_raw = x25519_generar()
        publica_par_raw, _ = x25519_generar()
        acciones: dict[Operacion, Callable[[], object]] = {
            "keygen": lambda: x25519_generar(),
            "decaps": lambda: x25519_intercambio(privada_raw, publica_par_raw),
        }
        return _medir("ECC", "X25519", operacion, capa, repeticiones, acciones)

    privada = x25519.X25519PrivateKey.generate()
    publica_par = x25519.X25519PrivateKey.generate().public_key()
    acciones = {
        "keygen": lambda: x25519.X25519PrivateKey.generate(),
        "decaps": lambda: privada.exchange(publica_par),
    }
    return _medir("ECC", "X25519", operacion, capa, repeticiones, acciones)


def _medir_ed25519(operacion: Operacion, capa: Capa, repeticiones: int) -> Medida:
    """Keygen, firma y verificacion de Ed25519 (la referencia clasica de 64 B)."""
    if capa == "api":
        publica_raw, privada_raw = ed25519_generar()
        firma = ed25519_firmar(privada_raw, MENSAJE)
        acciones: dict[Operacion, Callable[[], object]] = {
            "keygen": lambda: ed25519_generar(),
            "sign": lambda: ed25519_firmar(privada_raw, MENSAJE),
            "verify": lambda: ed25519_verificar(publica_raw, MENSAJE, firma),
        }
        return _medir("ECC", "Ed25519", operacion, capa, repeticiones, acciones)

    privada = ed25519.Ed25519PrivateKey.generate()
    publica = privada.public_key()
    firma_viva = privada.sign(MENSAJE)
    acciones = {
        "keygen": lambda: ed25519.Ed25519PrivateKey.generate(),
        "sign": lambda: privada.sign(MENSAJE),
        "verify": lambda: publica.verify(firma_viva, MENSAJE),
    }
    return _medir("ECC", "Ed25519", operacion, capa, repeticiones, acciones)


def tamanos_kem(mecanismo: str = MECANISMO_KEM) -> Tamanos:
    """Tamanos en bytes de un KEM: clave publica, privada y kem_ciphertext.

    El campo `firma` de `Tamanos` no aplica a un KEM: se rellena con 0. Los
    tamanos son deterministas (los fija el mecanismo), asi que basta una
    generacion/encapsulacion para leerlos.

    Se leen del diccionario `details` del propio objeto de liboqs y no se
    codifican a mano: si algun dia la build trae otro mecanismo con el mismo
    nombre, la tabla lo dira en vez de repetir las cifras de FIPS 203 de
    memoria. Los `int(...)` sellan el Any que llega de liboqs (sin stubs).
    """
    with abrir_kem(mecanismo) as kem:
        detalles = kem.details
        return Tamanos(
            mecanismo=mecanismo,
            clave_publica=int(detalles["length_public_key"]),
            clave_privada=int(detalles["length_secret_key"]),
            texto_cifrado=int(detalles["length_ciphertext"]),
            firma=0,
        )


def tamanos_sig(mecanismo: str = MECANISMO_SIG) -> Tamanos:
    """Tamanos en bytes de un esquema de firma: clave publica, privada y firma.

    El campo `texto_cifrado` no aplica a una firma: se rellena con 0. Mismo
    criterio que `tamanos_kem`: las cifras salen de `details`, no de FIPS 204
    escrito a mano.
    """
    with abrir_firma(mecanismo) as firmante:
        detalles = firmante.details
        return Tamanos(
            mecanismo=mecanismo,
            clave_publica=int(detalles["length_public_key"]),
            clave_privada=int(detalles["length_secret_key"]),
            texto_cifrado=0,
            firma=int(detalles["length_signature"]),
        )


def tamanos_classical(mecanismo: str = MECANISMO_RSA) -> Tamanos:
    """Tamanos en bytes de un mecanismo clasico: "RSA-<bits>", X25519, Ed25519.

    Todo se MIDE sobre artefactos reales (len de la clave, del texto cifrado,
    de la firma), nunca se escribe la cifra del estandar a mano.

    Las claves RSA se reportan en DER, no en el PEM que devuelve
    `classical.rsa_generar`: PEM es ese mismo DER en base64 con cabeceras, un
    33% mas grande, y lo que viaja por un canal real (un certificado, un
    handshake) es el DER. Comparar el PEM de RSA contra los bytes crudos de
    ML-KEM inflaria a RSA gratis, justo al reves del sesgo que hay que evitar.

    Para X25519 el campo `texto_cifrado` lleva los 32 bytes de la clave
    publica efimera: en un DH efimero es lo que el emisor pone en el canal, o
    sea el analogo del kem_ciphertext de ML-KEM (1088 B). No es una cifra
    inventada, es la longitud medida de esa clave.
    """
    if mecanismo.startswith("RSA-"):
        publica_pem, privada_pem = rsa_generar(_bits_rsa(mecanismo))
        publica = serialization.load_pem_public_key(publica_pem)
        privada = serialization.load_pem_private_key(privada_pem, password=None)
        publica_der = publica.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        privada_der = privada.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return Tamanos(
            mecanismo=mecanismo,
            clave_publica=len(publica_der),
            clave_privada=len(privada_der),
            # RSA hace las dos cosas, asi que aqui los dos campos aplican: el
            # bloque OAEP y la firma PSS miden los dos el modulo.
            texto_cifrado=len(rsa_cifrar_oaep(publica_pem, MENSAJE)),
            firma=len(rsa_firmar_pss(privada_pem, MENSAJE)),
        )
    if mecanismo == "X25519":
        publica_raw, privada_raw = x25519_generar()
        return Tamanos(
            mecanismo=mecanismo,
            clave_publica=len(publica_raw),
            clave_privada=len(privada_raw),
            texto_cifrado=len(publica_raw),
            firma=0,
        )
    if mecanismo == "Ed25519":
        publica_raw, privada_raw = ed25519_generar()
        return Tamanos(
            mecanismo=mecanismo,
            clave_publica=len(publica_raw),
            clave_privada=len(privada_raw),
            texto_cifrado=0,
            firma=len(ed25519_firmar(privada_raw, MENSAJE)),
        )
    raise ValueError(f"mecanismo clasico no soportado: {mecanismo!r}")


def tabla_medidas(
    repeticiones_pqc: int = REPETICIONES_PQC,
    repeticiones_clasico: int = REPETICIONES_CLASICO,
    mecanismo_rsa: str = MECANISMO_RSA,
) -> list[Medida]:
    """Todas las filas de tiempo del benchmark, en las dos capas.

    Es la tabla del criterio de cierre: RSA-3072 y las dos curvas clasicas
    contra ML-KEM-768 y ML-DSA-65, operacion por operacion. Primero las filas
    "primitiva" (la comparacion entre algoritmos, que es la que va a la figura
    de tiempos y a la tabla del README) y despues las "+carga" (lo que anade
    (de)serializar la clave en cada llamada, ver el docstring del modulo).

    Los dos parametros de repeticiones estan separados porque una iteracion de
    RSA cuesta cuatro ordenes de magnitud mas que una de ML-KEM (ver
    REPETICIONES_PQC / REPETICIONES_CLASICO). Bajarlos es legitimo para un
    smoke test; para la cifra publicable se usan los valores por defecto.

    `mecanismo_rsa` deja cambiar el tamano de modulo, para comparar contra otro
    nivel de seguridad (RSA-2048 son ~112 bits, RSA-3072 ~128) y para que el
    smoke test de la tarea 2.8 pueda usar un modulo pequeno sin pasarse diez
    segundos generando claves.
    """
    filas: list[Medida] = []
    for capa in ("primitiva", "api"):
        capa_actual = cast(Capa, capa)
        for operacion in OPS_RSA:
            filas.append(
                medir_classical(
                    "RSA", mecanismo_rsa, operacion, repeticiones_clasico, capa_actual
                )
            )
        for operacion in OPS_X25519:
            filas.append(
                medir_classical(
                    "ECC", "X25519", operacion, repeticiones_clasico, capa_actual
                )
            )
        for operacion in OPS_ED25519:
            filas.append(
                medir_classical(
                    "ECC", "Ed25519", operacion, repeticiones_clasico, capa_actual
                )
            )
        for operacion in OPS_KEM:
            filas.append(
                medir_kem(MECANISMO_KEM, operacion, repeticiones_pqc, capa_actual)
            )
        # ML-DSA en la capa "api" solo admite verify (ver medir_sig).
        for operacion in OPS_FIRMA if capa == "primitiva" else ("verify",):
            filas.append(
                medir_sig(MECANISMO_SIG, operacion, repeticiones_pqc, capa_actual)
            )
    return filas


def tabla_tamanos() -> list[Tamanos]:
    """Los tamanos de los cinco mecanismos de la tabla, en bytes medidos."""
    return [
        tamanos_classical(MECANISMO_RSA),
        tamanos_classical("X25519"),
        tamanos_classical("Ed25519"),
        tamanos_kem(MECANISMO_KEM),
        tamanos_sig(MECANISMO_SIG),
    ]


def entorno() -> dict[str, str]:
    """Donde se midio: sin esto, los tiempos no significan nada.

    Un benchmark sin maquina ni versiones es una anecdota: los mismos numeros
    salen distintos en otro procesador o con otra build de liboqs. Va dentro
    del JSON para que cualquiera sepa si sus cifras son comparables con estas.
    """
    return {
        "python": platform.python_version(),
        "plataforma": platform.platform(),
        "procesador": platform.processor() or platform.machine(),
        "liboqs": str(oqs.oqs_version()),
        "liboqs_python": str(oqs.oqs_python_version()),
        "medido_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def guardar_json(
    medidas: list[Medida], tamanos: list[Tamanos], ruta: Path = RUTA_JSON
) -> Path:
    """Escribe medidas + tamanos + entorno en `ruta` (JSON) y la devuelve.

    `asdict` de dataclasses hace la conversion sin escribir a mano ningun
    nombre de campo: si el contrato de `types.py` cambiase, el JSON lo sigue
    solo. indent=2 y ensure_ascii=False para que el fichero sea legible en un
    diff de PR, que es el sitio donde se revisa.
    """
    payload = {
        "entorno": entorno(),
        "medidas": [asdict(m) for m in medidas],
        "tamanos": [asdict(t) for t in tamanos],
    }
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return ruta


def entorno_del_json(ruta: Path = RUTA_JSON) -> dict[str, str]:
    """El bloque `entorno` que se guardo con las medidas de `ruta`.

    Lo consume el dashboard para poder decir debajo de la tabla en que maquina
    y con que liboqs se midio: una tabla de tiempos sin esa linea invita a
    comparar cifras que no son comparables.
    """
    payload = json.loads(ruta.read_text())
    return {str(k): str(v) for k, v in payload["entorno"].items()}


def _valor_literal(valor: object, literal: object, campo: str) -> str:
    """Comprueba que `valor` es uno de los valores permitidos por `literal`.

    Lo que sale de json.load es Any: para mypy --strict (y para no colar
    basura en un dataclass del contrato) hay que validar y estrechar. Los
    valores permitidos se sacan con get_args del propio Literal de types.py,
    asi que esta lista no se duplica aqui y no puede quedar desfasada.
    """
    permitidos = get_args(literal)
    if valor not in permitidos:
        raise ValueError(f"{campo} {valor!r} no esta en {list(permitidos)}")
    return cast(str, valor)


def cargar_json(ruta: Path = RUTA_JSON) -> tuple[list[Medida], list[Tamanos]]:
    """Lee el JSON del benchmark y reconstruye (medidas, tamanos).

    Es la puerta por la que las figuras (tarea 2.9) y el dashboard consumen
    los resultados SIN volver a medir: regenerar un PNG no tiene por que
    costar un minuto de CPU ni dar numeros distintos cada vez.

    Valida familia y operacion contra los Literal del contrato y convierte los
    numeros explicitamente: un JSON editado a mano falla aqui, con un mensaje
    claro, y no tres capas mas arriba al dibujar.
    """
    payload = json.loads(ruta.read_text())
    medidas = [
        Medida(
            familia=cast(Familia, _valor_literal(fila["familia"], Familia, "familia")),
            mecanismo=str(fila["mecanismo"]),
            operacion=cast(
                Operacion, _valor_literal(fila["operacion"], Operacion, "operacion")
            ),
            repeticiones=int(fila["repeticiones"]),
            media_ms=float(fila["media_ms"]),
            sigma_ms=float(fila["sigma_ms"]),
            p50_ms=float(fila["p50_ms"]),
        )
        for fila in payload["medidas"]
    ]
    tamanos = [
        Tamanos(
            mecanismo=str(fila["mecanismo"]),
            clave_publica=int(fila["clave_publica"]),
            clave_privada=int(fila["clave_privada"]),
            texto_cifrado=int(fila["texto_cifrado"]),
            firma=int(fila["firma"]),
        )
        for fila in payload["tamanos"]
    ]
    return medidas, tamanos
