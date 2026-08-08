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

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from cryptography.exceptions import InvalidTag
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

# Backend sin pantalla: streamlit renderiza la figura a PNG en un hilo de
# servidor; un backend interactivo ahi revienta. switch_backend (y no
# matplotlib.use antes del import) para no romper el orden de imports que
# exige ruff (E402).
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
MENSAJE_DEMO = "La criptografia post-cuantica protege esto en 2035."
# Shots del histograma de fases de Shor. 2048 dan picos estables y el circuito
# de 12 qubits tarda unas decimas de segundo en el simulador.
SHOTS_FASE = 2048
# Cuantos bytes en hexadecimal se ensenan de cada artefacto binario.
BYTES_PREVIA = 16

st.set_page_config(page_title="QPCS - QKD + PQC", layout="wide")


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
                "foton": i,
                "bit Alice": int(alice_bits[i]),
                "base Alice": base_txt[int(alice_bases[i])],
                "base Bob": base_txt[int(bob_bases[i])],
                "bases iguales": "si" if coincide else "no",
                "bit Bob": bob_txt,
                "resultado": resultado,
            }
        )
    return pd.DataFrame(filas)


def _colorea_fila(fila: pd.Series) -> list[str]:
    """Errores en rojo, descartados atenuados. La columna 'resultado' repite
    la informacion en texto: el color nunca es el unico canal."""
    if fila["resultado"] == "ERROR":
        return ["background-color: #ffd6d6"] * len(fila)
    if fila["resultado"] == "descartado":
        return ["color: #9a9a9a"] * len(fila)
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


# ---------------------------------------------------------------------------
# Controles del modulo 1 (barra lateral)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Parametros")
    st.caption("Estos controles son de la pestana **QKD (BB84)**.")
    n = st.select_slider(
        "Fotones", options=[1_000, 5_000, 10_000, 50_000], value=10_000
    )
    p = st.slider("Intensidad del espionaje de Eve", 0.0, 1.0, 0.0, 0.05)
    noise = st.slider("Ruido del canal", 0.0, 0.10, 0.01, 0.01)
    sample_fraction = st.slider("Fraccion de muestra (QBER)", 0.05, 0.50, 0.20, 0.05)
    seed = int(st.number_input("Semilla", value=42, step=1))
    st.caption(
        "Simulacion con el backend numpy (exacto y vectorizado): es el "
        "unico donde Eve esta modelada y el unico interactivo con 5·10^4 "
        "fotones. Ver run_bb84 en src/qkd/bb84.py."
    )

r = _simular(int(n), float(p), float(noise), float(sample_fraction), seed)

tab_qkd, tab_pqc = st.tabs(
    ["Modulo 1 · QKD (BB84)", "Modulo 2 · PQC (ML-KEM / ML-DSA) + Shor"]
)

# ===========================================================================
# PESTANA 1 - Modulo QKD (Fase 1, tarea 1.9). Contenido intacto: lo unico que
# cambia respecto a la Fase 1 es que ahora vive dentro de su pestana.
# ===========================================================================

