"""dashboard/qkd_app.py — tareas 1.9 y 2.9 (Carlos). Dashboard Streamlit.

Arranque local:

    streamlit run dashboard/qkd_app.py

Arranque en Docker (la direccion 0.0.0.0 es OBLIGATORIA: con el localhost
por defecto el contenedor escucha solo dentro de si mismo y desde el
navegador del anfitrion no se ve nada aunque el puerto este publicado):

    docker compose up
    # equivale a: streamlit run dashboard/qkd_app.py \
    #   --server.address=0.0.0.0 --server.port=8501

Este fichero NO reimplementa logica de protocolo: consume run_protocol,
run_until_qber y run_bb84 tal y como los exporta el paquete qkd, y las
funciones de `pqc` (shor, kem, hybrid, sig, benchmark) tal y como las exporta
el paquete pqc. Queda UNA sola excepcion documentada, la tabla de sifting, que
reproduce los tres sorteos iniciales de run_bb84 para poder ensenar los fotones
descartados (ver _datos_sifting). La otra excepcion que habia aqui -el
histograma de fases de Shor, que se ejecutaba a mano porque medir_fase_15
devuelve una sola fase por llamada- ya no hace falta: esa logica vive ahora en
`shor.histograma_fases_15`, que es lo que consume _muestrear_fases.

UN SOLO FICHERO, DOS MODULOS (tarea 2.9)
----------------------------------------
El panel del modulo 2 (PQC + Shor) vive aqui dentro, en su propia pestana, y no
en un dashboard/pqc_app.py aparte. La alternativa -pasar a una app multipagina
de Streamlit- obliga a mover ficheros a un directorio pages/ y a cambiar el
comando de arranque, y el criterio de cierre de la Fase 1 dice que el dashboard
arranca con `docker compose up`: no se toca. Con st.tabs los dos modulos
conviven sin que el de QKD cambie de comportamiento.

CUIDADO CON MATHTEXT (aprendido en la Fase 1)
--------------------------------------------
En las figuras de este fichero NO se usa notacion LaTeX de Matplotlib
($\\sigma$ y compania): la cache LRU de mathtext no es thread-safe y revienta
cuando Streamlit renderiza en un hilo de servidor. Se usan caracteres Unicode
(±, σ, μ). En las figuras generadas por script (scripts/make_pqc_plots.py) si
se puede usar mathtext, porque ahi no hay Streamlit.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from cryptography.exceptions import InvalidTag
from matplotlib.ticker import FuncFormatter, PercentFormatter
from pqc.benchmark import (
    RUTA_JSON,
    SUFIJO_CAPA_API,
    cargar_json,
    entorno_del_json,
)
from pqc.hybrid import MECANISMOS_ADMITIDOS, cifrar_mensaje, descifrar_mensaje
from pqc.kem import kem_generar
from pqc.shor import factorizar_15, histograma_fases_15
from pqc.sig import firmar, verificar
from pqc.types import FactorizacionShor, MensajeCifrado, ResultadoFirma
from qkd.bb84 import run_bb84
from qkd.protocol import QBER_THRESHOLD, run_protocol, run_until_qber
from qkd.types import ProtocolResult

# Backend sin pantalla: Streamlit renderiza la figura a PNG en un hilo de
# servidor. No se repite switch_backend cuando Agg ya esta activo: esa llamada
# cierra las figuras globales y podria interferir con otra sesion concurrente.
if str(plt.get_backend()).casefold() != "agg":
    plt.switch_backend("Agg")

# Cuantos fotones ensena la tabla de sifting. Suficiente para que se vea el
# patron (mitad de bases coinciden, errores donde toca) sin hacer scroll
# infinito.
N_FILAS_TABLA = 40

# --- Constantes del modulo 2 (tarea 2.9) -----------------------------------
# Mecanismos que ofrece el desplegable. Nomenclatura NIST obligatoria (FIPS
# 203/204): nunca "Kyber"/"Dilithium". El indice 1 es el nivel NIST 3, el
# recomendado y el que mide el benchmark.
#
# Los del KEM NO se listan aqui: son los mismos que `hybrid.MECANISMOS_ADMITIDOS`
# acepta dentro de un sobre, asi que se importan de alli. Tenerlos escritos dos
# veces permitiria que el desplegable ofreciese un mecanismo que luego el sobre
# rechaza, que es justo el fallo que nadie encuentra hasta la demo.
MECANISMOS_SIG = ("ML-DSA-44", "ML-DSA-65", "ML-DSA-87")
MENSAJE_DEMO = "La criptografía poscuántica protege este mensaje en 2035."
# Shots del histograma de fases de Shor. 2048 dan picos estables y el circuito
# de 12 qubits tarda unas decimas de segundo en el simulador.
SHOTS_FASE = 2048
# Cuantos bytes en hexadecimal se ensenan de cada artefacto binario.
BYTES_PREVIA = 16

# Paleta compartida por los graficos Matplotlib y la interfaz CSS. Los colores
# de exito y error quedan reservados para estados, no para decorar series.
COLOR_TINTA = "#172033"
COLOR_NAVY = "#17324d"
COLOR_TEAL = "#1b7472"
COLOR_MUTED = "#647184"
COLOR_BORDE = "#dbe2e8"
COLOR_EXITO = "#217451"
COLOR_ERROR = "#b34747"

st.set_page_config(
    page_title="QPCS · Criptografía cuántica y poscuántica",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": (
            "QPCS · Quantum & Physics Cryptography Suite. "
            "Simulación educativa de QKD, Shor y criptografía poscuántica."
        )
    },
)


def _cargar_estilos() -> None:
    """Carga la identidad visual sin introducir dependencias web externas."""
    ruta_css = Path(__file__).with_name("styles.css")
    st.markdown(
        f"<style>{ruta_css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True
    )


def _cabecera_seccion(etiqueta: str, titulo: str, descripcion: str) -> None:
    """Cabecera editorial comun a los dos modulos y sus apartados."""
    st.markdown(
        f"""
        <div class="qpcs-section">
            <div class="qpcs-section__eyebrow">{etiqueta}</div>
            <h2>{titulo}</h2>
            <p>{descripcion}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _preparar_ejes(ax: plt.Axes) -> None:
    """Aplica el mismo acabado sobrio y legible a todos los graficos."""
    ax.set_facecolor("#ffffff")
    ax.tick_params(colors=COLOR_MUTED, labelsize=9)
    ax.xaxis.label.set_color(COLOR_TINTA)
    ax.yaxis.label.set_color(COLOR_TINTA)
    ax.grid(color=COLOR_BORDE, alpha=0.8, linewidth=0.65)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_BORDE)
    ax.spines["left"].set_color(COLOR_BORDE)


