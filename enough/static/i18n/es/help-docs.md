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
tu copia local y sin conexión de (una parte de) la wikipedia en inglés — un único archivo Kiwix ZIM leído en su lugar, nunca extraído, así que el gestor de archivos solo muestra los artículos que guardas explícitamente. el botón 🚰 abre un lector estilo navegador con búsqueda de texto completo, enlaces cruzados, un dado de artículo aleatorio, una píldora de chat con tu readvisor, comentarios, y un único <strong>botón de guardar</strong> cuyo menú desplegable ofrece dos destinos (el <code>wiki/</code> de este proyecto, o el volumen global <code>~/enough/canon/wiki/</code> compartido entre proyectos). tu readvisor puede buscar y leer todo el archivo mediante sus herramientas de wiki.

### how
el primer clic en 🚰 ejecuta el asistente de configuración: elige un tamaño (el millón de artículos más leídos, sin imágenes, ≈ 16 GB es el predeterminado; el inglés completo ≈ 49 GB; también hay opciones más pequeñas), elige una carpeta de almacenamiento (los discos externos funcionan), confirma, y deja correr la descarga reanudable — pausa, cierra, retoma cuando quieras. puedes mantener <em>varias instalaciones</em> en distintos lugares (digamos, el archivo completo en un disco externo y uno pequeño en el disco interno) y cambiar entre ellas en la lista de instalaciones de ⚙; si un disco se desconecta, su instalación simplemente aparece como inalcanzable hasta que el disco vuelve. una vez instalado, pídele a tu readvisor que ejecute un <strong>wikisink</strong> para refrescar tus artículos guardados/comentados ("vigilados") desde la wikipedia en vivo y obtener un informe: cambios en artículos vigilados, picos de edición, artículos que suben y bajan en vistas, y borrados sospechosos. el botón 🛡 en cualquier artículo es la <em>anulación de borrado</em>: conserva tu copia local para siempre, excluida de las actualizaciones. ⚙ abre el gestor de instalaciones, incluido el reemplazo del archivo base cuando sale una instantánea más nueva. no tienes que ir a buscarlo: cuando existe una versión más nueva de tu variante, aparece una pequeña píldora en la barra de herramientas del lector (<code>newer snapshot: date · size</code>) — haz clic, confirma el tamaño, y corre la misma actualización en el mismo lugar, descargando primero e intercambiando solo cuando termina. la comprobación ocurre como mucho una vez al día, nunca bloquea el lector, y se queda callada cuando estás sin conexión.

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
se crea automáticamente en tu primer guardado a nivel de proyecto — sin configuración. las ejecuciones de actualización de wikisink tratan todo lo de aquí como <em>vigilado</em>: se refresca desde la wikipedia en vivo y se informa sobre ello. volver a guardar un artículo sobrescribe la carpeta con la copia más reciente; para quitar uno, pasa el cursor un momento sobre su carpeta en el árbol y haz clic en el 🗑 que aparece. las copias guardadas no están pensadas para editarse a mano — se desincronizarían del archivo. (la otra opción del botón de guardar guarda en el volumen global <code>~/enough/canon/wiki/</code>, compartido entre todos los proyectos.)

### ideas
- los artículos guardados se abren en el lector incluso cuando el disco del archivo está desconectado — son tus copias doblemente sin conexión.
- tu readvisor lee los artículos mediante sus herramientas de wiki (extracción de texto limpio), así que puede fundamentarse tanto en artículos guardados como archivados.
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
- pregúntale a tu readvisor sobre un pasaje resaltado mediante el 🤖 del menú emergente de selección — el pasaje se cita en el chat automáticamente.

## paradigm-active
name: paradigma
path: rness/active-paradigm

### what
el marco de razonamiento que tu readvisor está usando en este momento. hay exactamente un paradigma activo en cada momento; haz clic en otro para cambiar. el paradigma activo se carga por completo en el system prompt en cada turno, y tu readvisor también ve un breve catálogo de los demás paradigmas disponibles para poder sugerir (o iniciar) un cambio cuando el trabajo se beneficiaría de uno.

### how
haz clic en ● junto a un paradigma para activarlo en este proyecto. la elección queda registrada en <code>rness/active-paradigm</code>. los cambios iniciados por tu readvisor también se hacen escribiendo ese archivo, y surten efecto en el siguiente turno. añade paradigmas nuevos colocando un archivo markdown en <code>~/enough/defaults/paradigms/</code> (o en el <code>rness/paradigms/</code> de tu proyecto para paradigmas locales al proyecto). un bloque de frontmatter YAML al principio — <code>name:</code> y <code>description:</code> — le dice a tu readvisor para qué sirve el paradigma.

### ideas
- Paradigmas disponibles en este proyecto: {{paradigms-list}}
- escribe un paradigma para cada modo distinto de trabajo (investigar frente a escribir, explorar frente a ejecutar) y alterna entre ellos según avanza el día.
- una descripción de paradigma es esencialmente "cuándo debería usar esto" — escríbela pensando en tu readvisor, porque esa es la señal que lee para recomendar un cambio.

## requests
name: requests/
path: rness/requests/

### what
contenedores persistentes de tareas y subtareas. cada solicitud es un archivo markdown que recoge el objetivo de tu petición, el razonamiento de tu readvisor hasta el momento, y un bloque de continuación para que el trabajo pueda retomarse a través de reinicios de contexto — son la unidad de esfuerzo de larga duración en enough. también son útiles para continuar el trabajo si alcanzas el límite de la ventana de contexto. las solicitudes completadas viven junto a las activas en <code>rness/requests/done/</code>.

### how
las solicitudes nuevas aparecen automáticamente en <code>rness/requests/</code> a medida que tú y tu readvisor trabajan — haz clic en cualquier archivo del árbol del proyecto para verlo en el panel de archivos. desde ahí puedes <em>marcarla como hecha</em> (el archivo se mueve a <code>rness/requests/done/</code>) o <em>personalizarla</em>. para iniciar una solicitud a mano, coloca un archivo markdown en <code>rness/requests/</code> con un objetivo breve al principio.

### ideas
- trata una solicitud como un proyecto de larga duración — convierte una intención vaga en una y deja que tu readvisor la desarrolle a lo largo de varias sesiones.
- explora <code>rness/requests/done/</code> como un diario de lo que realmente has completado — es el registro más honesto de tu trabajo con tu readvisor.
- en los puntos de control de auto-reinicio de la ventana de contexto, enough escribe un bloque de Continuación en la solicitud activa — léelo antes de retomar si quieres redirigir el trabajo.

## skills
name: habilidades
path: rness/skills/

### what
interruptores por proyecto para las habilidades — unidades de capacidad especializada enlazadas simbólicamente desde <code>~/enough/defaults/skills/</code>. las habilidades activas añaden vocabulario, recetas o comportamientos a los que tu readvisor recurrirá durante la conversación. las habilidades que enough incluye de fábrica son <em>de confianza</em> y se activan al instante; todo lo demás bajo <code>rness/skills/</code> — descargado, regalado, o escrito para ti por tu propio readvisor — es <em>no confiable</em> hasta que se haya leído, y la primera vez que la activas, enough la audita antes de que una sola palabra llegue a tu readvisor.

### how
haz clic en ● / ○ para activar o desactivar una habilidad en este proyecto. puedes añadir habilidades a nivel de proyecto en <code>rness/skills/</code> — los estados de las habilidades se guardan por proyecto. para instalar habilidades nuevas de forma global, coloca una carpeta en <code>~/enough/defaults/skills/</code>; aparecerá en todos los proyectos (desactivada por defecto). edita una habilidad global en su origen y el cambio se propaga a todos los lugares donde está enlazada. una habilidad no confiable muestra una pequeña marca junto a su nombre que recorre <em>sin verificar</em> → <em>auditando…</em> → <em>auditada</em>; si la auditoría encuentra algo, la fila dice <em>marcada</em>, la habilidad permanece desactivada, y obtienes dos botones — <em>leer informe</em> (abre el informe completo) y <em>activar de todos modos</em> (pide confirmación, y luego registra la decisión como tuya). los informes llegan a <code>rness/io/output/analyzer/audits/&lt;skill&gt;/</code>. edita los archivos de una habilidad después y se vuelve a leer la próxima vez que la actives.

