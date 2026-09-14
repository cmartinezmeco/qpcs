"""scripts/make_pqc_plots.py — tarea 2.9 (Carlos). Graficas Matplotlib.

Regenera TODAS las figuras del modulo 2 con un solo comando:

    python scripts/make_pqc_plots.py            # dibuja con el JSON versionado
    python scripts/make_pqc_plots.py --medir    # re-mide (lento) y luego dibuja

Por que dos modos: medir el benchmark completo cuesta del orden de un minuto de
CPU (el keygen de RSA-3072 solo ya son ~25 s) y sus cifras dependen de la
maquina. Los resultados viven en docs/benchmark_pqc.json, versionado, y las
figuras leen de ahi: retocar un color no obliga a re-medir ni cambia los
numeros del README. --medir es lo que se lanza DENTRO del contenedor cuando se
quieren cifras nuevas (ver el README del modulo).

Reglas de la tarea:
  - Tres figuras, ni una mas. Salida versionada en docs/img/ (PNG, dpi=150,
    fondo blanco).
  - Semilla fija donde aplique: la parte Shor es reproducible bit a bit. La
    cripto real NO se siembra (sus claves deben ser impredecibles), y por eso
    las figuras 1 y 2 salen de un JSON medido, no de una semilla.
  - Barras de error DERIVADAS: el yerr de la figura 1 es la sigma de la muestra
    que calculo el benchmark, nunca un porcentaje inventado. La figura 2 no
    lleva barras porque los tamanos son deterministas: los fija el estandar.
  - Escala logaritmica en las figuras 1 y 2: los valores abarcan cuatro
    ordenes de magnitud (de 0.02 ms a 250 ms; de 32 B a 4032 B).
  - Ejes etiquetados con unidades. Matplotlib por defecto, sin estilos
    exoticos. Sin titulo dentro de la figura: el titulo va en el pie del
    README (misma regla que make_qkd_plots.py).
  - Este script NO reimplementa logica del modulo: consume `pqc.benchmark` y
    `pqc.shor` tal y como los exporta el paquete. La unica excepcion
    documentada es el histograma de fases de la figura 3 (ver figura_3_shor).

Convencion del equipo: los scripts SI pueden imprimir (src/ usa logging). Este
imprime la tabla tiempo/tamano y el resultado de Shor, que son exactamente los
numeros que van en el README.
"""

from __future__ import annotations

import argparse
from math import gcd
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from pqc.benchmark import (
    RUTA_JSON,
    SUFIJO_CAPA_API,
    cargar_json,
    guardar_json,
    tabla_medidas,
    tabla_tamanos,
)
from pqc.shor import circuito_orden_15, factorizar_15, histograma_fases_15
from pqc.types import Medida, Tamanos

# Backend sin pantalla: el script corre igual en local, en la CI y en Docker.
# switch_backend (y no matplotlib.use antes del import) para no romper el
# orden de imports que exige ruff (E402).
plt.switch_backend("Agg")

# Semilla unica de la parte Shor: reproducibilidad bit a bit de la figura 3.
SEMILLA = 42
# Base y qubits de conteo del circuito que se dibuja y se muestrea. a=7 tiene
# orden 4 modulo 15, asi que las fases validas son los cuatro multiplos de 1/4:
# es el caso donde el histograma ensena el mecanismo con mas claridad (y el
# mismo que fija el test test_fase_es_multiplo_de_1_sobre_4_para_a7).
A_SHOR = 7
N_COUNT = 8
# Shots del histograma de fases. 4096 dan picos con altura estable sin que la
# ejecucion pase de unas decimas de segundo.
SHOTS = 4096

# Mecanismos de las figuras 1 y 2, en orden de aparicion: primero los tres
# clasicos, despues los dos post-cuanticos.
MECANISMOS = ("RSA-3072", "X25519", "Ed25519", "ML-KEM-768", "ML-DSA-65")
PQC = ("ML-KEM-768", "ML-DSA-65")

