<!-- contenido de ayuda de enough. Una sección `## <id>` por burbuja (?).
     Edita libremente: `name:`/`path:` encabezan la sección; los cuerpos
     `### what`, `### how`, `### ideas` pueden contener HTML en línea.
     Cuatro tokens de expansión, todos resueltos del lado del cliente para
     que nada aquí se desvíe de lo que realmente está instalado:
       {{skills-list}} {{roles-list}} {{paradigms-list}}
         → el conjunto instalado en vivo (ver /api/help/defaults)
       {{convert-formats}}
         → la tabla de tipos de archivo convertibles, con la disponibilidad
           del motor en esta máquina (ver /api/convert/formats). Nunca
           listes extensiones de archivo a mano en el texto de ayuda;
           usa el token. -->

## wikisink
name: wikisink
path: ~/enough/wikisink/

### what
tu copia local y sin conexión de (una parte de) la wikipedia en inglés — un único archivo Kiwix ZIM leído en su lugar, nunca extraído, así que el gestor de archivos solo muestra los artículos que guardas explícitamente. el botón 🚰 abre un lector estilo navegador con búsqueda de texto completo, enlaces cruzados, un dado de artículo aleatorio, una píldora de chat con el agente, comentarios, y un único <strong>botón de guardar</strong> cuyo menú desplegable ofrece dos destinos (el <code>wiki/</code> de este proyecto, o el cachebox global <code>~/enough/cacheawl/wiki/</code> compartido entre proyectos). el agente puede buscar y leer todo el archivo mediante sus herramientas de wiki.

### how
el primer clic en 🚰 ejecuta el asistente de configuración: elige un tamaño (el millón de artículos más leídos, sin imágenes, ≈ 16 GB es el predeterminado; el inglés completo ≈ 49 GB; también hay opciones más pequeñas), elige una carpeta de almacenamiento (los discos externos funcionan), confirma, y deja correr la descarga reanudable — pausa, cierra, retoma cuando quieras. puedes mantener <em>varias instalaciones</em> en distintos lugares (digamos, el archivo completo en un disco externo y uno pequeño en el disco interno) y cambiar entre ellas en la lista de instalaciones de ⚙; si un disco se desconecta, su instalación simplemente aparece como inalcanzable hasta que el disco vuelve. una vez instalado, pídele al agente que ejecute un <strong>wikisink</strong> para refrescar tus artículos guardados/comentados ("vigilados") desde la wikipedia en vivo y obtener un informe: cambios en artículos vigilados, picos de edición, artículos que suben y bajan en vistas, y borrados sospechosos. el botón 🛡 en cualquier artículo es la <em>anulación de borrado</em>: conserva tu copia local para siempre, excluida de las actualizaciones. ⚙ abre el gestor de instalaciones, incluido el reemplazo del archivo base cuando sale una instantánea más nueva. no tienes que ir a buscarlo: cuando existe una versión más nueva de tu variante, aparece una pequeña píldora en la barra de herramientas del lector (<code>newer snapshot: date · size</code>) — haz clic, confirma el tamaño, y corre la misma actualización en el mismo lugar, descargando primero e intercambiando solo cuando termina. la comprobación ocurre como mucho una vez al día, nunca bloquea el lector, y se queda callada cuando estás sin conexión.

### ideas
- guarda los artículos de los que depende un proyecto en su carpeta <code>wiki/</code> — copias de fidelidad completa que se abren de nuevo en el lector, cada una con un manifiesto de atribución CC BY-SA incorporado.
- comenta las afirmaciones que dudas, y luego ejecuta un wikisink más tarde — los comentarios sobreviven a las actualizaciones del artículo (se reanclan o quedan huérfanos, pero nunca se pierden) y los artículos comentados se vigilan automáticamente.
- cuando un informe de wikisink señala un borrado sospechoso (eliminado por "relevancia" en vez de calidad — el caso clásico), abre el artículo y pulsa 🛡 antes del próximo reemplazo del archivo base.

## project-wiki
name: wiki/
path: wiki/

