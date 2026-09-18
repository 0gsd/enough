<!-- enough help content. One `## <id>` section per (?) bubble.
     Edit freely: `name:`/`path:` head the section; `### what`,
     `### how`, `### ideas` bodies may contain inline HTML.
     Four expansion tokens, all resolved client-side so nothing here
     drifts from what's actually installed:
       {{skills-list}} {{roles-list}} {{paradigms-list}}
         → the live installed set (see /api/help/defaults)
       {{convert-formats}}
         → the convertible-file-type table, with this machine's engine
           availability (see /api/convert/formats). Never hand-list
           file extensions in help text; use the token. -->

## wikisink
name: wikisink
path: ~/enough/wikisink/

### what
deine lokale, offline Kopie eines Ausschnitts der englischen Wikipedia — ein einzelnes Kiwix-ZIM-Archiv, an Ort und Stelle gelesen, nie entpackt, sodass der Dateimanager nur die Artikel zeigt, die du ausdrücklich speicherst. der 🚰-Button öffnet einen browserartigen Reader mit Volltextsuche, Querverweisen, einem Zufallsartikel-Würfel, einer Readvisor-Chat-Pille, Kommentaren und einem einzigen <strong>Speichern-Button</strong>, dessen Flyout zwei Ziele bietet (den <code>wiki/</code>-Ordner dieses Projekts, oder die globale <code>~/enough/cacheawl/wiki/</code>-Cachebox, projektübergreifend geteilt). deine Readvisors können das ganze Archiv über ihre Wiki-Tools durchsuchen und lesen.

### how
der erste Klick auf 🚰 startet den Einrichtungsassistenten: eine Größe wählen (top-1M-Artikel ohne Bilder ≈ 16 GB ist die Vorgabe; komplettes Englisch ≈ 49 GB; auch kleinere Optionen), einen Speicherordner wählen (externe Laufwerke funktionieren), bestätigen, und den fortsetzbaren Download laufen lassen — jederzeit pausieren, beenden, fortsetzen. du kannst <em>mehrere Installationen</em> an verschiedenen Orten behalten (etwa das volle Archiv auf einem externen Laufwerk plus ein kleines auf der internen Platte) und in der ⚙-Installationsliste zwischen ihnen wechseln; ist ein Laufwerk getrennt, zeigt seine Installation einfach als nicht erreichbar, bis das Laufwerk zurückkommt. einmal installiert, bitte deinen Chef-Readvisor um einen <strong>wikisink</strong>-Lauf, um deine gespeicherten/kommentierten („beobachteten“) Artikel aus der echten Wikipedia zu aktualisieren und einen Bericht zu bekommen: Änderungen an beobachteten Artikeln, Bearbeitungsspitzen, Aufrufe-Gewinner &amp; -Verlierer und verdächtige Löschungen. der 🛡-Button an jedem Artikel ist der <em>Löschungs-Override</em>: deine lokale Kopie für immer behalten, von Updates ausgeschlossen. ⚙ öffnet den Installationsmanager, einschließlich Ersatz des Basisarchivs, wenn ein neuerer Snapshot erscheint. danach musst du nicht suchen: existiert ein neuerer Build deiner Variante, erscheint eine kleine Pille in der Reader-Werkzeugleiste (<code>neuerer Snapshot: Datum · Größe</code>) — klicken, Größe bestätigen, und dasselbe In-Place-Upgrade läuft, lädt erst herunter und tauscht erst ein, wenn es fertig ist. die Prüfung geschieht höchstens einmal am Tag, blockiert den Reader nie und bleibt still, wenn du offline bist.

### ideas
- speichere die Artikel, auf die sich ein Projekt stützt, in seinem <code>wiki/</code>-Ordner — Kopien in voller Wiedergabetreue, die wieder im Reader öffnen, jede mit eingebautem CC-BY-SA-Zuordnungsmanifest.
- kommentiere Behauptungen, an denen du zweifelst, und lass später einen wikisink-Lauf laufen — Kommentare überstehen Artikel-Updates (neu angeheftet oder verwaist, nie verloren), und kommentierte Artikel werden automatisch beobachtet.
- wenn ein wikisink-Bericht eine verdächtige Löschung meldet (gelöscht wegen „Relevanz“ statt Qualität — der klassische Fall), öffne den Artikel und drück 🛡, bevor das nächste Mal das Basisarchiv getauscht wird.

## project-wiki
name: wiki/
path: wiki/

### what
Wikipedia-Artikel, die aus dem wikisink-Browser in dieses Projekt gespeichert wurden (Speichern-Button → „dieses Projekt“). jeder gespeicherte Artikel ist ein Ordner: <code>article.html</code> (der Artikel genau so, wie ihn das Archiv hatte — anklicken, um ihn im wikisink-Viewer zu lesen, volle Wiedergabetreue, Infoboxen inklusive) plus <code>_manifest.md</code> (Quell-URL, CC-BY-SA-Lizenz, Abrufdatum, Herkunft).

### how
wird automatisch beim ersten projektweiten Speichern angelegt — keine Einrichtung nötig. wikisink-Update-Läufe behandeln alles hier als <em>beobachtet</em>: aus der echten Wikipedia aktualisiert und im Bericht erwähnt. erneutes Speichern eines Artikels überschreibt den Ordner mit der frischesten Kopie; zum Entfernen kurz mit der Maus über seinen Ordner im Baum bleiben und auf das erscheinende 🗑 klicken. gespeicherte Kopien sind nicht zum Von-Hand-Bearbeiten gedacht — sie würden aus dem Takt mit dem Archiv geraten. (die andere Wahl des Speichern-Buttons speichert stattdessen in die globale <code>~/enough/cacheawl/wiki/</code>-Cachebox, geteilt über alle Projekte.)

### ideas
- gespeicherte Artikel öffnen im Reader auch dann, wenn das Laufwerk des Archivs abgesteckt ist — sie sind deine Offline-Offline-Kopien.
- deine Readvisors lesen Artikel über ihre Wiki-Tools (saubere Textextraktion), sodass sie sich sowohl auf gespeicherte als auch auf archivierte Artikel stützen können.
- Wikipedia-Text steht unter CC BY-SA: landet ein Teil eines Artikels in etwas, das du veröffentlichst, hat das Manifest alles, was du für die Zuordnung brauchst.

## wiki-comments
name: Kommentare
path: ~/enough/wikisink/comments/

