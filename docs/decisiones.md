# Decisiones del proyecto QPCS

Las decisiones que el proyecto dejó **declaradas pero sin cerrar** al llegar a la
Fase 4, con sus opciones, su recomendación razonada y lo que finalmente se
acordó. Una decisión que se queda sin tomar no desaparece: reaparece en cada
revisión y nadie sabe si es un descuido o una postura.

> Tarea 4.13 de la Fase 4. Entregable: este fichero.
> Las limitaciones ya asumidas y cerradas están en
> [`limitaciones.md`](limitaciones.md); este documento es el de las decisiones.

## Cómo se lee una entrada

Cada decisión lleva el mismo bloque al final:

```
ESTADO      : PENDIENTE DE REUNIÓN | CERRADA
FECHA       : la del acuerdo, no la de la redacción
ACORDADO POR: quién estuvo
```

Mientras `ESTADO` no diga `CERRADA`, la recomendación escrita aquí es **una
propuesta**, no un acuerdo. Está redactada para que la reunión parta de algún
sitio en vez de empezar en blanco, que es como se toman las decisiones malas y
lentas. Cuando se cierra, la entrada conserva la recomendación original y añade
un apartado **Lo acordado**: importa tanto lo que se decidió como si coincidió o
no con lo que se proponía.

Son ocho decisiones: **A1**, **A2** y **A3**, que venían de esta tarea; **B1**,
**B2** y **B3**, que llegaron con el bloque B; **C**, sobre los correos del
historial, y **D**, sobre dos dependencias con avisos de seguridad conocidos,
que aparecieron las dos en la auditoría previa a la publicación.

**Estado a 13 de septiembre de 2026: las ocho están cerradas.** No queda
ninguna casilla abierta, que era la condición para poder publicar el
repositorio sin contradecir su propio proceso.

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

### Lo acordado

**Opción 1: se deja como está y se documenta.** No se toca el Módulo 3.

No hay trabajo detrás de esta decisión, y ese es justamente el punto: la
explicación de por qué las métricas dan lo que dan ya está escrita en el README,
en `docs/limitaciones.md` y en el propio panel, y los dos tests que fijan el
comportamiento siguen donde estaban. Lo único que cambia es que deja de ser una
deuda abierta.

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Gonzalo, Marco, Carlos
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

### Lo acordado

**Opción 2: se quedan privados.** `_valores_de_permutacion` y `_material` siguen
con su guion bajo y sin exportarse en `__init__.py`.

El razonamiento que se impuso en la reunión es el de arriba: la API pública de un
módulo debe contener lo que necesita un *usuario* del módulo, no lo que necesitan
sus propias figuras y sus *benchmarks*. Esos tres consumidores son código del
mismo proyecto, no terceros, y promocionarlos convertiría un detalle interno en un
compromiso de estabilidad hacia fuera a cambio de nada. El test que vigila que no
desaparezcan cubre el riesgo real, que es que alguien los renombre sin enterarse.

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Gonzalo, Marco, Carlos
```

---

## A3 — La revisión de reparto

**De dónde viene.** El plan de proyecto pide una revisión de reparto cada tres
semanas. No consta que se haya hecho ninguna.

### La medida

Medido el **2026-09-05** sobre `origin/main` en el commit `9f090ef`
(2026-09-02), 51 *commits* sin contar *merges*, con estos comandos:

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
| **3. Escribir el reparto planeado** | Lo que estaba previsto al repartir las tareas, en vez de lo que acabó pasando. **Descartada**: el plan de proyecto es explícito —«si Gonzalo acabó escribiendo Cascade, hay que decirlo y ajustar, **no fingir**»— y la *checklist* de la Fase 1 añade que «si no coincide, se corrige el README, no el `git log`». |

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

### Lo acordado

**Opción 1: `.mailmap` y reparto por trabajo.** Con un matiz sobre los nombres.

1. Se crea `.mailmap` en la raíz. Une las **seis** identidades de git que
   aparecen en el historial —eran cinco cuando se escribió esta entrada; el
   propio trabajo de las últimas semanas añadió una más— en las tres personas
   que somos. `git shortlog -sn --no-merges` pasa a devolver tres nombres.
2. El nombre canónico de cada uno es su **alias de GitHub**: `cmartinezmeco`,
   `Marcociber` y `gonzaloz-hub`. Así lo que dice `git log` y lo que dice la web
   coinciden, que es lo que mira quien llega de fuera.
3. La tabla de *commits* del README **desaparece**, y solo se queda la columna de
   responsabilidad. El motivo, además del de arriba: la tabla ya estaba desfasada
   —publicaba 31 para Carlos cuando el método que ella misma describe daba 35— y
   cualquier tabla de *commits* queda obsoleta con el *commit* siguiente, incluido
   el que la corrija. Quien quiera los números tiene el comando en el README.

Conviene dejar dicho, porque es el error fácil: el `.mailmap` cambia lo que
**muestran** `git log`, `git shortlog` y `git blame`, pero no reescribe los
objetos de *commit*. Los correos siguen dentro del historial. Eso es otra
decisión, y está más abajo.

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Gonzalo, Marco, Carlos
```