### ideas
- Habilidades disponibles en este proyecto: {{skills-list}}
- crea habilidades globales o locales al proyecto para capturar tu estilo propio o las convenciones de tu campo.
- desactívalo todo para tener "conversación pura" — a veces el modelo tiene más espacio para epifanías espontáneas sin andamiaje.
- pídele a tu readvisor que <em>audite</em> una habilidad antes de activarla (el cuarto modo de analyzer) — el mismo informe que escribe la auditoría al primer uso, pero cuando tú decidas.

## roles
name: readvisors
path: rness/readvisors/

### what
los otros lectores de la sala. un readvisor es una carpeta con AGENT.md (quién es) y MOTIVATION.md (qué le importa) — una sola forma, con encabezados fijos, para que todos funcionen igual a pesar de su voz y sus manías. activados aquí, se funden en la voz única de tu readvisor jefe en la conversación normal; en una composure de tipo consejo cada uno habla por separado, con su propio nombre.

### how
haz clic en ● / ○ para activar o desactivar uno en este proyecto. el tooltip de cada fila dice su origen: los <em>que vienen con enough</em> (<code>defaults/readvisors/</code>) no tienen botón de borrado; los <em>globales</em> son tuyos, viven en <code>~/enough/readvisors/</code> y aparecen en todos los proyectos de esta máquina; los <em>del proyecto</em> pertenecen solo a esta carpeta (<code>rness/readvisors/&lt;name&gt;/</code>). la × de una fila global o de proyecto la borra, tras confirmar. la habilidad <em>readvisory</em> te entrevista y escribe uno nuevo.

### ideas
- Readvisors disponibles en este proyecto: {{roles-list}}
- construye un "patito de goma" que haga preguntas socráticas en vez de responder.
- usa los archivos de tu base de conocimiento con el paradigma <em>workflow-design</em> para hacer un experto del dominio (legal, diseño, redacción).
- activa dos que no estén de acuerdo, convoca un consejo y deja que lo discutan en el lienzo.

## rness
name: rness/
path: rness/

### what
el sistema externalizado del proyecto. rness/ es donde viven la configuración, las instrucciones, los archivos de conocimiento y los registros de historial de cada proyecto — todo lo que tu readvisor usa para este proyecto. está en la raíz del proyecto para que puedas editarlo directamente con cualquier gestor de archivos o editor; la interfaz de enough también muestra su contenido en la barra lateral.

### how
parte del contenido son enlaces simbólicos a <code>~/enough/defaults/</code> y se actualizan de forma centralizada. para diferenciarte en un proyecto, abre un archivo y haz clic en <em>personalizar</em> — se convierte en una copia local del proyecto. añade archivos nuevos libremente por conversación o con el gestor de archivos de tu sistema; tu readvisor descubrirá cualquier archivo añadido localmente en su siguiente turno.

### ideas
- familiarízate con los componentes que impulsan tu flujo de trabajo de enough y edítalos donde quieras.
- trátalo como documentación viva — ¿qué necesitaría saber un compañero de equipo nuevo, o un readvisor nuevo?
- poda el conocimiento obsoleto de vez en cuando para que tu readvisor no cite decisiones caducas.

## agent-md
name: AGENT.md
path: rness/AGENT.md

### what
las instrucciones de trabajo de tu readvisor para este proyecto. se usan en cada turno junto con MOTIVATION.md. todo lo que hay aquí moldea cómo habla tu readvisor, qué hace, y qué evita.

### how
haz clic en el archivo para verlo; pulsa <em>personalizar</em> para crear una copia local del proyecto y editarla. o abre <code>rness/AGENT.md</code> en cualquier editor — los cambios guardados surten efecto en el siguiente mensaje.

### ideas
- añade barreras específicas del proyecto (p. ej., "siempre revisa la ortografía y la exactitud antes de dar una edición por terminada").
- enumera las convenciones de nombres de tu proyecto para que tu readvisor no tenga que adivinar (ni alucinnovar).
- codifica el estilo de colaboración que quieres — parco, exploratorio, deferente, directo.

## motivation-md
name: MOTIVATION.md
path: rness/MOTIVATION.md

### what
el "por qué" de tu readvisor para este proyecto — valores, prioridades y metas más allá de la lista literal de tareas. se usa junto con AGENT.md en cada turno.

### how
igual que AGENT.md — haz clic para previsualizar, personaliza para tener una copia local del proyecto, o edita el archivo directamente.

### ideas
- detalla los compromisos que te importan: exactitud sobre velocidad, brevedad sobre exhaustividad, etc.
- nombra, con tus propias palabras, la experiencia que el proyecto busca ofrecer a quien lo use.
- describe cómo se siente "terminado" — tu readvisor calibrará su sentido de progreso contra eso.

## paradigms
name: paradigms/
path: rness/paradigms/

### what
el conjunto completo de marcos de razonamiento disponibles en este proyecto. cada paradigma es un archivo markdown con un bloque de frontmatter YAML (<code>name</code> + <code>description</code>) y un cuerpo que describe cómo abordar el trabajo — heurísticas, criterios de decisión, cuándo preguntar y cuándo actuar. hay exactamente uno activo en cada momento (consulta la sección <strong>paradigma</strong> en lo alto de la barra lateral para cambiarlo).

### how
enlazado simbólicamente desde <code>~/enough/defaults/paradigms/</code>. edita a nivel global para actualizar el comportamiento en todos los proyectos; haz clic en <em>personalizar</em> en cualquier archivo para bifurcarlo solo para este proyecto. se pueden añadir paradigmas nuevos simplemente colocando un archivo markdown en la carpeta de valores predeterminados — dale un <code>name:</code> y <code>description:</code> en el frontmatter para que tu readvisor sepa cuándo recomendarlo.

### ideas
- Paradigmas disponibles en este proyecto: {{paradigms-list}}
- escribe un paradigma para cada modo distinto de trabajo (investigar frente a escribir, explorar frente a ejecutar) y alterna entre ellos según avanza el día.
- una descripción de paradigma es esencialmente "cuándo debería usar esto" — escríbela pensando en tu readvisor, porque esa es la señal que lee para recomendar un cambio.

## policies
name: policies/
path: rness/policies/

### what
reglas estrictas que tu readvisor debe seguir — qué herramientas usar, qué archivos puede leer o escribir, cómo formatear las solicitudes, cómo manejar la presión sobre la ventana de contexto, y qué rutas están en la lista de permitidos.

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
conocimiento específico del proyecto que no encaja en <code>rness/io/</code> ni en <code>~/enough/infoworld/</code>: siempre contiene <code>project-profile.md</code> (notas vivas que tu readvisor mantiene sobre este proyecto — tus preferencias y estilo de trabajo tal como se observan aquí, personas / archivos recurrentes, convenciones adoptadas) y <code>session-logs/</code> (el mensaje y la respuesta de cada turno, guardados como markdown).

### how
<code>project-profile.md</code> se inyecta en el system prompt en cada turno — tanto tu readvisor como tú pueden editarlo. los registros de sesión son de solo anexado. añade subcarpetas nuevas para cualquier memoria local al proyecto que quieras que tu readvisor consulte.

### ideas
- mantén una subcarpeta de glosario para la jerga específica del proyecto.
- deja que tu readvisor escriba un archivo de "lecciones aprendidas" a medida que iteran juntos.
- archiva los registros de sesión antiguos de vez en cuando para que las búsquedas de tu readvisor sigan siendo rápidas.

## io
name: io/
path: rness/io/

### what
un espacio a nivel de proyecto para archivos que tu readvisor lee (<code>input/</code>) o en los que escribe (<code>output/</code>). útil cuando quieres que tu readvisor procese un archivo sin ensuciar la raíz del proyecto.

### how
coloca archivos en <code>rness/io/input/</code> y tu readvisor los verá. todo lo que tu readvisor genera llega a <code>rness/io/output/</code> — revisa y mueve lo que quieras conservar, y luego vacía el resto. los documentos también cuentan: un archivo de word o un pdf colocado aquí se abre como un gemelo en markdown y se lee como cualquier otro archivo, tanto para ti como para tu readvisor.

### ideas
- coloca un CSV o una transcripción en <code>input/</code> y pídele a tu readvisor que la resuma.
- coloca el pdf que alguien te mandó por correo en <code>input/</code>, haz clic en él, y léelo como markdown — el original se queda exactamente como llegó.
- reúne varios borradores de salida en <code>output/</code> y elige el mejor (o haz que el modelo los evalúe entre sí).
- vacía ambas carpetas de vez en cuando — tu readvisor no necesita el trabajo de borrador de ayer en su contexto.

## infoworld
name: canon
path: ~/enough/canon/