### what
Kommentare im Stil von Google Docs auf Wikipedia-Artikeln — Text markieren und 💬 drücken, oder das 💬 in der Werkzeugleiste nutzen, um einen Kommentar an einem Absatz anzuheften. Threads unterstützen Antworten und Auflösen/Wiedereröffnen. Kommentare hängen am <em>Artikel</em>, nicht an einer gespeicherten Datei, sie folgen dem Artikel also, ob er gespeichert, nur durchgeblättert, aktualisiert oder sogar aus der echten Wikipedia gelöscht wird.

### how
Text im wikisink-Reader auswählen → 💬 kommentieren. die Verankerung degradiert sanft, wenn sich Artikel ändern: zuerst exakte Textübereinstimmung; wurde der zitierte Text wegbearbeitet, heftet sich der Kommentar neu an seinen Absatz („neu angeheftet“); ist auch der Absatz weg, überlebt er als „verwaist“ im Panel. nichts wird je automatisch gelöscht. das Kommentieren eines Artikels nimmt ihn in die beobachtete Menge für wikisink-Updates auf.

### ideas
- kommentiere Statistiken oder Behauptungen, die sich wahrscheinlich ändern — nach einem wikisink-Lauf sind neu angeheftete Kommentare ein Signal, dass genau diese Stelle bearbeitet wurde.
- frag deinen Chef-Readvisor über 🤖 im Auswahl-Popup nach einer markierten Passage — die Passage wird automatisch in den Chat zitiert.

## paradigm-active
name: Paradigma
path: rness/active-paradigm

### what
das Denkgerüst, in dem deine Readvisors gerade arbeiten. immer genau ein Paradigma ist aktiv; auf ein anderes klicken, um zu wechseln. das aktive Paradigma wird bei jedem Zug vollständig in den System-Prompt geladen, und dein Chef-Readvisor sieht auch einen kurzen Katalog der anderen verfügbaren Paradigmen, damit er einen Wechsel vorschlagen (oder selbst einleiten) kann, wenn die Arbeit davon profitieren würde.

### how
auf ● neben einem Paradigma klicken, um es für dieses Projekt zu aktivieren. die Wahl wird in <code>rness/active-paradigm</code> festgehalten. ein von deinem Chef-Readvisor eingeleiteter Wechsel geschieht ebenfalls, indem er diese Datei schreibt, und wirkt ab dem nächsten Zug. neue Paradigmen hinzufügen, indem du eine Markdown-Datei in <code>~/enough/defaults/paradigms/</code> ablegst (oder in das <code>rness/paradigms/</code> deines Projekts für projektlokale). ein YAML-Frontmatter-Block oben — <code>name:</code> und <code>description:</code> — sagt deinen Readvisors, wofür das Paradigma da ist.

### ideas
- Paradigmen, die in diesem Projekt verfügbar sind: {{paradigms-list}}
- schreib ein Paradigma für eine bestimmte Arbeitsweise (Recherche vs. Schreiben, Erkundung vs. Umsetzung) und wechsle im Lauf des Tages zwischen ihnen.
- eine Paradigmen-Beschreibung ist im Kern „wann sollte ich das benutzen“ — schreib sie für deinen Chef-Readvisor, denn das ist das Signal, das er liest, um einen Wechsel zu empfehlen.

## requests
name: Anfragen/
path: rness/requests/

### what
dauerhafte Behälter für Aufgaben und Teilaufgaben. jede Anfrage ist eine Markdown-Datei, die das Ziel deiner Anfrage, die bisherige Argumentation deines Chef-Readvisors und einen Continuation-Block festhält, damit die Arbeit über Kontext-Resets hinweg fortgesetzt werden kann — das ist die Einheit für lang laufende Arbeit in enough. sie helfen auch dabei, weiterzuarbeiten, wenn du an ein Kontextfenster stößt. erledigte Anfragen liegen neben den aktiven in <code>rness/requests/done/</code>.

### how
neue Anfragen erscheinen automatisch in <code>rness/requests/</code>, während du und dein Chef-Readvisor arbeitet — auf eine Datei im Projektbaum klicken, um sie im Dateipanel anzuzeigen. von dort kannst du sie <em>als erledigt markieren</em> (die Datei wandert nach <code>rness/requests/done/</code>) oder <em>anpassen</em>. um eine Anfrage von Hand zu starten, eine Markdown-Datei mit kurzem Ziel oben in <code>rness/requests/</code> ablegen.

### ideas
- behandle eine Anfrage wie ein lang laufendes Projekt — zerlege eine vage Absicht in eine und lass deinen Chef-Readvisor sie über mehrere Sitzungen hinweg ausarbeiten.
- durchstöbere <code>rness/requests/done/</code> als Journal dessen, was du wirklich abgeschlossen hast — es ist das ehrlichste Protokoll dessen, was du und dein Chef-Readvisor wirklich geliefert habt.
- bei Auto-Reset-Checkpoints des Kontextfensters schreibt dein Chef-Readvisor einen Continuation-Block in die aktive Anfrage — lies ihn vor dem Fortsetzen, wenn du umlenken willst.

## skills
name: Skills
path: rness/skills/

### what
Schalter pro Projekt für Skills — Einheiten fokussierter Fähigkeiten, verlinkt aus <code>~/enough/defaults/skills/</code>. aktive Skills fügen Vokabular, Rezepte oder Verhaltensweisen hinzu, auf die deine Readvisors im Gespräch zurückgreifen. Skills, die enough mitliefert, sind <em>vertrauenswürdig</em> und schalten sofort um; alles andere unter <code>rness/skills/</code> — heruntergeladen, geschenkt oder von deinem eigenen Chef-Readvisor für dich geschrieben — ist <em>nicht vertrauenswürdig</em>, bis es gelesen wurde, und beim ersten Einschalten prüft enough es in einem Audit, bevor auch nur ein Wort davon deine Readvisors erreicht.

### how
auf ● / ○ klicken, um einen Skill für dieses Projekt ein- oder auszuschalten. du kannst projektlokale Skills zu <code>rness/skills/</code> hinzufügen — der Status wird pro Projekt gespeichert. um neue Skills global zu installieren, einen Ordner in <code>~/enough/defaults/skills/</code> ablegen; er erscheint dann in jedem Projekt (standardmäßig aus). bearbeite einen globalen Skill an der Quelle, und die Änderung verbreitet sich überall dort, wo er verlinkt ist. ein nicht vertrauenswürdiger Skill zeigt neben seinem Namen eine kleine Markierung, die von <em>ungeprüft</em> → <em>Audit läuft…</em> → <em>geprüft</em> wandert; findet das Audit etwas, liest die Zeile <em>markiert</em>, der Skill bleibt aus, und du bekommst zwei Buttons — <em>Bericht lesen</em> (öffnet den vollständigen Bericht) und <em>trotzdem aktivieren</em> (bestätigt und vermerkt die Entscheidung als deine). Berichte landen in <code>rness/io/output/analyzer/audits/&lt;skill&gt;/</code>. bearbeitest du die Dateien eines Skills danach, wird er beim nächsten Einschalten neu gelesen.

