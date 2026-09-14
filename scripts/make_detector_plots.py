"""scripts/make_detector_plots.py - tarea 4.9 (Carlos). Figuras del modulo 4.

Regenera TODAS las figuras del modulo con un solo comando:

    python scripts/make_detector_plots.py

Reglas de la tarea, heredadas de las tres fases anteriores:
  - Cuatro figuras, ni una mas. Salida versionada en docs/img/ (PNG,
    dpi=150, fondo blanco).
  - Sin titulo dentro de la figura: el titulo va en el pie del README.
  - Ejes etiquetados con unidades.
  - Este script NO reimplementa la logica del modulo: consume `detector`
    tal y como lo exporta el paquete.
  - Determinismo: la cadena de analisis (espectro, filtrado, entropia) es
    deterministica sobre los datos de entrada. Los BITS finales de la
    figura 3 NO lo son -la semilla de Toeplitz es de os.urandom, nunca
    sembrada-, asi que las figuras que muestran
    bits extraidos (fig. 3) publican la LONGITUD, no el contenido, y no
    se comparan por MD5 bit a bit como las de los tres modulos previos:
    solo se compara que el fichero se REGENERA sin error.

Igual que en la Fase 3 (script make_chaos_plots.py, ver su cabecera): los
scripts SI pueden imprimir. Este imprime las cifras que van a los pies de
figura del README.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from detector import (
    ajustar_alfa,
    cargar_muestra,
    densidad_espectral,
    detectar_picos,
    digitalizar,
    estimar_entropia,
    extraer,
    factor_fano,
    filtrar,
    rango_alfa_en_hz,
)
from detector.types import BITS_BAJOS, EPSILON_PA, NPERSEG, RANGO_ALFA, UMBRAL_PICO

# Backend sin pantalla: el script corre igual en local, en la CI y en Docker.
plt.switch_backend("Agg")

# Salida versionada, relativa a la raiz del repo.
DIR_SALIDA = Path(__file__).resolve().parents[1] / "docs" / "img"

# Paleta consistente con las figuras de los otros tres modulos.
COLOR_PRINCIPAL = "#17324d"
COLOR_ACENTO = "#1b7472"
COLOR_ALERTA = "#b34747"
COLOR_NEUTRO = "#6b6b6b"


def figura_1_espectro_anotado() -> None:
    """La PSD en log-log, con el ajuste de 1/f, el suelo blanco y los
    picos de interferencia marcados. La figura estrella del modulo:
    ensena los cuatro tipos de ruido en una sola imagen.

    NOTA HONESTA (tarea 4.9, encontrado al revisar esta figura): con
    los datos reales, el primer punto valido del espectro (0.244 Hz)
    cae DENTRO del rango de ajuste RANGO_ALFA convertido a Hz (0.05,
    5.0), y es casi el doble del segundo punto -- es el mismo punto
    que detectar_picos() marca como interferencia (informe de Marco,
    tarea 4.8: "la deriva residual del primer bin"). ajustar_alfa()
    tiene una mascara para excluir picos antes de ajustar, pero con
    solo ~20 puntos en el rango y un filtro de mediana de ventana 11,
    es posible que ese punto extremo en el borde de la ventana no se
    filtre bien. NO se ha tocado ajustar_alfa() (tarea 4.4, de Gonzalo,
    ya mergeada): no hay evidencia de que sea un bug y no un limite
    conocido del filtro de mediana con pocos puntos. Se documenta aqui
    y en el print() de esta funcion en vez de ocultarlo.
    """
    senal, fs = cargar_muestra()
    freqs, psd, k = densidad_espectral(senal, fs, NPERSEG)
    picos = detectar_picos(freqs, psd, UMBRAL_PICO)

    # BUG DE LA TAREA 4.4 ARREGLADO EN ESTA MISMA RAMA (ver el commit
    # anterior a este script): RANGO_ALFA esta documentado en types.py
    # como fraccion de Nyquist, pero ajustar_alfa lo compara contra Hz.
    # rango_alfa_en_hz hace la conversion.
    rango_hz = rango_alfa_en_hz(RANGO_ALFA, fs)
    alfa, alfa_error = ajustar_alfa(freqs, psd, rango_hz)
    fano = factor_fano(senal)

    # Suelo blanco: mediana de la mitad de alta frecuencia del espectro,
    # igual criterio que usa test_integration.py para AnalisisEspectral.
    suelo_blanco = float(np.median(psd[len(psd) // 2 :]))

    fig, ax = plt.subplots(figsize=(9.0, 5.4))
    mascara_valida = (freqs > 0) & (psd > 0)
    ax.loglog(
        freqs[mascara_valida],
        psd[mascara_valida],
        lw=1.0,
        color=COLOR_PRINCIPAL,
        label="PSD (Welch)",
    )

    # La recta del ajuste, dibujada SOLO en su rango de validez: fuera de
    # ese rango, el ajuste no dice nada.
    f_min, f_max = rango_hz
    f_recta = np.array([f_min, f_max])
    # S(f) = A / f^alfa. La A se despeja de un punto medio del ajuste
    # para que la recta pase por la nube de puntos, no solo tenga la
    # pendiente correcta.
    mascara_ajuste = (freqs >= f_min) & (freqs <= f_max) & mascara_valida
    if mascara_ajuste.any() and alfa != 0.0:
        f_ref = freqs[mascara_ajuste][len(freqs[mascara_ajuste]) // 2]
        a_const = psd[mascara_ajuste][len(freqs[mascara_ajuste]) // 2] * f_ref**alfa
        ax.loglog(
            f_recta,
            a_const / f_recta**alfa,
            "--",
            lw=1.8,
            color=COLOR_ALERTA,
            label=f"ajuste 1/f: \u03b1 = {alfa:.3f} \u00b1 {alfa_error:.3f}",
        )

    ax.axhline(
        suelo_blanco,
        ls=":",
        lw=1.4,
        color=COLOR_NEUTRO,
        label=f"suelo blanco \u2248 {suelo_blanco:.3g}",
    )

    for pico in picos:
        ax.axvline(pico, ls="-", lw=1.0, color=COLOR_ACENTO, alpha=0.6)
    if picos:
        ax.plot(
            [],
            [],
            "-",
            color=COLOR_ACENTO,
            alpha=0.6,
            label=f"picos detectados: {', '.join(f'{p:.3g} Hz' for p in picos)}",
        )

    ax.set_xlabel("frecuencia (Hz)")
    ax.set_ylabel("densidad espectral de potencia")
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)
    ax.grid(alpha=0.2, lw=0.5, which="both")

    print(
        f"[figura 1] N={len(senal)} K={k} tramos, "
        f"alfa={alfa:.4f}+-{alfa_error:.4f}, Fano={fano:.2f}, "
        f"picos={picos}, suelo_blanco={suelo_blanco:.4g}"
    )
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "detector_espectro.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_2_antes_y_despues_del_filtro() -> None:
    """Dos espectros superpuestos: antes y despues de filtrar. Se ve el
    pico de interferencia desaparecer y el resto del espectro sobrevivir.
    """
    senal, fs = cargar_muestra()
    freqs, psd_antes, _ = densidad_espectral(senal, fs, NPERSEG)
    picos = detectar_picos(freqs, psd_antes, UMBRAL_PICO)

    senal_filtrada = filtrar(senal, fs, picos)
    freqs2, psd_despues, _ = densidad_espectral(
        senal_filtrada.astype(np.int32), fs, NPERSEG
    )

    fig, ax = plt.subplots(figsize=(9.0, 5.4))
    mascara_v1 = (freqs > 0) & (psd_antes > 0)
    mascara_v2 = (freqs2 > 0) & (psd_despues > 0)
    ax.loglog(
        freqs[mascara_v1],
        psd_antes[mascara_v1],
        lw=1.0,
        color=COLOR_NEUTRO,
        alpha=0.7,
        label="antes de filtrar",
    )
    ax.loglog(
        freqs2[mascara_v2],
        psd_despues[mascara_v2],
        lw=1.2,
        color=COLOR_ACENTO,
        label="despues de filtrar",
    )
    for pico in picos:
        ax.axvline(pico, ls="--", lw=1.0, color=COLOR_ALERTA, alpha=0.5)
    if picos:
        ax.plot(
            [],
            [],
            "--",
            color=COLOR_ALERTA,
            alpha=0.5,
            label=f"interferencia filtrada: {', '.join(f'{p:.3g} Hz' for p in picos)}",
        )

    ax.set_xlabel("frecuencia (Hz)")
    ax.set_ylabel("densidad espectral de potencia")
    ax.legend(loc="upper right", fontsize=8.5, framealpha=0.9)
    ax.grid(alpha=0.2, lw=0.5, which="both")

    idx_pico = np.argmin(np.abs(freqs[mascara_v1] - picos[0])) if picos else None
    if idx_pico is not None:
        antes_en_pico = psd_antes[mascara_v1][idx_pico]
        idx_pico2 = np.argmin(np.abs(freqs2[mascara_v2] - picos[0]))
        despues_en_pico = psd_despues[mascara_v2][idx_pico2]
        print(
            f"[figura 2] potencia en el pico ({picos[0]:.4g} Hz): "
            f"antes={antes_en_pico:.4g}, despues={despues_en_pico:.4g}, "
            f"factor={antes_en_pico / despues_en_pico:.1f}x"
        )
    else:
        print("[figura 2] sin picos detectados en esta ejecucion")

    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "detector_filtro.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_3_embudo_de_entropia() -> None:
    """Cascada muestras -> bits conservados -> bits de min-entropia ->
    bits extraidos. Equivalente al embudo de bits del modulo 1: ensena
    de un vistazo cuanto se pierde en cada paso, y en particular que el
    ultimo salto es EXACTAMENTE el peaje del leftover hash lemma, no una
    perdida arbitraria.

    Escala logaritmica en el eje: bits_conservados = muestras x
    BITS_BAJOS es mayor que muestras, asi que en escala lineal la
    barra de "muestras" parece mas corta que las de bits, cuando el
    mensaje real del embudo es la caida DESDE bits_conservados hacia
    abajo. Con log-x las cuatro etapas se leen en su magnitud real.

    Solo la LONGITUD de los bits extraidos es determinista: su
    CONTENIDO no lo es (semilla de Toeplitz de os.urandom, nunca
    sembrada).
    """
    senal, fs = cargar_muestra()
    freqs, psd, _ = densidad_espectral(senal, fs, NPERSEG)
    picos = detectar_picos(freqs, psd, UMBRAL_PICO)
    filtrada = filtrar(senal, fs, picos)
    simbolos = digitalizar(filtrada, BITS_BAJOS)
    estimacion = estimar_entropia(simbolos)
    resultado = extraer(simbolos, estimacion, EPSILON_PA)

    muestras = len(senal)
    bits_conservados = muestras * BITS_BAJOS
    bits_min_entropia = muestras * estimacion.h_min
    bits_extraidos = resultado.longitud_segura
    peaje = bits_min_entropia - bits_extraidos

    etapas = [
        ("muestras", float(muestras), f"{muestras:,}"),
        (
            f"bits conservados\n(\u00d7{BITS_BAJOS} bits bajos)",
            float(bits_conservados),
            f"{bits_conservados:,} bits",
        ),
        (
            f"bits de min-entropia\n(\u00d7{estimacion.h_min:.3f} bits/simb.)",
            bits_min_entropia,
            f"{bits_min_entropia:,.0f} bits",
        ),
        (
            "bits extraidos\n(Toeplitz, tarea 1.6)",
            float(bits_extraidos),
            f"{bits_extraidos:,} bits (\u2212{peaje:,.0f})",
        ),
    ]

    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    colores = [COLOR_NEUTRO, COLOR_PRINCIPAL, COLOR_ACENTO, COLOR_ALERTA]
    y_positions = list(range(len(etapas)))[::-1]

    for (_etiqueta, valor, texto), y, color in zip(
        etapas, y_positions, colores, strict=True
    ):
        ax.barh(y, valor, height=0.55, color=color, alpha=0.85)
        ax.text(valor * 1.08, y, texto, va="center", fontsize=9, color=color)

    ax.set_xscale("log")
    ax.set_yticks(y_positions)
    ax.set_yticklabels([e[0] for e in etapas], fontsize=9.5)
    ax.set_xlabel("cantidad (escala logaritmica)")
    ax.set_xlim(muestras * 0.5, bits_conservados * 3.0)
    ax.grid(alpha=0.2, lw=0.5, axis="x", which="both")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    print(
        f"[figura 3] muestras={muestras} -> conservados={bits_conservados} "
        f"-> min_entropia={bits_min_entropia:.0f} -> extraidos={bits_extraidos} "
        f"(peaje leftover hash lemma: {peaje:.0f} bits)"
    )
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "detector_embudo.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_4_los_tres_estimadores() -> None:
    """Barras con h_mas_comun, h_colision y h_markov, con el minimo
    destacado. Ensena visualmente por que se toma el minimo de los tres
    (regla de SP 800-90B): cada estimador es
    ciego a cierto tipo de estructura, y con los datos reales de este
    modulo es el estimador de COLISION el que da el minimo, no el de
    Markov como cabria esperar por el argumento teorico de que Markov
    es el unico que ve la correlacion del 1/f residual. Se documenta
    tal cual sale, sin forzar la narrativa a la teoria: los tres se
    usan justamente porque no se sabe de antemano cual va a ganar.
    """
    senal, fs = cargar_muestra()
    freqs, psd, _ = densidad_espectral(senal, fs, NPERSEG)
    picos = detectar_picos(freqs, psd, UMBRAL_PICO)
    filtrada = filtrar(senal, fs, picos)
    simbolos = digitalizar(filtrada, BITS_BAJOS)
    estimacion = estimar_entropia(simbolos)

    nombres = ["valor mas comun", "colision", "Markov"]
    valores = [estimacion.h_mas_comun, estimacion.h_colision, estimacion.h_markov]
    es_minimo = [abs(v - estimacion.h_min) < 1e-9 for v in valores]

    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    colores = [COLOR_ALERTA if minimo else COLOR_PRINCIPAL for minimo in es_minimo]
    barras = ax.bar(nombres, valores, color=colores, alpha=0.88, width=0.55)

    for barra, valor, minimo in zip(barras, valores, es_minimo, strict=True):
        etiqueta = f"{valor:.3f}" + (" \u2190 minimo" if minimo else "")
        ax.text(
            barra.get_x() + barra.get_width() / 2,
            valor + max(valores) * 0.02,
            etiqueta,
            ha="center",
            fontsize=9,
            fontweight="bold" if minimo else "normal",
            color=COLOR_ALERTA if minimo else COLOR_PRINCIPAL,
        )

    ax.set_ylabel("min-entropia estimada (bits/simbolo)")
    ax.set_ylim(0, max(valores) * 1.18)
    ax.grid(alpha=0.2, lw=0.5, axis="y")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    print(
        f"[figura 4] h_mas_comun={estimacion.h_mas_comun:.4f} "
        f"h_colision={estimacion.h_colision:.4f} "
        f"h_markov={estimacion.h_markov:.4f} -> h_min={estimacion.h_min:.4f}"
    )
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "detector_estimadores.png", dpi=150, facecolor="white")
    plt.close(fig)


def main() -> None:
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    figura_1_espectro_anotado()
    figura_2_antes_y_despues_del_filtro()
    figura_3_embudo_de_entropia()
    figura_4_los_tres_estimadores()
    print(f"figuras regeneradas en {DIR_SALIDA}")


if __name__ == "__main__":
    main()