# Grupos del eje x de la figura 1. Cada grupo junta las operaciones que hacen
# LO MISMO con nombres distintos segun la familia: "encrypt" (RSA cifra un
# bloque) y "encaps" (ML-KEM transporta un secreto) no son la misma primitiva,
# pero son el mismo paso del protocolo y por eso se comparan lado a lado. El
# intercambio de X25519 aparece en el grupo de desencapsular, etiquetado
# "decaps" por el benchmark (ver medir_classical).
GRUPOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("keygen", ("keygen",)),
    ("cifrar /\nencapsular", ("encrypt", "encaps")),
    ("descifrar /\ndesencapsular", ("decrypt", "decaps")),
    ("firmar", ("sign",)),
    ("verificar", ("verify",)),
)

# Los cuatro artefactos de la figura 2 y de que campo de `Tamanos` salen.
ARTEFACTOS: tuple[tuple[str, str], ...] = (
    ("clave\npublica", "clave_publica"),
    ("clave\nprivada", "clave_privada"),
    ("texto cifrado /\nclave efimera", "texto_cifrado"),
    ("firma", "firma"),
)

# Salida versionada, relativa a la raiz del repo (no al cwd): el script
# funciona igual lanzado desde la raiz o desde scripts/.
DIR_SALIDA = Path(__file__).resolve().parents[1] / "docs" / "img"


def _color(mecanismo: str) -> str:
    """Un color estable por mecanismo, en el orden del ciclo por defecto."""
    return f"C{MECANISMOS.index(mecanismo)}"


def _trama(mecanismo: str) -> str:
    """Trama diagonal para lo post-cuantico.

    El color ya distingue mecanismos, pero la division que cuenta la figura es
    clasico vs post-cuantico: la trama la hace visible sin depender del color
    (y sobrevive a una impresion en blanco y negro).
    """
    return "//" if mecanismo in PQC else ""


def _indice(medidas: list[Medida]) -> dict[tuple[str, str], Medida]:
    """(mecanismo, operacion) -> Medida, para buscar filas sin recorrer listas."""
    return {(m.mecanismo, m.operacion): m for m in medidas}


def _fila(
    indice: dict[tuple[str, str], Medida], mecanismo: str, operaciones: tuple[str, ...]
) -> Medida | None:
    """La Medida de `mecanismo` para la primera de `operaciones` que exista.

    Devuelve None si ese mecanismo no hace ninguna de esas operaciones (X25519
    no firma, Ed25519 no cifra): en la figura simplemente no se dibuja barra.
    """
    for operacion in operaciones:
        medida = indice.get((mecanismo, operacion))
        if medida is not None:
            return medida
    return None