### ideas
- Skills, die in diesem Projekt verfügbar sind: {{skills-list}}
- baue globale oder projektlokale Skills, um deinen Hausstil oder Fachkonventionen einzufangen.
- schalte alles aus für „reines Gespräch“ — manchmal hat das Modell ohne jedes Gerüst mehr Luft für emergente Geistesblitze.
- bitte deinen Chef-Readvisor, einen Skill zu <em>prüfen</em>, bevor du ihn aktivierst (der vierte Modus von analyzer) — derselbe Bericht, den das Erstnutzungs-Audit schreibt, nur nach deinem Zeitplan.

## roles
name: Readvisors
path: rness/readvisors/

### what
die anderen Leser im Raum. ein Readvisor ist ein Ordner mit AGENT.md (wer er ist) und MOTIVATION.md (was ihm wichtig ist) — eine Form, feste Überschriften, damit jeder Readvisor trotz eigener Stimme und eigener Marotten gleich funktioniert. hier eingeschaltet, gehen sie im gewöhnlichen Gespräch in der einen Stimme deines Chef-Readvisors auf; in einer Composure vom Typ Rat spricht jeder einzeln, unter seinem eigenen Namen.

### how
klicke ● / ○, um einen für dieses Projekt ein- oder auszuschalten. der Tooltip jeder Zeile nennt ihre Herkunft: <em>mitgelieferte</em> kommen mit enough (<code>defaults/readvisors/</code>) und haben keinen Entfernen-Knopf; <em>globale</em> gehören dir, liegen in <code>~/enough/readvisors/</code> und tauchen in jedem Projekt dieser Maschine auf; <em>Projekt</em>-Readvisors gehören nur zu diesem Ordner (<code>rness/readvisors/&lt;name&gt;/</code>). das × auf einer globalen oder Projekt-Zeile löscht sie, nach einer Rückfrage. der <em>readvisory</em>-Skill befragt dich und schreibt einen neuen.

### ideas
- Readvisors in diesem Projekt: {{roles-list}}
- bau dir eine „Quietscheente“, die sokratische Fragen stellt, statt zu antworten.
- nutze die Dateien deiner Wissensbasis mit dem Paradigma <em>workflow-design</em>, um einen Fachexperten zu bauen (Recht, Design, Text).
- schalte zwei ein, die sich uneinig sind, halte dann einen Rat und lass sie es auf der Leinwand ausdiskutieren.

## rness
name: rness/
path: rness/

### what
das externalisierte System des Projekts. in rness/ liegen Konfiguration, Anweisungen, Wissensdateien und Verlaufsprotokolle jedes Projekts — alles, was deine Readvisors für dieses Projekt nutzen. es sitzt oben im Projekt, sodass du es direkt mit jedem Dateimanager oder Editor bearbeiten kannst; die enough-Oberfläche zeigt seinen Inhalt auch in der Seitenleiste.

### how
manche Inhalte sind Symlinks nach <code>~/enough/defaults/</code> und aktualisieren sich zentral. um für ein Projekt abzuweichen, eine Datei öffnen und auf <em>anpassen</em> klicken — sie wird zu einer projektlokalen Kopie. neue Dateien frei über Gespräche oder den Dateimanager deines Systems hinzufügen; deine Readvisors sehen lokal hinzugefügte Dateien beim nächsten Zug.

### ideas
- lerne die Bausteine kennen, die deinen enough-Workflow antreiben, und bearbeite sie, wo immer du willst.
- behandle es als lebendige Dokumentation — was müsste ein neues Teammitglied oder ein neuer Readvisor wissen?
- entrümple veraltetes Wissen regelmäßig, damit deine Readvisors keine überholten Entscheidungen zitieren.

## agent-md
name: AGENT.md
path: rness/AGENT.md

### what
wer dein Chef-Readvisor ist und wie er hier arbeitet: seine Arbeitsanweisungen für dieses Projekt, bei jedem Zug zusammen mit MOTIVATION.md verwendet. alles hier prägt, wie er spricht, was er tut und was er vermeidet.

### how
auf die Datei klicken, um sie anzusehen; <em>anpassen</em> drücken, um eine projektlokale Kopie abzuzweigen und zu bearbeiten. oder <code>rness/AGENT.md</code> in einem beliebigen Editor öffnen — gespeicherte Änderungen wirken ab der nächsten Nachricht.

### ideas
- füge projektspezifische Leitplanken hinzu (z. B. „vor dem Abschluss einer Bearbeitung immer Rechtschreibung und Fakten doppelt prüfen“).
- liste die Namenskonventionen deines Projekts auf, damit dein Chef-Readvisor nicht raten (oder halluzinnovieren) muss.
- kodiere den Zusammenarbeitsstil, den du willst — knapp, forschend, zurückhaltend, direkt.

## motivation-md
name: MOTIVATION.md
path: rness/MOTIVATION.md

### what
das „Warum“ deines Chef-Readvisors für dieses Projekt — Werte, Prioritäten und Ziele jenseits der reinen Aufgabenliste. wird bei jedem Zug zusammen mit AGENT.md verwendet.

### how
genau wie bei AGENT.md — anklicken zur Vorschau, anpassen für eine projektlokale Kopie, oder die Datei direkt bearbeiten.

### ideas
- benenne die Abwägungen, die dir wichtig sind: Korrektheit vor Tempo, Kürze vor Gründlichkeit, und so weiter.
- beschreib in deinen eigenen Worten, welches Nutzererlebnis das Projekt anstrebt.
- beschreib, wie sich „fertig“ anfühlt — dein Chef-Readvisor kalibriert sein Fortschrittsgefühl daran.

## paradigms
name: Paradigmen/
path: rness/paradigms/