---

## B1 — Publicar la imagen en GitHub Container Registry

**De dónde viene.** De la tarea 4.15: si el arranque compila liboqs cada vez, la primera
experiencia de un revisor son varios minutos de `docker build` antes de ver nada.

### El hecho, medido (no supuesto)

En esta misma tarea se cronometraron dos *builds* reales, en la misma máquina:

| Build | Tiempo | Contexto |
|---|---|---|
| Con caché de Buildx (CI, PR #48) | ~15 min la primera vez que se activó la caché; baja en las siguientes | Runner de GitHub Actions |
| Sin caché (`--no-cache`, local) | ~17 min (197 s el `git clone` + compilación de liboqs, ~756 s instalando requirements, el resto exportando capas) | Máquina de Carlos, WSL2 |
| `docker pull` de una imagen ya publicada | Segundos (no medido aquí: no había imagen publicada todavía) | — |

El número que importa para la decisión no es el de la CI —esa caché ya está resuelta en la
tarea 4.14—, sino el de alguien que clona el repositorio por primera vez y sigue el arranque
rápido del README. Hoy son minutos de compilación antes de ver el panel.

### Opciones

| Opción | Qué gana | Qué cuesta |
|---|---|---|
| **1. Publicar en GHCR** (`ghcr.io/cmartinezmeco/qpcs`) | El arranque rápido pasa de `docker build` (~10–17 min) a `docker pull` (segundos). Primera impresión mucho mejor para un revisor. | Hay que mantener la imagen al día: un paso de CI que la reconstruya y la suba en cada *push* a `main`, y decidir el etiquetado. Exige que el repositorio sea público, porque GHCR solo es gratuito para repositorios públicos —ver B2—. |
| **2. Dejarlo como está** (`docker build` local, con la caché de Buildx de la tarea 4.14 acelerando reconstrucciones sucesivas) | Cero mantenimiento extra. Ninguna dependencia de que el repositorio sea público. | El primer *build* de cualquiera sigue tardando minutos. La caché de Buildx solo ayuda en la CI, no en la máquina de quien clona el repositorio por primera vez. |

### Recomendación

**Publicar en GHCR (opción 1), pero solo cuando B2 esté decidida primero** —B1 no se puede
cerrar en el vacío, depende de esa otra decisión—. Si el repositorio se queda privado, la
opción 2 es la única viable y esta decisión se cierra sola por descarte.

Coste de mantenimiento estimado: un *job* de CI adicional (*push* a `main` → `docker build` +
`docker push` a GHCR), unas 15–20 líneas de YAML siguiendo el mismo patrón que `build-limpio`
de la tarea 4.14.

### Lo acordado

**Opción 1: se publica en GHCR.** B2 salió público, así que la dependencia queda satisfecha.

Lo que se hizo al cerrarla:

1. Un *job* `publicar-imagen` en `.github/workflows/ci.yml` que construye y sube la imagen en
   cada *push* a `main`, solo si el *job* `test` ha pasado. Reutiliza la caché de Buildx del
   *job* anterior, así que publicar cuesta segundos y no otra compilación de liboqs.
2. Dos etiquetas: `:main`, que se mueve y es la que apunta el README, y `:sha-<commit>`, que no
   se mueve nunca y permite reproducir una ejecución concreta meses después.
3. El arranque rápido del README pasa a `docker pull`, con las instrucciones de construir la
   imagen a mano justo debajo para quien quiera probar un cambio propio.

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Gonzalo, Marco, Carlos
```

---

## B3 — Qué licencia

**De dónde viene.** Sin fichero `LICENSE`, por defecto nadie puede usar, copiar ni distribuir
este código, aunque el repositorio sea público. Viene de la tarea 4.17.

### Las licencias de las dependencias, comprobadas (no supuestas)

Verificado con `pip-licenses` sobre el entorno real, más la licencia de `liboqs` —biblioteca en
C, que no está en PyPI— comprobada en su repositorio:

| Paquete | Licencia |
|---|---|
| Qiskit, Qiskit-Aer, Streamlit | Apache-2.0 |
| `liboqs` (C) y `liboqs-python` | MIT |
| `cryptography` | Apache-2.0 / BSD (dual) |
| NumPy, SciPy | BSD |
| `uproot` | BSD-3-Clause |
| `matplotlib` | PSF License |

Todas permisivas. **Ninguna es incompatible con MIT, Apache 2.0 ni GPL-3.0.** Una salvedad
honesta: `liboqs` incluye implementaciones de terceros de algunos algoritmos bajo licencias
distintas, en sus propias subcarpetas, documentado en su propio `LICENSE.txt`. No afecta a este
proyecto, que solo consume la biblioteca compilada a través de `liboqs-python`, pero se dice en
vez de asumir que «MIT en general» cubre absolutamente todo.

### Opciones

| Opción | Qué permite | Qué exige |
|---|---|---|
| **MIT** | Todo: usar, copiar, modificar, distribuir, uso comercial. | Mantener el aviso de copyright y la licencia en las copias. |
| **Apache 2.0** | Lo mismo que MIT. | Lo mismo que MIT, más una cláusula explícita de concesión de patentes: quien contribuye al proyecto concede los derechos de patente necesarios para usar lo que aportó, y quien demande por patentes pierde la licencia. |
| **GPL-3.0** | Usar, copiar, modificar. | Que cualquier derivado se distribuya también bajo GPL-3.0 (*copyleft*). Incompatible en la práctica con que una empresa integre el código en un producto propietario. |

### Recomendación

**MIT o Apache 2.0.** La primera es la más simple y la más común en portafolios; la segunda
añade la cláusula de patentes. GPL-3.0 queda descartada: el propósito declarado del proyecto es
demostrar dominio técnico ante quien lo revise, no proteger un producto, y el *copyleft*
desincentiva precisamente la lectura que se busca.

### Lo acordado

**Apache 2.0.** Se elige sobre MIT por la cláusula explícita de patentes. En un repositorio que
implementa criptografía —y en particular esquemas post-cuánticos, que es un terreno con patentes
vivas— una licencia que diga expresamente qué pasa con las patentes vale más que una que calle.
El coste sobre MIT es un fichero más largo y poco más.

Lo que se hizo al cerrarla:

1. `LICENSE` en la raíz con el texto íntegro de Apache 2.0 y el aviso de copyright a nombre de
   los tres.
2. `license: Apache-2.0` y `license-url` en `CITATION.cff`, que hasta ahora invitaba a citar un
   software que nadie podía usar legalmente.
3. Badge de licencia en el README, enlazado al fichero, y la sección de reparto diciendo cuál es
   y por qué.

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Gonzalo, Marco, Carlos
```

---

## B2 — Si el repositorio va a ser público

**De dónde viene.** Es la decisión que condiciona a las otras dos del bloque B:
sin repositorio público no hay GHCR gratuito (B1) y la licencia (B3) importa
mucho menos. Y es la única con consecuencias fuera del repositorio.

### Opciones

| Opción | Qué implica |
|---|---|
| **Público** | Cualquiera puede verlo y clonarlo. Habilita GHCR gratis. Es el escenario para el que se escribió el README de escaparate y toda la Fase 4. Y expone de forma permanente el historial completo. |
| **Privado** | Solo se enseña con invitación. El README de escaparate sigue sirviendo para un tribunal o una entrevista, pero pierde su función de que alguien lo encuentre. |

### Lo acordado

**Público**, con acceso de escritura restringido a los tres.

El trabajo entero de la Fase 4 está construido sobre esa hipótesis: el README de
escaparate, los *badges*, los *topics*, el `CITATION.cff`, la prueba de los diez
minutos. Mantenerlo privado después de haberlo pulido para ser visto es pagar el
coste y no cobrar el beneficio.

La objeción que se puso sobre la mesa: publicar significa que las limitaciones
también son públicas, y alguien que lea solo la frase «esto no es un QRNG
certificado» fuera de contexto puede quedarse con la impresión equivocada. La
respuesta es que las limitaciones están escritas con sus tres partes —qué no
hace, por qué, qué haría falta— y un revisor técnico eso lo lee como una virtud.

**Sobre los permisos, que es la otra mitad de la decisión.** Colaboradores con
permiso de escritura: solo Carlos, Marco y Gonzalo. De cara al público, el
repositorio queda en modo lectura más *issues*: cualquiera puede abrir una
*issue*, y nadie de fuera puede escribir en el repositorio ni aprobar nada.

Y hay algo que conviene saber antes de que sorprenda: **GitHub no permite
desactivar los *forks* ni los *pull requests* en un repositorio público.**
Cualquiera puede clonar, bifurcar y abrir un PR. Lo que eso no le da es ningún
permiso: un PR de fuera es una propuesta que solo se integra si uno de los tres
la aprueba y la mergea. El `README` lo dice con todas las letras —las *issues* se
agradecen, el código lo escribimos nosotros— para que nadie pierda el tiempo.

### Lo que tenía que ocurrir antes de cambiar la visibilidad

1. Que existiera `LICENSE` (B3), **en el repositorio y subido**, no solo
   decidido. Un repositorio público que invita a citarse y que nadie puede usar
   legalmente es el peor de los dos mundos.
2. Que Marco y Gonzalo dieran su conformidad sobre sus correos (decisión C, justo
   debajo).

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Gonzalo, Marco, Carlos
```

---

## C — Los correos personales en el historial

**De dónde viene.** De la auditoría previa a la publicación. No estaba en este
documento porque no salió del trabajo de ninguna tarea, sino de mirar el
historial completo antes de hacerlo público.

### El hecho, medido

Los metadatos de *commit* de este repositorio contienen tres direcciones de
correo personales, repartidas por la mayor parte del historial:

| Identidad | Dónde aparece |
|---|---|
| La dirección personal de Carlos (`cmartinez…@gmail.com`) | Como autor y como *committer* |
| La dirección personal de Marco (`marcogit…@gmail.com`) | Como autor y como *committer* |
| La dirección personal de Gonzalo (`gonzaloz…@gmail.com`) | Como autor y como *committer* |
| La dirección `noreply` de GitHub de Carlos | Como autor, desde media fase |

> Las direcciones van recortadas **aquí a propósito**. Están enteras en los
> metadatos de los *commits*, que es de lo que trata esta decisión, pero
> escribirlas completas en un fichero de texto de un repositorio público sería
> ponérselo aún más fácil a un *scraper*: no habría ni que consultar la API.
> Quien las necesite las tiene en `git log`; quien solo quiera entender la
> decisión no las necesita.

Al publicar, esas tres direcciones quedan expuestas de forma permanente y
legibles por cualquiera a través de la API de GitHub. **Dos de las tres son de
terceros**, no de quien pulsa el botón de publicar. Que Carlos cambiara a la
dirección `noreply` a mitad de proyecto sugiere que la exposición no era
intencionada.

### Por qué no vale el `.mailmap` de A3

Un `.mailmap` cambia lo que **muestran** `git log`, `git shortlog` y `git blame`,
pero no borra nada de los objetos de *commit*. Resuelve A3 —que el historial
parezca de tres personas y no de seis— y no resuelve esto. Son dos problemas
distintos que casualmente se parecen.

### Opciones

| Opción | Qué implica |
|---|---|
| **1. Conformidad por escrito** | Marco y Gonzalo dicen que les parece bien y se deja el historial como está. Coste: cero. |
| **2. Reescribir el historial** | `git filter-repo` sobre los *commits* afectados. Cambian **todos** los hashes desde el primero reescrito, se rompen las referencias por hash de `docs/decisiones.md`, hay que hacer `push --force` y que los tres reclonen, y los *pull requests* ya fusionados quedan apuntando a *commits* que no existen. |

### Lo acordado

**Opción 1: conformidad por escrito.** Se preguntó explícitamente a Marco y a
Gonzalo si les parecía bien que sus direcciones de correo personales quedaran
expuestas en el historial al publicar el repositorio. Los dos confirmaron que
sí, en la reunión de cierre del 13 de septiembre de 2026. El historial **no**
se reescribe: se queda tal como está, con las tres direcciones visibles.

De cara al futuro, y aunque la decisión ya esté tomada: los tres deberíamos
activar en nuestras cuentas el correo `noreply` de GitHub y la opción *Block
command line pushes that expose my email*, que es lo que Carlos ya hizo a
mitad de proyecto, para que los *commits* nuevos no sigan exponiendo la
dirección personal por defecto.

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Gonzalo, Marco, Carlos
```

---

## D — Dependencias con avisos de seguridad conocidos

**De dónde viene.** Auditoría de dependencias con `pip-audit` previa a la
publicación.

`cryptography` se subió de la `42.0.5` a la `48.0.1`, que es lo que se podía
subir sin romper nada. Del resto, seis paquetes siguen teniendo avisos
publicados, y esta entrada explica qué se hace con cada uno. El criterio es el
mismo para todos: **mirar si el camino de código que dispara el fallo existe en
este proyecto**, y decidir con eso en vez de con el número de la versión.

### El hecho, medido

`pillow` no está pineada en `requirements.txt`: es dependencia transitiva
de Streamlit, resuelta hoy en `10.4.0`. `pip-audit` reporta más de veinte
avisos sobre esa versión, arreglados en versiones que van de 12.1.1 a
12.3.0. La inmensa mayoría son fallos de lectura o escritura fuera de
límites al decodificar formatos de imagen específicos y manipulados a
propósito: PSD, FITS, PCF, BDF, GD, McIdas AREA, JPEG2000, TGA y PDF.

El vector de entrada real en este proyecto es la pestaña del Módulo 3, que
acepta imágenes subidas por el usuario (`_imagen_subida` en
`dashboard/qkd_app.py`). El filtro `type=[...]` de `st.file_uploader` es
solo una ayuda del selector de fichero en el navegador, **no** una barrera
de seguridad: cualquiera puede renombrar un fichero manipulado con
extensión `.png` y Pillow lo abre igual si reconoce su firma interna,
porque `Image.open()` autodetecta el formato por el contenido del
fichero, no por su nombre.

### Por qué no se sube la versión

Streamlit 1.33.0 declara `pillow<11,>=7.1.0` como dependencia. La versión
que cierra todos los avisos conocidos es la 12.3.0, **incompatible** con
esa restricción. Subir Pillow sin subir Streamlit rompe la instalación;
subir Streamlit también exige repetir el ciclo completo de verificación
(tests y comparación de MD5 de las figuras) que ya se hizo con
`cryptography`, con más riesgo de romper algo a pocas horas de cerrar el
proyecto.

### Lo acordado

**Mitigar en el código, no en la versión.** Se añade una restricción
explícita de formatos en `_imagen_subida`:

```python
formatos_permitidos = ("PNG", "JPEG", "BMP", "TIFF")
with Image.open(fichero, formats=formatos_permitidos) as abierta:
```

Esto corta el acceso a los complementos vulnerables (PSD, FITS, PCF, BDF,
GD, McIdas, JPEG2000, TGA) **independientemente de la versión de Pillow**
instalada: si Pillow nunca intenta interpretar esos formatos, da igual
que su implementación tenga un fallo o no. Es además una mitigación más
duradera que subir de versión, porque protege también contra
vulnerabilidades de esos mismos complementos que se descubran en el
futuro.

Queda como deuda declarada, no resuelta del todo: la versión de Pillow
sigue siendo la 10.4.0, y si algún día Streamlit se actualiza a una
versión que acepte Pillow ≥ 12.3.0, debería aprovecharse ese momento para
subirla también.

Verificado: `_imagen_subida` sigue abriendo un PNG válido correctamente
tras el cambio.

### protobuf, el mismo problema y sin necesitar mitigación

`protobuf` tampoco está pineada: es transitiva de Streamlit, resuelta hoy
en `4.25.9`. `pip-audit` reporta PYSEC-2026-1805, una denegación de
servicio en `google.protobuf.json_format.ParseDict()` al parsear mensajes
`Any` anidados de forma profunda, arreglada en `5.29.6`.

Streamlit 1.33.0 exige `protobuf<5,>=3.20`: la versión que arregla el
aviso, 5.29.6, es incompatible con esa restricción, igual que con
Pillow.

A diferencia de Pillow, aquí no hace falta ninguna mitigación de código:
`grep` confirma que el proyecto no llama a `json_format.ParseDict()` ni a
ninguna otra función de `google.protobuf.json_format` en ningún sitio.
El vector de la vulnerabilidad no existe en esta aplicación porque el
camino de código que la dispara nunca se ejecuta.

### Los otros cuatro: `cryptography`, `qiskit`, `pyarrow` y `streamlit`

Los cuatro arrastran avisos y en los cuatro el camino vulnerable **no existe en
este proyecto**. Comprobado a mano antes de escribirlo, no supuesto:

| Paquete | Avisos | Dónde está el fallo | Por qué aquí no aplica |
|---|---|---|---|
| `cryptography` 48.0.1 | 3 | Validación de cadenas X.509 (restricciones de nombre, recursión con certificados autofirmados duplicados) y descifrado PKCS#7 | El proyecto solo importa de `hazmat.primitives`: AEAD, HKDF y las asimétricas. **Cero usos** de `x509`, de `pkcs7` y de verificación de cadenas. No hay certificados en ninguna parte de este código. |
| `qiskit` 1.0.2 | 3 | Deserialización de ficheros **QPY** manipulados, con ejecución de código en el peor caso | El proyecto no lee ni escribe QPY en ningún sitio: los circuitos se construyen en memoria y se simulan. **Cero usos** de `qpy`. |
| `pyarrow` 16.1.0 | 2 | Lectura de ficheros **Parquet** e **IPC de Arrow** no confiables | Es dependencia transitiva de Streamlit, que la usa para *serializar* los `DataFrame` que el panel enseña. El proyecto no lee Parquet ni IPC de ninguna fuente. **Cero usos** directos. |
| `streamlit` 1.33.0 | 3 | Dos son **exclusivos de Windows** (recorrido de rutas en el servicio de ficheros estáticos, y SSRF con exposición de credenciales NTLM). El tercero es un hash débil en la caché, que exige acceso local y el propio aviso califica de explotación difícil | El despliegue documentado es el contenedor, que es Linux. Y el servicio de ficheros estáticos ni se activa: `.streamlit/config.toml` no toca la sección `[server]`, así que queda en su valor por defecto, desactivado. |

### Por qué no se suben, y qué haría falta para subirlos

`streamlit` es el tapón. La 1.33.0 fija `pillow<11`, `protobuf<5` y arrastra la
`pyarrow` contemporánea, así que **los cuatro se mueven juntos o no se mueve
ninguno**. Y `pyarrow` no se puede subir sola por un motivo propio y ya medido:
la 25.x revienta al serializar `DataFrame` en `st.dataframe`, que es lo que hace
la mitad del panel.

`cryptography` sí se podría subir a la 49 o la 50, pero cerraría avisos de un
camino de código que este proyecto no recorre, a cambio de repetir el ciclo
completo de verificación a pocas horas de cerrar.

Subir todo eso es una tarea de verdad: actualizar Streamlit, revisar que el panel
sigue funcionando, volver a pasar los tests y **regenerar las diecisiete figuras
comparadas por MD5**, que es donde está el trabajo real. Se declara aquí como lo
que es —deuda conocida y acotada, no un descuido— y se hace cuando haya tiempo
para hacerlo bien.

### Lo que sí queda montado para no enterarse tarde

`.github/dependabot.yml` abre un *pull request* mensual por cada actualización, y
la CI ejecuta `pip-audit` en cada vuelta y deja el informe en el resumen de la
ejecución. Ese paso **no tumba la CI a propósito**: si lo hiciera, hoy mismo
estaría en rojo y las dos únicas salidas serían subir a ciegas o silenciar el
paso. Las dos son peores que leer el informe.

```
ESTADO      : CERRADA
FECHA       : 2026-09-13
ACORDADO POR: Carlos
```

> **Resumen, para quien venga de fuera.** Seis dependencias tienen avisos
> publicados. En Pillow el camino existía y se ha cerrado por código. En los
> otros cinco el camino no existe en este proyecto, y está comprobado uno por
> uno. Ninguno se ha silenciado.

---

## Registro

| Fecha | Qué cambió |
|---|---|
| 2026-09-05 | Fichero creado con A1, A2 y A3 redactadas y la medida de reparto tomada sobre `9f090ef`. Las tres quedan pendientes de la reunión del bloque B. |
| 2026-09-13 | **Reunión de cierre.** Se cierran las seis decisiones: A1 (dejarlo), A2 (dejarlo), A3 (`.mailmap` con los alias de GitHub y reparto sin tabla de *commits*), B1 (publicar en GHCR), B2 (repositorio público, escritura solo para los tres) y B3 (Apache 2.0). Se añade la decisión **C**, sobre los correos del historial: Marco y Gonzalo dan su conformidad por escrito en la propia reunión y el historial no se reescribe. |
| 2026-09-13 | Se añade la decisión **D**, de la auditoría de dependencias con `pip-audit`. `cryptography` sube a la `48.0.1`. Los seis paquetes que conservan avisos se revisan uno por uno: en Pillow el camino vulnerable existía y se cierra por código (restricción explícita de formatos en `_imagen_subida`); en `protobuf`, `qiskit`, `pyarrow`, `streamlit` y el propio `cryptography` se comprueba que ese camino no se recorre en este proyecto. Queda declarada como deuda acotada, no como resuelta del todo. |
| 2026-09-14 | Última revisión antes de publicar. Las ocho decisiones cerradas, `LICENSE` en la raíz, la imagen publicándose en GHCR y el reparto escrito por trabajo. El documento queda sin ninguna casilla abierta. |