### what
el almacén de archivos global de la máquina, compartido entre todos los proyectos de enough. (esto reemplaza a la antigua biblioteca <code>infoworld/</code> — en tu primer inicio de esta versión, tus carpetas <code>personal/</code>, <code>public/</code> y <code>wiki/</code> se movieron aquí, y cada una se convirtió en un volumen.) un <em>volumen</em> es una carpeta de nivel superior en el almacén: ya sea texto simple que quieres conservar para siempre, o una "réplica en caché" ingerida desde una ruta local, un sitio web, o un conjunto de artículos de wikipedia. el almacén está oculto del árbol de archivos de cada proyecto y se gestiona mediante el modo canon y las herramientas de canon de tu readvisor.

### how
abre el modo canon (el botón canon de la barra superior) para una vista de dos paneles: tu proyecto en un lado, los volúmenes en el otro. arrastra un archivo de un lado a otro para copiarlo, shift-arrastra para moverlo; la barra de ingesta compone una petición a tu readvisor para traer una ruta, sitio o tema de wiki. o simplemente pídeselo a tu readvisor — puede listar, crear e ingerir en volúmenes (sujeto al interruptor del broker "canon tools"). cada volumen lleva un catálogo <code>canon.cosm</code> autogenerado de su contenido (solo lectura — se regenera a partir de los archivos) y metadatos ocultos; nunca editas esos directamente.

### ideas
- ingiere un sitio de documentación con poca profundidad para que tu readvisor pueda fundamentarse en él completamente sin conexión.
- mantén un volumen <code>personal</code> de material de referencia consultable desde cualquier proyecto.
- guarda los artículos de wikipedia de los que dependes en el volumen global <code>wiki</code> — compartido en todas partes, sin atarse a un solo proyecto.

## mode-system
name: modo lectura / edición
path: the file viewer

### what
al hacer clic en un archivo se abre en un único <strong>modo lectura/edición</strong> unificado con dos facetas — una faceta de lectura (el ojo) y una faceta de edición (el lápiz). vive como un panel lateral mini junto al chat, o expandido a pantalla completa; usa el interruptor mini↔completo para cambiar. las ediciones están protegidas contra pérdida, así que no perderás cambios sin guardar por navegar a otro lado por accidente. los archivos que enough no muestra de forma nativa igual se abren: un archivo de word, pdf, presentación o libro de excel se abre como su <em>gemelo</em> en markdown (ve la burbuja de <em>documento convertido</em> en cualquiera de esas filas), y una imagen se abre en un visor simple con tamaños de ajuste y 1:1.

### how
haz un clic en un archivo del árbol para abrirlo en el panel mini; expándelo a pantalla completa cuando quieras más espacio. alterna entre las facetas de lectura (ojo) y edición (lápiz) con los botones dedicados en la barra del modo lectura/edición. cada modo abierto muestra un indicador cuadrado arriba a la derecha (el más nuevo a la izquierda) con una pequeña cinta de x roja para cerrarlo — los modos se <em>apilan</em>, así que cerrar uno revela el modo de abajo exactamente como lo dejaste. haz clic en un indicador enterrado para traer ese modo al frente; pulsa <code>esc</code> para cerrar el modo superior. el mismo patrón de indicador + cinta cubre todos los modos de pantalla completa: wikisink, girraph, merirmaid, canon, el visor cosm, el diccionario, y el <strong>visor de documentos</strong>, donde lees este centro de ayuda y la especificación de MacroCOSM (lo abre el pequeño botón de <strong>ayuda</strong> arriba a la derecha de la ventana de ui).

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
- pídele a tu readvisor que lea un documento por su nombre — <code>read_file</code> sobre <code>report.pdf</code> le entrega el gemelo, convirtiendo uno primero si aún no existe.
- leer pdf, presentaciones de powerpoint y libros de excel necesita el <strong>extra de pdf</strong> (⚙ ventana de ui → extras): unos 250 MB para descargar, cerca de 1 GB instalado, más unos 0.7 GB de modelos de documento en <code>~/enough/weights/docling/</code>. <em>escribir</em> pdf a partir de markdown funciona en cualquier instalación, sin extra.

## merirmaid
name: merirmaid
path: *.merirmaid

### what
la variante de enough de un diagrama <a href="https://mermaid.js.org/" target="_blank" rel="noopener">Mermaid</a>: código fuente de diagrama en texto plano con un pequeño encabezado, renderizado en vivo como imagen en el navegador (diagramas de flujo, diagramas de secuencia, máquinas de estado, diagramas ER — todo lo que Mermaid soporta). dos tipos: un diagrama <em>wip</em> que puedes ajustar, y un <em>espejo</em> que refleja alguna estructura (como el contenido de un volumen) y es de solo lectura.

### how
pídele a tu readvisor que dibuje o revise un diagrama — escribe el código fuente <code>.merirmaid</code>; abrir el archivo lo renderiza. en un diagrama wip puedes hacer clic en el texto de un nodo para editar la etiqueta ahí mismo (con un contador de caracteres en vivo); los cambios estructurales pasan por tu readvisor mediante la píldora de chat. los nodos pueden enlazar a otros diagramas o documentos — haz clic en ellos para seguirlos, con migas de pan para volver atrás. un diagrama con errores muestra el error más el código fuente, nunca un panel en blanco. los diagramas espejo muestran una insignia de "espejo" en vez de asas de edición.

### ideas
- pídele a tu readvisor que diagrame un proceso o arquitectura sobre el que estás razonando, y luego refínalo en la conversación.
- enlaza un conjunto de diagramas entre sí con nodos en los que se puede hacer clic para construir un mapa navegable.
- combínalo con girraphs: un girraph para el argumento, un merirmaid para el flujo.

## canon
name: canon
path: ~/enough/canon/

### what
el almacén global de la máquina para <em>volúmenes</em> — carpetas de nivel superior que guardan texto que quieres conservar para siempre, o réplicas en caché ingeridas desde una ruta local, un sitio web, o artículos de wikipedia. compartido entre todos los proyectos y oculto de los árboles de archivos de los proyectos. aquí es donde vive ahora la antigua biblioteca <code>infoworld</code>.

### how
abre el modo canon desde la barra superior para la vista de dos paneles (proyecto ↔ volúmenes): arrastra para copiar un archivo entre ellos, shift-arrastra para moverlo, y usa la barra de ingesta para pedirle a tu readvisor que traiga una fuente a un volumen — o, sin agente, para ver la fuente y sus límites en una confirmación sencilla y hacer la ingesta tú mismo. o habla directamente con tu readvisor — puede listar, crear e ingerir en volúmenes cuando el interruptor del broker "canon tools" está activado (las ingestas de url también respetan tus interruptores de fetch_url). cada volumen mantiene un catálogo autogenerado de su contenido (<code>canon.cosm</code>, solo lectura) y metadatos ocultos que no tocas. haz doble clic en ese catálogo — o en un Holotype, o en cualquier otro archivo <code>.cosm</code> — para recorrerlo en el visor cosm; el botón <strong>catálogo del proyecto</strong> hace lo mismo con el de este proyecto (<code>rness/canon.cosm</code>). un texto que tiene una fabula lleva una pequeña insignia de gemelo teñida.

### ideas
- ingiere un sitio de documentación o una carpeta de notas para que tu readvisor pueda trabajar con ella sin conexión.
- mueve un artefacto terminado a un volumen para mantenerlo fuera del proyecto de trabajo pero aun así accesible desde cualquier lugar.
- haz clic en el pequeño botón de diagrama del icono de un volumen para ver su forma de un vistazo en el visor de merirmaid.

## cosm-viewer
name: visor cosm
path: *.cosm

### what
la vista estructurada de cualquier volumen <code>.cosm</code> — el catálogo de un volumen de canon, un Holotype (<em>holotipo</em>) de Comprise, la fabula de un texto, un fabulac, un árbol de producto independiente. el riel de la izquierda muestra el catálogo (su nombre, el lenguaje en el que está escrito, su dirección), sus módulos y clases con cuántos elementos tiene cada uno, y las comprobaciones; la columna de al lado muestra una tarjeta por elemento: su id, su clase y su estado, su nombre y su resumen, y luego cada uno de los demás campos. un id que apunta a otro elemento es un enlace, y una pregunta abierta lleva un <strong>?</strong> en un círculo.