### what
artículos de wikipedia guardados en este proyecto desde el navegador de wikisink (el botón de guardar → "este proyecto"). cada guardado es una carpeta: <code>article.html</code> (el artículo exactamente como lo tenía el archivo — haz clic para leerlo en el visor de wikisink, con fidelidad completa, infoboxes y todo) más <code>_manifest.md</code> (url de origen, licencia CC BY-SA, fecha de obtención, procedencia).

### how
se crea automáticamente en tu primer guardado a nivel de proyecto — sin configuración. las ejecuciones de actualización de wikisink tratan todo lo de aquí como <em>vigilado</em>: se refresca desde la wikipedia en vivo y se informa sobre ello. volver a guardar un artículo sobrescribe la carpeta con la copia más reciente; para quitar uno, pasa el cursor un momento sobre su carpeta en el árbol y haz clic en el 🗑 que aparece. las copias guardadas no están pensadas para editarse a mano — se desincronizarían del archivo. (la otra opción del botón de guardar guarda en el cachebox global <code>~/enough/cacheawl/wiki/</code>, compartido entre todos los proyectos.)

### ideas
- los artículos guardados se abren en el lector incluso cuando el disco del archivo está desconectado — son tus copias doblemente sin conexión.
- el agente lee los artículos mediante sus herramientas de wiki (extracción de texto limpio), así que puede fundamentarse tanto en artículos guardados como archivados.
- el texto de wikipedia es CC BY-SA: si parte de un artículo termina en algo que publicas, el manifiesto tiene todo lo que necesitas para la atribución.

## wiki-comments
name: comentarios
path: ~/enough/wikisink/comments/

### what
comentarios al estilo google docs sobre artículos de wikipedia — resalta texto y pulsa 💬, o usa el 💬 de la barra de herramientas para fijar un comentario a un párrafo. los hilos admiten respuestas y resolver/reabrir. los comentarios se adjuntan al <em>artículo</em>, no a ningún archivo guardado, así que siguen al artículo tanto si está guardado, como si solo se navegó, se actualizó, o incluso se eliminó de la wikipedia en vivo.

### how
selecciona texto en el lector de wikisink → comenta con 💬. el anclaje se degrada con elegancia cuando los artículos cambian: primero busca coincidencia exacta de texto; si el texto citado fue editado, el comentario se reancla a su párrafo (marcado como "reanclado"); si el párrafo también desapareció, sobrevive como "huérfano" en el panel. nada se elimina nunca automáticamente. comentar un artículo lo añade al conjunto vigilado para las actualizaciones de wikisink.

### ideas
- comenta estadísticas o afirmaciones que probablemente cambien — después de una ejecución de wikisink, los comentarios reanclados son una señal de que ese punto exacto fue editado.
- pregúntale al agente sobre un pasaje resaltado mediante el 🤖 del menú emergente de selección — el pasaje se cita en el chat automáticamente.

## paradigm-active
name: paradigma
path: rness/active-paradigm

### what
el marco de razonamiento que el agente está usando en este momento. hay exactamente un paradigma activo en cada momento; haz clic en otro para cambiar. el paradigma activo se carga por completo en el system prompt en cada turno, y el agente también ve un breve catálogo de los demás paradigmas disponibles para poder sugerir (o iniciar) un cambio cuando el trabajo se beneficiaría de uno.

### how
haz clic en ● junto a un paradigma para activarlo en este proyecto. la elección queda registrada en <code>rness/active-paradigm</code>. los cambios iniciados por el agente también se hacen escribiendo ese archivo, y surten efecto en el siguiente turno. añade paradigmas nuevos colocando un archivo markdown en <code>~/enough/defaults/paradigms/</code> (o en el <code>rness/paradigms/</code> de tu proyecto para paradigmas locales al proyecto). un bloque de frontmatter YAML al principio — <code>name:</code> y <code>description:</code> — le dice al agente para qué sirve el paradigma.

### ideas
- Paradigmas disponibles en este proyecto: {{paradigms-list}}
- escribe un paradigma para cada modo distinto de trabajo (investigar frente a escribir, explorar frente a ejecutar) y alterna entre ellos según avanza el día.
- una descripción de paradigma es esencialmente "cuándo debería usar esto" — escríbela pensando en el agente, porque esa es la señal que lee para recomendar un cambio.