### what
die vollständige Menge der in diesem Projekt verfügbaren Denkgerüste. jedes Paradigma ist eine Markdown-Datei mit einem YAML-Frontmatter-Block (<code>name</code> + <code>description</code>) und einem Textkörper, der beschreibt, wie an die Arbeit heranzugehen ist — Heuristiken, Entscheidungskriterien, wann man fragt statt handelt. immer genau eines ist aktiv (zum Wechseln siehe den Abschnitt <strong>Paradigma</strong> oben in der Seitenleiste).

### how
verlinkt aus <code>~/enough/defaults/paradigms/</code>. global bearbeiten, um das Verhalten in jedem Projekt zu ändern; auf einer Datei auf <em>anpassen</em> klicken, um sie nur für dieses Projekt abzuzweigen. neue Paradigmen lassen sich einfach hinzufügen, indem man eine Markdown-Datei in den defaults-Ordner legt — gib ihr ein Frontmatter <code>name:</code> und <code>description:</code>, damit dein Chef-Readvisor weiß, wann er sie empfehlen soll.

### ideas
- Paradigmen, die in diesem Projekt verfügbar sind: {{paradigms-list}}
- schreib ein Paradigma für eine bestimmte Arbeitsweise (Recherche vs. Schreiben, Erkundung vs. Umsetzung) und wechsle im Lauf des Tages zwischen ihnen.
- eine Paradigmen-Beschreibung ist im Kern „wann sollte ich das benutzen“ — schreib sie für deinen Chef-Readvisor, denn das ist das Signal, das er liest, um einen Wechsel zu empfehlen.

## policies
name: Richtlinien/
path: rness/policies/

### what
feste Regeln, an die sich deine Readvisors halten müssen — welche Tools sie nutzen, welche Dateien sie lesen oder schreiben dürfen, wie sie Anfragen formatieren, wie sie mit Druck auf das Kontextfenster umgehen, und welche Pfade auf der Positivliste stehen.

### how
verlinkt aus <code>~/enough/defaults/policies/</code>. global bearbeiten, um die Regeln für jedes Projekt zu ändern, oder pro Projekt anpassen. vor allem die Positivlisten werden am häufigsten angepasst, da sowohl lokale Pfade als auch Web-URLs ausdrücklich gelistet sein müssen.

### ideas
- zieh die Lese-/Schreib-Positivliste enger, wenn du mit Geheimnissen oder sensiblem Code arbeitest.
- füge eine Richtlinie dafür hinzu, wie mit lang laufenden Skripten oder Hintergrundprozessen umzugehen ist.
- definiere dein eigenes Checkpoint-Format, falls der Standard-Continuation-Block nicht passt.

## knowledge
name: Wissen/
path: rness/knowledge/

### what
projektspezifisches Wissen, das nicht nach <code>rness/io/</code> oder <code>~/enough/infoworld/</code> gehört: enthält immer <code>project-profile.md</code> (lebendige Notizen, die dein Chef-Readvisor zu diesem Projekt führt — deine Vorlieben und dein hier beobachteter Arbeitsstil, wiederkehrende Personen/Dateien, übernommene Konventionen) und <code>session-logs/</code> (Prompt und Antwort jedes Zugs, als Markdown gespeichert).

### how
<code>project-profile.md</code> wird bei jedem Zug in den System-Prompt eingespeist — sowohl du als auch dein Chef-Readvisor könnt sie bearbeiten. Sitzungsprotokolle werden nur angehängt, nie überschrieben. füge neue Unterordner für jede projektlokale Erinnerung hinzu, die deine Readvisors zurate ziehen sollen.

### ideas
- führe einen Glossar-Unterordner für projektspezifischen Fachjargon.
- lass deinen Chef-Readvisor eine „Lessons Learned“-Datei schreiben, während ihr gemeinsam iteriert.
- archiviere alte Sitzungsprotokolle regelmäßig, damit die Suchen deiner Readvisors schnell bleiben.

## io
name: io/
path: rness/io/

### what
ein projektweiter Bereich für Dateien, aus denen deine Readvisors lesen (<code>input/</code>) oder in die sie schreiben (<code>output/</code>). nützlich, wenn eine Datei bearbeitet werden soll, ohne das Projekt-Wurzelverzeichnis zu verunreinigen.

### how
Dateien in <code>rness/io/input/</code> ablegen, und deine Readvisors sehen sie. alles, was sie erzeugen, landet in <code>rness/io/output/</code> — sichten, verschieben, was bleiben soll, den Rest löschen. auch Dokumente zählen: eine Word-Datei oder ein PDF, das hier abgelegt wird, öffnet als Markdown-Zwilling und liest sich wie jede andere Datei, für dich wie für sie.

### ideas
- lege ein CSV oder ein Transkript in <code>input/</code> ab und bitte deinen Chef-Readvisor um eine Zusammenfassung.
- lege das PDF, das dir jemand gemailt hat, in <code>input/</code>, klick es an und lies es als Markdown — das Original bleibt genau so, wie es ankam.
- sammle mehrere Entwurfs-Outputs in <code>output/</code> und wähl den besten aus (oder lass das Modell sie gegeneinander bewerten).
- leere beide regelmäßig — deine Readvisors brauchen die Fingerübungen von gestern nicht in ihrem Kontext.

## infoworld
name: cacheawl
path: ~/enough/cacheawl/

### what
der rechnerweite Dateispeicher, geteilt über jedes enough-Projekt. (das ersetzt die alte <code>infoworld/</code>-Bibliothek — beim ersten Start dieser Version wurden deine Ordner <code>personal/</code>, <code>public/</code> und <code>wiki/</code> hierher verschoben, jeder wurde eine Cachebox.) eine <em>Cachebox</em> ist ein Ordner oberster Ebene im Speicher: entweder Klartext, den du für immer behalten willst, oder eine „Cache-Kopie“, importiert aus einem lokalen Pfad, einer Website oder einer Reihe von Wikipedia-Artikeln. der Speicher ist im Dateibaum jedes Projekts verborgen und wird über den cacheawl-Modus + die Cachebox-Tools deiner Readvisors verwaltet.

### how
den cacheawl-Modus öffnen (der cacheawl-Button in der oberen Leiste) für eine zweigeteilte Ansicht: dein Projekt auf der einen Seite, die Cacheboxen auf der anderen. eine Datei rüberziehen, um sie zu kopieren, shift-ziehen, um sie zu verschieben; die Import-Leiste formuliert für deinen Chef-Readvisor eine Anfrage, um einen Pfad/eine Site/ein Wiki-Thema hereinzuholen. oder frag einfach im Panel — deine Readvisors können Cacheboxen auflisten, anlegen und befüllen (gesteuert durch den Broker-Schalter „cacheawl tools“). jede Box trägt ein automatisch erzeugtes <code>_cachebox.merirmaid</code>-Diagramm ihres Inhalts (nur lesbar — es erzeugt sich aus den Dateien neu) und verborgene Metadaten; die bearbeitest du nie direkt.

