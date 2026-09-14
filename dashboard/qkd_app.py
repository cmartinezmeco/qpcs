"""dashboard/qkd_app.py — tareas 1.9, 2.9, 3.10 y 4.9 (Carlos). Dashboard Streamlit.

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

UN SOLO FICHERO, CUATRO MODULOS (tareas 2.9, 3.10 y 4.9)
-------------------------------------------------------
El panel del modulo 2 (PQC + Shor) vive aqui dentro, en su propia pestana, y no
en un dashboard/pqc_app.py aparte. La alternativa -pasar a una app multipagina
de Streamlit- obliga a mover ficheros a un directorio pages/ y a cambiar el
comando de arranque, y el criterio de cierre de la Fase 1 dice que el dashboard
arranca con `docker compose up`: no se toca. Con st.tabs los dos modulos
conviven sin que el de QKD cambie de comportamiento.

El modulo 3 (caos determinista) entra igual, como tercera pestana de nivel
superior, y reutiliza tal cual el sistema visual del rediseno: styles.css,
_cabecera_seccion y _preparar_ejes. Ni una linea de logica de cifrado vive
aqui: todo sale de `chaos` tal y como lo exporta el paquete. La unica
excepcion, documentada donde se usa, es el ayudante privado
cipher._valores_de_permutacion, que hace falta para ensenar la imagen
PERMUTADA PERO NO DIFUNDIDA -un estado intermedio que cifrar_imagen no
devuelve- sin reimplementar la receta de la orbita y arriesgarse a que se
separe de la del cifrado.

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
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from chaos import (
    ClaveCaotica,
    chi2_histograma,
    cifrar_aes_gcm,
    cifrar_flujo_trivial,
    cifrar_imagen,
    correlacion_adyacente,
    descifrar_imagen,
    entropia_esperada,
    entropia_shannon,
    imagen_de_prueba,
    lyapunov_logistico,
    permutacion_desde_orbita,
)
from chaos.cipher import _valores_de_permutacion
from chaos.types import UMBRAL_LYAPUNOV
from cryptography.exceptions import InvalidTag
from detector import (
    EstimacionEntropia,
    ResultadoExtraccion,
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
from matplotlib.ticker import FuncFormatter, PercentFormatter
from PIL import Image
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

# --- Constantes del modulo 4 (tarea 4.9) -----------------------------------
# Ancho de linea del volcado hexadecimal que se DESCARGA. Son unos 450 000
# digitos: en una sola linea el fichero es incomodo de abrir, y en renglones
# de 64 se lee como cualquier volcado hexadecimal de toda la vida. Los saltos
# son de presentacion, no forman parte del dato.
ANCHO_HEX = 64
# Cuantos digitos se mandan al HTML para la linea de muestra de la pantalla.
# No es lo que se ve: lo que se ve lo decide el ancho disponible, y del
# recorte se encarga la hoja de estilo. Este numero solo tiene que ser
# holgado para que nunca falte texto que ensenar, ni siquiera en una pantalla
# muy ancha.
VISTA_HEX = 320

# --- Constantes del modulo 3 (tarea 3.10) ----------------------------------
# Clave por defecto de la demostracion. r = 3.99 es caotico sin ambiguedad y
# esta lejos de la ventana de periodo 3 en 3.83, que es la trampa del modulo.
X0_DEMO = 0.4
R_DEMO = 3.99
# Lado maximo de una imagen subida por el usuario. El cifrado es un bucle de
# Python sobre cada pixel: 512x512 son 262 144 vueltas y ~0.3 s, y de ahi
# para arriba la interfaz empieza a arrastrarse. Las imagenes mas grandes se
# reescalan en vez de rechazarse, que para una demostracion es mas util.
LADO_MAXIMO_SUBIDA = 512
# Perturbacion de la clave equivocada. 1e-15 es del orden del ultimo bit de
# la mantisa de un float64: es la sensibilidad a la clave, que
# no es una propiedad del cifrado sino del exponente de Lyapunov.
EPSILON_CLAVE = 1e-15
# Clave AES de la tabla comparativa. Fija y visible A PROPOSITO: esto es una
# demostracion didactica, no un despliegue, y lo que importa es que las tres
# columnas se midan sobre la misma imagen. El nonce SI es fresco en cada
# llamada, que es justo la diferencia con el esquema caotico.
CLAVE_AES_DEMO = bytes(range(32))
# Pares que se dibujan en la dispersion de correlacion. Los mismos 5000 con
# los que metrics.correlacion_adyacente calcula r, para que la figura y el
# numero de la tabla hablen de la misma muestra.
PARES_CORRELACION = 5000

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
    # Ya no hay barra lateral: los parametros de BB84 viven dentro de su
    # pestana desde el rediseno del modulo 1.
    initial_sidebar_state="collapsed",
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
    """Cabecera editorial comun a los cuatro modulos y sus apartados."""
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
# simulacion completa y la interfaz se arrastraria.
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
        # Todas las celdas van como texto. Una columna numerica la alinea
        # Streamlit a la derecha y las de texto a la izquierda, y la tabla
        # salia con dos columnas escoradas a un lado y cinco al otro. Aqui
        # no hay nada que sumar ni ordenar: son etiquetas de posicion.
        filas.append(
            {
                "Fotón": str(i),
                "Bit de Alice": str(int(alice_bits[i])),
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


# ---------------------------------------------------------------------------
# Modulo 3: caos determinista (tarea 3.10). El motivo de la cache aqui es el
# tercero de los tres del fichero, y el mas fisico: cifrar una imagen de
# 512x512 son 262 144 vueltas de un bucle secuencial de Python en cada una de
# las dos pasadas de difusion, mas tres millones de iteraciones del mapa para
# generar la orbita. Sin cache, mover cualquier control -incluso uno de otra
# pestana, porque Streamlit reejecuta el script entero- relanzaria el cifrado
# completo y la interfaz se arrastraria.
#
# Y hay una diferencia con el modulo 2 que conviene tener presente al leer
# esto: aqui cachear NO cambia lo que se ve. El cifrado caotico es
# determinista a partir de la clave, asi que la cache devuelve exactamente lo
# mismo que devolveria recalcular. En el modulo 2 la cache existe justo por lo
# contrario (congelar un nonce fresco para que la demo se pueda seguir).
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _clave_caotica(sistema: str, x0: float, r: float, y0: float, z0: float):
    """Construye la ClaveCaotica a partir de los controles.

    Se pasan los cinco campos siempre y se descartan los que no aplican, en
    vez de montar el dataclass en la interfaz: asi el contrato de
    ClaveCaotica (que r es solo del logistico, y que y0/z0 son solo de
    Lorenz) se cumple en un unico sitio.
    """
    if sistema == "logistico":
        return ClaveCaotica(sistema="logistico", x0=x0, r=r)
    return ClaveCaotica(sistema="lorenz", x0=x0, y0=y0, z0=z0)


@st.cache_data(show_spinner=False)
def _diagnosticar_clave(sistema: str, x0: float, r: float):
    """Exponente de Lyapunov de la clave, para el semaforo.

    Solo tiene sentido para el mapa logistico: en Lorenz, sigma, rho y beta
    son constantes del contrato (types.py) y no partes variables de la
    clave, asi que lambda_1 no depende de lo que el usuario mueva. Devuelve
    None en ese caso y el semaforo lo dice con palabras.
    """
    if sistema != "logistico":
        return None
    return lyapunov_logistico(x0, r)


@st.cache_data(show_spinner=False)
def _cifrar_cadena(
    imagen: np.ndarray, sistema: str, x0: float, r: float, y0: float, z0: float
) -> dict[str, np.ndarray]:
    """Las cuatro imagenes del panel, de una sola pasada.

    original -> permutada -> cifrada -> descifrada. La permutada es un
    estado intermedio que cifrar_imagen no devuelve (el contenedor lleva el
    resultado final), asi que se reconstruye con el mismo ayudante que usa
    el propio orquestador, y no con una copia de la receta: ver el docstring
    del fichero.
    """
    clave = _clave_caotica(sistema, x0, r, y0, z0)
    m = imagen.size
    sigma = permutacion_desde_orbita(_valores_de_permutacion(clave, m), m)
    cifrada = cifrar_imagen(imagen, clave)
    return {
        "permutada": imagen.ravel()[sigma].reshape(imagen.shape),
        "cifrada": cifrada.datos,
        "descifrada": descifrar_imagen(cifrada, clave),
        "hash_plano": cifrada.hash_plano,
        "iv": cifrada.iv,
    }


@st.cache_data(show_spinner=False)
def _descifrar_con_otra_clave(
    imagen: np.ndarray, sistema: str, x0: float, r: float, y0: float, z0: float
) -> np.ndarray:
    """Descifra con una clave que difiere en 1e-15 en x0.

    Es el interruptor de "clave equivocada" del enunciado, y lo que ensena
    no es un fallo del cifrado sino el exponente de Lyapunov en accion: esa
    diferencia se amplifica como e^(lambda*n) y tras el transitorio de mil
    iteraciones que descarta el keystream las dos orbitas no tienen ninguna
    relacion. El descarte del transitorio no es higiene numerica, es lo que
    produce la sensibilidad a la clave.

    No lanza ni avisa: un cifrado sin autenticacion NO PUEDE distinguir
    "clave equivocada" de "cifrado manipulado", y fingir que si es
    exactamente la diferencia con AES-GCM que la tabla de abajo hace
    visible. Devuelve ruido, y quien quiera verificar compara el SHA-256.
    """
    clave = _clave_caotica(sistema, x0, r, y0, z0)
    cifrada = cifrar_imagen(imagen, clave)
    equivocada = _clave_caotica(sistema, x0 + EPSILON_CLAVE, r, y0, z0)
    return descifrar_imagen(cifrada, equivocada)


@st.cache_data(show_spinner=False)
def _tabla_tres_columnas(
    imagen: np.ndarray, sistema: str, x0: float, r: float, y0: float, z0: float
) -> pd.DataFrame:
    """La tabla comparativa, medida en vivo sobre la imagen que se ve.

    Las tres columnas se miden con las MISMAS funciones sobre la MISMA
    imagen: es lo que la convierte en una comparacion y no en tres medidas
    sueltas. NPCR y UACI se miden entre DOS CIFRADOS INDEPENDIENTES (dos
    claves separadas por 1e-15 en el caotico, dos nonces en AES, dos claves
    en el contador), que es la unica lectura en la que los tres esquemas son
    comparables: con la misma clave, un XOR con flujo fijo daria NPCR = 1/M
    por definicion.

    Las dos ultimas filas -prueba de seguridad y autenticacion- NO salen de
    ninguna medida. Son la leccion del modulo, y por eso estan aqui dentro y
    no en un pie de pagina.
    """
    clave = _clave_caotica(sistema, x0, r, y0, z0)
    otra_clave = _clave_caotica(sistema, x0 + EPSILON_CLAVE, r, y0, z0)
    otra_aes = bytes(range(1, 33))

    caotico = cifrar_imagen(imagen, clave).datos
    caotico_2 = cifrar_imagen(imagen, otra_clave).datos
    aes, _, _ = cifrar_aes_gcm(imagen, CLAVE_AES_DEMO)
    aes_2, _, _ = cifrar_aes_gcm(imagen, CLAVE_AES_DEMO)
    trivial = cifrar_flujo_trivial(imagen, CLAVE_AES_DEMO)
    trivial_2 = cifrar_flujo_trivial(imagen, otra_aes)

    columnas = {
        "Imagen plana": (imagen, None),
        "Esquema caótico": (caotico, caotico_2),
        "AES-256-GCM": (aes, aes_2),
        "Contador trivial": (trivial, trivial_2),
    }
    filas: dict[str, list[str]] = {}
    for etiqueta, (datos, pareja) in columnas.items():
        entropia = entropia_shannon(datos)
        fila = [
            f"{entropia:.4f}",
            f"{correlacion_adyacente(datos, 'horizontal'):+.4f}",
            f"{correlacion_adyacente(datos, 'vertical'):+.4f}",
            f"{correlacion_adyacente(datos, 'diagonal'):+.4f}",
            f"{chi2_histograma(datos):,.1f}".replace(",", " "),
        ]
        if pareja is None:
            fila += ["—", "—", "—", "—"]
        else:
            npcr = 100.0 * float(np.count_nonzero(datos != pareja)) / datos.size
            uaci = (
                float(np.abs(datos.astype(np.int16) - pareja.astype(np.int16)).mean())
                / 255.0
                * 100.0
            )
            autentica = "sí (tag GCM)" if etiqueta == "AES-256-GCM" else "no"
            prueba = "sí" if etiqueta == "AES-256-GCM" else "ninguna"
            fila += [f"{npcr:.4f}", f"{uaci:.4f}", prueba, autentica]
        filas[etiqueta] = fila

    esperado = [
        f"{entropia_esperada(imagen.size):.4f}",
        "0",
        "0",
        "0",
        "255 ± 22.6",
        "99.6094",
        "33.4635",
        "—",
        "—",
    ]
    indice = [
        "Entropía (bits/px)",
        "Correlación H",
        "Correlación V",
        "Correlación D",
        "χ² (255 gl)",
        "NPCR (%)",
        "UACI (%)",
        "Prueba de seguridad",
        "Autenticación",
    ]
    return pd.DataFrame({**filas, "Esperado": esperado}, index=indice)


def _imagen_subida(fichero) -> np.ndarray | None:
    """Convierte lo que suba el usuario en una imagen uint8 en escala de grises.

    El modulo trabaja en 8 bits y en escala de grises, y eso no es una
    limitacion de la interfaz sino del alcance declarado de la fase: el
    color es una extension trivial en volumen que no anade nada
    conceptual, y esta fuera a proposito. Aqui se convierte en vez de
    rechazar el fichero, y se dice en pantalla.

    Devuelve None si el fichero no se puede abrir como imagen, para que la
    pestana lo diga en vez de reventar con un traceback.
    """
    if fichero is None:
        return None
    # Restriccion explicita de formatos: sin esto, Image.open() autodetecta
    # el formato por el CONTENIDO del fichero, no por su extension, y el
    # selector del navegador (el "type" de st.file_uploader) es solo un
    # filtro de interfaz, no una barrera de seguridad -se puede renombrar
    # cualquier fichero con extension .png y Pillow lo abrira igual si
    # reconoce su firma interna-. Varios complementos de formato que Pillow
    # trae activados por defecto (PSD, FITS, PCF, BDF, GD, McIdas, TGA,
    # JPEG2000, entre otros) han tenido vulnerabilidades de lectura/escritura
    # fuera de limites explotables con un fichero manipulado. Restringir a
    # los cuatro formatos que la interfaz ofrece de verdad cierra esa via
    # de entrada, tanto para las vulnerabilidades ya conocidas como para
    # las que puedan aparecer en otros complementos en el futuro.
    formatos_permitidos = ("PNG", "JPEG", "BMP", "TIFF")
    try:
        with Image.open(fichero, formats=formatos_permitidos) as abierta:
            gris = abierta.convert("L")
            lado_mayor = max(gris.size)
            if lado_mayor > LADO_MAXIMO_SUBIDA:
                escala = LADO_MAXIMO_SUBIDA / lado_mayor
                nuevo = (
                    max(1, int(gris.width * escala)),
                    max(1, int(gris.height * escala)),
                )
                gris = gris.resize(nuevo, Image.LANCZOS)
            return np.asarray(gris, dtype=np.uint8).copy()
    except OSError:
        return None


@dataclass(frozen=True)
class AnalisisDetector:
    """Resultado tipado del analisis completo de la pestana del modulo 4
    (tarea 4.9). Reemplaza a un dict[str, object]: con un dataclass,
    mypy --strict sabe el tipo exacto de cada campo sin necesitar
    ningun type: ignore en el resto del bloque de la pestana.
    """

    n: int
    fs: float
    frecuencias: np.ndarray
    psd: np.ndarray
    k_tramos: int
    picos: tuple[float, ...]
    rango_hz: tuple[float, float]
    alfa: float
    alfa_error: float
    fano: float
    suelo_blanco: float
    estimacion: EstimacionEntropia
    resultado: ResultadoExtraccion
    bits_bajos: int


def _hex_previa(datos: bytes) -> str:
    """Los primeros bytes en hexadecimal, para ensenar un artefacto binario."""
    return datos[:BYTES_PREVIA].hex() + (" ..." if len(datos) > BYTES_PREVIA else "")


def _entero_es(valor: int) -> str:
    """Agrupa millares con punto para los contadores visibles en espanol."""
    return f"{valor:,}".replace(",", ".")


def _mostrar_flujo_qkd(resultado: ProtocolResult) -> None:
    """Resume la perdida de bits a lo largo de la cadena BB84.

    Las cuatro etapas van dentro de un solo rectangulo y con las flechas
    entre medias, igual que las cadenas de los modulos 2 y 3. Antes eran
    cuatro tarjetas separadas: se leian como cuatro medidas independientes
    cuando lo que cuentan es una sola cifra perdiendo bits por el camino.
    """
    tras_muestra = int(resultado.qber.remaining.alice.size)
    final = 0 if resultado.final_key is None else int(resultado.final_key.size)
    estado_final = "Protocolo abortado" if resultado.aborted else "Clave destilada"
    etapas = (
        ("Preparación", _entero_es(resultado.n_photons), "fotones enviados"),
        ("Cribado", _entero_es(resultado.sifted_len), "bases coincidentes"),
        ("Estimación", _entero_es(tras_muestra), "bits tras medir el QBER"),
        ("Privacidad", _entero_es(final), estado_final),
    )
    piezas: list[str] = []
    for posicion, (etiqueta, valor, detalle) in enumerate(etapas):
        if posicion:
            piezas.append('<div class="qpcs-flow__arrow">→</div>')
        piezas.append(
            '<div class="qpcs-flow__step">'
            f'<span class="qpcs-flow__label">{etiqueta}</span>'
            f'<span class="qpcs-flow__value">{valor}</span>'
            f'<span class="qpcs-flow__detail">{detalle}</span>'
            "</div>"
        )
    st.markdown(
        f'<div class="qpcs-flow">{"".join(piezas)}</div>',
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
# Cabecera y pestanas
# ---------------------------------------------------------------------------

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
            <span class="qpcs-tag">Caos determinista</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_qkd, tab_pqc, tab_chaos, tab_detector = st.tabs(
    [
        "Módulo 1 · Distribución de claves",
        "Módulo 2 · Amenaza y defensa",
        "Módulo 3 · Caos determinista",
        "Módulo 4 · Ruido de detectores",
    ]
)

# ===========================================================================
# PESTANA 1 - Modulo QKD (Fase 1, tarea 1.9).
#
# DONDE VIVEN LOS CONTROLES. Hasta ahora los parametros de BB84 estaban en la
# barra lateral, y hacia falta una nota aclarando que solo afectaban a este
# modulo: el panel tiene cuatro y la barra lateral se lee como global. Ahora
# estan dentro de la pestana, a la izquierda de las figuras que gobiernan,
# que es donde los modulos 3 y 4 pusieron los suyos desde el principio. La
# barra lateral ya no existe.
# ===========================================================================

with tab_qkd:
    _cabecera_seccion(
        "Módulo 01 · QKD / BB84",
        "Distribución cuántica de claves",
        "Observa cómo el ruido y la interceptación dejan una huella medible en el "
        "canal, y cómo BB84 decide si todavía es posible destilar una clave segura.",
    )

    col_parametros, col_figuras = st.columns([2, 3], gap="large")

    # -----------------------------------------------------------------------
    # Los controles del experimento
    # -----------------------------------------------------------------------

    with col_parametros:
        with st.container(border=True):
            st.subheader("Parámetros del experimento")
            st.caption(
                "Mueve cualquiera de los cinco y todo lo de esta pestaña se "
                "vuelve a calcular con ellos."
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
                    "Una muestra mayor reduce la incertidumbre, pero sacrifica más "
                    "bits de la clave."
                ),
            )
            seed = int(
                st.number_input(
                    "Semilla de la simulación",
                    value=42,
                    step=1,
                    help=(
                        "La misma semilla y los mismos parámetros reproducen el "
                        "resultado."
                    ),
                )
            )
            st.markdown(
                """
                <div class="qpcs-note">
                    Motor NumPy exacto y vectorizado. Es el único backend
                    interactivo que modela a Eve y admite hasta 50.000 fotones
                    con fluidez.
                </div>
                """,
                unsafe_allow_html=True,
            )

    p = p_porcentaje / 100
    noise = ruido_porcentaje / 100
    sample_fraction = muestra_porcentaje / 100
    r = _simular(int(n), float(p), float(noise), float(sample_fraction), seed)

    # -----------------------------------------------------------------------
    # Las dos figuras, una encima de la otra
    # -----------------------------------------------------------------------

    with col_figuras:
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
                # Todas las columnas son texto (ver _datos_sifting), asi que la
                # tabla sale alineada a la izquierda de punta a punta en vez de
                # mezclar dos numeros a la derecha con cinco textos a la
                # izquierda.
                st.dataframe(
                    df.style.apply(_colorea_fila, axis=1),
                    hide_index=True,
                    height=440,
                    use_container_width=True,
                )
                st.caption(
                    "Solo sobreviven las bases coincidentes. Los errores se "
                    "resaltan en rojo y los fotones descartados aparecen atenuados; "
                    "el significado nunca depende únicamente del color."
                )

    # -----------------------------------------------------------------------
    # El resultado de la ejecucion, a lo ancho
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
            # pendiente en el README, igual que se decidio en la tarea 2.3.
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
                        st.markdown(f"""