def _motivo_aborto_legible(motivo: str | None) -> str:
    """Acentua los mensajes del nucleo sin alterar su contrato ni sus tests."""
    if motivo is None:
        return "La ejecución no ha producido una clave final."
    sustituciones = {
        "espia": "espía",
        "reconciliacion": "reconciliación",
        "amplificacion": "amplificación",
    }
    for original, corregido in sustituciones.items():
        motivo = motivo.replace(original, corregido)
    return motivo[0].upper() + motivo[1:]


_cargar_estilos()


# ---------------------------------------------------------------------------
# Simulaciones cacheadas. Streamlit reejecuta el script ENTERO en cada
# interaccion: sin @st.cache_data, mover cualquier slider relanzaria la
# simulacion completa y la interfaz se arrastraria (seccion 5.9 de la guia).
# ---------------------------------------------------------------------------


@st.cache_data
def _simular(
    n: int, p: float, noise: float, sample_fraction: float, seed: int
) -> ProtocolResult:
    """La cadena completa con los parametros de los sliders."""
    return run_protocol(
        n_photons=n,
        eve_rate=p,
        noise=noise,
        sample_fraction=sample_fraction,
        rng=np.random.default_rng(seed),
    )


@st.cache_data
def _barrido_qber(
    n: int, noise: float, sample_fraction: float, seed: int
) -> tuple[list[float], list[float], list[float]]:
    """Barrido de Q(p) para redibujar la figura 1 con los parametros actuales.

    Se cachea aparte de _simular: solo depende de (n, ruido, muestra,
    semilla), asi que mover el slider de Eve NO lo recalcula, solo mueve el
    marcador de la ejecucion actual sobre la curva ya calculada.
    """
    ps = np.linspace(0.0, 1.0, 11)
    qs: list[float] = []
    sigmas: list[float] = []
    for p in ps:
        est = run_until_qber(
            n_photons=n,
            eve_rate=float(p),
            noise=noise,
            sample_fraction=sample_fraction,
            rng=np.random.default_rng(seed),
        )
        qs.append(est.qber)
        sigmas.append(est.sigma)
    return list(ps), qs, sigmas


@st.cache_data
def _datos_sifting(n: int, p: float, noise: float, seed: int) -> pd.DataFrame | None:
    """Los primeros fotones de la MISMA simulacion que muestran las metricas.

    El paquete qkd no expone la vista por foton previa al sifting (bits y
    bases se quedan dentro de run_bb84), asi que aqui se reproducen los tres
    sorteos iniciales de run_bb84 (bits de Alice, bases de Alice, bases de
    Bob: paso 1 de bb84.py) con la misma semilla y en el mismo orden. Como
    run_protocol siembra su rng igual, la tabla ensena literalmente los
    primeros fotones de la ejecucion de las metricas.

    Defensa contra el drift: si algun dia cambia el orden de sorteo interno
    de run_bb84, la comprobacion de consistencia de abajo falla y la funcion
    devuelve None (la tabla se oculta con un aviso en vez de ensenar datos
    inventados).

    Los bits de Bob NO se reproducen: salen del SiftedKeys real. En las
    posiciones descartadas el resultado de Bob se tira sin publicarse (asi
    lo hace el protocolo), y la tabla lo refleja con un "-".
    """
    sifted = run_bb84(
        n_photons=n, rng=np.random.default_rng(seed), eve_rate=p, noise=noise
    )

    rng = np.random.default_rng(seed)
    alice_bits = rng.integers(0, 2, size=n, dtype=np.uint8)
    alice_bases = rng.integers(0, 2, size=n, dtype=np.uint8)
    bob_bases = rng.integers(0, 2, size=n, dtype=np.uint8)

    # Comprobacion de consistencia con la simulacion real.
    if not np.array_equal(alice_bits[sifted.indices], sifted.alice):
        return None

    # rango[pos] = posicion de "pos" dentro de sifted.indices (que esta
    # ordenado por construccion: flatnonzero). Para mapear foton -> bit de
    # Bob cribado.
    n_tabla = min(N_FILAS_TABLA, n)
    kept = np.zeros(n, dtype=bool)
    kept[sifted.indices] = True
    rango = np.searchsorted(sifted.indices, np.arange(n_tabla))

    base_txt = {0: "Z", 1: "X"}
    filas: list[dict[str, str | int]] = []
    for i in range(n_tabla):
        coincide = alice_bases[i] == bob_bases[i]
        if kept[i]:
            bob_bit = int(sifted.bob[rango[i]])
            error = bob_bit != int(alice_bits[i])
            resultado = "ERROR" if error else "ok"
            bob_txt = str(bob_bit)
        else:
            # Bases distintas: el resultado de Bob se descarta sin
            # publicarse, no hay nada que ensenar.
            resultado = "descartado"
            bob_txt = "-"
        filas.append(
            {
                "Fotón": i,
                "Bit de Alice": int(alice_bits[i]),
                "Base de Alice": base_txt[int(alice_bases[i])],
                "Base de Bob": base_txt[int(bob_bases[i])],
                "Bases iguales": "Sí" if coincide else "No",
                "Bit de Bob": bob_txt,
                "Resultado": {
                    "ERROR": "Error",
                    "descartado": "Descartado",
                    "ok": "Correcto",
                }[resultado],
            }
        )
    return pd.DataFrame(filas)