### ideas
- importiere eine Dokuseite in geringer Tiefe, damit sich deine Readvisors vollständig offline darauf stützen können.
- führe eine <code>personal</code>-Cachebox mit Referenzmaterial, das aus jedem Projekt abfragbar ist.
- speichere Wikipedia-Artikel, auf die du dich verlässt, in die globale <code>wiki</code>-Cachebox — überall geteilt, an kein einzelnes Projekt gebunden.

## mode-system
name: Lese-/Bearbeitungsmodus
path: the file viewer

### what
ein Klick auf eine Datei öffnet sie im einheitlichen <strong>Lese-/Bearbeitungsmodus</strong> mit zwei Seiten — einer Leseseite (Auge) und einer Bearbeitungsseite (Stift). er lebt entweder als kleines Seitenpanel neben dem Chat oder ausgeklappt im Vollbild; zum Wechseln den Mini↔Voll-Umschalter nutzen. Bearbeitungen sind schmutz-gesichert, sodass du ungespeicherte Änderungen nicht aus Versehen durch Wegnavigieren verlierst. Dateien, die enough nicht nativ anzeigt, öffnen trotzdem: eine Word-Datei, ein PDF, eine Präsentation oder Arbeitsmappe öffnet als ihr Markdown-<em>Zwilling</em> (siehe die Hilfeblase <em>konvertiertes Dokument</em> bei jeder solchen Zeile), und ein Bild öffnet in einem schlichten Betrachter mit Einpassen- und 1:1-Größen.

### how
einfacher Klick auf eine Datei im Baum öffnet sie im Mini-Panel; ausklappen aufs Vollbild, wenn du Platz brauchst. zwischen der Lese- (Auge) und der Bearbeitungsseite (Stift) mit den eigenen Seiten-Umschalt-Buttons im Lese-/Bearbeitungs-Rahmen wechseln. jeder offene Modus zeigt oben rechts einen quadratischen Indikator (neuester links) mit einem kleinen rot-x-Band zum Schließen — Modi <em>stapeln</em> sich, das Schließen eines Modus legt also den darunterliegenden genau so frei, wie du ihn verlassen hast. auf einen vergrabenen Indikator klicken, um diesen Modus nach vorn zu holen; <code>esc</code> schließt den obersten Modus. dasselbe Muster aus Indikator + Band gilt für jeden Vollbild-Modus (wikisink, girraph, merirmaid, cacheawl und den nur lesbaren Referenzmodus <strong>Hilfe-Center</strong>, gestartet über den kleinen <strong>Hilfe</strong>-Button oben rechts im UI-Fenster).

### ideas
- halte eine Datei im Mini-Panel offen, während du chattest — Referenz und Gespräch Seite an Seite.
- geh für lange Dokumente oder beim Bearbeiten ins Vollbild, zurück zu Mini, wenn du nur kurz reinschauen willst.

## converted-file
name: konvertiertes Dokument
path: the original, plus its markdown twin

### what
ein Dokument, das enough nicht nativ anzeigt — eine Word-Datei, ein PDF, eine Präsentation, eine Arbeitsmappe — dargestellt als <em>eine</em> Zeile, die als Markdown öffnet. anklicken, und du bekommst seinen <strong>Zwilling</strong>: eine Markdown-Kopie neben dem Original (<code>memo.docx</code> → <code>memo.docx.md</code>), die sich wie jede andere Markdown-Datei liest, markieren und bearbeiten lässt. der Zwilling, alle aus dem Dokument gelösten Bilder (<code>memo.docx.assets/</code>) und ein kleines verborgenes Manifest sind in diese eine Zeile eingefaltet, sodass der Baum so aufgeräumt bleibt wie dein Ordner im Finder aussieht. das Abzeichen am rechten Rand der Zeile sagt, wie der Stand ist: still bedeutet, der Zwilling stimmt mit dem Original überein; ein leuchtendes Abzeichen mit Punkt bedeutet entweder, du hast den Zwilling bearbeitet (und kannst diese Änderungen zurückexportieren), oder das Original hat sich außerhalb von enough geändert — rot bedeutet beides, der einzige Fall, bei dem enough nachfragt. ein hohles Abzeichen bedeutet „noch nicht konvertiert“, oder bei PDFs, dass das PDF-Extra nicht installiert ist.

### how
einmal klicken. beim ersten Öffnen jedes Dokument-<em>Typs</em> erklärt ein kurzes Modal, was gleich passiert; danach öffnet es einfach. den Zwilling wie jede Datei bearbeiten, dann <strong>Export</strong> im Rahmen des Dokuments nutzen: die Vorgabe schreibt eine datierte Kopie neben das Original (<code>memo-2026-08-19-1042.docx</code>), und „das Original überschreiben“ ist ein Radio-Button darunter, mit einem Rückgängig-Angebot danach. dasselbe Modal trägt <em>das Original synchron halten</em> — jedes Speichern des Zwillings schreibt das Original für dich neu — nur für die Formate angeboten, die sich zurückschreiben lassen. hat sich das Original unter dir geändert (in Word bearbeitet, von irgendwoher neu exportiert), bemerkt enough das beim Öffnen oder Speichern und fragt, welche Seite gewinnt: deinen Zwilling behalten, über das Original exportieren, oder vom Original neu konvertieren — und der ersetzte Zwilling wird so oder so für Rückgängig aufbewahrt. <strong>Originale werden nie neu geschrieben, außer du verlangst es</strong>, und jedes Überschreiben hinterlässt ein Rückgängig.

### ideas
- was enough auf diese Weise öffnen kann, und was es zurückschreiben kann: {{convert-formats}}
- bitte deinen Chef-Readvisor, ein Dokument beim Namen zu lesen — <code>read_file</code> auf <code>report.pdf</code> gibt ihm den Zwilling, wobei nötigenfalls erst einer erzeugt wird.
- das Lesen von PDFs, PowerPoint-Präsentationen und Excel-Arbeitsmappen braucht das <strong>PDF-Extra</strong> (⚙ UI-Fenster → Extras): rund 250 MB Download, rund 1 GB installiert, dazu etwa 0,7 GB Dokumentmodelle in <code>~/enough/weights/docling/</code>. <em>Schreiben</em> von PDFs aus Markdown funktioniert bei jeder Installation, ganz ohne Extra.