## requests
name: requests/
path: rness/requests/

### what
contenedores persistentes de tareas y subtareas. cada solicitud es un archivo markdown que recoge el objetivo de tu petición, el razonamiento del agente hasta el momento, y un bloque de continuación para que el trabajo pueda retomarse a través de reinicios de contexto — son la unidad de esfuerzo de larga duración en enough. también son útiles para continuar el trabajo si alcanzas el límite de la ventana de contexto. las solicitudes completadas viven junto a las activas en <code>rness/requests/done/</code>.

### how
las solicitudes nuevas aparecen automáticamente en <code>rness/requests/</code> a medida que tú y el agente trabajan — haz clic en cualquier archivo del árbol del proyecto para verlo en el panel de archivos. desde ahí puedes <em>marcarla como hecha</em> (el archivo se mueve a <code>rness/requests/done/</code>) o <em>personalizarla</em>. para iniciar una solicitud a mano, coloca un archivo markdown en <code>rness/requests/</code> con un objetivo breve al principio.

### ideas
- trata una solicitud como un proyecto de larga duración — convierte una intención vaga en una y deja que el agente la desarrolle a lo largo de varias sesiones.
- explora <code>rness/requests/done/</code> como un diario de lo que realmente has completado — es el registro más honesto de tu trabajo con este agente.
- en los puntos de control de auto-reinicio de la ventana de contexto, el agente escribe un bloque de Continuación en la solicitud activa — léelo antes de retomar si quieres redirigir el trabajo.

## skills
name: habilidades
path: rness/skills/

### what
interruptores por proyecto para las habilidades — unidades de capacidad especializada enlazadas simbólicamente desde <code>~/enough/defaults/skills/</code>. las habilidades activas añaden vocabulario, recetas o comportamientos a los que el agente recurrirá durante la conversación. las habilidades que enough incluye de fábrica son <em>de confianza</em> y se activan al instante; todo lo demás bajo <code>rness/skills/</code> — descargado, regalado, o escrito para ti por tu propio agente — es <em>no confiable</em> hasta que se haya leído, y la primera vez que la activas, enough la audita antes de que una sola palabra llegue al agente.

### how
haz clic en ● / ○ para activar o desactivar una habilidad en este proyecto. puedes añadir habilidades a nivel de proyecto en <code>rness/skills/</code> — los estados de las habilidades se guardan por proyecto. para instalar habilidades nuevas de forma global, coloca una carpeta en <code>~/enough/defaults/skills/</code>; aparecerá en todos los proyectos (desactivada por defecto). edita una habilidad global en su origen y el cambio se propaga a todos los lugares donde está enlazada. una habilidad no confiable muestra una pequeña marca junto a su nombre que recorre <em>sin verificar</em> → <em>auditando…</em> → <em>auditada</em>; si la auditoría encuentra algo, la fila dice <em>marcada</em>, la habilidad permanece desactivada, y obtienes dos botones — <em>leer informe</em> (abre el informe completo) y <em>activar de todos modos</em> (pide confirmación, y luego registra la decisión como tuya). los informes llegan a <code>rness/io/output/analyzer/audits/&lt;skill&gt;/</code>. edita los archivos de una habilidad después y se vuelve a leer la próxima vez que la actives.

### ideas
- Habilidades disponibles en este proyecto: {{skills-list}}
- crea habilidades globales o locales al proyecto para capturar tu estilo propio o las convenciones de tu campo.
- desactívalo todo para tener "conversación pura" — a veces el modelo tiene más espacio para epifanías espontáneas sin andamiaje.
- pídele al agente que <em>audite</em> una habilidad antes de activarla (el cuarto modo de analyzer) — el mismo informe que escribe la auditoría al primer uso, pero cuando tú decidas.

## roles
name: roles
path: rness/roles/

### what
agentes consultores que puedes invocar en la conversación, tomados de <code>~/enough/defaults/roles/</code>. cada rol es una carpeta que contiene AGENT.md (instrucciones) y MOTIVATION.md (motivaciones) — el mismo par de archivos que define al agente principal, pero acotado a una personalidad complementaria (o adversaria).