with tab_qkd:
    st.title("QKD: distribucion cuantica de claves (BB84)")

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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "QBER medido",
        f"{r.qber.qber:.2%}",
        f"± {r.qber.sigma:.2%} (1 sigma)",
        delta_color="off",
    )
    c2.metric(
        "Clave final",
        "0 bits" if r.final_key is None else f"{r.final_key.size} bits",
    )
    c3.metric("Rendimiento", f"{r.secret_fraction:.1%}")
    c4.metric("f_EC (Cascade)", "—" if f_ec is None else f"{f_ec:.2f}")

    # --- El semaforo -------------------------------------------------------

    if r.aborted:
        st.error(f"PROTOCOLO ABORTADO — {r.abort_reason}.")
    else:
        assert r.final_key is not None
        st.success(f"Clave segura destilada: {r.final_key.size} bits.")

    # -----------------------------------------------------------------------
    # Figura Q(p) recalculada + tabla del sifting
    # -----------------------------------------------------------------------

    col_fig, col_tabla = st.columns([3, 2])

    with col_fig:
        st.subheader("QBER frente a la intensidad de Eve")
        ps, qs, sigmas = _barrido_qber(
            int(n), float(noise), float(sample_fraction), seed
        )
        fig, ax = plt.subplots(figsize=(6.5, 4))
        ax.errorbar(
            ps,
            qs,
            yerr=3 * np.asarray(sigmas),
            fmt="o",
            ms=4,
            capsize=3,
            label="QBER simulado (±3σ)",
            zorder=3,
        )
        ps_arr = np.asarray(ps)
        ax.plot(ps_arr, ps_arr / 4, "-", label="teoria: Q = p/4", zorder=2)
        ax.axhline(QBER_THRESHOLD, ls="--", color="gray", lw=1)
        ax.axhspan(QBER_THRESHOLD, 0.30, color="red", alpha=0.08, zorder=1)
        # Marcador de la ejecucion actual: rojo si aborto, verde si hay clave
        # (colores de estado, reservados para eso).
        ax.plot(
            [p],
            [r.qber.qber],
            "D",
            ms=9,
            color="#d62728" if r.aborted else "#2ca02c",
            label=f"ejecucion actual (p = {p:.2f})",
            zorder=4,
        )
        ax.set_xlabel("fraccion interceptada por Eve, p")
        ax.set_ylabel("QBER")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(0, 0.30)
        ax.grid(alpha=0.25, lw=0.5)
        ax.legend(fontsize=8)
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
        st.caption(
            "La recta teorica no es un ajuste: esta dibujada de la formula "
            "Q = p/4. El sombreado marca la zona por encima del umbral de "
            "seguridad del 11% (Shor-Preskill)."
        )

    with col_tabla:
        st.subheader(f"Sifting: primeros {N_FILAS_TABLA} fotones")
        df = _datos_sifting(int(n), float(p), float(noise), seed)
        if df is None:
            st.warning(
                "Tabla desactivada: el orden de sorteo interno de run_bb84 ha "
                "cambiado y la reconstruccion ya no coincide con la simulacion "
                "real. Revisar _datos_sifting en dashboard/qkd_app.py."
            )
        else:
            st.dataframe(
                df.style.apply(_colorea_fila, axis=1),
                hide_index=True,
                height=520,
                use_container_width=True,
            )
            st.caption(
                "Sobreviven las filas con bases iguales (~la mitad). Las filas "
                "en rojo son errores: aparecen al subir a Eve o el ruido. En "
                "las descartadas el resultado de Bob se tira sin publicarse."
            )

# ===========================================================================
# PESTANA 2 - Modulo PQC + Shor (Fase 2, tarea 2.9). Tres sub-pestanas: la
# amenaza (Shor), la defensa (cripto real) y su coste medido (benchmark), que
# es el arco entero del modulo 2.
# ===========================================================================