## merirmaid
name: merirmaid
path: *.merirmaid

### what
enoughs Spielart eines <a href="https://mermaid.js.org/" target="_blank" rel="noopener">Mermaid</a>-Diagramms: Klartext-Diagrammquelle mit kleinem Header, live im Browser zu einem Bild gerendert (Flussdiagramme, Sequenzdiagramme, Zustandsautomaten, ER-Diagramme — alles, was Mermaid unterstützt). zwei Arten: ein <em>wip</em>-Diagramm, das du anpassen kannst, und ein <em>mirror</em>, das eine Struktur widerspiegelt (etwa den Inhalt einer Cachebox) und nur lesbar ist.

### how
bitte deinen Chef-Readvisor, ein Diagramm zu zeichnen oder zu überarbeiten — er schreibt die <code>.merirmaid</code>-Quelle; das Öffnen der Datei rendert sie. in einem wip-Diagramm kannst du auf den Text eines Knotens klicken, um die Bezeichnung direkt zu bearbeiten (mit laufender Zeichenzählung); strukturelle Änderungen laufen über deinen Chef-Readvisor via Chat-Pille. Knoten können auf andere Diagramme oder Dokumente verlinken — anklicken zum Folgen, mit Breadcrumbs zum Zurückgehen. ein fehlerhaftes Diagramm zeigt den Fehler plus die Rohquelle, nie eine leere Fläche. Mirror-Diagramme zeigen ein „mirror“-Abzeichen statt Bearbeitungsgriffen.

### ideas
- lass deinen Chef-Readvisor einen Prozess oder eine Architektur diagrammieren, über die du gerade nachdenkst, und verfeinere es im Gespräch.
- verknüpfe mehrere Diagramme über klickbare Knoten zu einer navigierbaren Karte.
- kombiniere es mit girraphs: ein girraph für das Argument, ein merirmaid für den Ablauf.

## cacheawl
name: cacheawl
path: ~/enough/cacheawl/

### what
der rechnerweite Speicher der <em>Cacheboxen</em> — Ordner oberster Ebene mit Text, den du für immer behalten willst, oder Cache-Kopien, importiert aus einem lokalen Pfad, einer Website oder Wikipedia-Artikeln. geteilt über jedes Projekt und im Dateibaum der Projekte verborgen. hier lebt jetzt die alte <code>infoworld</code>-Bibliothek.

### how
den cacheawl-Modus über die obere Leiste öffnen für die zweigeteilte Ansicht (Projekt ↔ Cacheboxen): ziehen, um eine Datei zwischen ihnen zu kopieren, shift-ziehen zum Verschieben, und die Import-Leiste nutzen, um deinen Chef-Readvisor zu bitten, eine Quelle in eine Box zu holen. oder sag es einfach im Panel — deine Readvisors können Boxen auflisten, anlegen und befüllen, wenn der Broker-Schalter „cacheawl tools“ an ist (URL-Importe respektieren auch deine fetch_url-Schalter). jede Box zeigt ein automatisch erzeugtes Diagramm ihres Inhalts (<code>_cachebox.merirmaid</code>, nur lesbar) und hält verborgene Metadaten, die du nicht anfasst.

### ideas
- importiere eine Doku-Site oder einen Ordner voller Notizen, damit deine Readvisors offline damit arbeiten können.
- verschiebe ein fertiges Artefakt in eine Cachebox, damit es aus dem laufenden Projekt raus ist, aber überall erreichbar bleibt.
- doppelklicke das Diagramm einer Box, um ihre Form auf einen Blick im merirmaid-Betrachter zu sehen.

## footnotes
name: Fußnoten
path: (inside your markdown files)

### what
echte Fußnoten für Texte in Arbeit. <code>[^1]</code> im Fließtext schreiben und <code>[^1]: die Notiz selbst</code> unten in der Datei platzieren — in der Leseansicht erscheint jede Notiz als kleine Karte am Rand, an ihrer Markierung ausgerichtet. Karten sind direkt vor Ort bearbeitbar: umdrehen zum Bearbeiten, speichern oder abbrechen, fertig. die Datei auf der Festplatte bleibt schlichtes, portables Markdown.

### how
im Editor <code>[^]</code> tippen, und es wird automatisch zur nächsten Fußnotenzahl, oder den Fußnote-einfügen-Button der Werkzeugleiste an der Schreibmarke nutzen. eine neue Fußnote zwischen zwei bestehende setzen, und alles danach nummeriert sich selbst um, Definitionen inklusive. benannte Fußnoten wie <code>[^aside]</code> bleiben genau so, wie du sie geschrieben hast. eine Markierung ohne Definition zeigt eine leere Karte — hineinschreiben, und Speichern trägt die Definition für dich ein.

### ideas
- entwirf mit schnellen <code>[^]</code>-Markierungen und fülle die Texte später über die Randkarten.
- die Fußnotennummerierung bleibt sauber, egal in welcher Reihenfolge du schreibst — paginieren verlässt sich darauf, ein „textlich fertiger“ Text braucht also keinen Aufräumdurchgang.

## paginate
name: paginieren
path: (next to the markdown it came from)

### what
verwandelt einen fertigen Text in ein sauber gesetztes PDF — echte Seiten, Kapitel, die frisch beginnen, Fußnoten zusammengeführt, wo immer du sie willst (auf der Seite, am Ende jedes Kapitels, oder in einem abschließenden Fußnotenteil gesammelt). das Markdown bleibt das bearbeitbare Original; das PDF ist eine datierte Momentaufnahme daneben, z. B. <code>book-2026-08-23.pdf</code>.

### how
eine Markdown-Datei in der Leseansicht öffnen und den Paginieren-Button in der Werkzeugleiste drücken. eine Seitengröße wählen (Letter, A4, Taschenbuch … oder eigene), Hoch- oder Querformat, eine der mitgelieferten Schriften, einen Rand, und optional Seitenzahlen und lebende Kolumnentitel (dein Text oder der Kapitelname). 2-up setzt zwei Seiten pro Blatt; Booklet verschachtelt sie so, dass ein doppelseitiger Druck sich zu einem heftbaren Buch falzt. „PDF in enough holen“ fügt eine seitenweise Ansicht mit Pfeiltasten-Blättern und Vollbild hinzu. jedes exportierte PDF trägt heimlich sein eigenes Quell-Markdown mit sich, sodass der Reimport in ein Projekt den Text — Fußnoten inklusive — exakt wiederherstellt.