1. **Estimación de fase.** El circuito (8 qubits de conteo y 4 de trabajo)
   mide una fase y/2⁸ ≈ s/r del operador |y⟩ → |{res.a}·y mod 15⟩.
2. **Fracciones continuas.** El denominador del mejor convergente proporciona
   el orden **r = {res.orden}** mediante un cálculo clásico inmediato.
3. **Reducción clásica.** gcd({res.a}^(r/2) ± 1, 15) produce
   **{res.factores[0]} y {res.factores[1]}**.
""")

                # El aviso del modelo de amenaza va a lo ancho y no dentro de
                # la columna estrecha de al lado del histograma: son tres
                # parrafos, y en dos quintos de pagina se convertian en una
                # tira estrecha larguisima con medio panel vacio al lado. Es
                # ademas lo mas importante de esta pestana, asi que ocupa el
                # ancho entero.
                st.warning(
                    "**Modelo de amenaza, no herramienta de ataque.** "
                    "Lo que acabas de ejecutar factoriza el número 15. El "
                    "oráculo de exponenciación modular está escrito a mano "
                    "para cada pareja (a, N), y construirlo en general para "
                    "un número grande es justamente el trabajo que nadie "
                    "sabe hacer todavía.\n\n"
                    "Conviene decir con todas las letras dónde está hoy la "
                    "frontera. **A fecha de septiembre de 2026 esa máquina "
                    "no existe, ni de lejos.** Los procesadores cuánticos "
                    "disponibles se cuentan en cientos o unos pocos miles "
                    "de qubits *físicos*, ruidosos y sin corrección de "
                    "errores en funcionamiento continuo. Romper una clave "
                    "RSA-2048 con Shor exige unos pocos miles de qubits "
                    "*lógicos*, y cada qubit lógico se construye encima de "
                    "miles de físicos que se dedican solo a corregir los "
                    "errores de los demás. Las estimaciones publicadas de "
                    "cuántos qubits físicos harían falta se han ido "
                    "revisando a la baja con los años, pero ninguna baja "
                    "del orden del millón, y todas dan por hecha una "
                    "corrección de errores que hoy no está resuelta. La "
                    "distancia no es de ingeniería: son varios órdenes de "
                    "magnitud.\n\n"
                    "Entonces, ¿por qué migrar ya? Porque el tráfico "
                    "cifrado se puede guardar. Quien archive hoy una "
                    "conversación protegida con RSA o con curvas podrá "
                    "descifrarla el día que esa máquina llegue, y ese día "
                    "no hay forma de retirar lo que ya se envió. Es lo que "
                    "se conoce como *harvest now, decrypt later*, y es de "
                    "lo que trata la pestaña siguiente."
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

            # Las dos tablas van una encima de otra y a todo lo ancho. Lado a
            # lado, la de tiempos se comia siete columnas en tres quintos de
            # pagina y la de tamanos se quedaba con un hueco fijo de 430 px
            # para cinco filas: el resto eran renglones en blanco.
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

            with st.container(border=True):
                st.subheader("Tamaño de los artefactos")
                # Sin altura fija: la tabla crece lo que midan sus filas y se
                # acaba ahi.
                st.dataframe(
                    df_tamanos,
                    hide_index=True,
                    use_container_width=True,
                )
                st.caption(
                    "Los tamaños son deterministas y no necesitan barras de "
                    "error. Un cero indica que el artefacto no aplica."
                )

            datos_entorno = entorno_del_json()
            with st.expander("Consultar el entorno de medición"):
                st.markdown(f"""