### how
haz doble clic en un catálogo, un Holotype o cualquier archivo <code>.cosm</code> en canon, o haz clic en una fila <code>.cosm</code> del árbol de archivos. haz clic en un módulo o una clase del riel para ir allí, y en cualquier id enlazado para saltar a ese elemento — una píldora «volver» te devuelve. <strong>lente</strong> dibuja el volumen como diagrama en merirmaid; haz shift-clic en un nodo y elige <strong>mostrar el elemento</strong> para volver a su tarjeta. <strong>abrir en bruto</strong> muestra el propio archivo como texto plano, <strong>sobre este formato</strong> abre la especificación en la sección sobre el lenguaje de este volumen, ⌘F busca palabras en las tarjetas, y el botón de tamaño acopla el visor a un lado.

### ideas
- abre el catálogo de este proyecto con el botón <strong>catálogo del proyecto</strong> de canon para ver de un vistazo cada archivo, sus gemelos y sus atems.
- un Holotype grande muestra al principio cuarenta tarjetas por clase; <strong>mostrar todos</strong> trae el resto.
- las comprobaciones son las genéricas de MacroCOSM; las reglas propias de un Holotype son cosa de Comprise, y el riel dice cuántas les deja.

## docs
name: visor de documentos
path: docs/HELP_CENTER.md · docs/MACROCOSM_OES.md · docs/THYM.md · docs/ASCRIBE.md · docs/COMPRISE_OES.md

### what
donde se leen los cinco documentos de enough: este <strong>centro de ayuda</strong>, en el idioma de tu interfaz, y las cuatro especificaciones OES tal como las publica cosmoes.org: la <strong>especificación de MacroCOSM OES</strong>, la gramática común en la que está escrito cada archivo <code>.cosm</code>; <strong>Thym</strong>, el pequeño lenguaje en el que se escriben los programas de enough, con su compilador y su entorno de ejecución; <strong>Ascribe</strong>, el MiniCOSM del holograph, una persona descrita lo bastante bien como para que no haga falta ningún nombre; y <strong>Comprise OES</strong>, una empresa tal como la describe Comprise. las cuatro especificaciones están en inglés, y enough las mantiene al día desde cosmoes.org: al arrancar pide una vez su manifiesto y descarga solo un texto que haya cambiado (una preferencia de esta ventana lo apaga). cada uno viene en tres densidades: <strong>fabula</strong>, cada parte como una tarjeta; <strong>short</strong>, el documento para leer, tal como se escribió; y <strong>atem</strong>, el documento entero como un esquema de frases de una línea. una palabra que el documento define es un enlace discreto a su tarjeta, y el margen de una sección dice cuántas veces el resto del documento remite a ella y cuántos ejemplos contiene — haz clic en él para ver la tarjeta de la sección. una tarjeta empieza con su línea y su lugar en el documento, y luego dice el resto: de dónde vienen sus palabras, de qué está hecha, las comprobaciones que la tocan, las lentes que la dibujan, sus ejemplos y cada lugar que la menciona.

### how
abre el centro de ayuda con <strong>ayuda</strong>, arriba en la ventana de ui, y las especificaciones con <strong>MacroCOSM</strong>, a su lado, un pequeño menú con las cuatro: MacroCOSM OES, Thym, Ascribe y Comprise OES. la especificación de MacroCOSM también se abre desde <strong>sobre este formato</strong> en el visor cosm, que te deja en la sección correcta. los tres botones de la barra cambian la densidad (las flechas pasan de uno a otro), y el visor recuerda tu elección para cada documento. en <strong>short</strong>, <strong>contenido</strong> lista las secciones, un número de sección en el texto es un enlace, ⌘F busca, y un salto deja una píldora «volver adonde estabas». en <strong>atem</strong>, haz clic en cualquier línea para leer esa sección; ahí ⌘F busca solo en los nombres y las líneas. en <strong>fabula</strong>, el <strong>esquema</strong> junto a las tarjetas pasa a una página de sección, reduce las tarjetas a algunos tipos de elemento o a un solo MiniCOSM, y lista las comprobaciones; la ruta de migas de una tarjeta te lleva a su lugar en el short y la píldora de volver te trae de vuelta, <strong>grafo a su alrededor</strong> dibuja el elemento y sus vecinos en merirmaid (shift+clic en un nodo para <strong>mostrar el elemento</strong>), y ⌘F busca en las tarjetas de la página. la tarjeta de un ejemplo está viva: su bloque se lee como un volumen propio, dice si pasa las comprobaciones y se abre en una lente o en el visor cosm. el botón de tamaño acopla el visor junto a tu trabajo.

### ideas
- en el centro de ayuda, prueba primero <strong>atem</strong>: todo el manual en unas pocas pantallas, una línea por sección.
- en la especificación, empieza por la sección 2, el modelo en una página, y tenla acoplada junto a un Holotype en el visor cosm mientras aprendes a leer uno.
- la insignia de una especificación dice su edición; pasa el ratón por encima para ver si el texto vino de cosmoes.org y cuándo se revisó, o si es la copia que trae enough.
- en <strong>fabula</strong>, las burbujas de ayuda también son tarjetas: cada (?) de la app, con las partes del centro de ayuda a las que remite.
- en la especificación, abre un tipo desde la lista de referencia de <strong>atem</strong>: su tarjeta muestra sus campos, las listas cerradas que usan y el manifiesto que lo declara.

## canon-chip
name: chip de canon
path: notes.md → notes.md.fabulan.cosm

### what
el pequeño grupo en la cabecera de un texto, junto al chip de conversión, que dice si este texto tiene una <strong>fabula</strong>, su gemelo: un archivo <code>.cosm</code> escrito a su lado (<code>notes.md</code> → <code>notes.md.fabulan.cosm</code>) que desmonta el texto — las palabras en las que se apoya, las personas y cosas que nombra, las afirmaciones que hace y cómo las sabe, y los sucesos que cuenta. la insignia del gemelo está tintada cuando hay gemelo, hueca cuando no, y lleva un punto cuando el texto ha cambiado desde que se escribió su gemelo. nada se descompila por su cuenta: solo cuando tú lo pides.

### how
<strong>gemelo</strong> da la vuelta al lector hacia el gemelo, al mismo tamaño, en lugar del texto: las tarjetas del visor cosm, con <strong>volver al texto</strong> para regresar, <strong>compilar un short</strong> para escribir el gemelo como un <em>short</em> — un nuevo relato en markdown junto al texto, <code>notes.short-2026-10-23-1042.md</code>, como lo contó el autor o por peso (el pequeño ▾ elige; el gemelo recuerda cada short que se ha contado a partir de él) — <strong>lente</strong> para un diagrama y <strong>abrir en bruto</strong> para el propio archivo. si todavía no hay gemelo, el botón descompila primero y da la vuelta cuando termina. el botón <strong>atem</strong> te da el texto entero en una línea (mira la tarjeta del atem). <strong>descompilar</strong> crea el gemelo y <strong>actualizar el gemelo</strong> lo vuelve a crear; los dos abren antes una pequeña tarjeta: prosa o verso (enough sugiere uno; tú eliges) y dónde se ejecuta el modelo, y avisa si el gemelo ya está al día. el trabajo aparece como un aviso que puedes cancelar. con un modelo en marcha tarda un rato, y un mensaje que envíes mientras tanto espera su turno; sin modelo obtienes un andamio etiquetado — las palabras y los nombres, todavía sin afirmaciones —, y sin agente, la etiqueta dice <em>sin agente</em>.

### ideas
- descompila una vez un capítulo largo y lee luego las afirmaciones del gemelo como la lista de lo que el capítulo de verdad sostiene.
- <strong>atem</strong> y <strong>descompilar</strong> están también en el menú de shift-clic de canon y en el menú de opción+clic del árbol de archivos, y <strong>atem</strong> en el menú de nodos de merirmaid para un nodo que nombra un texto.
- un gemelo abierto en bruto es texto sencillo que puedes leer y editar; el visor cosm lo revisa por ti.

## fabula-card
name: descompilar… / el fabulac
path: notes.md → notes.md.fabulan.cosm · tool/ → tool.fabulac.cosm

### what
la tarjeta que viene antes de una descompilación, y la tarjeta del <strong>fabulac</strong> de una carpeta. en un texto pregunta dos cosas: si leerlo como <strong>prosa</strong> (un <code>fabulan</code>) o como <strong>verso</strong> (un <code>fabulap</code>) — enough sugiere uno por el aspecto del texto, y tú eliges — y dónde se ejecuta el modelo. lista el gemelo que el texto ya tiene de cada tipo, dice cuándo uno está al día, y cuando un gemelo aún lleva su nombre antiguo (<code>notes.md.cosm</code>) avisa de que descompilarlo de nuevo escribe el nombre nuevo y quita el archivo antiguo. en una carpeta de python muestra la construcción de su fabulac, <code>tool.fabulac.cosm</code>, en cinco etapas: reconocimiento e historia por reglas, y luego lectura, plegado y preguntas, que piden un modelo.