with tab_pqc:
    st.title("PQC: la amenaza (Shor) y su defensa (ML-KEM / ML-DSA)")
    sub_shor, sub_real, sub_bench = st.tabs(
        ["Shor: la amenaza", "PQC real: la defensa", "Benchmark: el coste"]
    )

    # -----------------------------------------------------------------------
    # Shor: factorizacion por busqueda de orden
    # -----------------------------------------------------------------------

    with sub_shor:
        col_ctrl, col_res = st.columns([1, 3])

        with col_ctrl:
            n_shor = st.selectbox("Numero a factorizar (N)", options=[15, 21])
            semilla_shor = int(
                st.number_input("Semilla de Shor", value=42, step=1, key="semilla_shor")
            )
            st.caption(
                "Shor SI se siembra: es una simulacion Qiskit/NumPy "
                "determinista. Misma semilla, misma factorizacion."
            )

        if n_shor == 21:
            # Limitacion conocida, y se dice en la interfaz en vez de esconder
            # la opcion: factorizar 21 necesita su propio oraculo compilado
            # (c_amod21, 5 qubits de trabajo). Queda documentado como trabajo
            # pendiente en el README, igual que la guia decidio en la tarea 2.3.
            with col_res:
                st.info(
                    "**N = 21 no esta implementado.** El oraculo de "
                    "exponenciacion modular esta compilado A MANO para cada "
                    "par (a, N): el de N=15 usa 4 qubits de trabajo y unas "
                    "puertas SWAP/X; el de N=21 necesita 5 qubits y su propio "
                    "c_amod21. Es una limitacion conocida y documentada, no un "
                    "fallo: N=15 es el requisito duro del modulo."
                )
        else:
            res = _factorizar(semilla_shor)

            with col_res:
                m1, m2, m3, m4 = st.columns(4)
                # Con ok=False los campos son CENTINELAS, no medidas (a=0,
                # orden=0: ver el docstring de FactorizacionShor). Se ensena
                # "—" en vez del cero, que aqui se leeria como "el orden es
                # cero". `intentos` si significa lo mismo en los dos casos.
                m1.metric(
                    "Factores de 15",
                    f"{res.factores[0]} × {res.factores[1]}" if res.ok else "—",
                )
                m2.metric("Orden r hallado", str(res.orden) if res.ok else "—")
                m3.metric("Base a usada", str(res.a) if res.ok else "—")
                m4.metric("Intentos", res.intentos)
                if res.ok:
                    st.success(
                        f"15 = {res.factores[0]} × {res.factores[1]} por "
                        f"busqueda de orden cuantica (fase medida "
                        f"{res.fase_medida:.3f} ≈ s/r con r = {res.orden})."
                    )
                else:
                    st.error(
                        "Shor no encontro factores en el numero maximo de "
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
                col_hist, col_texto = st.columns([3, 2])

                with col_hist:
                    st.subheader(f"Fase medida con a = {res.a} ({SHOTS_FASE} shots)")
                    fig_shor, ax_shor = plt.subplots(figsize=(6.5, 4))
                    # Las lineas de referencia van en los multiplos de 1/r con el r
                    # que hallo la ejecucion: no son un ajuste, son la prediccion.
                    for k in range(res.orden):
                        ax_shor.axvline(
                            k / res.orden, ls="--", color="gray", lw=1, zorder=1
                        )
                        ax_shor.text(
                            k / res.orden,
                            SHOTS_FASE * 0.34,
                            f"s/r = {k}/{res.orden}",
                            rotation=90,
                            fontsize=8,
                            color="gray",
                            ha="right",
                            va="bottom",
                        )
                    # Sin mathtext: en Streamlit la cache de mathtext de Matplotlib
                    # no es thread-safe (ver el docstring del modulo).
                    ax_shor.bar(fases, veces, width=0.012, color="C0", zorder=3)
                    ax_shor.set_xlabel("fase medida y/2⁸ (adimensional)")
                    ax_shor.set_ylabel(f"veces medida (de {SHOTS_FASE} shots)")
                    ax_shor.set_xlim(-0.05, 1.0)
                    ax_shor.set_ylim(0, SHOTS_FASE * 0.5)
                    ax_shor.grid(axis="y", alpha=0.25, lw=0.5)
                    fig_shor.tight_layout()
                    st.pyplot(fig_shor)
                    plt.close(fig_shor)
                    st.caption(
                        f"Los picos caen en los multiplos de 1/r con r = "
                        f"{res.orden}: eso es lo que las fracciones continuas "
                        "convierten en el orden, y de ahi salen los factores."
                    )

                with col_texto:
                    st.subheader("Que se esta viendo")
                    st.markdown(
                        f"""
1. **Estimacion de fase.** El circuito ({8} qubits de conteo + 4 de trabajo)
   mide una fase y/2⁸ ≈ s/r del operador |y⟩ → |{res.a}·y mod 15⟩.
2. **Fracciones continuas.** El denominador del mejor convergente da el orden
   **r = {res.orden}** (clasico, instantaneo).
3. **Reduccion clasica.** gcd({res.a}^(r/2) ± 1, 15) →
   **{res.factores[0]} y {res.factores[1]}**.

Esto es un **modelo de amenaza sobre numeros de juguete**, no una herramienta
que rompa nada en produccion: el oraculo esta compilado a mano para (a, N) y
factorizar RSA-2048 necesitaria del orden de miles de qubits logicos con
correccion de errores, que no existen.
"""
                    )

    # -----------------------------------------------------------------------
    # PQC real: cifrar y firmar un mensaje de verdad
    # -----------------------------------------------------------------------

    with sub_real:
        col_ctrl, col_estado = st.columns([2, 3])

        with col_ctrl:
            mensaje = st.text_input("Mensaje a cifrar y firmar", MENSAJE_DEMO)
            mecanismo_kem = st.selectbox(
                "Mecanismo KEM (FIPS 203)", MECANISMOS_ADMITIDOS, 1
            )
            mecanismo_sig = st.selectbox(
                "Mecanismo de firma (FIPS 204)", MECANISMOS_SIG, 1
            )
            # Un toggle y no un boton: el boton no sobrevive al rerun de
            # Streamlit sin session_state, y aqui interesa poder comparar el
            # antes y el despues sin que la demo se reinicie.
            manipular = st.toggle("Manipular un byte en transito", value=False)
            st.caption(
                "Estas claves NO se siembran: liboqs las genera con su propio "
                "CSPRNG y deben ser impredecibles. Cambiar el mensaje o el "
                "mecanismo genera un par nuevo."
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

        with col_estado:
            st.subheader("Lo que recibe el destinatario")
            try:
                descifrado = descifrar_mensaje(clave_privada, sobre_recibido).decode()
                st.success(f"Descifrado con {sobre.mecanismo}: “{descifrado}”")
            except InvalidTag:
                # No es un fallo del programa: es exactamente lo que tiene que
                # pasar. AES-GCM no devuelve texto en claro si el tag no cuadra.
                st.error(
                    "InvalidTag: AES-GCM ha detectado la manipulacion y NO "
                    "devuelve ni un byte de texto en claro."
                )
            if verificar(firma_recibida):
                st.success(f"Firma {firma.mecanismo} valida: el mensaje es autentico.")
            else:
                st.error(
                    f"Firma {firma.mecanismo} INVALIDA: la verificacion "
                    "devuelve False (nunca lanza: el caso negativo es un "
                    "resultado legitimo de la operacion)."
                )

        st.subheader("Los artefactos, con sus tamanos reales")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("kem_ciphertext", f"{len(sobre.kem_ciphertext)} B")
        t2.metric("nonce (AES-GCM)", f"{len(sobre.nonce)} B")
        t3.metric("clave publica de firma", f"{len(firma.clave_publica)} B")
        t4.metric("firma", f"{len(firma.firma)} B")

        st.code(
            f"mecanismo       : {sobre.mecanismo}  (KEM → HKDF-SHA256 → AES-256-GCM)\n"
            f"mensaje         : {mensaje}\n"
            f"kem_ciphertext  : {len(sobre.kem_ciphertext):>5} B -> "
            f"{_hex_previa(sobre.kem_ciphertext)}\n"
            f"nonce           : {len(sobre.nonce):>5} B -> "
            f"{_hex_previa(sobre.nonce)}   (fresco en cada cifrado)\n"
            f"aead_ciphertext : {len(sobre_recibido.aead_ciphertext):>5} B -> "
            f"{_hex_previa(sobre_recibido.aead_ciphertext)}"
            f"{'   <- BYTE MANIPULADO' if manipular else ''}\n"
            f"firma           : {len(firma_recibida.firma):>5} B -> "
            f"{_hex_previa(firma_recibida.firma)}"
            f"{'   <- BYTE MANIPULADO' if manipular else ''}",
            language="text",
        )
        st.caption(
            "Un KEM no cifra el mensaje: transporta un secreto de 32 bytes del "
            "que HKDF-SHA256 deriva la clave AES-256-GCM que si lo cifra. "
            "Firmar no oculta nada, autentica: el mensaje viaja en claro junto "
            "a la firma."
        )

    # -----------------------------------------------------------------------
    # Benchmark: la tabla medida (no se mide aqui, se lee del JSON)
    # -----------------------------------------------------------------------

    with sub_bench:
        st.subheader("Coste medido: clasico vs post-cuantico")
        if not RUTA_JSON.exists():
            st.info(
                f"No hay medidas todavia ({RUTA_JSON.name} no existe). "
                "Generalas con `python scripts/make_pqc_plots.py --medir` "
                "DENTRO del contenedor, que es donde las cifras son "
                "comparables."
            )
        else:
            # El dashboard NO mide: medir el benchmark cuesta ~1 min de CPU y
            # Streamlit reejecuta el script en cada interaccion. Se lee el JSON
            # versionado que produjo scripts/make_pqc_plots.py --medir.
            medidas, tamanos = cargar_json()
            con_carga = st.toggle(
                "Ensenar tambien la capa que (de)serializa la clave "
                f"(«{SUFIJO_CAPA_API.strip()}»)",
                value=False,
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
            col_t, col_s = st.columns([3, 2])
            with col_t:
                st.dataframe(
                    df_medidas.style.format(
                        {"media_ms": "{:.3f}", "sigma_ms": "{:.3f}", "p50_ms": "{:.3f}"}
                    ),
                    hide_index=True,
                    height=430,
                    use_container_width=True,
                )
                st.caption(
                    "media ± σ y mediana (p50), en milisegundos. La σ es la de "
                    "la muestra, DERIVADA de las repeticiones: una media sin "
                    "barra de error no es una medida, es una anecdota. La "
                    "mediana esta para detectar contaminacion del planificador."
                )
            with col_s:
                st.dataframe(
                    pd.DataFrame([asdict(t) for t in tamanos]),
                    hide_index=True,
                    height=430,
                    use_container_width=True,
                )
                st.caption(
                    "Tamanos en bytes (0 = no aplica). Sin barras de error: "
                    "son deterministas, los fija el estandar. El compromiso en "
                    "una linea: la PQC gana en tiempo y pierde en bytes."
                )

            datos_entorno = entorno_del_json()
            st.caption(
                "Medido en: "
                f"{datos_entorno['plataforma']} · {datos_entorno['procesador']} · "
                f"Python {datos_entorno['python']} · "
                f"liboqs {datos_entorno['liboqs']} · "
                f"{datos_entorno['medido_utc']}. Otra maquina da otras cifras: "
                "por eso el entorno viaja con las medidas."
            )
