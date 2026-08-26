"""scripts/bench_chaos.py — tareas 3.9 y 3.10 (Carlos). Banco de medidas del modulo 3.

    python scripts/bench_chaos.py             # etapas + cadena completa
    python scripts/bench_chaos.py --ciclos    # ademas, la longitud del ciclo (lento)

Responde a las tres preguntas que la guia deja abiertas para este modulo:

  1. Cuanto cuesta cifrar y descifrar, y donde se va el tiempo (por etapas).
  2. Si la asimetria cifrar/descifrar del cap. 5.3 se ve o no se ve, y por que.
  3. Si el cuello de botella justifica compilar con Numba (cap. 1.2). La regla
     del proyecto es "NumPy primero, Numba solo TRAS MEDIR": esto es el medir.

Convencion de medida, heredada del banco del modulo 2 (src/pqc/benchmark.py):
  - Reloj time.perf_counter, NUNCA time.time (time.time salta con NTP).
  - Calentamiento que se ejecuta y se tira.
  - Recolector de basura apagado durante la muestra: una pasada del gc ciclico
    cae en una iteracion arbitraria y contamina la media sin tocar la mediana.
  - Se publican media, sigma de la muestra y p50. Una media sin barra de error
    no es una medida.

No se reutiliza `pqc.benchmark._cronometrar` a proposito: es privado de otro
modulo y su import arrastra oqs (liboqs) entero para cronometrar un bucle de
NumPy. Son quince lineas; duplicar quince lineas cuesta menos que atar el
modulo 3 al 2.

Este script NO escribe ningun JSON versionado, al reves que el del modulo 2.
Alli el JSON existe porque las figuras se dibujan de el; aqui ninguna figura
depende de estas cifras, asi que versionarlas solo crearia un fichero que
envejece en silencio. Las cifras que se publican van al README con la maquina
en la que se midieron.
"""

from __future__ import annotations

import argparse
import gc
import statistics
import time
from collections.abc import Callable

import numpy as np
from chaos import (
    ClaveCaotica,
    cifrar_imagen,
    descifrar_imagen,
    deshacer_adelante,
    difundir_adelante,
    imagen_de_prueba,
    keystream,
    orbita_logistica,
    permutacion_desde_orbita,
)
from chaos.cipher import _material, _valores_de_permutacion

# Lados de las imagenes cuadradas que se miden. 512 es el tamano del criterio
# de cierre de la tarea 3.6 ("cifra 512x512 en menos de 2 segundos").
LADOS = (128, 256, 512)
# Lado para Lorenz: RK4 evalua el campo cuatro veces por paso sobre arrays de
# NumPy y va dos ordenes de magnitud mas lento por muestra que el mapa
# logistico. Medir 512x512 con Lorenz seria un minuto por repeticion.
LADO_LORENZ = 64

REPETICIONES = 9
CALENTAMIENTO = 2

CLAVE_LOGISTICA = ClaveCaotica(sistema="logistico", x0=0.4, r=3.99)
CLAVE_LORENZ = ClaveCaotica(sistema="lorenz", x0=1.0, y0=1.0, z0=1.0)

# --- Parametros del modo --ciclos --------------------------------------
# Muestra de claves para medir la longitud del ciclo de la orbita en precision
# finita (guia Fase 3, cap. 4.5). Son x0 repartidos por (0, 1) con el mismo r
# caotico: lo que se mide es la orbita, no el parametro.
CLAVES_CICLO = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
R_CICLO = 3.99
# Pasos de orbita que se recorren buscando un ciclo. 4 millones son 64 veces
# los 65536 bytes que necesita una imagen de 256x256, y ~1.5 s por clave.
PASOS_CICLO = 4_000_000


def _cronometrar(fn: Callable[[], object]) -> tuple[float, float, float]:
    """(media, sigma, p50) en milisegundos, con el gc apagado.

    La sigma es la de la muestra (n-1 en el denominador): una cifra
    DERIVADA de estas mismas medidas, no un porcentaje inventado. Con una
    sola repeticion devuelve 0.0, que significa "sin barra de error" y no
    "error cero".
    """
    gc.collect()
    gc_estaba_activo = gc.isenabled()
    gc.disable()
    try:
        for _ in range(CALENTAMIENTO):
            fn()
        muestras = []
        for _ in range(REPETICIONES):
            t0 = time.perf_counter()
            fn()
            muestras.append((time.perf_counter() - t0) * 1000.0)
    finally:
        if gc_estaba_activo:
            gc.enable()

    media = statistics.fmean(muestras)
    sigma = statistics.stdev(muestras) if len(muestras) > 1 else 0.0
    return media, sigma, statistics.median(muestras)


def _fila(etiqueta: str, medida: tuple[float, float, float], total: float) -> None:
    media, sigma, p50 = medida
    porcentaje = f"{100.0 * media / total:5.1f} %" if total > 0 else "      "
    print(f"  {etiqueta:<34} {media:9.2f} {sigma:8.2f} {p50:9.2f}   {porcentaje}")


