"""Regenera los dos esquemas del documento de teoria del Modulo 4.

    python scripts/make_detector_theory_figs.py

Salida (versionada, con su MD5 comprobado en CI como las cuatro figuras del
modulo):

    docs/img/detector_cadena_lectura.png
    docs/img/detector_estrategia.png

Reglas del proyecto que este script respeta:
  - Nada de MathText ("$...$") en las etiquetas: se usan caracteres Unicode
    (alfa, sigma, flechas). Es el bug que la Fase 1 documento y que reaparecio
    en la Fase 2 con el formateador logaritmico.
  - dpi=150, fondo blanco, sin titulo dentro de la figura (el pie va en el
    documento que la enlaza).
  - Sin datos: son esquemas, no graficas, asi que no hay semilla que fijar.
"""

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

SALIDA = pathlib.Path("docs/img")

AZUL_B, AZUL_L, AZUL_T = "#3b7dd8", "#eef6ff", "#13314f"
AMBAR_B, AMBAR_L, AMBAR_T = "#d08b26", "#fff4e5", "#5a3d0a"
GRIS_B, GRIS_L, GRIS_T = "#8a8f98", "#f2f3f5", "#2b2f36"
VERDE_B, VERDE_L, VERDE_T = "#3f9155", "#eaf6ee", "#14401f"


def _caja(ax, x, y, w, h, texto, borde, relleno, color_texto, fs=9, discont=False):
    p = FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.4,
        edgecolor=borde,
        facecolor=relleno,
        linestyle=(0, (4, 3)) if discont else "solid",
        zorder=2,
    )
    ax.add_patch(p)
    ax.text(
        x, y, texto, ha="center", va="center", fontsize=fs, color=color_texto, zorder=3
    )


def _flecha(
    ax, xy_a, xy_b, color="#4a4f57", discont=False, etiqueta=None, dx=0.0, dy=0.0
):
    ax.add_patch(
        FancyArrowPatch(
            xy_a,
            xy_b,
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=1.2,
            color=color,
            linestyle=(0, (3, 3)) if discont else "solid",
            shrinkA=2,
            shrinkB=2,
            zorder=4,
        )
    )
    if etiqueta:
        mx = (xy_a[0] + xy_b[0]) / 2 + dx
        my = (xy_a[1] + xy_b[1]) / 2 + dy
        ax.text(
            mx,
            my,
            etiqueta,
            ha="center",
            va="center",
            fontsize=7.5,
            color="#4a4f57",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"),
            zorder=4,
        )


def _lienzo(w_in, h_in):
    fig, ax = plt.subplots(figsize=(w_in, h_in))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    return fig, ax


def cadena_de_lectura() -> None:
    """Esquema 1: los eslabones de la cadena y el ruido que anade cada uno."""
    fig, ax = _lienzo(10.0, 3.4)

    xs = [0.075, 0.245, 0.415, 0.585, 0.755, 0.925]
    y = 0.80
    h = 0.20
    cajas = [
        ("partícula", GRIS_B, GRIS_L, GRIS_T, 0.115),
        ("sensor\n(carga)", AZUL_B, AZUL_L, AZUL_T, 0.135),
        ("amplificador", AZUL_B, AZUL_L, AZUL_T, 0.135),
        ("conformador\n(shaper)", AZUL_B, AZUL_L, AZUL_T, 0.135),
        ("ADC", AZUL_B, AZUL_L, AZUL_T, 0.115),
        ("número\nen disco", GRIS_B, GRIS_L, GRIS_T, 0.125),
    ]
    for x, (t, b, r, c, ww) in zip(xs, cajas):
        _caja(ax, x, y, ww, h, t, b, r, c, fs=8.6)

    for i in range(len(xs) - 1):
        _flecha(ax, (xs[i] + cajas[i][4] / 2, y), (xs[i + 1] - cajas[i + 1][4] / 2, y))

    ruidos = [
        (xs[1], "ruido de disparo\nPoisson · F = 1"),
        (xs[2], "ruido térmico + 1/f\nJohnson–Nyquist"),
        (xs[3], "interferencias\n50 Hz y armónicos"),
        (xs[4], "cuantización"),
    ]
    y_r = 0.30
    for x, t in ruidos:
        _flecha(ax, (x, y - h / 2), (x, y_r + 0.095), color=AMBAR_B, discont=True)
        _caja(
            ax, x, y_r, 0.145, 0.19, t, AMBAR_B, AMBAR_L, AMBAR_T, fs=7.6, discont=True
        )

    ax.text(
        0.5,
        0.07,
        "Cada eslabón añade ruido de una naturaleza distinta: esa diferencia es lo que permite separarlos después.",
        ha="center",
        va="center",
        fontsize=8,
        color="#4a4f57",
    )

    SALIDA.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    fig.savefig(SALIDA / "detector_cadena_lectura.png", dpi=150, facecolor="white")
    plt.close(fig)