### how
haz clic en ● / ○ para activar un rol en este proyecto. añade roles nuevos de forma global creando <code>~/enough/defaults/roles/&lt;name&gt;/</code> con AGENT.md y MOTIVATION.md dentro; el trabajo a nivel de proyecto y las ediciones se propagan igual que con las habilidades.

### ideas
- Roles disponibles en este proyecto: {{roles-list}}
- crea un "pato de goma" que haga preguntas socráticas en vez de responder.
- usa los archivos de tu base de conocimiento con el paradigma <em>workflow-design</em> para crear un rol de experto en un campo (legal, diseño, redacción).

## rness
name: rness/
path: rness/

### what
el sistema externalizado del proyecto. rness/ es donde viven la configuración, las instrucciones, los archivos de conocimiento y los registros de historial de cada proyecto — todo lo que el agente usa para este proyecto. está en la raíz del proyecto para que puedas editarlo directamente con cualquier gestor de archivos o editor; la interfaz de enough también muestra su contenido en la barra lateral.

### how
parte del contenido son enlaces simbólicos a <code>~/enough/defaults/</code> y se actualizan de forma centralizada. para diferenciarte en un proyecto, abre un archivo y haz clic en <em>personalizar</em> — se convierte en una copia local del proyecto. añade archivos nuevos libremente por conversación o con el gestor de archivos de tu sistema; el agente descubrirá cualquier archivo añadido localmente en su siguiente turno.

### ideas
- familiarízate con los componentes que impulsan tu flujo de trabajo de enough y edítalos donde quieras.
- trátalo como documentación viva — ¿qué necesitaría saber un nuevo compañero de equipo, agente o rol?
- poda el conocimiento obsoleto de vez en cuando para que el agente no cite decisiones caducas.

## agent-md
name: AGENT.md
path: rness/AGENT.md

### what
las instrucciones de trabajo del agente para este proyecto. se usan en cada turno junto con MOTIVATION.md. todo lo que hay aquí moldea cómo habla el agente, qué hace, y qué evita.

### how
haz clic en el archivo para verlo; pulsa <em>personalizar</em> para crear una copia local del proyecto y editarla. o abre <code>rness/AGENT.md</code> en cualquier editor — los cambios guardados surten efecto en el siguiente mensaje.

### ideas
- añade barreras específicas del proyecto (p. ej., "siempre revisa la ortografía y la exactitud antes de dar una edición por terminada").
- enumera las convenciones de nombres de tu proyecto para que el agente no tenga que adivinar (ni alucinnovar).
- codifica el estilo de colaboración que quieres — parco, exploratorio, deferente, directo.

## motivation-md
name: MOTIVATION.md
path: rness/MOTIVATION.md

### what
el "por qué" del agente para este proyecto — valores, prioridades y metas más allá de la lista literal de tareas. se usa junto con AGENT.md en cada turno.

### how
igual que AGENT.md — haz clic para previsualizar, personaliza para tener una copia local del proyecto, o edita el archivo directamente.

### ideas
- detalla los compromisos que te importan: exactitud sobre velocidad, brevedad sobre exhaustividad, etc.
- nombra, con tus propias palabras, la experiencia que el proyecto busca ofrecer a quien lo use.
- describe cómo se siente "terminado" — el agente calibrará su sentido de progreso contra eso.

## paradigms
name: paradigms/
path: rness/paradigms/

### what
el conjunto completo de marcos de razonamiento disponibles en este proyecto. cada paradigma es un archivo markdown con un bloque de frontmatter YAML (<code>name</code> + <code>description</code>) y un cuerpo que describe cómo abordar el trabajo — heurísticas, criterios de decisión, cuándo preguntar y cuándo actuar. hay exactamente uno activo en cada momento (consulta la sección <strong>paradigma</strong> en lo alto de la barra lateral para cambiarlo).

