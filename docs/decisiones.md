# Decisiones abiertas de QPCS

Las decisiones que el proyecto dejó **declaradas pero sin cerrar** al llegar a la
Fase 4, con sus opciones, su recomendación razonada y su estado. Una decisión que
se queda sin tomar no desaparece: reaparece en cada revisión y nadie sabe si es
un descuido o una postura.

> Tarea 4.13 de la Fase 4. Entregable: este fichero.
> Las limitaciones ya asumidas y cerradas están en
> [`limitaciones.md`](limitaciones.md); este documento es solo lo que **sigue
> abierto**.

## Cómo se lee una entrada

Cada decisión lleva el mismo bloque al final:

```
ESTADO      : PENDIENTE DE REUNIÓN | CERRADA
FECHA       : la del acuerdo, no la de la redacción
ACORDADO POR: quién estuvo
```

Mientras `ESTADO` diga `PENDIENTE DE REUNIÓN`, la recomendación escrita aquí es
**una propuesta**, no un acuerdo. Está redactada para que la reunión parta de
algún sitio en vez de empezar en blanco, que es como se toman las decisiones
malas y lentas.

Las tres decisiones de esta tarea son **A1**, **A2** y **A3**. Hay además dos
decisiones más que llegan con tareas posteriores del bloque B y que se anotarán
aquí cuando toque; están listadas al final para que no se pierdan.

---

## A1 — NPCR y UACI frente al texto plano

**De dónde viene.** Hallazgo de la Fase 3, declarado en su momento como decisión
de grupo y nunca cerrado.

### El hecho, medido

Con la difusión encadenada por XOR que especifica el Módulo 3, el esquema entero
es afín sobre GF(2). Un cambio de un bit en el texto **plano** se propaga como un
delta XOR **constante**, así que toda diferencia de intensidad vale exactamente 1.
Consecuencias, las dos derivadas y aseveradas contra la implementación:

| Métrica | Valor canónico del campo | Lo que este esquema puede dar |
|---|---:|---|
| UACI (cambio en el plano) | 33,4635 % | **acotada en 0,392 %** |
| NPCR (cambio en el plano) | 99,6094 % | de 0 % a 100 %, ≈50 % de media |

Está fijado por `test_avalancha_ante_un_cambio_en_el_plano` y
`test_uaci_diferencial_esta_acotada_por_la_linealidad_del_XOR`
([`tests/chaos/test_cipher.py`](../tests/chaos/test_cipher.py)). La tabla que el
proyecto publica mide NPCR y UACI entre **dos criptogramas independientes**, que
es la única lectura bajo la cual los tres esquemas del banco son comparables.

Detalle completo en [`limitaciones.md` § M3.7](limitaciones.md).

### Las opciones

| Opción | Qué implica |
|---|---|
| **1. Dejarlo y documentarlo** | Cero riesgo técnico. El README y `limitaciones.md` explican la diferencia con la literatura y **por qué** las métricas dan lo que dan. El trabajo de documentación ya está hecho. |
| **2. Cambiar la difusión** | Mezclar **dos operaciones de grupo distintas** (suma modular y XOR). Las métricas alcanzarían los valores canónicos, pero es tocar el núcleo de un módulo cerrado, invalida el vector de prueba [`vectors/keystream_v1.json`](../vectors/keystream_v1.json) y obliga a volver a medirlo todo: tabla, figuras y MD5 en CI. |

### Recomendación

**Opción 1: dejarlo y documentarlo**, salvo argumento fuerte en contra.

Tres razones, en orden de peso:

1. El módulo está verificado y el cambio **invalidaría el vector de prueba**, que
   es precisamente la defensa contra el fallo silencioso de determinismo. Se
   perdería una garantía real a cambio de dos cifras más bonitas.
2. La Regla 3 del plan de proyecto dice que no se reabren módulos cerrados en la
   fase de pulido.
3. El motivo de fondo: un repositorio que **explica** por qué sus métricas
   difieren de las de la literatura demuestra más criterio que uno que las hace
   coincidir sin explicar nada. Y el Módulo 3 existe justamente para enseñar que
   esas métricas no prueban seguridad —alcanzar sus valores canónicos sería
   coherente con la literatura que el módulo cuestiona, no con el módulo.

```
ESTADO      : PENDIENTE DE REUNIÓN
FECHA       : ____________
ACORDADO POR: ____________
```

---

## A2 — Los ayudantes privados de `cipher.py`