def estrategia_del_analisis() -> None:
    """Esquema 2: los cuatro pasos, y por que el Fano va el ultimo."""
    fig, ax = _lienzo(9.5, 5.4)

    _caja(
        ax,
        0.5,
        0.94,
        0.30,
        0.085,
        "señal cruda (cuentas ADC)",
        GRIS_B,
        GRIS_L,
        GRIS_T,
        fs=9,
    )
    _caja(
        ax,
        0.5,
        0.79,
        0.30,
        0.085,
        "1 · PSD por el método de Welch",
        AZUL_B,
        AZUL_L,
        AZUL_T,
        fs=9,
    )
    _flecha(ax, (0.5, 0.897), (0.5, 0.833))

    ax.text(
        0.5,
        0.705,
        "la FORMA del espectro separa tres cosas",
        ha="center",
        va="center",
        fontsize=8.2,
        style="italic",
        color="#4a4f57",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none"),
        zorder=5,
    )

    _caja(
        ax,
        0.16,
        0.575,
        0.28,
        0.105,
        "picos estrechos\n3 · detección de picos",
        AMBAR_B,
        AMBAR_L,
        AMBAR_T,
        fs=8.4,
    )
    _caja(
        ax,
        0.5,
        0.575,
        0.28,
        0.105,
        "pendiente en f^(−α)\n2 · ajuste de α",
        AMBAR_B,
        AMBAR_L,
        AMBAR_T,
        fs=8.4,
    )
    _caja(
        ax,
        0.845,
        0.575,
        0.28,
        0.105,
        "plano\nel espectro NO los separa",
        GRIS_B,
        GRIS_L,
        GRIS_T,
        fs=8.4,
    )

    _flecha(ax, (0.44, 0.748), (0.20, 0.628))
    _flecha(ax, (0.5, 0.748), (0.5, 0.628))
    _flecha(ax, (0.56, 0.748), (0.80, 0.628))

    _caja(
        ax,
        0.33,
        0.395,
        0.34,
        0.095,
        "filtrado: notch + paso alto\n(fase cero, orden bajo)",
        AZUL_B,
        AZUL_L,
        AZUL_T,
        fs=8.4,
    )
    _flecha(ax, (0.16, 0.522), (0.27, 0.443))
    _flecha(ax, (0.5, 0.522), (0.40, 0.443))

    _caja(
        ax,
        0.5,
        0.235,
        0.30,
        0.085,
        "4 · factor de Fano  F = Var / E",
        AZUL_B,
        AZUL_L,
        AZUL_T,
        fs=9,
    )
    _flecha(ax, (0.33, 0.347), (0.44, 0.278))
    _flecha(ax, (0.845, 0.522), (0.60, 0.278))

    _caja(
        ax,
        0.235,
        0.075,
        0.29,
        0.095,
        "ruido de disparo\nPoisson · fundamental",
        VERDE_B,
        VERDE_L,
        VERDE_T,
        fs=8.4,
    )
    _caja(
        ax,
        0.765,
        0.075,
        0.29,
        0.095,
        "ruido térmico\ngaussiano",
        VERDE_B,
        VERDE_L,
        VERDE_T,
        fs=8.4,
    )
    _flecha(ax, (0.42, 0.192), (0.29, 0.123), etiqueta="F ≈ 1", dx=-0.03, dy=0.012)
    _flecha(ax, (0.58, 0.192), (0.71, 0.123), etiqueta="F ≠ 1", dx=0.03, dy=0.012)

    SALIDA.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    fig.savefig(SALIDA / "detector_estrategia.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    cadena_de_lectura()
    estrategia_del_analisis()
    print(f"figuras escritas en {SALIDA.resolve()}")
