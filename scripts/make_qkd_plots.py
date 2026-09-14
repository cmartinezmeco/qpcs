"""scripts/make_qkd_plots.py — tarea 1.8 (Carlos). Graficas Matplotlib.

Regenera TODAS las figuras del README con un solo comando:

    python scripts/make_qkd_plots.py

Reglas de la tarea:
  - Tres figuras, ni una mas. Salida versionada en docs/img/ (PNG, dpi=150,
    fondo blanco).
  - Semilla fija: las figuras son reproducibles bit a bit.
  - Sin titulo dentro de la figura: el titulo va en el pie del README. El
    estadistico monobit z de la figura 2 va como anotacion dentro de los
    ejes, no en un titulo, para no violar esa regla.
  - Ejes etiquetados. Matplotlib por defecto, sin estilos exoticos.
  - Este script NO reimplementa logica de protocolo: consume QRNG,
    run_until_qber y run_protocol tal y como los exporta el paquete qkd.

Convencion del equipo: los scripts SI pueden imprimir (src/qkd usa logging).
Este imprime el R^2 de la figura 1 y el balance de bits de la figura 3, que
son los numeros que van en los pies de figura del README.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from qkd.protocol import QBER_THRESHOLD, run_protocol, run_until_qber
from qkd.qrng import QRNG

# Backend sin pantalla: el script corre igual en local, en la CI y en Docker.
# switch_backend (y no matplotlib.use antes del import) para no romper el
# orden de imports que exige ruff (E402).
plt.switch_backend("Agg")

# Semilla unica de todo el script: reproducibilidad bit a bit de las figuras.
SEMILLA = 42
# Fotones por punto del barrido de Eve (figura 1). Con 40 000 fotones la
# sigma binomial del QBER es ~0.005: las barras de error se ven pero no
# dominan (mismo n que usan los tests de la tarea 1.4).
N_BARRIDO = 40_000
# Bits del QRNG para la figura 2.
N_QRNG = 100_000
# Ejecucion del embudo (figura 3): los parametros de la tabla
# publicada en el README (N = 100 000, ruido 2%, sin Eve).
N_EMBUDO = 100_000
RUIDO_EMBUDO = 0.02

# Salida versionada, relativa a la raiz del repo (no al cwd): el script
# funciona igual lanzado desde la raiz o desde scripts/.
DIR_SALIDA = Path(__file__).resolve().parents[1] / "docs" / "img"


def _miles(v: int) -> str:
    """Formatea 100000 -> '100 000' (separador de miles con espacio)."""
    return f"{v:,}".replace(",", " ")


def figura_1_qber_vs_eve() -> None:
    """QBER frente a la intensidad del espionaje: la figura estrella.

    Puntos simulados con barras de error (3 sigma, derivada de la binomial
    de la muestra) y la recta teorica Q = p/4 dibujada de la formula, SIN
    ajustar nada: si pasa por los puntos es porque la fisica es correcta.
    """
    ps = np.linspace(0.0, 1.0, 11)
    qs: list[float] = []
    sigmas: list[float] = []
    for p in ps:
        # Misma semilla en cada punto: cada ejecucion es independiente y la
        # figura entera es reproducible.
        est = run_until_qber(
            n_photons=N_BARRIDO,
            eve_rate=float(p),
            rng=np.random.default_rng(SEMILLA),
        )
        qs.append(est.qber)
        sigmas.append(est.sigma)

    q_arr = np.asarray(qs)
    # R^2 CONTRA LA TEORIA (no contra un ajuste): 1 - SS_res/SS_tot con la
    # prediccion p/4. Es el numero del criterio de cierre de fase
    # ("Q(p) = p/4 con R^2 > 0.99") y va en el pie de figura del README.
    ss_res = float(np.sum((q_arr - ps / 4) ** 2))
    ss_tot = float(np.sum((q_arr - q_arr.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot
    print(f"[figura 1] R^2 frente a la recta teorica Q = p/4: {r2:.5f}")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.errorbar(
        ps,
        qs,
        yerr=3 * np.asarray(sigmas),
        fmt="o",
        capsize=3,
        label="QBER simulado ($\\pm 3\\sigma$)",
        zorder=3,
    )
    # NO es un ajuste: es la prediccion teorica dibujada tal cual.
    ax.plot(ps, ps / 4, "-", label="teoria: $Q = p/4$ (sin ajustar)", zorder=2)
    ax.axhline(QBER_THRESHOLD, ls="--", color="gray", lw=1)
    ax.axhspan(QBER_THRESHOLD, 0.30, color="red", alpha=0.08, zorder=1)
    ax.text(
        0.02,
        QBER_THRESHOLD + 0.005,
        "umbral de seguridad (11 %)",
        fontsize=8,
        color="gray",
    )
    ax.set_xlabel("fraccion de fotones interceptados por Eve, $p$ (adimensional)")
    ax.set_ylabel("QBER (fraccion de errores)")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(0, 0.30)
    ax.grid(alpha=0.25, lw=0.5)
    ax.legend()
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "qber_vs_eve.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_2_histograma_qrng() -> None:
    """Histograma del QRNG: equilibrio 0/1 (monobit) y rachas.

    Usa el backend qiskit del QRNG (el cuantico simulado, no el atajo
    numpy): es la pieza que la figura ensena y genera 10^5 bits en ~2 s,
    medido antes de decidirlo. El panel de rachas se anade porque es mas
    informativo y mas dificil de falsificar que el monobit a secas.
    """
    bits = QRNG(seed=SEMILLA, backend="qiskit").random_bits(N_QRNG)
    n = bits.size
    unos = int(bits.sum())
    ceros = n - unos
    # Estadistico monobit del NIST: z = |ceros - unos| / sqrt(n) ~ N(0,1).
    # Mismo criterio que test_monobit_dentro_de_4_sigma (tarea 1.2).
    z = abs(2 * unos - n) / np.sqrt(n)
    print(f"[figura 2] monobit: ceros={ceros}, unos={unos}, z={z:.3f}")

    # Longitudes de racha: distancias entre cambios de valor consecutivos.
    cambios = np.flatnonzero(np.diff(bits)) + 1
    bordes = np.concatenate((np.array([0]), cambios, np.array([n])))
    rachas = np.diff(bordes)
    max_l = 12
    observadas = np.bincount(rachas, minlength=max_l + 1)[1 : max_l + 1]
    # Para bits i.i.d. justos, P(racha de longitud L) = 2^-L: el numero
    # esperado de rachas de longitud L es N_rachas * 2^-L.
    longitudes = np.arange(1, max_l + 1)
    esperadas = rachas.size * 0.5**longitudes

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4))

    # --- Panel A: recuento de ceros y unos con el valor esperado n/2 ---
    ax1.bar([0, 1], [ceros, unos], width=0.6, color="C0")
    ax1.axhline(n / 2, ls="--", color="gray", lw=1)
    for x, v in ((0, ceros), (1, unos)):
        ax1.text(x, v, _miles(v), ha="center", va="bottom", fontsize=9)
    # El estadistico va como anotacion (la regla "sin titulo dentro de la
    # figura" manda sobre el "z en el titulo"). La
    # leyenda de la linea discontinua va en el mismo cuadro para no chocar
    # con las cifras de las barras.
    ax1.text(
        0.03,
        0.97,
        f"monobit $z$ = {z:.2f}  ($|z| < 4$: sin sesgo)\n"
        f"linea discontinua: esperado $n/2$ = {_miles(n // 2)}",
        transform=ax1.transAxes,
        fontsize=9,
        va="top",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )
    ax1.set_xticks([0, 1], ["0", "1"])
    ax1.set_xlabel("valor del bit")
    ax1.set_ylabel("numero de bits")
    ax1.set_ylim(0, n * 0.62)

    # --- Panel B: histograma de rachas frente a la geometrica teorica ---
    ax2.bar(longitudes, observadas, width=0.7, color="C0", label="observadas")
    ax2.plot(
        longitudes,
        esperadas,
        "o-",
        color="C1",
        ms=4,
        lw=1,
        label="esperadas: $N_r \\cdot 2^{-L}$",
    )
    # Escala log: la caida geometrica se ve como recta si el QRNG es justo.
    ax2.set_yscale("log")
    ax2.set_xlabel("longitud de la racha, $L$ (bits)")
    ax2.set_ylabel("numero de rachas")
    ax2.set_xticks(longitudes)
    ax2.legend()

    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "qrng_histograma.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_3_embudo_de_bits() -> None:
    """El embudo de bits: de 10^5 fotones a la clave final destilada.

    Es la tabla de balance del README hecha figura, y lo que
    demuestra que la cadena llega hasta el final (reconciliacion y
    amplificacion de privacidad) y no se queda en el sifting.
    """
    r = run_protocol(
        n_photons=N_EMBUDO,
        eve_rate=0.0,
        noise=RUIDO_EMBUDO,
        rng=np.random.default_rng(SEMILLA),
    )
    if r.aborted or r.reconciliation is None or r.final_key is None:
        # Con ruido del 2% y sin Eve el protocolo no puede abortar; si lo
        # hace, la figura seria mentira: mejor reventar con motivo.
        raise RuntimeError(f"el protocolo aborto ({r.abort_reason}): revisa Q")

    rec = r.reconciliation
    n_rec = int(rec.bob.size)
    ell = int(r.final_key.size)

    # MEJORA D1: f_EC sale de la property del contrato, ya implementada
    # (antes se calculaba aqui a mano porque el dataclass no almacenaba Q).
    f_ec = rec.efficiency

    print("[figura 3] balance de bits de la ejecucion (para el README):")
    print(f"  fotones enviados      {_miles(r.n_photons):>8}")
    print(f"  tras sifting          {_miles(r.sifted_len):>8}")
    print(f"  tras estimar QBER     {_miles(n_rec):>8}   (Q = {r.qber.qber:.2%})")
    leak_txt = f"(leak_ec = {_miles(rec.leak_ec)} bits, f_EC = {f_ec:.2f})"
    print(f"  tras Cascade          {_miles(n_rec):>8}   {leak_txt}")
    print(f"  clave final           {_miles(ell):>8}")
    print(f"  rendimiento           {r.secret_fraction:.1%}")

    etapas = [
        "fotones\nenviados",
        "tras\nsifting",
        "tras estimar\nQBER",
        "tras\nCascade",
        "clave\nfinal",
    ]
    valores = [r.n_photons, r.sifted_len, n_rec, n_rec, ell]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    barras = ax.bar(etapas, valores, width=0.65, color="C0")
    ax.bar_label(barras, labels=[_miles(v) for v in valores], padding=3, fontsize=9)
    # La barra "tras Cascade" mide lo mismo que la anterior (Cascade no
    # acorta la clave: publica paridades). La fuga se anota dentro.
    ax.text(
        3,
        n_rec / 2,
        f"se publican\n{_miles(rec.leak_ec)} bits\nde paridad",
        ha="center",
        va="center",
        fontsize=8,
        color="white",
    )
    ax.set_ylabel("bits")
    ax.set_ylim(0, r.n_photons * 1.12)
    ax.grid(axis="y", alpha=0.25, lw=0.5)
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "embudo_de_bits.png", dpi=150, facecolor="white")
    plt.close(fig)


def main() -> None:
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    figura_1_qber_vs_eve()
    figura_2_histograma_qrng()
    figura_3_embudo_de_bits()
    print(f"figuras regeneradas en {DIR_SALIDA}")


if __name__ == "__main__":
    main()