### how
enlazado simbólicamente desde <code>~/enough/defaults/paradigms/</code>. edita a nivel global para actualizar el comportamiento en todos los proyectos; haz clic en <em>personalizar</em> en cualquier archivo para bifurcarlo solo para este proyecto. se pueden añadir paradigmas nuevos simplemente colocando un archivo markdown en la carpeta de valores predeterminados — dale un <code>name:</code> y <code>description:</code> en el frontmatter para que el agente sepa cuándo recomendarlo.

### ideas
- Paradigmas disponibles en este proyecto: {{paradigms-list}}
- escribe un paradigma para cada modo distinto de trabajo (investigar frente a escribir, explorar frente a ejecutar) y alterna entre ellos según avanza el día.
- una descripción de paradigma es esencialmente "cuándo debería usar esto" — escríbela pensando en el agente, porque esa es la señal que lee para recomendar un cambio.

## policies
name: policies/
path: rness/policies/

### what
reglas estrictas que el agente debe seguir — qué herramientas usar, qué archivos puede leer o escribir, cómo formatear las solicitudes, cómo manejar la presión sobre la ventana de contexto, y qué rutas están en la lista de permitidos.

### how
enlazado simbólicamente desde <code>~/enough/defaults/policies/</code>. edita a nivel global para actualizar las reglas de todos los proyectos, o personalízalas por proyecto. las listas de permitidos en particular son lo que más se ajusta, ya que tanto las rutas locales como las url deben listarse explícitamente.

### ideas
- endurece la lista de permitidos de lectura/escritura cuando trabajes con secretos o código sensible.
- añade una política sobre cómo manejar scripts de larga duración o procesos en segundo plano.
- define tu propio formato de punto de control si el bloque de Continuación predeterminado no te encaja.

## knowledge
name: conocimiento
path: rness/knowledge/

### what
conocimiento específico del proyecto que no encaja en <code>rness/io/</code> ni en <code>~/enough/infoworld/</code>: siempre contiene <code>project-profile.md</code> (notas vivas que el agente mantiene sobre este proyecto — tus preferencias y estilo de trabajo tal como se observan aquí, personas / archivos recurrentes, convenciones adoptadas) y <code>session-logs/</code> (el mensaje y la respuesta de cada turno, guardados como markdown).

### how
<code>project-profile.md</code> se inyecta en el system prompt en cada turno — tanto el agente como tú pueden editarlo. los registros de sesión son de solo anexado. añade subcarpetas nuevas para cualquier memoria local al proyecto que quieras que el agente consulte.

### ideas
- mantén una subcarpeta de glosario para la jerga específica del proyecto.
- deja que el agente escriba un archivo de "lecciones aprendidas" a medida que iteran juntos.
- archiva los registros de sesión antiguos de vez en cuando para que las búsquedas del agente sigan siendo rápidas.

## io
name: io/
path: rness/io/

### what
un espacio a nivel de proyecto para archivos que el agente lee (<code>input/</code>) o en los que escribe (<code>output/</code>). útil cuando quieres que el agente procese un archivo sin ensuciar la raíz del proyecto.

### how
coloca archivos en <code>rness/io/input/</code> y el agente los verá. todo lo que el agente genera llega a <code>rness/io/output/</code> — revisa y mueve lo que quieras conservar, y luego vacía el resto. los documentos también cuentan: un archivo de word o un pdf colocado aquí se abre como un gemelo en markdown y se lee como cualquier otro archivo, tanto para ti como para el agente.

### ideas
- coloca un CSV o una transcripción en <code>input/</code> y pídele al agente que la resuma.
- coloca el pdf que alguien te mandó por correo en <code>input/</code>, haz clic en él, y léelo como markdown — el original se queda exactamente como llegó.
- reúne varios borradores de salida en <code>output/</code> y elige el mejor (o haz que el modelo los evalúe entre sí).
- vacía ambas carpetas de vez en cuando — el agente no necesita el trabajo de borrador de ayer en su contexto.

## infoworld
name: cacheawl
path: ~/enough/cacheawl/