- **Plataforma:** {datos_entorno['plataforma']}
- **Procesador:** {datos_entorno['procesador']}
- **Python:** {datos_entorno['python']}
- **liboqs:** {datos_entorno['liboqs']}
- **Fecha UTC:** {datos_entorno['medido_utc']}
""")
                # La lista y la nota se tocaban. Un renglon de aire entre
                # medias separa el dato de su comentario.
                st.write("")
                st.caption(
                    "Otra máquina puede producir cifras distintas; por eso el "
                    "entorno forma parte inseparable de las medidas."
                )


# ===========================================================================
# PESTANA 3 - Modulo de caos determinista (Fase 3, tarea 3.10).
#
# El aviso que gobierna el modulo entero va ARRIBA DEL TODO y no en un pie
# de pagina: este es el unico modulo del repositorio cuyas metricas salen
# espectaculares y cuya seguridad real es nula, y la interfaz es justo donde
# esa confusion se produce. Si alguien solo mira esta pestana en una demo,
# tiene que leer la advertencia antes que la tabla.
# ===========================================================================

with tab_chaos:
    _cabecera_seccion(
        "Módulo 03 · Caos determinista",
        "Cifrado de imágenes con el mapa logístico y Lorenz",
        "Una imagen entra, sale ruido y vuelve intacta. La clave define una "
        "órbita, la órbita define un flujo de bytes y ese flujo define "
        "completamente el cifrado: no hay ninguna otra fuente de aleatoriedad.",
    )
    st.warning(
        "**El aviso que gobierna todo el módulo.** Esto es un esquema de "
        "permutación–difusión basado en caos determinista. Tiene métricas "
        "excelentes y **no tiene prueba de seguridad**. **No sustituye a AES.** "
        "Usa un sistema caótico porque es física interesante y visualmente "
        "demostrable, no porque sea criptográficamente superior."
    )
    st.markdown(
        """
        <div class="qpcs-process">
            <div class="qpcs-process__item">
                <strong>Clave</strong><span>Define la órbita</span>
            </div>
            <div class="qpcs-process__arrow">→</div>
            <div class="qpcs-process__item">
                <strong>Keystream</strong><span>Bits bajos de la órbita</span>
            </div>
            <div class="qpcs-process__arrow">→</div>
            <div class="qpcs-process__item">
                <strong>Permutación</strong><span>Rompe la correlación</span>
            </div>
            <div class="qpcs-process__arrow">→</div>
            <div class="qpcs-process__item">
                <strong>Difusión</strong><span>Aplana el histograma</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Controles. Van DENTRO de la pestana y no en la barra lateral: la lateral
    # es de BB84 desde la Fase 1 y su cabecera lo dice, asi que meter aqui los
    # parametros de otro modulo obligaria a leer dos sitios para entender una
    # sola figura.
    # -----------------------------------------------------------------------

    col_control, col_diagnostico = st.columns([2, 3], gap="large")

    with col_control:
        with st.container(border=True):
            st.subheader("Clave y dinámica")
            sistema_caos = st.selectbox(
                "Sistema dinámico",
                options=["logistico", "lorenz"],
                format_func=lambda s: {
                    "logistico": "Mapa logístico (1D, discreto)",
                    "lorenz": "Lorenz (3D, continuo, RK4)",
                }[s],
                help=(
                    "Los dos generan el mismo tipo de flujo de bytes. Lorenz "
                    "integra con Runge-Kutta de paso fijo y es dos órdenes de "
                    "magnitud más lento por muestra."
                ),
            )
            x0_caos = st.number_input(
                "x₀ (condición inicial)",
                min_value=0.001,
                max_value=0.999,
                value=X0_DEMO,
                step=0.05,
                format="%.3f",
                help="Debe estar en (0, 1): 0 y 1 son puntos fijos del mapa.",
            )
            if sistema_caos == "logistico":
                r_caos = st.slider(
                    "r (parámetro del mapa)",
                    min_value=2.50,
                    max_value=4.00,
                    value=R_DEMO,
                    step=0.01,
                    help=(
                        "Prueba r = 3.83: está dentro del rango caótico nominal "
                        "y sin embargo tiene periodo 3. El módulo lo rechaza."
                    ),
                )
                y0_caos, z0_caos = 1.0, 1.0
            else:
                r_caos = R_DEMO
                y0_caos = st.number_input("y₀", value=1.0, step=0.5, format="%.2f")
                z0_caos = st.number_input("z₀", value=1.0, step=0.5, format="%.2f")
                st.markdown(
                    """
                    <div class="qpcs-note">
                        σ, ρ y β son constantes del contrato, no partes de la
                        clave: por eso λ no depende de lo que muevas aquí.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with st.container(border=True):
            st.subheader("Imagen")
            origen = st.radio(
                "Origen de la imagen",
                options=["generada", "subida"],
                format_func=lambda o: {
                    "generada": "Imagen de prueba generada",
                    "subida": "Subir una imagen propia",
                }[o],
                horizontal=True,
                help=(
                    "Las cifras publicadas en el README salen siempre de la "
                    "imagen generada, que es reproducible. La subida es para "
                    "la demostración."
                ),
            )
            if origen == "generada":
                lado_caos = st.select_slider(
                    "Tamaño",
                    options=[64, 128, 256, 512],
                    value=128,
                    format_func=lambda v: f"{v}×{v}",
                )
                imagen_caos = imagen_de_prueba(lado_caos, lado_caos)
                st.markdown(
                    """
                    <div class="qpcs-note">
                        Cuadrante plano, degradado, bordes duros y textura
                        sembrada: las cuatro estructuras que las métricas
                        tienen que ver desaparecer.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                fichero_subido = st.file_uploader(
                    "Imagen (PNG, JPG…)", type=["png", "jpg", "jpeg", "bmp", "tif"]
                )
                subida = _imagen_subida(fichero_subido)
                if fichero_subido is not None and subida is None:
                    st.error(
                        "No se ha podido abrir ese fichero como imagen. "
                        "Prueba con un PNG o un JPG."
                    )
                imagen_caos = (
                    subida if subida is not None else imagen_de_prueba(128, 128)
                )
                if subida is not None:
                    st.caption(
                        f"Convertida a escala de grises de 8 bits, "
                        f"{subida.shape[1]}×{subida.shape[0]} px. El color está "
                        f"fuera del alcance declarado de la fase, no es un fallo "
                        f"de la aplicación."
                    )

            clave_equivocada = st.toggle(
                "Descifrar con la clave equivocada",
                value=False,
                help=(
                    "Cambia x₀ en 1e-15, el último bit de la mantisa. El "
                    "resultado es indistinguible de ruido."
                ),
            )

    # -----------------------------------------------------------------------
    # El semaforo de Lyapunov. Es la pieza que impide cifrar con una clave que
    # no produce caos, y aqui es tambien la que explica POR QUE cuando el
    # cifrado se niega a ejecutarse.
    # -----------------------------------------------------------------------

    with col_diagnostico:
        with st.container(border=True):
            st.subheader("Diagnóstico del caos")
            st.caption(
                "λ se calcula para la clave que has puesto; no se cita de "
                "ningún artículo. Es lo que decide si el módulo cifra o no."
            )
            diagnostico_caos = _diagnosticar_clave(sistema_caos, x0_caos, r_caos)
            if diagnostico_caos is None:
                st.info(
                    "**Lorenz con los parámetros clásicos (σ = 10, ρ = 28, "
                    "β = 8/3).** λ₁ ≈ +0.906 está verificado por test contra la "
                    "suma del espectro, −(σ + 1 + β) = −13.667, que es una "
                    "comprobación independiente y gratuita del integrador. No "
                    "depende de la clave, así que no se recalcula aquí."
                )
            else:
                d1, d2, d3 = st.columns(3, gap="medium")
                d1.metric(
                    "Exponente λ",
                    f"{diagnostico_caos.lyapunov:+.4f}",
                    f"± {diagnostico_caos.sigma:.4f} (1 σ)",
                    delta_color="off",
                )
                d2.metric("Umbral", f"{UMBRAL_LYAPUNOV:.2f}")
                d3.metric("Iteraciones", _entero_es(diagnostico_caos.n_iteraciones))
                if diagnostico_caos.es_caotico:
                    st.success(
                        f"**Clave aceptada.** λ = {diagnostico_caos.lyapunov:+.4f} "
                        f"> {UMBRAL_LYAPUNOV}: las trayectorias vecinas se separan "
                        f"exponencialmente y el flujo de bytes no se repite."
                    )
                else:
                    st.error(
                        f"**Clave rechazada.** λ = {diagnostico_caos.lyapunov:+.4f} "
                        f"no supera {UMBRAL_LYAPUNOV}: con r = {r_caos:.2f} el mapa "
                        f"es periódico y el «cifrado» sería un puñado de bytes "
                        f"repetidos. El módulo se niega a cifrar en vez de "
                        f"producir una imagen que parece cifrada y no lo está."
                    )
            st.markdown(
                """
                <div class="qpcs-note">
                    Para r = 4 el valor exacto es ln 2 = 0.693147…, y no es una
                    referencia bibliográfica: el mapa logístico con r = 4 es
                    conjugado con el mapa de la tienda. El test
                    <code>test_lyapunov_de_r4_es_ln2</code> lo comprueba con la
                    tolerancia derivada del propio error estándar.
                </div>
                """,
                unsafe_allow_html=True,
            )

    # -----------------------------------------------------------------------
    # La cadena visual. Si la clave no es caotica, cifrar_imagen lanza
    # ValueError: se captura y se ensena el motivo, que es exactamente lo que
    # el modulo quiere demostrar, en vez de dejar caer un traceback.
    # -----------------------------------------------------------------------

    try:
        etapas_caos = _cifrar_cadena(
            imagen_caos, sistema_caos, x0_caos, r_caos, y0_caos, z0_caos
        )
    except ValueError as error_caos:
        etapas_caos = None
        st.error(f"**El módulo se ha negado a cifrar.** {error_caos}")

    if etapas_caos is not None:
        if clave_equivocada:
            recuperada = _descifrar_con_otra_clave(
                imagen_caos, sistema_caos, x0_caos, r_caos, y0_caos, z0_caos
            )
            etiqueta_final = "descifrada con la clave equivocada"
        else:
            recuperada = etapas_caos["descifrada"]
            etiqueta_final = "descifrada"

        st.markdown(
            '<div class="qpcs-kicker">La cadena, paso a paso</div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            paneles_caos = (
                ("original", imagen_caos),
                ("permutada", etapas_caos["permutada"]),
                ("cifrada", etapas_caos["cifrada"]),
                (etiqueta_final, recuperada),
            )
            fig_cadena, ejes_cadena = plt.subplots(
                2, 4, figsize=(11.0, 4.8), height_ratios=[5, 2]
            )
            fig_cadena.patch.set_facecolor("#ffffff")
            for columna, (etiqueta, datos) in enumerate(paneles_caos):
                ax_img = ejes_cadena[0, columna]
                ax_img.imshow(
                    datos, cmap="gray", vmin=0, vmax=255, interpolation="nearest"
                )
                ax_img.set_xlabel(etiqueta, fontsize=10, color=COLOR_TINTA)
                ax_img.set_xticks([])
                ax_img.set_yticks([])
                for lado in ax_img.spines.values():
                    lado.set_edgecolor(COLOR_BORDE)

                ax_hist = ejes_cadena[1, columna]
                ax_hist.bar(
                    np.arange(256),
                    np.bincount(datos.ravel(), minlength=256),
                    width=1.0,
                    color=COLOR_TEAL if columna == 2 else COLOR_NAVY,
                )
                ax_hist.set_xlim(0, 255)
                ax_hist.set_yticks([])
                ax_hist.tick_params(labelsize=7, colors=COLOR_MUTED)
                ax_hist.set_xlabel("valor del píxel", fontsize=8, color=COLOR_TINTA)
                for lado in ("top", "right"):
                    ax_hist.spines[lado].set_visible(False)
            fig_cadena.tight_layout()
            st.pyplot(fig_cadena, use_container_width=True)
            plt.close(fig_cadena)

            st.caption(
                "El histograma de la permutada es IDÉNTICO al del original: "
                "permutar mueve píxeles, no cambia sus valores. Solo se aplana "
                "tras la difusión. Ninguna de las dos etapas basta sola."
            )

        # --- Verificacion del round-trip ----------------------------------
        exacto = bool(np.array_equal(recuperada, imagen_caos))
        if clave_equivocada:
            npcr_ruido = (
                100.0
                * float(np.count_nonzero(recuperada != imagen_caos))
                / imagen_caos.size
            )
            st.error(
                f"**Con la clave equivocada no se recupera nada.** El resultado "
                f"difiere del original en el {npcr_ruido:.2f} % de los píxeles "
                f"(el valor esperado entre dos imágenes independientes es "
                f"99.6094 %). Una diferencia de 1e-15 en x₀ basta: es el "
                f"exponente de Lyapunov amplificándola como e^(λn) durante las "
                f"mil iteraciones del transitorio."
            )
            st.markdown(
                """
                <div class="qpcs-note">
                    Fíjate en que el módulo <strong>no ha dado ningún error</strong>:
                    ha devuelto ruido tan tranquilo. Un cifrado sin autenticación
                    no puede distinguir «clave equivocada» de «cifrado
                    manipulado», y esa es exactamente la diferencia con AES-GCM
                    que la tabla de abajo hace visible.
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif exacto:
            st.success(
                f"**Descifrado correcto, byte a byte.** El SHA-256 de la imagen "
                f"recuperada coincide con el que viaja en el contenedor "
                f"(`{etapas_caos['hash_plano'][:16]}…`), y el IV de la cadena "
                f"es {etapas_caos['iv']}."
            )
            st.caption(
                "Ese hash del texto plano FILTRA información: permite confirmar "
                "una conjetura sobre la imagen sin descifrarla. Se conserva por "
                "su valor didáctico y está documentado como limitación conocida."
            )
        else:
            st.error(
                "**El round-trip no ha sido exacto.** Esto no debería ocurrir "
                "nunca: es el fallo silencioso y significa que "
                "el determinismo está roto en este entorno."
            )

        # --- Correlacion entre pixeles adyacentes -------------------------
        st.markdown(
            '<div class="qpcs-kicker">Correlación entre píxeles adyacentes</div>',
            unsafe_allow_html=True,
        )
        col_disp, col_texto = st.columns([3, 2], gap="large")
        with col_disp:
            with st.container(border=True):
                fig_corr, ejes_corr = plt.subplots(
                    1, 2, figsize=(7.6, 3.9), sharex=True, sharey=True
                )
                fig_corr.patch.set_facecolor("#ffffff")
                for ax_corr, (etiqueta, datos, color) in zip(
                    ejes_corr,
                    (
                        ("original", imagen_caos, COLOR_NAVY),
                        ("cifrada", etapas_caos["cifrada"], COLOR_TEAL),
                    ),
                    strict=True,
                ):
                    x_pares = datos[:, :-1].ravel()
                    y_pares = datos[:, 1:].ravel()
                    paso_pares = max(1, x_pares.size // PARES_CORRELACION)
                    ax_corr.plot(
                        x_pares[::paso_pares],
                        y_pares[::paso_pares],
                        ".",
                        ms=1.5,
                        alpha=0.35,
                        color=color,
                    )
                    _preparar_ejes(ax_corr)
                    ax_corr.set_xlim(0, 255)
                    ax_corr.set_ylim(0, 255)
                    ax_corr.set_xlabel(f"píxel (i, j) · {etiqueta}")
                ejes_corr[0].set_ylabel("píxel adyacente (i, j+1)")
                fig_corr.tight_layout()
                st.pyplot(fig_corr, use_container_width=True)
                plt.close(fig_corr)

        with col_texto:
            with st.container(border=True):
                st.subheader("Qué se está viendo")
                r_original = correlacion_adyacente(imagen_caos, "horizontal")
                r_cifrada = correlacion_adyacente(etapas_caos["cifrada"], "horizontal")
                st.metric(
                    "Correlación horizontal",
                    f"{r_cifrada:+.4f}",
                    f"antes de cifrar: {r_original:+.4f}",
                    delta_color="off",
                )
                st.markdown(f"""
                    En una imagen natural cada píxel se parece muchísimo a su
                    vecino y los puntos se agolpan sobre la diagonal. En la
                    cifrada llenan el cuadrado.

                    La tolerancia no es un 0.05 redondo: para *n* pares
                    independientes el coeficiente muestral se distribuye como
                    N(0, 1/√n), así que con {_entero_es(PARES_CORRELACION)} pares
                    σ = {1 / np.sqrt(PARES_CORRELACION):.4f} y el umbral de 4σ es
                    **{4 / np.sqrt(PARES_CORRELACION):.4f}**.
                    """)

        # --- La tabla de las tres columnas --------------------------------
        st.markdown(
            '<div class="qpcs-kicker">Las tres columnas, sobre esta misma imagen</div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            st.dataframe(
                _tabla_tres_columnas(
                    imagen_caos, sistema_caos, x0_caos, r_caos, y0_caos, z0_caos
                ),
                use_container_width=True,
            )
            st.caption(
                "Medido en vivo sobre la imagen que estás viendo, con las mismas "
                "funciones para las tres columnas. NPCR y UACI se miden entre dos "
                "cifrados independientes (dos claves separadas por 1e-15, dos "
                "nonces de AES, dos claves del contador): es la única lectura en "
                "la que los tres esquemas son comparables."
            )

        st.info(
            "**Lo que se deduce de que las tres columnas salgan iguales, y es la "
            "lección del módulo.** Las métricas estándar del cifrado caótico son "
            "condiciones **necesarias, no suficientes**. Detectan defectos "
            "groseros —un histograma sesgado, una permutación que no permuta, una "
            "difusión que no propaga— y nada más. Que un esquema las pase "
            "significa que no tiene errores obvios, no que sea seguro. El "
            "contador trivial es `SHA256(clave ‖ contador)` usado como flujo, una "
            "construcción que nadie defendería como cifrado serio, y las pasa "
            "igual de bien. La seguridad de AES no viene de aprobar estos tests: "
            "viene de veinticinco años de criptoanálisis público, de un proceso "
            "de estandarización abierto y de argumentos de resistencia frente a "
            "familias de ataque conocidas. Nuestro esquema no tiene nada de eso."
        )

        with st.expander("Limitaciones conocidas de este módulo"):
            st.markdown("""
- **Sin seguridad demostrable.** No hay reducción a un problema duro ni prueba
  en el modelo del oráculo aleatorio. Ninguna.
- **Sin autenticación.** No hay MAC ni etiqueta: descifrar con la clave
  equivocada devuelve ruido, nunca un error. Pruébalo con el interruptor.
- **Determinista y sin nonce.** Cifrar dos veces la misma imagen con la misma
  clave da exactamente el mismo resultado, y reutilizar la clave con dos
  imágenes es tan catastrófico como reutilizar un one-time pad.
- **NPCR y UACI frente a un cambio del *texto plano* no alcanzan sus valores
  ideales, y no pueden.** Con la difusión XOR encadenada el esquema es afín
  sobre GF(2): un cambio de un bit se propaga como una diferencia *constante*,
  toda diferencia de intensidad vale 1 y eso deja UACI por debajo de 0.392 %.
  Los valores de la tabla son los de **sensibilidad a la clave**, que sí los
  alcanzan, y están etiquetados como lo que son.
- **`hash_plano` filtra información.** Viaja junto al cifrado y permite
  confirmar una conjetura sobre la imagen sin descifrarla.
- **Ciclos de precisión finita.** Cualquier órbita en float64 es periódica; si
  cicla antes de agotar la imagen, el keystream se repite. El módulo lo mide y
  avisa por registro.
- **Ataques conocidos contra esta familia**, documentados y no implementados:
  texto plano elegido, reutilización de clave, recuperación del estado y
  degradación por precisión finita.
- **Alcance.** Escala de grises de 8 bits. Sin color, vídeo ni audio; sin
  gestión de claves; sin compresión; sin GPU.
""")

# ===========================================================================
# PESTANA 4 - Modulo 4: ruido de detectores y extraccion de entropia
# (tarea 4.9). Mismo patron que las pestanas 2 y 3: reutiliza styles.css,
# _cabecera_seccion y _preparar_ejes.
# ===========================================================================

with tab_detector:
    _cabecera_seccion(
        "Módulo 04 · Ruido de detectores",
        "Ruido de detectores y extracción de entropía",
        "Se extrae min-entropía de ruido físico real de un detector de "
        "CMS (CERN Open Data), y se destila con el mismo extractor de "
        "Toeplitz que la tarea 1.6 usa para BB84.",
    )

    st.markdown(
        """
        <div class="qpcs-note">
            <strong>No es un generador de números aleatorios certificado.</strong>
            No hay tests de salud en tiempo real de la fuente ni modelo de
            atacante: es una demostración de la cadena completa de
            extracción de entropía sobre ruido físico real, con la
            min-entropía estimada según los estimadores de NIST SP 800-90B.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_control, col_resultado = st.columns([2, 3], gap="large")

    with col_control:
        with st.container(border=True):
            st.subheader("Señal")
            st.caption(
                "nPFCands (candidatos de Particle Flow) de un evento "
                "ZeroBias de CMS. Es un PROXY de ruido, no una lectura "
                "directa de ADC: ver data/FUENTE.md."
            )
            muestras_pct = st.slider(
                "Cuántas muestras usar (%)",
                min_value=10,
                max_value=100,
                value=100,
                step=10,
                help=(
                    "El subconjunto versionado tiene ~495.000 muestras. "
                    "Menos muestras: análisis más rápido, menos resolución "
                    "en el espectro (K de Welch más pequeño)."
                ),
            )
            aplicar_filtro = st.checkbox(
                "Aplicar filtrado (notch + paso alto)",
                value=True,
                help=(
                    "Sin filtrar, los picos de interferencia inflan "
                    "artificialmente la min-entropía estimada, porque su "
                    "componente determinista se confunde con variación real."
                ),
            )
            bits_bajos_ui = st.slider(
                "Bits bajos conservados al digitalizar",
                min_value=1,
                max_value=8,
                value=BITS_BAJOS,
                help=(
                    "Los bits de orden ALTO llevan el sesgo de la "
                    "distribución de la fuente; los de orden BAJO son, a "
                    "efectos prácticos, uniformes (misma idea que la "
                    "cuantización del módulo 3)."
                ),
            )

    @st.cache_data(show_spinner="Calculando el espectro y la entropía...")
    def _analisis_detector_cacheado(
        muestras_pct: int, aplicar_filtro: bool, bits_bajos: int
    ) -> tuple[
        int,
        float,
        np.ndarray,
        np.ndarray,
        int,
        tuple[float, ...],
        tuple[float, float],
        float,
        float,
        float,
        float,
        EstimacionEntropia,
        ResultadoExtraccion,
    ]:
        """Toda la cadena del modulo, cacheada: un Welch sobre cientos
        de miles de muestras no es instantaneo, y sin cache cada
        movimiento de un control la relanzaria entera.

        Devuelve una TUPLA de tipos simples, no AnalisisDetector: un
        dataclass definido en este mismo script se redefine en cada
        rerun de Streamlit (exec() del propio script), asi que pickle
        lo rechaza con "it's not the same object as
        __main__.AnalisisDetector" aunque el nombre y los campos
        coincidan. EstimacionEntropia y ResultadoExtraccion SI vienen
        de un modulo importado normal (detector), que no se redefine,
        asi que esos dos si se pueden devolver tal cual.
        """
        senal_completa, fs = cargar_muestra()
        n = max(1000, int(len(senal_completa) * muestras_pct / 100))
        senal = senal_completa[:n]

        freqs, psd, k_tramos = densidad_espectral(senal, fs, NPERSEG)
        picos = detectar_picos(freqs, psd, UMBRAL_PICO)
        rango_hz = rango_alfa_en_hz(RANGO_ALFA, fs)
        alfa, alfa_error = ajustar_alfa(freqs, psd, rango_hz)
        fano = factor_fano(senal)
        suelo_blanco = float(np.median(psd[len(psd) // 2 :]))

        if aplicar_filtro:
            senal_para_digitalizar = filtrar(senal, fs, picos)
        else:
            senal_para_digitalizar = senal.astype(np.float64)

        simbolos = digitalizar(senal_para_digitalizar, bits_bajos)
        estimacion = estimar_entropia(simbolos)
        resultado = extraer(simbolos, estimacion, EPSILON_PA)

        return (
            n,
            fs,
            freqs,
            psd,
            k_tramos,
            picos,
            rango_hz,
            alfa,
            alfa_error,
            fano,
            suelo_blanco,
            estimacion,
            resultado,
        )

    _resultado_cacheado = _analisis_detector_cacheado(
        muestras_pct, aplicar_filtro, bits_bajos_ui
    )
    analisis = AnalisisDetector(
        n=_resultado_cacheado[0],
        fs=_resultado_cacheado[1],
        frecuencias=_resultado_cacheado[2],
        psd=_resultado_cacheado[3],
        k_tramos=_resultado_cacheado[4],
        picos=_resultado_cacheado[5],
        rango_hz=_resultado_cacheado[6],
        alfa=_resultado_cacheado[7],
        alfa_error=_resultado_cacheado[8],
        fano=_resultado_cacheado[9],
        suelo_blanco=_resultado_cacheado[10],
        estimacion=_resultado_cacheado[11],
        resultado=_resultado_cacheado[12],
        bits_bajos=bits_bajos_ui,
    )

    with col_resultado:
        with st.container(border=True):
            st.subheader("Espectro de potencia (Welch)")
            fig_espectro, ax_espectro = plt.subplots(figsize=(7.2, 4.2))
            mascara_valida = (analisis.frecuencias > 0) & (analisis.psd > 0)
            ax_espectro.loglog(
                analisis.frecuencias[mascara_valida],
                analisis.psd[mascara_valida],
                lw=1.0,
                color=COLOR_TINTA,
            )
            f_min, f_max = analisis.rango_hz
            if analisis.alfa != 0.0:
                mascara_ajuste = (
                    (analisis.frecuencias >= f_min)
                    & (analisis.frecuencias <= f_max)
                    & mascara_valida
                )
                if mascara_ajuste.any():
                    idx_ref = len(analisis.frecuencias[mascara_ajuste]) // 2
                    f_ref = analisis.frecuencias[mascara_ajuste][idx_ref]
                    a_const = (
                        analisis.psd[mascara_ajuste][idx_ref] * f_ref**analisis.alfa
                    )
                    f_recta = np.array([f_min, f_max])
                    ax_espectro.loglog(
                        f_recta,
                        a_const / f_recta**analisis.alfa,
                        "--",
                        lw=1.6,
                        color=COLOR_TEAL,
                    )
            for pico in analisis.picos:
                ax_espectro.axvline(pico, ls="-", lw=0.9, color=COLOR_ERROR, alpha=0.5)
            ax_espectro.set_xlabel("frecuencia (Hz)")
            ax_espectro.set_ylabel("densidad espectral")
            # El formateador logaritmico por defecto de matplotlib genera
            # etiquetas MathText ($10^{...}$), y la cache de mathtext no
            # es segura entre los hilos de sesiones concurrentes de
            # Streamlit (el mismo fallo que la Fase 2 documento con el
            # benchmark en escala logaritmica). Se
            # sustituye por texto plano con FuncFormatter.
            formateador_log = FuncFormatter(
                lambda valor, _pos: (f"{valor:g}" if valor != 0 else "0")
            )
            ax_espectro.xaxis.set_major_formatter(formateador_log)
            ax_espectro.yaxis.set_major_formatter(formateador_log)
            # Sustituir SOLO el formateador principal no basta: un eje log
            # tambien genera ticks MENORES con su propio formateador por
            # defecto (tambien generador de MathText), y como el bug es
            # una condicion de carrera entre hilos de Streamlit, a veces
            # no llega a dispararse y a veces si (visto en produccion:
            # una recarga funciono, la siguiente crasheo en exactamente
            # este punto). minorticks_off() quita el origen del problema
            # en vez de parchear un formateador mas.
            ax_espectro.minorticks_off()
            _preparar_ejes(ax_espectro)
            fig_espectro.tight_layout()
            st.pyplot(fig_espectro)
            plt.close(fig_espectro)

            picos_texto = (
                ", ".join(f"{p:.3g} Hz" for p in analisis.picos)
                if analisis.picos
                else "sin picos detectados"
            )
            st.caption(
                f"α = {analisis.alfa:.4f} ± {analisis.alfa_error:.4f}  ·  "
                f"Fano = {analisis.fano:.2f}  ·  "
                f"K = {analisis.k_tramos} tramos  ·  picos: {picos_texto}"
            )

    # -----------------------------------------------------------------------
    # Los estimadores y el embudo, uno al lado del otro y a la misma altura.
    # Antes iban apilados dentro de la columna derecha, debajo del espectro:
    # la pagina se hacia larguisima y quedaban dos quintos de ancho sin usar.
    # -----------------------------------------------------------------------

    col_estimadores, col_embudo = st.columns(2, gap="large")

    with col_estimadores:
        with st.container(border=True):
            st.subheader("Estimadores de min-entropía")
            est = analisis.estimacion
            filas_estimadores = [
                ("Valor más común", est.h_mas_comun),
                ("Colisión", est.h_colision),
                ("Markov", est.h_markov),
            ]
            df_estimadores = pd.DataFrame(
                filas_estimadores, columns=["Estimador", "bits/símbolo"]
            )
            df_estimadores["Es el mínimo"] = df_estimadores["bits/símbolo"].apply(
                lambda v: "← se usa este" if abs(v - est.h_min) < 1e-9 else ""
            )
            st.dataframe(
                df_estimadores.style.format({"bits/símbolo": "{:.4f}"}),
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                "Se toma el MÍNIMO de los tres (regla de NIST SP 800-90B): "
                "cada estimador es ciego a cierto tipo de estructura, y el "
                "que da el valor más bajo es el que encontró la que los "
                f"demás no vieron. Mínimo usado: {est.h_min:.4f} bits/símbolo."
            )

    with col_embudo:
        with st.container(border=True):
            st.subheader("Del ruido a los bits")
            bits_conservados = analisis.n * analisis.bits_bajos
            bits_min_entropia = analisis.n * est.h_min
            bits_extraidos = analisis.resultado.longitud_segura
            peaje = bits_min_entropia - bits_extraidos

            fig_embudo, ax_embudo = plt.subplots(figsize=(7.2, 3.4))
            etapas_ui = [
                ("muestras", float(analisis.n), COLOR_MUTED),
                (
                    f"bits (×{analisis.bits_bajos})",
                    float(bits_conservados),
                    COLOR_TINTA,
                ),
                ("min-entropía", bits_min_entropia, COLOR_TEAL),
                ("extraídos", float(bits_extraidos), COLOR_ERROR),
            ]
            y_pos = list(range(len(etapas_ui)))[::-1]
            for (_etiqueta, valor, color), y in zip(etapas_ui, y_pos, strict=True):
                ax_embudo.barh(y, valor, height=0.55, color=color, alpha=0.85)
            ax_embudo.set_xscale("log")
            ax_embudo.set_yticks(y_pos)
            ax_embudo.set_yticklabels([e[0] for e in etapas_ui], fontsize=9)
            ax_embudo.set_xlabel("cantidad (escala logarítmica)")
            ax_embudo.xaxis.set_major_formatter(formateador_log)
            ax_embudo.minorticks_off()
            _preparar_ejes(ax_embudo)
            fig_embudo.tight_layout()
            st.pyplot(fig_embudo, use_container_width=True)
            plt.close(fig_embudo)

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Bits de min-entropía", _entero_es(int(bits_min_entropia)))
            col_b.metric("Bits extraídos", _entero_es(bits_extraidos))
            col_c.metric("Peaje (leftover hash lemma)", f"−{peaje:.0f} bits")

    # -----------------------------------------------------------------------
    # Los bits, a lo ancho y enteros.
    # -----------------------------------------------------------------------

    with st.container(border=True):
        st.subheader("Bits extraídos")
        bits_bytes = np.packbits(analisis.resultado.bits).tobytes()

        if not bits_bytes:
            st.info(
                "No hay bits que enseñar: con los parámetros actuales la fuente "
                "no tiene min-entropía suficiente para extraer nada."
            )
        else:
            st.markdown(f"""
Estos {_entero_es(len(analisis.resultado.bits))} bits salen del ruido de un
detector de verdad. La señal es el número de candidatos de *Particle Flow* por
evento de una toma **ZeroBias** del experimento **CMS**, publicada en abierto
por el CERN: [registro 31316 de CERN Open
Data](https://opendata.cern.ch/record/31316), con licencia CC0. La procedencia
completa —la URI exacta del fichero, el script que extrajo la muestra y las
cuatro colecciones que se probaron antes y no sirvieron— está en
[`data/FUENTE.md`](https://github.com/cmartinezmeco/qpcs/blob/main/data/FUENTE.md).
""")
            st.caption(
                f"z (monobit) = {analisis.resultado.z_monobit:.4f}  ·  "
                f"χ² = {analisis.resultado.chi2:.2f}  ·  "
                f"{_entero_es(len(bits_bytes))} bytes. "
                "El CONTENIDO no es reproducible entre ejecuciones: la semilla "
                "de Toeplitz sale de os.urandom, nunca sembrada."
            )

            # En pantalla, UNA linea y nada mas. Son cuatrocientos y pico mil
            # digitos: ensenarlos todos no informa de nada que no diga ya la
            # cifra de al lado, y en cambio alarga la pagina sin fin y obliga
            # al navegador a pintar miles de renglones en cada recalculo.
            #
            # Se manda al HTML un trozo holgado y el recorte lo hace la hoja
            # de estilo (.qpcs-hex, con text-overflow), no Python: asi la
            # linea llena el ancho que haya -pantalla grande o movil- y acaba
            # siempre en puntos suspensivos justo donde toca.
            hex_completo = bits_bytes.hex()
            st.markdown(
                f'<div class="qpcs-hex">{hex_completo[:VISTA_HEX]}</div>',
                unsafe_allow_html=True,
            )

            # Y quien los quiera de verdad, que se los lleve. El fichero va en
            # renglones de 64 digitos, como cualquier volcado hexadecimal: se
            # abre en cualquier editor sin ahogarlo con una linea de medio
            # mega, y los saltos no estorban a nadie que vaya a parsearlo
            # (bytes.fromhex de Python, xxd -r -p y compania se saltan los
            # blancos). El nombre lleva el numero de bits porque el contenido
            # cambia en cada ejecucion: dos descargas no son el mismo fichero.
            hex_en_lineas = "\n".join(
                hex_completo[i : i + ANCHO_HEX]
                for i in range(0, len(hex_completo), ANCHO_HEX)
            )
            n_bits = len(analisis.resultado.bits)
            st.download_button(
                label=f"Descargar los {_entero_es(len(hex_completo))} dígitos (.txt)",
                data=hex_en_lineas,
                file_name=f"qpcs-bits-extraidos-{n_bits}.txt",
                mime="text/plain",
                help=(
                    "El volcado completo en hexadecimal, en renglones de 64 "
                    "dígitos. Son "
                    f"{_entero_es(len(bits_bytes))} bytes de entropía destilada."
                ),
            )
