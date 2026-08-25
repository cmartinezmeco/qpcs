"""scripts/check_chaos_determinism.py — tarea 3.9 (Carlos). Harness de determinismo.

Comprueba que el modulo de caos produce EXACTAMENTE los mismos bytes en dos
entornos distintos (el venv local y el contenedor):

    python scripts/check_chaos_determinism.py           # comprueba y resume
    python scripts/check_chaos_determinism.py --json    # solo las huellas, en JSON

Por que existe un script ademas del test
----------------------------------------
tests/chaos/test_keystream.py ya compara el keystream contra
vectors/keystream_v1.json, y eso es lo que la CI corre dentro del contenedor.
Pero un test solo sabe decir "pasa" o "falla" en el entorno donde se ejecuta, y
el fallo que hay que cazar aqui es de OTRA naturaleza: dos entornos que dan
resultados distintos, cada uno consistente consigo mismo (guia Fase 3, cap. 4.1).

Este script emite HUELLAS, no veredictos. Con --json produce un objeto
comparable byte a byte entre maquinas:

    python scripts/check_chaos_determinism.py --json > /tmp/local.json
    docker run --rm -v "$PWD":/app qpcs:ci \
        python scripts/check_chaos_determinism.py --json > /tmp/contenedor.json
    diff /tmp/local.json /tmp/contenedor.json && echo "determinismo cruzado OK"

Y cubre mas terreno que el test del vector: el vector fija el KEYSTREAM, que es
donde empieza el problema, pero no dice nada de la cadena completa. Si alguien
cambiara el orden de las dos pasadas de difusion, o el troceado de
_material, el keystream seguiria coincidiendo y las imagenes ya cifradas
dejarian de descifrarse. Por eso aqui tambien se toma la huella del cifrado
entero, con los dos sistemas.

Convencion del equipo: los scripts SI pueden imprimir (src/chaos usa logging).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
from chaos import (
    ClaveCaotica,
    cifrar_imagen,
    descifrar_imagen,
    imagen_de_prueba,
    keystream_logistico,
)
from chaos.types import ESCALA_BITS, SUBMUESTREO, TRANSITORIO

# El vector de prueba versionado. NO se regenera desde aqui, ni desde ningun
# otro sitio: si un test falla contra el, el bug esta en el codigo (guia Fase 3,
# cap. 7.1). Este script solo lo LEE.
RUTA_VECTOR = Path(__file__).resolve().parents[1] / "vectors" / "keystream_v1.json"

# Bytes de keystream que se regeneran para contrastar con el vector. Es el
# tamano que el propio vector declara en sha256_de_1e6_bytes: cambiarlo aqui
# haria que la comparacion no significara nada.
N_BYTES_VECTOR = 1_000_000

# Imagenes de las huellas de la cadena completa. La de Lorenz es pequena a
# proposito: RK4 hace cuatro evaluaciones del campo por paso con arrays de
# NumPy y va unas 150 veces mas lento por muestra que el mapa logistico, asi
# que 32x32 da la misma garantia de determinismo en una fraccion del tiempo.
# La logistica NO es cuadrada (128x97) tambien a proposito: una forma cuadrada
# esconderia una confusion entre alto y ancho en el reshape.
FORMA_LOGISTICA = (128, 97)
FORMA_LORENZ = (32, 32)

CLAVE_LOGISTICA = ClaveCaotica(sistema="logistico", x0=0.4, r=3.99)
CLAVE_LORENZ = ClaveCaotica(sistema="lorenz", x0=1.0, y0=1.0, z0=1.0)


def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def _huella_de_cifrado(clave: ClaveCaotica, alto: int, ancho: int) -> dict[str, object]:
    """Huella de la cadena ENTERA, no solo del keystream.

    Se incluye el iv porque sale del keystream (es su byte 2M) y el
    hash_plano porque es lo que permite verificar el descifrado sin tener
    la imagen delante. El round-trip se comprueba aqui mismo: una huella
    estable de un cifrado que no se descifra no valdria de nada.
    """
    img = imagen_de_prueba(alto, ancho)
    cifrada = cifrar_imagen(img, clave)
    descifrada = descifrar_imagen(cifrada, clave)
    return {
        "forma": f"{alto}x{ancho}",
        "sha256_plano": _sha256(img.tobytes()),
        "sha256_cifrado": _sha256(cifrada.datos.tobytes()),
        "iv": int(cifrada.iv),
        "round_trip_exacto": bool(np.array_equal(descifrada, img)),
    }


def huellas() -> dict[str, object]:
    """Todas las huellas del modulo, en un objeto serializable.

    Es lo que se compara entre entornos. Deliberadamente NO incluye nada
    que dependa de la maquina (ni tiempos, ni versiones, ni rutas): si
    dos ejecuciones difieren en algo de aqui, el determinismo esta roto.
    """
    ks = keystream_logistico(CLAVE_LOGISTICA, N_BYTES_VECTOR)
    return {
        "constantes": {
            "transitorio": TRANSITORIO,
            "submuestreo": SUBMUESTREO,
            "escala_bits": ESCALA_BITS,
        },
        "keystream": {
            "clave": {"x0": CLAVE_LOGISTICA.x0, "r": CLAVE_LOGISTICA.r},
            "n_bytes": N_BYTES_VECTOR,
            "primeros_64_bytes_hex": ks[:64].tobytes().hex(),
            "sha256": _sha256(ks.tobytes()),
        },
        "cifrado_logistico": _huella_de_cifrado(CLAVE_LOGISTICA, *FORMA_LOGISTICA),
        "cifrado_lorenz": _huella_de_cifrado(CLAVE_LORENZ, *FORMA_LORENZ),
    }


def _contrastar_con_el_vector(datos: dict[str, object]) -> list[str]:
    """Compara las huellas contra vectors/keystream_v1.json.

    Devuelve la lista de discrepancias (vacia si todo cuadra). Se
    comprueban tambien las CONSTANTES del contrato: el vector las lleva
    escritas dentro precisamente para que cambiar TRANSITORIO o
    SUBMUESTREO sin cambiar de version del vector salte aqui y no en una
    imagen que dejo de descifrarse tres semanas despues.
    """
    vector = json.loads(RUTA_VECTOR.read_text(encoding="utf-8"))
    fallos: list[str] = []

    constantes = dict(datos["constantes"])  # type: ignore[arg-type]
    for nombre, valor_vector in vector["constantes"].items():
        if constantes[nombre] != valor_vector:
            fallos.append(
                f"la constante {nombre} vale {constantes[nombre]} en types.py y "
                f"{valor_vector} en el vector: o se revierte el cambio o el "
                f"vector pasa a keystream_v2.json en su propio PR"
            )

    clave_vector = vector["clave"]
    keystream = dict(datos["keystream"])  # type: ignore[arg-type]
    if dict(keystream["clave"]) != clave_vector:  # type: ignore[arg-type]
        fallos.append(
            f"este script usa la clave {keystream['clave']} y el vector se "
            f"genero con {clave_vector}: la comparacion no significaria nada"
        )
        return fallos

    if keystream["primeros_64_bytes_hex"] != vector["primeros_64_bytes_hex"]:
        fallos.append("los primeros 64 bytes del keystream NO coinciden con el vector")
    if keystream["sha256"] != vector["sha256_de_1e6_bytes"]:
        fallos.append(
            f"el SHA-256 de {N_BYTES_VECTOR} bytes de keystream NO coincide con "
            f"el vector"
        )
    return fallos


def _imprimir_resumen(datos: dict[str, object], fallos: list[str]) -> None:
    """El informe legible. El JSON es para diff; esto es para leer."""
    keystream = dict(datos["keystream"])  # type: ignore[arg-type]
    print(f"entorno            {platform.platform()}")
    print(f"python             {platform.python_version()}")
    print(f"numpy              {np.__version__}")
    print(f"vector             {RUTA_VECTOR}")
    print()
    print(f"keystream[:64]     {keystream['primeros_64_bytes_hex'][:32]}...")
    print(f"sha256 de 1e6 B    {keystream['sha256']}")
    for etiqueta in ("cifrado_logistico", "cifrado_lorenz"):
        bloque = dict(datos[etiqueta])  # type: ignore[arg-type]
        print(
            f"{etiqueta:<18} {bloque['forma']:>7}  sha256 "
            f"{str(bloque['sha256_cifrado'])[:16]}...  iv {bloque['iv']:>3}  "
            f"round-trip {'exacto' if bloque['round_trip_exacto'] else 'ROTO'}"
        )
    print()
    if fallos:
        print("DETERMINISMO ROTO:")
        for fallo in fallos:
            print(f"  - {fallo}")
    else:
        print("las huellas coinciden con el vector versionado.")
        print(
            "para el cruce local/contenedor, compara la salida de --json en los "
            "dos entornos (ver el docstring de este fichero)."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "emite solo las huellas en JSON, ordenadas y sin datos del entorno, "
            "para poder hacer diff entre el venv local y el contenedor"
        ),
    )
    args = parser.parse_args()

    datos = huellas()
    fallos = _contrastar_con_el_vector(datos)
    # El round-trip es parte del contrato: una huella estable de un cifrado
    # irreversible seria determinismo sin cifrado.
    for etiqueta in ("cifrado_logistico", "cifrado_lorenz"):
        bloque = dict(datos[etiqueta])  # type: ignore[arg-type]
        if not bloque["round_trip_exacto"]:
            fallos.append(f"{etiqueta}: el descifrado NO devuelve la imagen original")

    if args.json:
        # sort_keys para que el diff entre entornos no dependa del orden de
        # insercion, y salto de linea final para que `diff` no se queje.
        print(json.dumps(datos, indent=2, sort_keys=True))
    else:
        _imprimir_resumen(datos, fallos)

    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