### what
el almacén de archivos global de la máquina, compartido entre todos los proyectos de enough. (esto reemplaza a la antigua biblioteca <code>infoworld/</code> — en tu primer inicio de esta versión, tus carpetas <code>personal/</code>, <code>public/</code> y <code>wiki/</code> se movieron aquí, y cada una se convirtió en un cachebox.) un <em>cachebox</em> es una carpeta de nivel superior en el almacén: ya sea texto simple que quieres conservar para siempre, o una "réplica en caché" ingerida desde una ruta local, un sitio web, o un conjunto de artículos de wikipedia. el almacén está oculto del árbol de archivos de cada proyecto y se gestiona mediante el modo cacheawl y las herramientas de cachebox del agente.

### how
abre el modo cacheawl (el botón cacheawl de la barra superior) para una vista de dos paneles: tu proyecto en un lado, los cacheboxes en el otro. arrastra un archivo de un lado a otro para copiarlo, shift-arrastra para moverlo; la barra de ingesta compone una petición al agente para traer una ruta, sitio o tema de wiki. o simplemente pídeselo al agente — puede listar, crear e ingerir en cacheboxes (sujeto al interruptor del broker "cacheawl tools"). cada caja lleva un diagrama <code>_cachebox.merirmaid</code> autogenerado de su contenido (solo lectura — se regenera a partir de los archivos) y metadatos ocultos; nunca editas esos directamente.

### ideas
- ingiere un sitio de documentación con poca profundidad para que el agente pueda fundamentarse en él completamente sin conexión.
- mantén un cachebox <code>personal</code> de material de referencia consultable desde cualquier proyecto.
- guarda los artículos de wikipedia de los que dependes en el cachebox global <code>wiki</code> — compartido en todas partes, sin atarse a un solo proyecto.

## mode-system
name: modo lectura / edición
path: the file viewer

### what
al hacer clic en un archivo se abre en un único <strong>modo lectura/edición</strong> unificado con dos facetas — una faceta de lectura (el ojo) y una faceta de edición (el lápiz). vive como un panel lateral mini junto al chat, o expandido a pantalla completa; usa el interruptor mini↔completo para cambiar. las ediciones están protegidas contra pérdida, así que no perderás cambios sin guardar por navegar a otro lado por accidente. los archivos que enough no muestra de forma nativa igual se abren: un archivo de word, pdf, presentación o libro de excel se abre como su <em>gemelo</em> en markdown (ve la burbuja de <em>documento convertido</em> en cualquiera de esas filas), y una imagen se abre en un visor simple con tamaños de ajuste y 1:1.

### how
haz un clic en un archivo del árbol para abrirlo en el panel mini; expándelo a pantalla completa cuando quieras más espacio. alterna entre las facetas de lectura (ojo) y edición (lápiz) con los botones dedicados en la barra del modo lectura/edición. cada modo abierto muestra un indicador cuadrado arriba a la derecha (el más nuevo a la izquierda) con una pequeña cinta de x roja para cerrarlo — los modos se <em>apilan</em>, así que cerrar uno revela el modo de abajo exactamente como lo dejaste. haz clic en un indicador enterrado para traer ese modo al frente; pulsa <code>esc</code> para cerrar el modo superior. el mismo patrón de indicador + cinta cubre todos los modos de pantalla completa (wikisink, girraph, merirmaid, cacheawl, y el modo de referencia de solo lectura <strong>centro de ayuda</strong>, que se abre desde el pequeño botón de <strong>ayuda</strong> arriba a la derecha de la ventana de ui).

### ideas
- mantén un archivo abierto en el panel mini mientras conversas — referencia y conversación lado a lado.
- pasa a pantalla completa para documentos largos o al editar, y vuelve a mini cuando solo necesites echar un vistazo.

## converted-file
name: documento convertido
path: the original, plus its markdown twin