def _cabecera(titulo: str) -> None:
    print(f"\n{titulo}")
    print(
        f"  {'etapa':<34} {'media(ms)':>9} {'sigma':>8} {'p50(ms)':>9}   "
        f"{'del total':>9}"
    )


def medir_cadena() -> dict[int, tuple[float, float]]:
    """Cifrado y descifrado completos para cada tamano.

    Devuelve {lado: (media_cifrar, media_descifrar)} para el resumen final.
    """
    resultados: dict[int, tuple[float, float]] = {}
    _cabecera("CADENA COMPLETA (mapa logistico)")
    for lado in LADOS:
        img = imagen_de_prueba(lado, lado)
        cifrada = cifrar_imagen(img, CLAVE_LOGISTICA)
        # El argumento por defecto liga la variable del bucle: sin el, los
        # cinco lambdas medirian siempre la ultima imagen (ruff B023).
        m_cifrar = _cronometrar(lambda i=img: cifrar_imagen(i, CLAVE_LOGISTICA))
        m_descifrar = _cronometrar(
            lambda c=cifrada: descifrar_imagen(c, CLAVE_LOGISTICA)
        )
        _fila(f"cifrar {lado}x{lado}", m_cifrar, 0.0)
        _fila(f"descifrar {lado}x{lado}", m_descifrar, 0.0)
        resultados[lado] = (m_cifrar[0], m_descifrar[0])

    img_lorenz = imagen_de_prueba(LADO_LORENZ, LADO_LORENZ)
    cifrada_lorenz = cifrar_imagen(img_lorenz, CLAVE_LORENZ)
    _fila(
        f"cifrar {LADO_LORENZ}x{LADO_LORENZ} (Lorenz)",
        _cronometrar(lambda: cifrar_imagen(img_lorenz, CLAVE_LORENZ)),
        0.0,
    )
    _fila(
        f"descifrar {LADO_LORENZ}x{LADO_LORENZ} (Lorenz)",
        _cronometrar(lambda: descifrar_imagen(cifrada_lorenz, CLAVE_LORENZ)),
        0.0,
    )
    return resultados


def medir_etapas(lado: int) -> dict[str, float]:
    """Desglose por etapas de un cifrado, para saber DONDE se va el tiempo.

    Es lo que decide la cuestion de Numba: no sirve compilar la etapa que
    la guia supone cara, sino la que el reloj dice que lo es.
    """
    img = imagen_de_prueba(lado, lado)
    m = img.size

    orbita_perm = _valores_de_permutacion(CLAVE_LOGISTICA, m)
    sigma_perm = permutacion_desde_orbita(orbita_perm, m)
    k_ad, k_atr, iv_ad, _iv_atr = _material(CLAVE_LOGISTICA, m)
    permutada = img.ravel()[sigma_perm]
    difundida = difundir_adelante(permutada, k_ad, iv_ad)

    medidas = {
        "keystream (2M+2 bytes)": _cronometrar(
            lambda: keystream(CLAVE_LOGISTICA, 2 * m + 2)
        ),
        "orbita de la permutacion": _cronometrar(
            lambda: _valores_de_permutacion(CLAVE_LOGISTICA, m)
        ),
        "argsort estable": _cronometrar(
            lambda: permutacion_desde_orbita(orbita_perm, m)
        ),
        "difundir (bucle secuencial)": _cronometrar(
            lambda: difundir_adelante(permutada, k_ad, iv_ad)
        ),
        "deshacer (vectorizado)": _cronometrar(
            lambda: deshacer_adelante(difundida, k_ad, iv_ad)
        ),
    }
    total_cifrado = _cronometrar(lambda: cifrar_imagen(img, CLAVE_LOGISTICA))[0]

    _cabecera(f"ETAPAS DE UN CIFRADO {lado}x{lado} (total {total_cifrado:.1f} ms)")
    for etiqueta, medida in medidas.items():
        _fila(etiqueta, medida, total_cifrado)

    etapas = {etiqueta: medida[0] for etiqueta, medida in medidas.items()}
    # El total del cifrado COMPLETO viaja con las etapas para que el
    # veredicto de abajo use un solo denominador. Sumar las etapas medidas y
    # dividir por esa suma daria porcentajes mas altos y de otra magnitud
    # (el cifrado hace ademas el XOR, los reshape, el hash y la validacion
    # de lambda), y mezclar los dos denominadores en el mismo parrafo es
    # justo el tipo de cifra que no se puede publicar.
    etapas["_total_cifrado"] = total_cifrado
    return etapas