**De dónde viene.** Deuda declarada en la tarea 3.10, con un test que la vigila.

### El hecho

Tres consumidores de **fuera** del paquete importan ayudantes **privados** de
[`src/chaos/cipher.py`](../src/chaos/cipher.py), los dos por el mismo motivo:
necesitan un estado intermedio que la API pública no devuelve.

| Ayudante | Quién lo usa desde fuera | Para qué |
|---|---|---|
| `_valores_de_permutacion` | el test de la avalancha, la figura 2 y la pestaña 3 del dashboard | la receta de la órbita que alimenta a σ; la figura enseña la imagen permutada pero **no** difundida |
| `_material` | el banco de medidas | el troceado del *keystream* en `(k_ida, k_vuelta, iv, iv)`, para cronometrar cada etapa por separado |

La alternativa en su día era copiar la receta en cada sitio, y entonces una copia
se separaría de la del cifrado sin que nadie lo notara: eso es peor, porque el
síntoma sería *una figura que miente*, no un error.

La dependencia está **por escrito** y vigilada por
`test_los_ayudantes_privados_que_se_usan_fuera_siguen_existiendo`
([`tests/chaos/test_scaffold.py`](../tests/chaos/test_scaffold.py)), que falla el
día que alguien los renombre. Ese día es exactamente cuando hay que tomar esta
decisión — y por eso conviene tomarla antes.

### Las opciones

| Opción | Qué implica |
|---|---|
| **1. Promocionarlos a públicos** | Añadir los dos nombres a `__all__` en [`src/chaos/__init__.py`](../src/chaos/__init__.py) (sin el guion bajo, o manteniéndolo y documentando la excepción). El contrato pasa a ser explícito y `test_lo_que_consumen_el_dashboard_y_los_scripts_es_publico` los cubre como a los demás. Coste: la API pública crece con dos funciones que exponen estado intermedio. |
| **2. Dejarlo como está** | La deuda sigue declarada, con su motivo escrito y su test vigilándola. Coste: la API pública del módulo no describe del todo lo que el módulo realmente exporta. |

### Recomendación

**Opción 2: dejarlo como está**, con una matización.

El test que lo vigila ya convierte la deuda en algo que no puede romperse en
silencio, que es el criterio con el que este proyecto ha tratado el resto de sus
deudas. Promocionarlos a públicos ampliaría la superficie de API con dos
funciones que devuelven estado interno del cifrado —no son operaciones que un
usuario del módulo quiera— y el guion bajo comunica correctamente que **no** son
para consumo general.

La matización: si en la reunión se prefiere la opción 1, es un cambio de cinco
minutos en un solo fichero. Lo que no puede es quedarse otra fase sin decidir.

```
ESTADO      : PENDIENTE DE REUNIÓN
FECHA       : ____________
ACORDADO POR: ____________
```

---

## A3 — La revisión de reparto

**De dónde viene.** El plan de proyecto pide una revisión de reparto cada tres
semanas. No consta que se haya hecho ninguna.

### La medida

Medido el **2026-09-05** sobre `origin/main` en el commit `9f090ef`
(2026-09-02), 51 *commits* sin contar *merges*, con los comandos que fija la guía:

```bash
git shortlog -sn --no-merges
git log --format='%an' --no-merges -- src/qkd/      | sort | uniq -c | sort -rn
git log --format='%an' --no-merges -- src/pqc/      | sort | uniq -c | sort -rn
git log --format='%an' --no-merges -- src/chaos/    | sort | uniq -c | sort -rn
git log --format='%an' --no-merges -- src/detector/ | sort | uniq -c | sort -rn
```

**Total del repositorio** (`git shortlog -sn --no-merges`), tal cual sale:

| Autor según git | Commits |
|---|---:|
| Carlos Martínez-Meco López | 26 |
| Marcociber | 14 |
| Gonzalo ZG | 8 |
| gonzaloz-hub | 2 |
| Marco López Ballestrino | 1 |

**Por módulo**, *commits* que tocan cada carpeta:

| Carpeta | Carlos | Marco (`Marcociber` + `Marco López Ballestrino`) | Gonzalo (`Gonzalo ZG` + `gonzaloz-hub`) |
|---|---:|---:|---:|
| `src/qkd/` | 2 | 3 | 1 |
| `src/pqc/` | 3 | 1 | 1 |
| `src/chaos/` | 3 | 5 | 1 |
| `src/detector/` | 4 | 3 | 6 |

