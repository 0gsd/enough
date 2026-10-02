Hi, hier ist Graham, der Erfinder von enough. Dieses Dokument – diesen Teil hier ausgenommen – wird vor allem von Agenten geschrieben und gepflegt. Ich werde mit ziemlicher Sicherheit hin und wieder ein paar Grahamismen einstreuen, aber die Idee ist, meinen eigenen Drang, unterhaltsames Zeug zu schreiben, nicht der umfassenden Dokumentation in die Quere kommen zu lassen.

# das enough-Hilfe-Center

> Alles, was du mit enough machen kannst, an einem Ort. Geschrieben für enough **0.4.1**. Neu in dieser Runde: **das Wörterbuch** — FEED, das hauseigene englische Wörterbuch von enough: rund 96.000 Wörter mit ihrem Klang, ihren Familien und ihren Geschichten, auf deinem eigenen Rechner gebaut, einen Rechtsklick von jedem Wort entfernt, das du gerade liest, und mit Platz daneben für Wörter, die du selbst mitbringst (Abschnitt 13); **text-planning** als Heimat-Paradigma, in dem jedes Projekt beginnt, mit dem alten Paradigma `default` darin aufgegangen (Abschnitt 16); eine kurze Einführung in enough, einen Klick entfernt in einem leeren Gespräch (Abschnitt 5); und ein Inhaltsverzeichnis, eine Suche und lebendige Abschnittslinks in diesem Handbuch (Abschnitt 10). Aus der Runde davor: **`/pal`**, wobei dein Chef-Readvisor erst hier, lokal, nachdenkt und dann eine einzige zugespitzte Frage an das von dir eingerichtete Cloud-Modell schickt und dir genau zeigt, was die Maschine verlassen hat (Abschnitt 15.3); und Räte, die als Antwort, als Dokument oder als neue Composure enden, mit einem einzeiligen Auftrag pro Readvisor und einem Weg, einen bereits abgeschlossenen Rat erneut einzuberufen (Abschnitt 18). Aus der Composure-Runde: die Leinwand, die jetzt der Boden jedes Projekts ist, mit dem Gespräch in einem Panel daneben (Abschnitte 4 und 5); **Readvisors**, wie die Rollen jetzt heißen, angeführt von einem Chef-Readvisor namens Ed (Abschnitt 17); **Räte**, in denen mehrere Readvisors reihum über eine Sache nachdenken, schriftlich, während du zusiehst (Abschnitt 18); und zwei Skills, `readvisory` und `scaffold` (Abschnitt 19). Ein Projekt, das vor jener Runde angelegt wurde, bekommt seinen Ordner `rness/roles/` beim nächsten Öffnen in `rness/readvisors/` umbenannt, mit unversehrten Ein/Aus-Einstellungen (Abschnitt 8). Ebenfalls hier, aus den Runden davor: der Startbildschirm (jedes Projekt, das du je begonnen hast, in einer Liste, mit einem Weg hinein und einem Weg zurück hinaus — Abschnitt 2), die Konvertierungsrunde (PDFs, Word-Dokumente, E-Books, Präsentationen und Arbeitsmappen öffnen als bearbeitbare Markdown-Zwillinge, mit Export, Sync und einem Bildbetrachter — Abschnitt 7), die Skills-Runde (analyzers neuer Audit-Modus, der Skill `anything-finder`, und das Erstnutzungs-Audit, das jeden Skill liest, den enough nicht mitgeliefert hat, bevor er hereingelassen wird), der Runde vom August 2026 (sieben lokale Modelle mit machbarkeitsgeprüften Installationen, und **enough.app** — die signierte, notariell beglaubigte Desktop-Anwendung), der Interface-Runde vom Juli 2026 (der Modus-Stapel, Hilfeblasen pro Ordner, girraph→merirmaid-Spiegel), und der 0.3.0-Einstellungsrunde (UI- und Textgröße pro Projekt, und die Oberfläche + Hilfe in sechs Sprachen — Abschnitt 10). Wo dieses Dokument und die App vor dir sich widersprechen, hat die App recht und dieses Dokument einen Fehler — Korrekturen willkommen unter [enough.support](https://enough.support).

enough ist ein persönliches Sprachsystem, das auf deinem eigenen Rechner läuft. Du richtest es auf einen Ordner, sprichst mit ihm, und es hilft dir beim Planen, Schreiben, Überarbeiten, Recherchieren und Übersetzen. Die Modelle sind standardmäßig lokal. Deine Dateien bleiben deine. Und fast alles, was du es tun siehst, ist in schlichten Markdown-Dateien festgelegt, die du öffnen, lesen und ändern kannst.

Behalte beim Lesen einen Gedanken im Hinterkopf: **die eingebauten Funktionen in diesem Handbuch sind nur ein Bruchteil dessen, was enough kann.** Die Paradigmen, Readvisors und Skills im Lieferumfang sind ein Starterkit — funktionierende Beispiele für drei Anpassungsmechanismen, nicht deren Grenzen. Das Endziel ist, dass du deine eigenen schreibst, oder deinen Chef-Readvisor bittest, sie mit dir zu schreiben: ein Paradigma für die Art, wie du Essays planst, einen Readvisor, der wie dein härtester Leser argumentiert, einen Skill, der deinen Hausstil kodiert. Abschnitt 3 erklärt, wie. Er ist der wichtigste Abschnitt in diesem Dokument, und das Handbuch wird dich immer wieder dorthin zurückschicken.

---

## 1. Installation, Shortcuts und diese Dokumentation

### 1.1 Was du brauchst

- Ein Mac mit Apple Silicon. (enough wird auf macOS gebaut und getestet. Linux-Unterstützung ist geplant; Windows ist machbar.)
- Plattenplatz für mindestens ein Modell — das kleinste ist etwa 5 GB.
- Keine Konten, keine API-Schlüssel, keine Abos. Sofern du dich nicht später für den Cloud-Modell-Slot entscheidest (Abschnitt 15.2), läuft alles lokal.

### 1.2 Installieren

Zwei Türen, ein Haus.

**Die App — der kurze Weg.** Lade das `enough`-DMG von der Releases-Seite herunter, öffne es, zieh **enough** in den Programme-Ordner und starte es. macOS wird anmerken, dass es sich um eine App aus dem Internet handelt — sie ist signiert und notariell beglaubigt, also ist das der freundliche blaue Dialog mit einem **Öffnen**-Button, einmal, keine Warnung, gegen die du ankämpfen musst. Ein Erststart-Assistent übernimmt von dort: er baut seine eigene Python-Umgebung, zeigt dir die Modellliste mit einem ehrlichen Urteil darüber, was auf *diesen* Rechner passt (Abschnitt 15.1), listet auf, welche optionalen Extras du schon hast, und übergibt dich an den Startbildschirm, um den Ordner zu wählen, in dem du arbeiten willst (Abschnitt 2). Der größte Teil der Wartezeit ist Modell-Download. Kein Terminal, kein Homebrew, kein git.

Die App bringt ihre eigene Inferenz-Engine und Python mit. Die optionalen Extras — Spracheingabe, Webseiten-Abruf, Grammatikprüfung, Übersetzung — sind weiterhin eigenständige Programme; die Extras-Seite des Assistenten nennt jedes einzelne, was ohne es abgeschaltet bleibt, und wie man es bekommt. Nichts ist erforderlich, und nichts installiert sich hinter deinem Rücken. Ein Extra ist gar kein eigenständiges Programm: **PDF-Lesen** installiert sich aus enough heraus, wann immer du willst (Abschnitt 7.8).

**Das Terminal — der lange Weg, mit mehr Hebeln.** Klone das Repository, dann doppelklicke `install-enough.command` im Klon:

```bash
git clone https://github.com/0gsd/enough.git ~/Downloads/enough-seed
open ~/Downloads/enough-seed
```

Beim ersten Doppelklick sträubt sich macOS Gatekeeper vielleicht wegen eines „nicht identifizierten Entwicklers“ — diese Vorsicht gilt der `.command`-Datei, die nicht so signiert ist wie die App. Rechtsklick auf die Datei und einmal **Öffnen** wählen; macOS merkt sich das Vertrauen von da an.

Der Launcher führt `bootstrap.sh` aus, einen zehnstufigen interaktiven Installer, der vor jedem Schritt fragt und erklärt, was er gleich tut. Ctrl-C ist jederzeit sicher. Ein erneuter Lauf ist ebenfalls sicher — er prüft zuerst den Zustand und macht dort weiter, wo du aufgehört hast. Die Schritte, grob:

1. Deine Plattform prüfen.
2. Nach Homebrew schauen und beim Installieren helfen, falls es fehlt.
3. Die Helferprogramme installieren, auf die sich enough stützt: `llama.cpp` (lokale Modell-Inferenz), `whisper-cpp` (Spracheingabe), `tor` (anonymisierte Web-Abrufe) und `harper` (lokale Grammatikprüfung, vom analyzer-Skill genutzt). Die Dokumentkonverter — pandoc, um abgerufene Webseiten und Word-Dateien in Markdown zu verwandeln, und typst, zum Schreiben von PDFs — stehen nicht mehr auf dieser Liste: sie sind in enoughs eigener Python-Umgebung enthalten, installiert in Schritt 5, auf jeder Plattform. Falls du zufällig ein eigenes pandoc von Homebrew hast, nutzt enough stattdessen dieses.
4. `~/enough/` einrichten, das globale Installationsverzeichnis.
5. die Python-Umgebung vorbereiten (über `uv`).
6. Modellgewichte herunterladen. Jedes unterstützte Modell wird einzeln angeboten, jeweils mit seiner Größe und einer Machbarkeitsprüfung gegen den Arbeitsspeicher und freien Plattenplatz deines Rechners — ✓ heißt komfortabel, ~ heißt knapp, ✗ heißt woanders suchen. Sag ja zu so vielen oder so wenigen, wie du willst; Abschnitt 15.1 beschreibt sie alle, und was du auslässt, ist später eine Ein-Klick-Installation.
7. das Spracheingabe-Modell (whisper) platzieren.
8. das Offline-Übersetzungsmodell platzieren, genutzt vom Skill `translator`.
9. den Befehl `enough` in deinen PATH legen.
10. fertig, mit einer ausgedruckten Liste nächster Schritte.

Später aktualisieren: `update-enough.command` aus `~/enough/` ausführen, oder `/update-enough` in das Chat-Feld tippen. Wenn neue Defaults erscheinen, erwähnt enough das in der Oberfläche und verweist dich auf diesen Befehl, sodass du nicht selbst nachsehen musst. `update-weights.command` aktualisiert Modellgewichte separat.

### 1.3 Starten

**Aus der App:** doppelklicken, und du landest auf dem **Startbildschirm** — jeder Ordner, den du je zu einem enough-Projekt gemacht hast, in einer Liste, mit einer Möglichkeit, einen weiteren hinzuzufügen. Einen auswählen, und er öffnet. Das ist Abschnitt 2, und es lohnt sich, ihn vor diesem hier zu lesen.

Das **enough**-Menü enthält eine Einstellung, **Reopen Last Project on Launch**, standardmäßig aus: schalte sie ein, und die App überspringt den Start und setzt dich direkt dorthin zurück, wo du warst. Ein Fenster, ein Projekt zur Zeit — und **Datei → Projekt schließen** (⌘W) bringt dich zurück zum Start, wann immer du wechseln willst, ohne zu beenden (Abschnitt 2.5).

Es gibt dort immer noch einen schlichten Ordner-Auswähler, aber du wirst ihm vermutlich nie begegnen: er ist der Rückfallplan für den Fall, dass der Startbildschirm selbst nicht hochkommt — ein halbfertiges Update, eine kaputte Installation —, damit dir auch an einem schlechten Tag ein Weg zu deiner Arbeit bleibt.

**Aus dem Terminal:** enough läuft pro Projektordner. Öffne ein Terminal in einem beliebigen Ordner und führe aus:

```bash
enough
```

dann `http://127.0.0.1:3456` besuchen (enough öffnet es für dich). Anderer Ordner, anderes Projekt, anderes Gedächtnis. Der eine Ordner, aus dem du nicht starten kannst, ist `~/enough/` selbst — die CLI verweigert sich, weil das die Installation ist, kein Projekt.

Den Startbildschirm bekommst du auch von überall:

```bash
enough --home
```

Derselbe Bildschirm, dieselbe Liste, in deinem Browser statt im App-Fenster. Öffne von dort ein Projekt, und das Terminal, in dem du es gestartet hast, wird zum Terminal dieses Projekts.

Wenn du den Befehl lieber nie eintippen willst: zwei Starter liegen in `~/enough/shortcuts/`:

- **`enough-on.command`** — in einen Projektordner kopieren (`cp ~/enough/shortcuts/enough-on.command ~/some-project/`), dann im Finder doppelklicken. Ein Terminal-Fenster öffnet in diesem Ordner mit laufendem enough; ⌘W oder Ctrl-C stoppt es.
- **`setup-quick-action.sh`** — einmal ausführen (`bash ~/enough/shortcuts/setup-quick-action.sh`), und du bekommst eine Finder-Schnellaktion: Rechtsklick auf einen beliebigen Ordner → Schnellaktionen → **In enough starten**. Falls der Menüpunkt nicht erscheint, ihn unter Systemeinstellungen → Tastatur → Tastaturkurzbefehle → Dienste → Dateien und Ordner aktivieren.

### 1.4 Diese Dokumentation, und der Rest davon

Diese Datei ist das ausführliche Handbuch. Außerdem gibt es:

- **Eingebettete Hilfe** — die `(?)`-Blasen überall in der Oberfläche, jede erklärt, woran sie hängt: ein *Was*, ein *Wie* und eine *Ideen*-Liste. Siehe Abschnitt 10.6.
- **Die Spickzettel** — Tastenkürzel und Markdown-Syntax, einen Klick entfernt im UI-Fenster. Siehe Abschnitt 10.5.
- **[enough.support](https://enough.support)** — das Community-Forum: Installationshilfe, Workflow-Schaufenster, und Leute, die dir gern helfen, die Anpassungen zu bauen, zu denen dieses Handbuch dich immer wieder anstupst.

Und das alles — dieses Handbuch, die Blasen, die Oberfläche drumherum — liest sich in sechs Sprachen: Englisch, Französisch, Spanisch, Deutsch, Chinesisch und Japanisch. Abschnitt 10.4 hat das Dropdown und das Kleingedruckte.

---

## 2. Der Startbildschirm

Bevor du in einem Projekt bist, bist du auf **Start**: ein Rahmen, der jeden Ordner auflistet, den du je zu einem enough-Projekt gemacht hast, plus eine Kachel zum Hinzufügen eines weiteren. Es ist bewusst der ruhigste Bildschirm der Anwendung. Kein Chat, keine Seitenleiste, kein Modell, kein Readvisor — noch läuft nichts, und über nichts wird nachgedacht. Nur deine Projekte, und der ⚙-UI-Button in der oberen Leiste für das Thema und dieses Handbuch.

Du siehst ihn:

- beim allerersten Start, wenn der Erststart-Assistent fertig ist;
- bei jedem weiteren Start, außer **Reopen Last Project on Launch** ist an (Abschnitt 1.3);
- immer, wenn du ein Projekt schließt (Abschnitt 2.5);
- aus dem Terminal, jederzeit, mit `enough --home`.

Der einzige Weg, ihn *nicht* zu sehen, ist dieser Schalter. Schalte **Reopen Last Project on Launch** ein, und enough geht direkt zurück zum Projekt, in dem du warst; der Start schaltet sich nie dazwischen. Schalte ihn aus, und der Start ist, wo jeder Start beginnt. Dieser Schalter ist die ganze Einstellung — es gibt sonst nichts zu konfigurieren.

### 2.1 Das Raster, die Liste, und ¶ W C

Zwei Ansichten, umgeschaltet über das Buttonpaar oben rechts im Rahmen, und enough merkt sich, welche du bevorzugst.

**Symbole** ist die Stöber-Ansicht: ein Ordnersymbol, der Projektname, und eine schlichte Zeile darunter — *vor 3 Tagen bearbeitet*, oder ein echtes Datum, sobald es älter als eine Woche ist.

**Liste** ist die Vergleichs-Ansicht. Sechs Spalten:

| Spalte | was sie ist |
|---|---|
| Name | der Anzeigename des Projekts (der, den du in der Projekt-Titelleiste setzt, oder der Ordnername) |
| ¶ | Absätze |
| W | Wörter |
| C | Zeichen |
| zuletzt aktualisiert | die jüngste Änderung an irgendeiner der Dateien, die diese Zählungen erfassen |
| erstellt | wann der Ordner zu einem enough-Projekt wurde |

Diese drei mittleren Spalten sind dieselben drei Anzeigen, die enough in der oberen Leiste zeigt, während du ein Dokument offen hast — ¶ für Absätze (durch Leerzeilen getrennte Blöcke), W für Wörter, C für Zeichen einschließlich Leerzeichen und Zeilenumbrüchen — aufsummiert über das ganze Projekt. Die Regel, *welche* Dateien gezählt werden, ist einen Satz wert, denn sie ist es, die den Zahlen eine Bedeutung gibt: jede Markdown-Datei, die dir der eigene Dateibaum des Projekts zeigen würde, **einschließlich der Zwillinge konvertierter Dokumente** (eine `.docx`, die du hier bearbeitest, ist dein Text), und **nicht** irgendetwas in `rness/` (enoughs eigenes Gerüst ist nicht dein Buch). Die Zahl in der W-Spalte ist also, nahezu genau, wie viel du geschrieben hast.

Auf eine Spaltenüberschrift klicken, um danach zu sortieren; nochmal klicken, um umzukehren. Projekte ohne etwas zu berichten — nie geöffnet, nie gezählt — sinken so oder so nach unten, statt so zu tun, als wären sie die ältesten. Die Standardreihenfolge ist zuletzt bearbeitet zuerst.

Ein Projekt, dessen Ordner gerade nicht da ist — ein abgestecktes externes Laufwerk, ein Ordner, den du im Finder verschoben hast — wird grau dargestellt, mit dem gemerkten Pfad im Tooltip. Es wird **nicht** aus der Liste entfernt, und es behält die Zählungen, die es beim letzten Mal hatte. Ein Projekt auf einem Laufwerk in der Schublade ist kein verlorenes Projekt.

### 2.2 Ein Projekt anklicken: die Karte

Ein einzelner Klick öffnet kein Projekt. Er zeichnet dir eine **Karte** davon: ein nur lesbares merirmaid-Diagramm (Abschnitt 21) des sichtbaren Inhalts des Ordners, mit einem kleinen Info-Knoten oben, der den Pfad, die Dateizahl, die ¶- und W-Summen trägt, sowie wann das Projekt erstellt, zuletzt geöffnet und zuletzt bearbeitet wurde. Es ist dieselbe Art von Bild, die cacheawl für eine Cachebox zeichnet (Abschnitt 12.1), nur auf ein Projekt gerichtet.

Die Karte ist für den Moment gedacht, in dem du vier Ordner mit plausiblen Namen hast und wissen willst, in welchem die Kapitel stecken. Hinschauen, dann entscheiden.

Hast du dich entschieden, öffnet es der **Projekt öffnen**-Button in der Werkzeugleiste. Esc, oder das Band oben rechts, bringt dich zurück zum Raster. Und wenn du ohnehin schon wusstest, welches du wolltest, **doppelklicke** die Kachel oder Zeile, und es öffnet ohne den Umweg.

Das Öffnen sieht so oder so gleich aus: der Loader erscheint für ein, zwei Sekunden, während enough den Startbildschirm herunterfährt und das Projekt an seiner Stelle hochfährt, und dann bist du in der Gesprächsansicht (Abschnitt 4), genau als hättest du direkt in diesen Ordner gestartet.

### 2.3 Einen Ordner hinzufügen

Die letzte Kachel im Raster — die mit dem Plus — ist, wie ein Ordner zu einem Projekt wird.

Klick sie an, und macOS öffnet seinen eigenen Ordner-Auswähler. Wähl einen beliebigen Ordner mit Notizen, Entwürfen oder Dokumenten; enough fügt ihm `rness/` hinzu (Abschnitt 8), registriert ihn auf deinem Startbildschirm und öffnet ihn. Die Kachel sagt *warte auf den Ordner-Auswähler…*, während der Dialog offen ist, also nimm dir beim Stöbern so viel Zeit, wie du willst.

Zwei Arten von Ordnern werden abgelehnt, und enough sagt dir, welche und warum, statt vage zu scheitern:

- **`~/enough` selbst, oder irgendetwas darin.** Das ist die Installation, kein Projekt. (Der Befehl `enough` verweigert denselben Ordner aus demselben Grund.)
- **Alles innerhalb eines cloud-synchronisierten Ordners** — Google Drive, Dropbox, iCloud Drive. Das ist keine Pingeligkeit. Das `rness/` eines Projekts besteht aus Symlinks zurück in die globalen Defaults, und Sync-Clients schreiben Symlinks routinemäßig um oder brechen sie; du bekämst ein Projekt, das still aufhört, deinen globalen Einstellungen zu folgen, auf dem Rechner, wo du es nicht bemerkt hast. Halte Projekte auf der lokalen Platte und synchronisiere stattdessen die fertige Arbeit.

Ein Ordner, der schon auf deinem Startbildschirm ist, ist kein Fehler — enough öffnet ihn einfach.

Kann der Ordner-Auswähler gar nicht erst erscheinen (ein Rechner, der kein Mac ist, eine Sandbox, die sich weigert), bietet das Modal stattdessen ein schlichtes Textfeld, um den Pfad einzutippen, mit dem Grund darüber angezeigt. Alles Weitere ist identisch.

### 2.4 Ein Projekt ausblenden

Der Start listet alles, für immer, und nach einem Jahr voller Experimente wird das lang. Also: **option-klick auf eine Kachel oder Zeile, um sie auszublenden.**

Ausblenden ist ein Vermerk in enoughs eigener Liste und sonst nichts. Es sagt das auch, wenn es fragt: der Ordner auf der Festplatte wird nicht angefasst, `rness/` wird nicht angefasst, und kein einziges Wort darin ändert sich. Es gibt kein „dieses Projekt löschen“ auf dem Startbildschirm, und das ist Absicht — ein Projekt zu löschen heißt, einen Ordner voller deines Geschriebenen zu löschen, und das ist eine Aufgabe für den Finder, wo du sehen kannst, was du tust.

Der Chip **ausgeblendet** neben den Ansicht-Buttons holt sie zurück, beschriftet mit ihrer Anzahl. Ausgeblendete Projekte werden grau mit *ausgeblendet* in ihrer Zeile dargestellt; option-klick auf eines, um es einzublenden (keine Bestätigung — es geht sofort und ist sofort umkehrbar). In der App lässt sich derselbe Schalter auch über **Ansicht → Ausgeblendete Projekte zeigen** bedienen.

### 2.5 Ein Projekt schließen, und zurückkommen

Zwei Türen, ein Raum.

**In der App:** **Datei → Projekt schließen**, oder **⌘W**. Das Backend des Projekts fährt sauber herunter, und der Startbildschirm erscheint an seiner Stelle, eine Sekunde oder so später.

**Überall, App oder Browser:** der Button **Projekt schließen → Start** oben im ⚙-UI-Fenster (Abschnitt 10). Er fragt zuerst, weil Schließen die Sitzung beendet — das Gespräch vor dir ist vorbei, genau wie bei einem Beenden — und landet dich dann genau dort, wo auch ⌘W dich hinbringen würde.

Keins von beiden fasst deinen Ordner an. Deine Dateien, dein `rness/`, deine Anfrage-Dateien und deine Sitzungsprotokolle sind alle genau dort, wo du sie gelassen hast; nur das laufende Gespräch endet.

Eine Folge des neuen ⌘W, die zu kennen sich lohnt, wenn du enough schon eine Weile nutzt: **⌘W schließt das Fenster nicht mehr.** enough ist eine Ein-Fenster-Anwendung, und das Schließen dieses Fensters beendet sie, also deckten ⌘Q und der rote Button dieses Terrain schon ab, und ⌘W hatte eine bessere Aufgabe zu erledigen.

Und eine Wechselwirkung zwischen diesem und der Reopen-Einstellung, denn sonst überrascht sie dich garantiert genau einmal: **ein Projekt zu schließen lässt enough es nicht vergessen.** Ist **Reopen Last Project on Launch** an, und du schließt ein Projekt, bleibst eine Weile auf dem Start und beendest dann — öffnet der nächste Start wieder dieses Projekt, nicht den Start. Der Schalter ist die Einstellung, die entscheidet, wo du beginnst; Projekt schließen ist der Button, der entscheidet, wo du gerade bist. Willst du von jetzt an auf dem Start beginnen, schalte den Schalter aus.

### 2.6 Was der Start sich merkt

Drei kleine Dinge, alle rechnerweit — sie folgen dir von Projekt zu Projekt und zurück zum Start, und sie werden in keinem Projektordner gespeichert:

- **Das Thema und die Schrift** (Abschnitt 10.1). Der Start trägt, was du zuletzt gewählt hast, und ein Thema, zu dem du *auf* dem Startbildschirm wechselst, ist das Thema, in dem dein Projekt öffnet. Das ist der Punkt, der früher genervt hat: der Startbildschirm und der Arbeitsbildschirm sind sich jetzt immer einig.
- **Symbole oder Liste**, aus Abschnitt 2.1.
- **Ob ausgeblendete Projekte angezeigt werden**, aus Abschnitt 2.4.

Alles andere über ein Projekt lebt im Ordner dieses Projekts, wo du es lesen kannst.

---

## 3. Workflow-Anpassung auf einer Kernebene

Wenn du nur einen Abschnitt liest, lies diesen.

Die meiste Software gibt dir Funktionen. enough gibt dir Mechanismen. Persönlichkeit, Methode und Fähigkeiten deines Chef-Readvisors werden bei jeder einzelnen Nachricht neu aus Markdown-Dateien zusammengesetzt, die auf deiner Festplatte liegen:

- **`AGENT.md`** — wer dein Chef-Readvisor ist und wie er arbeitet (Abschnitt 5.3)
- **`MOTIVATION.md`** — warum: Werte, Prioritäten, wie sich „fertig“ anfühlt
- **Richtlinien** — feste Regeln darüber, was gelesen, geschrieben und abgerufen werden darf (Abschnitt 5.4)
- **Das aktive Paradigma** — das gerade geltende Denkgerüst (Abschnitt 16)
- **Aktivierte Skills** — Fähigkeiten, auf die sie zurückgreifen können (Abschnitt 19)
- **Aktivierte Readvisors** — andere Urteile, die in die Stimme eingefaltet oder in einen Rat gesetzt werden (Abschnitt 17)
- **Das Projektprofil** — was über dieses Projekt gelernt wurde (Abschnitt 8.1)

Bearbeite eines davon, in der App oder in einem beliebigen Texteditor, und die Änderung wirkt ab der nächsten Nachricht. Kein Neubau, kein Neustart, keine Plugin-API. Wenn du eine Markdown-Datei schreiben kannst, kannst du deine Readvisors umprogrammieren.

### 3.1 Global vs. projektlokal

Alles Anpassbare folgt einem Muster: **Defaults leben in `~/enough/defaults/`, Projekte verlinken darauf, und jedes Projekt kann den Link aufbrechen.**

Bearbeite eine Datei in `~/enough/defaults/`, und jedes Projekt, das noch damit verlinkt ist, übernimmt die Änderung. In einem Projekt eine verlinkte Datei öffnen und auf **anpassen** klicken — der Link wird zu einer projektlokalen Kopie, und von da an geht dieses Projekt seinen eigenen Weg, während die anderen weiter dem globalen Default folgen. Der Dateibaum zeigt dir auf einen Blick, was was ist: verlinkte Dateien erscheinen *kursiv und gedämpft*, lokale Kopien normal.

Neue Skills und Paradigmen, die in `~/enough/defaults/` abgelegt werden, erscheinen beim nächsten Start in jedem Projekt; Readvisors haben ein zweites, beschreibbares Zuhause für sich in `~/enough/readvisors/` (Abschnitt 17). Skills und Readvisors kommen ausgeschaltet an, sodass sich nichts hinter deinem Rücken ändert; du aktivierst sie pro Projekt, wenn du sie willst. Ein Skill, den enough nicht mitgeliefert hat — heruntergeladen, von einem Freund geschickt, während einer Sitzung für dich geschrieben — wird gelesen, bevor er hereingelassen wird. Abschnitt 19.9 behandelt das.

### 3.2 Die drei Bausteinarten

| | Paradigma | Skill | Readvisor |
|---|---|---|---|
| Was es ist | ein Denkgerüst — wie an Arbeit herangegangen wird | eine fokussierte Fähigkeit — Vokabular, Rezepte, Abläufe | ein zweites Urteil — mit eigener AGENT.md + MOTIVATION.md |
| Wie viele aktiv | immer genau eines | beliebig viele eingeschaltet | beliebig viele eingeschaltet |
| Liegt unter | `rness/paradigms/<name>.md` | `rness/skills/<name>/SKILL.md` | `rness/readvisors/<name>/` |
| Mitgelieferte Beispiele | text-planning (Heimat), translation, workflow-design | analyzer, anything-finder, girraph-merirmaid, lexicographer, memoir-dialectic, readvisory, scaffold, translator | block-breaker, open-skeptic |

### 3.3 Eigene bauen

Du kannst diese Dateien von Hand schreiben — sie sind Markdown mit einem kleinen YAML-Block oben —, aber du musst nicht. Das mitgelieferte **workflow-design-Paradigma** (Abschnitt 16.3) existiert, damit dein Chef-Readvisor sie mit dir bauen kann. Sag „bau mir einen Skill, der…“ oder „mach ein Paradigma für…“, und er wechselt in workflow-design, stellt seine klärenden Fragen (Umfang? Name? Auslösebedingungen? Begleitdateien?), und schreibt den Baustein richtig, einschließlich des `description:`-Frontmatters, das künftigen Zügen sagt, wann sie darauf zurückgreifen sollen. Readvisors haben ihren eigenen Weg hinein — den `readvisory`-Skill (Abschnitt 19.6), der einen Menschen befragt statt eine Spezifikation.

Was Leute tatsächlich bauen:

- Ein **Paradigma** für jede eigene Arbeitsweise — Recherche, Entwurf, Überarbeitung — mit ausdrücklichen Regeln, wann gewechselt wird.
- Einen **Skill**, der die Stimme eines Newsletters, ein Zitierformat oder die Terminologie einer Dissertation kodiert.
- Einen **Readvisor** als Gummiente, die sokratische Fragen stellt, oder als skeptischen Peer-Reviewer, oder als den Freund, dessen Geschmack sie am meisten vertrauen, einmal befragt und dann behalten.

Der Rest dieses Handbuchs beschreibt die eingebauten Bausteine. Lies jeden von ihnen als durchgearbeitetes Beispiel, das du kopieren, abzweigen und verbessern darfst.

---

## 4. Composure — die Basis des Stapels

Öffne ein Projekt, und du landest auf einer **Composure**: eine Leinwand, die das Fenster füllt, mit dem Gespräch in einem Panel daneben (Abschnitt 5). Das ist das Erdgeschoss. Es ist kein Modus, den du betrittst und wieder verlässt — jeder andere Modus stapelt sich darüber und schließt am Ende wieder darauf zurück, und es gibt keine Möglichkeit, ihn zu schließen, weil darunter nichts mehr käme. (Der *Startbildschirm* aus Abschnitt 2 ist etwas ganz anderes — dort bist du, bevor ein Projekt offen ist; hier bist du, sobald eines offen ist.)

Eine Composure ist eine `.comp`-Datei: Kästen voller Geschriebenem, und freihändige Tinte, auf einer randlosen Fläche, über die du schiebst und zoomst. Die Kästen heißen **Module**. Es gibt keinen Speichern-Button — alles wird geschrieben, während du arbeitest — und die Datei selbst ist gewöhnliches HTML, eine `.comp` öffnet also als schlichte, lesbare Seite in jedem Browser, auf einem Rechner ganz ohne installiertes enough. Das ist kein Nebeneffekt. Ein Dokument, das du nur in dem Programm lesen kannst, das es gemacht hat, ist ein Dokument, das du jemandem geliehen hast.

Was drumherum liegt:

- **Die Werkzeugleiste**, quer über der Leinwand: der Titel der Composure (hineintippen, wegklicken, umbenannt), der Lese-/Bearbeiten-Schalter, die Werkzeuge, **ein Modul hinzufügen**, Rückgängig und Wiederherstellen, die Zoom-Gruppe, die Suche, der Kommentar-Schalter und das **Composures**-Menü — neu aus einem Form…, öffnen…, als Form speichern….
- **Die Seitenleiste.** Der Dateibaum des Projekts, dazu die Steuerbereiche: das aktive **Paradigma**, die Schalter für **Skills** und **Readvisors**, und deine **Anfragen**. Option-Klick auf eine Datei oder einen Ordner öffnet ein Kontextmenü (neue Datei, neuer Ordner, Pfad kopieren, Namen kopieren). ⌘\ blendet die ganze Seitenleiste aus und wieder ein.
- **Die obere Leiste.** Buttons für das Modell-Fenster, den Broker, das UI-Fenster, wikisink (🚰) und cacheawl; die Anzeigen für die gerade gestapelt offenen Modi (Abschnitt 14); und ganz rechts der Schalter für das Readvisor-Panel.

### 4.1 Sich bewegen

**Schieben** mit einem Zwei-Finger-Scroll, mit gedrückter Leertaste, oder mit der mittleren Maustaste. **Zoomen** mit Pinch, mit ⌘-Scrollen um den Zeiger herum, mit ⌘+ / ⌘− / ⌘0, oder mit **einpassen**, das alles, was du hast, ins Bild nimmt und zentriert. Die Zoom-Anzeige in der Werkzeugleiste ist ein Button: anklicken für 100 %.

Drei Dinge bewegen die Ansicht von selbst, und alle drei wollen helfen.

**Das Einpassen, wann immer sich der Platz ändert.** Auf einer Tafel — jeder Composure, die nicht die Form einer Seite hat — endet jede Änderung des Platzes, den die Leinwand zur Verfügung hat, genau dort, wo dich **einpassen** hinsetzen würde: alles im Bild, zentriert. Blende die Seitenleiste aus, öffne oder schließe das Readvisor-Panel, gib ihm das ganze Fenster und nimm es wieder zurück, öffne die Kommentare, zieh das Fenster auf oder zu, ändere die UI-Größe: einen Moment, nachdem die Änderung zur Ruhe gekommen ist, kommt auch die Tafel zur Ruhe. Es wartet auch auf dich. Es nimmt dir die Ansicht nie weg, solange du ziehst, pinchst oder scrollst, und solange ein Modus über der Composure gestapelt ist, hält es sich zurück, bis du wieder zu ihr hinunterkommst. Von Hand zu zoomen funktioniert weiterhin wie immer; es hält, bis sich der Platz das nächste Mal ändert.

**Die Panel-Stufen.** Auf einer Seite macht das Ausblenden eines Seitenpanels die Leinwand nicht nur breiter, es macht sie *größer*: Text auf einer Seite liest sich bei etwa 12 Punkt, wenn Seitenleiste und Readvisor-Panel beide offen sind, bei etwa 14 mit einem von beiden ausgeblendet, und bei etwa 16 mit beiden. Die Änderung wird über eine Fünftelsekunde animiert, verankert an deinem Cursor, wenn du tippst, und an der Mitte der Ansicht, wenn nicht, damit du deinen Platz nicht verlierst.

**Die Seiteneinpassung.** Eine Composure in Seitenform — blank, Journal, Rat — wird zentriert und auf dem Zoom gehalten, bei dem ihre volle Breite mit bequemem Rand hineinpasst, bis du das erste Mal von Hand zoomst. Ein breiteres Fenster zeigt mehr Fläche um das Blatt herum, nicht ein größeres Blatt. Eingepasst wird nur die Breite: eine Seite ist höher als die meisten Fenster, ihr unteres Ende ist also immer einen Schub entfernt. Ändert sich der Platz, behält eine Seite diese Anordnung — die Breite neu eingepasst, das Blatt neu zentriert, deine Leseposition dort, wo sie war —, statt so verkleinert zu werden, dass man ein langes Blatt ganz auf einmal sieht.

**Schauseiten.** Zoom weit genug heraus, und jedes Modul klappt auf seine **Schauseite** zusammen: sein Titel, so groß gesetzt, wie der Kasten es zulässt, der Rumpf als Blindtext. Sechzig Karten lesen sich dann als sechzig Titel statt als sechzig graue Rechtecke, und eine Tafel, die du in Lesegröße gebaut hast, ist auch auf einen Blick noch eine Tafel. Gib einem Modul einen Titel, und du entscheidest, was diese Schauseite sagt. Tinte wiederum wird langsamer dünn, als alles andere schrumpft, damit eine herausgezoomte Skizze immer noch als Skizze lesbar bleibt.

### 4.2 Die vier Werkzeuge

Der Lese-/Bearbeiten-Schalter arbeitet wie überall sonst in enough: ein Auge zum Lesen, ein Stift zum Ändern. Die Werkzeuge gibt es nur auf der Bearbeitungsseite, und jedes hat einen Buchstaben.

- **Zeiger (V)** wählt aus. Klick ein Modul an, zieh es zum Verschieben, zieh an einem Griff zum Ändern der Größe, zieh einen Rahmen über leere Fläche, um mehrere einzufangen. Umschalt-Klick nimmt eines dazu oder heraus. Pfeiltasten stupsen an; mit Umschalt in größeren Schritten. Entfernen löscht — mit Warnung vorweg, wenn Geschriebenes darin steht, und ⌘Z, um es zurückzuholen. Doppelklick auf ein Textmodul, und du bist mit dem Textwerkzeug darin.
- **Text (T)** setzt den Cursor in ein Textmodul. Es kann keine Kästen machen, und ein Klick auf leere Fläche tut nichts; das ist die Aufgabe des Modul-hinzufügen-Buttons. Innerhalb einer Seite bekommst du fett und kursiv, Überschriftenebenen, Listen, Checklisten, Zitate, Code, Links und die vier Markierungsfarben — mit dem Markdown, das du ohnehin tippst: `# `, `- `, `1. `, `[] `, `> ` und ein eingerahmter Block werden beim Tippen zum echten Ding. Alles, was du einfügst, wird zuerst auf schlichte Struktur heruntergebrochen.
- **Stift (P)** zeichnet. Zeichne einfach drauflos; die Linie wird geglättet und vereinfacht, sobald du loslässt. Hältst du beim Ziehen **Umschalt**, bekommst du ein gerades Stück mit einer Pfeilspitze am Ende — so sagt man *dies, dann das*.
- **Radierer (E)** wischt weg. Er ist ein Kreis, der auf dem Bildschirm immer gleich groß bleibt, wie weit du auch herausgezoomt hast. Zieh ihn durch eine Linie, und das Stück unter dem Kreis verschwindet, die beiden Enden bleiben als getrennte Striche zurück; ⌘Z setzt die Linie wieder in einem Stück zusammen.

Tinte liegt auf der Fläche, *unter* den Modulen, eine Notiz kann also über drei Karten laufen und ein Pfeil zwei verbinden. Heb einen Strich mit dem Zeiger auf, indem du in seine Nähe klickst, und der Inspektor bietet die fünf Tintenfarben — Tinte, Rot, Blau, Grün, Gelb — und ein Löschen.

### 4.3 Module: die sechs Arten

Ein **Text**-Modul ist Geschriebenes, mit so vielen Seiten darin, wie du willst. Die anderen fünf zeigen auf etwas, zeigen dir beim Lesen eine lebende Vorschau davon, und öffnen beim Klick die Sache selbst:

- **eine Datei in diesem Projekt** — ihre ersten Zeilen, und ein Klick öffnet sie genau so, wie ein Klick im Dateibaum es täte (konvertierte Dokumente eingeschlossen). Lass eines auf eine `.comp` zeigen, und der Klick tauscht die Leinwand unter dir aus — das ist es, was aus einer Tafel einen Einstieg in die Tiefe macht.
- **ein wikisink-Artikel** — die ersten Absätze, und ein Klick öffnet den wikisink-Reader dort (Abschnitt 11). Auf einem Rechner ohne Archiv sagt die Karte das, behält den Artikelnamen, und füllt sich selbst aus, sobald eines installiert ist.
- **ein Link ins Web** — der Titel und der Host. Ein Klick öffnet ihn in deinem Browser, wie jeder andere externe Link in der App.
- **eine zwischengespeicherte Webseite** — der Text der Seite vom letzten Abruf, mit Datum und einem **Aktualisieren**-Button. Das Aktualisieren läuft genau wie jeder andere Web-Zugriff durch den Broker, deine Abruf-Schalter, Positivlisten und die Tor-Leitung gelten also alle — und verweigert der Broker, zeigt dir die Karte seine Ablehnung in den eigenen Worten des Brokers, damit du weißt, welchen Schalter du dir ansehen musst.
- **ein Bild** — das Bild, auf den Kasten skaliert. Ein Klick öffnet den Bildbetrachter (Abschnitt 7.9).

**Ein Modul hinzufügen** öffnet eine kurze Liste der sechs. enough platziert und dimensioniert das neue für dich, nahe bei dem, was du gerade angesehen hast, und wählt es aus.

### 4.4 Der Inspektor

Wähl auf der Bearbeitungsseite etwas aus, und daneben — nie darüber — erscheint ein kleines Panel mit allem, was zutrifft:

- **Zehn Hintergrundfarben**: Papier, Gelb, Pink, Blau, Grün, Orange, Flieder und Grau, dazu **Tinte**, eine dunkle Karte, und **klar**, gar keine Karte. Die letzten beiden sind für Struktur: eine dunkle Karte für eine Überschriftenreihe, eine klare für eine Beschriftung, die nicht wie eine Notiz aussehen soll.
- **Textgröße**, kleiner und größer, nur für dieses Modul.
- **Seiten**: eine hinzufügen, eine entfernen. Ein Modul mit mehr als einer Seite trägt Blätter-Buttons und eine `n / N`-Beschriftung, und Text, der über eine Seite hinauswächst, bietet **auf einer neuen Seite weiter →** an, statt still für immer weiterzuwachsen.
- **Reihenfolge**: nach vorn holen, nach hinten schicken.
- **Das eigene Feld der jeweiligen Art**, wo es eines gibt — ein Dateiwähler, der deinen Projektbaum beim Tippen durchsucht, ein wikisink-Suchfeld, ein Adressfeld, eine Aktualisierungsregel.
- **Dieses Modul kommentieren**, und **löschen**.

Wähl mehrere Module aus, und der Inspektor sagt, wie viele es sind, und bietet an, was noch sinnvoll ist.

### 4.5 Forms, und eigene speichern

Ein **Form** ist eine Composure-Vorlage. Fünf werden mitgeliefert:

- **blank** — ein seitenförmiges Blatt, das auf der Bearbeitungsseite öffnet, mit dem Cursor schon darin blinkend.
- **cards** — eine Tafel aus Textkarten in einem Raster, die herausgezoomt und eingepasst öffnet.
- **scaffold** — eine Tafel, angelegt als Spalten von Beats, mit einem Band über dem Kopf für die Prämisse und einer Reihe am Fuß für die Enden. Es ist das, was der `scaffold`-Skill (Abschnitt 19.7) füllt, wenn er aus einem Haufen Notizen eine Struktur macht.
- **journal** — ein datiertes Protokoll. Ein Modul, ein Eintrag je Seite. Öffnest du ein Journal, landest du auf der *heutigen* Seite, mit dem Cursor darin, und diese Seite steht nur im Arbeitsspeicher, bis du etwas schreibst — das Journal zu öffnen und es sich dann anders zu überlegen hinterlässt also nichts. Der Eintrag speichert sich selbst, während du tippst; gehst du, ohne ihn abzulegen, öffnet das Journal wieder denselben unfertigen Entwurf. **Diesen Eintrag ablegen** stempelt ihn mit dem Datum und macht ihn dauerhaft schreibgeschützt — enough weigert sich danach, ihn zu ändern, und der Cursor geht nicht mehr hinein — und bringt dich weiter auf eine frische Seite. Durch abgelegte Einträge zurückzublättern ist gefahrlos: eine Seite umzublättern, in die du nichts geschrieben hast, speichert überhaupt nichts. Kommentieren kannst du abgelegten Text weiterhin, was ja gerade der Sinn des Ablegens ist.
- **council** — ein Raum voller Readvisors, die reihum über eine Sache nachdenken. Das ist Abschnitt 18.

**Als Form speichern…**, im Composures-Menü, behält die Composure, die du gerade ansiehst, als dein eigenes Form. Es landet in `rness/composure-forms/` und gehört von da an in diesem Projekt zur Liste. Ein eigenes Form, das den Namen eines mitgelieferten trägt, gewinnt.

### 4.6 Suche, Kommentare, und Zurücknehmen

**Die Suche** liest den reinen Text jedes Moduls und jeder Seite — oder den eines einzelnen Moduls, wenn genau eines ausgewählt ist. Enter und Umschalt+Enter laufen die Treffer ab, mit einer Zählung neben dem Feld. Ein Treffer ist ein *Ort*, keine Markierung: die Leinwand gleitet dorthin, blättert auf seine Seite, wenn er auf einer anderen liegt, und blitzt kurz über den Worten auf. Nichts in deinem Text wird angefasst, um dir zu zeigen, wo er steht. Esc leert die Anfrage.

**Kommentare** funktionieren wie die von wikisink (Abschnitt 11.2), auf denselben Karten. Markier Text in einem Modul und kommentier ihn, oder kommentier ein ganzes Modul über den Inspektor oder das Menü, das ein Rechtsklick darauf öffnet; der Kommentar-Button in der Werkzeugleiste öffnet das Panel. Antworten, erledigen, wieder öffnen, hinspringen. Text, den du später wegbearbeitest, wird an sein Modul neu geheftet; ein ganz gelöschtes Modul hinterlässt den Kommentar als **verwaist** im Panel, beschriftet, nie still weggeworfen. Kommentare liegen in einer verborgenen Datei neben der `.comp` statt darin, die Composure selbst bleibt also sauber — und sie funktionieren an Dingen, die du gar nicht bearbeiten kannst, etwa an einer abgelegten Journalseite oder einem Ratsbeitrag.

**Rückgängig** ist ⌘Z, Wiederherstellen ist ⇧⌘Z, bis zu hundert Schritte je offener Composure. Innerhalb einer Textseite übernimmt das Rückgängig deines Browsers, was dort das richtige ist.

### 4.7 Wo Composures liegen, und was beim Start aufgeht

Neue Composures landen in `rness/io/composure/`, benannt nach ihrem Titel und dem Datum. Es sind gewöhnliche Dateien: kopier sie, stell sie unter git, schick eine an jemanden, der noch nie von enough gehört hat.

Nichts wird geschrieben, bevor nicht etwas *hinein*geschrieben wurde. Eine Composure, die du öffnest und nie anfasst, hinterlässt überhaupt keine Datei — nicht einmal eine leere. Sobald es etwas zu speichern gibt, hält dich der Speicherstand in der Werkzeugleiste auf dem Laufenden: *wird gespeichert…*, dann *gespeichert*, oder *nicht gespeichert — wird wiederholt*, wenn der Server kurz nicht erreichbar ist, was die ehrliche Meldung ist statt einer stillen Lüge.

Welche Composure dich empfängt, bestimmst du. Das **Projekt**-Fenster — das mit Name, Beschreibung und Ordner des Projekts — trägt eine Zeile **beim Start öffnen** mit vier Antworten: *eine neue leere Seite*, *die zuletzt benutzte Composure*, *eine bestimmte Composure…*, oder *eine neue aus einem Form…*. Ist das, worauf du gezeigt hast, inzwischen umbenannt oder gelöscht, öffnet enough eine leere Seite und sagt es in einer Zeile, statt dich beim Hereinkommen anzufahren.

Und jede `.comp` im Dateibaum öffnet mit einem Klick. Sie stapelt sich nicht über das, was du gerade tust — sie *wird* das, was die Leinwand zeigt, denn es gibt immer nur ein Erdgeschoss.

### 4.8 Unter den Stapel schauen

Die Modus-Stapel-Anzeigen in der oberen Leiste (Abschnitt 14) enden in einem dauerhaften Quadrat für die Composure. Es hat kein Schließen-Band, weil es nichts zu schließen gibt.

Klick es an, während Modi gestapelt sind, und jeder einzelne verschwindet und zeigt dir die Leinwand darunter, mit ihrem Zustand genau so, wie er war — deine Scroll-Position, deine ungespeicherten Änderungen, dein Abstieg in einen verschachtelten girraph. Klick es noch einmal an, oder klick irgendeine andere Anzeige, und sie kommen sofort zurück. Esc während des Blicks stellt erst den Stapel wieder her und räumt dann ab.

Es ist für den Moment, in dem das, was du nachsehen musst, auf der Tafel liegt und du nicht drei Modi abbauen willst, um es zu sehen.

### 4.9 Was deine Readvisors mit einer Composure machen können

Sie können eine lesen, eine aus einem Form anlegen, Module hinzufügen, umfärben und umsortieren, eine Seite schreiben, eine Composure als Form speichern, und — mit dem `scaffold`-Skill (Abschnitt 19.7) — eine ganze Gliederung in einem Zug in eine ausgelegte Tafel verwandeln. Das alles hängt am Schalter **composure tools** im Broker (Abschnitt 9); deine eigene Leinwand hängt nie daran, genauso wenig wie dein eigenes wikisink- und cacheawl-Stöbern.

Was sie nicht können, ist eine `.comp` als Datei schreiben. Beide gewöhnlichen Türen zum Dateischreiben verweigern die Endung rundheraus, jede Änderung, die ein Readvisor macht, läuft also über dieselbe kleine Menge von Operationen, die du benutzt, eine nach der anderen, durch dieselbe Tür, aktenkundig. Das heißt: ein Modell, das durcheinanderkommt, kann kein Dokument beschädigen — das Schlimmste, was es anrichten kann, ist eine Karte, die du nicht wolltest, und ⌘Z liegt gleich daneben.

Ändert ein Readvisor ein Modul, während du auf die Composure schaust, aktualisiert es sich an Ort und Stelle, mit kurzem Aufblitzen. Das eine Modul, das dir nie unter den Händen aktualisiert wird, ist das, in das du gerade tippst.

---

## 5. Das Readvisor-Panel

Das Gespräch wohnt in einer Spalte am rechten Rand, neben dem, woran du arbeitest, statt an seiner Stelle. Dein **Chef-Readvisor** steht namentlich oben — **Ed**, bis du ihn umbenennst (Abschnitt 17) —, daneben alle anderen Readvisors, die du eingeschaltet hast. Im gewöhnlichen Gespräch antworten sie als eine Stimme, die aus all diesen Blickwinkeln schöpft; in einem Rat (Abschnitt 18) sprechen sie einzeln.

Tipp eine Nachricht und drück ⌘Enter, oder den Senden-Button. Antworten strömen live herein, und enough kann handeln, während dein Readvisor spricht — Dateien lesen und schreiben, Shell-Befehle ausführen, Seiten abrufen —, wobei jeder Tool-Aufruf im Protokoll erscheint, sobald er passiert. Der **Mikrofon-Button** diktiert: Sprache wird lokal von whisper.cpp transkribiert, deine Stimme verlässt den Rechner nie, und der Button pulsiert, während er aufnimmt. Noch einmal klicken stoppt.

Die beiden Stimmen halten sich an ihre eigenen Seiten der Spalte: deine Nachrichten sitzen am linken Rand, die deines Chef-Readvisors am rechten, jede mit einem dünnen Strich in ihrer eigenen Farbe am äußeren Rand, sodass sich ein langer Austausch auf einen Blick noch als Austausch liest. Nur die Blöcke wandern — der Text darin bleibt linksbündig, denn rechtsbündige Prosa liest sich schlecht. enoughs eigene Hinweise (eine Ablehnung, ein Tipp, die Frage, die ein `/pal` hinausgeschickt hat) laufen über die volle Breite, da sie niemandes Stimme sind.

**Eine kurze Einführung.** Ein leeres Gespräch bietet eine an: einen kleinen Link, *eine kurze Einführung in enough*, unter der Wartezeile. Klick darauf, oder tipp jederzeit `/intro`, und dein Chef-Readvisor bringt eine kurze Tour auf den Bildschirm — was ein Projekt ist, die Composure, Lesen/Bearbeiten, die Readvisors, die Paradigmen, das Wörterbuch und der Rest der lokalen Referenz, und wo das ganze Handbuch liegt. Kein Modell schreibt sie, sie erscheint also sofort und sagt jedes Mal dasselbe. Fragst du gleich als allererste Nachricht „Was kannst du?“ oder „Was ist enough?“, bekommst du dieselbe Einführung; später in einem Gespräch gehen diese Fragen wie alles andere an deinen Readvisor, denn dann meint „Was ist das?“ meistens etwas auf dem Bildschirm. Und wenn du mit einem schlichten Hallo beginnst, bietet dein Chef dir die Einführung womöglich vor allem anderen an. Sie folgt deiner Oberflächensprache, wo es eine Übersetzung davon gibt, und ist sonst auf Englisch.

### 5.1 Angedockt, ganz, geschlossen

Drei Zustände, ein Schalter ganz rechts in der oberen Leiste.

**Angedockt** ist die Vorgabe, und die, in der man wohnt. Es ist eine echte Spalte neben der Leinwand — oder neben jedem Modus, den du darüber gestapelt hast —, du musst also nie schließen, was du gerade liest, um danach zu fragen. In einem Fenster, das dafür zu schmal ist, wo das Andocken die Bühne unter etwa 480 Pixel quetschen würde, schwebt das Panel stattdessen über dem rechten Rand der Bühne, statt sie weiter zusammenzuschieben.

**Ganz** gibt dem Panel das ganze Fenster, mit dem Gespräch zentriert in einer lesbaren Spalte. Das ist der Rückgriff: die alte Diskussionsansicht, für den Fall, dass die Antwort lang ist und du dich mit ihr hinsetzen willst.

**Geschlossen** ist eine Spalte der Breite null. Endet ein Zug, während das Panel geschlossen ist, erscheint ein Punkt auf seinem Button in der oberen Leiste — *da ist etwas gelandet, während du weggeschaut hast*, nicht *hier steht eine gute Antwort* — und das Öffnen des Panels räumt ihn weg.

⌘/ öffnet und schließt. ⇧⌘/ gibt ihm das ganze Fenster, und ⌘/ holt es zurück. ⌘K fokussiert immer das Nachrichtenfeld und öffnet das Panel unterwegs, falls es zu war. Esc holt ein ganzes Panel zurück auf angedockt — aber Esc ist wirkungslos, solange der Cursor im Nachrichtenfeld steht, und das Öffnen des Panels setzt ihn genau dorthin, also erst wegklicken. **Esc schließt niemals ein angedocktes Panel**, mit Absicht: das wäre der eine Tastendruck, den alle versehentlich machen.

Offen oder geschlossen wird je Projekt gemerkt, in den eigenen Dateien dieses Projekts, und angewandt, bevor das Fenster zum ersten Mal zeichnet, damit beim Start nichts ruckt. Ganz ist eine Geste statt einer Einstellung und wird nie gemerkt.

**Eine Ausnahme, und das ist ein Rat.** Solange ein Rat auf der Leinwand läuft (Abschnitt 18), wird das Panel geschlossen gehalten und sein Schalter ist deaktiviert, mit einem Tooltip, der sagt, warum: Räte und der Chat teilen sich ein Modell, und es gibt nur eines davon. Verlässt du den Rat, bekommst du das Panel genau so zurück, wie du es hattest — deine eigene Vorliebe wird gemerkt, nicht überschrieben.

### 5.2 Eine Auswahl mitschicken

Markier Text irgendwo, wo das Panel ihn sehen kann — ein Dokument im Lese-/Bearbeitungsmodus, ein wikisink-Artikel, ein Modul auf einer Composure — und über dem Nachrichtenfeld erscheint ein Chip, der nennt, woher er stammt, und den Anfang zitiert. Schick ab, und diese Passage reitet mit deiner Nachricht mit, eingerahmt, beschriftet mit genau dem, was der Chip gesagt hat. Das × auf dem Chip wirft ihn weg.

Anhängen schlägt Beschreiben. Die genauen Worte gehen hinüber, und deinem Readvisor wird gesagt, woher sie stammen, statt dass er suchen gehen muss. Und *sonst* wird nichts angehängt: ein Modus, der hinter dem Panel offen steht, stempelt sich nicht still auf jede Nachricht, die du schickst. Was du gewählt hast, ist das, was mitgeht.

### 5.3 AGENT.md und MOTIVATION.md

Jedes Projekt trägt seine eigene Kopie dieser beiden Dateien in `rness/`. Sie sind die Wurzel der Identität deines Chef-Readvisors hier, und beide werden bei jedem Zug geladen.

**`AGENT.md`** ist das *Wie*: Arbeitsanweisungen. Ton, Leitplanken, Konventionen, stehende Befehle. „Halt die Prosa klein geschrieben.“ „Fass nie Dateien in `archive/` an.“ „Frag nach, bevor du Shell-Befehle ausführst, die länger als eine Zeile sind.“

**`MOTIVATION.md`** ist das *Warum*: Werte und Prioritäten jenseits der Aufgabe, die gerade ansteht. Wofür das Projekt da ist, wem es dient, welche Abwägungen zählen (Richtigkeit vor Tempo? Kürze vor Gründlichkeit?), wie sich „fertig“ anfühlt.

Klick eine der beiden Dateien in der Seitenleiste an, um sie zu lesen; drück **anpassen**, um deine projektlokale Kopie abzuzweigen, oder bearbeite sie in einem beliebigen Editor. Änderungen wirken ab der nächsten Nachricht. Jeder andere Readvisor nutzt dieselben zwei Dateien (Abschnitt 17) — der Chef ist keine andere Art Ding, nur derjenige, der standardmäßig spricht.

### 5.4 Der Richtlinien-Ordner und Positivlisten

`rness/policies/` enthält die festen Regeln. Nicht Persönlichkeit — Gesetz. Vier Richtlinien werden standardmäßig mitgeliefert:

- **`allowlists.md`** — die Reichweitenregeln. Drei Listen:
  1. *Datei-Lese-Präfixe:* absolute Pfade, die deine Readvisors außerhalb des Projekts lesen dürfen (Standard: `~/enough/`).
  2. *Datei-Lese-Schreib-Präfixe:* Pfade, in die sie außerhalb des Projekts auch schreiben dürfen. Diese Liste kommt **leer**: von Haus aus wird nichts außerhalb deines Projekts geschrieben, und das bleibt so, bis du bewusst einen Pfad hinzufügst.
  3. *Internet-Domains:* Hosts, die direkt abgerufen werden (die Vorgaben umfassen `gutenberg.org`, `en.wikipedia.org`, `en.wikisource.org`, `archive.org`, `standardebooks.org` und den Download-Host von Kiwix). Eine Domain, die nicht auf der Liste steht, ist nicht blockiert — der Abruf wird stattdessen über einen lokalen Tor-Proxy geleitet, damit eine spontane Recherche deine Adresse nicht in irgendwelchen Server-Logs hinterlässt. Ein Broker-Schalter kann diesen Rückfallweg abschalten, sodass Abrufe außerhalb der Liste rundheraus scheitern.
- **`context-management.md`** — wie ein sich füllendes Kontextfenster bemerkt wird, und wie man sauber daraus zurücksetzt, ohne den Zustand zu verlieren (Abschnitt 8.3).
- **`requests.md`** — wann und wie lang laufende Arbeit als Anfrage-Dateien verfolgt wird (Abschnitt 8.3).
- **`profile-maintenance.md`** — was ins Projektprofil gehört und was nicht (Abschnitt 8.1).

Richtlinien sind wie alles andere aus den Defaults verlinkt, du kannst die Positivliste also global verschärfen oder sie für ein Projekt anpassen, das eine lockerere (oder strengere) Reichweite braucht. `allowlists.md` zu bearbeiten ist in der Praxis die mit Abstand häufigste Anpassung: die Doku-Seiten hinzufügen, denen du vertraust, einen gemeinsamen Ordner hinzufügen, in den deine Readvisors schreiben können sollen, und weiter geht's mit deinem Tag.

---

## 6. Lese-/Bearbeitungsmodus

Klick eine beliebige Datei im Baum an, und sie öffnet im einheitlichen Lese-/Bearbeitungsmodus: ein Modus mit zwei *Seiten* — einer **Leseseite** (das Auge) zum Durchsehen, einer **Bearbeitungsseite** (der Stift) zum Ändern von Text.

### 6.1 Voll vs. Mini, und zwischen allem wechseln

Lesen/Bearbeiten kommt in zwei Größen. **Mini** ist ein Seitenpanel neben dem Chat: ein Referenzdokument griffbereit halten, während du dich unterhältst. (Das Mini-Panel lässt die Review-Werkzeugleiste bewusst weg — es ist zum Lesen und für schnelle Änderungen da, nicht zum Markieren.) **Voll** nimmt den ganzen Rahmen ein, für lange Dokumente und ernsthaftes Bearbeiten.

Größe wechseln über den Mini↔Voll-Button im Panel-Rahmen. Seite wechseln über den Seiten-Umschalter daneben. ⌘S speichert auf der Bearbeitungsseite. Wenn das, was du ansiehst, der Zwilling eines konvertierten Dokuments ist, nennt der Rahmen auch das Original und trägt einen **Export**-Button, um deine Änderungen dorthin zurückzuschreiben (Abschnitt 7.5). Und alles ist schmutz-gesichert: hast du ungespeicherte Änderungen, fragt enough nach, bevor irgendetwas sie verwirft — zu einer anderen Datei navigieren, den Modus schließen, zu einem anderen Dokument springen. Du wirst keine Stunde Arbeit an einen verirrten Klick verlieren.

Während ein Dokument offen ist, erscheinen drei Zähler in der oberen Leiste und halten mit deinem Tippen Schritt: **¶** Absätze, **W** Wörter, **C** Zeichen. (Die Listenansicht des Startbildschirms zeigt dir dieselben drei Summen für ein ganzes Projekt — Abschnitt 2.1.) Wird das Fenster schmal, behalten die Buttons und die Modus-Anzeigen ihre Plätze: zuerst wird der Projektname kürzer, bis auf etwa zehn Zeichen, und erst dann treten die Zähler ab, von rechts nach links.

Wie jeder Vollbild-Modus zeigt Lesen/Bearbeiten sein Symbol im Indikatorbereich oben rechts, mit einem kleinen rot-x-Band dran zum Schließen (Abschnitt 14).

### 6.2 Markieren

In der Leseseite jedes Markdown-Dokuments Text auswählen und in einer von vier Farben einfärben — **gelb, grün, blau, pink** — über die Werkzeugleiste oder das Popup, das über einer Auswahl erscheint. Dieselbe Werkzeugleiste bietet leichte Formatierung: fett, kursiv, unterstrichen (⌘B / ⌘I / ⌘U).

Markierungen sind dauerhaft, und sie leben außerhalb des Textstroms: jedes Dokument bekommt eine verborgene Begleitdatei (`.<dateiname>.highlights.json`) statt Markup, das in deinen Text gespleißt wird, sodass das Dokument selbst sauber bleibt. Ein farbiges Band am Rand markiert jede markierte Zeile. Markierungen überstehen Sitzungen, und überlappende Farben stapeln sich.

Und hier kommt der Teil, der ändert, wie du arbeitest: deine Readvisors können sie sehen. Das `read_highlights`-Tool listet jede Markierung in einem Dokument nach Farbe auf, und `navigate_to_highlight` springt die Ansicht zu einer davon. Das macht Markieren zu einem Kanal. Färb die vier Absätze, die umgeschrieben werden sollen, gelb, und die zwei, die du liebst, grün, dann sag „schreib die gelben Teile um; behalt den Ton der grünen.“ Erwähnst du eine Farbe, weiß dein Readvisor, dass du deine Markierungen meinst.

### 6.3 Unterstützte Dateitypen

- **Markdown (`.md`)** rendert formatiert in der Leseseite und als Quelltext in der Bearbeitungsseite. Markdown ist enoughs Muttersprache — fast alles, was das System selbst schreibt, ist Markdown.
- **Klartext**, und alles Textartige, öffnet in Lesen/Bearbeiten als Text.
- **`.girraph`**-Dateien öffnen stattdessen im girraph-Modus (Abschnitt 20).
- **`.merirmaid`**-Dateien öffnen stattdessen im merirmaid-Modus (Abschnitt 21).
- **Gespeicherte Wikipedia-Artikel** (`article.html` in einem `wiki/`-Ordner) öffnen im wikisink-Reader in voller Wiedergabetreue (Abschnitt 11.2).
- **Word-Dokumente, PDFs, E-Books, Präsentationen, Arbeitsmappen** öffnen als bearbeitbarer Markdown-**Zwilling** — eine Zeile im Baum, ein Klick, und ein **Export**-Button im Rahmen, um deine Änderungen zurückzuschreiben. Das ist Abschnitt 7, und das ist die ganze Geschichte.
- **Bilder** (`.png`, `.jpg`, `.gif`, `.webp`, `.bmp`, `.svg`) öffnen in einem schlichten Betrachter (Abschnitt 7.9). Bilder *innerhalb* eines Dokuments rendern in der Leseseite wie jedes andere Bild in Markdown.

enough ist immer noch ein Textsystem, und es bleibt eines: es rendert Markdown, kein Seitenlayout. Was es mit allem anderen macht, ist es zu konvertieren — verlustarm genug, um darin zu arbeiten, ehrlich genug, um dir zu sagen, was nicht überlebt hat.

---

## 7. Arbeiten mit PDFs, Word-Dokumenten und anderen Dateien

enough rendert kein PDF, layoutet kein Word-Dokument und zeichnet keine Tabelle, und es tut auch nicht so. Was es stattdessen macht, ist leiser und für die Art Arbeit, die du hier machst, nützlicher: es konvertiert das Dokument in Markdown, das du wirklich lesen, bearbeiten, markieren und deinen Readvisors übergeben kannst — und es hält dieses Markdown an das Original gebunden, sodass deine Änderungen zurückgehen können.

Nichts daran ist ein eigener Modus oder eine eigene App. Du klickst die Datei an. Sie öffnet.

### 7.1 Der Zwilling

Öffne `memo.docx`, und enough schreibt `memo.docx.md` daneben. Diese zweite Datei ist der **Zwilling**: eine schlichte Markdown-Kopie des Dokuments, in deinem Projektordner, deine zum Bearbeiten wie alles andere. Sie zu erzeugen verändert nie das Original.

Im Dateibaum siehst du weiterhin eine Zeile — `memo.docx`. Der Zwilling, der Ordner mit den aus dem Dokument gelösten Bildern (`memo.docx.assets/`) und eine kleine verborgene Datei, die festhält, was aus was konvertiert wurde, sind alle in diese eine Zeile eingefaltet, sodass dein Projekt weiterhin so aussieht wie im Finder. Klick die Zeile an, und der Zwilling öffnet im Lese-/Bearbeitungsmodus (Abschnitt 6) mit allem, was dieser Modus gibt: zwei Seiten, ⌘S, der Schmutz-Schutz — und, sobald du ins Vollbild gehst, Markierungen.

Zwei Folgen, die zu kennen sich lohnt. Die Benennung kann nicht kollidieren: ein `memo.md`, das du selbst geschrieben hast, ist eine andere Datei als `memo.docx.md`, und enough verwechselt sie nie. Und löschst du `memo.docx` im Finder, bricht nichts — der Zwilling wird still zu einer gewöhnlichen Markdown-Datei in deinem Baum, was er ohnehin schon immer war.

Deine Readvisors sehen dasselbe wie du. Bitte darum, `report.pdf` zu lesen, und sie bekommen den Zwilling, wobei nötigenfalls erst einer konvertiert wird; bitte darum, etwas zu ändern, und sie bearbeiten den Zwilling, genau dort, wo auch deine eigenen Änderungen hingehen.

### 7.2 Was enough auf diese Weise öffnen kann

Diese Liste stammt aus der App selbst statt aus Fließtext, den irgendjemand aktuell halten muss — liest du das außerhalb von enough, öffne das Hilfe-Center in der App (Abschnitt 10), um sie ausgefüllt zu sehen:

{{convert-formats}}

### 7.3 Das Abzeichen im Baum

Jedes konvertierbare Dokument trägt ein kleines Abzeichen am rechten Rand seiner Zeile, und das Abzeichen hat genau eine Aufgabe: dir zu sagen, ob die beiden Hälften noch übereinstimmen.

- **Still** — konvertiert, und beide Seiten stimmen überein. Nichts zu tun.
- **Leuchtend, in deiner Farbe** — du hast den Zwilling bearbeitet. Diese Änderungen sind im Markdown und noch nicht im Original; exportieren, wenn du bereit bist (Abschnitt 7.5).
- **Leuchtend, in der Farbe deines Readvisors** — das Original hat sich außerhalb von enough geändert, seit es konvertiert wurde. Jemand hat es in Word bearbeitet; eine neue Kopie ist darübergelandet; es kam von einem gemeinsamen Laufwerk herunter.
- **Leuchtend, in der Fehlerfarbe** — beides zugleich. Das ist der einzige Fall, bei dem enough nachfragt, und das tut es auch (Abschnitt 7.7).
- **Hohl** — konvertierbar, noch nicht konvertiert. Anklicken, und es konvertiert.
- **Hohl, und ein Klick erklärt ein Extra** — ein PDF, eine Präsentation oder eine Arbeitsmappe auf einer Installation, die die noch nicht lesen kann (Abschnitt 7.8).

Über dem Abzeichen schweben, für dasselbe in einem Satz. Das Abzeichen anzuklicken tut genau das, was das Anklicken des Dateinamens tut.

### 7.4 Beim ersten Öffnen

Beim ersten Öffnen jedes Dokument-*Typs* erklärt ein kurzes Modal, was gleich passiert — was ein Zwilling ist, wohin er geht, dass das Original bleibt, wo es ist. Ein OK-Button. Das ist einmal pro Typ, nicht einmal pro Datei: dein zweites Word-Dokument öffnet einfach.

Die Konvertierung eines Office-Dokuments ist schnell, deutlich unter einer Sekunde für alles Typische. Du siehst währenddessen einen kleinen Toast in der Ecke, mit einem **Abbrechen**-Button bei den langsamen. PDFs dauern länger und bekommen einen ehrlichen Fortschrittsbalken (Abschnitt 7.8).

### 7.5 Deine Änderungen zurückexportieren

Ein offener Zwilling trägt einen **Export**-Button in seinem Rahmen. Ein Modal, drei Entscheidungen:

**Welches Format.** Das eigene Format des Originals ist vorausgewählt, und die übrigen Exportziele sind auch da — ein Word-Dokument kann als PDF, EPUB oder eigenständige HTML-Seite hinausgehen. Alles, was das Format nicht kann, wird grau mit dem Grund gezeigt, nie still weggelassen.

**Eine Kopie, oder das Original.** Die Vorgabe ist eine **datierte Kopie**, neben das Original geschrieben — `memo-2026-08-19-1042.docx` — und der genaue Dateiname wird im Modal angezeigt, bevor du bestätigst. Nichts steht auf dem Spiel: du bekommst eine neue Datei, die alte bleibt unangetastet. Die zweite Option überschreibt das Original an Ort und Stelle, und sie wird nur angeboten, wenn das Zielformat des Exports das eigene Format des Originals ist. Wählst du sie, bietet dir enough danach ein **Rückgängig**: die neue Datei behalten, oder die alten Bytes zurücklegen, Byte für Byte.

**Ob es ab jetzt synchron gehalten werden soll** — Abschnitt 7.6.

Ein Wort dazu, was die Reise übersteht. Das Überschreiben einer `.docx` oder `.odt` nutzt das Original als Stil-Referenz, sodass Seitengröße, Schriften und etwaige lebende Kopf- und Fußzeilen mit deinem Text zurückkommen — Dinge, die Markdown nicht ausdrücken kann und die sonst verloren gingen. Was Markdown wirklich nicht tragen kann, kommt nicht zurück: nachverfolgte Änderungen und Kommentare (beim Hereinkommen akzeptiert und fallengelassen), Textboxen, Felder, genaue Bildgrößen. Diese Asymmetrie ist, warum die datierte Kopie die Vorgabe ist, und warum enough ein Original nie aus eigenem Antrieb neu schreibt.

### 7.6 Das Original synchron halten

Hak **das Original synchron halten** im Export-Modal an, und jedes Speichern des Zwillings schreibt still auch das Original neu. Bearbeite in enough, und die `.docx` auf deiner Festplatte ist aktuell, wann immer ein Kollege danach fragt. Es ist eine Einstellung pro Datei, sie greift in dem Moment, in dem du sie ankreuzt, und eine kleine Bestätigung erscheint jedes Mal, wenn ein Speichern durchgeht.

Es wird für die Formate angeboten, die sich zurückschreiben lassen — Word, OpenDocument, Rich Text, EPUB; die Spalte „synchron halten“ in Abschnitt 7.2 hat das letzte Wort. PDFs können nicht mitmachen, und der Grund ist es wert, klar ausgesprochen zu werden: enough kann ein PDF aus Markdown *schreiben*, aber es setzt das Dokument von Grund auf neu. Ein synchronisiertes PDF würde dein sorgfältig gestaltetes Original bei jedem Speichern durch einen schlichten Neusatz seiner Worte ersetzen. Das ist kein Sync, das ist ein Abriss, also wird es nicht angeboten.

### 7.7 Wenn sich beide Seiten geändert haben

Das Original kann sich ohne dich weiterbewegen. Du bearbeitest den Zwilling hier; jemand bearbeitet die `.docx` in Word; jetzt gibt es zwei Versionen der Wahrheit.

enough bemerkt das. Es vergleicht das Original mit dem, was es zum Zeitpunkt der Konvertierung festgehalten hat, in jedem Moment, der zählt — wenn der Baum gezeichnet wird, wenn du das Dokument öffnest, wenn du speicherst, wenn du exportierst — und eine Datei, die nur *angefasst* wurde (kopiert, gesichert, geöffnet und geschlossen), zählt nicht: die Prüfung liest Inhalte, nicht nur Zeitstempel.

Haben sich beide Seiten wirklich geändert, bekommst du ein Modal mit drei Möglichkeiten in klaren Worten:

- **Meinen Zwilling behalten.** Es wird nichts geschrieben. Das Abzeichen geht zurück zu „du hast es geändert“, und du entscheidest später.
- **Über das Original exportieren.** Dein Markdown gewinnt; das Original wird neu geschrieben, mit einem Rückgängig wie üblich.
- **Vom Original neu konvertieren.** Das Original gewinnt; ein frischer Zwilling wird geschrieben — und dein alter Zwilling wird daneben als Rückgängig-Datei aufbewahrt statt gelöscht.

Keine Wahl in diesem Modal zerstört etwas, das du nicht zurückbekommen kannst. Das ist die Design-Regel, auf der die ganze Funktion aufgebaut ist.

### 7.8 PDFs, Präsentationen und Arbeitsmappen lesen: das PDF-Extra

Ein PDF zu lesen ist ein schwierigeres Problem als eine Word-Datei zu lesen. Eine `.docx` weiß immer noch, was eine Überschrift ist; ein PDF weiß nur, wohin die Tinte ging, und eine Tabelle, ein zweispaltiges Layout oder einen Scan wieder herauszuholen, braucht echte Dokumentmodelle. Diese Modelle sind groß, also sind sie nicht in der Basisinstallation — stattdessen sind sie einen Klick entfernt: **⚙ UI-Fenster → Extras → PDF-Extra installieren**.

Was es ehrlich kostet:

- rund **250 MB Download**, und rund **1 GB auf der Platte** nach der Installation;
- dazu etwa **0,7 GB Modellgewichte**, einmalig geholt und in `~/enough/weights/docling/` behalten;
- ein paar Minuten, das meiste davon Download. Der Installer streamt sein Log ins Fenster, damit du zuschauen kannst, und die Engines schalten sich live ein — kein Neustart.

Was du bekommst: **PDFs**, auch gescannte (der Text wird per OCR aus den Pixeln gelesen); **PowerPoint-Präsentationen**, deren Folien zu Abschnitten mit Überschrift werden; und **Excel-Arbeitsmappen**, deren Tabellenblätter zu Markdown-Tabellen werden.

Geschwindigkeit, gemessen statt geschätzt, auf Apple Silicon: etwa **0,9 Sekunden pro Seite** für ein digitales PDF, dazu ein einmaliges **~10-sekündiges** Modell-Laden pro Konvertierung. Ein einseitiges PDF dauert also etwa zehn Sekunden, ein hundertseitiges Buch etwa anderthalb Minuten, und eine Präsentation oder Arbeitsmappe ein paar Sekunden. Lange Konvertierungen zeigen Fortschritt und lassen sich abbrechen; Abbrechen hinterlässt nichts — kein halb geschriebener Zwilling, keine verirrten Ordner.

Zwei Dinge ersparen dir später einen ratlosen Moment. Erstens: **PDFs schreiben braucht nichts davon.** Jeder Zwilling exportiert auf jeder Installation zu PDF, mit oder ohne Extra, weil der Schriftsetzer dafür mit enough mitkommt. Das Extra ist zum *Lesen*. Zweitens: erscheint die Meldung „braucht ein Extra“ auf einem Rechner, auf dem du sicher bist, es installiert zu haben, lies genau, welchen Satz du bekommen hast — die Pakete und die Modellgewichte sind zwei getrennte Downloads, und eine Verbindung, die mitten im Abruf abgebrochen ist, kann dir den ersten ohne den zweiten hinterlassen. Die Installation erneut laufen zu lassen, beendet den Job und lädt nichts neu herunter, das du schon hast.

Updates behalten das Extra. `update-enough.command` (und `/update-enough`) merken sich, was du installiert hast, und fragen bei jedem Sync erneut danach, sodass ein Routine-Update PDF-Lesen nie still wieder wegnimmt.

### 7.9 Bilder, und einen Blick aufs Original werfen

Klick ein Bild an, und es öffnet in einem schlichten Betrachter: standardmäßig auf Breite eingepasst, anklicken zum Wechsel auf tatsächliche Größe und Herumscrollen, ein Schachbrettmuster hinter allem Transparenten, und Name, Pixelmaße und Dateigröße im Kopfbereich. Er ist nur lesbar. enough ist kein Bildeditor und hat dort keine Ambitionen.

Bilder *innerhalb* eines Dokuments sind eine andere Sache, und sie kommen mit herüber: das Foto in deiner Word-Datei wird nach `memo.docx.assets/` extrahiert und rendert in der Leseseite des Zwillings genau wie jedes andere Markdown-Bild.

Und wenn der Zwilling nicht reicht, trägt der Rahmen eines PDFs **Original ansehen**: er öffnet das tatsächliche PDF im Panel, sodass du den Zwilling gegen die echte Seite prüfen kannst. Schließen, und du bist zurück im Zwilling, wo du aufgehört hast.

### 7.10 Was Konvertierung dich kostet, in zwei Sätzen

Zwei Grenzen sind es wert, laut benannt zu werden, statt dich sie entdecken zu lassen. Die Tabellenblätter einer Arbeitsmappe kommen als Tabellen Rücken an Rücken an, **ohne Blattname-Überschriften** — der Reader gibt sie nicht aus, und enough lässt lieber eine Lücke, als eine Bezeichnung zu erfinden. Und ein aus einem PDF gezogenes Bild bekommt jedes Mal den Alt-Text „Image“: es gibt keine Bildunterschrift in der Datei, um ihm eine bessere zu geben.

Darüber hinaus das stehende Versprechen: **deine Originale werden nie verändert, außer du verlangst es.** Konvertieren schreibt immer nur neue Dateien daneben. Export-Überschreiben ist der einzige Weg, der ein Original anfasst, er braucht einen bewussten Klick, und er hinterlässt dir ein Rückgängig.

---

## 8. Der Projektordner und `rness/`

Ein Projekt ist ein Ordner. Jeder beliebige Ordner. enough fügt ihm genau eine Sache hinzu: `rness/`, das externalisierte Gehirn für dieses Projekt. Alles, was deine Readvisors hier sind, wissen und sich merken, lebt in diesem Ordner als gewöhnliche Dateien. Du kannst alles davon lesen, alles davon bearbeiten, und es unter git stellen, falls das deine Gewohnheit ist.

Der Aufbau:

```
your-project/
  rness/
    AGENT.md            who your chief readvisor is    (5.3)
    MOTIVATION.md       why they work                  (5.3)
    active-paradigm     which paradigm is in force     (16)
    paradigms/          available reasoning frameworks (16)
    skills/             available skills               (19)
    readvisors/         the readvisors you can turn on (17)
    policies/           the hard rules                 (5.4)
    composure-forms/    composure forms you saved      (4.5)
    knowledge/          project memory                 (8.1)
      councils/         exported council transcripts   (18)
    io/                 input/output workspace          (8.2)
      composure/        where new composures land       (4.7)
    requests/           long-running work tracking      (8.3)
  ...your actual files...
```

Zwei davon kommen erst, wenn du sie brauchst: `composure-forms/` beim ersten Mal, wenn du eine Composure als Form speicherst, `knowledge/councils/` beim ersten Mal, wenn ein Rat abschließt. Ein leerer Ordner, der sich nie erklärt, ist ein Ordner, nach dem man am Ende fragt.

**Ist dieses Projekt älter als 0.3.5**, hat es einen Ordner `rness/roles/` statt `rness/readvisors/`. enough benennt ihn beim nächsten Öffnen des Projekts um, in einem Zug, und trägt deine projektlokalen Readvisors und deine Ein/Aus-Einstellungen unversehrt hinüber. Geht das nicht — eine schreibgeschützte Platte, ein Ordner, an dem etwas anderes hängt —, bricht nichts: alles läuft unter dem alten Namen weiter, und beim nächsten Start wird es erneut versucht.

Verlinkte Einträge (kursiv im Baum) folgen den globalen Defaults; jeden davon anpassen, um eine lokale Kopie abzuzweigen (Abschnitt 3.1). Dateien, die du auf beliebige Weise ins Projekt legst — Finder, ein anderer Editor, ein Readvisor — sind beim nächsten Zug für alle gleichermaßen sichtbar.

Ein konvertiertes Dokument (Abschnitt 7) fügt auch hier Dateien hinzu, immer neben dem Original und immer nach ihm benannt: `memo.docx` bekommt einen Zwilling unter `memo.docx.md`, seine Bilder in `memo.docx.assets/`, und eine verborgene `.memo.docx.convert.json`, die festhält, was wann aus was konvertiert wurde. Der Baum faltet alle drei in die Zeile des Originals, aber es sind gewöhnliche Dateien auf deiner Platte — du kannst das Paar auf einen anderen Rechner kopieren, unter git stellen, oder den Zwilling löschen und das Original nochmal anklicken, um einen frischen zu bekommen. Das verborgene Manifest ist enoughs Buchhaltung; lass es in Ruhe, und es bleibt korrekt. Lösch es, und enough behandelt das Dokument einfach so, als wäre es nie konvertiert worden.

### 8.1 Der Wissen-Ordner

`rness/knowledge/` ist projektbezogenes Gedächtnis.

**`project-profile.md`** ist die nützlichste Datei im Ordner. Ihr Inhalt wird bei jedem Zug in den System-Prompt eingespeist: was auch immer hier steht, ist im Arbeitsgedächtnis deines Chef-Readvisors, kein Nachschlagen nötig. Er pflegt sie, während ihr arbeitet — beobachtete Vorlieben, wiederkehrende Dateien und Personen, übernommene Konventionen, offen gelassene Fäden — und du kannst sie direkt bearbeiten. Eine stehende Vorliebe einmal im Profil festhalten, statt sie jede Sitzung zu wiederholen. Die profile-maintenance-Richtlinie hält die Datei diszipliniert: konkrete Beobachtungen statt vager Etiketten, Destillat statt Archiv.

**`session-logs/`** enthält ein datiertes Markdown-Protokoll der Züge jeder Sitzung, plus das Journal des Brokers (Abschnitt 9). Nur anhängende Historie. Durchstöbere sie, oder grep sie, wenn du rekonstruieren musst, was letzten Dienstag passiert ist.

Über diese beiden hinaus gehört der Ordner dir. Füg einen `glossary/`-Unterordner hinzu, eine Lessons-Learned-Datei, Hintergrundnotizen — deine Readvisors können alles zurate ziehen, was du hier ablegst.

### 8.2 Der io-Ordner

`rness/io/` ist der Durchgangs-Arbeitsbereich:

- **`input/`** — Dateien hier ablegen, damit sie verarbeitet werden. Abgerufene Webseiten landen auch automatisch hier, zu Markdown konvertiert und zwischengespeichert, sodass eine einmal abgerufene Seite für immer als Grundlage verfügbar bleibt.
- **`output/`** — wo erzeugte Artefakte landen. Sichten, behalten, was gut ist, den Rest löschen.
- **`cloud-cache/`** — nutzt du den Cloud-Modell-Slot, wird jeder Cloud-Austausch hier festgehalten (Abschnitt 15.2). Selbst Cloud-Arbeit hinterlässt eine lokale, mit grep durchsuchbare Papierspur.

### 8.3 Anfragen: wie lange Aufgaben überleben

Dieser Punkt schafft es selten in die Schnelleinstieg-Touren, aber er ist der Mechanismus, der Arbeit über mehrere Sitzungen hinweg möglich macht, also sind zwei Minuten gut investiert.

Bittest du um etwas, das mehr als ein, zwei Züge dauert, öffnet sich eine **Anfrage-Datei** in `rness/requests/`: ein Markdown-Protokoll des Ziels, der Fortschritts-Checkpoints und der unterwegs getroffenen Entscheidungen. Darum musst du nicht extra bitten. Die Form einer Aufgabe zu erkennen, ist die Aufgabe deines Chef-Readvisors.

Die Anfrage-Datei zählt, weil Kontextfenster sich füllen. enough beobachtet den Gesprächsdruck, und — gemäß der context-management-Richtlinie — checkpointet dein Chef-Readvisor seinen Zustand in die aktive Anfrage-Datei, bevor es überläuft. Je nach deiner Orchestrator-Einstellung setzt enough dann entweder automatisch zurück (löscht das Gespräch im Arbeitsspeicher und setzt frisch vom Checkpoint fort) oder pausiert mit einem Banner, damit du zurücksetzen kannst, wenn du bereit bist. So oder so ist das Dateisystem das eigentliche Gedächtnis, nicht das Gespräch: eine frische Sitzung liest den Continuation-Block der Anfrage-Datei und macht dort weiter, wo der Stand war.

Erledigte Anfragen wandern nach `rness/requests/done/` — klick **erledigt markieren** bei einer offenen Anfrage, oder sag es im Panel. Der done-Ordner ist für deine Readvisors schreibgeschützt, und er dient zugleich als ehrliches Journal von allem, was ihr beide tatsächlich abgeliefert habt.

---

## 9. Das Broker-Fenster

Der Broker ist enoughs Vertrauensanker. Jeder Tool-Aufruf, den deine Readvisors machen — jedes Dateilesen, Dateischreiben, jeder Shell-Befehl und Web-Abruf — läuft durch ihn hindurch. Das 🔀-Broker-Fenster ist, wo du das beobachtest und einstellst.

Dreizehn Schalter, in Gruppen:

| Schalter | Was er steuert |
|---|---|
| trace log | ob der Broker sein Journal überhaupt schreibt |
| local models only | ob der Cloud-Slot (OPRO-API) in der Modellauswahl überhaupt angeboten wird |
| read_file / write_file / shell brokered | Protokollierung pro Tool, je ein Schalter — drei insgesamt (die Positivlisten gelten *immer*, unabhängig davon) |
| fetch_url enabled | ob das Web-Abruf-Tool überhaupt funktioniert |
| Tor for off-list fetches | Domains außerhalb der Positivliste: über Tor leiten (an) oder verweigern (aus) |
| cache & convert fetches | abgerufene Seiten zu Markdown konvertieren und in `rness/io/input/` zwischenspeichern |
| wikisink tools | ob die vier Wiki-Tools deiner Readvisors funktionieren (dein eigenes 🚰-Browsen wird nie gesperrt) |
| wikisink live updates | ob Update-Läufe überhaupt Wikipedia kontaktieren dürfen (aus = Bericht nur aus lokalem Zustand) |
| cacheawl tools | ob die Cachebox-Tools deiner Readvisors funktionieren (dein eigener cacheawl-Modus wird nie gesperrt) |
| composure tools | ob deine Readvisors Composures lesen und bearbeiten dürfen (deine eigene Leinwand wird nie gesperrt — Abschnitt 4.9) |
| forge new readvisors | ob der `readvisory`-Skill einen fertigen Readvisor für dich installieren darf (Abschnitt 19.6). Aus lässt das Befragen und das Entwerfen zu und überlässt dir das Ablegen |

Die Kopfzeile des Fensters trägt außerdem den einen Button in enough, der ändert, wie jemand heißt: **Chef-Readvisor umbenennen**. Er öffnet ein kleines Feld, nimmt ein bis vierundzwanzig Zeichen, und der neue Name steht in der Signatur des nächsten Dings, das dein Chef sagt. Es ist eine rechnerweite Einstellung, wie das Thema — ein Chef, ein Name, überall. Eine Historie gibt es dazu nicht: die Signatur ist immer der aktuelle Name, denn eine Umbenennung, die durch dein Protokoll zurückgriffe, läse sich, als wären zwei verschiedene Personen im Raum gewesen.

Standardmäßig ist alles an: die Defaults vertrauen deinen Readvisors das Projekt an und halten sie mit einer Papierspur ehrlich. Diese Spur — das **Trace-Journal** — landet in `rness/knowledge/session-logs/<datum>-broker.md`: Zeitstempel, Tool, Entscheidung, Argumente, Ergebnis, für jeden vermittelten Aufruf. Und blockiert ein Schalter oder eine Positivliste etwas, bekommt der Readvisor eine klare Ablehnungsmeldung, die sagt, was blockiert wurde und warum, sodass er es dir sagen kann, statt still zu scheitern.

Beachte das Design-Prinzip in dieser Tabelle: Schalter, die die Tools deiner Readvisors sperren, sperren nie *deine* Oberfläche. cacheawl tools auszuschalten schließt dich nicht aus dem cacheawl-Modus aus. Es heißt, dass nichts in deinem Namen in den Speicher greifen kann.

---

## 10. Das UI-Fenster und die Hilfedokumente

Der ⚙-UI-Button öffnet die Anzeigeeinstellungen und das Referenzmaterial. Ein kleiner **Hilfe**-Button sitzt oben rechts in diesem Fenster, neben dem ×: er öffnet dieses Handbuch nur lesbar, in der App, als Vollbild-Modus wie jeder andere (Abschnitt 14). Daneben sitzt **Wörterbuch**, das FEED öffnet, enoughs eigenes englisches Wörterbuch (Abschnitt 13).

**Das Handbuch lesen.** Die Werkzeugleiste des Handbuchs hat einen **Inhalt**-Button: eine Liste aller nummerierten Abschnitte und Unterabschnitte, neben dem Text, wenn Platz dafür ist, und eingeklappt, wenn nicht (etwa in der schmalen Seitenpanel-Größe), wobei der Abschnitt, den du gerade liest, beim Scrollen markiert wird. **suchen**, oder ⌘F, solange das Handbuch oben liegt, öffnet eine Suchleiste: jeder Treffer wird an Ort und Stelle markiert, mit einer Zählung neben dem Feld, Return und shift-Return laufen sie ab, und Esc schließt sie. Und überall, wo dieses Handbuch „Abschnitt 7.3“ sagt, sind diese Worte ein Link, der dich dorthin bringt. Jeder Sprung — ein Klick im Inhalt, ein Abschnittslink, eine Suche, die dich weit weggetragen hat — hinterlässt eine kleine **↩ zurück, wo du warst**-Pille, und ein Klick bringt dich zurück an die Stelle, an der du gelesen hast.

Der Weg hinaus reitet jetzt auf der Titelleiste mit: **Projekt schließen → Start**, oben neben dem Hilfe-Button, das diese Sitzung beendet und dich zum Startbildschirm zurückbringt (Abschnitt 2.5). Es fragt, bevor es das tut, und es vermerkt, was es nicht tut — der Ordner auf der Festplatte bleibt unangetastet. In der App würdest du eher zu ⌘W greifen; dieser Button ist dasselbe, und er ist der *einzige*, wenn du enough im Browser laufen lässt. (Er ist nicht auf dem Startbildschirm selbst da, wo es kein Projekt zum Schließen gibt.)

Es enthält auch das eine Ding in enough, das du aus enough heraus installieren kannst: die **Extras**-Zeile für **PDF-Lesen** (Abschnitt 7.8). Die Zeile sagt, wo du stehst — nicht installiert, wird installiert, installiert, oder installiert, aber nicht fertig — und der Installieren-Button streamt sein ganzes Log ins Fenster, während er läuft, sodass ein langer Download etwas ist, dem du zusehen kannst, statt es nur abzuwarten. Ist er fertig, fangen PDFs an zu öffnen; nichts muss neu gestartet werden.

### 10.1 Themen

Vier werden mit enough mitgeliefert: **Enough Default** (tiefes Blauviolett-Dunkel), **Pastel** (blasses Papier, im Geiste des Terminal-Farbschemas „Man Page“), **Wireframe** und **Darknest**. Der Wechsel geschieht sofort, und jedes Symbol in der Oberfläche leitet seine helle oder dunkle Variante spontan neu ab.

Themen sind nicht fest verdrahtet. Sie leben in `~/enough/config/ui.json` als benannte Blöcke von Farbwerten, jeder als CSS Custom Property angewendet. Einen bestehenden Block kopieren, umbenennen, die Farben ändern, neu laden: dein Thema ist im Dropdown. Der `_doc`-Block oben in der Datei erklärt jeden Schlüssel.

### 10.2 Schriften

Dasselbe Muster. Vier mitgelieferte Stacks — SF Mono, System-Sans-Serif, Georgia Serif, Courier — und eigene Ergänzungen sind willkommen, in derselben `ui.json`. Für die Größe siehe die beiden Regler unten (Abschnitt 10.3) — und in einem Browser-Tab funktioniert obendrauf immer noch ganz gewöhnlicher Browser-Zoom (⌘+ / ⌘−).

### 10.3 Größe — UI-Größe und Textgröße

Browser-Zoom war hier immer die Antwort, bis die Desktop-App ohne einen Browser drumherum ankam. Also wuchs enough sich einen eigenen, und nutzte die Gelegenheit, es noch etwas besser zu machen: zwei Regler statt einem, in der Zeile unter dem Thema.

**UI-Größe** skaliert *alles* — Symbole, Beschriftungen, die Seitenleiste, den Chat, genau dieses Fenster — in Schritten von 0,1×. **Textgröße** skaliert nur das Dokument vor dir: die Seite in Lesen/Bearbeiten, einen wikisink-Artikel, die Dateivorschau, dieses Handbuch in seinem Referenzmodus. Sie multiplizieren sich, und sie stören sich nicht: eine 0,9×-Oberfläche um 1,5×-Text herum ist ein durchaus guter Weg, ein Manuskript zu lesen, und umgekehrt ein durchaus guter Weg, eines aus dem Weg deines Nachmittags zu schrumpfen. Auf eine der beiden Zahlen klicken, um diesen Regler auf 1,0× zurückschnappen zu lassen und den anderen in Ruhe zu lassen.

Beide werden **pro Projektordner** gemerkt — das Manuskript, das du quer durchs Zimmer liest, und die Notizen, die du am Schreibtisch führst, halten jeweils ihre eigenen Größen, und keine zieht die andere mit. Der Startbildschirm bleibt bei schlichter Größe, die Regler erscheinen dort also nicht.

Die Grenzen atmen mit deinem Bildschirm: grob 0,5× bis 2× auf heutigen Displays, enger in einem kleinen Fenster, damit die Oberfläche immer genug Raum behält, um sie selbst zu sein, weiter auf sehr großen, sehr dichten Bildschirmen (die 8K-Wand von 2046 bekommt 3×). Würde ein Schritt die Grenze überschreiten, wackelt der Button, die Zahl pulsiert rot, und nichts ändert sich — das ist die ganze Fehlermeldung.

### 10.4 Sprachen

Die Oberfläche spricht sechs: Englisch, Französisch, Spanisch, Deutsch, Chinesisch und Japanisch. Das Dropdown **UI-Sprache** in derselben Zeile schaltet alles um, was du gerade siehst — Beschriftungen, Tooltips, die `(?)`-Blasen, dieses Handbuch — live, ohne Neustart. Die Wahl gilt rechnerweit, sie reitet auf `ui.json` genau wie das Thema, sodass der Start und jedes Projekt sich darüber einig sind.

Was sie bewusst *nicht* anfasst: deine Dateien, deinen Chat, deine Readvisors. Sprich mit ihnen in welcher Sprache auch immer dir zusagt — die lokalen Modelle sind in allen sechs sicher unterwegs —, aber enough hält sein eigenes Gerüst (Skills, Paradigmen, Prompts, Projektdateien) auf Englisch, weil das die Sprache ist, die die Modelle am zuverlässigsten lesen. Ein paar erzeugte Dinge bleiben ebenfalls Englisch — Listen, live aus dem gezogen, was auf *deinem* Rechner installiert ist, wie die Skills in einer Blase oder die Dateiformat-Tabelle. Und überall, wo eine Übersetzung mit einer neuen englischen Beschriftung nicht mitgekommen ist, siehst du das Englische statt einer Leerstelle: weniger hübsch, nie kaputt. Eine entdeckt? Das ist ein Fehler — [enough.support](https://enough.support) freut sich darüber.

### 10.5 Spickzettel

Zwei Spalten Referenz, direkt im UI-Fenster.

**Tastenkürzel:**

| Tasten | Aktion |
|---|---|
| esc | den obersten offenen Modus schließen |
| ⌘ \ | Seitenleiste zeigen / verstecken |
| ⌘ / | das Readvisor-Panel zeigen / verstecken |
| ⇧ ⌘ / | dem Readvisor-Panel das ganze Fenster geben |
| ⌘ K | die Chat-Eingabe fokussieren |
| ⌘ Enter | die Nachricht senden |
| shift Enter | Zeilenumbruch statt Senden |
| ⌘ B / I / U | Auswahl fett / kursiv / unterstrichen (Leseseite) |
| ⌘ S | speichern (Bearbeitungsseite) |
| ⌥ click | Kontextmenü des Dateibaums |
| ⇧ ⌘ D | Wörterbucheintrag für das markierte Wort oder das Wort am Cursor |
| Rechtsklick auf ein Wort | Menü zum Wörterbucheintrag (Shift gedrückt halten für das Systemmenü) |

(Auf einer Nicht-Mac-Tastatur: Ctrl für ⌘, Alt für ⌥.)

Das sind die Tastenkürzel, die die Oberfläche selbst handhabt, sie funktionieren also in der App wie in einem Browser-Tab gleichermaßen. Die App fügt zwei eigene aus der Menüleiste hinzu: **⌘W** schließt das Projekt und bringt dich zurück zum Startbildschirm (Abschnitt 2.5) — es schließt das Fenster *nicht* mehr — und **⌘Q** beendet, wie es das immer schon tat.

**Der Markdown-Spickzettel:** Überschriften, Listen, Links, Code, Zitate — die ganze Kurzreferenz, für alle, die noch flüssig in Markdown werden. Was sich lohnt, denn enough spricht es überall nativ.

### 10.6 Eingebettete Hilfe (IHH)

Die `(?)`-Blasen, verstreut über die Oberfläche, sind das eingebaute Hilfesystem: eine Blase pro Konzept — Skills, Readvisors, das Readvisor-Panel, der Paradigmen-Wähler, die Composure mit ihren Modulen und Werkzeugen, das Journal, rness, io, Wissen, cacheawl, wikisink, das Modus-System, konvertierte Dokumente, und so weiter — jede mit einem **Was**, einem **Wie** und einer **Ideen**-Liste. Die Skills-, Readvisors- und Paradigmen-Blasen listen, was tatsächlich in *deinem* Projekt installiert ist, und die Blase zu konvertierten Dokumenten zieht ihre Dateitypen-Tabelle aus der eigenen Format-Registry der App — alles live erzeugt, sodass Hilfe nie aus dem Takt mit der Wirklichkeit gerät. (Dieselbe Tabelle erscheint in Abschnitt 7.2 dieses Handbuchs, aus derselben Quelle.)

Blasen werden pro Projektordner über die Checkbox „Hilfeblasen (?)“ im UI-Fenster gesteuert. Standardmäßig an für einen neuen Ordner, und die Einstellung bleibt pro Ordner haften — sodass dein eingespieltes Alltagsprojekt still werden kann, während ein frisches Experiment seine Stützräder behält.

Sogar die Hilfe selbst ist anpassbar. Der Inhalt lebt in einer Markdown-Datei (`enough/static/help-docs.md`); sie zu bearbeiten bearbeitet die Blasen.

---

## 11. Wikisink

Wikisink (🚰) legt eine Offline-Kopie der englischen Wikipedia auf deinem Rechner an: durchsuchbar in der App, volltextsuchbar, lesbar für deine Readvisors, kommentierbar, und auf Wunsch mit einem Änderungsbericht aktualisierbar. Nach der Einrichtung braucht es überhaupt kein Internet mehr.

### 11.1 Einrichtung

Klick 🚰 zum ersten Mal an, und der Assistent fragt drei Dinge.

1. **Größe.** Archive sind Kiwix-Builds, nur Text, sofern nicht anders vermerkt:

   | Variante | Inhalt | ungefähre Größe |
   |---|---|---|
   | top 1M Artikel *(Vorgabe)* | die meistgelesene Million | ~16 GB |
   | gesamte englische Wikipedia | jeder Artikel | ~49 GB |
   | top 50k | die meistgelesenen fünfzigtausend | ~2,1 GB |
   | top 50k mini | top ~50k, nur Einleitungsabschnitte | ~320 MB |
   | Simple English | komplette Simple Wikipedia | ~950 MB |

2. **Speicherort.** Vorgabe ist `~/enough/wikisink`; jeder Ordner funktioniert, externe Laufwerke eingeschlossen. Lass rund 5 % Spielraum über die Archivgröße hinaus.
3. **Bestätigung.** Der Download ist fortsetzbar und übersteht ein Beenden — pausieren, fortsetzen oder abbrechen aus demselben Fenster, während der Rest von enough weiterarbeitet.

Das Archiv ist eine einzelne `.zim`-Datei, an Ort und Stelle gelesen. Sie wird nie entpackt, und sie verstopft nie deinen Dateimanager. Du kannst **mehrere Installationen** registrieren — etwa das volle Archiv auf einem externen Laufwerk plus ein kleines auf der internen Platte — und in der ⚙-Installationsliste zwischen ihnen wechseln. Ein getrenntes Laufwerk bricht nichts: diese Installation zeigt als nicht erreichbar, bis das Laufwerk zurückkommt, und deine Kommentare und Overrides leben unabhängig von jedem einzelnen Archiv.

Einmal installiert, öffnet 🚰 den Reader: zurück und vor, live Titelvorschläge im Suchfeld (Enter führt eine Volltextsuche über das ganze Archiv aus), ein 🎲-Zufallsartikel-Würfel, und ein Quellen-Abzeichen, das dir sagt, ob du den Archiv-Snapshot liest (`ZIM <Datum>`), eine frischere Kopie aus einem Update-Lauf (`live <Datum>`), oder eine bewahrte Kopie (`preserved`). Interne Links bleiben in der App; externe Links öffnen in deinem Browser. Markier eine Passage, und sie erscheint als Chip über dem Nachrichtenfeld im Readvisor-Panel, bereit, mit deiner nächsten Nachricht mitzugehen (Abschnitt 5.2).

**Die Neuerer-Snapshot-Pille.** Kiwix baut diese Archive regelmäßig neu, und du solltest dafür nicht suchen müssen. Existiert ein neuerer Build *deiner* Variante, erscheint eine kleine Pille in der Reader-Werkzeugleiste — `neuerer Snapshot: <Datum> · <Größe>`. Anklicken, die Größe bestätigen, und das Upgrade läuft an Ort und Stelle: derselbe Speicherordner, erst heruntergeladen und erst eingetauscht, wenn es fertig ist, die alte Datei danach gelöscht und nicht vorher. Deine Kommentare, gespeicherten Artikel und 🛡-Overrides tragen unangetastet hinüber, weil keins von ihnen im Archiv selbst lebt. Die Pille wird zur Fortschrittsanzeige, während heruntergeladen wird, und verschwindet dann. enough prüft das höchstens einmal am Tag, nie während der Reader rendert, und bleibt still, wenn du offline bist — was der Normalzustand einer Offline-Wikipedia-Funktion ist. Dasselbe Upgrade ist auch auf dem langen Weg verfügbar, in der ⚙-Installationsliste, und wikisink-Läufe melden es ebenfalls (Abschnitt 11.3) — aber den Button zu drücken, ist immer deine Sache.

### 11.2 Artikel speichern und sperren

**Speichern.** Der Speichern-Button bietet zwei Ziele: den `wiki/`-Ordner dieses Projekts, oder die rechnerweite Wiki-Cachebox (`~/enough/cacheawl/wiki/`), geteilt von jedem Projekt. So oder so ist ein gespeicherter Artikel ein Ordner — `article.html`, der Artikel Byte für Byte, wie ihn das Archiv hatte, plus `_manifest.md` mit Titel, Quell-URL, Abrufdatum und der CC-BY-SA-Lizenzzeile. Jeder gespeicherte Artikel ist selbstbeschreibend, was heißt, dass die Zuordnung, die du brauchst, schon danebenliegt, falls sein Text je in etwas landet, das du veröffentlichst. Klick eine gespeicherte `article.html` im Baum an, und sie öffnet im Reader in voller Wiedergabetreue — Infoboxen, Tabellen, alles —, sogar wenn kein Archiv erreichbar ist. Zum Entfernen mit der Maus über den gespeicherten Ordner im Baum bleiben und auf das erscheinende 🗑 klicken.

Speichern ist für *dich*: Offline-Offline-Kopien, Zuordnung für Veröffentlichungen. Deine Readvisors brauchen keine gespeicherten Artikel — ihre Tools lesen jeden Artikel im Archiv bei Bedarf als sauberen Text.

**Kommentare.** Text auswählen und 💬 drücken, oder das 💬 in der Werkzeugleiste für eine Notiz auf Absatzebene nutzen. Threads leben im 🗨-Panel: antworten, auflösen, wiedereröffnen, springen. Kommentare hängen am *Artikel*, nicht an einer Datei, und sie überstehen Artikel-Updates, indem sie sanft degradieren. Noch vorhandener Text bleibt **verankert**. Wegbearbeiteter Text wird an seinen Absatz **neu angeheftet**. Ein ganz gelöschter Absatz lässt den Kommentar **verwaist** im Panel zurück — markiert, aber nie automatisch gelöscht.

**Sperren (Löschungs-Overrides).** Manchmal löscht die echte Wikipedia einen Artikel, auf den du dich verlassen hast; der klassische Fall ist ein Nischenthema, gestrichen wegen „Relevanz“ statt Qualität. Der 🛡-Button bewahrt deine lokale Kopie für immer — von da an ausgeliefert mit einem `preserved`-Abzeichen, von künftigen Aktualisierungen ausgeschlossen, weiter durchsuchbar. Update-Lauf-Berichte bewerten erkannte Löschungen sogar (Relevanz-artige Begründungen gelten als verdächtig; Urheberrechtsverletzungen als harmlos), sodass du weißt, welche Löschungen einen Blick verdienen. Und das Übersteuern ist bewusst allein deine Sache: ein Readvisor kann 🛡 empfehlen, aber er kann es nie selbst drücken.

### 11.3 Das wikisink-Update, mit Änderungsbericht

„Wikisink“ ist auch ein Verb. Jeder Artikel, den du gespeichert oder kommentiert hast, wird *beobachtet*, und deinen Readvisor zu bitten, „einen wikisink zu laufen“ (oder ihn zu seinem `wikisink`-Tool greifen zu lassen) prüft die beobachtete Menge gegen die echte Wikipedia und meldet zurück. Ein Lauf:

1. aktualisiert geänderte beobachtete Artikel in ein lokales Overlay (ihr Abzeichen springt auf `live`);
2. markiert **Bearbeitungsspitzen** — beobachtete Artikel, die plötzlich Dutzende Male am Tag bearbeitet werden, plus wikipediaweite Ausreißer-Kandidaten;
3. vergleicht die täglichen **Top-1000-Abrufzahlen-Ranglisten** mit dem letzten Lauf: Aufsteiger, Absteiger, Neueinsteiger, Aussteiger, und Abruftrends für deine beobachteten Artikel;
4. prüft auf **Löschungen** beobachteter oder kürzlich angesehener Artikel, bewertet nach Verdächtigkeit (Abschnitt 11.2);
5. vermerkt, wenn ein **neuerer Basis-Snapshot** verfügbar ist. Das mehrere GB große Basisarchiv zu ersetzen, ist immer deine Entscheidung — die Pille in der Reader-Werkzeugleiste drücken (Abschnitt 11.1) oder die ⚙-Installationsliste nutzen. Es gibt kein Tool, das es austauscht.

Der Bericht kommt als Markdown im Chat an; die vollständige, ungekappte Version wird im wikisink-Zustandsordner aufbewahrt. Läufe sind höflich zu Wikipedia — gebündelt, ehrlicher User-Agent — und bei Unterbrechung fortsetzbar, und ein `report-only`-Lauf überspringt den Aktualisierungsschritt. Zwei Broker-Schalter regeln das alles: einer sperrt die Wiki-Tools deiner Readvisors ganz, der andere kann Läufe vollständig offline erzwingen.

---

## 12. Cacheawl

Cacheawl ist der rechnerweite Textspeicher: der Ort für Dinge, die du für immer behalten willst und aus jedem Projekt erreichen können sollst. Er lebt unter `~/enough/cacheawl/`, verborgen vor dem Dateibaum jedes Projekts, geteilt über alle deine enough-Instanzen. (Hast du ein früheres enough genutzt, wurde deine alte `infoworld/`-Bibliothek beim ersten Start von 0.1.6 in cacheawl aufgelöst — `personal/`, `public/` und `wiki/` wurden deine ersten drei Cacheboxen. Nichts ging verloren.)

### 12.1 Cacheboxen und ihre merirmaid-Diagramme

Eine **Cachebox** ist ein Ordner oberster Ebene im Speicher, und es gibt sie in zwei Spielarten. **Schlichte Boxen** enthalten für immer behaltenen Text, den du selbst organisierst: eine `personal`-Box mit Referenznotizen, eine `press`-Box mit veröffentlichten Stücken, welche Struktur auch immer dir dient. **Cache-Kopien** sind Boxen, *importiert* aus einer Quelle — einem lokalen Ordner, einer Website, oder einer Reihe von Wikipedia-Artikeln —, die sich merken, woher sie kamen.

Jede Box trägt ein **merirmaid-Diagramm**: `_cachebox.merirmaid`, eine live Darstellung der Struktur der Box, neu erzeugt, wann immer sich der Inhalt ändert. Doppelklick, um die Form einer Box auf einen Blick zu sehen. Das Diagramm ist ein *Spiegel*, per Design nur lesbar, weil es die Wirklichkeit widerspiegelt — um das Diagramm zu ändern, die Box ändern. Ein günstiger Abgleich-Durchlauf hält Spiegel ehrlich, selbst wenn du Dateien vom Finder aus hinter enoughs Rücken hineinlegst.

Öffne den **cacheawl-Modus** aus der oberen Leiste für eine zweigeteilte Ansicht, Projekt auf der einen Seite, Speicher auf der anderen. Eine Datei rüberziehen, um sie zu kopieren. Shift-ziehen zum Verschieben. Shift-klick für ein Kontextmenü, und Doppelklick, um jede Datei in ihrem natürlichen Modus zu öffnen — girraph, merirmaid, Lesen/Bearbeiten, oder der Wiki-Reader — direkt aus dem Speicher.

### 12.2 Die Cachebox und lokale oder Web-Dokumente einfangen

Die **Import-Leiste** im cacheawl-Modus (oder eine schlichte Bitte im Gespräch) fängt Material von außen in eine Box ein:

- **Ein lokaler Pfad** — einen Ordner mit Notizen oder Dokumenten in den Speicher replizieren.
- **Eine Website** — eine Doku-Seite oder Referenzseite bis zu einer gewählten Tiefe crawlen (gedeckelt bei rund 500 Seiten) und als lokales Markdown behalten. Web-Importe respektieren deine Abruf-Schalter und Positivlisten, Tor-Routing eingeschlossen.
- **Wikipedia** — die Artikel eines Themas (gedeckelt bei rund 200) aus deinem wikisink-Archiv in dauerhaften, projektunabhängigen Text holen.

Importe laufen im Hintergrund. Die Box erscheint sofort mit einem Status „wird importiert“, dem du zusehen kannst, und ein gescheiterter Import sagt das auch, statt so zu tun, als wäre er fertig. Die Cachebox-Tools deiner Readvisors (auflisten, anlegen, importieren) werden durch den cacheawl-Broker-Schalter gesperrt; deine eigene Nutzung des cacheawl-Modus nie.

Warum der Aufwand? Weil Projektordner Arbeitsraum sind und cacheawl Bibliotheksraum ist. Importier die Dokumentation eines Frameworks einmal, und jedes künftige Projekt kann sich offline darauf stützen. Halt deine zeitlosen Referenznotizen in einer Box, und jeder Readvisor, mit dem du je sprichst, kann sie erreichen. Ein Artefakt fertigstellen und in eine Box verschieben, wo es sein Projekt überlebt.

---

## 13. Das Wörterbuch (FEED)

enough bringt ein eigenes Wörterbuch mit: **FEED**, das **hauseigene englische Wörterbuch von enough**. Es ist ein Originalwerk, für enough geschrieben statt anderswo lizenziert — rund 96.000 Stichwörter, jedes mit seiner Aussprache, seiner Wortart und einer schlichten Definition, die meisten dazu mit Beispielen, Formen, einer Herkunft, einem Datum der ersten Verwendung, einem Maß dafür, wie gebräuchlich das Wort ist, seinen Reimen, seinen Verwandten und seinen Entsprechungen in fünf anderen Sprachen.

Es lebt auf deinem Rechner. enough liefert das Wörterbuch als schlichten Text aus und baut daraus beim ersten Start nach einer Installation oder einem Update eine Datenbank — `~/enough/dict/feed.sqlite` —, im Hintergrund, während du dich um etwas anderes kümmerst. Öffnest du das Wörterbuch, solange das noch läuft, steht dort *der Satz wird gesetzt…* mit einer Prozentzahl, und es macht von allein weiter. Ein Wort nachzuschlagen berührt nie das Netzwerk: was du liest und über welche Wörter du dich gewundert hast, bleibt auf der Maschine.

### 13.1 Es öffnen

Im ⚙-UI-Fenster: Der **Wörterbuch**-Button sitzt oben neben **Hilfe** (Abschnitt 10). Das Wörterbuch öffnet als Vollbild-Modus, gestapelt wie jeder andere (Abschnitt 14); was du vorher gelesen hast, liegt beim Schließen also noch darunter, und Esc bringt dich zurück.

Es ist eine Leseoberfläche. In seine Einträge kannst du nicht tippen und sie auch nicht umordnen; Wörter hinzuzufügen und zu ändern läuft über deinen Chef-Readvisor (Abschnitt 13.7).

### 13.2 Seiten umblättern

Es ist wie ein gedrucktes Wörterbuch angelegt, nicht wie eine Liste, durch die man scrollt: so viele Einträge, wie ins Fenster passen, in zwei bis vier Spalten, wenn Platz ist, und eine Seite, die du umblätterst. → und ←, Bild ab und Bild auf, Leertaste und shift-Leertaste blättern alle um; ebenso ein Wisch über das Trackpad oder eine Drehung am Rad — eine Seite pro Geste — und ebenso die Buttons am Fuß, die das Wort nennen, das auf der nächsten Seite wartet, und das, das auf der letzten zurückgeblieben ist. Pos1 und Ende gehen zur ersten und zur letzten Seite.

Am oberen Rand jeder Seite laufen die **Leitwörter**, wie in jedem gedruckten Wörterbuch: links das erste Wort der Seite, rechts das letzte, und dazwischen eine Erinnerung daran, in welcher Reihenfolge du gerade liest. Eine Überschrift markiert die Stelle, an der jeweils eine neue Gruppe beginnt — ein Buchstabe, ein Fachgebiet, ein Jahrhundert. Am Fuß steht eine Angabe, wo du bist — welche Einträge auf der Seite stehen, von wie vielen (Seitenzahlen gibt es nicht, denn eine Seite fasst so viele Einträge, wie dein Fenster hergibt) — und **irgendwo aufschlagen**, das das Wörterbuch auf einer zufälligen Seite öffnet und ein Wort darauf aufleuchten lässt. Eine gute Methode, zehn Minuten zu verlieren.

Am rechten Rand entlang läuft das **Daumenregister**, die eingekerbten Reiter am Buchschnitt eines dicken Schreibtisch-Wörterbuchs: ein Reiter pro Buchstabe, jeder so hoch wie sein Anteil am Buch, sodass man auf einen Blick sieht, dass S dick ist und X dünn. Klick auf einen Reiter, und das Wörterbuch öffnet sich dort. Die Reiter folgen der Reihenfolge, in der du liest — Fachgebiete bei einer Sortierung nach Fachgebiet, Jahrhunderte bei einer nach Epoche —, und der, in dem du gerade bist, ist markiert.

Jeder Eintrag ist kurz: das Stichwort mit Punkten zwischen den Silben (*lan·tern*), seine Aussprache, seine Wortart, die Definition, ein Gebrauchslabel, wo es eines gibt, und ein paar verwandte Wörter, jedes ein Link, der zur Seite dieses Wortes blättert. ↑ und ↓ bewegen eine Auswahl durch die Einträge; Return oder ein Doppelklick öffnet den ausgewählten in voller Länge (Abschnitt 13.5). Ist das Wörterbuch schmal — ein kleines Fenster, oder neben ein angedocktes Readvisor-Panel gequetscht —, wird die Seite zu einer einzigen Spalte ausführlicherer Einträge, jeder mit einer kleinen Häufigkeitsanzeige, einer Zeitleiste, wann das Wort aufkam, und seinem Fachgebiet.

**Die Wortart-Zeichen.** Jeder Eintrag trägt für jede Wortart, die er hat, ein Zeichen in einer Farbe und einer Form, damit Farbe nie das einzige Signal ist: ein **Quadrat** für ein Substantiv, ein **Dreieck** für ein Verb, eine **Raute** für ein Adjektiv, ein **runder Punkt** für ein Adverb und ein **hohler Ring** für alles andere. In den Spalten sitzt das Zeichen vor der Abkürzung (*n.*, *v.*, *adj.* …) und als dünner Balken am Rand des Eintrags; ein Wort, das Substantiv und Verb zugleich ist, trägt beide.

### 13.3 Sortieren, und noch einmal sortieren

Alphabetisch ist nur der Anfang. **sortieren** ordnet das ganze Wörterbuch nach einem von neun Kriterien — alphabetisch, Länge, Fachgebiet, Epoche, Wortart, Häufigkeit, Silben, zuletzt hinzugefügt und Quelle —, und der Button daneben kehrt die Reihenfolge um, in schlichten Worten: *kurze zuerst* oder *lange zuerst*, *älteste zuerst* oder *neueste zuerst*, *seltenste zuerst* oder *häufigste zuerst*.

**dann** ist eine zweite Ordnung innerhalb der ersten, und da liegt der Spaß. Sortiere nach Fachgebiet, dann nach Epoche, und jedes Wissensgebiet reiht seine Wörter in der Reihenfolge auf, in der das Englische sie aufgelesen hat — die ältesten Wörter der Musik zuerst, die neuesten zuletzt. Sortiere nach Länge, dann alphabetisch, und du kannst jedes Wort mit fünf Buchstaben im ganzen Buch der Reihe nach lesen, was für Rätselbauer ein ganzer Nachmittag ist. Sortiere nach Häufigkeit, seltenste zuerst, und das Wörterbuch schlägt sich bei den Wörtern auf, die fast niemand benutzt. Solange eine zweite Ordnung aktiv ist, zeigt jeder Eintrag seinen Wert dafür am Rand.

**mehr** öffnet zwei kurze Zeilen. **probier** hält eine Handvoll Ordnungen für einen Klick bereit — *Fachgebiet, dann Epoche*; *Länge, dann alphabetisch*; *seltenste zuerst*; *Epoche, dann alphabetisch*; *neueste Wörter zuerst*; *nur deins*. **nur** schränkt das Buch auf ein Fachgebiet, eine Wortart, eine Häufigkeitsstufe oder auf FEEDs Wörter oder deine eigenen ein, und **zurücksetzen** hebt alles auf. Die Zahl oben rechts sagt, wie viele Einträge du siehst, und von wie vielen.

Das Wörterbuch merkt sich deine Ordnung, deine Filter und die Seite, auf der du warst, und öffnet beim nächsten Mal dort.

### 13.4 Ein Wort finden

Tipp ins Suchfeld oben — / oder ⌘F bringt dich dorthin —, und die Seite wird zu den Ergebnissen: jeder Eintrag, dessen Stichwort oder Definition enthält, was du getippt hast, mit markierten Treffern. Drückst du Return bei einem genauen Wort, tritt die Suche beiseite, und das Wörterbuch blättert stattdessen zur Seite dieses Wortes, in welcher Reihenfolge du auch liest. Esc leert die Suche und bringt dich zurück auf die Seite, auf der du davor warst.

Eine Form eines Wortes — *ran*, zum Beispiel — führt dich zu dem Wort, zu dem sie gehört, und die Karte einer nachgeschlagenen Form sagt, welche Form wovon sie ist. Ein Wort, das FEED nicht hat, öffnet seine Karte (Abschnitt 13.5) mit der Nachricht, ein paar nahen Wörtern, die es hat, und der Stelle, an der das Wort stünde, wenn es dort wäre.

### 13.5 Die Wortkarte

Doppelklick auf einen Eintrag, oder wähle ihn aus und drück Return, und er öffnet sich in voller Größe, als Karte über allem, was du gerade gemacht hast. Alles, was FEED über das Wort weiß, steht darauf, und das meiste schon in der ersten Ansicht:

- das Stichwort, seine Silben und seine Aussprache, dazu seine Wortarten mit ihren Zeichen;
- wie gebräuchlich es ist, als Anzeige von 0 bis 8 mit dem Namen der Stufe daneben;
- ein Streifen mit Fakten — Fachgebiet (und wie viele Wörter es sich teilen), erste Verwendung, Silben, Buchstaben, und ob der Eintrag von FEED ist oder deiner;
- eine Zeitleiste vom Altenglischen bis in die 2020er, auf der das Aufkommen des Wortes markiert ist;
- die **Bedeutung**, ein etwaiger **Gebrauch**-Hinweis, **Beispiele** mit hervorgehobenem Wort, seine **Formen** (Plurale, Zeiten und der Rest, jede mit eigener Aussprache), wovon es die **Form von** ist, falls es eine ist, und seine **Herkunft**.

Drei Reiter halten den Rest, einen Klick entfernt (oder 1, 2 und 3): **Wörter** — Synonyme, Antonyme, Verwandtes und Homophone; **Reime** — reine und unreine; und **Sprachen** — das Wort neben seinen Entsprechungen in Französisch, Spanisch, Deutsch, Chinesisch und Japanisch, mit der Definition, in jede dieser Sprachen übersetzt. Was FEED zu einem Wort nicht verzeichnet hat, sagt die Karte offen, statt eine Lücke zu lassen, wo du danach suchen würdest.

**Von Wort zu Wort wandern.** Jedes Wort auf der Karte ist ein Link, ebenso jedes Wort der Definition, der Beispiele und der Herkunft: Klick eines an, und die Karte wird die dieses Wortes. Der Pfad, den du gegangen bist, läuft oben entlang als **dein Weg**, und **‹ zurück** (oder ⌫) geht ihn Schritt für Schritt zurück. ← und → springen zum vorherigen und zum nächsten Eintrag in der Reihenfolge, in der du liest, mit *Eintrag n von m*, das sagt, wo du bist. **auf seiner Seite zeigen** — **im Wörterbuch öffnen**, wenn du von woanders kamst — schließt die Karte und schlägt das Wörterbuch bei dem Wort auf. Esc, das × oder ein Klick außerhalb der Karte schließt sie.

### 13.6 „Wörterbucheintrag“, überall, wo du liest

Klick mit der rechten Maustaste auf ein Wort — in der Leseseite oder der Bearbeitungsseite eines Dokuments, im Gespräch, auf einer Composure-Seite, in einem wikisink-Artikel, in diesem Handbuch —, und ein kleines Menü bietet **Wörterbucheintrag** an, der die Karte dieses Wortes über allem öffnet, was du gerade tust, und **kopieren**. Markier vorher eine kurze Wendung und klick mit rechts hinein, wird die Wendung nachgeschlagen. Im Wörterbuch selbst blättert derselbe Eintrag zur Seite des Wortes; auf der Karte führt er die Karte dorthin. ⇧⌘D tut dasselbe für das markierte Wort oder das Wort am Cursor, ganz ohne Menü. Auf einer Composure bekommt das Menü, das du ohnehin siehst, wenn du mit rechts auf ein Modul klickst, denselben Eintrag, sobald der Zeiger auf einem Wort steht.

Das Systemmenü ist nicht verschwunden; es ist nur um eine Taste verrückt. Ein Rechtsklick, der nicht auf einem Wort liegt — zwischen Wörtern, hinter dem Ende einer Zeile, auf einem Link, auf einem Bild —, bekommt das Systemmenü genau wie immer. Und ein Rechtsklick mit gehaltener **Shift**-Taste bekommt jedes Mal das Systemmenü, ob Wort oder nicht: Das ist der Weg zu Rechtschreibvorschlägen, zum systemeigenen Nachschlagen und zum Einfügen in ein Textfeld. Das Menü sagt es in seiner letzten Zeile, du musst dir also nichts merken.

### 13.7 Dein eigenes Wörterbuch

FEED selbst ändert sich nie unter dir, aber es ist nicht das einzige Wörterbuch hier. Daneben steht **dein eigenes**, das leer beginnt und nur enthält, was du hineintust: ein Wort, das deine Familie erfunden hat, ein Begriff aus deinem Fach, ein Name, den du für etwas hast, eine eigene Wortschöpfung — oder deine eigene Fassung eines Wortes, das FEED schon hat.

Du fügst etwas hinzu, indem du deinen Chef-Readvisor bittest. „Nimm *glimmerwick* in mein Wörterbuch auf.“ „Mein Team nennt ein Meeting, das eine E-Mail hätte sein sollen, ein *dronefest* — nimmst du das auf?“ „Ich hätte gern meine eigene Definition von *draft*.“ Das Gespräch läuft so, wie ein sorgfältiger Lexikograf es führen würde. Dein Readvisor schlägt das Wort zuerst nach, und hat FEED es schon, sagt er das und bietet an, es dir zu zeigen, statt stillschweigend ein zweites aufzunehmen. Ist es neu, entwirft er, was sich entwerfen lässt — Aussprache, Wortart, Silben, Formen —, und fragt dich nach dem, was nur du weißt: was es bedeutet, wie und wo du es benutzt, wer es sagt, woher es kommt, ein, zwei Fragen auf einmal. Dann liest er dir den Eintrag in schlichten Worten vor und wartet auf ein Ja, bevor er irgendetwas schreibt. Danach erwähnt er einmal, welche Teile noch leer sind; sie leer zu lassen, ist in Ordnung.

Deine Wörter sind auf jeder Seite und in jeder Ordnung mit denen von FEED durchmischt, markiert als **deins**, und *nur deins* unter **mehr** zeigt sie für sich allein. Ein Wort, das in beiden Wörterbüchern steht, gehört dir: Deine Version tritt überall in enough an die Stelle von FEEDs — auf der Seite, auf der Karte (markiert als *ersetzt FEED*) und in dem, was dein Readvisor findet, wenn er das Wort nachschlägt.

Sie liegen in einer einzigen Datei, `~/enough/dict/user-dictionary.sqlite`, getrennt von der von FEED und maschinenweit wie dein Theme, sodass jedes Projekt dieselben Wörter sieht. Ein Update baut FEEDs Datei von Grund auf neu und rührt deine nie an.

Um einen deiner Einträge zu entfernen, öffne seine Karte und drück **deinen Eintrag löschen**; es fragt vorher nach. Löschst du deine Version eines FEED-Wortes, kommt FEEDs eigener Eintrag zurück. Einen Eintrag zu ändern ist ein anderes Gespräch — „ändere das Beispiel für *glimmerwick*“ —, denn das Wörterbuch selbst ist nur zum Lesen da.

Dein Readvisor hat das Wörterbuch in jedem Projekt zur Hand, mit Skill oder ohne. Der Skill `lexicographer` (Abschnitt 19.4) ist für die Zeit, in der du oft Wörter hinzufügst: Eingeschaltet, trägt er FEEDs ganzen Hausstil in jeden Zug, sodass deine Einträge so klingen wie der Rest des Buches, ohne dass dein Readvisor erst den Stilleitfaden holen gehen muss.

---

## 14. Mehrfach aktiver Modus-Stapel

enoughs Vollbild-Modi — Lesen/Bearbeiten, girraph, merirmaid, wikisink, cacheawl, das Wörterbuch, dieses Handbuch — ersetzen sich nicht gegenseitig. Sie **stapeln** sich, wie Blätter Papier. cacheawl öffnen, einen girraph von innerhalb einer Box öffnen, eine Notizdatei darüber öffnen: drei Modi tief, und jeden zu schließen legt den darunterliegenden genau so frei, wie du ihn verlassen hast. Dieselbe Scroll-Position, derselbe Abstieg, dieselben ungespeicherten Änderungen.

Die obere Leiste zeigt einen quadratischen Indikator pro offenem Modus, neuester links. Jeder trägt ein kleines rot-x-Band, das genau diesen Modus schließt, auch einen vergrabenen. Auf den Indikator eines vergrabenen Modus klicken, um ihn nach oben zu holen, ohne sonst etwas zu stören. Schließt der letzte, bist du zurück auf der Composure — dem leeren Stapel (Abschnitt 4).

**Das Basis-Quadrat.** Am rechten Ende dieser Indikatoren sitzt eines, das immer da ist und kein Band hat: die Composure. Es gibt nichts zu schließen, weil sie das Erdgeschoss ist. Sie anzuklicken ist die **Blick**-Geste aus Abschnitt 4.8 — jeder gestapelte Modus verschwindet, du siehst die Leinwand an, und ein weiterer Klick (oder ein Klick auf irgendeinen anderen Indikator) holt sie alle unangetastet zurück.

**Das Readvisor-Panel steht überhaupt nicht im Stapel.** Es ist eine Spalte daneben (Abschnitt 5), ein angedocktes Panel und drei gestapelte Modi kommen also nebeneinander aus, ohne sich in die Quere zu kommen, und Esc schließt das Panel nie, solange es angedockt ist.

**Esc, der Reihe nach.** Esc heißt *aus dem innersten Ding heraus*, und das innerste Ding ist nicht immer ein Modus:

1. ein offenes Modal, das sein Esc selbst handhabt;
2. eine Bestätigungs-Überlagerung;
3. ein Textfeld, in das du tippst — wo Esc mit Absicht wirkungslos ist, damit ein verirrter Druck keine Nachricht wegwirft, an der du gerade schreibst (ein Suchfeld ist die Ausnahme: dort leert Esc erst die Suche und lässt dann los);
4. ein offenes Composure-Menü;
5. ein Readvisor-Panel im ganzen Fenster, das zurück auf angedockt fällt;
6. ein Blick, der die gestapelten Modi zurückstellt;
7. und erst dann der oberste Modus.

Zwei nützliche Dinge, die man kennen sollte:

- Das Mini-Lese-/Bearbeitungspanel schwebt *über* einem Vollbild-Modus, du kannst also ein Dokument griffbereit halten, während du darunter, sagen wir, im girraph-Modus arbeitest.
- Einen Modus zu öffnen, der schon irgendwo im Stapel steckt, verdoppelt ihn nicht. Es zielt den vorhandenen neu aus und holt ihn nach oben.

---

## 15. Das Modell-Fenster

Das Modell-Abzeichen in der oberen Leiste öffnet das Modell-Fenster: welches Gehirn dir gerade antwortet, was sonst noch verfügbar ist, und — wenn du willst — der Cloud-Slot.

### 15.1 Lokale Modelle: Überblick und Nutzungsempfehlungen

Sieben unterstützte lokale Modelle — und das Fenster ist jetzt auch, wo du sie installierst. Jede Zeile, die du noch nicht hast, zeigt ihre Download-Größe und ein Machbarkeitsurteil, berechnet gegen den Arbeitsspeicher und freien Plattenplatz *dieses Rechners*: ✓ komfortabel, ~ knapp, ✗ nicht empfohlen. Downloads laufen mit einem Live-Fortschrittsbalken, überstehen ein Beenden (sie setzen dort fort, wo sie aufgehört haben), und lassen sich abbrechen, ohne den Teil zu verlieren, den du schon hast. Installierte Modelle wechseln mit einem Klick, und jedes Modell außer dem aktiven lässt sich aus seiner Zeile löschen, wenn du die Platte zurückhaben willst.

| Spitzname | Modell | Platte | min. RAM | Anmerkungen |
|---|---|---|---|---|
| **G40-04** | Gemma 4 4B (E4B) | ~5,4 GB | 8 GB | das kleinste; passt überall; die Vorgabe |
| **Q35-09** | Qwen3.5-9B | ~5,9 GB | 10 GB | ausgewogene Mittelgröße; MTP-Spekulationsdecoding |
| **G40-12** | Gemma 4 12B (QAT) | ~7,0 GB | 12 GB | quantisierungsbewusst trainiert; der 16-GB-Sweet-Spot |
| **G40-26** | Gemma 4 26B MoE (4B aktiv) | ~15,6 GB | 20 GB | Großmodell-Qualität bei Mittelmodell-Tempo |
| **Q36-27** | Qwen3.6-27B dense | ~17,1 GB | 22 GB | das erfahrene Schwergewicht; MTP; langer Atem |
| **Q38-04** | Qwen3.8 27B (4-Bit) | ~19 GB + 1,7 Draft | 24 GB | der neueste Qwen; entwirft seine eigene Spekulation |
| **Q38-16** | Qwen3.8 27B (16-Bit) | ~54 GB + 3,2 Draft | 64 GB | volle Präzision, für die größten Macs |

Eine Namens-Falte, damit sie dich nie stolpern lässt: bei den beiden Q38-Namen ist die Zahl nach dem Strich die **Quantisierungsbreite**, nicht die Parameterzahl — Q38-04 und Q38-16 sind das *gleiche* 27-Milliarden-Parameter-Modell, in 4-Bit- und 16-Bit-Präzision. (G40-04, aus der älteren Konvention, ist wirklich ein 4-Milliarden-Parameter-Modell.) Die Beschriftungen im Fenster buchstabieren das aus, damit die Spitznamen es nie müssen.

Faustregeln. Auf einem 8–16-GB-Rechner mit G40-04 leben, und G40-12 zum Upgrade machen, sobald du Spielraum hast — quantisierungsbewusstes Training gibt ihm ungewöhnlich sauberen Output für seine Größe. Bei 32 GB ist G40-12 oder Q35-09 ein komfortabler Alltagsfahrer, mit G40-26 oder Q38-04 für die härtere Synthesearbeit. Bei 64 GB und mehr Q38-04 oder Q36-27 als Vorgabe und nicht mehr darüber nachdenken. Q38-16 ist seine eigene Kategorie: das Vollpräzisions-Schwergewicht für Rechner mit ernsthaftem Unified Memory und ~57 GB übrigem Plattenplatz — hast du einen Mac Studio und willst die Decke, ist das die Decke. Kontextfenster skalieren automatisch mit deinem RAM — jedes Modell liefert eine sinnvolle Vorgabe pro RAM-Stufe, überschreibbar in der Konfiguration — und die Qwen-Builds tragen Multi-Token Prediction für kostenloses Extra-Tempo: eingebaut in die Modelldatei für Q35/Q36, und über eine kleine begleitende „Draft“-Datei beim Q38-Paar, die automatisch mit heruntergeladen wird.

Noch eine Anmerkung für Terminal-Installationen: ein Modell lässt sich auf jedem llama.cpp *herunterladen*, aber nur auf einem hinreichend aktuellen Build *ausführen*. Ist deiner zu alt für ein neueres Modell, sagt das Fenster das und nennt die Lösung (`brew upgrade llama.cpp`). App-Installationen sehen diese Anmerkung nie — die App bringt ihre eigene Inferenz-Engine mit.

Modell wechseln startet den lokalen Inferenz-Server neu und leert das Gespräch im Arbeitsspeicher. Deine Dateien, Protokolle und der Anfrage-Zustand bleiben alle erhalten; ein Wechsel kostet dich Chat-Verlauf, nicht Arbeit.

### 15.2 OpenRouter-Unterstützung (der OPRO-API-Slot)

enough ist local-first, nicht local-only. Ein fünfter Modell-Slot, **OPRO-API**, leitet über OpenRouter zu Cloud-Modellen. Er ist standardmäßig aus, bewusst aufwendig zu aktivieren, und ehrlich über den Tausch: deine Prompts und Outputs verlassen den Rechner, im Austausch für Frontier-Modell-Fähigkeiten und, manchmal, geringere Kosten als die Hardware und der Strom, die ein vergleichbares lokales Modell verlangen würden.

Ihn zu aktivieren: **local models only** im Broker ausschalten, dann OPRO-API im Modell-Fenster anklicken. Ein Assistent mit drei Bildschirmen führt dich durch — drei ausdrückliche Bestätigungs-Checkboxen (du hast ein Konto, du verstehst die Abrechnung, du verstehst den Datenschutz-Tausch), dann dein API-Schlüssel, dann eine Live-Gesundheitsprüfung. Der Schlüssel wird im macOS-Schlüsselbund gespeichert. Er wird nie in eine Datei geschrieben, deine Readvisors haben keine Möglichkeit, ihn zu lesen, und der Broker verweigert Shell-Befehle, die auch nur so aussehen wie Versuche, an ihn heranzukommen. Einmal verifiziert, wird OPRO-API wählbar wie jedes andere Modell, und sein Einstellungspanel bietet erneutes Testen, Schlüssel aktualisieren, Schlüssel entfernen, und deine Wahl jeder beliebigen OpenRouter-Modell-ID.

Zwei Dinge halten Cloud-Nutzung rechenschaftspflichtig:

- **Alles wird lokal zwischengespeichert.** Jeder Cloud-Austausch wird in `rness/io/cloud-cache/` geschrieben, mit Token-Zahlen und einem Index — eine lokale Papierspur, die deine lokalen Readvisors später lesen können.
- **`cloud_pipeline`** lässt deine Readvisors große Jobs gebündelt durch den Cloud-Slot schicken — bis zu 200 Schritte, mit Zwischenspeicherung pro Schritt, optionaler Zusammenfassung pro Schritt, und einem abschließenden Kompilierungsdurchgang — Ergebnisse werden auf die Platte geschrieben, statt das Gespräch zu fluten. Bitte um „eine Cloud-Pipeline, die alle zwölf Kapitelzusammenfassungen entwirft“, und die Schwerarbeit passiert außerhalb des Gesprächs, vollständig protokolliert.

### 15.3 `/pal` — eine Frage nach draußen

Manchmal ist dein lokales Modell überfordert, und du hättest gern eine Meinung von außen. Ein **pal** ist genau das: keine neue Einstellung und kein zweites Konto, sondern schlicht das Cloud-Modell, das du im OPRO-API-Slot ohnehin schon eingerichtet hast, einmal erreicht, von Hand, aus einem sonst lokalen Zug heraus.

Beginn eine Nachricht mit `/pal`, und der Rest davon ist die Frage:

`/pal was ist gerade der Stand der Technik bei Spracherkennung auf dem Gerät?`

Dann passieren drei Dinge, der Reihe nach. Dein Chef-Readvisor denkt zuerst hier darüber nach, mit dem, was schon auf dem Rechner ist — seinem eigenen Wissen, den Dateien in deinem Projekt, den Wiki-Werkzeugen — und arbeitet heraus, was er lokal wirklich nicht klären kann. Er verfasst **einen** Prompt und schickt den ans Cloud-Modell. Dann antwortet er dir mit seiner eigenen Stimme und sagt klar, welche Teile vom pal kamen und welche seine eigenen sind.

**Du siehst, was hinausgegangen ist.** Bevor die Antwort eintrifft, erscheint der genaue Text, der hinausging, als eigene Blase, Wort für Wort — nie gekürzt, nie auf dem Weg zum Bildschirm zusammengefasst —, mit der Antwort darunter. Beides ist nach einem Neuladen immer noch da, und beides wird in dein Sitzungsprotokoll und in den Cloud-Cache geschrieben. `/pal` zu tippen *ist* die Zustimmung; es gibt keinen zweiten Bestätigungsschritt, denn eine Bestätigung, die jedes Mal erscheint, ist ein Knopf, den man zu klicken lernt, ohne ihn zu lesen. An ihre Stelle tritt, dass du immer sehen kannst, was hinausgegangen ist.

**Das Tor ist das Tor des Cloud-Slots, genau dasselbe.** `/pal` funktioniert, wenn **local models only** im Broker aus ist, ein Schlüssel hinterlegt ist und die letzte Gesundheitsprüfung bestanden wurde (15.2). Trifft eines davon nicht zu, sagt dir `/pal`, welches, und wie du es behebst — und es läuft kein Zug, also wird nichts ausgegeben und nichts verlässt den Rechner. Tipp `/` als erstes Zeichen im Eingabefeld, und eine Hinweiszeile sagt dir dasselbe, bevor du dich festlegst: ausgegraut mit dem Grund, wenn der Slot nicht nutzbar ist, und mit dem Namen des Modells, das gefragt würde, wenn er es ist — das ist der Unterschied zwischen einem Befehl und einer Überraschung auf deiner Rechnung.

**Ein Aufruf je `/pal`.** Dein Readvisor bekommt genau eine Frage nach draußen je Nachricht, die du so beginnst. Deckt die Antwort es nicht ab, sagt er das, und du kannst noch eine schicken. Und bei jedem anderen Zug verlässt nichts diesen Rechner: ohne `/pal` davor ist das Werkzeug schlicht nicht da, und ein Readvisor, der eine Meinung von außen für hilfreich hält, muss das sagen und dich entscheiden lassen.

Ist das Modell, mit dem du ohnehin sprichst, *selbst* OPRO-API, gibt es keinen pal zu fragen — das Cloud-Modell ist der, mit dem du sprichst. `/pal` sagt das, lässt das Token fallen und schickt den Rest der Nachricht wie gewohnt.

**Ein pal ist auf seinem Trainingsstand eingefroren, es sei denn, du bittest um das Web.** OpenRouter dokumentiert genau dafür ein Suffix: häng `:online` ans Ende der Modell-ID im OPRO-API-Einstellungspanel — `anthropic/claude-sonnet-4.5:online` — und deine Frage geht mit angehängten Websuch-Ergebnissen hinaus. Das ist OpenRouters eigene Funktion, und es steckt kein Code von uns dahinter; enough reicht die Modell-ID unverändert durch, und die Blasen zeigen sie mit dem Suffix, weil es je Suche extra kostet und du sehen können sollst, dass du darum gebeten hast.

---

## 16. Paradigmen

Ein Paradigma ist das Denkgerüst, in dem deine Readvisors arbeiten — die Spielregeln dafür, wie Arbeit passiert. Immer genau eines ist aktiv (oben in der Seitenleiste angezeigt; auf ● klicken zum Wechseln), und der volle Text des aktiven Paradigmas reitet bei jedem Zug im System-Prompt mit. Dein Chef-Readvisor sieht auch einen einzeiligen Katalog der anderen, damit er einen Wechsel vorschlagen kann — oder selbst vollziehen —, wenn deiner Bitte anderswo besser gedient wäre. Ein Wechsel, der für dich gemacht wird, ist nichts Exotisches: der Name des Paradigmas wird nach `rness/active-paradigm` geschrieben, und dir wird gesagt, dass es passiert ist.

### 16.1 text-planning

**Heimat.** Jedes neue Projekt beginnt hier, und jedes andere Paradigma kehrt hierher zurück, wenn seine Arbeit getan ist. Meistens fühlt es sich gar nicht wie ein Denkgerüst an: freies Gespräch, eine Stimme, für Fragen, Lesen, Recherche, Lektorat, Dateiarbeit und Entwerfen, wenn du ums Entwerfen bittest. Es trägt die stehenden Konventionen — zu wissen, dass „die gelben Teile“ deine Markierungen meint, wohin erzeugte Dateien gehen, wie Webseiten abgerufen werden —, und es ist der Verteiler, der bemerkt, wenn eines der anderen Paradigmen einer Bitte besser dienen würde, und umschaltet.

Es ist auch der Ort, an dem ein Text geplant wird, und das ist die lange Startbahn vor der Prosa: einen Roman, eine Essaysammlung, ein Sachbuch, eine Abhandlung oder ein Manifest von „ich glaube, ich will etwas schreiben“ zu einem brauchbaren Plan bringen. Nichts von dieser Maschinerie taucht auf, bevor du Planungsabsicht zeigst — „hilf mir, einen Roman zu planen“, „lass uns meine Essaysammlung gliedern“ —, und kein Skill muss dafür eingeschaltet werden. Dann baut dein Chef-Readvisor mit dir ein Plandokument im Projekt-Wurzelverzeichnis — geduldig, iterativ, über so viele Sitzungen, wie es braucht — und erzeugt auf Anfrage *Gerüste* pro Abschnitt: strukturelle Leitfäden (Beats, Überschriften, Ton-Erinnerungen, Wortbudgets), die du selbst zu Prosa ausbaust. Die Regel, die es ausmacht: **der Plan und die Gerüste enthalten nie Prosa.** Sie halten nur Struktur, und deine Stimme bleibt deine Stimme. Entwerfen ist eine eigene Sache, um die du mit so vielen Worten bitten kannst — „entwirf Kapitel 1 nach dem Plan“ —, und es wird in eine eigene Datei geschrieben, nie in den Plan; dein Readvisor bietet es nicht ungefragt an. Ein Projekt, das sich als Memoiren entpuppt, wird auf `memoir-dialectic` hingewiesen (Abschnitt 19.5), das eigens dafür gebaut ist.

**Wenn ein Projekt auf `default` stand.** `default` war bis zu dieser Runde das Heimat-Paradigma, und text-planning hat alles übernommen, was es tat. Ein Projekt, in dem `default` aktiv war, wird beim nächsten Öffnen auf text-planning umgestellt, wobei deine Einstellung für Hilfeblasen unverändert bleibt. Die eine Ausnahme ist ein Projekt, in dem du `default.md` zu einer eigenen Datei umgebaut hast: Diese Kopie gehört dir, also behält das Projekt sie und benutzt sie weiter, bis du wechselst.

### 16.2 translation

Erklärt Offline-Übersetzung zu einer Fähigkeit erster Klasse. Es paart sich mit dem Skill `translator` (Abschnitt 19.8): geht es bei einer Bitte darum, Text zwischen menschlichen Sprachen zu bewegen, wechselt dein Readvisor hierher, und ist der Skill ausgeschaltet, sagt er dir, was dir fehlt — und sagt es dir weiter, bis du ihn einschaltest. Mit eingeschaltetem Skill hast du einen lokalen Übersetzer für ~419 Sprachen, ohne Konto, ohne Ratenlimit, ohne Netzwerkabhängigkeit.

### 16.3 workflow-design

Das Paradigma über enough selbst, aktiv, wann immer du den Workflow gestaltest oder änderst, statt in ihm zu arbeiten: neue Skills, neue Readvisors, neue Paradigmen, Änderungen an AGENT.md oder MOTIVATION.md. Hier verhält sich dein Chef-Readvisor wie ein nachdenklicher Mitgestalter — klärende Fragen vor dem Bauen (Umfang? Name? Auslösebedingungen?), Alternativen, wenn dein erster Instinkt schärfer sein könnte, und eine verfolgte Anfrage-Datei für jeden Bau, denn Workflow-Änderungen überleben die Gespräche, die sie hervorbringen. Das ist das Paradigma, das Abschnitt 3 wahr macht.

---

## 17. Readvisors

Ein **Readvisor** ist ein Urteil, das du behalten kannst: mit eigener `AGENT.md` und `MOTIVATION.md`, denselben zwei Dateien, die auch deinen Chef-Readvisor definieren, zugeschnitten auf eine ganz bestimmte Art, ein Problem zu lesen. Pro Projekt im Bereich **Readvisors** der Seitenleiste ein- und ausschalten.

Der oben im Readvisor-Panel ist dein **Chef-Readvisor**, und ab Werk heißt er **Ed**. Diesen Namen darfst du ändern — **Chef-Readvisor umbenennen**, in der Kopfzeile des Broker-Fensters (Abschnitt 9). Der Chef ist keine andere Art Ding als die übrigen; er ist nur derjenige, der antwortet, wenn du niemanden Bestimmten gefragt hast.

**Mehrere Readvisors, eine Stimme.** Schalt drei ein, und du bekommst keine drei Antworten. Im gewöhnlichen Gespräch werden ihre Blickwinkel, ihr Fachwissen und ihre Warnungen in das eingefaltet, was dein Chef sagt — eine Stimme, manchmal aus mehreren gemacht. Treibt ein bestimmter Blickwinkel gerade einen Punkt an, erfährst du meistens, welcher. Willst du sie einzeln sprechen hören, unter eigenem Namen, reihum, dann ist das ein **Rat** (Abschnitt 18).

**Drei Orte, aus denen sie kommen**, und die Zeile in der Seitenleiste sagt, welcher:

- **mitgeliefert** — die beiden unten, die als Links in enoughs eigene Defaults ankommen, wie jeder andere mitgelieferte Baustein.
- **global** — alles in `~/enough/readvisors/`, was dir gehört und was jedes Projekt auf dieser Maschine sieht. Der Ordner wird nie für dich angelegt; er erscheint, sobald etwas zum ersten Mal einen Readvisor hineinlegt. (Das ist der beschreibbare. Der defaults-Ordner in einer Desktop-Installation ist versiegelt.)
- **Projekt** — ein echter Ordner im `rness/readvisors/` dieses Projekts, der allein zu diesem Projekt gehört.

Ein globaler und ein mitgelieferter Readvisor gleichen Namens verlieren gegen einen projektlokalen; die eigene Kopie eines Projekts gewinnt immer, und genau das gibt „anpassen“ seinen Sinn.

**Einen entfernen.** Nicht mitgelieferte Zeilen tragen ein ×. Es fragt vorher, denn es löscht Dateien: der Ordner eines Projekt-Readvisors verschwindet, ein globaler verschwindet aus `~/enough/readvisors/` und aus der Liste dieses Projekts. Was enough mitgeliefert hat, lässt sich so nicht entfernen — da ist nichts zu löschen, was ein Update nicht wieder hinlegen würde. Und ein entfernter Name wird auch aus der Aus-Liste des Projekts gestrichen, damit ein später eintreffender Readvisor gleichen Namens nicht rätselhafterweise ausgeschaltet ist.

### 17.1 block-breaker

Ein Spezialist für Schreibblockaden, destilliert aus den Antworten einer echten Autorin darüber, wie sie das Feststecken auflöst — was genau das ist, was der `readvisory`-Skill (Abschnitt 19.6) tut, und so sieht sein Ergebnis aus. Er diagnostiziert, bevor er verschreibt — Ideenmangel, Mutmangel, Strukturmangel und Erlaubnismangel sind vier verschiedene Probleme —, und greift dann zu Beschränkungen, wiederholungsbasiertem Brainstorming („zehn Varianten, dann eindampfen“), seltsamen Umdeutungen, und, wenn gewünscht, echten nächsten Sätzen. Unnachgiebig anti-defätistisch. Seine Kernüberzeugung: für jeden, der freiwillig schreibt, ist eine Blockade immer lösbar, denn die Regeln wurden erfunden, und das Heilmittel kann genauso erfunden werden.

### 17.2 open-skeptic

Ein „erleuchtbarer Schwarzseher“: echt begeistert von KI, wo sie stark ist, professionell misstrauisch, wo sie überverkauft wird. Herbeirufen, wenn du gerade einen Workflow bauen willst und die Fehlerarten früh benannt haben willst. Er wehrt sich dagegen, KI menschliche Erfahrung nachbilden zu lassen, gegen sich aufschaukelnde Fehlerketten ohne menschliche Prüfung, und gegen flüssige Zuversicht, die die Arbeit von Fachwissen übernimmt — während er KI als Zusammenstellungs-Maschine, Wissens-Prothese und Probepartner bejubelt. Er aktualisiert sich an Belegen: zeig ihm einen Workflow, der funktioniert, und er sagt das, unverblümt.

### 17.3 Eigene bauen

Zwei Beispiele, eine Form. Jeder Readvisor ist dasselbe Paar Markdown-Dateien mit denselben Überschriften: `AGENT.md`, die mit dem Anzeigenamen beginnt, den du in der Seitenleiste siehst, und dann beschreibt, wie diese Person denkt, und `MOTIVATION.md`, die sagt, was ihr wichtig ist, wovor sie schützt, und wo sie danebenliegt. Diese Form wird geprüft, wenn einer installiert wird — nicht, wenn einer geladen wird, ein Readvisor, den du vor Jahren von Hand geschrieben hast, funktioniert also noch genau wie damals.

Du kannst beide Dateien selbst schreiben. Der unterstützte Weg ist der **`readvisory`-Skill** (Abschnitt 19.6), der einen aus dem Urteil eines echten Menschen baut, indem er ihm Fragen stellt — dir, live, oder jemandem, dessen Rat du gern zur Hand hättest, über einen Fragebogen, den du ihm schickst. Readvisors sind der günstigste Weg, eine Lesart hinzuzufügen, die dir fehlt: eine sokratische Gummiente, ein Compliance-Prüfer, deine Zielleserin, die Lektorin, die immer das gefunden hat, was du selbst nicht sehen konntest.

---

## 18. Räte

Ein **Rat** ist eine Composure, auf der deine Readvisors reihum über eine Sache nachdenken, schriftlich, unter eigenem Namen, während du dabei zusiehst. Er ist die andere Hälfte von Abschnitt 17: dieselben Readvisors, die sonst in eine Stimme eingefaltet sind, aufgefaltet, aktenkundig uneinig.

Es ist eine gewöhnliche Composure, alles aus Abschnitt 4 gilt also weiterhin. Der **Auftrag** sitzt oben; jeder Beitrag landet darunter als Karte, überschrieben mit dem Namen des Sprechers und der Zugnummer, in dessen Farbe getönt — dein Chef auf Papier, du in Blau, jeder Readvisor in seiner eigenen Farbe für die Dauer des Rats, der Abschluss in Tinte. Die Spalte räumt sich beim Wachsen selbst auf, wie viel du auch herumgeschoben hast.

Die Beiträge gehören dem Rat, nicht dir. Du kannst sie verschieben, umfärben, kommentieren und herauszoomen und das Ganze als Spalte von Schauseiten lesen — aber du kannst keinen umschreiben, und kein Readvisor kann es auch. Ein Protokoll, das man bearbeiten kann, ist ein Vorschlag, kein Protokoll. Der Auftrag bleibt ein gewöhnliches Modul und bleibt bearbeitbar.

### 18.1 Einen aufsetzen

Neu aus dem **council**-Form, und du bekommst eine Einrichtungskarte mit vier Feldern für den Auftrag:

- **Eingabe** — worüber entschieden wird. Eine Frage, so scharf, wie du sie kriegst.
- **Parameter** — wie du ihn laufen lassen willst. „Zwei Runden, dann entscheiden.“
- **Einschränkungen** — was vom Tisch ist. „Die Prosa nicht umschreiben.“
- **Gewünschtes Ergebnis** — eines von dreien: **eine entschiedene Antwort**, am Ende auf die Leinwand geschrieben; **ein Dokument**, an einen Pfad geschrieben, den du benennst; oder **eine neue Composure**, ein ganzes Brett aus Karten, gebaut aus dem, was der Rat entschieden hat. Wähl Composure, und daneben erscheint ein zweites Bedienelement für die Anordnung — *scaffold*, wo jede Gruppe von Karten eine Spalte ist, oder *cards*, wo jede Gruppe eine Zeile ist. Was jedes davon am Ende tatsächlich tut, steht in 18.3.

Dann der Raum. Die Liste beginnt mit deinem Chef-Readvisor, jedem Readvisor, den du in diesem Projekt eingeschaltet hast, und **dir**; hak ab, wen du nicht dabeihaben willst. Bis zu zwölf, und keine zwei Teilnehmer dürfen denselben Namen tragen, denn ein Beitrag wird namentlich zugeordnet, und zwei Nadias sind kein Rat, sondern eine Verwechslung. **Max. Runden** steht auf 3 und kann alles von 1 bis 20 sein.

Jede Teilnehmerzeile nimmt außerdem einen optionalen **Auftrag**: eine Zeile, die sagt, wofür diese Person da ist. „hütet die Kontinuität.“ „vertritt die Leserin.“ „zweites Paar Augen.“ Er geht in die eigenen Anweisungen dieser Person und in sonst niemandes, als Letztes, nach allem anderen, was ihr gesagt wurde — er ist das Bestimmteste, was sie hat, und das, was ein langes Profil am leichtesten begräbt. Eine Zeile ist die ganze Idee; 200 Zeichen sind die Grenze, und alles Längere kommt abgelehnt zurück, statt stillschweigend gekürzt zu werden, denn ein halber Auftrag ist eine andere Aufgabe. Aufträge reisen außerdem in den Protokoll-Export mit, neben dem Namen, damit eine Leserin Monate später weiß, wer was wozu vertreten hat.

**Einberufen** startet ihn.

### 18.2 Ihn laufen lassen

Sechs Bedienelemente, und sie tun genau das, was sie sagen.

- **Nächster Zug** — ein Beitrag, von dem, der als Nächstes dran ist.
- **Eine Runde laufen lassen** — Züge, bis die Reihe wieder herum ist. Direkt nach dem Einberufen gedrückt, sind das alle; mit einem verbleibenden Platz gedrückt, ist das einer.
- **Bis zum Ende laufen lassen** — Runden, bis dein Maximum erreicht ist, im Hintergrund, mit Zwischenmeldungen.
- **Anhalten** — stoppt nach dem Beitrag, der gerade geschrieben wird. Ein halb fertiger, weggeworfener Beitrag ist die schlimmere Überraschung als ein Absatz zu viel.
- **Der Auftrag** — zurück zur Einrichtungskarte, um zu lesen, woran alle arbeiten, oder um vor dem Abschluss das Ergebnis zu ändern.
- **Abschließen** — der letzte Zug. Das ist 18.3.

Züge strömen herein. Eine Karte erscheint am Fuß der Spalte, mit Name und Zugnummer des Sprechers darauf, füllt sich, während die Worte ankommen, und wird zu einem echten Modul, sobald der Beitrag fertig ist. Die Reihenfolge ist der Chef und dann die Readvisors, wie sie gelistet sind; sie geht herum, und eine Runde schließt, wenn sie sich schließt.

**Du kannst jederzeit etwas sagen.** Das Eingabefeld am Fuß des Rats nimmt deinen eigenen Beitrag, und er geht als Karte hinein wie die von allen anderen, blau getönt. Spricht gerade niemand, landet er sofort; strömt gerade ein Zug, nimmt er den allernächsten Platz und zeigt sich bis dahin als ausstehend. So oder so ist er ein *Einwurf*, keine Umverteilung: der Readvisor, der an der Reihe war, spricht trotzdem als Nächster.

**Du kannst auch einem pal eine Frage stellen.** Ist der Cloud-Slot nutzbar (15.3), tipp `/pal` und deine Frage in das Eingabefeld des Rats — `/pal gibt es einen Namen für das Muster, um das wir kreisen?` — und dein Chef destilliert die bisherige Diskussion und deine Frage zu einem einzigen, für sich stehenden Prompt, schickt den hinaus, und die Antwort landet als Beitrag in eigener grauer Tönung, gesprochen von `pal · <Modell-ID>`. Der Prompt, der den Rechner verlassen hat, ist oben in diese Karte eingefaltet: zusammengeklappt, damit zwanzig Beiträge lesbar bleiben, nie verborgen, einen Klick vom Öffnen entfernt. Wie deine eigenen Beiträge ist er ein Einwurf — er bekommt eine Zugnummer, aber keinen Platz, also spricht der, der gerade an der Reihe war, trotzdem als Nächster, und die Runde rückt nicht vor.

**Das Readvisor-Panel bleibt für die Dauer geschlossen**, mit deaktiviertem Schalter und einem Tooltip, der erklärt, warum (Abschnitt 5.1). Räte und der Chat teilen sich ein Modell, und es gibt nur eines davon, ein Chat-Zug würde sich also entweder hinter dem Rat anstellen oder mit ihm kämpfen. Umgekehrt gilt dasselbe: drückst du ein Rats-Bedienelement, während dein Chef mitten in einer Chat-Antwort steckt, kommt ein Satz zurück, der das sagt, statt still zu warten.

### 18.3 Abschließen: die Antwort, das Dokument, die Composure, das Protokoll

**Abschließen** lässt einen letzten Zug laufen, in dem dein Chef-Readvisor sagt, wo es landet — mit Dank an die Argumente, die den Ausschlag gaben, mit Benennung der Uneinigkeit, die sich nicht aufgelöst hat, statt sie glattzubügeln, und mit dem, was noch offen ist. Dieser Beitrag wird wie jeder andere festgeschrieben, in Tinte getönt.

Was danach passiert, hängt vom **gewünschten Ergebnis** ab, das du bei der Einrichtung gewählt hast:

- **Eine Antwort** — nichts weiter. Diese letzte Karte ist das Ergebnis, und sie liegt auf der Leinwand, wo der Rat ist.
- **Ein Dokument** — der Abschluss wird als Markdown-Datei an einen Pfad in deinem Projekt geschrieben, den du benennst. Das läuft durch dieselbe Tür wie jedes andere Dateischreiben, mit denselben Positivlisten und demselben Rückgängig, und es überschreibt keine bestehende Datei, bevor du die Rückfrage gesehen und Ja gesagt hast. Danach wird unter dem Abschluss ein Link-Modul hinzugefügt, das darauf zeigt, sodass das Dokument einen Klick vom Rat entfernt ist, der es hervorgebracht hat.
- **Eine Composure** — der Abschluss kommt als Gliederung zurück, und enough baut daraus eine neue Composure neben dieser, unter `rness/io/composure/<rat>-output-<datum>.comp`, in der Anordnung, die du bei der Einrichtung gewählt hast. Jede Gruppe ist eine Spalte oder eine Zeile, jede Karte ist ein Stück dessen, was der Rat entschieden hat, und was er *nicht* geklärt hat, kann als offene Frage durchkommen — eine Karte mit dem Titel `[gap: wer verantwortet die Migration?]`, getönt, damit du sie alle auf einen Blick findest. Unter dem Abschluss kommt ein Link-Modul, das auf die neue Datei zeigt, sodass das Brett einen Klick vom Rat entfernt ist, der es hervorgebracht hat. Eine bestehende Datei wird nie überschrieben: eine zweite bekommt `-2`.

Das letzte davon verlangt von einem Modell Überschriften in einer exakten Form, und nicht jedes Modell trifft sie beim ersten Mal. Lässt sich die Gliederung nicht lesen, fragt enough noch einmal, mit ausbuchstabierter Grammatik. Lässt sich auch der zweite Versuch nicht lesen, bekommst du den Abschluss stattdessen als gewöhnliche Antwortkarte, mit einer Zeile, die sagt, dass genau das passiert ist, und es wird keine Datei geschrieben. Die Entscheidung des Rats wird nie weggeworfen, weil die Überschriften schiefgegangen sind — und ein drittes Mal wird nie versucht, denn ein Rat, der schon entschieden hat, sollte nicht zwei weitere Züge für Formatierung ausgeben.

So oder so wird das Ganze außerdem als schlichtes Markdown nach `rness/knowledge/councils/<datum>-<titel>.md` exportiert: der Auftrag, wer im Raum war und wofür jeder da war, die Rundenzahl, und jeder Beitrag der Reihe nach. Ein früherer Export wird nie überschrieben. Ein Rat, der stattgefunden hat, ist etwas, das du durchsuchen, zitieren und jemandem in die Hand drücken kannst, Monate nachdem die Composure irgendwohin verschoben wurde.

Ein abgeschlossener Rat ist fertig. Die Bedienelemente verschwinden, und von da an zeigt er dir den Protokollpfad, das Ergebnis und den Weg, ihn erneut einzuberufen (18.5).

### 18.4 Was es kostet, ehrlich

**Es ist langsam, und das soll es sein.** Jeder Beitrag ist ein vollständiger Modell-Zug — der Teilnehmer liest den Auftrag und alles bisher Gesagte, und schreibt. Vier Teilnehmer über drei Runden sind zwölf Züge, einer nach dem anderen, auf einem lokalen Modell. Es gibt keinen Trick, der das schneller macht, und ein Rat lohnt die Einberufung genau dann, wenn das Nachdenken zwölf Züge wert ist.

**Das Fenster wird gleichmäßig aufgeteilt.** Jeder Teilnehmer, der spricht, bekommt einen gleich großen Anteil am Kontextfenster des Modells — je die Hälfte bei zweien, je ein Viertel bei vieren. Dieser Anteil muss die eigene Identität des Teilnehmers tragen, plus so viel vom Rat, wie hineinpasst. Wird es eng, faltet enough die ältesten Beiträge auf je eine Zeile zusammen, eine Ein-Zeilen-Erinnerung daran, wer was gesagt hat: *Früher in diesem Rat: Ed (Zug 1): …*. Der Auftrag wird nie gefaltet, und der Beitrag, auf den gerade jemand antwortet, auch nicht — ein Teilnehmer, der nicht sehen kann, worauf er antwortet, hat nichts zu sagen.

Dieses Falten ist mechanisch — es nimmt den ersten Satz, es bittet kein Modell um eine Zusammenfassung, denn ein Rat, der Antworten darauf verwendet, sich selbst zusammenzufassen, zahlt zweimal für dasselbe Fenster. Jeder Zug meldet, ob er etwas gefaltet hat. Fängt er früh und oft damit an, ist die ehrliche Abhilfe nicht ein kleinerer Rat, sondern ein größeres Kontextfenster im Modell-Fenster (Abschnitt 15.1) oder ein Modell, in dem Platz dafür ist.

### 18.5 Erneut einberufen

Ein Rat schließt ab, und manchmal die Frage nicht. **Erneut einberufen** startet aus einem abgeschlossenen Rat einen frischen: derselbe Raum — dieselben Teilnehmer mit ihren Namen, Tönungen und Aufträgen —, dieselben Parameter, dieselben Einschränkungen, dasselbe gewünschte Ergebnis und dieselbe Rundengrenze, und ein Auftrag, der der *alte* Auftrag ist plus dem, was der Rat tatsächlich hervorgebracht hat, hingelegt als das, was jetzt auf dem Tisch liegt. Eine Antwort kommt als der Abschluss selbst herüber; ein Dokument oder eine Composure kommt als Verweis auf die Datei und deren erste paar tausend Zeichen herüber. Der neue Rat öffnet sich bereit, bei Zug null, ohne dass jemand gesprochen hätte.

Der alte Rat wird nicht neu gefahren und nicht umgeschrieben. Sein Status, seine Beiträge und sein Protokoll bleiben genau so, wie sie waren; er bekommt ein Link-Modul, das auf seinen Nachfolger zeigt, und der neue eines, das zurückzeigt, sodass sich die Kette von beiden Enden her liest und kein Ende eine Sackgasse ist. Ein Rat wird einmal erneut einberufen — danach ist der Knopf ein Link auf den Rat, der daraus geworden ist.

---

## 19. Skills

Ein Skill ist ein fokussiertes Fähigkeitspaket: ein Ordner mit einer `SKILL.md` (plus optionalen Referenzdokumenten und Skripten), der deinen Readvisors einen Ablauf, ein Vokabular oder eine Disziplin beibringt. Skills pro Projekt in der Seitenleiste ein- und ausschalten. Aus heißt wirklich aus — überhaupt nicht im Prompt — und neue Skills kommen deaktiviert an, sodass sich nichts hinter deinem Rücken ändert. Ein Skill, den enough nicht mitgeliefert hat, wird gelesen, bevor er überhaupt aktiviert werden kann (Abschnitt 19.9). Alles auszuschalten ist auch legitim: reines Gespräch, kein Gerüst, manchmal mehr Raum, damit das Modell dich überrascht.

### 19.1 analyzer

Vier Analysemodi in einem Skill.

**Summarize** erzeugt eine einseitige, ausgewogene Verdichtung jedes Textes: was er sagt, für wen er ist, Motivation und Schlagseiten der Autorin oder des Autors, Ton, Schlüsselzitate.

**Proofread** macht leichtes Lektorat — Tippfehler, Rechtschreibung — über ganze Dokumente bis zu ganzen Büchern, angetrieben von Harper, einem lokalen regelbasierten Grammatikprüfer. Es erzeugt auch einen separaten Korrektur-Bericht mit Vorschlägen und Funden wiederholter Formulierungen, sodass stille Korrekturen und Ermessensentscheidungen unterscheidbar bleiben.

**Decide** gibt dein Dilemma an drei archetypische Personas aus einem eingebauten Kader von zehn weiter, die es öffentlich diskutieren. Du bekommst eine Empfehlung *und* das Protokoll, sodass du die Argumentation abwägen kannst, statt einem Urteil zu vertrauen.

**Audit** liest etwas, dem du noch nicht zu vertrauen beschlossen hast — einen Skill, den dir jemand geschickt hat, einen Readvisor, ein Paradigma — und sagt dir, was es ist. Zuerst eine Erklärung in klarem Deutsch, was das Ding tatsächlich tut und warum du es wollen würdest, dann ein Sicherheitsdurchgang: Prompt-Injection-Versuche, Anweisungen, die die Reichweite eines Readvisors still erweitern, epistemische Warnzeichen, und jeglicher gebündelter Code, der zusätzlich einen deterministischen Scan bekommt, der gar kein Modell einbezieht. Das Urteil ist eines von drei Worten — **pass**, **flag**, **fail** — gestützt von benannten Funden, nie eine Punktzahl. Es ist nur lesend: Audit führt nie aus, bearbeitet, installiert oder aktiviert nie das, was es liest.

Berichte landen in `rness/io/output/analyzer/audits/<skill-name>/`: eine datierte `.md`, die du wie jede andere Datei lesen kannst, plus eine kleine `verdict.json` daneben. Bitte jederzeit namentlich um ein Audit — „prüf das, bevor ich es aktiviere“, „was macht dieser Skill eigentlich“ — und enough lässt diesen Modus auch ungefragt für dich laufen, beim ersten Einschalten eines Skills, den es nicht mitgeliefert hat. Beide Türen schreiben denselben Bericht in denselben Ordner. Abschnitt 19.9 erzählt diese Geschichte.

### 19.2 anything-finder

Ein Suchtrupp für die Dinge, die nicht auf der ersten Seite auftauchen. Drei Gesichter, ein Skill.

**find** ist die Vorgabe, und es trägt ein Playbook für jede von zehn Arten schwer auffindbarer Dinge, plus eine elfte für Missionen, die ins Stocken geraten. **Texte** — gemeinfreie Bücher, Gedichte, historische Dokumente. **Video** — seltene, verlorene und vergriffene Film- und TV-Werke, mit Sichtungs-Links und ihrer angegebenen Rechtslage. **Bilder**, freigegeben für ein Cover oder ein Zine. **Produkte** — obskures Equipment, Synthesizer, Instrumente, und wo man tatsächlich eines kauft. **Artikel** — das Paper hinter einer Paywall, gefunden als seine legitime offene Kopie: Preprint, Repository, Archiv. **Code** — großzügig lizenzierte Repos, einschließlich Bibliotheken, die nie GitHub berührt haben. **Bücher** — Leseempfehlungen, ähnlich dem, was du schon geliebt hast. **Audio** — Notenblätter, MIDI, Samples, Geräte-Handbücher. **Assets** — Schriften, Texturen, 3D-Modelle, Stockmaterial. **Daten** — Datensätze, öffentliche APIs, Regierungsdokumente, Zeitungsarchive.

Ergebnisse kommen als *Find-Karten* zurück: der Link, warum es der richtige Fund ist, und — bei allem Urheberrechts-Sensiblen — warum es zur Nutzung frei ist, mit Erscheinungsdatum oder ausdrücklicher Lizenz ausbuchstabiert. Frag es „finde mir eine gemeinfreie Ausgabe von *The Moonstone*, sauber genug zum Setzen“, „wo kann ich legal die Fassung von 1974 sehen“, „gibt es eine MIT-lizenzierte Bibliothek, die das macht“. Die ehrlichen Antworten gehören zum Deal: „das existiert, ist aber nicht legal verfügbar“ und „drei Kandidaten, ich bin zu 70 % beim zweiten“ sind hier echte Ergebnisse, und wo der einzige Weg eine Piraterie-Seite ist, sagt es das und gibt dir stattdessen die Bibliothek, das Verleihsystem oder den Shop an die Hand.

**patents** ist das Stand-der-Technik-Gesicht. Gib ihm eine Erfindung, und es führt eine strukturierte Neuheitssuche über erteilte Patente, veröffentlichte Anmeldungen und die nicht-patentliche Literatur aus, und berichtet dann, was es gefunden hat und was das für Neuheit und erfinderische Tätigkeit bedeutet — mit einem Kein-Rechtsrat-Hinweis, der in jedem Bericht bleibt, weil das ist, was es ist. „Ist das schon patentiert?“ „Stand der Technik zu einem magnetischen Fahrradschloss, das…“ „Ist meine Idee patentierbar?“ Datenbanken, die es nicht erreichen konnte, kommen als *ungeprüft* markiert zurück, nie still als *leer*.

**venture** ist das „ist das ein Geschäft?“-Gesicht, und es setzt sich aus den anderen beiden zusammen. Eine Markt-Durchsicht dessen, was schon existiert, eine Stand-der-Technik-Prüfung, und ein Durchgang durch die Wettbewerbslandschaft über Firmen, Open-Source-Alternativen, angrenzende Produkte, und den Friedhof derer, die es versucht haben und dichtgemacht haben. Was du bekommst, ist eine ausgewogene Lesart — was überlaufen ist, was angrenzt, was wirklich offen ist, und die Nische, die die Belege tatsächlich stützen — gefolgt vom stärksten Argument *dafür* und dem stärksten *dagegen*, jeder Punkt an einem Link verankert, und eine kurze Liste von Fragen, die nur du beantworten gehen kannst. Frag es „sollte ich das bauen“, „gibt es das schon als Produkt“, „wo ist hier die Marktlücke“. Es wird deine Idee nicht bewerten, deinen Businessplan nicht schreiben, oder dir sagen, Geld einzusammeln. Und es behandelt ein leeres Feld als Frage, nicht als grünes Licht.

Output geht nach `rness/io/output/anything-finder/`. Alles, was es abruft, läuft wie jeder andere Web-Zugriff durch den Broker, eine Domain außerhalb der Positivliste wird also über Tor geleitet — und weigert sich eine Quelle zu antworten, nennt der Bericht den Host und sagt dir, was du zu `allowlists.md` hinzufügen sollst, statt ein stilles Loch in den Ergebnissen zu lassen.

### 19.3 girraph-merirmaid

Der Disziplin-Skill für enoughs zwei Diagramm-Grundformen (Abschnitte 20 und 21). Die girraph-Hälfte lehrt richtiges IBIS-Mapping: eine Frage pro Zug, kein Lösungssprung, deine Bestätigung als Stopp-Regel. Die merirmaid-Hälfte trägt die Mermaid-Schreibregeln, etwa Knotenbezeichnungen kurz genug zu halten, dass du sie bequem bearbeiten kannst. Die Modi funktionieren ohne den Skill; mit ihm wird dein Readvisor zu einem wirklich disziplinierten Mapping-Partner.

### 19.4 lexicographer

Der Hausstil des Wörterbuchs (Abschnitt 13), deinem Readvisor in die Hand gegeben. Dein Chef kann auch bei ausgeschaltetem Skill Wörter nachschlagen und in dein eigenes Wörterbuch aufnehmen — das Wörterbuch ist immer in Reichweite —, aber mit eingeschaltetem Skill reist der ganze Leitfaden, Spalte für Spalte, bei jedem Zug mit: wie eine Aussprache geschrieben wird (weites amerikanisches IPA, mit markierter Betonung), zu welchem von FEEDs 45 Fachgebieten ein Wort gehört, wie eine erste Verwendung formuliert wird („late 18th century“, „2010s“), was die Häufigkeitsstufen bedeuten, wohin die Silbenpunkte kommen. Er trägt auch die Form des Gesprächs — erst nachschlagen, entwerfen, was sich entwerfen lässt, fragen, was nur du beantworten kannst, vorlesen, und erst auf dein Ja aufnehmen —, sodass ein Wort, das deine Familie seit zwanzig Jahren sagt, am Ende aussieht, als hätte es schon immer im Buch gestanden.

Frag ihn „Ist *flumpet* ein Wort?“, „nimm *glimmerwick* in mein Wörterbuch auf“, „meine Version von *draft*, bitte“. Zum Übersetzen von Text ist er nicht da — das ist `translator` —, und ein Korrekturleser ist er auch nicht; das ist analyzer.

### 19.5 memoir-dialectic

Ein geduldiger Memoiren-Mitgestalter über mehrere Sitzungen. Er befragt dich — ein, zwei Fragen zur Zeit, nie eine Flut — und legt alles ab: nummerierte Plandokumente in Gesprächsreihenfolge, ein Index für schnellen Wiedereinstieg, eine Notizdatei für unordentliche Gedanken-Dumps, und schließlich eine Gliederungs-Synthese und, nur wenn du es willst, Entwürfe. Der Ordner ist das Gedächtnis. Du kannst für Wochen oder Jahre verschwinden, und er macht dort weiter, wo du aufgehört hast. Gebaut für die volle Bandbreite von der kompletten Lebensgeschichte bis zu einem einzelnen Meilenstein, mit ausdrücklichem Umgang mit sensiblen Themen und Tabuzonen, und sorgfältiger Bewahrung deiner eigenen Formulierungen — Stimme zählt, besonders wenn ein Entwurf ansteht.

### 19.6 readvisory

Der Skill, der einen Readvisor macht (Abschnitt 17), indem er einen Menschen befragt, statt eine Spezifikation zu schreiben.

Zwei Wege, das zu sammeln. **Live**: er befragt *dich*, geduldig, ein bis zwei Fragen auf einmal, zwölf bis achtzehn insgesamt, dazu, wie du die Art von Sache, um die es bei diesem Readvisor gehen wird, tatsächlich entscheidest. **Fragebogen**: er schreibt eine schlichte, mailfertige Datei, die du jemandem schickst, dessen Urteil du gern zur Hand hättest — einer Freundin, einem Mentor, einer früheren Lektorin, einem Elternteil —, der sie in Ruhe beantwortet, und du fügst die Antworten ein, wann immer sie ankommen. Ein Fragebogen kann eine Woche in einem Posteingang liegen, die ganze Sache wird deshalb in einer Anfrage-Datei verfolgt (Abschnitt 8.3), die eine Sitzung Wochen später kalt aufnehmen kann.

Beide Wege enden gleich: ein kurzer Nachfassdurchgang bei *dir* (der Schritt, der einen Readvisor besser macht als ein Transkript), dann werden beide Dokumente entworfen und dir gezeigt, damit du sie Zeile für Zeile korrigierst, und erst dann, mit deinem Einverständnis, installiert — in dieses Projekt, oder nach `~/enough/readvisors/`, wo jedes Projekt auf der Maschine sie sieht. Beide Dokumente werden von derselben Sicherheitsprüfung gelesen, die ein heruntergeladener Skill bekommt, bevor irgendetwas geschrieben wird, und der Schalter **forge new readvisors** im Broker (Abschnitt 9) entscheidet, ob der letzte Schritt enoughs Sache ist oder deine.

Er hat ein klares Gespür dafür, wofür er nicht da ist. Er benennt deinen Chef-Readvisor nicht um, und er beruft keinen Rat ein: er macht die Teilnehmer, er leitet nicht die Sitzung.

### 19.7 scaffold

Macht aus einem Haufen Denkarbeit eine Struktur, die man sich ansehen kann.

Gib ihm einen Gedankenauswurf — ins Panel eingefügt, eine Datei im Projekt, oder eine Composure, die es schon gibt — und er liest auf Form hin statt auf Sätze. Er kennt Geschichtenformen (Bögen, Beats, Kontinuitätsfäden, Auflösungen, Enden) und Argumentformen (Behauptung, Gründe, Schlussregel, Gegenentwurf, Schluss) und Planformen (Ziel, Phasen, Abhängigkeiten, Risiken, Fertig-wenn). Er stellt höchstens zwei klärende Fragen, oft keine, und übergibt das Ergebnis dann an enough, das es als Composure auslegt: eine Karte je Beat oder Abschnitt oder Phase, gruppiert in Spalten oder Reihen, auf der Leinwand vor dir (Abschnitt 4.5).

Die Regel, die ihn wertvoll macht: **er erfindet nie Material, um ein Loch zu stopfen.** Wo die Struktur etwas braucht, das du nicht geschrieben hast, schreibt er stattdessen eine `[gap: …]`-Karte — orange getönt, mit der Frage darauf —, damit die Form dir zeigt, was du ihr noch schuldest. Eine Geschichte, bei der du das Ende kennst und die Wendung nicht, bekommt eine Lückenkarte, die genau das sagt, und sie ist meistens die nützlichste Karte auf der Tafel.

Er schreibt nicht das Stück. Er schreibt die Struktur, und jede Karte darauf gehört dir zum Bearbeiten, sobald sie landet.

(Ein Name, zwei Dinge, und es lohnt sich, sie einmal auseinanderzuhalten: die *Gerüste*, die das text-planning-Paradigma erzeugt — Abschnitt 16.1 —, sind strukturelle Leitfäden je Abschnitt, als Markdown geschrieben, damit du sie zu Prosa ausbaust. Dieser Skill erzeugt eine ganze Composure. Die beiden verstehen sich gut; ein in text-planning gebauter Plan ist ein guter Gedankenauswurf für diesen hier.)

### 19.8 translator

Offline-Übersetzung über ~419 Sprachen via MADLAD-400 — ein einmaliger ~3-GB-Download, der auf CPU oder Apple Silicon läuft und nie nach Hause telefoniert. Von kurzen Phrasen bis zu ganzen Dokumenten, von großen Sprachen bis zu ressourcenarmen und indigenen. Einen Brief übersetzen, ein README lokalisieren, prüfen, was eine Passage bedeutet, eine Phrase als Bedeutungs-Erhaltungstest durch eine dritte Sprache hin- und zurückschicken — alles bei abgestecktem Netzwerk. Für bestimmte ressourcenarme Sprachen bietet eine optionale NLLB-200-Engine höhere Qualität; sie trägt eine nichtkommerzielle Lizenz, ist also über das translation-Paradigma zum Zuschalten.

### 19.9 Eigene schreiben, und fremden vertrauen

Die acht oben sind Demonstrationen. Der Skill-*Mechanismus* — Markdown-Anweisungen, geladen beim Einschalten, mit einem `description:`, das einem Readvisor sagt, wann er zugreifen soll — ist die eigentliche Funktion. Hausstil-Leitfäden, Fach-Checklisten, wiederkehrende Berichtsformate, Datenverarbeitungs-Abläufe: kannst du eine Kompetenz in Prosa beschreiben, kannst du sie deinen Readvisors als Skill übergeben. Bau deine eigenen mit workflow-design (Abschnitt 16.3), oder zweig einen der acht ab und mach ihn zu deinem.

Das andere Ende dieser Schleife sind die Skills, die von woanders herkommen. Ein Skill ist Anweisungen, denen deine Readvisors folgen werden, was heißt, dass ein Skill aus dem Internet genau so viel Misstrauen verdient wie jede andere Datei aus dem Internet. Also liest enough sie für dich:

- **Was enough mitliefert, ist vertrauenswürdig, und sieht aus wie immer.** Die acht oben kommen als Links in die eigenen Defaults der Installation an. Sie schalten sofort um. Nichts auditiert sie.
- **Alles andere ist aus, bis es gelesen wurde.** Einen Skill-Ordner in `rness/skills/` fallen lassen — heruntergeladen, von einem Freund geschickt, aus einer `.skill` entpackt — und er sitzt dort deaktiviert, in der Seitenleiste als *ungeprüft* markiert. Beim ersten Einschalten lässt enough analyzers Audit-Modus darüber laufen (Abschnitt 19.1), bevor auch nur ein Wort davon einen Readvisor erreicht. Du siehst es in der Zeile passieren: *ungeprüft* → *Audit läuft…* → *geprüft*.
- **Markiert heißt nicht aktiviert.** Findet das Audit etwas, sagt die Zeile *markiert* (oder *fehlgeschlagen*), der Skill bleibt aus, und du bekommst zwei Buttons: **Bericht lesen** öffnet den vollständigen Bericht in der Leseansicht, und **trotzdem aktivieren** bittet um deine Bestätigung und vermerkt die Entscheidung dann als deine — der Fund wird nicht gelöscht, er wird überstimmt, und die Zeile liest von da an *von dir freigegeben*. Das Audit berät. Du entscheidest. (Arbeitest du lieber in der Datei, tut es dasselbe, die `verdict.json` dieses Skills auf `"verdict": "pass"` zu setzen.)
- **Einen Skill bearbeiten, und er wird neu gelesen.** Das Audit ist an die genauen Bytes gebunden, die es gelesen hat — Dateinamen wie Inhalte. Änderst du irgendetwas, wird er beim nächsten Einschalten erneut auditiert. Das gilt auch für einen, den du zuvor trotzdem aktiviert hattest: ein Override beschreibt eine bestimmte Dateimenge zu einem bestimmten Moment, und es übersteht keine Bearbeitung.
- **Ein Skill, der während einer Sitzung für dich geschrieben wurde, zählt auch als nicht vertrauenswürdig.** Das ist Absicht, kein Versehen. Wenn workflow-design eine neue `SKILL.md` nach `rness/skills/` schreibt, auditiert enough diese Hausaufgabe beim ersten Aktivieren. Das geht nahezu augenblicklich, wenn nichts zu finden ist.
- **Läuft kein Modell, kann ein Audit nicht fertig werden** — und es sagt das auch, markiert mit „die LLM-Hälfte des Audits konnte nicht laufen“, statt den Skill einfach durchzuwinken. Ein Modell einschalten und erneut umschalten, oder *trotzdem aktivieren* nutzen, wenn du schon weißt, was drinsteckt.

Berichte leben in `rness/io/output/analyzer/audits/<skill-name>/` — derselbe Ordner, in den analyzer schreibt, wenn du im Gespräch um ein Audit bittest. Zwei Türen, ein Dokument, und es ist eine gewöhnliche Markdown-Datei, die du öffnen, behalten oder löschen kannst.

---

## 20. Girraph-Modus und die Dateiendung `.girraph`

Es wird „graph“ ausgesprochen. Das *ir* ist stumm — es steht für *iterativ* und *rekursiv*. Das Tier ist eine 🦒, und das Tier ist auch stumm.

Ein girraph ist die Karte einer schwierigen Frage. Keine To-do-Liste: ein Bild eines *Widerstreits*, einschließlich der produktiven, die du mit dir selbst hast. Manche Probleme („Sollen wir zu Hause unterrichten?“, „Wovon handelt dieses Buch eigentlich?“, „Nehmen wir die Finanzierung an?“) lassen aus jeder Antwort einen Einwand sprießen und unter jedem Einwand eine neue Frage. Eine Liste begräbt diesen Streit. Ein girraph hält ihn sichtbar:

- ❓ **Fragen** — offene Fragen, immer als Fragen formuliert
- 💡 **Positionen** — mögliche Antworten
- ➕ ➖ **Argumente** — Gründe für und gegen eine Position
- 📄 **Notizen** — Hintergrund, Einschränkungen, Verweise auf Dokumente
- 🦒 **verschachtelte girraphs** — eine Teilfrage groß genug für eine eigene Karte

Die Abstammung ist IBIS, eine Methode aus den 1970ern für „vertrackte Probleme“ — die Art ohne saubere Antwort und ohne natürlichen Haltepunkt. Der girraph ist enoughs Klartext-Auffassung davon.

Das Format ist eine Textdatei, die auf `.girraph` endet, eine Zeile pro Gedanke, lesbar in jedem Editor, 2026 wie 2056:

```
%girraph 0.1
title: Should enough ship a plugin API?

q1 ? Should enough ship a plugin API?
p1 ! Ship a minimal one < q1
a1 + Ecosystem growth needs stable hooks < p1 by:graham
a2 - API surface = forever maintenance < p1 by:open-skeptic
```

`< q1` heißt „das beantwortet q1“; `by:` merkt sich, wessen Behauptung es ist. Keine Datenbank, nichts verborgen. Die Datei ist die Karte.

In der App öffnet ein Klick auf ein `.girraph` den girraph-Modus: einen einklappbaren Baum, den du direkt bearbeitest. Eine Bezeichnung anklicken, um sie umzuschreiben. Über einer Zeile schweben für Buttons zum Hinzufügen, Verknüpfen und Entfernen. Auf einen 🦒-Chip klicken, um in eine verschachtelte Karte abzusteigen — Breadcrumbs bringen dich zurück — und auf einen 📄-Chip klicken, um ein referenziertes Dokument an Ort und Stelle zu lesen. Im Panel „girraph this“ oder „map this out“ sagen, und dein Readvisor bearbeitet dieselbe Datei über dieselben Operationen auf Knotenebene, die du nutzt, sodass ihr beide gleichzeitig an der Karte arbeiten könnt. Knoten zu löschen braucht immer deine Bestätigung, und Kinder werden nie still verwaist.

Ein girraph kann auch einen **merirmaid-Spiegel** wachsen lassen: ein Klick auf den merirmaid-Button in der girraph-Werkzeugleiste erzeugt ein verknüpftes, sich selbst neu erzeugendes Mermaid-Diagramm der Karte — Fragen als Sechsecke, Positionen als Stadion-Formen, Zustimmungen und Einwände in ihren Farben umrandet —, das sich aktuell hält, während sich der girraph ändert. Karten in girraph, Blick in merirmaid.

Drei Gewohnheiten lassen girraphs funktionieren. Fragen als Fragen formulieren („Wie finanzieren wir Jahr zwei?“, nicht „das Geldproblem“). Argumente an Positionen hängen, nicht an Fragen — Gründe sind Gründe für oder gegen eine *Antwort*. Und einen Zweig in eine eigene Datei aufspalten, bevor er ausufert. Den Skill girraph-merirmaid aktivieren, und dein Readvisor wird dich an alle drei halten.

---

## 21. Merirmaid-Modus und die Dateiendung `.merirmaid`

Wo ein girraph ein Argument kartiert, bildet ein **merirmaid** eine Struktur ab. Eine `.merirmaid`-Datei ist ein [Mermaid](https://mermaid.js.org/)-Diagramm — Flussdiagramm, Sequenzdiagramm, Zustandsautomat, ER-Diagramm, alles, was Mermaid zeichnet — mit einem kleinen Frontmatter-Header, live im Browser gerendert. Lokal, natürlich; kein CDN, wie alles in enough.

Zwei Modalitäten, im Header deklariert:

- **wip** — ein Arbeits-Whiteboard. Auf den Text eines Knotens klicken und die Bezeichnung direkt bearbeiten, mit laufender Zeichenzählung; strukturelle Änderungen (eine Box hinzufügen, einen Pfeil neu verdrahten) laufen über deinen Readvisor — frag im Panel. Bitte um ein Diagramm deiner Pipeline, deiner Handlung, deiner Organisation, und dein Readvisor schreibt die Quelle, der Browser zeichnet sie, und du feilst an den Worten.
- **mirror** — ein nur lesbares Spiegelbild einer Struktur, die anderswo lebt: der Inhalt einer Cachebox (Abschnitt 12.1) oder ein girraph (Abschnitt 20). Spiegel erzeugen sich neu, wenn sich ihre Quelle ändert. Um das Bild zu ändern, das Ding ändern.

Diagramme verlinken. Ein Knoten kann auf ein anderes `.merirmaid`, ein `.girraph`, oder ein Markdown-Dokument zeigen, und ihn anzuklicken navigiert dorthin, Breadcrumbs markieren den Weg zurück — sodass eine Reihe von Diagrammen zu einem navigierbaren Atlas deines Projekts wird. Und hat ein Diagramm einen Syntaxfehler, zeigt der merirmaid-Modus den Fehler plus die Rohquelle statt einer leeren Fläche. Es gibt immer etwas, wovon aus man reparieren kann.

Der Skill girraph-merirmaid (Abschnitt 19.3) trägt die Schreibdisziplin für beide Dateitypen. Eine Faustregel daraus ist es wert, hier wiederholt zu werden: wenn der ehrliche erste Schritt eine Frage ist, willst du einen girraph; wenn es eine Box und ein Pfeil sind, willst du ein merirmaid.

---

## 22. Wo es von hier aus weitergeht

Der schnellste Weg, dir enough zu eigen zu machen:

1. Starte es in einem echten Projekt — etwas, das dir tatsächlich wichtig ist.
2. Verbring eine Sitzung mit Reden, und lass das Projektprofil anfangen, sich anzuhäufen.
3. Bearbeite `MOTIVATION.md`, um zu sagen, wofür das Projekt eigentlich da ist.
4. Beim ersten Mal, dass du eine Anweisung wiederholst, halt inne. Steck sie stattdessen in `AGENT.md`.
5. Beim ersten Mal, dass deine Arbeit eine Form hat, die die Defaults nicht treffen, sag „lass uns dafür ein Paradigma entwerfen“ — oder einen Skill, oder einen Readvisor — und lass workflow-design dich durchführen.

Diese Schleife — Reibung bemerken, die Lösung kodieren, weiterarbeiten — ist das ganze Spiel. Die eingebauten Bausteine bringen dich in Gang. Das System, bei dem du landest, liefert niemand mit. Das schreibst du.

---

*enough ist © 2026 Graham Smith, veröffentlicht unter der Apache License 2.0. Der eigene Text des Wörterbuchs — FEEDs Wörter, Definitionen und alles Übrige — ist ebenfalls © 2026 Graham Smith, steht aber nicht unter dieser Lizenz: Er wird zur Verwendung innerhalb von enough mitgeliefert, mit allen Rechten, die vorerst vorbehalten bleiben. Wikipedia-Inhalte, erreicht über wikisink, stehen unter CC BY-SA. Dieses Dokument: auch deins zum Bearbeiten.*
