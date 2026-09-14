"""scripts/make_chaos_plots.py — tarea 3.10 (Carlos). Figuras y GIF del modulo 3.

Regenera TODAS las figuras del modulo con un solo comando:

    python scripts/make_chaos_plots.py

Reglas de la tarea, heredadas de las dos fases anteriores:
  - Cuatro figuras y un GIF, ni una mas. Salida versionada en docs/img/
    (PNG, dpi=150, fondo blanco).
  - Sin titulo dentro de la figura: el titulo va en el pie del README.
  - Ejes etiquetados con unidades. Matplotlib por defecto, sin estilos
    exoticos.
  - Semilla fija donde haya azar. En este modulo casi no hay: la unica
    llamada a un generador sembrado es la textura de la imagen de prueba,
    dentro de imagen_de_prueba. El cifrado es determinista a partir de la
    clave, asi que las figuras son reproducibles BIT A BIT y la CI lo
    comprueba comparando el MD5 (igual que con las figuras de las fases 1 y 2).
  - Este script NO reimplementa la logica del modulo: consume `chaos` tal y
    como lo exporta el paquete.

La unica excepcion a lo anterior, y va documentada porque es una: la figura 2
necesita la imagen PERMUTADA PERO NO DIFUNDIDA, que es un estado intermedio
que cifrar_imagen no devuelve. En vez de reconstruir la receta de la orbita
aqui -y arriesgarse a que se separe de la del cifrado sin que nadie lo note-
se importa el ayudante privado cipher._valores_de_permutacion, exactamente
igual que hace tests/chaos/test_cipher.py y por el mismo motivo.

Convencion del equipo: los scripts SI pueden imprimir (src/chaos usa logging).
Este imprime las cifras que van a los pies de figura del README.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from chaos import (
    ClaveCaotica,
    cifrar_imagen,
    correlacion_adyacente,
    descifrar_imagen,
    entropia_shannon,
    imagen_de_prueba,
    lyapunov_logistico,
    orbita_logistica,
    orbita_lorenz,
    permutacion_desde_orbita,
)
from chaos.cipher import _valores_de_permutacion
from chaos.types import PASO_RK4, UMBRAL_LYAPUNOV
from matplotlib.animation import PillowWriter

# Backend sin pantalla: el script corre igual en local, en la CI y en Docker.
# switch_backend (y no matplotlib.use antes del import) para no romper el
# orden de imports que exige ruff (E402).
plt.switch_backend("Agg")

# Clave unica de todas las figuras. r = 3.99 es caotico sin ambiguedad, lejos
# de la ventana de periodo 3 en 3.83.
CLAVE = ClaveCaotica(sistema="logistico", x0=0.4, r=3.99)

# --- Figura 1: bifurcacion + Lyapunov ----------------------------------
# Malla de r. 1200 columnas dan una imagen nitida de las ventanas periodicas
# sin que el diagrama tarde mas de unos segundos.
R_MIN, R_MAX = 2.5, 4.0
N_R = 1200
# Iteraciones que se tiran para que solo quede el atractor, y puntos que se
# dibujan despues. Con 300 puntos por columna la region caotica se ve llena
# sin convertirse en una mancha uniforme.
TRANSITORIO_BIFURCACION = 1000
PUNTOS_BIFURCACION = 300
# Iteraciones del exponente para la curva. lyapunov_logistico usa 100 000 por
# defecto: eso son 120 millones de iteraciones para 1200 valores de r, varios
# minutos. Con 3000 la curva ya es lisa y la figura tarda segundos. Es una
# figura, no el test: el valor exacto lo fija test_lyapunov_de_r4_es_ln2.
N_LYAPUNOV = 3000
# La ventana de periodo 3, que es la trampa del modulo.
R_VENTANA = 3.83

# --- Figura 2: la cadena visual ----------------------------------------
LADO_CADENA = 256

# --- Figura 3: correlacion ---------------------------------------------
# Pares que se dibujan en la dispersion. 4000 llenan el cuadrado sin que el
# PNG pese de mas ni los puntos se solapen hasta ser una mancha.
PARES_DISPERSION = 4000

# --- Figura 4: el atractor ---------------------------------------------
PASOS_ATRACTOR = 30_000
TRANSITORIO_ATRACTOR = 2000

# --- El GIF ------------------------------------------------------------
# Fotogramas del GIF y tamano de la imagen que se anima. 24 fotogramas a 6
# por segundo son cuatro segundos de bucle; 128x128 mantiene el fichero por
# debajo del megabyte, que es lo que un README puede cargar sin molestar.
LADO_GIF = 128
FOTOGRAMAS_GIF = 24
FPS_GIF = 6

# Salida versionada, relativa a la raiz del repo (no al cwd): el script
# funciona igual lanzado desde la raiz o desde scripts/.
DIR_SALIDA = Path(__file__).resolve().parents[1] / "docs" / "img"

# Paleta sobria y consistente con las figuras de los otros dos modulos.
COLOR_PRINCIPAL = "#17324d"
COLOR_ACENTO = "#1b7472"
COLOR_ALERTA = "#b34747"


def _sin_ejes(ax: plt.Axes) -> None:
    """Quita marcas y ejes de un panel que ensena una imagen, no una grafica."""
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_edgecolor("#dbe2e8")


def figura_1_bifurcacion_y_lyapunov() -> None:
    """Diagrama de bifurcacion con lambda(r) debajo, mismo eje r.

    Es la figura que justifica la existencia de la tarea 3.3: se ve que
    lambda cruza a positivo exactamente donde empieza el caos y vuelve a
    negativo dentro de cada ventana periodica. La de periodo 3 en r = 3.83
    aparece marcada porque es la trampa del modulo: esta DENTRO del rango
    caotico nominal y sin embargo da un keystream de tres bytes repetidos.
    """
    erres = np.linspace(R_MIN, R_MAX, N_R)
    x_puntos: list[np.ndarray] = []
    y_puntos: list[np.ndarray] = []
    lambdas = np.empty(N_R, dtype=np.float64)

    for i, r in enumerate(erres):
        orb = orbita_logistica(
            0.4, float(r), TRANSITORIO_BIFURCACION + PUNTOS_BIFURCACION
        )
        atractor = orb[TRANSITORIO_BIFURCACION:]
        x_puntos.append(np.full(atractor.size, r))
        y_puntos.append(atractor)
        lambdas[i] = lyapunov_logistico(0.4, float(r), n=N_LYAPUNOV).lyapunov

    lam_en_la_ventana = lyapunov_logistico(0.4, R_VENTANA, n=N_LYAPUNOV).lyapunov
    lam_en_r4 = lyapunov_logistico(0.4, 4.0, n=N_LYAPUNOV).lyapunov
    print(
        f"[figura 1] lambda(r=4) = {lam_en_r4:.4f} (exacto: ln 2 = "
        f"{np.log(2.0):.4f}); lambda(r={R_VENTANA}) = {lam_en_la_ventana:.4f} "
        f"(ventana de periodo 3, NO caotica)"
    )

    fig, (ax_bif, ax_lam) = plt.subplots(
        2, 1, figsize=(7.6, 6.4), sharex=True, height_ratios=[3, 2]
    )

    ax_bif.plot(
        np.concatenate(x_puntos),
        np.concatenate(y_puntos),
        ",",
        color=COLOR_PRINCIPAL,
        alpha=0.35,
    )
    ax_bif.axvline(R_VENTANA, color=COLOR_ALERTA, lw=1.0, ls="--")
    ax_bif.text(
        R_VENTANA - 0.01,
        0.06,
        "ventana de periodo 3 (r = 3.83)",
        fontsize=8,
        color=COLOR_ALERTA,
        ha="right",
    )
    ax_bif.set_ylabel("valores visitados por la orbita, x")
    ax_bif.set_ylim(0, 1)

    ax_lam.plot(erres, lambdas, "-", color=COLOR_ACENTO, lw=1.0)
    ax_lam.axhline(0.0, color="gray", lw=1.0)
    ax_lam.axvline(R_VENTANA, color=COLOR_ALERTA, lw=1.0, ls="--")
    # La zona en la que el modulo RECHAZA la clave, que es la lectura
    # practica de toda la figura: no es "aqui hay caos", es "aqui se cifra".
    ax_lam.fill_between(
        erres,
        -1.5,
        0.0,
        where=lambdas <= UMBRAL_LYAPUNOV,
        color=COLOR_ALERTA,
        alpha=0.10,
    )
    ax_lam.text(
        2.55,
        -1.35,
        "lambda < 0: el modulo rechaza la clave",
        fontsize=8,
        color=COLOR_ALERTA,
    )
    ax_lam.set_xlabel("parametro del mapa logistico, r (adimensional)")
    ax_lam.set_ylabel("exponente de Lyapunov, lambda")
    ax_lam.set_ylim(-1.5, 0.8)
    ax_lam.set_xlim(R_MIN, R_MAX)
    ax_lam.grid(alpha=0.25, lw=0.5)

    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "chaos_bifurcacion.png", dpi=150, facecolor="white")
    plt.close(fig)


def _histograma(ax: plt.Axes, img: np.ndarray, color: str) -> None:
    """Histograma de 256 barras bajo cada panel de la figura 2."""
    ax.bar(
        np.arange(256),
        np.bincount(img.ravel(), minlength=256),
        width=1.0,
        color=color,
    )
    ax.set_xlim(0, 255)
    ax.set_yticks([])
    ax.tick_params(labelsize=7)
    ax.set_xlabel("valor del pixel", fontsize=8)


def figura_2_la_cadena_visual() -> None:
    """Original, permutada, cifrada y descifrada, con sus histogramas.

    Ensena de un vistazo el argumento del modulo: el histograma de la
    PERMUTADA es identico al del original -permutar mueve pixeles, no los
    altera- y solo se aplana despues de la difusion. Es decir, ninguna de
    las dos etapas basta sola.
    """
    img = imagen_de_prueba(LADO_CADENA, LADO_CADENA)
    m = img.size
    sigma = permutacion_desde_orbita(_valores_de_permutacion(CLAVE, m), m)
    permutada = img.ravel()[sigma].reshape(img.shape)
    cifrada = cifrar_imagen(img, CLAVE)
    descifrada = descifrar_imagen(cifrada, CLAVE)

    paneles = (
        ("original", img, COLOR_PRINCIPAL),
        ("permutada", permutada, COLOR_PRINCIPAL),
        ("cifrada", cifrada.datos, COLOR_ACENTO),
        ("descifrada", descifrada, COLOR_PRINCIPAL),
    )
    print(
        "[figura 2] entropia (bits/px): "
        + ", ".join(
            f"{etiqueta} {entropia_shannon(datos):.4f}"
            for etiqueta, datos, _ in paneles
        )
    )
    histograma_intacto = np.array_equal(
        np.bincount(img.ravel(), minlength=256),
        np.bincount(permutada.ravel(), minlength=256),
    )
    print(
        f"[figura 2] round-trip exacto: {np.array_equal(descifrada, img)}; "
        f"histograma de la permutada identico al del original: {histograma_intacto}"
    )

    fig, ejes = plt.subplots(2, 4, figsize=(10.5, 4.6), height_ratios=[5, 2])
    for columna, (etiqueta, datos, color) in enumerate(paneles):
        ax_img = ejes[0, columna]
        ax_img.imshow(datos, cmap="gray", vmin=0, vmax=255, interpolation="nearest")
        ax_img.set_xlabel(etiqueta, fontsize=10)
        _sin_ejes(ax_img)
        _histograma(ejes[1, columna], datos, color)

    ejes[1, 0].set_ylabel("frecuencia", fontsize=8)
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "chaos_cadena.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_3_correlacion() -> None:
    """Dispersion de (x_i, x_{i+1}) en la original y en la cifrada.

    La mas convincente del modulo: en la original los puntos se agolpan
    sobre la diagonal -un pixel se parece muchisimo a su vecino- y en la
    cifrada llenan el cuadrado uniformemente. El coeficiente de Pearson de
    cada panel va anotado dentro, con la tolerancia derivada de 1/sqrt(n)
    y no con un 0.05 redondo.
    """
    img = imagen_de_prueba()
    cifrada = cifrar_imagen(img, CLAVE).datos

    fig, ejes = plt.subplots(1, 2, figsize=(9.2, 4.6), sharex=True, sharey=True)
    for ax, (etiqueta, datos, color) in zip(
        ejes,
        (
            ("imagen original", img, COLOR_PRINCIPAL),
            ("imagen cifrada", cifrada, COLOR_ACENTO),
        ),
        strict=True,
    ):
        x = datos[:, :-1].ravel()
        y = datos[:, 1:].ravel()
        # Submuestreo por paso FIJO, no aleatorio: la figura no necesita una
        # semilla y los pares quedan repartidos por toda la imagen. Es la
        # misma politica que usa metrics.correlacion_adyacente.
        paso = max(1, x.size // PARES_DISPERSION)
        ax.plot(x[::paso], y[::paso], ".", ms=1.6, alpha=0.35, color=color)
        r = correlacion_adyacente(datos, "horizontal")
        ax.text(
            8,
            238,
            f"{etiqueta}\ncorrelacion horizontal r = {r:+.4f}",
            fontsize=9,
            va="top",
            color=color,
        )
        ax.set_xlabel("valor del pixel (i, j)")
        ax.set_xlim(0, 255)
        ax.set_ylim(0, 255)
        ax.grid(alpha=0.2, lw=0.5)
    ejes[0].set_ylabel("valor del pixel adyacente (i, j+1)")

    print(
        "[figura 3] correlacion horizontal: original "
        f"{correlacion_adyacente(img, 'horizontal'):+.4f}, cifrada "
        f"{correlacion_adyacente(cifrada, 'horizontal'):+.4f} "
        f"(tolerancia 4/sqrt(5000) = {4 / np.sqrt(5000):.4f})"
    )
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "chaos_correlacion.png", dpi=150, facecolor="white")
    plt.close(fig)


def figura_4_atractor_de_lorenz() -> None:
    """El atractor en 3D, coloreado por tiempo.

    No aporta nada a la criptografia y es la que mas gente va a mirar, asi
    que conviene que exista y que este bien: el color indica el avance del
    tiempo, de modo que se ve que la trayectoria salta entre las dos alas
    sin ningun patron. Esa es, visualmente, la sensibilidad a las
    condiciones iniciales que el modulo usa como generador.
    """
    trayectoria = orbita_lorenz(
        np.array([1.0, 1.0, 1.0]), PASOS_ATRACTOR + TRANSITORIO_ATRACTOR, PASO_RK4
    )[TRANSITORIO_ATRACTOR:]

    fig = plt.figure(figsize=(7.2, 6.0))
    ax = fig.add_subplot(111, projection="3d")
    tiempo = np.arange(trayectoria.shape[0]) * PASO_RK4
    # Se dibuja por tramos para poder colorear por tiempo sin cargar una
    # coleccion de 30 000 segmentos, que multiplicaria el peso del PNG.
    tramos = 120
    corte = np.array_split(np.arange(trayectoria.shape[0]), tramos)
    mapa = plt.get_cmap("viridis")
    for k, indices in enumerate(corte):
        # El +1 solapa el ultimo punto del tramo con el primero del siguiente:
        # sin el, la curva sale con 120 agujeros de un paso.
        fin = min(indices[-1] + 2, trayectoria.shape[0])
        segmento = trayectoria[indices[0] : fin]
        ax.plot(
            segmento[:, 0],
            segmento[:, 1],
            segmento[:, 2],
            lw=0.45,
            color=mapa(k / (tramos - 1)),
        )

    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.tick_params(labelsize=8)
    # elev/azim FIJOS: sin esto Matplotlib usa su angulo por defecto, que deja
    # el atractor casi de canto y superpone las dos alas. Con estos dos
    # numeros se ve la figura de mariposa, que es la razon de existir de esta
    # figura. Van escritos y no "ajustados a ojo cada vez" porque la CI
    # compara el MD5 del PNG: cualquier cambio aqui la pone roja a proposito.
    ax.view_init(elev=26, azim=-62)
    ax.set_box_aspect((1.0, 1.0, 0.75), zoom=1.08)
    print(
        f"[figura 4] atractor: {PASOS_ATRACTOR} pasos de RK4 con h = {PASO_RK4} "
        f"({tiempo[-1]:.0f} unidades de tiempo), rangos "
        f"x [{trayectoria[:, 0].min():.1f}, {trayectoria[:, 0].max():.1f}], "
        f"z [{trayectoria[:, 2].min():.1f}, {trayectoria[:, 2].max():.1f}]"
    )
    fig.tight_layout()
    fig.savefig(DIR_SALIDA / "chaos_atractor.png", dpi=150, facecolor="white")
    plt.close(fig)


def gif_del_cifrado() -> None:
    """El GIF del README: la imagen desapareciendo pixel a pixel y volviendo.

    Cada fotograma ensena la imagen con los primeros k pixeles (en el orden
    en que los recorre la difusion) ya sustituidos por los del cifrado. La
    primera mitad del bucle cifra y la segunda descifra, asi que se ve el
    round-trip completo: la imagen se disuelve en ruido y vuelve INTACTA,
    que es exactamente lo que el modulo promete.

    Es tambien la unica figura animada del repositorio, y usa PillowWriter
    (Pillow ya entra como dependencia de Matplotlib, no se anade nada al
    requirements.txt).
    """
    img = imagen_de_prueba(LADO_GIF, LADO_GIF)
    cifrada = cifrar_imagen(img, CLAVE).datos
    descifrada = descifrar_imagen(cifrar_imagen(img, CLAVE), CLAVE)
    assert np.array_equal(descifrada, img), "el GIF no puede ensenar un round-trip roto"

    plano = img.ravel()
    cifrado_plano = cifrada.ravel()
    m = plano.size
    mitad = FOTOGRAMAS_GIF // 2

    fig, ax = plt.subplots(figsize=(3.6, 3.9))
    lienzo = ax.imshow(img, cmap="gray", vmin=0, vmax=255, interpolation="nearest")
    _sin_ejes(ax)
    pie = ax.set_xlabel("original", fontsize=11)
    fig.tight_layout()

    ruta = DIR_SALIDA / "chaos_cifrado.gif"
    escritor = PillowWriter(fps=FPS_GIF)
    with escritor.saving(fig, str(ruta), dpi=100):
        for k in range(FOTOGRAMAS_GIF):
            if k < mitad:
                # Cifrando: crece la parte ya sustituida por el cifrado.
                cuantos = int(round(m * (k + 1) / mitad))
                marco = np.concatenate((cifrado_plano[:cuantos], plano[cuantos:]))
                pie.set_text(f"cifrando  {100 * cuantos // m:>3} %")
            else:
                # Descifrando: la parte cifrada se va devolviendo a su sitio.
                cuantos = int(round(m * (k - mitad + 1) / (FOTOGRAMAS_GIF - mitad)))
                marco = np.concatenate((plano[:cuantos], cifrado_plano[cuantos:]))
                pie.set_text(f"descifrando  {100 * cuantos // m:>3} %")
            lienzo.set_data(marco.reshape(img.shape))
            escritor.grab_frame(facecolor="white")
    plt.close(fig)
    print(
        f"[gif] {FOTOGRAMAS_GIF} fotogramas a {FPS_GIF} fps, {LADO_GIF}x{LADO_GIF}, "
        f"{ruta.stat().st_size / 1024:.0f} kB"
    )


def main() -> None:
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    figura_1_bifurcacion_y_lyapunov()
    figura_2_la_cadena_visual()
    figura_3_correlacion()
    figura_4_atractor_de_lorenz()
    gif_del_cifrado()
    print(f"figuras regeneradas en {DIR_SALIDA}")


if __name__ == "__main__":
    main()