### how
<strong>descompilar</strong> o <strong>actualizar el gemelo</strong> la abre en un texto; <strong>construir su fabulac…</strong> en el menú de opción-clic de una carpeta, o <strong>construir y compilar…</strong> en un fabulac en el visor cosm, la abre en una carpeta. <strong>dónde se ejecuta el modelo</strong> es <em>aquí</em>, el modelo de esta máquina, salvo que elijas la nube para esta sola tarea, lo que solo se ofrece cuando la nube está abierta; una construcción en la nube admite un tope de llamadas al modelo por etapa. la construcción muestra su etapa, los archivos leídos y las llamadas hechas; <strong>cancelar</strong> conserva cada etapa terminada, y <strong>retomar</strong> sigue desde donde se paró mientras la carpeta no cambie. sin modelo, una construcción deja el <em>esbozo</em>, reconocimiento e historia, y dice qué espera. <strong>compilar</strong> cuenta el fabulac <strong>como código</strong>, un <em>cshort</em>, o como un <em>catem</em> a la profundidad line, overview o manual; lo que ha producido se lista debajo, cada uno con <strong>abrir</strong>.

### ideas
- construye una vez el fabulac de una herramienta pequeña y lee su catem a la profundidad overview antes de leer su código.
- sin agente, una construcción deja igualmente el esbozo: los archivos, sus interfaces, la historia y la licencia.
- un cshort es un texto para leer: enough nunca lo ejecuta.

## cshort
name: cshort / catem
path: tool.cshort-2026-11-05-1412/ · tool.catem-2026-11-05-1415.md

### what
aquello en lo que se compila un fabulac, leído aquí. un <strong>cshort</strong> es una carpeta de código fuente escrita solo a partir del fabulac, archivo por archivo, con <code>CSHORT.md</code>, que dice de qué elemento salió cada archivo, el pie que dice cómo se hizo y la licencia de la fuente. un <strong>catem</strong> es markdown que dice lo que un usuario puede hacer con el programa, a una profundidad: <code>line</code>, <code>overview</code> o <code>manual</code>.

### how
abre uno desde la lista de la tarjeta del fabulac, desde un aviso cuando termina una compilación, o desde el menú de opción-clic de la carpeta del cshort o del archivo del catem. los archivos de un cshort están a la izquierda; haz clic en uno para leerlo como texto plano. nada aquí lo ejecuta, lo abre en una terminal ni lo descarga para ejecutarlo: enough nunca ejecuta un cshort. esc cierra el visor.

### ideas
- lee primero <code>CSHORT.md</code>: dice de qué parte del fabulac se escribió cada archivo.
- pon un cshort junto al original y compáralos: lo que le faltó al fabulac le falta al cshort.

## dialectic-card
name: las preguntas
path: notes.md.fabulan.cosm → notes.md.fabulan.answers-2026-11-05-1200.cosm

### what
lo que un volumen pregunta a una persona: lo que su fuente no podía decir, cada cosa una <strong>pregunta</strong> sobre un lugar concreto, de una sola clase (palabras, una elección, sí o no, un número, una fecha, un elemento, las líneas que lo muestran), hecha a alguien: el autor, alguien experto en la obra, quienes lo hicieron, quien lo sepa. la tarjeta muestra una o dos a la vez, comprueba la respuesta mientras escribes y guarda lo que dices en una <strong>sesión</strong> que envías entera. la sesión de un gemelo se escribe a su lado como un archivo de respuestas; el volumen solo cambia cuando las respuestas se <strong>incorporan</strong>.

### how
<strong>preguntas</strong> en la barra del visor cosm la abre, con cuántas están abiertas; también la abren la tarjeta fabula y el aviso de una descompilación o una construcción que trajo preguntas. responde, o di <strong>no lo sé</strong> (también es una respuesta: el lugar queda abierto, con tus palabras), <strong>prefiero no decirlo</strong> (se guarda como un hecho) o <strong>saltar por ahora</strong>. <strong>guardar estas, y las siguientes</strong> avanza; <strong>enviar la sesión</strong> las anota todas y dice, pregunta por pregunta, qué se anotó, qué se saltó y qué se rechazó, y una respuesta rechazada vuelve con lo que escribiste. <strong>incorporar las respuestas</strong> las lleva al volumen, con el modelo de aquí salvo que elijas la nube para ese único trabajo; lo que espera a que un modelo relea su elemento se lista, y una pregunta que una comprobación planteó contra una respuesta va primero. <strong>volver a preguntar</strong> reabre una pregunta incorporada o rechazada; un volumen sin preguntas puede <strong>plantear las preguntas</strong>, por reglas.

### ideas
- «no lo sé, pero la responsable de soporte lo sabría» es una buena respuesta: el campo queda abierto con esas palabras, para preguntar a la siguiente persona.
- responde dos, envía, incorpora: una sesión corta también es una sesión.

## holograph
name: las preguntas de un holograph
path: self/ → self/D/questions.cosm

### what
un <strong>holograph</strong> (Ascribe) describe a una persona sin nombre, y se llena preguntándote sobre ti. sus preguntas son <strong>solo para el titular</strong>; lo que dices se anota en su propio módulo D, con tus palabras, y nunca sale de él. una respuesta que parece un dato personal (una dirección de correo, un número de teléfono, una fecha de nacimiento, una dirección postal, el nombre de una persona) se rechaza, con palabras que dicen por qué, y no se escribe nada de ella. una lectura de tu propio texto propone <em>candidatos</em>, y de cada uno se pregunta <strong>sí</strong>, <strong>en parte</strong> o <strong>no</strong>. no se ofrece ninguna línea de modelo: nada de un holograph va a un modelo en la nube.

### how
ábrela con <strong>preguntas</strong> en el visor cosm sobre el holograph; primero se pregunta por la parte más delgada del yo, y un holograph se incorpora enseguida, por reglas. <strong>el isograph…</strong> hace su proyección pública con un programa tuyo que toma el holograph solo: clases, palabras FEED, franjas y décadas, cada una marcada stated, y ningún nombre, ninguna palabra tuya, nada de la dialéctica. la publicación se anota en el holograph antes de escribir el isograph a su lado, uno por época.

### ideas
- describe a las personas por lo que son para ti («un práctico del puerto jubilado»), o con un seudónimo que declares en el catálogo.
- di <strong>en parte</strong> a un candidato que casi acierta, y luego dilo a tu manera.

## atem-card
name: tarjeta del atem
path: (the atem of a text or a passage)

### what
un <strong>atem</strong> es la reducción más ajustada, justa, completa y en lenguaje llano de un texto o de un pasaje. la tarjeta pone <em>la línea</em> en grande — una frase de quince a veinticinco palabras que dice lo que dice el todo — y luego tres partes breves: <strong>foco</strong>, lo que está pasando y hacia dónde te hace mirar el autor; <strong>empuje</strong>, lo que el autor quiere que te lleves; <strong>tirón</strong>, lo que de verdad deberías llevarte, con los supuestos ocultos y las dependencias nombrados. donde empuje y tirón no coinciden suele estar lo más útil de la tarjeta. deja el puntero sobre una etiqueta para ver su definición. cuando el modelo dice cómo se saben las afirmaciones, una franja muestra las seis posturas con sus cuentas.

### how
pide uno con <strong>atem</strong> en el chip de canon o en un menú de archivo (el texto entero: su atem se guarda en la fabula del texto), o selecciona un pasaje y haz clic derecho: <strong>atem de la selección</strong> está en el lector, el editor, un artículo de wikisink, el centro de ayuda, la especificación y una página de texto de composure. mientras lee, la tarjeta lo dice y ofrece cancelar. <strong>copiar</strong> copia la línea (⇧-clic copia las cuatro partes), <strong>fijar en el gemelo</strong> guarda el atem de un pasaje en el gemelo del texto junto con su lugar, y <strong>abrir el gemelo</strong> muestra el gemelo al que fue el atem del texto entero. sin modelo en marcha, la tarjeta muestra un andamio: la línea y el foco salen de las primeras frases del texto, y empuje y tirón siguen siendo preguntas abiertas.