Consolidando los alias: **Carlos 26, Marco 15, Gonzalo 10**.

### Los dos hallazgos

**1. Cada persona aparece bajo dos identidades de git.** Gonzalo firma como
`Gonzalo ZG` y como `gonzaloz-hub`; Marco, como `Marcociber` y como
`Marco López Ballestrino`. Cualquiera que ejecute `git shortlog` a pelo verá
cinco autores en un equipo de tres, y contará mal.

**2. Hoy no hay ningún reparto escrito contra el que comparar.** La sección
`## 👥 Team` del README lista **roles** (Physics, Cybersecurity, Data
Engineering), no personas ni módulos. Es decir: el criterio de cierre «el reparto
escrito coincide con el `git log`» no está incumplido —está *vacío*. Esta medida
es el **insumo** de la sección de reparto que escribirá la tarea 4.16, no una
comprobación contra algo que ya exista.

### Lo que estos números NO dicen

Hay que decirlo antes de que alguien los use para repartir mérito:

- **Un *commit* no es una unidad de trabajo.** Uno que añade 700 líneas cuenta
  igual que una corrección de formato. En este repositorio hay *commits* de
  ambos tipos y bien visibles en el historial.
- **`git log -- <ruta>` cuenta *commits* que tocan esa ruta**, no autoría de
  líneas. Un arreglo de una línea en el fichero de otro suma igual que escribirlo
  entero.
- **Los *merges* están excluidos**, y con ellos parte de la integración —que es
  trabajo real y recae sobre quien mergea.
- **Hay trabajo que no vive en `src/`**: los tests, las figuras, el dashboard, la
  CI, el Dockerfile y los documentos de teoría. La tabla por módulo no los ve, y
  son una fracción grande del proyecto.

### Las opciones

| Opción | Qué implica |
|---|---|
| **1. Escribir el reparto real, con `.mailmap`** | Añadir un fichero `.mailmap` que una los alias de cada persona, y redactar la sección de reparto del README con lo que salga después de unirlos, describiendo **qué hizo cada uno** (módulos y tareas) y no solo cuántos *commits* tiene. |
| **2. Escribir el reparto real sin tocar los alias** | Misma sección de reparto, pero quien ejecute `git shortlog` seguirá viendo cinco autores y tendrá que consolidarlos a mano. |
| **3. Escribir el reparto planeado** | Lo que decían las guías de fase. **Descartada**: el plan de proyecto es explícito —«si Gonzalo acabó escribiendo Cascade, hay que decirlo y ajustar, **no fingir**»— y la *checklist* de la Fase 1 añade que «si no coincide, se corrige el README, no el `git log`». |

### Recomendación

**Opción 1: escribir el reparto real, con `.mailmap`.**

El `.mailmap` cuesta cuatro líneas y hace que la comprobación del criterio de
cierre sea ejecutable por cualquiera sin explicaciones: `git shortlog -sn` pasa a
devolver tres nombres, que es el número de personas que hay. Sin él, el criterio
«el reparto coincide con el `git log`» exige que quien lo comprueba sepa de
antemano que dos de los cinco autores son la misma persona dos veces, y eso es
justo lo que un revisor externo no sabe.

Y sobre el contenido: la sección de reparto debe describir **trabajo**, no contar
*commits*, por todo lo del apartado anterior. Los números de arriba sirven para
detectar una divergencia grande entre lo planeado y lo real —y para el Módulo 4
la hay que merece una frase: `src/detector/` es la carpeta donde Gonzalo tiene más
*commits* (6) pese a que la mitad de entropía era de Marco, porque las tareas 4.3
a 4.5 son suyas y son tres de las siete tareas de código del módulo.

**Lo que hay que hacer con esto, en orden:**

1. Cerrar esta decisión en la reunión del bloque B.
2. Si sale la opción 1, crear `.mailmap` en la raíz.
3. La tarea **4.16** escribe la sección de reparto del README a partir de esta
   medida, y vuelve a ejecutar `git shortlog -sn --no-merges` en ese momento —el
   historial habrá crecido con el propio bloque B, así que esta tabla es una
   foto del 2026-09-05, no la definitiva.

```
ESTADO      : PENDIENTE DE REUNIÓN
FECHA       : ____________
ACORDADO POR: ____________
```

---

## B1 — Publicar la imagen en GitHub Container Registry