def figura_1_tiempos(medidas: list[Medida]) -> None:
    """Tiempos por operacion, clasico vs post-cuantico. La figura estrella.

    Panel A: barras agrupadas por operacion con las barras de error de la
    sigma medida, en escala log. Es la capa "primitiva" del benchmark, la que
    compara ALGORITMOS: el material de clave ya esta cargado, asi que lo que
    se ve es el coste de cifrar/firmar y no el de nuestro formato de claves.

    Panel B: lo que anade (de)serializar la clave en cada llamada, o sea la
    diferencia entre la capa "primitiva" y la capa "+carga" del benchmark. Va
    en esta figura y no escondido en el JSON porque es el detalle que mas
    facilmente convierte un benchmark en una mentira: en RSA la carga del PEM
    (que OpenSSL 3 valida entera) cuesta ~60 veces mas que el descifrado.
    """
    indice = _indice(medidas)
    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(13, 5.2))

    # --- Panel A: comparacion entre algoritmos ---------------------------
    ancho = 0.8 / len(MECANISMOS)
    for j, mecanismo in enumerate(MECANISMOS):
        xs: list[float] = []
        medias: list[float] = []
        sigmas: list[float] = []
        for i, (_, operaciones) in enumerate(GRUPOS):
            medida = _fila(indice, mecanismo, operaciones)
            if medida is None:
                continue
            xs.append(i + (j - (len(MECANISMOS) - 1) / 2) * ancho)
            medias.append(medida.media_ms)
            sigmas.append(medida.sigma_ms)
        medias_arr = np.asarray(medias)
        sigmas_arr = np.asarray(sigmas)
        # El extremo INFERIOR de la barra de error se recorta al 90% de la
        # media para no cruzar el cero en un eje logaritmico (hay operaciones
        # con sigma del orden de la media: el keygen de RSA busca primos al
        # azar). El extremo superior es la sigma entera y el valor exacto esta
        # en el JSON y en la tabla del README: no se esta escondiendo nada.
        yerr = np.vstack([np.minimum(sigmas_arr, medias_arr * 0.9), sigmas_arr])
        ax_a.bar(
            xs,
            medias_arr,
            width=ancho,
            color=_color(mecanismo),
            hatch=_trama(mecanismo),
            edgecolor="white",
            label=mecanismo,
            yerr=yerr,
            capsize=2,
            error_kw={"lw": 0.9, "ecolor": "0.25"},
        )

    ax_a.set_yscale("log")
    # Aire por arriba para que la leyenda no pise la barra mas alta (el keygen
    # de RSA, que se va tres ordenes de magnitud por encima del resto). El
    # maximo se toma SOLO de las filas que este panel dibuja: metiendo tambien
    # las de la capa "+carga" (que van al panel B) el techo salia de una barra
    # que no esta aqui y aplastaba el panel entero.
    dibujadas = [m.media_ms for m in medidas if m.mecanismo in MECANISMOS]
    ax_a.set_ylim(top=max(dibujadas) * 12)
    ax_a.set_xticks(range(len(GRUPOS)), [nombre for nombre, _ in GRUPOS], fontsize=9)
    ax_a.set_ylabel("tiempo por operacion (ms, escala log)")
    ax_a.set_xlabel("operacion (nombre clasico / nombre del KEM)")
    ax_a.grid(axis="y", alpha=0.25, lw=0.5)
    ax_a.legend(fontsize=8, ncols=2)
    ax_a.set_title("A · coste del algoritmo (clave ya cargada)", fontsize=10)

    # --- Panel B: lo que cuesta la serializacion de la clave -------------
    # Solo las filas que existen en las dos capas, ordenadas por el factor
    # entre ellas: arriba donde la serializacion pesa mas.
    pares: list[tuple[str, float, float]] = []
    for (mecanismo, operacion), medida in indice.items():
        if mecanismo.endswith(SUFIJO_CAPA_API):
            continue
        con_carga = indice.get((mecanismo + SUFIJO_CAPA_API, operacion))
        if con_carga is None:
            continue
        pares.append(
            (f"{mecanismo} · {operacion}", medida.media_ms, con_carga.media_ms)
        )
    pares.sort(key=lambda par: par[2] / par[1])

    # Grafico de mancuernas (dos marcadores unidos) y no barras: en un eje
    # logaritmico la LONGITUD de una barra no es proporcional a su valor, asi
    # que un par de barras log invita a leer mal el factor. Con dos marcadores
    # lo que se compara es la posicion, que en log si es honesta, y el largo
    # del segmento es literalmente el sobrecoste.
    ys = np.arange(len(pares))
    for y, (_, primitiva, con_carga) in zip(ys, pares, strict=True):
        ax_b.plot([primitiva, con_carga], [y, y], color="0.65", lw=1.3, zorder=1)
        ax_b.text(
            con_carga * 1.6,
            y,
            f"×{con_carga / primitiva:.0f}" if con_carga / primitiva >= 10 else "",
            va="center",
            fontsize=7.5,
            color="C3",
        )
    ax_b.scatter(
        [par[1] for par in pares],
        ys,
        s=32,
        color="C0",
        zorder=3,
        label="primitiva (clave ya cargada)",
    )
    ax_b.scatter(
        [par[2] for par in pares],
        ys,
        s=32,
        color="C3",
        marker="s",
        zorder=3,
        label="API del modulo (+carga de clave)",
    )
    ax_b.set_xscale("log")
    ax_b.set_yticks(ys, [par[0] for par in pares], fontsize=7)
    ax_b.set_ylim(-0.8, len(pares) - 0.2)
    ax_b.set_xlabel("tiempo por operacion (ms, escala log)")
    ax_b.set_xlim(min(par[1] for par in pares) / 3, max(par[2] for par in pares) * 12)
    ax_b.grid(axis="x", alpha=0.25, lw=0.5)
    ax_b.legend(fontsize=8, loc="lower right")
    ax_b.set_title("B · lo que anade (de)serializar la clave", fontsize=10)

    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "pqc_tiempos.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_2_tamanos(tamanos: list[Tamanos]) -> None:
    """Tamanos en bytes: la contraparte honesta de la figura 1.

    Aqui la PQC pierde, y hay que ensenarlo: una firma ML-DSA-65 pesa 3309
    bytes contra los 64 de Ed25519. Juntas, las figuras 1 y 2 cuentan el
    compromiso entero (se paga en ancho de banda, no en CPU).

    Sin barras de error a proposito: los tamanos no son una medida con
    dispersion, son deterministas (los fija FIPS 203/204 y el modulo RSA). La
    unica cifra que necesita explicacion es el "texto cifrado" de X25519: son
    los 32 bytes de la clave publica efimera, que es lo que un DH pone en el
    canal (el analogo del kem_ciphertext de ML-KEM).
    """
    por_mecanismo = {t.mecanismo: t for t in tamanos}
    fig, ax = plt.subplots(figsize=(9, 4.8))

    ancho = 0.8 / len(MECANISMOS)
    for j, mecanismo in enumerate(MECANISMOS):
        # .get y no [ ]: si el JSON viene de una version que aun no media uno
        # de los cinco mecanismos, la figura se dibuja sin esa serie en vez de
        # morir con un KeyError a mitad del script.
        tam = por_mecanismo.get(mecanismo)
        if tam is None:
            continue
        xs: list[float] = []
        valores: list[int] = []
        for i, (_, campo) in enumerate(ARTEFACTOS):
            bytes_ = int(getattr(tam, campo))
            # 0 significa "no aplica" en el contrato de Tamanos (una firma no
            # tiene texto cifrado): no se dibuja barra, no se dibuja un cero.
            if bytes_ == 0:
                continue
            xs.append(i + (j - (len(MECANISMOS) - 1) / 2) * ancho)
            valores.append(bytes_)
        barras = ax.bar(
            xs,
            valores,
            width=ancho,
            color=_color(mecanismo),
            hatch=_trama(mecanismo),
            edgecolor="white",
            label=mecanismo,
        )
        ax.bar_label(barras, fontsize=6.5, padding=2, rotation=90)

    ax.set_yscale("log")
    # Suelo en 10 B para que las barras de 32 B (X25519 / Ed25519) se vean, y
    # techo con aire para que las etiquetas de 4032 B no pisen la leyenda.
    ax.set_ylim(10, 30_000)
    ax.set_xticks(
        range(len(ARTEFACTOS)), [nombre for nombre, _ in ARTEFACTOS], fontsize=9
    )
    ax.set_ylabel("tamano del artefacto (bytes, escala log)")
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    ax.legend(fontsize=8, ncols=2)
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "pqc_tamanos.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_3_shor() -> None:
    """Shor: el circuito de estimacion de fase y el histograma de la fase.

    Es la prueba VISUAL de que el mecanismo funciona: los picos del histograma
    caen en los multiplos de 1/r (con a=7 mod 15, r=4), que es exactamente lo
    que las fracciones continuas convierten en el orden y de ahi en los
    factores 3 y 5.

    Ya NO hay excepcion a "el script no reimplementa logica del modulo": el
    muestreo con muchos disparos vive en `shor.histograma_fases_15`, que es
    justo lo que faltaba (medir_fase_15 devuelve UNA fase por llamada, que es
    lo que necesita la factorizacion). Antes estas mismas siete lineas -
    transpile, run con SHOTS y conversion de bitstring a fase - estaban aqui y
    otra vez en el dashboard.
    """
    histograma = histograma_fases_15(
        A_SHOR, np.random.default_rng(SEMILLA), N_COUNT, SHOTS
    )
    fases = np.array(list(histograma.keys()))
    cuentas = np.array(list(histograma.values()))

    # La factorizacion completa, con la misma semilla que el test: los numeros
    # que se anotan en la figura salen de aqui, no escritos a mano.
    res = factorizar_15(np.random.default_rng(SEMILLA))
    print(
        f"[figura 3] Shor: {res.n} = {res.factores[0]} x {res.factores[1]} "
        f"(a = {res.a}, r = {res.orden}, intentos = {res.intentos}, "
        f"fase = {res.fase_medida:.3f}, ok = {res.ok})"
    )
    print(f"[figura 3] fases medidas con a={A_SHOR}: {np.sort(fases)}")

    fig, (ax_circuito, ax_hist) = plt.subplots(
        1, 2, figsize=(15, 4.8), gridspec_kw={"width_ratios": [1.5, 1]}
    )

    # --- Panel A: el circuito -------------------------------------------
    # fold=-1: sin plegado, el circuito entero en una linea. Necesita
    # pylatexenc (esta en requirements.txt) o el dibujante mpl no arranca.
    # El circuito se pide aqui solo para DIBUJARLO: quien lo ejecuta es
    # histograma_fases_15, que construye el suyo con los mismos parametros.
    circuito_orden_15(A_SHOR, N_COUNT).draw(
        "mpl", ax=ax_circuito, fold=-1, style="clifford"
    )
    ax_circuito.set_title(
        f"A · estimacion de fase de U|y> = |{A_SHOR}y mod 15>  "
        f"({N_COUNT} qubits de conteo + 4 de trabajo)",
        fontsize=10,
    )

    # --- Panel B: histograma de la fase medida ---------------------------
    # El orden real de A_SHOR modulo 15, calculado (no escrito a mano): es la
    # prediccion contra la que se comparan los picos medidos. Y la reduccion
    # clasica para ESTA base, para que la anotacion de la figura sea aritmetica
    # de la misma `a` que el histograma y no la de la ejecucion de arriba (que
    # elige su `a` con el rng y da los mismos factores por otro camino).
    r_teorico = next(k for k in range(1, 15) if pow(A_SHOR, k, 15) == 1)
    x = pow(A_SHOR, r_teorico // 2, 15)
    p, q = gcd(x - 1, 15), gcd(x + 1, 15)
    for k in range(r_teorico):
        ax_hist.axvline(k / r_teorico, ls="--", color="gray", lw=1, zorder=1)
        ax_hist.text(
            k / r_teorico,
            SHOTS * 0.31,
            f"$s/r = {k}/{r_teorico}$",
            rotation=90,
            fontsize=8,
            color="gray",
            ha="right",
            va="bottom",
        )
    ax_hist.bar(fases, cuentas, width=0.012, color="C0", zorder=3)
    ax_hist.set_xlabel(f"fase medida $y/2^{{{N_COUNT}}}$ (adimensional)")
    ax_hist.set_ylabel(f"veces medida (de {SHOTS} shots)")
    ax_hist.set_xlim(-0.05, 1.0)
    ax_hist.set_ylim(0, SHOTS * 0.45)
    ax_hist.grid(axis="y", alpha=0.25, lw=0.5)
    ax_hist.text(
        0.03,
        0.97,
        "las lineas discontinuas NO son un ajuste: son los\n"
        f"multiplos de $1/r$ con $r = {r_teorico}$, el orden real de "
        f"${A_SHOR}$ mod $15$\n"
        f"reduccion clasica: $\\gcd({A_SHOR}^{{{r_teorico // 2}}} \\pm 1,"
        f"\\ 15) = \\{{{min(p, q)}, {max(p, q)}\\}}$",
        transform=ax_hist.transAxes,
        fontsize=8,
        va="top",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.85},
    )
    ax_hist.set_title("B · la fase medida cae en los multiplos de 1/r", fontsize=10)

    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "shor_fase.png", dpi=150, facecolor="white")
    plt.close(fig)