### what
un documento que enough no muestra de forma nativa — un archivo de word, un pdf, una presentación, un libro de excel — mostrado como <em>una sola</em> fila que se abre como markdown. haz clic en él y obtienes su <strong>gemelo</strong>: una copia en markdown escrita junto al original (<code>memo.docx</code> → <code>memo.docx.md</code>) que se lee, resalta y edita como cualquier otro archivo markdown. el gemelo, cualquier imagen extraída del documento (<code>memo.docx.assets/</code>) y un pequeño manifiesto oculto se pliegan en esa única fila, así que el árbol se mantiene tan ordenado como se ve tu carpeta en finder. la insignia en el borde derecho de la fila dice cómo van las cosas: en silencio significa que el gemelo coincide con el original; una insignia iluminada con un punto significa que editaste el gemelo (y puedes exportar esos cambios de vuelta) o que el original cambió fuera de enough — y rojo significa ambas cosas, que es el único caso sobre el que enough te pregunta. una insignia hueca significa "aún no convertido", o, para los pdf, que el extra de pdf no está instalado.

### how
haz un clic. la primera vez que abres cada <em>tipo</em> de documento, un pequeño modal explica lo que está por pasar; después de eso, simplemente se abre. edita el gemelo como cualquier archivo, y luego usa <strong>exportar</strong> en la barra del documento: la opción predeterminada escribe una copia con fecha junto al original (<code>memo-2026-08-19-1042.docx</code>), y "sobrescribir el original" es una opción debajo, con oferta de deshacer después. el mismo modal incluye <em>mantener el original sincronizado</em> — cada guardado del gemelo reescribe el original por ti — ofrecido solo para los formatos que se pueden escribir de vuelta. si el original cambió debajo de ti (editado en word, reexportado desde algún lugar), enough se da cuenta al abrir o al guardar y pregunta qué lado gana: conservar tu gemelo, exportar sobre el original, o reconvertir desde el original — y el gemelo que reemplaza se guarda aparte para poder deshacer en cualquier caso. <strong>los originales nunca se reescriben a menos que tú lo pidas</strong>, y cada sobrescritura deja un deshacer.

### ideas
- lo que enough puede abrir así, y lo que puede escribir de vuelta: {{convert-formats}}
- pídele al agente que lea un documento por su nombre — <code>read_file</code> sobre <code>report.pdf</code> le entrega el gemelo, convirtiendo uno primero si aún no existe.
- leer pdf, presentaciones de powerpoint y libros de excel necesita el <strong>extra de pdf</strong> (⚙ ventana de ui → extras): unos 250 MB para descargar, cerca de 1 GB instalado, más unos 0.7 GB de modelos de documento en <code>~/enough/weights/docling/</code>. <em>escribir</em> pdf a partir de markdown funciona en cualquier instalación, sin extra.

## merirmaid
name: merirmaid
path: *.merirmaid

### what
la variante de enough de un diagrama <a href="https://mermaid.js.org/" target="_blank" rel="noopener">Mermaid</a>: código fuente de diagrama en texto plano con un pequeño encabezado, renderizado en vivo como imagen en el navegador (diagramas de flujo, diagramas de secuencia, máquinas de estado, diagramas ER — todo lo que Mermaid soporta). dos tipos: un diagrama <em>wip</em> que puedes ajustar, y un <em>espejo</em> que refleja alguna estructura (como el contenido de un cachebox) y es de solo lectura.

### how
pídele al agente que dibuje o revise un diagrama — escribe el código fuente <code>.merirmaid</code>; abrir el archivo lo renderiza. en un diagrama wip puedes hacer clic en el texto de un nodo para editar la etiqueta ahí mismo (con un contador de caracteres en vivo); los cambios estructurales pasan por el agente mediante la píldora de chat. los nodos pueden enlazar a otros diagramas o documentos — haz clic en ellos para seguirlos, con migas de pan para volver atrás. un diagrama con errores muestra el error más el código fuente, nunca un panel en blanco. los diagramas espejo muestran una insignia de "espejo" en vez de asas de edición.

### ideas
- pídele al agente que diagrame un proceso o arquitectura sobre el que estás razonando, y luego refínalo en la conversación.
- enlaza un conjunto de diagramas entre sí con nodos en los que se puede hacer clic para construir un mapa navegable.
- combínalo con girraphs: un girraph para el argumento, un merirmaid para el flujo.

## cacheawl
name: cacheawl
path: ~/enough/cacheawl/