### ideas
- lee el atem de un borrador antes de enviarlo. si la línea no es lo que querías decir, el borrador tampoco.
- fija los atems de los pasajes clave de una pieza larga y tendrás una columna vertebral para revisar.
- compara empuje y tirón en el argumento de otra persona: el hueco entre ambos es donde objetar.

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

## composure
name: composure
path: rness/io/composure/

### what
el lienzo que siempre está ahí, detrás de todo lo demás — la capa base de la ventana, no un modo en el que entras y del que sales. una <strong>composure</strong> es un archivo <code>.comp</code>: cajas de escritura (<em>módulos</em>) y tinta a mano alzada sobre un escritorio sin bordes que puedes desplazar y ampliar. se abre en cualquier navegador como una página normal, sin enough instalado, porque el archivo en sí es html corriente.

### how
la barra de herramientas recorre la parte de arriba: el título (para renombrarlo, escribe y haz clic fuera), el interruptor lectura/edición, las herramientas, deshacer/rehacer, el grupo de zoom, la búsqueda, el panel de comentarios y el menú de composures. desplaza el lienzo con dos dedos, con espacio+arrastrar o con el botón central; amplía con pellizco, ⌘+rueda, ⌘+ / ⌘− / ⌘0, o con «encajar». no hay botón de guardar — todo se va escribiendo sobre la marcha, y una composure que abres y nunca tocas no llega a escribir ningún archivo. aléjate lo suficiente y cada módulo se pliega hasta quedarse en su <em>cara</em>: su título, tan grande como quepa, con el cuerpo simulado, de modo que sesenta tarjetas se leen como sesenta títulos.

### ideas
- ten un tablero por proyecto, como el mapa que miras antes de ponerte a escribir.
- un módulo <code>.comp</code> que apunta a otro <code>.comp</code> convierte un tablero en un desglose: al hacer clic, el lienzo cambia bajo tus pies.
- selecciona un pasaje dentro de un módulo y viajará con tu siguiente mensaje a tu readvisor, en un bloque de código y con su etiqueta.

## composure-modules
name: módulos
path: (inside a .comp file)

### what
las cajas de una composure. un módulo de <strong>texto</strong> es escritura — encabezados, listas, listas de tareas, citas, enlaces, resaltados — con tantas páginas dentro como quieras. los otros cinco apuntan a algo: un <strong>archivo</strong> de este proyecto, un artículo de <strong>wikisink</strong>, un <strong>enlace web</strong>, una <strong>página web</strong> en caché, o una <strong>imagen</strong>. un módulo que apunta muestra una vista previa en vivo mientras lees, y al hacer clic se abre la cosa de verdad.

### how
el botón de añadir módulo abre una lista corta con los seis tipos. con un módulo seleccionado en modo edición, el inspector aparece a su lado: muestra de fondo, tamaño del texto, páginas, delante/detrás, el campo propio de cada tipo (un selector de archivos, una búsqueda de artículos, una dirección), y un botón de comentario. arrastra para mover, arrastra un asa para redimensionar, las flechas para moverlo poquito a poco (con mayús, a pasos más grandes), suprimir para quitarlo — con un aviso previo si tiene texto dentro, y ⌘Z para recuperarlo. el texto que se sale de su caja te ofrece una página nueva en vez de crecer en silencio.

### ideas
- ponle un título a un módulo y conservará su nombre cuando te alejes más allá del tamaño de lectura.
- las muestras <code>tinta</code> y <code>transparente</code> son para dar estructura — una tarjeta oscura para una fila de encabezado, una transparente para una etiqueta que no es una tarjeta en absoluto.
- apunta un módulo al archivo que no dejas de reabrir; el tablero se vuelve un escritorio con los papeles adecuados ya encima.

## composure-tools
name: herramientas
path: (the composure toolbar)

### what
cuatro herramientas, y solo existen mientras editas: el <strong>puntero</strong> (V) selecciona, mueve, redimensiona y hace selección por recuadro; el <strong>texto</strong> (T) mete el cursor dentro de un módulo; el <strong>lápiz</strong> (P) dibuja; la <strong>goma</strong> (E) borra. la tinta son polilíneas a mano alzada tendidas sobre el escritorio, debajo de los módulos, así que una nota puede cruzar tres tarjetas y una flecha puede unir dos.

### how
con el lápiz, simplemente dibuja — la línea se suaviza y se simplifica al soltar. mantén <strong>mayús</strong> mientras arrastras y obtendrás un segmento recto con una punta de flecha al final. la goma es un círculo que mantiene el mismo tamaño en pantalla por mucho que te alejes; al arrastrarla por encima de una línea, borra la parte que queda bajo el círculo y deja los dos extremos como trazos separados, y ⌘Z devuelve la línea de una pieza. coge un trazo con el puntero haciendo clic cerca de él — el inspector te ofrece entonces los cinco colores de tinta, y suprimir lo borra. las líneas adelgazan más despacio de lo que encoge el dibujo, así que un esbozo visto de lejos sigue leyéndose como un esbozo.

### ideas
- rodea con un círculo las tres tarjetas que van juntas antes de decidir cómo se llama el grupo.
- traza flechas con mayús+arrastrar entre módulos para mostrar qué va después de qué, y luego mueve los módulos; la flecha se queda donde la dibujaste, que suele ser la respuesta honesta.
- dibuja en rojo sobre un tablero que estás revisando y borra las marcas a medida que las vas resolviendo.

## journal
name: diario
path: rness/io/composure/

### what
un form de composure para llevar un registro con fecha. un módulo, una entrada por página. al abrir un diario aterrizas en la página de <em>hoy</em> con el cursor ya dentro — y esa página solo existe en memoria hasta que escribes algo, así que abrir el diario y arrepentirte no deja nada atrás.

### how
escribe. la entrada se guarda sola sobre la marcha, y si te vas sin archivarla, el diario vuelve a abrirse en ese mismo borrador sin terminar. cuando la entrada esté lista, pulsa <strong>archivar esta entrada</strong>: la página queda sellada con la fecha y pasa a ser de solo lectura para siempre — enough se negará a cambiarla después, y el cursor no entrará en ella. archivar te lleva a una página nueva para la próxima vez. hojear hacia atrás por las entradas archivadas no tiene riesgo: pasar una página en la que no escribiste no guarda absolutamente nada. sobre el texto archivado sí puedes comentar, que es justo para lo que se archiva.

### ideas
- archiva al final de una sesión de trabajo, no al final del día; la fecha es un dato, no una fecha límite.
- comenta una entrada archivada antigua cuando resulte que estaba equivocada — el registro se queda, y la segunda lectura se sienta a su lado.
- pídele a tu readvisor que lea el diario cuando quieras un resumen de por dónde fue realmente un trabajo largo.

## readvisor-panel
name: panel del readvisor
path: (the right-hand panel)

### what
la conversación, en una columna propia junto a lo que sea que estés haciendo. arriba aparece el nombre de tu <strong>readvisor jefe</strong>, y al lado los demás readvisors que tengas activados — en la conversación normal responden con una sola voz, apoyándose en todas esas perspectivas.

### how
⌘/ lo abre y lo cierra; ⇧⌘/ le da toda la ventana y ⌘/ otra vez lo devuelve a su sitio. se coloca junto al lienzo o junto a cualquier modo abierto, así que nunca tienes que cerrar lo que estás leyendo para preguntar por ello. selecciona texto — en un documento, en un artículo de wikisink, en un módulo de composure — y aparecerá una ficha encima de la caja de mensaje que muestra exactamente lo que se va a adjuntar; la × la descarta. cuando un turno termina con el panel cerrado, aparece un punto en su botón de la barra superior.

### ideas
- déjalo acoplado mientras escribes y pregunta de pasada; es un colega en el escritorio de al lado, no una ventana que abres.
- adjunta una selección en vez de describirla — las palabras exactas cruzan, en un bloque de código, con su procedencia.
- dale toda la ventana cuando quieras leer bien una respuesta larga, y vuelve a acoplarlo para ponerte a trabajar con ella.

## council
name: consejo
path: (a composure whose form is council)

### what
varios readvisors y tú, pensando en una sola cosa por turnos, por escrito, en el lienzo. un consejo es una composure normal con el encargo arriba y una tarjeta por intervención debajo, con un tinte por cada participante y encabezada con un nombre y un número de turno. las intervenciones pertenecen al motor: puedes moverlas, cambiarles el estilo, dibujar tinta encima y comentarlas, pero no reescribirlas.