def _imprimir_tabla(medidas: list[Medida], tamanos: list[Tamanos]) -> None:
    """La tabla del README por stdout: tiempos de la capa primitiva y tamanos.

    Se imprime siempre (con o sin --medir) para que copiar las cifras al
    README no obligue a abrir el JSON a mano.
    """
    por_mecanismo = {t.mecanismo: t for t in tamanos}
    print(
        f"\n{'operacion':<10} {'mecanismo':<21} {'media (ms)':>11} "
        f"{'sigma (ms)':>11} {'p50 (ms)':>10} {'reps':>5}  tamano"
    )
    for medida in medidas:
        if medida.mecanismo.endswith(SUFIJO_CAPA_API):
            continue
        # .get y no [ ]: `tabla_medidas` y `tabla_tamanos` son independientes,
        # asi que no todo mecanismo medido tiene por que tener tamanos. El
        # sobre hibrido ("ML-KEM-768 hibrido") es el primer caso real: mide
        # tiempo pero no es un mecanismo con claves propias. Antes esto era un
        # KeyError que mataba el script AL FINAL, despues de haber reescrito
        # ya el JSON y las tres figuras.
        tam = por_mecanismo.get(medida.mecanismo)
        etiquetas = (
            {
                "keygen": f"pk {tam.clave_publica} B",
                "encaps": f"ct {tam.texto_cifrado} B",
                "encrypt": f"ct {tam.texto_cifrado} B",
                "sign": f"sig {tam.firma} B",
            }
            if tam is not None
            else {}
        )
        print(
            f"{medida.operacion:<10} {medida.mecanismo:<21} {medida.media_ms:>11.3f} "
            f"{medida.sigma_ms:>11.3f} {medida.p50_ms:>10.3f} "
            f"{medida.repeticiones:>5}  {etiquetas.get(medida.operacion, '—')}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--medir",
        action="store_true",
        help=(
            "re-mide el benchmark completo (~1 min de CPU) y reescribe "
            f"{RUTA_JSON.name}. Sin este flag se dibuja con el JSON versionado."
        ),
    )
    args = parser.parse_args()

    if args.medir:
        print("midiendo el benchmark completo (esto tarda ~1 min)...")
        medidas = tabla_medidas()
        tamanos = tabla_tamanos()
        print(f"resultados escritos en {guardar_json(medidas, tamanos)}")
    else:
        if not RUTA_JSON.exists():
            raise SystemExit(
                f"no existe {RUTA_JSON}: lanza primero "
                "'python scripts/make_pqc_plots.py --medir' (dentro del "
                "contenedor, que es donde las cifras son comparables)."
            )
        medidas, tamanos = cargar_json()
        print(f"dibujando con las medidas de {RUTA_JSON}")

    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    figura_1_tiempos(medidas)
    figura_2_tamanos(tamanos)
    figura_3_shor()
    _imprimir_tabla(medidas, tamanos)
    print(f"\nfiguras regeneradas en {DIR_SALIDA}")


if __name__ == "__main__":
    main()