**De donde viene.** Declarada en la guia de la Fase 4 (cap. 7.5, tarea 4.15):
si el arranque compila liboqs cada vez, la primera experiencia de un revisor
son varios minutos de `docker build` antes de ver nada.

### El hecho, medido (no supuesto)

En esta misma tarea se cronometraron dos builds reales, en la misma maquina:

| Build | Tiempo | Contexto |
|---|---|---|
| Con cache de Buildx (CI, PR #48) | ~15 min la primera vez que se activo la cache; bajara en ejecuciones siguientes | Runner de GitHub Actions |
| Sin cache (`--no-cache`, local) | ~17 min (197s el `git clone` + compilacion de liboqs, ~756s instalando requirements, resto en exportar capas) | Maquina de Carlos, WSL2 |
| `docker pull` de una imagen ya publicada | Segundos (no medido aqui: no hay imagen publicada todavia) | — |

El numero que importa para la decision no es el de la CI (esa cache ya esta
resuelta, tarea 4.14): es el de alguien que clona el repo por primera vez y
sigue el Quick Start del README. Hoy son minutos de compilacion antes de ver
el dashboard.

### Opciones

| Opcion | Que gana | Que cuesta |
|---|---|---|
| **1. Publicar en GHCR** (`ghcr.io/cmartinezmeco/qpcs`) | El Quick Start pasa de `docker build` (~10-17 min) a `docker pull` (segundos). Primera impresion mucho mejor para un revisor. | Hay que mantener la imagen al dia: un paso de CI que la reconstruya y la suba en cada push a `main`, y decidir el etiquetado (`latest`, por commit, por version). Exige que el repositorio sea publico (GHCR gratuito solo lo es para repos publicos) -ver B2-. |
| **2. Dejarlo como esta** (`docker build` local, con la cache de Buildx de la tarea 4.14 acelerando reconstrucciones sucesivas) | Cero mantenimiento extra. Ninguna dependencia de que el repo sea publico. | El primer build de cualquiera sigue tardando minutos. La cache de Buildx solo ayuda en la CI (GitHub Actions), no en la maquina de quien clona el repo por primera vez. |

### Recomendacion

**Publicar en GHCR (opcion 1), pero solo cuando B2 (repositorio publico) este
decidido primero** -B1 no se puede cerrar en el vacio, depende de esa otra
decision-. Si el repositorio se queda privado, la opcion 2 es la unica viable
y esta decision se cierra sola por descarte.

Coste de mantenimiento estimado: un job de CI adicional (`push` a `main` ->
`docker build` + `docker push` a GHCR), unas 15-20 lineas de YAML siguiendo el
mismo patron que `build-limpio` de la tarea 4.14.

**Lo que hay que hacer con esto, en orden:**

1. Cerrar primero B2 (repositorio publico) en la reunion del bloque B.
2. Si B2 sale que si: implementar el job de publicacion en GHCR (encaja en
   `ci/cache-y-endurecimiento` o en una tarea propia; se decide en la reunion),
   y cambiar el paso 3 del Quick Start del README de `docker build` a
   `docker pull ghcr.io/cmartinezmeco/qpcs`.
3. Si B2 sale que no: esta decision se cierra como "opcion 2, por descarte",
   sin trabajo adicional.

```
ESTADO      : PENDIENTE DE REUNIÓN
FECHA       : ____________
ACORDADO POR: ____________
```

---

## Decisiones que llegan con tareas posteriores

No se deciden aquí, pero se anotan para que no se pierdan entre tareas. Cuando se
tomen, su entrada se añade a este mismo fichero con el mismo bloque de estado.

| Ref. | Decisión | Tarea que la cierra |
|---|---|---|
| **B2** | **Si el repositorio va a ser público.** Condiciona a B1 (arriba, ya con opciones preparadas) y a la licencia. | 4.15 / 4.17 |
| **B3** | **Qué licencia** (MIT, Apache 2.0 o GPL-3.0), y comprobar —no suponer— que ninguna licencia de las dependencias (`liboqs`, Qiskit, `cryptography`, NumPy, SciPy, `uproot`, Streamlit) es incompatible con la elegida. | 4.17 |

---

## Registro

| Fecha | Qué cambió |
|---|---|
| 2026-09-05 | Fichero creado con A1, A2 y A3 redactadas y la medida de reparto tomada sobre `9f090ef`. Las tres quedan pendientes de la reunión del bloque B. |