def medir_ciclos() -> None:
    """Longitud del ciclo de la orbita en precision finita (cap. 4.5).

    Cualquier orbita en float64 es periodica: el espacio de estados es
    finito. La unica pregunta es cual es el periodo, y la guia pide
    MEDIRLO y publicarlo en vez de ignorarlo.

    El metodo es exacto y no es Floyd: dos estados float64 IDENTICOS
    tienen el mismo futuro, asi que la orbita cicla dentro del tramo
    generado si y solo si el tramo contiene un valor repetido. Eso es un
    np.unique -O(n log n), medio segundo para cuatro millones de pasos-
    frente a las decenas de segundos que cuesta recorrer el mismo tramo
    con la liebre y la tortuga comparando de uno en uno.

    Lo que se publica no es "el ciclo mide X" sino una COTA INFERIOR:
    "no cicla en menos de PASOS_CICLO pasos". Es lo honesto cuando no se
    encuentra ninguno, y es exactamente lo que el README dice.
    """
    print(f"\nLONGITUD DEL CICLO (r = {R_CICLO}, {PASOS_CICLO:,} pasos por clave)")
    print(f"  {'x0':<10} {'valores distintos':>18} {'ciclo':>28}")
    ciclos_hallados: list[int] = []
    for x0 in CLAVES_CICLO:
        t0 = time.perf_counter()
        orb = orbita_logistica(x0, R_CICLO, PASOS_CICLO)
        distintos = int(np.unique(orb).size)
        if distintos == orb.size:
            veredicto = f"ninguno < {PASOS_CICLO:,}"
        else:
            # Hay al menos un estado repetido: la orbita esta ciclando. Se
            # localiza el primer par repetido para dar la longitud exacta.
            orden = np.argsort(orb, kind="stable")
            ordenados = orb[orden]
            iguales = np.flatnonzero(ordenados[1:] == ordenados[:-1])
            primero = int(np.min(np.abs(np.diff(orden[iguales[0] : iguales[0] + 2]))))
            ciclos_hallados.append(primero)
            veredicto = f"{primero:,}"
        transcurrido = time.perf_counter() - t0
        print(
            f"  {x0:<10.4f} {distintos:>18,} {veredicto:>28}   "
            f"({transcurrido:.1f} s)"
        )

    if ciclos_hallados:
        print(f"\n  minimo observado: {min(ciclos_hallados):,} pasos")
    else:
        print(
            f"\n  ninguna de las {len(CLAVES_CICLO)} claves cicla en "
            f"{PASOS_CICLO:,} pasos: la cota inferior del ciclo es ese numero, "
            f"que son {PASOS_CICLO // 3:,} bytes de keystream"
        )


def _veredicto_numba(etapas: dict[str, float], lado: int) -> None:
    """La decision sobre Numba, escrita con los numeros que la sostienen.

    La guia (cap. 1.2) da por hecho que el cuello de botella es el bucle
    secuencial de la difusion, y por eso lo senala como el sitio donde
    Numba tendria sentido. El reloj dice otra cosa, y por eso se mide.
    """
    total = etapas["_total_cifrado"]
    orbitas = etapas["keystream (2M+2 bytes)"] + etapas["orbita de la permutacion"]
    difusion = etapas["difundir (bucle secuencial)"] * 2  # ida y vuelta
    print(f"\nDECISION SOBRE NUMBA (medida en {lado}x{lado})")
    print(f"  porcentajes sobre un cifrado completo, {total:.1f} ms")
    print(
        f"  generar orbitas (bucles de Python): {orbitas:7.1f} ms  "
        f"({100.0 * orbitas / total:.0f} %)"
    )
    print(
        f"  difusion, las dos pasadas:          {difusion:7.1f} ms  "
        f"({100.0 * difusion / total:.0f} %)"
    )
    print(
        "\n  El cuello de botella NO es la difusion: es la generacion de las\n"
        "  orbitas, que es justo el camino del keystream. Compilar ahi es\n"
        "  exactamente lo que la guia (cap. 1.2) marca como mas peligroso:\n"
        "  Numba puede reasociar y emitir FMA, y un cambio en el ultimo bit\n"
        "  de la mantisa destruye la orbita en ~50 iteraciones. Con la\n"
        "  difusion sola el techo de mejora es el porcentaje de arriba.\n"
        "  Veredicto: el pipeline se queda en NumPy. numba no se usa."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ciclos",
        action="store_true",
        help=(
            "mide ademas la longitud del ciclo de la orbita para una muestra "
            "de claves (~15 s). Es la limitacion del cap. 4.5, que se mide y "
            "se publica en vez de ignorarse."
        ),
    )
    args = parser.parse_args()

    print(f"repeticiones={REPETICIONES}, calentamiento={CALENTAMIENTO}, gc apagado")
    tiempos = medir_cadena()
    etapas = medir_etapas(256)
    _veredicto_numba(etapas, 256)

    print("\nASIMETRIA CIFRAR / DESCIFRAR")
    print(
        "  La guia (cap. 5.3) anticipa que descifrar salga uno o dos ordenes de\n"
        "  magnitud mas rapido que cifrar, porque deshacer la difusion es una\n"
        "  linea vectorizada y hacerla es un bucle. En la ETAPA se ve; en la\n"
        "  CADENA no, y la explicacion esta en el desglose de arriba: las dos\n"
        "  direcciones regeneran el MISMO keystream, que es la parte cara."
    )
    for lado, (cifrar, descifrar) in tiempos.items():
        print(
            f"  {lado}x{lado}: cifrar {cifrar:7.1f} ms   descifrar "
            f"{descifrar:7.1f} ms   x{cifrar / descifrar:.2f}"
        )

    if args.ciclos:
        medir_ciclos()


if __name__ == "__main__":
    main()