### ideas
- prüf einen Entwurf im Taschenbuchformat mit Anmerkungen am Kapitelende, bevor du dich für die endgültige Form entscheidest.
- druck ein Booklet eines kurzen Stücks: Booklet-Layout, halbes Letter-Format, das Ergebnis heften.
- schick jemandem das PDF; kommt es je ohne das Original zurück, stellt der Import das Markdown perfekt wieder her.

## composure
name: composure
path: rness/io/composure/

### what
die Leinwand, die immer hinter allem anderen liegt — die Grundschicht des Fensters, kein Modus, den du betrittst und wieder verlässt. eine <strong>Composure</strong> ist eine <code>.comp</code>-Datei: Kästen voller Geschriebenem (<em>Module</em>) und freihändige Tinte auf einer randlosen Fläche, über die du schiebst und zoomst. sie öffnet in jedem Browser als schlichte Seite, ganz ohne installiertes enough, weil die Datei selbst gewöhnliches HTML ist.

### how
die Werkzeugleiste läuft oben entlang: der Titel (umbenennen durch Hineintippen und Wegklicken), der Lese-/Bearbeiten-Schalter, die Werkzeuge, Rückgängig/Wiederherstellen, die Zoom-Gruppe, die Suche, das Kommentarpanel und das Composures-Menü. schieben mit zwei Fingern, mit gedrückter Leertaste oder der mittleren Maustaste; zoomen mit Pinch, ⌘-Scrollen, ⌘+ / ⌘− / ⌘0 oder „einpassen“. es gibt keinen Speichern-Button — alles wird geschrieben, während du arbeitest, und eine Composure, die du öffnest und nie anfasst, legt überhaupt keine Datei an. zoom weit genug heraus, und jedes Modul klappt auf seine <em>Schauseite</em> zusammen: sein Titel, so groß wie er passt, der Rumpf als Blindtext — sechzig Karten lesen sich dann als sechzig Titel.

### ideas
- halt eine Tafel je Projekt als die Karte, auf die du schaust, bevor du zu schreiben anfängst.
- ein <code>.comp</code>-Modul, das auf eine andere <code>.comp</code> zeigt, macht aus einer Tafel einen Einstieg in die Tiefe: ein Klick tauscht die Leinwand unter dir aus.
- markier eine Passage in einem Modul, und sie reitet mit deiner nächsten Nachricht an deinen Readvisor mit, eingerahmt und beschriftet.

## composure-modules
name: Module
path: (inside a .comp file)

### what
die Kästen auf einer Composure. ein <strong>Text</strong>-Modul ist Geschriebenes — Überschriften, Listen, Checklisten, Zitate, Links, Markierungen — mit so vielen Seiten darin, wie du willst. die anderen fünf zeigen auf etwas: auf eine <strong>Datei</strong> in diesem Projekt, einen <strong>wikisink</strong>-Artikel, einen <strong>Weblink</strong>, eine zwischengespeicherte <strong>Webseite</strong> oder ein <strong>Bild</strong>. ein zeigendes Modul zeigt beim Lesen eine lebende Vorschau, und ein Klick öffnet die Sache selbst.

### how
der Modul-hinzufügen-Button öffnet eine kurze Liste der sechs Arten. ist im Bearbeitungsmodus ein Modul ausgewählt, erscheint der Inspektor daneben: Hintergrundfarbe, Textgröße, Seiten, vor/zurück, das eigene Feld der jeweiligen Art (ein Dateiwähler, eine Artikelsuche, eine Adresse) und ein Kommentar-Button. ziehen zum Verschieben, an einem Griff ziehen zum Ändern der Größe, Pfeiltasten zum Anstupsen (mit Umschalt größere Schritte), Entfernen zum Löschen — mit Warnung vorweg, wenn Geschriebenes darin steht, und ⌘Z, um es zurückzuholen. Text, der über seinen Kasten hinauswächst, bietet dir eine neue Seite an, statt still weiterzuwachsen.

### ideas
- gib einem Modul einen Titel, und es behält seinen Namen, wenn du unter die Lesegröße hinauszoomst.
- die Farben <code>Tinte</code> und <code>klar</code> sind für Struktur — eine dunkle Karte für eine Überschriftenreihe, eine klare für eine Beschriftung, die gar keine Karte sein soll.
- lass ein Modul auf eine Datei zeigen, die du immer wieder öffnest; die Tafel wird zum Schreibtisch, auf dem die richtigen Papiere schon liegen.

## composure-tools
name: Werkzeuge
path: (the composure toolbar)

### what
vier Werkzeuge, und es gibt sie nur, solange du bearbeitest: der <strong>Zeiger</strong> (V) wählt aus, verschiebt, ändert Größen und zieht Auswahlrahmen auf; <strong>Text</strong> (T) setzt den Cursor in ein Modul; der <strong>Stift</strong> (P) zeichnet; der <strong>Radierer</strong> (E) wischt weg. Tinte sind freihändige Linienzüge, die auf der Fläche liegen, unter den Modulen — eine Notiz kann also über drei Karten laufen und ein Pfeil zwei verbinden.

### how
mit dem Stift zeichnest du einfach drauflos — die Linie wird geglättet und vereinfacht, sobald du loslässt. hältst du beim Ziehen <strong>Umschalt</strong>, bekommst du ein gerades Stück mit einer Pfeilspitze am Ende. der Radierer ist ein Kreis, der auf dem Bildschirm immer gleich groß bleibt, wie weit du auch herauszoomst; ziehst du ihn durch eine Linie, verschwindet das Stück unter dem Kreis und die beiden Enden bleiben als getrennte Striche zurück — ⌘Z setzt die Linie wieder in einem Stück zusammen. einen Strich hebst du mit dem Zeiger auf, indem du in seine Nähe klickst; der Inspektor bietet dann die fünf Tintenfarben, und Entfernen löscht ihn. Linien werden langsamer dünn, als die Zeichnung schrumpft, damit eine herausgezoomte Skizze immer noch als Skizze lesbar bleibt.

### ideas
- kringel die drei Karten ein, die zusammengehören, bevor du entscheidest, wie die Gruppe heißt.
- zieh mit Umschalt Pfeile zwischen die Module, um zu zeigen, was worauf folgt, und verschieb die Module dann; der Pfeil bleibt, wo du ihn gezogen hast, was meistens die ehrlichere Antwort ist.
- zeichne rot über eine Tafel, die du durchsiehst, und radier die Marken weg, wenn du sie erledigt hast.