def _colorea_fila(fila: pd.Series) -> list[str]:
    """Errores en rojo, descartados atenuados. La columna 'resultado' repite
    la informacion en texto: el color nunca es el unico canal."""
    if fila["Resultado"] == "Error":
        return ["background-color: #fbeaea; color: #852f2f"] * len(fila)
    if fila["Resultado"] == "Descartado":
        return ["color: #7b8796; background-color: #f6f8f9"] * len(fila)
    return [""] * len(fila)


# ---------------------------------------------------------------------------
# Modulo 2: Shor y PQC, tambien cacheados. Aqui el motivo es distinto y hay
# dos:
#   - Shor cuesta unas decimas de segundo por ejecucion (transpilar y simular
#     12 qubits): sin cache se relanzaria al tocar cualquier control de la otra
#     pestana, porque Streamlit reejecuta el script entero.
#   - El cifrado y la firma son rapidisimos, pero NO son deterministas (nonce
#     fresco y par de claves nuevo en cada llamada). Sin cache, el hexadecimal
#     que se ensena cambiaria en cada interaccion y la demo seria imposible de
#     seguir. Cachear por (mensaje, mecanismos) la congela hasta que el usuario
#     cambia algo de verdad.
# ---------------------------------------------------------------------------


@st.cache_data
def _factorizar(semilla: int) -> FactorizacionShor:
    """Shor sobre N=15 con semilla explicita (reproducible, ver src/pqc/shor.py)."""
    return factorizar_15(np.random.default_rng(semilla))


@st.cache_data
def _muestrear_fases(a: int, semilla: int) -> tuple[list[float], list[int]]:
    """Histograma de la fase medida, en las dos listas que quiere ax.bar().

    La simulacion entera la hace `shor.histograma_fases_15`; aqui solo se
    parte el diccionario {fase: veces} en dos listas paralelas y se cachea.
    Antes esto reimplementaba el transpile + run + conversion de bitstring a
    fase, siete lineas duplicadas tambien en scripts/make_pqc_plots.py.

    La semilla se pasa envuelta en un np.random.Generator y no directamente
    como seed_simulator: es la convencion del modulo (todo lo estocastico
    recibe un Generator explicito y deriva de el la semilla del backend), y
    antes este fichero se la saltaba.
    """
    histograma = histograma_fases_15(a, np.random.default_rng(semilla), 8, SHOTS_FASE)
    return list(histograma.keys()), list(histograma.values())


@st.cache_data
def _cifrar_y_firmar(
    mensaje: str, mecanismo_kem: str, mecanismo_sig: str
) -> tuple[bytes, MensajeCifrado, ResultadoFirma]:
    """Cifra con ML-KEM y firma con ML-DSA el mismo mensaje.

    Devuelve tambien la clave privada del KEM porque el receptor de la demo la
    necesita para descifrar. Las claves viven en memoria durante la ejecucion y
    nada mas: la gestion de claves persistente esta explicitamente fuera de la
    Fase 2.
    """
    clave_publica, clave_privada = kem_generar(mecanismo_kem)
    sobre = cifrar_mensaje(clave_publica, mensaje.encode(), mecanismo_kem)
    firma = firmar(mensaje.encode(), mecanismo_sig)
    return clave_privada, sobre, firma


def _hex_previa(datos: bytes) -> str:
    """Los primeros bytes en hexadecimal, para ensenar un artefacto binario."""
    return datos[:BYTES_PREVIA].hex() + (" ..." if len(datos) > BYTES_PREVIA else "")


def _entero_es(valor: int) -> str:
    """Agrupa millares con punto para los contadores visibles en espanol."""
    return f"{valor:,}".replace(",", ".")