### how
rellena el encargo — entrada, parámetros, restricciones, salida deseada — marca quién está en la sala, dale a quien quieras un <em>cometido</em> de una línea si está ahí para algo concreto («cuida la continuidad», «defiende al lector»), fija el máximo de rondas, y pulsa convocar. a partir de ahí lo llevas tú: <em>siguiente turno</em> toma una intervención, <em>correr una ronda</em> da la vuelta entera, <em>correr hasta el final</em> llega al tope de rondas, <em>pausa</em> lo detiene, <em>concluir</em> le pide la decisión al jefe. el compositor de abajo es tuyo: lo que digas ocupa el siguiente hueco sin costarle el turno a nadie, y un <code>/pal</code> escrito ahí manda una sola pregunta destilada al modelo en la nube y trae la respuesta como una intervención. al concluir, lo que el consejo decidió se escribe con la forma que elegiste — una tarjeta resaltada, un archivo markdown en la ruta que tú quieras, o una composure nueva entera de tarjetas junto a esta — y la transcripción se exporta a <code>rness/knowledge/councils/</code>. un consejo concluido se puede <em>volver a convocar</em>: un consejo nuevo con la misma sala, los mismos cometidos y lo que este decidió como punto de partida.

### ideas
- dale a un readvisor el argumento contrario y averigua si sobrevive al contacto con los demás.
- un cometido es la forma más barata de evitar que tres readvisors digan lo mismo de tres maneras.
- elige documento como salida cuando la decisión deba salir del lienzo convertida en un archivo que puedas citar, o composure cuando lo que quieras sea la forma de la decisión y no sus párrafos.
- di algo tú en cuanto un consejo empiece a dar vueltas; una interrupción sale más barata que otra ronda.
- vuelve a convocar en vez de empezar de cero cuando la respuesta era la buena pero no estaba terminada.

## chief-readvisor
name: readvisor jefe
path: (the name on every reply)

### what
el único readvisor con el que hablas siempre. tiene un nombre — Ed de fábrica — y ese nombre firma cada respuesta de la conversación, encabeza el panel del readvisor, y habla primero en un consejo. el nombre es global: uno por máquina, guardado junto a tu tema y tu idioma de interfaz, no dentro de un proyecto concreto.

### how
pulsa el botón de renombrar que hay junto a la × de esta cabecera, escribe un nombre nuevo y guarda. de 1 a 24 caracteres: letras y dígitos, más espacio, guion, apóstrofo y punto, en el alfabeto que prefieras. todas las superficies que muestran el nombre se ponen al día al instante, sin recargar nada. un consejo que ya ha hablado conserva el nombre con el que se firmaron sus intervenciones — las intervenciones se atribuyen por nombre, y un cambio a mitad de camino se leería como dos personas distintas.

### ideas
- elige algo que dirías en voz alta; vas a estar leyéndolo todo el día.
- renombra antes de convocar un consejo, no durante uno.

## pal
name: pal
path: (the OPRO-API model slot)

### what
una sola pregunta, enviada hacia fuera, a la vista. un <strong>pal</strong> es el modelo en la nube que ya configuraste en la ranura OPRO-API, alcanzado una vez, a mano, desde un turno que por lo demás es enteramente local. no hay ajuste de pal, ni cuenta de pal, ni un segundo interruptor: si la ranura de nube funciona, un pal funciona, y si no, la explicación de siempre del broker es toda la historia. escribir <code>/pal</code> es el consentimiento — no hay paso de confirmación, porque un paso de confirmación que aparece siempre es un botón que la gente aprende a pulsar. lo que lo sustituye es que el prompt que sale de esta máquina se te muestra palabra por palabra, antes de la respuesta, cada vez, en vivo y también después de recargar.

### how
empieza un mensaje con <code>/pal</code> y el resto es la pregunta: <code>/pal ¿cuál es el estado del arte en reconocimiento de voz en el dispositivo?</code>. escribe <code>/</code> como primer carácter y aparece una fila de sugerencia encima del compositor que nombra el modelo al que se llegaría; tab o un clic la completa, y cuando la ranura de nube está cerrada la fila se pone gris y dice por qué. tu readvisor lo piensa entonces aquí primero — su propio conocimiento, los archivos de este proyecto, las herramientas de wiki —, resuelve qué es lo que de verdad no puede zanjar en local, manda <strong>un</strong> solo prompt afinado, y te responde con su propia voz diciendo qué partes vinieron del pal. una llamada por cada mensaje con <code>/pal</code>. el mismo comando funciona en el compositor de un consejo, donde el jefe destila el encargo y toda la transcripción en el prompt; la respuesta cae como una intervención gris cuya primera línea pliega lo que se envió.

### ideas
- pon <code>:online</code> al final del id del modelo en los ajustes de OpenRouter — <code>anthropic/claude-sonnet-4.5:online</code> — y tu pal responde con la web delante. cobra un extra por cada búsqueda, y es el arreglo para un modelo congelado en su fecha de corte de entrenamiento.
- resérvalo para lo que un modelo local no puede tener: las noticias de esta semana, una biblioteca publicada el mes pasado, una segunda opinión sobre un juicio que ya has hecho.
- lee la burbuja de salida antes de leer la respuesta. es el único sitio que muestra exactamente qué salió, y está ahí a propósito.

## agentmode
name: sin agente
path: ~/enough/config/ui.json → agent_free

### what
un solo interruptor para toda la máquina. <strong>agente libre</strong> es como enough ha funcionado siempre: corre un modelo, tu readvisor lee a tu lado, los consejos se reúnen, las habilidades y los paradigmas dan forma a las respuestas. <strong>sin agente</strong> es nada de IA — no arranca ningún modelo, y todo lo que necesita uno se hace a un lado: el panel readvisor y su botón, la ficha de selección, «preguntar a tu readvisor», la breve introducción, los paradigmas, readvisors y habilidades de la barra lateral, los consejos y <code>/pal</code>. lo que queda es tuyo para trabajarlo a mano: composure, el diccionario, wikisink, canon, convertir, paginar, girraph y merirmaid, el visor cosm, y el visor de documentos con esta ayuda dentro.

### how
deslízalo en la ventana de ui, junto al idioma, o en la ventana de modelo, donde es el mismo interruptor. la etiqueta cambia con él: <em>agente libre</em> cuando está apagado, <em>sin agente</em> cuando está encendido, y la insignia de la barra superior dice <em>sin agente</em> mientras lo esté. encenderlo detiene el modelo enseguida; apagarlo lo vuelve a arrancar de la forma habitual, y la ventana de modelo muestra cómo carga. mientras está encendido todavía puedes instalar y borrar modelos, pero no cambiar a uno. la barra de ingesta de canon te pide confirmar la fuente, la profundidad y los límites, y luego descarga por su cuenta; y descompilar, atem y compilar siguen funcionando — por reglas, con la etiqueta sin agente. la elección se guarda en <code>~/enough/config/ui.json</code>, y cada proyecto se abre como lo dejaste.

### ideas
- enciéndelo cuando la máquina necesite su memoria para otra cosa: un proyecto se abre en segundos, sin un modelo de 5 a 17 GB que cargar.
- escribe un primer borrador sin agente, luego vuelve a deslizarlo y pregúntale a tu readvisor qué le parece.
- en un avión, o donde prefieras que nada corra en segundo plano, sin agente es el ajuste honesto.

## thym
name: ejecutar con…
path: *.thym → a plan, a run, a trace

### what
<strong>thym</strong> es el pequeño lenguaje en el que se escriben los programas de enough. un <strong>programa</strong> es un archivo <code>.thym</code> que dice, paso a paso, qué hacer con un texto — desmontarlo en su fabula, medir cómo está escrito, empaquetarlo — y por qué. cada paso nombra un movimiento; un paso que le pregunta al modelo lleva un rombo relleno, y su respuesta se comprueba contra el contrato del movimiento antes de guardar nada. un programa también es un documento: abre un archivo <code>.thym</code> y lo lees en las tres densidades — su porqué y sus pasos en una línea cada uno (atem), tal como se escribió (short), o como tarjetas con los contratos de cada paso colgando debajo (fabula).

