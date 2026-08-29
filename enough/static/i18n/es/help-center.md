Hola, soy Graham, el creador de enough. Este documento —salvo esta parte, quiero decir— está escrito y mantenido principalmente por agentes. Casi seguro que de vez en cuando le voy a echar algunos "Grahamismos" encima, pero la idea es no dejar que mis propias ganas de escribir cosas divertidas se interpongan en el camino de una documentación exhaustiva.

# el centro de ayuda de enough

> Todo lo que puedes hacer con enough, en un solo lugar. Escrito para enough **0.3.0**, incluyendo la pantalla de inicio (cada proyecto que has empezado alguna vez, en una sola lista, con una entrada y una salida — sección 2), la ronda de conversión (PDF, documentos de Word, libros electrónicos, presentaciones y libros de excel se abren como gemelos editables en markdown, con exportación, sincronización y un visor de imágenes — sección 6), la ronda de habilidades (el nuevo modo de auditoría de analyzer, la habilidad `anything-finder`, y la auditoría al primer uso que lee cualquier habilidad que enough no incluyera de fábrica antes de dejarla entrar), la ronda de agosto de 2026 (siete modelos locales con instalaciones verificadas por viabilidad, y **enough.app** — la aplicación de escritorio firmada y notarizada), la ronda de interfaz de julio de 2026 (la pila de modos, burbujas de ayuda por carpeta, espejos girraph→merirmaid), y la ronda de preferencias de 0.3.0 (escala de ui y de texto por proyecto, y la interfaz + ayuda en seis idiomas — sección 9). Donde este documento y la app frente a ti no coincidan, la app tiene la razón y este documento tiene un error — las correcciones son bienvenidas en [enough.support](https://enough.support).

enough es un sistema personal de lenguaje que corre en tu propia máquina. Lo apuntas a una carpeta, le hablas, y te ayuda a planear, escribir, revisar, investigar y traducir. Los modelos son locales por defecto. Tus archivos siguen siendo tuyos. Y casi todo lo que lo ves hacer está definido en archivos markdown simples que puedes abrir, leer y cambiar.

Guarda una idea mientras lees: **las funciones incorporadas en este manual son solo una fracción de lo que enough puede hacer.** Los paradigmas, roles y habilidades que vienen de fábrica son un kit inicial — ejemplos funcionando de tres mecanismos de personalización, no sus límites. La meta final es que escribas los tuyos, o que el agente los escriba contigo: un paradigma para tu forma de planear ensayos, un rol que discuta como tu lector más exigente, una habilidad que codifique tu estilo propio. La sección 3 explica cómo. Es la sección más importante de este documento, y el manual te va a seguir mandando de vuelta a ella.

---

## 1. Instalación, atajos, y esta documentación

### 1.1 Qué necesitas

- Un Mac con Apple Silicon. (enough se construye y se prueba en macOS. El soporte para Linux está planeado; Windows es factible.)
- Espacio en disco para al menos un modelo — el más pequeño ronda los 5 GB.
- Sin cuentas, sin claves de API, sin suscripciones. A menos que más adelante actives la ranura de modelo en la nube (sección 13.2), todo corre localmente.

### 1.2 Instalando

Dos puertas, la misma casa.

**La app — el camino corto.** Descarga el DMG de `enough` desde la página de releases, ábrelo, arrastra **enough** a Aplicaciones, y lánzalo. macOS notará que es una app de internet — pero está firmada y notarizada, así que esto es el amigable diálogo azul con un botón **Abrir**, una sola vez, no una advertencia que hay que sortear. Una guía de primer inicio se encarga del resto: construye su propio entorno de Python, te muestra la lista de modelos con un veredicto honesto sobre qué le cabe a *esta* máquina (sección 13.1), lista qué extras opcionales ya tienes, y te entrega a la pantalla de inicio para elegir la carpeta en la que quieres trabajar (sección 2). La mayor parte de la espera es la descarga del modelo. Sin Terminal, sin Homebrew, sin git.

La app trae su propio motor de inferencia y su propio Python. Los extras opcionales — entrada de voz, obtención de páginas web, revisión gramatical, traducción — siguen siendo programas separados; la página de Extras de la guía nombra cada uno, qué se desactiva sin él, y cómo conseguirlo. Nada es obligatorio, y nada se instala a tus espaldas. Un extra ni siquiera es un programa separado: la **lectura de PDF** se instala desde dentro de enough cuando tú quieras (sección 6.8).

**La terminal — el camino largo, con más palancas.** Clona el repositorio, y luego haz doble clic en `install-enough.command` dentro de la copia clonada:

```bash
git clone https://github.com/0gsd/enough.git ~/Downloads/enough-seed
open ~/Downloads/enough-seed
```

La primera vez que hagas doble clic, es posible que macOS Gatekeeper se resista con un "desarrollador no identificado" — esa advertencia es sobre el archivo `.command`, que no está firmado como sí lo está la app. Haz clic derecho en el archivo y elige **Abrir** una vez; macOS recuerda la confianza de ahí en adelante.

El lanzador ejecuta `bootstrap.sh`, un instalador interactivo de diez pasos que pregunta antes de cada paso y explica lo que está por hacer. Ctrl-C es seguro en cualquier momento. Volver a ejecutarlo también es seguro — primero revisa el estado y retoma donde lo dejaste. Los pasos, a grandes rasgos:

1. Revisa tu plataforma.
2. Busca Homebrew, y te ayuda a instalarlo si falta.
3. Instala los programas auxiliares en los que se apoya enough: `llama.cpp` (inferencia de modelos local), `whisper-cpp` (entrada de voz), `tor` (obtención anonimizada de páginas web), y `harper` (revisión gramatical local, usada por la habilidad analyzer). Los conversores de documentos — pandoc, para convertir páginas web obtenidas y archivos de Word a markdown, y typst, para escribir PDF — ya no están en esa lista: vienen dentro del propio entorno de Python de enough, instalados en el paso 5, en todas las plataformas. Si por casualidad ya tienes tu propio pandoc de Homebrew, enough usa ese en su lugar.
4. Prepara `~/enough/`, el directorio de instalación global.
5. Prepara el entorno de Python (mediante `uv`).
6. Descarga los pesos de los modelos. Cada modelo compatible se ofrece de uno en uno, cada uno con su tamaño y una verificación de viabilidad contra la memoria y el disco libre de tu máquina — ✓ significa cómodo, ~ significa ajustado, ✗ significa busca en otro lado. Di que sí a tantos como quieras; la sección 13.1 los describe todos, y cualquiera que te saltes se puede instalar después con un solo clic.
7. Coloca el modelo de entrada de voz (whisper).
8. Coloca el modelo de traducción sin conexión, usado por la habilidad `translator`.
9. Pon el comando `enough` en tu PATH.
10. Listo, con una lista impresa de próximos pasos.

Actualizar más adelante: ejecuta `update-enough.command` desde `~/enough/`, o escribe `/update-enough` en el cuadro de chat. Cuando salen valores predeterminados nuevos, enough lo menciona en la interfaz y te señala ese comando, así que no tienes que andar revisando. `update-weights.command` actualiza los pesos de los modelos por separado.

### 1.3 Lanzando

**Desde la app:** haz doble clic, y caes en la **pantalla de inicio** — cada carpeta que alguna vez convertiste en proyecto de enough, en una sola lista, con una forma de añadir otra. Elige una y se abre. Esa es la sección 2, y vale la pena leerla antes que esta.

El menú **enough** tiene un solo ajuste, **Reabrir el último proyecto al iniciar**, desactivado por defecto: actívalo y la app se salta la pantalla de inicio y te devuelve directo a donde estabas. Una ventana, un proyecto a la vez — y **Archivo → Cerrar proyecto** (⌘W) te deja de vuelta en inicio cuando quieras moverte, sin salir de la app (sección 2.5).

Todavía hay un simple selector de carpetas ahí dentro, pero probablemente nunca te lo encuentres: es el respaldo para cuando la propia pantalla de inicio no puede aparecer — una actualización a medias, una instalación rota — para que hasta en un mal día te quede una forma de llegar a tu trabajo.

**Desde la terminal:** enough corre por carpeta de proyecto. Abre una terminal en cualquier carpeta y ejecuta:

```bash
enough
```

y luego visita `http://127.0.0.1:3456` (enough te lo abre solo). Carpeta distinta, proyecto distinto, memoria de agente distinta. La única carpeta desde la que no puedes lanzarlo es `~/enough/` misma — la CLI se niega, porque eso es la instalación, no un proyecto.

También puedes llegar a la pantalla de inicio, desde cualquier lugar:

```bash
enough --home
```

La misma pantalla, la misma lista, en tu navegador en vez de en la ventana de la app. Abre un proyecto desde ahí y la terminal en la que lo iniciaste se convierte en la terminal de ese proyecto.

Si prefieres no escribir nunca el comando, hay dos lanzadores incluidos en `~/enough/shortcuts/`:

- **`enough-on.command`** — cópialo a una carpeta de proyecto (`cp ~/enough/shortcuts/enough-on.command ~/algun-proyecto/`), y luego haz doble clic en él desde Finder. Se abre una ventana de Terminal en esa carpeta con enough corriendo; ⌘W o Ctrl-C lo detiene.
- **`setup-quick-action.sh`** — ejecútalo una vez (`bash ~/enough/shortcuts/setup-quick-action.sh`) y obtienes una Acción Rápida de Finder: clic derecho en cualquier carpeta → Acciones Rápidas → **Launch in enough**. Si el elemento del menú no aparece, actívalo en Configuración del Sistema → Teclado → Atajos de Teclado → Servicios → Archivos y Carpetas.

### 1.4 Esta documentación, y el resto

Este archivo es el manual extenso. También tienes:

- **Ayuda integrada** — las burbujas `(?)` repartidas por la interfaz, cada una explicando lo que tiene al lado: un *qué es*, un *cómo se usa*, y una lista de *ideas*. Ve la sección 9.6.
- **Las chuletas de referencia** — atajos de teclado y sintaxis de markdown, a un clic en la ventana de ui. Ve la sección 9.5.
- **[enough.support](https://enough.support)** — el foro de la comunidad: ayuda de instalación, gente mostrando sus flujos de trabajo, y personas que con gusto te van a ayudar a construir las personalizaciones hacia las que este manual te sigue empujando.

Y todo esto — este manual, las burbujas, la interfaz que las rodea — se lee en seis idiomas: inglés, francés, español, alemán, chino y japonés. La sección 9.4 tiene el menú desplegable y la letra pequeña.

---

## 2. La pantalla de inicio

Antes de entrar a un proyecto, estás en **inicio**: un solo cuadro que lista cada carpeta que alguna vez convertiste en proyecto de enough, más una casilla para añadir otra. Es, a propósito, la pantalla más silenciosa de la aplicación. Sin chat, sin barra lateral, sin modelo, sin agente — todavía no corre nada y no se está pensando en nada. Solo tus proyectos, y el botón de ui ⚙ en la barra superior para el tema y este manual.

La vas a ver:

- la primera vez que lanzas la app, cuando termina la guía de primer inicio;
- en cada lanzamiento después de eso, a menos que **Reabrir el último proyecto al iniciar** esté activado (sección 1.3);
- cada vez que cierras un proyecto (sección 2.5);
- desde la terminal, en cualquier momento, con `enough --home`.

La única forma de *no* verla es ese interruptor. Activa **Reabrir el último proyecto al iniciar** y enough vuelve directo al proyecto en el que estabas; inicio nunca se interpone. Desactívalo y inicio es donde empieza cada lanzamiento. Ese interruptor es todo el ajuste — no hay nada más que configurar.

### 2.1 La cuadrícula, la lista, y ¶ W C

Dos vistas, alternadas con el par de botones arriba a la derecha del cuadro, y enough recuerda cuál prefieres.

**Iconos** es la vista de exploración: un glifo de carpeta, el nombre del proyecto, y una línea sencilla debajo — *editado hace 3 días*, o una fecha real una vez que pasa de la semana.

**Lista** es la vista de comparación. Seis columnas:

| columna | qué es |
|---|---|
| nombre | el nombre visible del proyecto (el que pones en la barra de título del proyecto, o el nombre de la carpeta) |
| ¶ | párrafos |
| W | palabras |
| C | caracteres |
| última actualización | el cambio más reciente en cualquiera de los archivos que cubren esos totales |
| creado | cuándo se convirtió la carpeta en un proyecto de enough |

Esas tres columnas del medio son las mismas tres cifras que enough pone en la barra superior mientras tienes un documento abierto — ¶ para párrafos (bloques separados por línea en blanco), W para palabras, C para caracteres incluyendo espacios y saltos de línea — sumadas a lo largo de todo el proyecto. La regla sobre *qué* archivos se cuentan vale una frase, porque es la que hace que los números signifiquen algo: todo archivo markdown que el propio árbol de archivos del proyecto te mostraría, **incluyendo los gemelos de los documentos convertidos** (un `.docx` que estás editando aquí es tu escritura), y **no** nada dentro de `rness/` (el andamiaje del agente no es tu libro). Así que el número en la columna W es, casi, cuánto has escrito.

Haz clic en cualquier encabezado de columna para ordenar por ella; haz clic en el mismo otra vez para invertir el orden. Los proyectos sin nada que reportar — nunca abiertos, nunca contados — se hunden al fondo de cualquier forma, en vez de fingir ser los más antiguos. El orden predeterminado es el de edición más reciente primero.

Un proyecto cuya carpeta no está ahí en este momento — un disco externo desconectado, una carpeta que moviste en Finder — se muestra en gris, con la ruta que recuerda en el tooltip. **No** se elimina de la lista, y conserva los totales que tenía la última vez que lo viste. Un proyecto en un disco guardado en un cajón no es un proyecto perdido.

### 2.2 Hacer clic en un proyecto: el mapa

Un solo clic no abre un proyecto. Te dibuja un **mapa** de él: un diagrama merirmaid de solo lectura (sección 18) del contenido visible de la carpeta, con un pequeño nodo de información arriba que lleva la ruta, el número de archivos, los totales de ¶ y W, y cuándo se creó el proyecto, cuándo se abrió y cuándo se editó por última vez. Es el mismo tipo de imagen que cacheawl dibuja para un cachebox (sección 11.1), pero apuntando a un proyecto en vez de eso.

El mapa es para ese momento en que tienes cuatro carpetas con nombres plausibles y quieres saber cuál tiene los capítulos adentro. Mira, y luego decide.

Cuando ya decidiste, el botón **abrir proyecto** de la barra de herramientas lo abre. Esc, o la cinta arriba a la derecha, te devuelve a la cuadrícula. Y si ya sabías cuál querías, haz **doble clic** en la casilla o fila y se abre sin el rodeo.

Abrir se ve igual de cualquier forma: el cargador aparece por uno o dos segundos mientras enough apaga la pantalla de inicio e inicia el proyecto en su lugar, y luego estás en la vista de conversación (sección 4) exactamente como si hubieras lanzado directo hacia esa carpeta.

### 2.3 Añadir una carpeta

La última casilla de la cuadrícula — la que tiene el signo de más — es cómo una carpeta se convierte en un proyecto.

Haz clic y macOS abre su propio selector de carpetas. Elige cualquier carpeta de notas, borradores o documentos; enough le añade `rness/` (sección 7), la registra en tu pantalla de inicio, y la abre. La casilla dice *esperando al selector de carpetas…* mientras el diálogo está abierto, así que tómate el tiempo que quieras explorando.

Se rechazan dos tipos de carpeta, y enough te dice cuál y por qué en vez de fallar de forma vaga:

- **`~/enough` misma, o cualquier cosa dentro de ella.** Eso es la instalación, no un proyecto. (El comando `enough` rechaza la misma carpeta por la misma razón.)
- **Cualquier cosa dentro de una carpeta sincronizada con la nube** — Google Drive, Dropbox, iCloud Drive. Esto no es puntillosidad. El `rness/` de un proyecto está construido con enlaces simbólicos de vuelta a los valores predeterminados globales, y los clientes de sincronización reescriben o rompen los enlaces simbólicos como cosa de rutina; te quedaría un proyecto que deja de seguir tus ajustes globales en silencio, en la máquina donde no te diste cuenta. Mantén los proyectos en el disco local y sincroniza el trabajo terminado en su lugar.

Una carpeta que ya está en tu pantalla de inicio no es un error — enough simplemente la abre.

Si el selector de carpetas no puede aparecer en absoluto (una máquina que no es un Mac, un sandbox que se niega), el modal ofrece en su lugar un campo de texto simple para escribir la ruta, con la razón mostrada arriba. Todo lo que sigue es idéntico.

### 2.4 Ocultar un proyecto

Inicio lista todo, para siempre, y después de un año de experimentos eso se hace largo. Así que: **opción+clic en cualquier casilla o fila para ocultarla.**

Ocultar es solo una nota en la propia lista de enough y nada más. Lo dice cuando pregunta: la carpeta en el disco no se toca, `rness/` no se toca, y ni una palabra en ella cambia. No hay un "eliminar este proyecto" en la pantalla de inicio, y eso es a propósito — eliminar un proyecto significa eliminar una carpeta llena de tu escritura, y ese es un trabajo para Finder, donde puedes ver lo que estás haciendo.

El chip **ocultos** junto a los botones de vista los trae de vuelta, etiquetado con cuántos hay. Los proyectos ocultos se muestran en gris con *oculto* en su línea; opción+clic en uno para dejar de ocultarlo (sin confirmación — es instantáneo y es instantáneamente reversible). En la app puedes accionar el mismo interruptor desde **Ver → Mostrar Proyectos Ocultos**.

### 2.5 Cerrar un proyecto, y volver

Dos puertas, el mismo cuarto.

**En la app:** **Archivo → Cerrar Proyecto**, o **⌘W**. El backend del proyecto se apaga con elegancia y la pantalla de inicio aparece en su lugar, un segundo después más o menos.

**En cualquier lugar, app o navegador:** el botón **cerrar proyecto → inicio** en lo alto de la ventana de ui ⚙ (sección 9). Pregunta primero, porque cerrar termina la sesión — la conversación frente a ti se acaba, igual que pasaría al salir — y luego te deja exactamente en el mismo lugar al que te llevaría ⌘W.

Ninguno de los dos toca tu carpeta. Tus archivos, tu `rness/`, tus archivos de solicitud, y tus registros de sesión están todos exactamente donde los dejaste; solo termina la conversación que estaba corriendo.

Una consecuencia del nuevo ⌘W que vale la pena saber si has usado enough por un tiempo: **⌘W ya no cierra la ventana.** enough es una aplicación de una sola ventana y cerrar esa ventana la cierra por completo, así que ⌘Q y el botón rojo ya cubrían ese terreno, y ⌘W tenía un trabajo mejor que hacer.

Y una interacción entre esto y el ajuste de reapertura, porque si no te va a sorprender exactamente una vez: **cerrar un proyecto no hace que enough lo olvide.** Si **Reabrir el último proyecto al iniciar** está activado y cierras un proyecto, te quedas un rato en inicio, y luego sales — el siguiente lanzamiento reabre ese proyecto, no inicio. El interruptor es el ajuste que decide dónde empiezas; Cerrar Proyecto es el botón que decide dónde estás ahora mismo. Si quieres empezar en inicio de ahora en adelante, desactiva el interruptor.

### 2.6 Lo que inicio recuerda

Tres cosas pequeñas, todas globales a la máquina — te siguen de proyecto en proyecto y de vuelta a inicio, y no se guardan en ninguna carpeta de proyecto:

- **El tema y la fuente** (sección 9.1). Inicio lleva puesto lo último que elegiste, y un tema al que cambias *en* la pantalla de inicio es el tema en el que se abre tu proyecto. Este es el que solía molestar a la gente: la pantalla de lanzamiento y la pantalla de trabajo ahora concuerdan, siempre.
- **Iconos o lista**, de la sección 2.1.
- **Si se muestran los proyectos ocultos**, de la sección 2.4.

Todo lo demás sobre un proyecto vive en la carpeta de ese proyecto, donde puedes leerlo.

---

## 3. Personalización del flujo de trabajo a nivel central

Si vas a leer una sola sección, que sea esta.

La mayoría del software te da funciones. enough te da mecanismos. La personalidad, el método y el conjunto de habilidades del agente se ensamblan de nuevo en cada mensaje a partir de archivos markdown que están en tu disco:

- **`AGENT.md`** — quién es el agente y cómo opera (sección 4.1)
- **`MOTIVATION.md`** — por qué: valores, prioridades, cómo se siente "terminado"
- **Políticas** — reglas estrictas sobre qué puede leer, escribir y obtener (sección 4.2)
- **El paradigma activo** — el marco de razonamiento vigente ahora mismo (sección 14)
- **Habilidades activadas** — capacidades a las que puede recurrir (sección 16)
- **Roles activados** — otras personalidades que puedes invocar (sección 15)
- **El perfil del proyecto** — lo que ha aprendido sobre este proyecto (sección 7.1)

Edita cualquiera de estos, en la app o en cualquier editor de texto, y el cambio surte efecto en el siguiente mensaje. Sin reconstruir, sin reiniciar, sin API de plugins. Si puedes escribir un archivo markdown, puedes reprogramar a tu agente.

### 3.1 Global frente a local al proyecto

Todo lo personalizable sigue un mismo patrón: **los valores predeterminados viven en `~/enough/defaults/`, los proyectos se enlazan a ellos, y cualquier proyecto puede romper el enlace.**

Edita un archivo en `~/enough/defaults/` y todo proyecto que todavía esté enlazado a él recoge el cambio. En un proyecto, abre un archivo enlazado y haz clic en **personalizar** — el enlace se convierte en una copia local del proyecto, y de ahí en adelante ese proyecto sigue su propio camino mientras los demás siguen el valor predeterminado global. El árbol de archivos te dice cuál es cuál de un vistazo: los archivos enlazados se muestran *en cursiva y apagados*, las copias locales se muestran normal.

Las habilidades, roles y paradigmas nuevos que colocas en `~/enough/defaults/` aparecen en todos los proyectos en el siguiente lanzamiento. Las habilidades y roles llegan desactivados, así que nada cambia a tus espaldas; los activas por proyecto cuando los quieres. Una habilidad que enough no incluyó de fábrica — una que descargaste, una que te mandó un amigo, una que tu propio agente escribió para ti — se lee antes de que se le permita entrar. La sección 16.6 cubre eso.

### 3.2 Los tres tipos de componente

| | Paradigma | Habilidad | Rol |
|---|---|---|---|
| Qué es | Un marco de razonamiento — cómo el agente aborda el trabajo | Una capacidad especializada — vocabulario, recetas, procedimientos | Una segunda personalidad que puedes invocar — su propio AGENT.md + MOTIVATION.md |
| Cuántos activos | Exactamente uno a la vez | Cualquier cantidad activada | Cualquier cantidad activada |
| Vive en | `rness/paradigms/<name>.md` | `rness/skills/<name>/SKILL.md` | `rness/roles/<name>/` |
| Ejemplos incluidos | default, text-planning, translation, workflow-design | analyzer, anything-finder, girraph-merirmaid, memoir-dialectic, translator | block-breaker, open-skeptic |

### 3.3 Construir el tuyo propio

Puedes escribir estos archivos a mano — son markdown con un pequeño bloque YAML arriba — pero no tienes que hacerlo. El **paradigma workflow-design** incluido (sección 14.4) existe para que el agente pueda construirlos contigo. Di "constrúyeme una habilidad que…" o "crea un rol que…" o "haz un paradigma para…" y el agente cambia a workflow-design, hace sus preguntas aclaratorias (¿alcance? ¿nombre? ¿condiciones que lo disparan? ¿archivos complementarios?), y escribe el componente como corresponde, incluyendo el frontmatter `description:` que le dice a turnos futuros cuándo recurrir a él.

Cosas que la gente realmente construye:

- Un **paradigma** para cada modo distinto de su trabajo — investigar, redactar, revisar — con reglas explícitas de cuándo cambiar.
- Una **habilidad** que codifica la voz de un boletín, un formato de citas, la terminología de una tesis.
- Un **rol** que es un pato de goma haciendo preguntas socráticas, o un revisor par escéptico, o un experto en un campo construido a partir de tus propios archivos de conocimiento.

El resto de este manual describe los que vienen incluidos. Lee cada uno de ellos como un ejemplo resuelto que tienes permiso de copiar, bifurcar y mejorar.

---

## 4. Conversación con el agente — la base de la pila

Abre un proyecto y caes en la vista de conversación: la charla con tu agente, más la barra lateral mostrando tu proyecto. Esta es la planta baja. Todos los demás modos se apilan encima de ella y eventualmente se cierran de vuelta hacia ella. (La *pantalla de inicio* de la sección 2 es otra cosa por completo — ahí es donde estás antes de que un proyecto esté abierto; aquí es donde estás una vez que lo está.)

Lo que hay aquí:

- **El chat.** Escribe un mensaje, pulsa ⌘Enter (o el botón de enviar). Las respuestas llegan en vivo, y el agente puede actuar mientras habla — leyendo y escribiendo archivos, ejecutando comandos de shell, obteniendo páginas — y cada llamada a herramienta aparece en la transcripción a medida que ocurre.
- **El botón de micrófono.** Haz clic y dicta. El habla se transcribe con whisper.cpp localmente; tu voz nunca sale de la máquina. El botón palpita mientras graba. Haz clic otra vez para detener.
- **La barra lateral.** El árbol de archivos del proyecto, más las secciones de control: el **paradigma** activo, interruptores para **habilidades** y **roles**, y tus **solicitudes**. Opción+clic en cualquier archivo o carpeta para un menú contextual (nuevo archivo, nueva carpeta, copiar ruta, copiar nombre). ⌘\ oculta y muestra toda la barra lateral.
- **La barra superior.** Botones para la ventana de modelo, el broker, la ventana de ui, wikisink (🚰), y cacheawl — y en el borde derecho, los indicadores de los modos que estén apilados en ese momento (sección 12).

### 4.1 AGENT.md y MOTIVATION.md

Cada proyecto lleva su propia copia de estos dos archivos en `rness/`. Son la raíz de la identidad del agente, y ambos se cargan en cada turno.

**`AGENT.md`** es el *cómo*: instrucciones de trabajo. Tono, barreras, convenciones, órdenes permanentes. "Mantén la prosa en minúsculas." "Nunca toques archivos en `archive/`." "Pregunta antes de ejecutar comandos de shell de más de una línea."

**`MOTIVATION.md`** es el *por qué*: valores y prioridades más allá de la tarea que tiene enfrente. Para qué es el proyecto, a quién sirve, qué compromisos importan (¿exactitud sobre velocidad? ¿brevedad sobre exhaustividad?), cómo se siente "terminado".

Haz clic en cualquiera de los dos archivos en la barra lateral para leerlo; pulsa **personalizar** para bifurcar tu copia local del proyecto, o edítalo en el editor que prefieras. Los cambios llegan en el siguiente mensaje. Los roles usan el mismo patrón de dos archivos (sección 15) — el agente principal no es especial, solo es el primero.

### 4.2 La carpeta de políticas y las listas de permitidos

`rness/policies/` contiene las reglas estrictas del agente. No es personalidad — es ley. Cuatro políticas vienen de fábrica:

- **`allowlists.md`** — las reglas de alcance. Tres listas:
  1. *Prefijos de lectura de archivos:* rutas absolutas que el agente puede leer fuera del proyecto (predeterminado: `~/enough/`).
  2. *Prefijos de lectura-escritura de archivos:* rutas en las que también puede escribir fuera del proyecto. Esta lista viene **vacía**: recién instalado, el agente solo escribe dentro de tu proyecto, y se queda así hasta que añadas una ruta deliberadamente.
  3. *Dominios de internet:* hosts que se obtienen directamente (los predeterminados incluyen `gutenberg.org`, `en.wikipedia.org`, `en.wikisource.org`, `archive.org`, `standardebooks.org`, y el host de descargas de Kiwix). Un dominio que no está en la lista no queda bloqueado — la obtención se enruta en su lugar por un proxy Tor local, así que una búsqueda puntual no deja tu dirección en los registros de algún servidor. Un interruptor del broker puede desactivar ese respaldo, haciendo que las obtenciones fuera de lista fallen sin más.
- **`context-management.md`** — cómo el agente detecta que se le llena la ventana de contexto y se reinicia con elegancia sin perder su estado (sección 7.3).
- **`requests.md`** — cuándo y cómo el agente registra el trabajo de larga duración como archivos de solicitud (sección 7.3).
- **`profile-maintenance.md`** — qué pertenece al perfil del proyecto y qué no (sección 7.1).

Las políticas están enlazadas simbólicamente desde los valores predeterminados como todo lo demás, así que puedes endurecer la lista de permitidos globalmente o personalizarla para un proyecto que necesite un alcance más laxo (o más estricto). Editar `allowlists.md` es, en la práctica, la personalización más común de todas: añade los sitios de documentación en los que confías, añade una carpeta compartida en la que el agente debería poder escribir, y sigue con tu día.

---

## 5. Modo lectura/edición

Haz clic en cualquier archivo del árbol y se abre en el modo unificado de lectura/edición: un modo con dos *facetas* — una **faceta de lectura** (el ojo) para revisar, una **faceta de edición** (el lápiz) para cambiar texto.

### 5.1 Completo frente a mini, y cambiar entre todo

Lectura/edición viene en dos tamaños. **Mini** es un panel lateral junto al chat: mantén un documento de referencia al alcance de la mano mientras conversas. (El panel mini omite a propósito la barra de herramientas de revisión — es para leer y hacer ediciones rápidas, no para marcado.) **Completo** ocupa todo el cuadro, para documentos largos y edición seria.

Cambia de tamaño con el botón mini↔completo en la barra del panel. Cambia de faceta con el botón de alternar faceta junto a él. ⌘S guarda en la faceta de edición. Cuando lo que estás viendo es el gemelo de un documento convertido, la barra también nombra el original y lleva un botón de **exportar** para escribir tus cambios de vuelta en él (sección 6.5). Y todo está protegido contra pérdida: si tienes ediciones sin guardar, enough pregunta antes de dejar que algo las descarte — navegar a otro archivo, cerrar el modo, saltar a otro documento. No vas a perder una hora de trabajo por un clic perdido.

Mientras un documento está abierto, tres contadores aparecen en la barra superior y se mantienen al día con lo que escribes: **¶** párrafos, **W** palabras, **C** caracteres. (La vista de lista de la pantalla de inicio te muestra los mismos tres totales para todo un proyecto — sección 2.1.)

Como todo modo a pantalla completa, lectura/edición muestra su icono en el área de indicadores arriba a la derecha, con una pequeña cinta de x roja colgando para cerrarlo (sección 12).

### 5.2 Resaltado

En la faceta de lectura de cualquier documento markdown, selecciona texto y píntalo de uno de cuatro colores — **amarillo, verde, azul, rosa** — desde la barra de herramientas o el menú emergente que aparece sobre una selección. La misma barra ofrece formato ligero: negrita, cursiva, subrayado (⌘B / ⌘I / ⌘U).

Los resaltados son durables, y viven fuera de banda: cada documento obtiene un archivo complementario oculto (`.<filename>.highlights.json`) en vez de marcado insertado en tu texto, así que el documento en sí se mantiene limpio. Una franja de color en el margen marca cada línea resaltada. Los resaltados persisten entre sesiones, y los colores superpuestos se apilan.

Aquí está la parte que cambia cómo trabajas: el agente puede verlos. Su herramienta `read_highlights` lista cada resaltado de un documento por color, y `navigate_to_highlight` salta la vista hasta uno. Eso convierte el resaltado en un canal. Pinta de amarillo los cuatro párrafos que quieres reescribir y de verde los dos que amas, y luego di "reescribe las partes amarillas; conserva el tono de las verdes." Cuando mencionas un color, el agente sabe que te refieres a tus resaltados.

### 5.3 Tipos de archivo compatibles

- **Markdown (`.md`)** se muestra formateado en la faceta de lectura y como código fuente en la faceta de edición. Markdown es la lengua nativa de enough — casi todo lo que el propio sistema escribe es markdown.
- **Texto plano**, y cualquier cosa parecida a texto, se abre en lectura/edición como texto.
- Los archivos **`.girraph`** se abren en modo girraph en su lugar (sección 17).
- Los archivos **`.merirmaid`** se abren en modo merirmaid en su lugar (sección 18).
- Los **artículos de Wikipedia guardados** (`article.html` dentro de una carpeta `wiki/`) se abren en el lector de wikisink con fidelidad completa (sección 10.2).
- Los **documentos de Word, PDF, libros electrónicos, presentaciones, libros de excel** se abren como un **gemelo** editable en markdown — una fila en el árbol, un clic, y un botón de **exportar** en la barra para escribir tus cambios de vuelta. Esa es la sección 6, y es toda la historia.
- Las **imágenes** (`.png`, `.jpg`, `.gif`, `.webp`, `.bmp`, `.svg`) se abren en un visor simple (sección 6.9). Las imágenes *dentro* de un documento se muestran en la faceta de lectura como cualquier otra imagen en markdown.

enough sigue siendo un sistema de texto, y se mantiene como tal: renderiza markdown, no maquetación de página. Lo que hace con todo lo demás es convertirlo — con la suficiente fidelidad como para trabajar en ello, con la suficiente honestidad como para decirte qué no sobrevivió.

---

## 6. Trabajar con PDF, documentos de Word, y otros archivos

enough no renderiza un PDF, no maqueta un documento de Word, ni dibuja una hoja de cálculo, y no finge hacerlo. Lo que hace en su lugar es más discreto y, para el tipo de trabajo que haces aquí, más útil: convierte el documento en markdown que de verdad puedes leer, editar, resaltar, y entregarle a tu agente — y mantiene ese markdown atado al original, para que tus cambios puedan volver.

Nada de esto es un modo separado o una app separada. Haces clic en el archivo. Se abre.

### 6.1 El gemelo

Abre `memo.docx` y enough escribe `memo.docx.md` junto a él. Ese segundo archivo es el **gemelo**: una copia en markdown simple del documento, sentada en tu carpeta de proyecto, tuya para editar como cualquier otra cosa. Crearlo nunca modifica el original.

En el árbol de archivos sigues viendo una sola fila — `memo.docx`. El gemelo, la carpeta de imágenes extraídas del documento (`memo.docx.assets/`), y un pequeño archivo oculto que registra qué se convirtió de qué se pliegan todos en esa única fila, así que tu proyecto sigue viéndose como se ve en Finder. Haz clic en la fila y el gemelo se abre en modo lectura/edición (sección 5) con todo lo que ese modo te da: dos facetas, ⌘S, la protección contra pérdida — y, una vez que pasas a pantalla completa, los resaltados.

Dos consecuencias que vale la pena saber. Los nombres no pueden chocar: un `memo.md` que escribiste tú mismo es un archivo distinto de `memo.docx.md`, y enough nunca los confunde. Y si eliminas `memo.docx` en Finder, nada se rompe — el gemelo se convierte en silencio en un archivo markdown ordinario en tu árbol, que es todo lo que siempre fue.

Tu agente ve lo mismo que tú. Pídele que lea `report.pdf` y obtiene el gemelo, convirtiendo uno primero si todavía no existe; pídele que cambie algo y edita el gemelo, exactamente donde van tus propias ediciones.

### 6.2 Lo que enough puede abrir de esta forma

Esta lista viene de la propia app en vez de un texto que alguien tiene que acordarse de actualizar — si estás leyendo esto fuera de enough, abre el centro de ayuda en la app (sección 9) para verla completa:

{{convert-formats}}

### 6.3 La insignia en el árbol

Todo documento convertible lleva una pequeña insignia en el borde derecho de su fila, y la insignia tiene exactamente un trabajo: decirte si las dos mitades todavía concuerdan.

- **En silencio** — convertido, y ambos lados coinciden. Nada que hacer.
- **Iluminada, en tu color** — editaste el gemelo. Esos cambios están en el markdown y todavía no en el original; exporta cuando estés listo (sección 6.5).
- **Iluminada, en el color del agente** — el original cambió fuera de enough desde que se convirtió. Alguien lo editó en Word; una copia nueva cayó encima; bajó de un disco compartido.
- **Iluminada, en el color de error** — ambas cosas anteriores. Este es el único caso sobre el que enough te va a preguntar, y lo hace (sección 6.7).
- **Hueca** — convertible, aún no convertido. Haz clic y se convierte.
- **Hueca, y al hacer clic explica un extra** — un pdf, presentación, o libro de excel en una instalación que todavía no puede leer esos formatos (sección 6.8).

Pasa el cursor sobre la insignia para lo mismo en una frase. Hacer clic en la insignia hace exactamente lo mismo que hacer clic en el nombre del archivo.

### 6.4 La primera vez que abres uno

La primera vez que abres cada *tipo* de documento, un pequeño modal explica lo que está por pasar — qué es un gemelo, a dónde va, que el original se queda donde está. Un solo botón OK. Es una vez por tipo, no una vez por archivo: tu segundo documento de Word simplemente se abre.

La conversión de un documento de oficina es rápida, muy por debajo de un segundo para cualquier cosa típica. Vas a ver un pequeño aviso en la esquina mientras corre, con un botón de **cancelar** en los lentos. Los PDF tardan más y tienen una barra de progreso honesta (sección 6.8).

### 6.5 Exportar tus cambios de vuelta

Un gemelo abierto lleva un botón de **exportar** en su barra. Un modal, tres decisiones:

**Qué formato.** El propio formato del original viene preseleccionado, y el resto de los destinos de exportación también están ahí — un documento de Word puede salir como PDF, EPUB, o una página HTML autocontenida. Todo lo que el formato no pueda hacer se muestra en gris con la razón, nunca desaparece en silencio.

**Una copia, o el original.** El valor predeterminado es una **copia con fecha** escrita junto al original — `memo-2026-08-19-1042.docx` — y el nombre exacto del archivo se previsualiza en el modal antes de confirmar. Nada está en riesgo: obtienes un archivo nuevo, el viejo no se toca. La segunda opción sobrescribe el original en su lugar, y solo se ofrece cuando el formato al que exportas es el propio del original. Tómala y enough te ofrece un **deshacer** después: conserva el archivo nuevo, o devuelve los bytes viejos, byte por byte.

**Si mantenerlo sincronizado** de ahora en adelante — sección 6.6.

Una palabra sobre qué sobrevive el viaje. Sobrescribir un `.docx` o `.odt` usa el original como referencia de estilo, así que el tamaño de página, las fuentes, y los encabezados y pies de página vuelven junto con tu texto — cosas que markdown no tiene forma de expresar y que de otro modo se perderían. Lo que markdown realmente no puede llevar no vuelve: los cambios rastreados y comentarios (aceptados y descartados al entrar), cuadros de texto, campos, el tamaño preciso de las imágenes. Esa asimetría es la razón por la que la copia con fecha es el valor predeterminado, y por la que enough nunca reescribe un original por iniciativa propia.

### 6.6 Mantener el original sincronizado

Marca **mantener el original sincronizado** en el modal de exportación y cada guardado del gemelo reescribe también el original en silencio. Edita en enough, y el `.docx` en tu disco está al día cada vez que un colega lo pida. Es un ajuste por archivo, se aplica en el momento en que lo marcas, y una pequeña confirmación aparece cada vez que un guardado se completa.

Se ofrece para los formatos que se pueden escribir de vuelta — Word, OpenDocument, Rich Text, EPUB; la columna "mantener sincronizado" de la sección 6.2 es la autoridad. Los PDF no pueden participar, y vale la pena decir la razón sin rodeos: enough puede *escribir* un PDF a partir de markdown, pero recompone el documento desde cero. Un PDF sincronizado reemplazaría tu original cuidadosamente maquetado con una simple recomposición de sus palabras, cada vez que guardaras. Eso no es una sincronización, es una demolición, así que no se ofrece.

### 6.7 Cuando ambos lados cambiaron

El original puede seguir su camino sin ti. Tú editas el gemelo aquí; alguien más edita el `.docx` en Word; ahora hay dos versiones de la verdad.

enough se da cuenta. Compara el original contra lo que registró al momento de la conversión en cada momento que importa — cuando se dibuja el árbol, cuando abres el documento, cuando guardas, cuando exportas — y un archivo que solo fue *tocado* (copiado, respaldado, abierto y cerrado) no cuenta: la comprobación lee el contenido, no solo las marcas de tiempo.

Cuando de verdad ambos lados cambiaron, obtienes un modal con tres opciones en palabras simples:

- **Conservar mi gemelo.** No se escribe nada. La insignia vuelve a "lo cambiaste tú" y decides más tarde.
- **Exportar sobre el original.** Tu markdown gana; el original se reescribe, con un deshacer ofrecido como siempre.
- **Reconvertir desde el original.** El original gana; se escribe un gemelo nuevo — y tu gemelo viejo se guarda aparte como archivo de deshacer en vez de eliminarse.

Ninguna opción de ese modal destruye algo que no puedas recuperar. Esa es la regla de diseño sobre la que está construida toda la función.

### 6.8 Leer PDF, presentaciones y libros de excel: el extra de PDF

Leer un PDF es un problema más difícil que leer un archivo de Word. Un `.docx` todavía sabe qué es un encabezado; un PDF solo sabe a dónde fue a parar la tinta, y sacarle una tabla, una maquetación a dos columnas, o un escaneo requiere modelos de documento de verdad. Esos modelos son grandes, así que no están en la instalación base — están a un clic de distancia en su lugar: **ventana de ui ⚙ → extras → instalar el extra de PDF**.

Lo que cuesta, con honestidad:

- unos **250 MB para descargar**, y cerca de **1 GB en disco** una vez instalado;
- más unos **0.7 GB de pesos de modelo**, obtenidos una vez y guardados en `~/enough/weights/docling/`;
- unos minutos, la mayoría descarga. El instalador transmite su registro a la ventana para que puedas mirar, y los motores se activan en vivo — sin reiniciar.

Lo que obtienes: **PDF**, incluidos los escaneados (el texto se lee de los píxeles mediante OCR); **presentaciones de PowerPoint**, cuyas diapositivas se convierten en secciones con encabezado; y **libros de Excel**, cuyas hojas se convierten en tablas de markdown.

Velocidad, medida y no adivinada, en Apple silicon: cerca de **0.9 segundos por página** para un PDF digital, más una carga de modelo única de **~10 segundos** por conversión. Así que un PDF de una página tarda unos diez segundos, un libro de cien páginas cerca de minuto y medio, y una presentación o libro de excel un par de segundos. Las conversiones largas muestran progreso y se pueden cancelar; cancelar no deja nada atrás — ningún gemelo a medio escribir, ninguna carpeta suelta.

Dos cosas te ahorran un momento de confusión más tarde. Primero: **escribir PDF no necesita nada de esto.** Cualquier gemelo se exporta a PDF en cualquier instalación, con extra o sin extra, porque el compositor que lo hace viene incluido con enough. El extra es para *leer*. Segundo: si el mensaje de "necesita un extra" aparece en una máquina donde estás seguro de haberlo instalado, lee qué frase te salió exactamente — los paquetes y los pesos de modelo son dos descargas separadas, y una conexión que se cortó a medio camino puede dejarte con la primera y no con la segunda. Volver a correr la instalación termina el trabajo y no vuelve a descargar nada que ya tengas.

Las actualizaciones conservan el extra. `update-enough.command` (y `/update-enough`) recuerdan lo que instalaste y lo vuelven a pedir en cada sincronización, así que una actualización de rutina nunca te quita la lectura de PDF en silencio.

### 6.9 Imágenes, y ver el original

Haz clic en una imagen y se abre en un visor simple: ajustada al ancho por defecto, haz clic para cambiar a tamaño real y desplazarte por ella, un patrón de cuadros detrás de cualquier cosa transparente, y el nombre, las dimensiones en píxeles, y el tamaño del archivo en el encabezado. Es de solo lectura. enough no es un editor de imágenes y no tiene ambiciones en ese terreno.

Las imágenes *dentro* de un documento son harina de otro costal, y sí que pasan: la foto de tu archivo de Word se extrae a `memo.docx.assets/` y se muestra en la faceta de lectura del gemelo exactamente como cualquier otra imagen de markdown.

Y cuando el gemelo no basta, la barra de un PDF lleva **ver original**: abre el PDF real en el panel, para que puedas comprobar el gemelo contra la página de verdad. Ciérralo y vuelves al gemelo, donde lo dejaste.

### 6.10 Lo que la conversión te cuesta, en dos frases

Vale la pena nombrar dos límites en voz alta en vez de dejar que los descubras solo. Las hojas de un libro de excel llegan como tablas una tras otra **sin encabezados con el nombre de la hoja** — el lector no los emite, y enough prefiere dejar un vacío antes que inventar una etiqueta. Y una imagen extraída de un PDF recibe el texto alternativo "Image", siempre: no hay ninguna leyenda en el archivo que le dé una mejor.

Más allá de eso, la promesa permanente: **tus originales nunca se modifican a menos que tú lo pidas.** Convertir solo escribe archivos nuevos junto a ellos. Exportar-sobrescribir es el único camino que toca un original, requiere un clic deliberado, y te deja un deshacer.

---

## 7. La carpeta del proyecto y `rness/`

Un proyecto es una carpeta. Cualquier carpeta. enough le añade exactamente una cosa: `rness/`, el cerebro externalizado del agente para este proyecto. Todo lo que el agente es, sabe y recuerda aquí vive en esa carpeta como archivos ordinarios. Puedes leerlo todo, editarlo todo, y ponerlo bajo git si esa es tu costumbre.

La disposición:

```
your-project/
  rness/
    AGENT.md            who the agent is here          (4.1)
    MOTIVATION.md       why it works                   (4.1)
    active-paradigm     which paradigm is in force     (14)
    paradigms/          available reasoning frameworks (14)
    skills/             available skills               (16)
    roles/              available personas             (15)
    policies/           the hard rules                 (4.2)
    knowledge/          project memory                 (7.1)
    io/                 input/output workspace          (7.2)
    requests/           long-running work tracking      (7.3)
  ...your actual files...
```

Las entradas enlazadas simbólicamente (en cursiva en el árbol) siguen los valores predeterminados globales; personaliza cualquiera de ellas para bifurcar una copia local (sección 3.1). Los archivos que sueltas en el proyecto por cualquier medio — Finder, otro editor, el agente — son igualmente visibles para todos en el siguiente turno.

Un documento convertido (sección 6) también añade archivos aquí, siempre junto al original y siempre nombrados en función de él: `memo.docx` obtiene un gemelo en `memo.docx.md`, sus imágenes en `memo.docx.assets/`, y un `.memo.docx.convert.json` oculto que registra qué se convirtió de qué y cuándo. El árbol pliega los tres en la fila del original, pero son archivos ordinarios en tu disco — puedes copiar el par a otra máquina, ponerlos bajo git, o eliminar el gemelo y volver a hacer clic en el original para obtener uno nuevo. El manifiesto oculto es la contabilidad de enough; déjalo en paz y se mantiene exacto. Elimínalo y enough simplemente trata el documento como si nunca se hubiera convertido.

### 7.1 La carpeta de conocimiento

`rness/knowledge/` es la memoria por proyecto.

**`project-profile.md`** es el archivo más útil de la carpeta. Su contenido se inyecta en el system prompt del agente en cada turno: lo que esté escrito aquí está en la memoria de trabajo del agente, sin necesidad de buscarlo. El agente lo mantiene mientras trabajas — preferencias observadas, archivos y personas recurrentes, convenciones que has adoptado, hilos que quedaron abiertos — y tú puedes editarlo directamente. Declara una preferencia permanente una vez en el perfil en vez de repetirla en cada sesión. La política profile-maintenance mantiene el archivo disciplinado: observaciones concretas en vez de etiquetas vagas, destilación en vez de archivo muerto.

**`session-logs/`** contiene un registro markdown fechado de los turnos de cada sesión, más el diario del broker (sección 8). Historial de solo anexado. Explóralo, o hazle grep, cuando necesites reconstruir qué pasó el martes pasado.

Más allá de esos dos, la carpeta es tuya. Añade una subcarpeta `glossary/`, un archivo de lecciones aprendidas, notas de contexto — el agente puede consultar lo que sea que pongas aquí.

### 7.2 La carpeta io

`rness/io/` es el espacio de trabajo de paso:

- **`input/`** — suelta archivos aquí para que el agente los procese. Las páginas web obtenidas también caen aquí automáticamente, convertidas a markdown y en caché, así que una página obtenida una vez queda fundamentada para siempre.
- **`output/`** — donde caen los artefactos generados. Revisa, conserva lo bueno, vacía el resto.
- **`cloud-cache/`** — si usas la ranura de modelo en la nube, cada intercambio con la nube se registra aquí (sección 13.2). Incluso el trabajo en la nube deja un rastro de papel local y rastreable con grep.

### 7.3 Solicitudes: cómo sobreviven los trabajos largos

Este rara vez aparece en los recorridos de inicio rápido, pero es el mecanismo que hace posible el trabajo de varias sesiones, así que vale la pena dos minutos.

Cuando pides algo que va a tomar más de un turno o dos, el agente abre un **archivo de solicitud** en `rness/requests/`: un registro en markdown del objetivo, los puntos de control de progreso, y las decisiones tomadas en el camino. No tienes que pedir esto. Reconocer la forma de una tarea es trabajo del agente.

El archivo de solicitud importa porque las ventanas de contexto se llenan. enough vigila la presión conversacional, y — según la política context-management — el agente guarda un punto de control de su estado en el archivo de solicitud activo antes de que las cosas se desborden. Según tu configuración de orquestador, enough entonces o bien se auto-reinicia (borrando la conversación en memoria y retomando desde cero a partir del punto de control) o se pausa con un aviso para que reinicies cuando estés listo. De cualquier forma, el sistema de archivos es la memoria real, no la conversación: una sesión nueva lee el bloque de Continuación del archivo de solicitud y retoma donde estaban las cosas.

Las solicitudes terminadas se mueven a `rness/requests/done/` — haz clic en **marcar hecha** en una solicitud abierta, o díselo al agente. La carpeta done está protegida contra escritura por parte del agente, y funciona a la vez como un diario honesto de todo lo que ustedes dos realmente han entregado.

---

## 8. La ventana del broker

El broker es el ancla de confianza de enough. Cada llamada a herramienta que hace el agente — cada lectura de archivo, escritura de archivo, comando de shell, y obtención web — pasa por él. La ventana del broker 🔀 es donde observas y ajustas eso.

Once interruptores, en grupos:

| Interruptor | Qué controla |
|---|---|
| trace log | Si el broker siquiera escribe su diario |
| solo modelos locales | Si la ranura de nube (OPRO-API) se ofrece siquiera en el selector de modelo |
| read_file / write_file / shell brokered | Registro de trazas por herramienta, un interruptor cada una — tres en total (las listas de permitidos se aplican *siempre*, pase lo que pase) |
| fetch_url activado | Si la herramienta de obtención web del agente funciona siquiera |
| Tor para obtenciones fuera de lista | Dominios fuera de la lista de permitidos: enrutar por Tor (activado) o negar (desactivado) |
| cachear y convertir obtenciones | Convertir las páginas obtenidas a markdown y guardarlas en caché en `rness/io/input/` |
| herramientas de wikisink | Si las cuatro herramientas de wiki del agente funcionan (tu propia navegación con 🚰 nunca está sujeta a esto) |
| actualizaciones en vivo de wikisink | Si las ejecuciones de actualización pueden contactar a Wikipedia siquiera (desactivado = informe solo desde el estado local) |
| herramientas de cacheawl | Si las herramientas de cachebox del agente funcionan (tu propio modo cacheawl nunca está sujeto a esto) |

Todo viene activado por defecto: los valores predeterminados confían en el agente con el proyecto y lo mantienen honesto con un rastro en papel. Ese rastro — el **diario de trazas** — cae en `rness/knowledge/session-logs/<date>-broker.md`: marca de tiempo, herramienta, decisión, argumentos, resultado, para cada llamada intermediada. Y cuando un interruptor o una lista de permitidos bloquea algo, el agente recibe un mensaje de rechazo claro que dice qué se bloqueó y por qué, para que pueda decírtelo en vez de fallar en silencio.

Fíjate en el principio de diseño de esa tabla: los interruptores que restringen las herramientas del agente nunca restringen *tu* interfaz. Desactivar las herramientas de cacheawl no te deja fuera del modo cacheawl. Significa que el agente no puede meterse en el almacén por su cuenta.

---

## 9. La ventana de ui y los documentos de ayuda

El botón de ui ⚙ abre las preferencias de pantalla y el material de referencia. Un pequeño botón de **ayuda** está en la esquina superior derecha de esa ventana, junto a la ×: abre este manual de solo lectura, en la app, como un modo a pantalla completa igual que cualquier otro (sección 12).

La salida ahora vive en la barra de título: **cerrar proyecto → inicio**, ahí arriba junto al botón de ayuda, que termina esta sesión y te devuelve a la pantalla de inicio (sección 2.5). Pregunta antes de hacerlo, y aclara lo que no hace — la carpeta en el disco no se toca. En la app probablemente irías más bien por ⌘W; este botón es lo mismo, y es el *único* si estás corriendo enough en un navegador. (No está ahí en la propia pantalla de inicio, donde no hay ningún proyecto que cerrar.)

También tiene la única cosa en enough que puedes instalar desde dentro de enough: la fila de **extras** para la **lectura de PDF** (sección 6.8). La fila dice dónde estás parado — no instalado, instalando, instalado, o instalado-pero-no-terminado — y el botón de instalar transmite todo su registro a la ventana mientras corre, así que una descarga larga es algo que puedes mirar en vez de algo que solo esperas. Cuando termina, los PDF empiezan a abrirse; no hace falta reiniciar nada.

### 9.1 Temas

Cuatro vienen con enough: **Enough Default** (violeta azulado oscuro y profundo), **Pastel** (papel pálido, en el espíritu del esquema "Man Page" de Terminal), **Wireframe**, y **Darknest**. Cambiar es instantáneo, y cada icono de la interfaz vuelve a derivar su variante clara u oscura al vuelo.

Los temas no están fijados en el código. Viven en `~/enough/config/ui.json` como bloques nombrados de valores de color, cada uno aplicado como una propiedad personalizada de CSS. Copia un bloque existente, renómbralo, cambia los colores, recarga: tu tema está en el menú desplegable. El bloque `_doc` al principio del archivo explica cada clave.

### 9.2 Fuentes

Mismo patrón. Cuatro conjuntos incluidos — SF Mono, sans-serif del sistema, Georgia serif, Courier — y tus propias adiciones son bienvenidas en el mismo `ui.json`. Para el tamaño, ve los dos diales de abajo (sección 9.3) — y en una pestaña de navegador, el viejo y buen zoom del navegador (⌘+ / ⌘−) sigue funcionando bien encima de ellos.

### 9.3 Tamaño — escala de ui y escala de texto

El zoom del navegador siempre fue la respuesta aquí, hasta que llegó la app de escritorio sin ningún navegador envolviéndola. Así que enough se hizo el suyo propio, y aprovechó la oportunidad para hacerlo aún mejor: dos diales en vez de uno, en la fila debajo del tema.

**escala de ui** redimensiona *todo* — iconos, etiquetas, la barra lateral, el chat, esta misma ventana — en pasos de 0.1×. **escala de texto** redimensiona solo el documento que tienes enfrente: la página en lectura/edición, un artículo de wikisink, la vista previa de archivo, este manual en su modo de referencia. Se multiplican, y no interfieren entre sí: una interfaz a 0.9× con texto a 1.5× es una forma perfectamente buena de leer un manuscrito, y lo contrario es una forma perfectamente buena de encoger uno para que no te estorbe la tarde. Haz clic en cualquiera de los dos números para que ese dial vuelva a 1.0× y dejar el otro tal cual.

Ambos se recuerdan **por carpeta de proyecto** — el manuscrito que lees desde el otro lado del cuarto y las notas que llevas en el escritorio guardan cada uno su propio tamaño, y ninguno arrastra al otro. La pantalla de inicio se queda en tamaño normal, así que los diales no aparecen ahí.

Los límites respiran con tu pantalla: entre 0.5× y 2× más o menos en las pantallas de hoy, estrechándose en una ventana pequeña para que la interfaz siempre conserve espacio suficiente para ser ella misma, aflojándose en pantallas muy grandes y muy densas (la pared 8K de 2046 llega a 3×). Cuando un paso cruzaría el límite, el botón tiembla, el número pulsa en rojo, y nada cambia — ese es todo el mensaje de error.

### 9.4 Idiomas

La interfaz habla seis idiomas: inglés, francés, español, alemán, chino y japonés. El menú desplegable de **idioma de la interfaz** en la misma fila cambia todo lo que estás viendo — etiquetas, tooltips, las burbujas `(?)`, este manual — en vivo, sin reiniciar. La elección es global a la máquina, viajando en `ui.json` igual que el tema, así que inicio y todos los proyectos concuerdan en ello.

Lo que deliberadamente *no* toca: tus archivos, tu chat, tu agente. Habla con el agente en el idioma que te convenga — los modelos locales se sienten cómodos en los seis — pero enough mantiene su propio andamiaje (habilidades, paradigmas, prompts, archivos de proyecto) en inglés, porque ese es el idioma que los modelos leen con más fiabilidad. Unas pocas cosas generadas también se quedan en inglés — listas obtenidas en vivo de lo que está instalado en *tu* máquina, como las habilidades en una burbuja o la tabla de formatos de archivo. Y en cualquier lugar donde una traducción todavía no haya alcanzado a una etiqueta nueva en inglés, vas a ver el inglés en vez de un vacío: menos bonito, nunca roto. ¿Encontraste una? Eso es un error — [enough.support](https://enough.support) lo recibe con gusto.

### 9.5 Chuletas de referencia

Dos columnas de referencia, justo en la ventana de ui.

**Atajos de teclado:**

| Teclas | Acción |
|---|---|
| esc | cerrar el modo abierto más reciente |
| ⌘ \ | mostrar / ocultar la barra lateral |
| ⌘ K | enfocar el campo de chat |
| ⌘ Enter | enviar el mensaje |
| shift Enter | salto de línea en vez de enviar |
| ⌘ B / I / U | negrita / cursiva / subrayado de la selección (faceta de lectura) |
| ⌘ S | guardar (faceta de edición) |
| ⌥ clic | menú contextual del árbol de archivos |

(En un teclado que no es de Mac: Ctrl en vez de ⌘, Alt en vez de ⌥.)

Esos son los atajos que la interfaz misma maneja, así que funcionan igual en la app y en una pestaña de navegador. La app añade dos propios, desde la barra de menú: **⌘W** cierra el proyecto y te devuelve a la pantalla de inicio (sección 2.5) — ya *no* cierra la ventana — y **⌘Q** sale de la app, como siempre lo ha hecho.

**La chuleta de markdown:** encabezados, listas, enlaces, código, citas — toda la referencia rápida, para cualquiera que todavía se esté volviendo fluido en markdown. Lo cual vale la pena, ya que enough lo habla de forma nativa en todas partes.

### 9.6 Ayuda integrada (IHH)

Las burbujas `(?)` repartidas por la interfaz son el sistema de ayuda incorporado: una burbuja por concepto — habilidades, roles, el selector de paradigma, rness, io, conocimiento, cacheawl, wikisink, el sistema de modos, documentos convertidos, y así — cada una con un **qué es**, un **cómo se usa**, y una lista de **ideas**. Las burbujas de habilidades, roles y paradigmas listan lo que realmente está instalado en *tu* proyecto, y la burbuja de documento convertido saca su tabla de tipos de archivo del propio registro de formatos de la app — todo generado en vivo, para que la ayuda nunca se desincronice de la realidad. (La misma tabla aparece en la sección 6.2 de este manual, de la misma fuente.)

Las burbujas se controlan por carpeta de proyecto con la casilla "burbujas de ayuda (?)" en la ventana de ui. Activadas por defecto para una carpeta nueva, y el ajuste se queda pegado por carpeta — así que tu proyecto veterano de todos los días puede quedarse callado mientras un experimento nuevo conserva sus rueditas de entrenamiento.

Hasta la ayuda es personalizable. El contenido vive en un archivo markdown (`enough/static/help-docs.md`); editarlo edita las burbujas.

---

## 10. Wikisink

Wikisink (🚰) pone una copia sin conexión de la Wikipedia en inglés en tu máquina: navegable dentro de la app, buscable a texto completo, legible por el agente, anotable, y actualizable a pedido con un informe de cambios. Después de la configuración no necesita internet en absoluto.

### 10.1 Configuración

Haz clic en 🚰 por primera vez y el asistente pregunta tres cosas.

1. **Tamaño.** Los archivos son compilaciones de Kiwix, solo texto salvo que se indique lo contrario:

   | variante | contenido | tamaño aprox. |
   |---|---|---|
   | top 1M artículos *(predeterminado)* | el millón más leído | ~16 GB |
   | toda la Wikipedia en inglés | cada artículo | ~49 GB |
   | top 50k | los cincuenta mil más leídos | ~2.1 GB |
   | top 50k mini | top ~50k, solo secciones introductorias | ~320 MB |
   | inglés simple | la Simple Wikipedia completa | ~950 MB |

2. **Almacenamiento.** El predeterminado es `~/enough/wikisink`; cualquier carpeta funciona, discos externos incluidos. Deja cerca de un 5% de margen más allá del tamaño del archivo.
3. **Confirmación.** La descarga es reanudable y sobrevive a los cierres — pausa, reanuda, o cancela desde la misma ventana mientras el resto de enough sigue funcionando.

El archivo es un único archivo `.zim` leído en su lugar. Nunca se extrae, y nunca abarrota tu gestor de archivos. Puedes registrar **varias instalaciones** — digamos, el archivo completo en un disco externo más uno pequeño en el disco interno — y cambiar entre ellas en la lista de instalaciones de ⚙. Un disco desconectado no rompe nada: esa instalación se muestra como inalcanzable hasta que el disco vuelve, y tus comentarios y anulaciones viven independientemente de cualquier archivo individual.

Una vez instalado, 🚰 abre el lector: atrás y adelante, sugerencias de título en vivo en el cuadro de búsqueda (Enter ejecuta una búsqueda de texto completo sobre todo el archivo), un dado 🎲 de artículo aleatorio, y una insignia de fuente que te dice si estás leyendo la instantánea del archivo (`ZIM <date>`), una copia más fresca de una ejecución de actualización (`live <date>`), o una copia preservada (`preserved`). Los enlaces internos se quedan dentro de la app; los enlaces externos se abren en tu navegador. La píldora de chat de abajo entrega el artículo actual — o tu pasaje seleccionado — directo al agente.

**La píldora de instantánea más nueva.** Kiwix reconstruye estos archivos periódicamente, y no deberías tener que andar buscando eso. Cuando existe una versión más nueva de *tu* variante, aparece una pequeña píldora en la barra de herramientas del lector — `newer snapshot: <date> · <size>`. Haz clic, confirma el tamaño, y la actualización corre en el mismo lugar: la misma carpeta de almacenamiento, descargada primero e intercambiada solo cuando termina, el archivo viejo eliminado después de eso y no antes. Tus comentarios, guardados, y anulaciones 🛡 pasan intactos, porque ninguno de ellos vive dentro del archivo. La píldora se convierte en el indicador de progreso mientras descarga, y luego desaparece. enough revisa esto como mucho una vez al día, nunca mientras el lector está renderizando, y se queda callada cuando estás sin conexión — que es el estado normal de una función de Wikipedia sin conexión. La misma actualización está disponible por el camino largo, en la lista de instalaciones de ⚙, y las ejecuciones de wikisink del agente también la reportan (sección 10.3) — pero apretar el botón siempre es decisión tuya.

### 10.2 Guardar y bloquear artículos

**Guardar.** El botón de guardar ofrece dos destinos: la carpeta `wiki/` de este proyecto, o el cachebox de wiki global a la máquina (`~/enough/cacheawl/wiki/`) compartido por todos los proyectos. De cualquier forma, un guardado es una carpeta — `article.html`, el artículo byte por byte tal como lo tenía el archivo, más `_manifest.md` que lleva el título, la url de origen, la fecha de obtención, y la línea de licencia CC BY-SA. Cada artículo guardado se describe a sí mismo, lo que significa que si su texto alguna vez termina en algo que publicas, la atribución que necesitas ya está sentada justo al lado. Haz clic en un `article.html` guardado en el árbol y se abre en el lector con fidelidad completa — infoboxes, tablas y todo — incluso cuando no se puede alcanzar ningún archivo. Para dejar de guardarlo, pasa el cursor sobre la carpeta guardada en el árbol y haz clic en el 🗑 que aparece.

Guardar es para *ti*: copias doblemente sin conexión, atribución para publicar. El agente no necesita los guardados — sus herramientas leen cualquier artículo del archivo como texto limpio a pedido.

**Comentarios.** Selecciona texto y pulsa 💬, o usa el 💬 de la barra de herramientas para una nota a nivel de párrafo. Los hilos viven en el panel 🗨: responder, resolver, reabrir, saltar. Los comentarios se adjuntan al *artículo*, no a ningún archivo, y sobreviven a las actualizaciones del artículo degradándose con elegancia. El texto que sigue presente se queda **anclado**. El texto que fue editado y desapareció se **reancla** a su párrafo. Un párrafo eliminado por completo deja el comentario **huérfano** en el panel — etiquetado, pero nunca eliminado automáticamente.

**Bloqueo (anulaciones de borrado).** A veces la Wikipedia en vivo elimina un artículo del que dependías; el caso clásico es un tema de nicho cortado por "relevancia" en vez de calidad. El botón 🛡 preserva tu copia local para siempre — servida de ahí en adelante con una insignia `preserved`, excluida de futuras actualizaciones, y aún buscable. Los informes de las ejecuciones de actualización de hecho puntúan los borrados detectados (las justificaciones con sabor a "relevancia" puntúan como sospechosas; las de violación de derechos de autor puntúan como benignas), así que sabes qué borrados merecen una mirada. Y anular es deliberadamente decisión tuya y de nadie más: el agente puede recomendar 🛡, pero nunca puede apretarlo él mismo.

### 10.3 La actualización de wikisink, con informe de cambios

"Wikisink" también es un verbo. Cada artículo que has guardado o comentado está *vigilado*, y pedirle al agente que "ejecute un wikisink" (o dejar que invoque su herramienta `wikisink`) revisa el conjunto vigilado contra la Wikipedia en vivo e informa de vuelta. Una ejecución:

1. refresca los artículos vigilados que cambiaron hacia una capa local (su insignia cambia a `live`);
2. señala **picos de edición** — artículos vigilados que de repente se editan docenas de veces al día, más candidatos a oleada a nivel de toda Wikipedia;
3. compara los **rankings diarios de las 1000 páginas más vistas** contra la última ejecución: los que suben, los que bajan, las entradas nuevas, las bajas, y las tendencias de vistas de tus artículos vigilados;
4. revisa si hay **borrados** de artículos vigilados o vistos recientemente, puntuados por sospecha (sección 10.2);
5. anota cuándo hay disponible una **instantánea base más nueva**. Reemplazar el archivo base de varios GB siempre es decisión tuya — aprieta la píldora en la barra de herramientas del lector (sección 10.1) o usa la lista de instalaciones de ⚙. No hay ninguna herramienta del agente que lo intercambie.

El informe llega al chat como markdown; la versión completa sin recortar se guarda en la carpeta de estado de wikisink. Las ejecuciones son corteses con Wikipedia — por lotes, con un User-Agent honesto — y reanudables si se interrumpen, y una ejecución `report-only` se salta el paso de refresco. Dos interruptores del broker gobiernan todo esto: uno restringe por completo las herramientas de wiki del agente, el otro puede forzar que las ejecuciones sean completamente sin conexión.

---

## 11. Cacheawl

Cacheawl es el almacén de texto global a la máquina: el lugar para las cosas que quieres conservar para siempre y alcanzar desde cualquier proyecto. Vive en `~/enough/cacheawl/`, oculto del árbol de archivos de cada proyecto, compartido entre todas tus instancias de enough. (Si corriste una versión anterior de enough, tu antigua biblioteca `infoworld/` se disolvió dentro de cacheawl en el primer lanzamiento de 0.1.6 — `personal/`, `public/`, y `wiki/` se convirtieron en tus primeros tres cacheboxes. No se perdió nada.)

### 11.1 Los cacheboxes y sus diagramas merirmaid

Un **cachebox** es una carpeta de nivel superior en el almacén, y viene en dos variantes. Las **cajas simples** guardan texto conservado para siempre que tú mismo organizas: una caja `personal` de notas de referencia, una caja `press` de piezas publicadas, la estructura que sea que te sirva. Las **réplicas en caché** son cajas *ingeridas* desde una fuente — una carpeta local, un sitio web, o un conjunto de artículos de Wikipedia — que recuerdan de dónde vinieron.

Cada caja lleva un **diagrama merirmaid**: `_cachebox.merirmaid`, un diagrama en vivo de la estructura de la caja, regenerado cada vez que el contenido cambia. Haz doble clic para ver la forma de una caja de un vistazo. El diagrama es un *espejo*, de solo lectura por diseño, porque refleja la realidad — para cambiar el diagrama, cambia la caja. Una pasada barata de reconciliación mantiene los espejos honestos incluso cuando sueltas archivos desde Finder a espaldas de enough.

Abre el **modo cacheawl** desde la barra superior para una vista de dos paneles, proyecto de un lado, almacén del otro. Arrastra un archivo de un lado a otro para copiarlo. Shift-arrastra para moverlo. Shift-clic para un menú contextual, y doble clic para abrir cualquier archivo en su modo natural — girraph, merirmaid, lectura/edición, o el lector de wiki — directo desde el almacén.

### 11.2 El cachebox y capturar documentos locales o web

La **barra de ingesta** en modo cacheawl (o un simple pedido conversacional) captura material externo hacia una caja:

- **Una ruta local** — replica una carpeta de notas o documentos hacia el almacén.
- **Un sitio web** — rastrea un sitio de documentación o de referencia hasta una profundidad elegida (con un tope de unas 500 páginas) y lo guarda como markdown local. Las ingestas web respetan tus interruptores de obtención y tus listas de permitidos, enrutamiento por Tor incluido.
- **Wikipedia** — saca los artículos de un tema (con un tope de unos 200) de tu archivo de wikisink hacia texto permanente e independiente del proyecto.

Las ingestas corren en segundo plano. La caja aparece de inmediato con un estado de "ingiriendo" que puedes observar, y una ingesta fallida lo dice en vez de fingir que terminó. Las herramientas de cachebox del agente (listar, crear, ingerir) están sujetas al interruptor del broker de cacheawl; tu propio uso del modo cacheawl nunca lo está.

¿Para qué molestarse? Porque las carpetas de proyecto son espacio de trabajo y cacheawl es espacio de biblioteca. Ingiere la documentación de un framework una vez, y cualquier proyecto futuro puede fundamentarse en ella sin conexión. Guarda tus notas de referencia perennes en una caja, y cualquier agente con el que hables alguna vez puede alcanzarlas. Termina un artefacto y muévelo a una caja, donde sobrevive a su proyecto.

---

## 12. Apilamiento de varios modos activos

Los modos a pantalla completa de enough — lectura/edición, girraph, merirmaid, wikisink, cacheawl — no se reemplazan entre sí. Se **apilan**, como hojas de papel. Abre cacheawl, abre un girraph desde dentro de una caja, abre un archivo de notas sobre eso: tres modos de profundidad, y cerrar cada uno revela el que está debajo exactamente como lo dejaste. Misma posición de scroll, mismo descenso, mismas ediciones sin guardar.

La barra superior muestra un indicador cuadrado por cada modo abierto, el más nuevo a la izquierda. Cada uno lleva una pequeña cinta de x roja que cierra ese modo específico, incluso uno enterrado. Haz clic en el indicador de un modo enterrado para subirlo hasta arriba sin molestar nada más. Esc siempre cierra el modo superior. Cuando se cierra el último, vuelves a la vista de conversación — la pila vacía (sección 4).

Dos comodidades que vale la pena saber:

- El panel mini de lectura/edición flota *encima* de un modo a pantalla completa, así que puedes mantener un documento al alcance de la mano mientras trabajas en, digamos, modo girraph por debajo.
- Abrir un modo que ya está en algún lugar de la pila no lo duplica. Reapunta y sube el que ya tenías.

---

## 13. La ventana de modelo

La insignia de modelo en la barra superior abre la ventana de modelo: qué cerebro te está respondiendo, qué más está disponible, y — si tú eliges — la ranura de nube.

### 13.1 Modelos locales: panorama y recomendaciones de uso

Siete modelos locales compatibles — y la ventana es ahora también donde los instalas. Cada fila que todavía no tienes muestra su tamaño de descarga y un veredicto de viabilidad calculado contra la memoria y el disco libre de *esta máquina*: ✓ cómodo, ~ ajustado, ✗ no recomendado. Las descargas corren con una barra de progreso en vivo, sobreviven a un cierre (retoman donde se quedaron), y se pueden cancelar sin perder la parte que ya tienes. Los modelos instalados cambian con un clic, y cualquier modelo salvo el activo se puede eliminar desde su fila cuando quieras recuperar el disco.

| apodo | modelo | disco | RAM mín. | notas |
|---|---|---|---|---|
| **G40-04** | Gemma 4 4B (E4B) | ~5.4 GB | 8 GB | el más pequeño; cabe en cualquier lado; el predeterminado |
| **Q35-09** | Qwen3.5-9B | ~5.9 GB | 10 GB | tamaño medio equilibrado; decodificación especulativa MTP |
| **G40-12** | Gemma 4 12B (QAT) | ~7.0 GB | 12 GB | entrenado con reconocimiento de cuantización; el punto justo de los 16 GB |
| **G40-26** | Gemma 4 26B MoE (4B activos) | ~15.6 GB | 20 GB | calidad de modelo grande a velocidad de modelo mediano |
| **Q36-27** | Qwen3.6-27B denso | ~17.1 GB | 22 GB | el peso pesado con experiencia; MTP; piernas largas |
| **Q38-04** | Qwen3.8 27B (4 bits) | ~19 GB + 1.7 draft | 24 GB | el Qwen más nuevo; redacta su propia especulación |
| **Q38-16** | Qwen3.8 27B (16 bits) | ~54 GB + 3.2 draft | 64 GB | precisión completa, para los Mac más grandes |

Una arruga de nomenclatura, para que nunca te haga tropezar: en los dos nombres Q38, el número después del guion es el **ancho de cuantización**, no la cantidad de parámetros — Q38-04 y Q38-16 son el *mismo* modelo de 27 mil millones de parámetros, en precisión de 4 bits y de 16 bits. (G40-04, de la convención más antigua, sí es de verdad un modelo de 4 mil millones de parámetros.) Las etiquetas en la ventana lo explican con detalle para que los apodos nunca tengan que hacerlo.

Reglas generales. En una máquina de 8–16 GB, vive con G40-04, y haz de G40-12 tu mejora una vez que tengas margen — el entrenamiento con reconocimiento de cuantización le da una salida inusualmente limpia para su tamaño. Con 32 GB, G40-12 o Q35-09 es un caballo de batalla diario cómodo, con G40-26 o Q38-04 para el trabajo de síntesis más difícil. Con 64 GB en adelante, Q38-04 o Q36-27 como tu predeterminado, y deja de pensarlo. Q38-16 es su propia categoría: el peso pesado de precisión completa para máquinas con memoria unificada de verdad y ~57 GB de disco de sobra — si tienes un Mac Studio y quieres el techo, este es el techo. Las ventanas de contexto escalan con tu RAM automáticamente — cada modelo viene con un predeterminado sensato por nivel de RAM, sobrescribible en la configuración — y las compilaciones de Qwen llevan Predicción Multi-Token para velocidad extra gratis: incorporada en el archivo del modelo para Q35/Q36, y mediante un pequeño archivo complementario "draft" para el par Q38, que se descarga junto con él automáticamente.

Una nota más para las instalaciones de terminal: un modelo se puede *descargar* en cualquier llama.cpp pero solo se puede *ejecutar* en una compilación suficientemente reciente. Si la tuya es demasiado vieja para un modelo nuevo, la ventana lo dice y nombra la solución (`brew upgrade llama.cpp`). Las instalaciones de la app nunca ven esa nota — la app trae su propio motor de inferencia.

Cambiar de modelo reinicia el servidor de inferencia local y borra la conversación en memoria. Tus archivos, registros, y el estado de las solicitudes persisten todos; un cambio te cuesta el historial de scroll del chat, no el trabajo.

### 13.2 Soporte de OpenRouter (la ranura OPRO-API)

enough es local primero, no local únicamente. Una quinta ranura de modelo, **OPRO-API**, enruta a través de OpenRouter hacia modelos en la nube. Está desactivada por defecto, deliberadamente laboriosa de activar, y honesta sobre el intercambio: tus prompts y resultados salen de la máquina, a cambio de capacidad de modelo de frontera y, a veces, menor costo que el hardware y la electricidad que exigiría un modelo local comparable.

Activarla: desactiva **solo modelos locales** en el broker, y luego haz clic en OPRO-API en la ventana de modelo. Un asistente de tres pantallas te guía: tres casillas de confirmación explícitas (tienes una cuenta, entiendes la facturación, entiendes el intercambio de privacidad), luego tu clave de API, luego una verificación de estado en vivo. La clave se guarda en el Llavero de macOS. Nunca se escribe en ningún archivo, el agente no tiene forma de leerla, y el broker rechaza los comandos de shell que siquiera parezcan intentos de acceder a ella. Una vez verificada, OPRO-API se vuelve seleccionable como cualquier otro modelo, y su panel de ajustes ofrece volver a probar, actualizar la clave, eliminar la clave, y tu elección de cualquier id de modelo de OpenRouter.

Dos cosas mantienen responsable el uso de la nube:

- **Todo se guarda en caché localmente.** Cada intercambio con la nube se escribe en `rness/io/cloud-cache/` con conteos de tokens y un índice — un rastro de papel local que tu agente local puede leer después.
- **`cloud_pipeline`** permite que el agente procese trabajos grandes por lotes a través de la ranura de nube — hasta 200 pasos, con caché por paso, resumen opcional por paso, y una pasada final de compilación — escribiendo los resultados en disco en vez de inundar la conversación. Pide "un cloud pipeline que redacte los doce resúmenes de capítulo" y el trabajo pesado ocurre fuera de banda, completamente registrado.

---

## 14. Paradigmas

Un paradigma es el marco de razonamiento del agente — las reglas de juego de cómo ocurre el trabajo. Hay exactamente uno activo a la vez (se muestra en lo alto de la barra lateral; haz clic en ● para cambiar), y el texto completo del paradigma activo viaja en el system prompt en cada turno. El agente también ve un catálogo de una línea de los demás, así que puede sugerir un cambio — o hacerlo — cuando tu pedido se atendería mejor en otro lugar. Un cambio iniciado por el agente no tiene nada de exótico: escribe el nombre del paradigma en `rness/active-paradigm` y te dice que lo hizo.

### 14.1 default

Conversación libre de un solo agente. El paradigma para la mayoría del trabajo, y el enrutador que vigila los momentos en que otro paradigma encaja mejor. También lleva las convenciones permanentes — como saber que "las partes amarillas" significa tus resaltados.

### 14.2 text-planning

Para la larga pista de despegue antes de la prosa: llevar una novela, una colección de ensayos, un libro de no ficción, o un manifiesto desde "creo que quiero escribir algo" hasta un plan utilizable. El agente construye un documento de plan contigo en la raíz del proyecto — con paciencia, de forma iterativa, a lo largo de tantas sesiones como haga falta — y luego, a pedido, genera *andamios* por sección: guías estructurales (beats, encabezados, recordatorios de voz, presupuestos de palabras) que tú expandes en prosa por tu cuenta. La regla que define al paradigma: **nunca escribe tu prosa.** Los andamios contienen solo estructura. Tu voz se queda siendo tu voz. (Se activa junto con la habilidad `analyzer` o `memoir-dialectic`; las memorias se le pasan a memoir-dialectic, que está construida específicamente para ellas.)

### 14.3 translation

Declara la traducción sin conexión como una capacidad de primera clase. Se combina con la habilidad `translator` (sección 16.5): cuando un pedido implica mover texto entre idiomas humanos, el agente cambia aquí, y si la habilidad está desactivada te dice lo que te estás perdiendo — y te lo sigue diciendo hasta que la actives. Con la habilidad activada, tienes un traductor local de ~419 idiomas sin cuenta, sin límite de tasa, y sin dependencia de red.

### 14.4 workflow-design

El paradigma sobre enough mismo, activo cada vez que estás creando o cambiando el flujo de trabajo en vez de trabajar dentro de él: habilidades nuevas, roles nuevos, paradigmas nuevos, ediciones a AGENT.md o MOTIVATION.md. Aquí el agente se comporta como un colaborador reflexivo en el diseño — preguntas aclaratorias antes de construir (¿alcance? ¿nombre? ¿condiciones que lo disparan?), alternativas cuando tu primer instinto podría ser más afinado, y un archivo de solicitud rastreado para cada construcción, ya que los cambios de flujo de trabajo sobreviven a las conversaciones que los producen. Este es el paradigma que hace real la sección 3.

---

## 15. Roles

Un rol es una segunda personalidad que puedes invocar en la conversación: su propio `AGENT.md` y `MOTIVATION.md`, el mismo patrón de dos archivos que define a tu agente principal, acotado a un personaje complementario — o deliberadamente adversario. Activa roles por proyecto en la barra lateral. Los roles activados viajan en el system prompt, y los invocas por nombre ("¿qué diría open-skeptic de este plan?").

### 15.1 block-breaker

Un especialista en bloqueo de escritor, destilado a partir de las respuestas de un escritor real sobre cómo disuelve el estar atascado. Diagnostica antes de prescribir — sin ideas, sin nervio, sin estructura, y sin permiso son cuatro problemas distintos — y luego recurre a restricciones, lluvia de ideas basada en repeticiones ("diez variaciones, y luego recorta"), reencuadres raros, y, cuando se le pide, oraciones siguientes de verdad. Implacablemente anti-derrotista. Su creencia central: para cualquiera que escribe voluntariamente, el bloqueo siempre se puede resolver, porque las reglas se inventaron y la cura también se puede inventar.

### 15.2 open-skeptic

Un "agorero abierto a la luz": genuinamente entusiasta sobre la IA donde es fuerte, profesionalmente suspicaz donde está sobrevendida. Invócalo cuando estés por construir un flujo de trabajo y quieras que se nombren los modos de falla temprano. Se resiste a pedirle a la IA que replique la experiencia humana, a las cadenas de error acumulativo sin revisión humana, y a la confianza fluida haciendo el trabajo de la pericia — mientras aplaude a la IA como motor de recopilación, prótesis de conocimiento, y compañera de ensayo. Se actualiza con la evidencia: muéstrale un flujo de trabajo que funciona y lo dice, sin rodeos.

### 15.3 Hacer el tuyo propio

Dos ejemplos, un patrón — instrucciones más motivación, en dos archivos markdown. Los roles son la forma más barata de añadir una voz que te falta: un pato de goma socrático, un revisor de cumplimiento, una personalidad de lector para tu público objetivo, un experto en un campo alimentado con tus propios archivos de conocimiento. Pide uno en el paradigma workflow-design y el agente te va a entrevistar y escribir ambos archivos.

---

## 16. Habilidades

Una habilidad es un paquete de capacidad especializada: una carpeta con un `SKILL.md` (más documentos de referencia y scripts opcionales) que le enseña al agente un procedimiento, un vocabulario, o una disciplina. Activa las habilidades por proyecto en la barra lateral. Desactivada significa de verdad desactivada — ni siquiera está en el prompt — y las habilidades nuevas llegan desactivadas, así que nada cambia a tus espaldas. Una habilidad que enough no incluyó de fábrica se lee antes de que se pueda activar siquiera (sección 16.6). Desactivarlo todo también es legítimo: conversación pura, sin andamiaje, a veces más espacio para que el modelo te sorprenda.

### 16.1 analyzer

Cuatro modos analíticos en una sola habilidad.

**Summarize** (resumir) produce un digest de una página, equilibrado, de cualquier texto: qué dice, para quién es, la motivación y los sesgos del autor, el tono, citas clave.

**Proofread** (corregir) hace corrección de estilo ligera — erratas, ortografía — a lo largo de documentos completos, hasta libros enteros, impulsado por Harper, un corrector gramatical local basado en reglas. También produce un informe de corrección separado con sugerencias y hallazgos de frases repetidas, así los arreglos silenciosos y las decisiones de criterio se mantienen distinguibles.

**Decide** (decidir) le entrega tu dilema a tres personalidades arquetípicas de una lista incorporada de diez, que lo debaten con todo registrado. Obtienes una recomendación *y* la transcripción, así que puedes sopesar el razonamiento en vez de solo confiar en un veredicto.

**Audit** (auditar) lee algo que todavía no has decidido si confiar — una habilidad que alguien te mandó, un rol, un paradigma — y te dice qué es. Primero una explicación en lenguaje llano de qué hace realmente la cosa y por qué la querrías, luego una pasada de seguridad: intentos de inyección de prompts, instrucciones que amplían el alcance del agente en silencio, señales de alerta epistémicas, y cualquier código incluido, que también recibe un escaneo determinista que no involucra ningún modelo en absoluto. El veredicto es una de tres palabras — **pass** (aprobado), **flag** (marcado), **fail** (fallido) — respaldado por hallazgos con nombre, nunca un puntaje. Es de solo lectura: audit nunca ejecuta, edita, instala, o activa lo que está leyendo.

Los informes llegan a `rness/io/output/analyzer/audits/<skill-name>/`: un `.md` fechado que puedes leer como cualquier otro archivo, más un pequeño `verdict.json` al lado. Pide una auditoría por nombre cuando quieras — "revisa esto antes de que lo active", "qué hace realmente esta habilidad" — y enough también corre este modo por ti, sin que se lo pidas, la primera vez que activas una habilidad que no vino de fábrica. Las dos puertas escriben el mismo informe a la misma carpeta. La sección 16.6 tiene esa historia.

### 16.2 anything-finder

Una partida de búsqueda para las cosas que no aparecen en la primera página. Tres caras, una habilidad.

**find** es la predeterminada, y lleva un manual de estrategias para cada uno de diez tipos de cosas difíciles de encontrar, más una undécima para misiones que se estancan. **Textos** — libros de dominio público, poemas, documentos históricos. **Video** — cine y TV raros, perdidos, y descatalogados, con enlaces para ver y su legalidad indicada. **Imágenes** autorizadas para una portada o un fanzine. **Productos** — equipo oscuro, sintetizadores, instrumentos, y dónde realmente comprar uno. **Artículos** — el paper atrapado detrás de un muro de pago, encontrado como su copia abierta legítima: preprint, repositorio, archivo. **Código** — repositorios con licencia permisiva, incluidas bibliotecas que nunca pasaron por GitHub. **Libros** — recomendaciones parecidas a lo que ya amaste. **Audio** — partituras, MIDI, samples, manuales de equipo. **Recursos** — fuentes tipográficas, texturas, modelos 3D, metraje de stock. **Datos** — conjuntos de datos, APIs públicas, documentos gubernamentales, archivos de periódicos.

Los resultados vuelven como *find cards* (tarjetas de hallazgo): el enlace, por qué es el ítem correcto, y — para cualquier cosa sensible en derechos de autor — por qué es seguro usarlo, con la fecha de publicación o la licencia explícita detalladas. Pídele "encuéntrame una edición de dominio público de *La piedra lunar* lo bastante limpia para maquetar", "dónde puedo ver legalmente la versión de 1974", "hay alguna biblioteca con licencia MIT que haga esto". Las respuestas honestas son parte del trato: "esto existe pero no está disponible legalmente" y "tres candidatos, tengo un 70% de confianza en el segundo" son resultados reales aquí, y donde la única ruta es un sitio de piratería lo va a decir y en su lugar te va a dar la biblioteca, el sistema de préstamo, o la tienda.

**patents** es la cara de arte previo. Dale una invención y ejecuta una búsqueda de novedad estructurada a través de patentes concedidas, solicitudes publicadas, y la literatura no-patente, y luego reporta qué encontró y qué significa eso para la novedad y la no obviedad — con un descargo de "esto no es asesoría legal" que se mantiene en cada informe, porque eso es exactamente lo que es. "¿Ya está patentado esto?" "Arte previo sobre un candado de bicicleta magnético que…" "¿Es patentable mi idea?" Las bases de datos que no pudo alcanzar vuelven etiquetadas como *sin revisar*, nunca en silencio como *vacías*.

**venture** es la cara de "¿esto es un negocio?", y combina las otras dos. Un barrido de mercado de lo que ya existe, una revisión de arte previo, y una pasada de panorama competitivo sobre empresas, alternativas de código abierto, productos adyacentes, y el cementerio de los que lo intentaron y cerraron. Lo que obtienes es una lectura equilibrada — qué está saturado, qué es adyacente, qué está genuinamente abierto, y la cuña que la evidencia realmente respalda — seguida por el caso más fuerte *a favor* y el caso más fuerte *en contra*, cada punto anclado a un enlace, y una lista corta de preguntas que solo tú puedes ir a responder. Pídele "¿debería construir esto?", "¿esto ya existe como producto?", "¿dónde está el hueco de mercado aquí?". No va a puntuar tu idea, ni escribir tu plan de negocios, ni decirte que levantes capital. Y trata un campo vacío como una pregunta, no como luz verde.

La salida va a `rness/io/output/anything-finder/`. Todo lo que obtiene pasa por el broker como cualquier otro acceso web, así que un dominio fuera de la lista de permitidos se enruta por Tor — y cuando una fuente se niega a responder, el informe nombra el host y te dice qué añadir a `allowlists.md`, en vez de dejar un hueco silencioso en los resultados.

### 16.3 girraph-merirmaid

La habilidad de disciplina para las dos primitivas de diagrama de enough (secciones 17 y 18). La mitad de girraph enseña mapeo IBIS apropiado: una pregunta por turno, sin saltar a soluciones, tu confirmación como regla de parada. La mitad de merirmaid lleva las reglas de autoría de Mermaid, como mantener las etiquetas de nodo lo bastante cortas para que puedas editarlas cómodamente. Los modos funcionan sin la habilidad; con ella, el agente se convierte en un compañero de mapeo genuinamente disciplinado.

### 16.4 memoir-dialectic

Un colaborador de memorias paciente, de varias sesiones. Te entrevista — una o dos preguntas a la vez, nunca una inundación — y archiva todo: documentos de plan numerados en orden de conversación, un índice para retomar rápido, un archivo de notas para volcados mentales desordenados, y eventualmente una síntesis de esquema y, solo si lo quieres, borradores. La carpeta es la memoria. Puedes desaparecer por semanas o años y retoma donde lo dejaste. Construido para todo el rango, desde una historia de vida completa hasta un solo hito, con manejo explícito de temas sensibles y zonas prohibidas, y preservación cuidadosa de tu propia forma de hablar — la voz importa, especialmente si se viene un borrador.

### 16.5 translator

Traducción sin conexión a través de ~419 idiomas mediante MADLAD-400 — una descarga única de ~3 GB que corre en CPU o Apple Silicon y nunca llama a casa. Desde frases cortas hasta documentos completos, desde idiomas principales hasta idiomas indígenas y de pocos recursos. Traduce una carta, localiza un README, comprueba qué significa un pasaje, haz un viaje de ida y vuelta de una frase a través de un tercer idioma como prueba de preservación de sentido — todo con la red desconectada. Para ciertos idiomas de pocos recursos, un motor opcional NLLB-200 ofrece mayor calidad; lleva una licencia no comercial, así que se activa voluntariamente a través del paradigma de traducción.

### 16.6 Escribir la tuya propia, y confiar en las de otras personas

Las cinco de arriba son demostraciones. El *mecanismo* de habilidad — instrucciones en markdown, cargadas cuando se activan, con un `description:` que le dice al agente cuándo intervenir — es la función real. Guías de estilo propio, listas de verificación de un campo, formatos de informe recurrentes, procedimientos de manejo de datos: si puedes describir una competencia en prosa, se la puedes entregar a tu agente como una habilidad. Construye la tuya con workflow-design (sección 14.4), o bifurca una de las cinco y hazla tuya.

El otro extremo de ese bucle son las habilidades que llegan de algún otro lado. Una habilidad son instrucciones que tu agente va a seguir, lo que significa que una habilidad de internet merece exactamente tanta sospecha como cualquier otro archivo de internet. Así que enough las lee por ti:

- **Lo que enough incluye de fábrica es de confianza, y siempre lo ha parecido.** Las cinco de arriba llegan como enlaces hacia los propios valores predeterminados de la instalación. Se activan al instante. Nada las audita.
- **Todo lo demás está desactivado hasta que se haya leído.** Suelta una carpeta de habilidad en `rness/skills/` — descargada, mandada por un amigo, descomprimida de un `.skill` — y se queda ahí desactivada, marcada como *sin verificar* en la barra lateral. La primera vez que la activas, enough corre el modo de auditoría de analyzer sobre ella (sección 16.1) antes de que una sola palabra le llegue al agente. Lo ves pasar en la fila: *sin verificar* → *auditando…* → *auditada*.
- **Marcada significa no activada.** Si la auditoría encuentra algo, la fila dice *marcada* (o *fallida*), la habilidad se queda desactivada, y obtienes dos botones: **leer informe** abre el informe completo en la vista de lectura, y **activar de todos modos** te pide confirmar y luego registra la decisión como tuya — el hallazgo no se borra, se anula, y la fila desde entonces dice *confiada por ti*. La auditoría aconseja. Tú decides. (Si prefieres trabajar en el archivo, editar el `verdict.json` de esa habilidad a `"verdict": "pass"` hace lo mismo.)
- **Edita una habilidad y se vuelve a leer.** La auditoría está atada a los bytes exactos que leyó — tanto los nombres de archivo como el contenido. Cambia cualquier cosa y la próxima vez que actives esa habilidad, se audita de nuevo. Eso incluye una que hubieras activado de todos modos antes: una anulación describe un conjunto particular de archivos en un momento particular, y no sobrevive a una edición.
- **Las habilidades que tu agente escribe para ti también cuentan como no confiables.** Eso es deliberado, no un descuido. Cuando workflow-design escribe un `SKILL.md` nuevo en `rness/skills/`, el agente audita su propia tarea al activarla por primera vez. Es casi instantáneo cuando no hay nada que encontrar.
- **Sin ningún modelo corriendo, una auditoría no puede terminar** — y lo dice, marcando con "la mitad de la auditoría que usa el llm no pudo correr" en vez de dejar pasar la habilidad sin más. Enciende un modelo y activa de nuevo, o usa *activar de todos modos* si ya sabes qué hay ahí.

Los informes viven en `rness/io/output/analyzer/audits/<skill-name>/` — la misma carpeta en la que escribe analyzer cuando pides una auditoría en la conversación. Dos puertas, un documento, y es un archivo markdown ordinario que puedes abrir, conservar, o eliminar.

---

## 17. El modo girraph y la extensión `.girraph`

Se pronuncia "graph" (como en inglés). La "ir" es muda — corresponde a *iterative* y *recursive* (iterativo y recursivo). El animal es un 🦒, y el animal también es mudo.

Un girraph es un mapa de una pregunta difícil. No una lista de tareas: una imagen de un *desacuerdo*, incluidos los productivos que tienes contigo mismo. Algunos problemas ("¿Deberíamos educar en casa?", "¿De qué trata realmente este libro?", "¿Aceptamos el financiamiento?") hacen brotar una objeción de cada respuesta y una pregunta nueva debajo de cada objeción. Una lista entierra esa pelea. Un girraph la mantiene visible:

- ❓ **issues** (cuestiones) — preguntas abiertas, siempre formuladas como preguntas
- 💡 **positions** (posiciones) — respuestas posibles
- ➕ ➖ **arguments** (argumentos) — razones a favor y en contra de una posición
- 📄 **notes** (notas) — contexto, restricciones, referencias a documentos
- 🦒 **nested girraphs** (girraphs anidados) — una subpregunta lo bastante grande para su propio mapa

El linaje es IBIS, un método de los años 70 para "problemas perversos" — el tipo que no tiene una respuesta limpia ni un punto de parada natural. El girraph es la versión en texto plano que enough hace de él.

El formato es un archivo de texto que termina en `.girraph`, una línea por pensamiento, legible en cualquier editor en 2026 o en 2056:

```
%girraph 0.1
title: Should enough ship a plugin API?

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
```

`< q1` significa "esto responde a q1"; `by:` recuerda de quién es la afirmación. Sin base de datos, nada oculto. El archivo es el mapa.

En la app, hacer clic en un `.girraph` abre el modo girraph: un árbol colapsable que editas directamente. Haz clic en una etiqueta para reescribirla. Pasa el cursor sobre una fila para ver los botones de añadir, enlazar, y eliminar. Haz clic en un chip 🦒 para descender a un mapa anidado — las migas de pan te traen de vuelta — y haz clic en un chip 📄 para leer un documento referenciado en el lugar. En el chat, di "haz un girraph de esto" o "mapea esto," y el agente edita el mismo archivo mediante las mismas operaciones a nivel de nodo que usas tú, así que los dos pueden trabajar el mapa a la vez. Eliminar nodos siempre requiere tu confirmación, y los hijos nunca quedan huérfanos en silencio.

Un girraph también puede hacer crecer un **espejo merirmaid**: un clic en el botón de merirmaid en la barra de herramientas del girraph crea un diagrama Mermaid vinculado y auto-regenerable del mapa — cuestiones como hexágonos, posiciones como estadios, apoyos y objeciones trazados en sus colores — que se mantiene al día a medida que el girraph cambia. Mapea en girraph, échale un vistazo en merirmaid.

Tres hábitos hacen que los girraphs funcionen. Formula las cuestiones como preguntas ("¿Cómo financiamos el segundo año?", no "el problema del dinero"). Ata los argumentos a las posiciones, no a las cuestiones — las razones son razones a favor o en contra de una *respuesta*. Y separa una rama en su propio archivo antes de que se desparrame. Activa la habilidad girraph-merirmaid y el agente te va a hacer cumplir las tres.

---

## 18. El modo merirmaid y la extensión `.merirmaid`

Donde un girraph mapea un argumento, un **merirmaid** representa una estructura. Un archivo `.merirmaid` es un diagrama de [Mermaid](https://mermaid.js.org/) — diagrama de flujo, diagrama de secuencia, máquina de estados, diagrama ER, cualquier cosa que Mermaid dibuje — con un pequeño encabezado de frontmatter, renderizado en vivo en el navegador. Localmente, por supuesto; sin CDN, como todo en enough.

Dos modalidades, declaradas en el encabezado:

- **wip** — una pizarra de trabajo. Haz clic en el texto de cualquier nodo y edita la etiqueta ahí mismo, con un contador de caracteres en vivo; los cambios estructurales (añadir una caja, recablear una flecha) pasan por el agente mediante la píldora de chat. Pide un diagrama de tu pipeline, tu trama, tu organización, y el agente escribe el código fuente, el navegador lo dibuja, y tú afinas las palabras.
- **mirror** — un reflejo de solo lectura de una estructura que vive en otro lugar: el contenido de un cachebox (sección 11.1) o un girraph (sección 17). Los espejos se regeneran cuando su fuente cambia. Para cambiar la imagen, cambia la cosa.

Los diagramas enlazan. Un nodo puede apuntar a otro `.merirmaid`, un `.girraph`, o un documento markdown, y hacer clic en él navega hasta ahí, con migas de pan marcando el camino de vuelta — así que un conjunto de diagramas se convierte en un atlas navegable de tu proyecto. Y cuando un diagrama tiene un error de sintaxis, el modo merirmaid muestra el error más el código fuente en bruto en vez de un panel en blanco. Siempre hay algo desde donde arreglarlo.

La habilidad girraph-merirmaid (sección 16.3) lleva la disciplina de autoría para los dos tipos de archivo. Una regla general de ella vale la pena repetirla aquí: si el primer movimiento honesto es hacer una pregunta, quieres un girraph; si es dibujar una caja y una flecha, quieres un merirmaid.

---

## 19. A dónde ir desde aquí

La forma más rápida de hacer que enough sea tuyo:

1. Lánzalo en un proyecto real — algo que de verdad te importe.
2. Pasa una sesión conversando, y deja que el perfil del proyecto empiece a acumularse.
3. Edita `MOTIVATION.md` para decir para qué es realmente el proyecto.
4. La primera vez que repitas una instrucción, detente. Ponla en `AGENT.md` en su lugar.
5. La primera vez que tu trabajo tenga una forma que no encaja con los valores predeterminados, di "diseñemos un paradigma para esto" — o una habilidad, o un rol — y deja que workflow-design te guíe.

Ese bucle — notar la fricción, codificar el arreglo, seguir trabajando — es todo el juego. Los componentes incluidos te ponen en marcha. El sistema con el que terminas, nadie lo distribuye. Tú lo escribes.

---

*enough es © 2026 Graham Smith, publicado bajo la Apache License 2.0. El contenido de Wikipedia al que se llega mediante wikisink es CC BY-SA. Este documento: también es tuyo para editar.*