### what
el almacén global de la máquina para <em>cacheboxes</em> — carpetas de nivel superior que guardan texto que quieres conservar para siempre, o réplicas en caché ingeridas desde una ruta local, un sitio web, o artículos de wikipedia. compartido entre todos los proyectos y oculto de los árboles de archivos de los proyectos. aquí es donde vive ahora la antigua biblioteca <code>infoworld</code>.

### how
abre el modo cacheawl desde la barra superior para la vista de dos paneles (proyecto ↔ cacheboxes): arrastra para copiar un archivo entre ellos, shift-arrastra para moverlo, y usa la barra de ingesta para pedirle al agente que traiga una fuente a una caja. o habla directamente con el agente — puede listar, crear e ingerir en cajas cuando el interruptor del broker "cacheawl tools" está activado (las ingestas de url también respetan tus interruptores de fetch_url). cada caja muestra un diagrama autogenerado de su contenido (<code>_cachebox.merirmaid</code>, solo lectura) y mantiene metadatos ocultos que no tocas.

### ideas
- ingiere un sitio de documentación o una carpeta de notas para que el agente pueda trabajar con ella sin conexión.
- mueve un artefacto terminado a un cachebox para mantenerlo fuera del proyecto de trabajo pero aun así accesible desde cualquier lugar.
- haz doble clic en el diagrama de una caja para ver su forma de un vistazo en el visor de merirmaid.

## footnotes
name: notas al pie
path: (inside your markdown files)

### what
notas al pie de verdad para textos en curso. escribe <code>[^1]</code> en la prosa y pon <code>[^1]: la nota en sí</code> al final del archivo — en la vista de lectura, cada nota aparece como una pequeña tarjeta en el margen, alineada con su marcador. las tarjetas son editables ahí mismo: dale la vuelta a una para editar, guarda o cancela, listo. el archivo en el disco se mantiene como markdown simple y portable.

### how
en el editor, escribe <code>[^]</code> y se convierte automáticamente en el siguiente número de nota al pie, o usa el botón de insertar nota al pie de la barra de herramientas en la posición del cursor. coloca una nota al pie nueva entre dos existentes y todo lo que viene después se renumera solo, definiciones incluidas. las notas al pie con nombre como <code>[^aside]</code> se dejan exactamente como las escribiste. un marcador sin definición todavía muestra una tarjeta vacía — escribe en ella y al guardar se escribe la definición por ti.

### ideas
- redacta con marcadores rápidos <code>[^]</code> y rellena los cuerpos más tarde desde las tarjetas del margen.
- la numeración de las notas al pie se mantiene limpia sin importar en qué orden escribas — paginar depende de esto, así que un texto de "prosa terminada" no necesita una pasada de limpieza.

## paginate
name: paginar
path: (next to the markdown it came from)

### what
convierte un texto terminado en un pdf compuesto con esmero — páginas reales, capítulos que empiezan de cero, notas al pie reconciliadas donde tú quieras (en la página, al final de cada capítulo, o reunidas en una sección final de notas). el markdown sigue siendo el original editable; el pdf es una instantánea con fecha junto a él, p. ej. <code>book-2026-08-23.pdf</code>.

### how
abre un archivo markdown en la vista de lectura y pulsa el botón paginar en la barra de herramientas. elige un tamaño de página (carta, a4, libro de bolsillo… o personalizado), vertical u horizontal, una de las fuentes incluidas, un margen, y opcionalmente números de página y encabezados de página (tu texto, o el nombre del capítulo). 2 por hoja pone dos páginas por hoja; folleto las intercala para que una impresión a doble cara se pliegue en un libro grapable. "traer el pdf a enough" añade una vista página por página con cambio de página mediante las flechas y pantalla completa. cada pdf exportado lleva en secreto su propio markdown de origen, así que volver a importarlo a un proyecto restaura el texto — notas al pie y todo — con exactitud.

### ideas
- revisa un borrador en tamaño de bolsillo con notas al final de cada capítulo antes de decidir la forma final.
- imprime un folleto de una pieza corta: diseño folleto, media carta, y grapa el resultado.
- envíale a alguien el pdf; si alguna vez vuelve sin el original, al importarlo se recupera el markdown perfectamente.