## journal
name: Journal
path: rness/io/composure/

### what
ein Composure-Form zum Führen eines datierten Protokolls. ein Modul, ein Eintrag je Seite. öffnest du ein Journal, landest du auf der <em>heutigen</em> Seite, mit dem Cursor schon darin — und diese Seite steht nur im Arbeitsspeicher, bis du etwas schreibst, das Journal zu öffnen und es sich dann anders zu überlegen hinterlässt also nichts.

### how
schreib. der Eintrag speichert sich selbst, während du tippst, und gehst du, ohne ihn abzulegen, öffnet das Journal beim nächsten Mal wieder denselben unfertigen Entwurf. ist der Eintrag fertig, drück <strong>diesen Eintrag ablegen</strong>: die Seite wird mit dem Datum gestempelt und dauerhaft schreibgeschützt — enough weigert sich danach, sie zu ändern, und der Cursor geht nicht mehr hinein. das Ablegen bringt dich weiter auf eine frische Seite fürs nächste Mal. durch abgelegte Einträge zurückzublättern ist gefahrlos: eine Seite umzublättern, in die du nichts geschrieben hast, speichert überhaupt nichts. kommentieren kannst du abgelegten Text weiterhin — genau dafür legt man ihn ab.

### ideas
- leg am Ende einer Arbeitssitzung ab, nicht am Ende eines Tages; das Datum ist eine Tatsache, keine Frist.
- kommentier einen alten abgelegten Eintrag, wenn sich herausstellt, dass er falsch war — das Protokoll bleibt stehen, und der zweite Gedanke steht daneben.
- bitte deinen Readvisor, das Journal zu lesen, wenn du wissen willst, wohin eine lange Arbeit tatsächlich gegangen ist.

## readvisor-panel
name: Readvisor-Panel
path: (the right-hand panel)

### what
das Gespräch, in einer eigenen Spalte neben dem, woran du gerade arbeitest. dein <strong>Chef-Readvisor</strong> steht namentlich oben, daneben alle anderen Readvisors, die du eingeschaltet hast — im gewöhnlichen Gespräch antworten sie als eine Stimme, die aus all diesen Blickwinkeln schöpft.

### how
⌘/ öffnet und schließt es; ⇧⌘/ gibt ihm das ganze Fenster, und ⌘/ holt es zurück. es sitzt neben der Leinwand oder neben jedem offenen Modus, du musst also nie schließen, was du gerade liest, um danach zu fragen. markier Text — in einem Dokument, in einem wikisink-Artikel, in einem Composure-Modul — und über dem Nachrichtenfeld erscheint ein Chip, der genau zeigt, was gleich mitgeht; das × wirft ihn weg. endet ein Zug, während das Panel geschlossen ist, erscheint ein Punkt auf seinem Button in der oberen Leiste.

### ideas
- lass es angedockt, während du schreibst, und frag nebenbei; es ist ein Kollege am Nachbartisch, kein Fenster, das du öffnest.
- häng eine Auswahl an, statt sie zu beschreiben — die genauen Worte gehen hinüber, eingerahmt, mit der Angabe, woher sie stammen.
- gib ihm das ganze Fenster, wenn du eine lange Antwort in Ruhe lesen willst, und dock es danach wieder an, um damit zu arbeiten.

## council
name: Rat
path: (a composure whose form is council)

### what
mehrere Readvisors und du, die reihum über eine Sache nachdenken, schriftlich, auf der Leinwand. ein Rat ist eine gewöhnliche Composure mit dem Auftrag oben und einer Karte je Beitrag darunter, je Sprecher eingefärbt und mit Namen und Zugnummer überschrieben. die Beiträge gehören dem Rat: du kannst sie verschieben, umfärben, übertuschen und kommentieren, aber nicht umschreiben.

### how
füll den Auftrag aus — Eingabe, Parameter, Einschränkungen, gewünschtes Ergebnis —, hak ab, wer im Raum ist, setz die maximale Rundenzahl und drück einberufen. dann treib ihn an: <em>nächster Zug</em> nimmt einen Beitrag, <em>eine Runde laufen lassen</em> geht einmal herum, <em>bis zum Ende laufen lassen</em> läuft bis zur Rundengrenze, <em>anhalten</em> stoppt ihn, <em>abschließen</em> bittet den Chef um die Entscheidung. das Eingabefeld unten gehört dir: was du sagst, nimmt den nächsten Platz, ohne jemandem seinen Zug zu kosten. der Abschluss schreibt die Antwort als hervorgehobene Karte — oder als Markdown-Datei an den Pfad, den du gewählt hast — und exportiert das ganze Protokoll nach <code>rness/knowledge/councils/</code>.

### ideas
- gib einem Readvisor den Gegenentwurf und finde heraus, ob er den Kontakt mit den anderen übersteht.
- setz das Ergebnis auf ein Dokument, wenn die Entscheidung die Leinwand als zitierbare Datei verlassen soll.
- sag selbst etwas, sobald ein Rat anfängt, im Kreis zu gehen; ein Einwurf ist billiger als noch eine Runde.

## chief-readvisor
name: Chef-Readvisor
path: (the name on every reply)

### what
der eine Readvisor, mit dem du immer sprichst. er hat einen Namen — ab Werk Ed —, und dieser Name zeichnet jede Antwort im Gespräch, steht oben im Readvisor-Panel und spricht als Erster in einem Rat. der Name ist global: einer je Rechner, neben deinem Thema und deiner Oberflächensprache aufbewahrt statt in irgendeinem einzelnen Projekt.

### how
drück den Umbenennen-Button neben dem × in dieser Kopfzeile, tipp einen neuen Namen und speichere. 1 bis 24 Zeichen: Buchstaben und Ziffern, dazu Leerzeichen, Bindestrich, Apostroph und Punkt, in welcher Schrift du willst. jede Stelle, die den Namen zeigt, zieht sofort nach, ohne Neuladen. ein Rat, der schon gesprochen hat, behält den Namen, mit dem seine Beiträge gezeichnet sind — Beiträge werden namentlich zugeordnet, und eine Umbenennung mittendrin läse sich wie zwei verschiedene Personen.

### ideas
- nimm etwas, das du auch laut sagen würdest; du wirst es den ganzen Tag lesen.
- benenn um, bevor du einen Rat einberufst, nicht währenddessen.