### how
<strong>ejecutar con…</strong> está en los menús de opción+clic y de shift-clic de un texto, en la tarjeta de un archivo de canon y en la de un programa. elige un programa — primero los de este proyecto, luego los de canon, luego los que vienen con enough; uno que no compila aparece en gris, con el motivo — y su <strong>plan</strong> se muestra antes de que nada se ejecute: cuántos nodos, cuántos le preguntan a un modelo y si cabe en esta máquina. <strong>ejecutar</strong> lo pone en marcha; la tarjeta lo sigue nodo a nodo y puedes cancelarlo. cuando se completa, su <strong>traza</strong> se abre en el visor cosm, una tarjeta por nodo con cada comprobación y su veredicto, y lo que hizo queda junto al texto en el árbol (<code>notes.package.cosm</code> y <code>notes.thym/</code> para un paquete). sin agente, solo se ofrecen los programas en los que ningún paso le pregunta a un modelo, y una línea dice cuántos se quedaron fuera.

### ideas
- lee el plan de un programa antes de ejecutarlo sobre un texto largo: la línea del coste te dice cuántas veces se le va a preguntar al modelo.
- un programa que no pregunta nada se ejecuta en un momento, sin agente o no: <code>words</code>, <code>count</code> y <code>cut</code> nunca necesitan un modelo.
- una ejecución rechazada no es una ejecución rota: su traza dice qué paso la detuvo y por qué, y no se guardó nada de lo que estaba haciendo.
- la sección 13.4 del centro de ayuda lo tiene todo: los tres programas que vienen con enough, la traza y las diez escalas.

## package
name: paquete
path: *.package.cosm · *.thym/

### what
un <strong>paquete</strong> es un texto que sale de casa con lo que lo describe: el texto exactamente como se escribió, su fabula (su gemelo), el morfo del autor cuando lo hay — cómo se aparta el texto, en diez escalas, del relato más llano de esa misma fabula — y su contexto. viene en dos formas, lado a lado: un archivo, <code>notes.package.cosm</code>, que viaja, y una carpeta, <code>notes.thym/</code>, que puedes abrir archivo por archivo. su catálogo lista cada archivo con su huella, nombra el programa y la ejecución que lo hicieron, y nunca nombra al autor salvo que el texto lo haga.

### how
abre cualquiera de las dos formas y el visor cosm muestra la tarjeta del paquete: lo que contiene (cada archivo es un enlace, en la forma de carpeta), qué lo hizo y cuándo, <strong>abrir el texto</strong>, y <strong>leer a través de…</strong>, que cuenta el texto de nuevo en un morfo que tú eliges — el del paquete, para leerlo a la manera del autor, uno tuyo, o el morfo nulo. el texto de dentro nunca se toca. <code>publish-story</code>, uno de los programas que vienen con enough, deja un paquete junto a cualquier texto sobre el que lo ejecutes. <strong>empaquetar…</strong>, en un texto cuya fabula está al día, hace uno por reglas, sin preguntarle nada al modelo, y puede sellarlo también, con una clave que se te muestra una sola vez y no se guarda en ninguna parte; <strong>desempaquetar…</strong>, en cualquier forma de un paquete, comprueba primero cada huella, vuelve a escribir el texto y su gemelo a su lado, y pide la clave cuando el paquete está sellado.

### ideas
- envía el archivo único: todo lo que un lector necesita para leerlo a su manera va dentro.
- abre <code>morph.cosm</code> en la forma de carpeta para ver las diez escalas del autor, con las frases que movieron cada una.
- las huellas están ahí para que un lector pueda saber que el texto es el que se empaquetó.
- la sección 12.6 del centro de ayuda dice qué contiene un paquete, cómo guarda su clave uno sellado y qué comprueba primero el desempaquetado.

## reading
name: lectura
path: *.read-*-YYYY-MM-DD-HHMM.md

### what
una <strong>lectura</strong> es el texto de otra persona contado de nuevo a través de un morfo — el tuyo, el del autor o el morfo nulo — en tu máquina, como un archivo nuevo junto al texto. va etiquetada dos veces: <code>read_through:</code> arriba del todo, y una línea de pie al final: <em>a reading of notes.md through plain-letter, made here on … ; the text stands unchanged</em>. la franja bajo la cabecera del lector muestra esa etiqueta mientras la lectura esté abierta, en cualquiera de las dos facetas y de los dos tamaños, y no se puede cerrar: una lectura nunca se hace pasar por el texto.

### how
pide una con <strong>leer a través de…</strong> en un paquete, o en un texto que tenga fabula; elige un morfo, y la lectura se abre en cuanto está escrita, como <code>notes.read-plain-letter-2026-11-01-1042.md</code> (con <code>-2</code>, <code>-3</code> cuando ya hay una de ese minuto). una lectura necesita un modelo — <code>read</code> no tiene sustituto por reglas —, así que sin agente la tarjeta lo dice y no lee nada. una lectura de una lectura se rechaza: una lectura lee una fabula, y una lectura es un relato.

### ideas
- lee un informe denso a través del morfo nulo para ver exactamente lo que afirma, una afirmación por frase.
- lee una carta a través de tu propio morfo para oír cómo lo habrías dicho tú, y luego vuelve al original.
- guarda las lecturas: cada una nombra su morfo y su día, así que puedes poner lado a lado las lecturas de un mismo texto.
- la sección 12.6 del centro de ayuda trata de las lecturas y su etiqueta; la sección 13.4, de los morfos a través de los que se cuentan.

## thym-editor
name: un programa mientras lo escribes
path: *.thym in the editor

### what
abre un archivo <code>.thym</code> en el editor y una franja bajo la barra de herramientas dice, cada vez que haces una pausa, qué saca de él el <strong>compilador</strong>: <em>compila</em>, o la línea que rechaza, la comprobación que la rechazó y las propias palabras del compilador, que nombran la instrucción y, cuando se conoce, el arreglo. también dice qué gramática pide la primera línea — <code>thym 0</code> o <code>thym 1</code>, y qué tiene que decir un programa en <code>thym 0</code> para usar una palabra de <code>thym 1</code> — y, en cuanto compila, qué toma el programa, qué da y cuántos de sus pasos preguntan a un modelo. comprobar solo lee: nada se ejecuta y no se pregunta a ningún modelo.

### how
<kbd>F8</kbd> pone el cursor en la línea que nombra el compilador, con la línea entera seleccionada; <kbd>shift</kbd>+<kbd>F8</kbd> vuelve atrás. <strong>los movimientos…</strong> abre Thym a mano, donde <strong>ponerlo</strong> escribe una llamada en el cursor. <strong>planificar y ejecutar…</strong> abre ejecutar con… sobre este programa: un plan y una ejecución leen el archivo tal como está guardado, así que guarda antes para planificar lo que ves. un programa incluido nunca se edita donde está: cópialo al proyecto (desde su página, o desde los programas para empezar) y cambia la copia.

### ideas
- escribe primero la línea de versión: <code>thym 1</code> abre las carpetas, los bucles que recogen, <code>keeps</code>, <code>depth</code> y varias salidas.
- deja un rechazo en pantalla y léelo entero: dice qué instrucción y, casi siempre, qué escribir en su lugar.
- mantén pequeño un programa y planifícalo sobre una entrada real antes de confiarle una ejecución larga.

## thym-moves
name: Thym a mano
path: the moves, and the programs to start from

### what
<strong>los movimientos</strong> son todos los pasos que un programa puede llamar, según las declaraciones que lee el compilador: cada uno con su firma (lo que toma, sus palabras como <code>as</code>, <code>with</code>, <code>to</code>, y lo que da), si pregunta a un modelo, las comprobaciones que mantiene su contrato, su andamio para una ejecución por reglas, el formato que lo declara y si solo <code>thym 1</code> lo ve. están agrupados por ese formato y se buscan por cualquiera de sus palabras. <strong>programas para empezar</strong> son los incluidos con enough, cada uno con su línea <code>why:</code>.

### how
escribe en la búsqueda para acotar la lista; <kbd>↓</kbd> pasa de la búsqueda al botón del primer movimiento. con un programa abierto en el editor, <strong>ponerlo</strong> escribe una llamada del movimiento en el cursor y selecciona su primer operando para que lo renombres. <strong>leerlo</strong> abre un programa incluido como documento; <strong>copiar a este proyecto para cambiarlo</strong> escribe una copia tuya en <code>programs/</code> y la abre en el editor, y el archivo incluido queda como está.

### ideas
- busca el nombre de una comprobación para encontrar los movimientos que la mantienen.
- cambia a <code>thym 0</code> para ver qué puede llamar un programa más antiguo.
- empieza por el programa incluido más cercano a lo que quieres, y cambia una copia.