def _mostrar_flujo_qkd(resultado: ProtocolResult) -> None:
    """Resume la perdida de bits a lo largo de la cadena BB84."""
    tras_muestra = int(resultado.qber.remaining.alice.size)
    final = 0 if resultado.final_key is None else int(resultado.final_key.size)
    estado_final = "Protocolo abortado" if resultado.aborted else "Clave destilada"
    st.markdown(
        f"""
        <div class="qpcs-flow">
            <div class="qpcs-flow__step">
                <span class="qpcs-flow__label">Preparación</span>
                <span class="qpcs-flow__value">{_entero_es(resultado.n_photons)}</span>
                <span class="qpcs-flow__detail">fotones enviados</span>
            </div>
            <div class="qpcs-flow__step">
                <span class="qpcs-flow__label">Cribado</span>
                <span class="qpcs-flow__value">{_entero_es(resultado.sifted_len)}</span>
                <span class="qpcs-flow__detail">bases coincidentes</span>
            </div>
            <div class="qpcs-flow__step">
                <span class="qpcs-flow__label">Estimación</span>
                <span class="qpcs-flow__value">{_entero_es(tras_muestra)}</span>
                <span class="qpcs-flow__detail">bits tras medir el QBER</span>
            </div>
            <div class="qpcs-flow__step">
                <span class="qpcs-flow__label">Privacidad</span>
                <span class="qpcs-flow__value">{_entero_es(final)}</span>
                <span class="qpcs-flow__detail">{estado_final}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _grafico_benchmark(df: pd.DataFrame) -> plt.Figure:
    """Convierte la tabla de latencias en una comparacion visual logaritmica."""
    operaciones = {
        "keygen": "Generar clave",
        "encaps": "Encapsular",
        "decaps": "Desencapsular",
        "sign": "Firmar",
        "verify": "Verificar",
        "encrypt": "Cifrar",
        "decrypt": "Descifrar",
    }
    datos = df.sort_values("media_ms", ascending=True).reset_index(drop=True)
    etiquetas = [
        f"{mecanismo} · {operaciones.get(operacion, operacion)}"
        for mecanismo, operacion in zip(
            datos["mecanismo"], datos["operacion"], strict=True
        )
    ]
    posiciones = np.arange(len(datos))
    es_clasica = datos["familia"].isin(["RSA", "ECC"]).to_numpy()
    media = datos["media_ms"].to_numpy(dtype=float)
    sigma = datos["sigma_ms"].to_numpy(dtype=float)
    error_inferior = np.minimum(sigma, media * 0.92)
    error = np.vstack([error_inferior, sigma])

    altura = max(4.8, min(8.0, 0.42 * len(datos) + 1.8))
    fig, ax = plt.subplots(figsize=(9, altura))
    for mascara, color, marcador, etiqueta in (
        (es_clasica, COLOR_NAVY, "o", "Criptografía clásica"),
        (~es_clasica, COLOR_TEAL, "D", "Criptografía poscuántica"),
    ):
        ax.errorbar(
            media[mascara],
            posiciones[mascara],
            xerr=error[:, mascara],
            fmt=marcador,
            markersize=6,
            color=color,
            ecolor=color,
            elinewidth=1.4,
            capsize=3,
            alpha=0.92,
            label=etiqueta,
        )
    ax.set_yticks(posiciones, etiquetas)
    ax.set_xscale("log")
    # El formateador logaritmico por defecto de Matplotlib produce etiquetas
    # MathText ($\mathdefault{...}$). La cache global de ese parser no es
    # thread-safe y puede romperse cuando dos sesiones de Streamlit renderizan
    # a la vez (IndexError: pop from empty list). Texto plano conserva la escala
    # y evita por completo el parser de MathText, igual que los otros graficos.
    ax.xaxis.set_major_formatter(FuncFormatter(lambda valor, _: f"{valor:g}"))
    ax.set_xlabel("Tiempo medio (ms, escala logarítmica)")
    ax.set_ylabel("")
    ax.grid(axis="x", which="both", color=COLOR_BORDE, alpha=0.8, linewidth=0.65)
    _preparar_ejes(ax)
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    fig.patch.set_facecolor("#ffffff")
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Controles del modulo 1 (barra lateral)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        """
        <div class="qpcs-sidebar-brand">
            <div class="qpcs-sidebar-brand__mark">Q</div>
            <div class="qpcs-sidebar-brand__text">
                <strong>QPCS</strong>
                <span>CRYPTOGRAPHY SUITE</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.header("Configuración de BB84")
    st.markdown(
        '<div class="qpcs-note">Estos parámetros afectan únicamente al '
        "experimento del Módulo 1.</div>",
        unsafe_allow_html=True,
    )
    n = st.select_slider(
        "Fotones enviados",
        options=[1_000, 5_000, 10_000, 50_000],
        value=10_000,
        format_func=_entero_es,
        help="Número de fotones preparados por Alice para esta ejecución.",
    )
    p_porcentaje = st.slider(
        "Intercepción de Eve",
        0,
        100,
        0,
        5,
        format="%d %%",
        help="Porcentaje de fotones que Eve intercepta y reenvía.",
    )
    ruido_porcentaje = st.slider(
        "Ruido del canal",
        0,
        10,
        1,
        1,
        format="%d %%",
        help="Probabilidad de error físico independiente del espionaje.",
    )
    muestra_porcentaje = st.slider(
        "Muestra pública para el QBER",
        5,
        50,
        20,
        5,
        format="%d %%",
        help=(
            "Una muestra mayor reduce la incertidumbre, pero sacrifica más bits "
            "de la clave."
        ),
    )
    seed = int(
        st.number_input(
            "Semilla de la simulación",
            value=42,
            step=1,
            help="La misma semilla y los mismos parámetros reproducen el resultado.",
        )
    )
    p = p_porcentaje / 100
    noise = ruido_porcentaje / 100
    sample_fraction = muestra_porcentaje / 100
    st.markdown(
        """
        <div class="qpcs-note">
            Motor NumPy exacto y vectorizado. Es el único backend interactivo
            que modela a Eve y admite hasta 50.000 fotones con fluidez.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("QPCS · Módulos 1 y 2 · Entorno educativo y reproducible")

r = _simular(int(n), float(p), float(noise), float(sample_fraction), seed)

st.markdown(
    """
    <div class="qpcs-hero">
        <div class="qpcs-hero__eyebrow">Quantum &amp; Physics Cryptography Suite</div>
        <h1>Criptografía frente al horizonte cuántico</h1>
        <p>
            Un laboratorio interactivo para comprender cómo se distribuyen claves
            con BB84, por qué Shor amenaza la criptografía clásica y cómo responden
            los estándares poscuánticos actuales.
        </p>
        <div class="qpcs-hero__tags">
            <span class="qpcs-tag">QKD · BB84</span>
            <span class="qpcs-tag">Algoritmo de Shor</span>
            <span class="qpcs-tag">ML-KEM · ML-DSA</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_qkd, tab_pqc = st.tabs(
    ["Módulo 1 · Distribución de claves", "Módulo 2 · Amenaza y defensa"]
)

# ===========================================================================
# PESTANA 1 - Modulo QKD (Fase 1, tarea 1.9). Contenido intacto: lo unico que
# cambia respecto a la Fase 1 es que ahora vive dentro de su pestana.
# ===========================================================================

with tab_qkd:
    _cabecera_seccion(
        "Módulo 01 · QKD / BB84",
        "Distribución cuántica de claves",
        "Observa cómo el ruido y la interceptación dejan una huella medible en el "
        "canal, y cómo BB84 decide si todavía es posible destilar una clave segura.",
    )

    # -----------------------------------------------------------------------
    # Metricas grandes
    # -----------------------------------------------------------------------

    # MEJORA D1: f_EC sale ya de la property del contrato
    # (ReconciliationResult.efficiency), no de una copia local de la formula.
    # La property devuelve NaN cuando no esta definida (h(Q) = 0 o n = 0) y
    # aqui eso se ensena como "—", igual que antes.
    f_ec: float | None = None
    if r.reconciliation is not None:
        eficiencia = r.reconciliation.efficiency
        if math.isfinite(eficiencia):
            f_ec = eficiencia

    st.markdown(
        '<div class="qpcs-kicker">Resultado de la ejecución</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4, gap="medium")
    c1.metric(
        "QBER observado",
        f"{r.qber.qber:.2%}",
        f"Incertidumbre ± {r.qber.sigma:.2%} (1 σ)",
        delta_color="off",
        help="Proporción de errores observados en la muestra pública.",
    )
    c2.metric(
        "Clave final segura",
        "0 bits" if r.final_key is None else f"{_entero_es(r.final_key.size)} bits",
        help="Longitud después de reconciliar errores y amplificar la privacidad.",
    )
    c3.metric(
        "Rendimiento",
        f"{r.secret_fraction:.1%}",
        help="Bits de clave final por cada fotón enviado.",
    )
    c4.metric(
        "Eficiencia de Cascade",
        "—" if f_ec is None else f"{f_ec:.2f}",
        help="f_EC = 1 sería el límite ideal de Shannon; Cascade suele quedar cerca.",
    )

    # --- El semaforo -------------------------------------------------------

    if r.aborted:
        st.error(f"**Protocolo abortado.** {_motivo_aborto_legible(r.abort_reason)}")
    else:
        assert r.final_key is not None
        st.success(
            f"**Canal aceptado.** Se ha destilado una clave segura de "
            f"{_entero_es(r.final_key.size)} bits."
        )

    st.markdown(
        '<div class="qpcs-kicker">Recorrido de los bits</div>', unsafe_allow_html=True
    )
    _mostrar_flujo_qkd(r)

    # -----------------------------------------------------------------------
    # Figura Q(p) recalculada + tabla del sifting
    # -----------------------------------------------------------------------

    col_fig, col_tabla = st.columns([3, 2], gap="large")

    with col_fig:
        with st.container(border=True):
            st.subheader("QBER frente a la interceptación de Eve")
            st.caption(
                "El rombo señala esta ejecución; las barras muestran tres "
                "desviaciones típicas."
            )
            ps, qs, sigmas = _barrido_qber(
                int(n), float(noise), float(sample_fraction), seed
            )
            fig, ax = plt.subplots(figsize=(7.2, 4.4))
            fig.patch.set_facecolor("#ffffff")
            ax.errorbar(
                ps,
                qs,
                yerr=3 * np.asarray(sigmas),
                fmt="o",
                color=COLOR_TEAL,
                ecolor="#74a9a7",
                ms=5,
                capsize=3,
                label="Simulación (±3 σ)",
                zorder=3,
            )
            ps_arr = np.asarray(ps)
            ax.plot(
                ps_arr,
                ps_arr / 4,
                "-",
                color=COLOR_NAVY,
                lw=1.8,
                label="Predicción teórica: Q = p/4",
                zorder=2,
            )
            ax.axhline(
                QBER_THRESHOLD,
                ls="--",
                color=COLOR_ERROR,
                lw=1.2,
                label="Umbral de seguridad (11 %)",
            )
            ax.axhspan(
                QBER_THRESHOLD,
                0.30,
                color=COLOR_ERROR,
                alpha=0.075,
                zorder=1,
            )
            # Marcador de la ejecucion actual: rojo si aborto, verde si hay clave
            # (colores de estado, reservados para eso).
            ax.plot(
                [p],
                [r.qber.qber],
                "D",
                ms=8,
                color=COLOR_ERROR if r.aborted else COLOR_EXITO,
                markeredgecolor="white",
                markeredgewidth=1.2,
                label=f"Ejecución actual ({p:.0%} interceptado)",
                zorder=4,
            )
            ax.set_xlabel("Fotones interceptados por Eve")
            ax.set_ylabel("QBER")
            ax.set_xlim(-0.02, 1.02)
            ax.set_ylim(0, 0.30)
            ax.xaxis.set_major_formatter(PercentFormatter(1.0))
            ax.yaxis.set_major_formatter(PercentFormatter(1.0))
            _preparar_ejes(ax)
            ax.legend(frameon=False, fontsize=8, loc="upper left")
            fig.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)
            st.caption(
                "La recta no es un ajuste: representa la predicción Q = p/4. "
                "La franja roja comienza en el límite de seguridad del 11 % "
                "de Shor–Preskill."
            )

    with col_tabla:
        with st.container(border=True):
            st.subheader(f"Cribado de los primeros {N_FILAS_TABLA} fotones")
            st.caption("Una vista posición a posición del intercambio cuántico.")
            df = _datos_sifting(int(n), float(p), float(noise), seed)
            if df is None:
                st.warning(
                    "La tabla se ha desactivado porque la reconstrucción ya no "
                    "coincide con la simulación real. Revisa `_datos_sifting` en "
                    "`dashboard/qkd_app.py`."
                )
            else:
                st.dataframe(
                    df.style.apply(_colorea_fila, axis=1),
                    hide_index=True,
                    height=500,
                    use_container_width=True,
                    column_config={
                        "Fotón": st.column_config.NumberColumn(format="%d"),
                        "Bit de Alice": st.column_config.NumberColumn(format="%d"),
                    },
                )
                st.caption(
                    "Solo sobreviven las bases coincidentes. Los errores se "
                    "resaltan en rojo y los fotones descartados aparecen atenuados; "
                    "el significado nunca depende únicamente del color."
                )

# ===========================================================================
# PESTANA 2 - Modulo PQC + Shor (Fase 2, tarea 2.9). Tres sub-pestanas: la
# amenaza (Shor), la defensa (cripto real) y su coste medido (benchmark), que
# es el arco entero del modulo 2.
# ===========================================================================

with tab_pqc:
    _cabecera_seccion(
        "Módulo 02 · Criptografía poscuántica",
        "De la amenaza de Shor a la defensa poscuántica",
        "Recorre el problema completo: un algoritmo cuántico que debilita la "
        "criptografía clásica, estándares resistentes que ya funcionan y el coste "
        "real de adoptarlos.",
    )
    st.markdown(
        """
        <div class="qpcs-process">
            <div class="qpcs-process__item">
                <strong>Shor</strong><span>Expone la amenaza</span>
            </div>
            <div class="qpcs-process__arrow">→</div>
            <div class="qpcs-process__item">
                <strong>ML-KEM + ML-DSA</strong><span>Protegen y autentican</span>
            </div>
            <div class="qpcs-process__arrow">→</div>
            <div class="qpcs-process__item">
                <strong>Benchmark</strong><span>Mide el coste de migrar</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    sub_shor, sub_real, sub_bench = st.tabs(
        ["01 · Amenaza: Shor", "02 · Defensa: PQC real", "03 · Coste: benchmark"]
    )

    # -----------------------------------------------------------------------
    # Shor: factorizacion por busqueda de orden
    # -----------------------------------------------------------------------

    with sub_shor:
        _cabecera_seccion(
            "Experimento 01",
            "Factorización mediante búsqueda de orden",
            "Ejecuta una demostración reproducible del algoritmo de Shor sobre "
            "N = 15 y relaciona la fase medida con los factores obtenidos.",
        )
        col_ctrl, col_res = st.columns([1, 3], gap="large")

        with col_ctrl:
            with st.container(border=True):
                st.subheader("Parámetros")
                n_shor = st.selectbox(
                    "Número a factorizar (N)",
                    options=[15, 21],
                    help="El circuito compilado está implementado para N = 15.",
                )
                semilla_shor = int(
                    st.number_input(
                        "Semilla de Shor",
                        value=42,
                        step=1,
                        key="semilla_shor",
                        help="Permite repetir exactamente la misma simulación.",
                    )
                )
                st.markdown(
                    """
                    <div class="qpcs-note">
                        Esta simulación sí se siembra: la misma semilla produce
                        la misma base y la misma factorización.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if n_shor == 21:
            # Limitacion conocida, y se dice en la interfaz en vez de esconder
            # la opcion: factorizar 21 necesita su propio oraculo compilado
            # (c_amod21, 5 qubits de trabajo). Queda documentado como trabajo
            # pendiente en el README, igual que la guia decidio en la tarea 2.3.
            with col_res, st.container(border=True):
                st.subheader("Resultado")
                st.info(
                    "**N = 21 todavía no está implementado.** El oráculo de "
                    "exponenciación modular se compila específicamente para cada "
                    "par (a, N). El circuito de N = 15 usa cuatro qubits de trabajo; "
                    "N = 21 necesita cinco y su propio `c_amod21`. Es una limitación "
                    "conocida y documentada, no un error de la aplicación."
                )
        else:
            res = _factorizar(semilla_shor)

            with col_res, st.container(border=True):
                st.subheader("Resultado de la factorización")
                m1, m2, m3, m4 = st.columns(4, gap="medium")
                # Con ok=False los campos son CENTINELAS, no medidas (a=0,
                # orden=0: ver el docstring de FactorizacionShor). Se ensena
                # "—" en vez del cero, que aqui se leeria como "el orden es
                # cero". `intentos` si significa lo mismo en los dos casos.
                m1.metric(
                    "Factores de 15",
                    f"{res.factores[0]} × {res.factores[1]}" if res.ok else "—",
                )
                m2.metric("Orden r", str(res.orden) if res.ok else "—")
                m3.metric("Base a", str(res.a) if res.ok else "—")
                m4.metric("Intentos", res.intentos)
                if res.ok:
                    st.success(
                        f"15 = {res.factores[0]} × {res.factores[1]} por "
                        f"búsqueda cuántica de orden. La fase medida es "
                        f"{res.fase_medida:.3f} ≈ s/r, con r = {res.orden}."
                    )
                else:
                    st.error(
                        "Shor no encontró factores en el número máximo de "
                        "intentos (orden impar o a^(r/2) ≡ -1 en todos)."
                    )

            # El histograma y su explicacion solo tienen sentido si la ejecucion
            # encontro algo: con ok=False, `a` y `orden` son centinelas a 0, y a=0
            # ni siquiera es una base valida -pasarselo a circuito_orden_15 levanta
            # ValueError y tumba la pagina con un traceback-. Antes el muestreo se
            # lanzaba ANTES de mirar `ok`, asi que el st.error de arriba, que es la
            # forma correcta de contar el fracaso, era inalcanzable.
            if res.ok:
                fases, veces = _muestrear_fases(int(res.a), semilla_shor)
                col_hist, col_texto = st.columns([3, 2], gap="large")

                with col_hist:
                    with st.container(border=True):
                        st.subheader(f"Distribución de fase con a = {res.a}")
                        st.caption(f"Resultado de {_entero_es(SHOTS_FASE)} disparos.")
                        fig_shor, ax_shor = plt.subplots(figsize=(7.2, 4.4))
                        fig_shor.patch.set_facecolor("#ffffff")
                        # Las lineas de referencia van en los multiplos de 1/r con el r
                        # que hallo la ejecucion: no son un ajuste, son la prediccion.
                        for k in range(res.orden):
                            ax_shor.axvline(
                                k / res.orden,
                                ls="--",
                                color=COLOR_NAVY,
                                alpha=0.55,
                                lw=1,
                                zorder=1,
                            )
                            ax_shor.text(
                                k / res.orden,
                                SHOTS_FASE * 0.34,
                                f"s/r = {k}/{res.orden}",
                                rotation=90,
                                fontsize=8,
                                color=COLOR_MUTED,
                                ha="right",
                                va="bottom",
                            )
                        # Sin mathtext: en Streamlit la cache de mathtext de Matplotlib
                        # no es thread-safe (ver el docstring del modulo).
                        ax_shor.bar(
                            fases,
                            veces,
                            width=0.012,
                            color=COLOR_TEAL,
                            zorder=3,
                        )
                        ax_shor.set_xlabel("Fase medida y/2⁸ (adimensional)")
                        ax_shor.set_ylabel(
                            f"Frecuencia (de {_entero_es(SHOTS_FASE)} disparos)"
                        )
                        ax_shor.set_xlim(-0.05, 1.0)
                        ax_shor.set_ylim(0, SHOTS_FASE * 0.5)
                        _preparar_ejes(ax_shor)
                        fig_shor.tight_layout()
                        st.pyplot(fig_shor, use_container_width=True)
                        plt.close(fig_shor)
                        st.caption(
                            f"Los picos aparecen en múltiplos de 1/r, con r = "
                            f"{res.orden}. Las fracciones continuas convierten "
                            "esas posiciones en el orden del que salen los factores."
                        )

                with col_texto:
                    with st.container(border=True):
                        st.subheader("Cómo leer el resultado")
                        st.markdown(
                            f"""
1. **Estimación de fase.** El circuito (8 qubits de conteo y 4 de trabajo)
   mide una fase y/2⁸ ≈ s/r del operador |y⟩ → |{res.a}·y mod 15⟩.
2. **Fracciones continuas.** El denominador del mejor convergente proporciona
   el orden **r = {res.orden}** mediante un cálculo clásico inmediato.
3. **Reducción clásica.** gcd({res.a}^(r/2) ± 1, 15) produce
   **{res.factores[0]} y {res.factores[1]}**.
"""
                        )
                        st.warning(
                            "**Modelo de amenaza, no herramienta de ataque.** "
                            "El oráculo está compilado para números de juguete. "
                            "Factorizar RSA-2048 requeriría miles de qubits lógicos "
                            "con corrección de errores, una capacidad que todavía no "
                            "existe."
                        )

    # -----------------------------------------------------------------------
    # PQC real: cifrar y firmar un mensaje de verdad
    # -----------------------------------------------------------------------

    with sub_real:
        _cabecera_seccion(
            "Experimento 02",
            "Cifrado y firma poscuánticos reales",
            "Protege un mensaje con ML-KEM y AES-256-GCM, fírmalo con ML-DSA "
            "y comprueba en directo qué ocurre si alguien altera el contenido.",
        )
        st.markdown(
            """
            <div class="qpcs-process">
                <div class="qpcs-process__item">
                    <strong>ML-KEM</strong><span>Acuerda un secreto</span>
                </div>
                <div class="qpcs-process__arrow">→</div>
                <div class="qpcs-process__item">
                    <strong>HKDF-SHA256</strong><span>Deriva la clave</span>
                </div>
                <div class="qpcs-process__arrow">→</div>
                <div class="qpcs-process__item">
                    <strong>AES-256-GCM</strong><span>Cifra y autentica</span>
                </div>
                <div class="qpcs-process__arrow">+</div>
                <div class="qpcs-process__item">
                    <strong>ML-DSA</strong><span>Firma el mensaje</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_ctrl, col_estado = st.columns([2, 3], gap="large")

        with col_ctrl:
            with st.container(border=True):
                st.subheader("Preparar el envío")
                mensaje = st.text_input(
                    "Mensaje a cifrar y firmar",
                    MENSAJE_DEMO,
                    help="El contenido se cifra y se firma de forma independiente.",
                )
                mecanismo_kem = st.selectbox(
                    "Mecanismo KEM · FIPS 203",
                    MECANISMOS_ADMITIDOS,
                    1,
                    help="ML-KEM establece el secreto usado por el cifrado simétrico.",
                )
                mecanismo_sig = st.selectbox(
                    "Mecanismo de firma · FIPS 204",
                    MECANISMOS_SIG,
                    1,
                    help="ML-DSA demuestra la autoría y la integridad del mensaje.",
                )
                # Un toggle y no un boton: el boton no sobrevive al rerun de
                # Streamlit sin session_state, y aqui interesa poder comparar el
                # antes y el despues sin que la demo se reinicie.
                manipular = st.toggle(
                    "Alterar un byte durante el tránsito",
                    value=False,
                    help="Simula una modificación maliciosa antes de la recepción.",
                )
                st.markdown(
                    """
                    <div class="qpcs-note">
                        Las claves reales no se siembran. liboqs usa su propio
                        generador criptográfico para que sean impredecibles.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        clave_privada, sobre, firma = _cifrar_y_firmar(
            mensaje, mecanismo_kem, mecanismo_sig
        )

        # El "byte en transito" se altera sobre una COPIA reconstruida: los
        # dataclasses del contrato son frozen=True y no se mutan.
        if manipular:
            sobre_recibido = MensajeCifrado(
                sobre.kem_ciphertext,
                sobre.nonce,
                bytes([sobre.aead_ciphertext[0] ^ 0x01]) + sobre.aead_ciphertext[1:],
                sobre.mecanismo,
            )
            firma_recibida = ResultadoFirma(
                firma.mensaje,
                bytes([firma.firma[0] ^ 0x01]) + firma.firma[1:],
                firma.clave_publica,
                firma.mecanismo,
            )
        else:
            sobre_recibido, firma_recibida = sobre, firma

        with col_estado, st.container(border=True):
            st.subheader("Resultado en el destinatario")
            if manipular:
                st.warning(
                    "Se ha alterado el sobre después del envío. Las dos "
                    "comprobaciones deben rechazarlo."
                )
            try:
                descifrado = descifrar_mensaje(clave_privada, sobre_recibido).decode()
                st.success(
                    f"**Confidencialidad verificada.** Descifrado con "
                    f"{sobre.mecanismo}: «{descifrado}»"
                )
            except InvalidTag:
                # No es un fallo del programa: es exactamente lo que tiene que
                # pasar. AES-GCM no devuelve texto en claro si el tag no cuadra.
                st.error(
                    "**Integridad comprometida.** AES-GCM ha detectado la "
                    "alteración (`InvalidTag`) y no devuelve ningún texto en claro."
                )
            if verificar(firma_recibida):
                st.success(
                    f"**Autenticidad verificada.** La firma {firma.mecanismo} "
                    "es válida."
                )
            else:
                st.error(
                    f"**Firma rechazada.** La verificación con {firma.mecanismo} "
                    "confirma que el artefacto recibido ha sido alterado."
                )

        st.markdown(
            '<div class="qpcs-kicker">Tamaño de los artefactos</div>',
            unsafe_allow_html=True,
        )
        t1, t2, t3, t4 = st.columns(4, gap="medium")
        t1.metric(
            "Encapsulado ML-KEM",
            f"{_entero_es(len(sobre.kem_ciphertext))} B",
            help="Artefacto de encapsulación generado por ML-KEM.",
        )
        t2.metric(
            "Nonce de AES-GCM",
            f"{_entero_es(len(sobre.nonce))} B",
            help="Valor único y fresco usado por el cifrado autenticado.",
        )
        t3.metric(
            "Clave pública de firma",
            f"{_entero_es(len(firma.clave_publica))} B",
            help="Clave pública necesaria para verificar ML-DSA.",
        )
        t4.metric(
            "Firma ML-DSA",
            f"{_entero_es(len(firma.firma))} B",
            help="Firma poscuántica asociada al mensaje.",
        )

        with st.expander("Inspeccionar los artefactos binarios"):
            st.code(
                f"mecanismo       : {sobre.mecanismo}  "
                "(KEM → HKDF-SHA256 → AES-256-GCM)\n"
                f"mensaje         : {mensaje}\n"
                f"kem_ciphertext  : {len(sobre.kem_ciphertext):>5} B -> "
                f"{_hex_previa(sobre.kem_ciphertext)}\n"
                f"nonce           : {len(sobre.nonce):>5} B -> "
                f"{_hex_previa(sobre.nonce)}   (fresco en cada cifrado)\n"
                f"aead_ciphertext : {len(sobre_recibido.aead_ciphertext):>5} B -> "
                f"{_hex_previa(sobre_recibido.aead_ciphertext)}"
                f"{'   <- BYTE ALTERADO' if manipular else ''}\n"
                f"firma           : {len(firma_recibida.firma):>5} B -> "
                f"{_hex_previa(firma_recibida.firma)}"
                f"{'   <- BYTE ALTERADO' if manipular else ''}",
                language="text",
            )
            st.caption(
                "Un KEM no cifra por sí solo: transporta un secreto del que "
                "HKDF-SHA256 deriva la clave de AES-256-GCM. La firma no oculta "
                "el mensaje; demuestra su autoría y que no ha cambiado."
            )

    # -----------------------------------------------------------------------
    # Benchmark: la tabla medida (no se mide aqui, se lee del JSON)
    # -----------------------------------------------------------------------

    with sub_bench:
        _cabecera_seccion(
            "Experimento 03",
            "El coste medido de la transición",
            "Compara latencias y tamaños de artefactos clásicos y poscuánticos "
            "a partir del benchmark reproducible guardado con el proyecto.",
        )
        if not RUTA_JSON.exists():
            st.info(
                f"Todavía no hay medidas (`{RUTA_JSON.name}` no existe). "
                "Genéralas con `python scripts/make_pqc_plots.py --medir` "
                "dentro del contenedor, donde el entorno es comparable."
            )
        else:
            # El dashboard NO mide: medir el benchmark cuesta ~1 min de CPU y
            # Streamlit reejecuta el script en cada interaccion. Se lee el JSON
            # versionado que produjo scripts/make_pqc_plots.py --medir.
            medidas, tamanos = cargar_json()
            con_carga = st.toggle(
                "Incluir el coste de cargar y serializar las claves "
                f"(«{SUFIJO_CAPA_API.strip()}»)",
                value=False,
                help=(
                    "Añade la capa de la API pública, además de la operación "
                    "criptográfica pura."
                ),
            )
            filas = [
                asdict(m)
                for m in medidas
                if con_carga or not m.mecanismo.endswith(SUFIJO_CAPA_API)
            ]
            df_medidas = pd.DataFrame(filas)[
                [
                    "operacion",
                    "familia",
                    "mecanismo",
                    "media_ms",
                    "sigma_ms",
                    "p50_ms",
                    "repeticiones",
                ]
            ]
            with st.container(border=True):
                st.subheader("Latencia por operación")
                st.caption(
                    "El eje logarítmico permite comparar operaciones separadas "
                    "por varios órdenes de magnitud; las barras representan ±1 σ."
                )
                fig_benchmark = _grafico_benchmark(df_medidas)
                st.pyplot(fig_benchmark, use_container_width=True)
                plt.close(fig_benchmark)

            operaciones_es = {
                "keygen": "Generar clave",
                "encaps": "Encapsular",
                "decaps": "Desencapsular",
                "sign": "Firmar",
                "verify": "Verificar",
                "encrypt": "Cifrar",
                "decrypt": "Descifrar",
            }
            df_tabla = df_medidas.copy()
            df_tabla["operacion"] = df_tabla["operacion"].map(operaciones_es)
            df_tabla = df_tabla.rename(
                columns={
                    "operacion": "Operación",
                    "familia": "Familia",
                    "mecanismo": "Mecanismo",
                    "media_ms": "Media (ms)",
                    "sigma_ms": "σ (ms)",
                    "p50_ms": "Mediana (ms)",
                    "repeticiones": "Repeticiones",
                }
            )
            df_tamanos = pd.DataFrame([asdict(t) for t in tamanos]).rename(
                columns={
                    "mecanismo": "Mecanismo",
                    "clave_publica": "Clave pública (B)",
                    "clave_privada": "Clave privada (B)",
                    "texto_cifrado": "Texto cifrado (B)",
                    "firma": "Firma (B)",
                }
            )

            col_t, col_s = st.columns([3, 2], gap="large")
            with col_t:
                with st.container(border=True):
                    st.subheader("Medidas de tiempo")
                    st.dataframe(
                        df_tabla.style.format(
                            {
                                "Media (ms)": "{:.3f}",
                                "σ (ms)": "{:.3f}",
                                "Mediana (ms)": "{:.3f}",
                            }
                        ),
                        hide_index=True,
                        height=430,
                        use_container_width=True,
                    )
                    st.caption(
                        "La desviación típica se deriva de todas las repeticiones; "
                        "la mediana ayuda a detectar ruido del planificador."
                    )
            with col_s:
                with st.container(border=True):
                    st.subheader("Tamaño de los artefactos")
                    st.dataframe(
                        df_tamanos,
                        hide_index=True,
                        height=430,
                        use_container_width=True,
                    )
                    st.caption(
                        "Los tamaños son deterministas y no necesitan barras de "
                        "error. Un cero indica que el artefacto no aplica."
                    )

            datos_entorno = entorno_del_json()
            with st.expander("Consultar el entorno de medición"):
                st.markdown(
                    f"""
- **Plataforma:** {datos_entorno['plataforma']}
- **Procesador:** {datos_entorno['procesador']}
- **Python:** {datos_entorno['python']}
- **liboqs:** {datos_entorno['liboqs']}
- **Fecha UTC:** {datos_entorno['medido_utc']}
"""
                )
                st.caption(
                    "Otra máquina puede producir cifras distintas; por eso el "
                    "entorno forma parte inseparable de las medidas."
                )
