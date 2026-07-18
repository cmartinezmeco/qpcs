"""dashboard/qkd_app.py — tarea 1.9 (Carlos). Dashboard Streamlit.

Arranque local:

    streamlit run dashboard/qkd_app.py

Arranque en Docker (la direccion 0.0.0.0 es OBLIGATORIA: con el localhost
por defecto el contenedor escucha solo dentro de si mismo y desde el
navegador del anfitrion no se ve nada aunque el puerto este publicado):

    docker compose up
    # equivale a: streamlit run dashboard/qkd_app.py \
    #   --server.address=0.0.0.0 --server.port=8501

Este fichero NO reimplementa logica de protocolo: consume run_protocol,
run_until_qber y run_bb84 tal y como los exporta el paquete qkd. La unica
excepcion documentada es la tabla de sifting, que reproduce los tres
sorteos iniciales de run_bb84 para poder ensenar los fotones descartados
(ver _datos_sifting).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from qkd.bb84 import run_bb84
from qkd.privacy import binary_entropy
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

st.set_page_config(page_title="QPCS - BB84", layout="wide")
st.title("QKD: distribucion cuantica de claves (BB84)")


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
# Controles
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Parametros")
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

# ---------------------------------------------------------------------------
# Metricas grandes
# ---------------------------------------------------------------------------

# f_EC calculada aqui con binary_entropy porque la property
# ReconciliationResult.efficiency del contrato sigue sin implementar (y tal
# y como esta declarada no puede: el dataclass no almacena Q).
f_ec: float | None = None
if r.reconciliation is not None:
    h = binary_entropy(r.qber.qber)
    if h > 0.0 and r.reconciliation.bob.size > 0:
        f_ec = r.reconciliation.leak_ec / (r.reconciliation.bob.size * h)

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

# --- El semaforo -----------------------------------------------------------

if r.aborted:
    st.error(f"PROTOCOLO ABORTADO — {r.abort_reason}.")
else:
    assert r.final_key is not None
    st.success(f"Clave segura destilada: {r.final_key.size} bits.")

# ---------------------------------------------------------------------------
# Figura Q(p) recalculada + tabla del sifting
# ---------------------------------------------------------------------------

col_fig, col_tabla = st.columns([3, 2])

with col_fig:
    st.subheader("QBER frente a la intensidad de Eve")
    ps, qs, sigmas = _barrido_qber(int(n), float(noise), float(sample_fraction), seed)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.errorbar(
        ps,
        qs,
        yerr=3 * np.asarray(sigmas),
        fmt="o",
        ms=4,
        capsize=3,
        label="QBER simulado ($\\pm 3\\sigma$)",
        zorder=3,
    )
    ps_arr = np.asarray(ps)
    ax.plot(ps_arr, ps_arr / 4, "-", label="teoria: $Q = p/4$", zorder=2)
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
        label=f"ejecucion actual ($p$ = {p:.2f})",
        zorder=4,
    )
    ax.set_xlabel("fraccion interceptada por Eve, $p$")
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
