Hi, hier ist Graham, der Erfinder von enough. Dieses Dokument – diesen Teil hier ausgenommen – wird vor allem von Agenten geschrieben und gepflegt. Ich werde mit ziemlicher Sicherheit hin und wieder ein paar Grahamismen einstreuen, aber die Idee ist, meinen eigenen Drang, unterhaltsames Zeug zu schreiben, nicht der umfassenden Dokumentation in die Quere kommen zu lassen.

# das enough-Hilfe-Center

> Alles, was du mit enough machen kannst, an einem Ort. Geschrieben für enough **0.3.0**, einschließlich des Startbildschirms (jedes Projekt, das du je begonnen hast, in einer Liste, mit einem Weg hinein und einem Weg zurück hinaus — Abschnitt 2), der Konvertierungsrunde (PDFs, Word-Dokumente, E-Books, Präsentationen und Arbeitsmappen öffnen als bearbeitbare Markdown-Zwillinge, mit Export, Sync und einem Bildbetrachter — Abschnitt 6), der Skills-Runde (analyzers neuer Audit-Modus, der Skill `anything-finder`, und das Erstnutzungs-Audit, das jeden Skill liest, den enough nicht mitgeliefert hat, bevor er hereingelassen wird), der Runde vom August 2026 (sieben lokale Modelle mit machbarkeitsgeprüften Installationen, und **enough.app** — die signierte, notariell beglaubigte Desktop-Anwendung), der Interface-Runde vom Juli 2026 (der Modus-Stapel, Hilfeblasen pro Ordner, girraph→merirmaid-Spiegel), und der 0.3.0-Einstellungsrunde (UI- und Textgröße pro Projekt, und die Oberfläche + Hilfe in sechs Sprachen — Abschnitt 9). Wo dieses Dokument und die App vor dir sich widersprechen, hat die App recht und dieses Dokument einen Fehler — Korrekturen willkommen unter [enough.support](https://enough.support).

enough ist ein persönliches Sprachsystem, das auf deinem eigenen Rechner läuft. Du richtest es auf einen Ordner, sprichst mit ihm, und es hilft dir beim Planen, Schreiben, Überarbeiten, Recherchieren und Übersetzen. Die Modelle sind standardmäßig lokal. Deine Dateien bleiben deine. Und fast alles, was du es tun siehst, ist in schlichten Markdown-Dateien festgelegt, die du öffnen, lesen und ändern kannst.

Behalte beim Lesen einen Gedanken im Hinterkopf: **die eingebauten Funktionen in diesem Handbuch sind nur ein Bruchteil dessen, was enough kann.** Die Paradigmen, Rollen und Skills im Lieferumfang sind ein Starterkit — funktionierende Beispiele für drei Anpassungsmechanismen, nicht deren Grenzen. Das Endziel ist, dass du deine eigenen schreibst, oder den Agenten bittest, sie mit dir zu schreiben: ein Paradigma für die Art, wie du Essays planst, eine Rolle, die wie dein härtester Leser argumentiert, ein Skill, der deinen Hausstil kodiert. Abschnitt 3 erklärt, wie. Er ist der wichtigste Abschnitt in diesem Dokument, und das Handbuch wird dich immer wieder dorthin zurückschicken.

---

## 1. Installation, Shortcuts und diese Dokumentation

### 1.1 Was du brauchst

- Ein Mac mit Apple Silicon. (enough wird auf macOS gebaut und getestet. Linux-Unterstützung ist geplant; Windows ist machbar.)
- Plattenplatz für mindestens ein Modell — das kleinste ist etwa 5 GB.
- Keine Konten, keine API-Schlüssel, keine Abos. Sofern du dich nicht später für den Cloud-Modell-Slot entscheidest (Abschnitt 13.2), läuft alles lokal.

### 1.2 Installieren

Zwei Türen, ein Haus.

**Die App — der kurze Weg.** Lade das `enough`-DMG von der Releases-Seite herunter, öffne es, zieh **enough** in den Programme-Ordner und starte es. macOS wird anmerken, dass es sich um eine App aus dem Internet handelt — sie ist signiert und notariell beglaubigt, also ist das der freundliche blaue Dialog mit einem **Öffnen**-Button, einmal, keine Warnung, gegen die du ankämpfen musst. Ein Erststart-Assistent übernimmt von dort: er baut seine eigene Python-Umgebung, zeigt dir die Modellliste mit einem ehrlichen Urteil darüber, was auf *diesen* Rechner passt (Abschnitt 13.1), listet auf, welche optionalen Extras du schon hast, und übergibt dich an den Startbildschirm, um den Ordner zu wählen, in dem du arbeiten willst (Abschnitt 2). Der größte Teil der Wartezeit ist Modell-Download. Kein Terminal, kein Homebrew, kein git.

Die App bringt ihre eigene Inferenz-Engine und Python mit. Die optionalen Extras — Spracheingabe, Webseiten-Abruf, Grammatikprüfung, Übersetzung — sind weiterhin eigenständige Programme; die Extras-Seite des Assistenten nennt jedes einzelne, was ohne es abgeschaltet bleibt, und wie man es bekommt. Nichts ist erforderlich, und nichts installiert sich hinter deinem Rücken. Ein Extra ist gar kein eigenständiges Programm: **PDF-Lesen** installiert sich aus enough heraus, wann immer du willst (Abschnitt 6.8).

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
6. Modellgewichte herunterladen. Jedes unterstützte Modell wird einzeln angeboten, jeweils mit seiner Größe und einer Machbarkeitsprüfung gegen den Arbeitsspeicher und freien Plattenplatz deines Rechners — ✓ heißt komfortabel, ~ heißt knapp, ✗ heißt woanders suchen. Sag ja zu so vielen oder so wenigen, wie du willst; Abschnitt 13.1 beschreibt sie alle, und was du auslässt, ist später eine Ein-Klick-Installation.
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

dann `http://127.0.0.1:3456` besuchen (enough öffnet es für dich). Anderer Ordner, anderes Projekt, anderes Agentengedächtnis. Der eine Ordner, aus dem du nicht starten kannst, ist `~/enough/` selbst — die CLI verweigert sich, weil das die Installation ist, kein Projekt.

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

- **Eingebettete Hilfe** — die `(?)`-Blasen überall in der Oberfläche, jede erklärt, woran sie hängt: ein *Was*, ein *Wie* und eine *Ideen*-Liste. Siehe Abschnitt 9.6.
- **Die Spickzettel** — Tastenkürzel und Markdown-Syntax, einen Klick entfernt im UI-Fenster. Siehe Abschnitt 9.5.
- **[enough.support](https://enough.support)** — das Community-Forum: Installationshilfe, Workflow-Schaufenster, und Leute, die dir gern helfen, die Anpassungen zu bauen, zu denen dieses Handbuch dich immer wieder anstupst.

Und das alles — dieses Handbuch, die Blasen, die Oberfläche drumherum — liest sich in sechs Sprachen: Englisch, Französisch, Spanisch, Deutsch, Chinesisch und Japanisch. Abschnitt 9.4 hat das Dropdown und das Kleingedruckte.

---

## 2. Der Startbildschirm

Bevor du in einem Projekt bist, bist du auf **Start**: ein Rahmen, der jeden Ordner auflistet, den du je zu einem enough-Projekt gemacht hast, plus eine Kachel zum Hinzufügen eines weiteren. Es ist bewusst der ruhigste Bildschirm der Anwendung. Kein Chat, keine Seitenleiste, kein Modell, kein Agent — noch läuft nichts, und über nichts wird nachgedacht. Nur deine Projekte, und der ⚙-UI-Button in der oberen Leiste für das Thema und dieses Handbuch.

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

Diese drei mittleren Spalten sind dieselben drei Anzeigen, die enough in der oberen Leiste zeigt, während du ein Dokument offen hast — ¶ für Absätze (durch Leerzeilen getrennte Blöcke), W für Wörter, C für Zeichen einschließlich Leerzeichen und Zeilenumbrüchen — aufsummiert über das ganze Projekt. Die Regel, *welche* Dateien gezählt werden, ist einen Satz wert, denn sie ist es, die den Zahlen eine Bedeutung gibt: jede Markdown-Datei, die dir der eigene Dateibaum des Projekts zeigen würde, **einschließlich der Zwillinge konvertierter Dokumente** (eine `.docx`, die du hier bearbeitest, ist dein Text), und **nicht** irgendetwas in `rness/` (das Gerüst des Agenten ist nicht dein Buch). Die Zahl in der W-Spalte ist also, nahezu genau, wie viel du geschrieben hast.

Auf eine Spaltenüberschrift klicken, um danach zu sortieren; nochmal klicken, um umzukehren. Projekte ohne etwas zu berichten — nie geöffnet, nie gezählt — sinken so oder so nach unten, statt so zu tun, als wären sie die ältesten. Die Standardreihenfolge ist zuletzt bearbeitet zuerst.

Ein Projekt, dessen Ordner gerade nicht da ist — ein abgestecktes externes Laufwerk, ein Ordner, den du im Finder verschoben hast — wird grau dargestellt, mit dem gemerkten Pfad im Tooltip. Es wird **nicht** aus der Liste entfernt, und es behält die Zählungen, die es beim letzten Mal hatte. Ein Projekt auf einem Laufwerk in der Schublade ist kein verlorenes Projekt.

### 2.2 Ein Projekt anklicken: die Karte

Ein einzelner Klick öffnet kein Projekt. Er zeichnet dir eine **Karte** davon: ein nur lesbares merirmaid-Diagramm (Abschnitt 18) des sichtbaren Inhalts des Ordners, mit einem kleinen Info-Knoten oben, der den Pfad, die Dateizahl, die ¶- und W-Summen trägt, sowie wann das Projekt erstellt, zuletzt geöffnet und zuletzt bearbeitet wurde. Es ist dieselbe Art von Bild, die cacheawl für eine Cachebox zeichnet (Abschnitt 11.1), nur auf ein Projekt gerichtet.

Die Karte ist für den Moment gedacht, in dem du vier Ordner mit plausiblen Namen hast und wissen willst, in welchem die Kapitel stecken. Hinschauen, dann entscheiden.

Hast du dich entschieden, öffnet es der **Projekt öffnen**-Button in der Werkzeugleiste. Esc, oder das Band oben rechts, bringt dich zurück zum Raster. Und wenn du ohnehin schon wusstest, welches du wolltest, **doppelklicke** die Kachel oder Zeile, und es öffnet ohne den Umweg.

Das Öffnen sieht so oder so gleich aus: der Loader erscheint für ein, zwei Sekunden, während enough den Startbildschirm herunterfährt und das Projekt an seiner Stelle hochfährt, und dann bist du in der Gesprächsansicht (Abschnitt 4), genau als hättest du direkt in diesen Ordner gestartet.

### 2.3 Einen Ordner hinzufügen

Die letzte Kachel im Raster — die mit dem Plus — ist, wie ein Ordner zu einem Projekt wird.

Klick sie an, und macOS öffnet seinen eigenen Ordner-Auswähler. Wähl einen beliebigen Ordner mit Notizen, Entwürfen oder Dokumenten; enough fügt ihm `rness/` hinzu (Abschnitt 7), registriert ihn auf deinem Startbildschirm und öffnet ihn. Die Kachel sagt *warte auf den Ordner-Auswähler…*, während der Dialog offen ist, also nimm dir beim Stöbern so viel Zeit, wie du willst.

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

**Überall, App oder Browser:** der Button **Projekt schließen → Start** oben im ⚙-UI-Fenster (Abschnitt 9). Er fragt zuerst, weil Schließen die Sitzung beendet — das Gespräch vor dir ist vorbei, genau wie bei einem Beenden — und landet dich dann genau dort, wo auch ⌘W dich hinbringen würde.

Keins von beiden fasst deinen Ordner an. Deine Dateien, dein `rness/`, deine Anfrage-Dateien und deine Sitzungsprotokolle sind alle genau dort, wo du sie gelassen hast; nur das laufende Gespräch endet.

Eine Folge des neuen ⌘W, die zu kennen sich lohnt, wenn du enough schon eine Weile nutzt: **⌘W schließt das Fenster nicht mehr.** enough ist eine Ein-Fenster-Anwendung, und das Schließen dieses Fensters beendet sie, also deckten ⌘Q und der rote Button dieses Terrain schon ab, und ⌘W hatte eine bessere Aufgabe zu erledigen.

Und eine Wechselwirkung zwischen diesem und der Reopen-Einstellung, denn sonst überrascht sie dich garantiert genau einmal: **ein Projekt zu schließen lässt enough es nicht vergessen.** Ist **Reopen Last Project on Launch** an, und du schließt ein Projekt, bleibst eine Weile auf dem Start und beendest dann — öffnet der nächste Start wieder dieses Projekt, nicht den Start. Der Schalter ist die Einstellung, die entscheidet, wo du beginnst; Projekt schließen ist der Button, der entscheidet, wo du gerade bist. Willst du von jetzt an auf dem Start beginnen, schalte den Schalter aus.

### 2.6 Was der Start sich merkt

Drei kleine Dinge, alle rechnerweit — sie folgen dir von Projekt zu Projekt und zurück zum Start, und sie werden in keinem Projektordner gespeichert:

- **Das Thema und die Schrift** (Abschnitt 9.1). Der Start trägt, was du zuletzt gewählt hast, und ein Thema, zu dem du *auf* dem Startbildschirm wechselst, ist das Thema, in dem dein Projekt öffnet. Das ist der Punkt, der früher genervt hat: der Startbildschirm und der Arbeitsbildschirm sind sich jetzt immer einig.
- **Symbole oder Liste**, aus Abschnitt 2.1.
- **Ob ausgeblendete Projekte angezeigt werden**, aus Abschnitt 2.4.

Alles andere über ein Projekt lebt im Ordner dieses Projekts, wo du es lesen kannst.

---

## 3. Workflow-Anpassung auf einer Kernebene

Wenn du nur einen Abschnitt liest, lies diesen.

Die meiste Software gibt dir Funktionen. enough gibt dir Mechanismen. Persönlichkeit, Methode und Fähigkeiten des Agenten werden bei jeder einzelnen Nachricht neu aus Markdown-Dateien zusammengesetzt, die auf deiner Festplatte liegen:

- **`AGENT.md`** — wer der Agent ist und wie er arbeitet (Abschnitt 4.1)
- **`MOTIVATION.md`** — warum: Werte, Prioritäten, wie sich „fertig“ anfühlt
- **Richtlinien** — feste Regeln darüber, was er lesen, schreiben und abrufen darf (Abschnitt 4.2)
- **Das aktive Paradigma** — das gerade geltende Denkgerüst (Abschnitt 14)
- **Aktivierte Skills** — Fähigkeiten, auf die er zurückgreifen kann (Abschnitt 16)
- **Aktivierte Rollen** — andere Personas, die du herbeirufen kannst (Abschnitt 15)
- **Das Projektprofil** — was er über dieses Projekt gelernt hat (Abschnitt 7.1)

Bearbeite eines davon, in der App oder in einem beliebigen Texteditor, und die Änderung wirkt ab der nächsten Nachricht. Kein Neubau, kein Neustart, keine Plugin-API. Wenn du eine Markdown-Datei schreiben kannst, kannst du deinen Agenten umprogrammieren.

### 3.1 Global vs. projektlokal

Alles Anpassbare folgt einem Muster: **Defaults leben in `~/enough/defaults/`, Projekte verlinken darauf, und jedes Projekt kann den Link aufbrechen.**

Bearbeite eine Datei in `~/enough/defaults/`, und jedes Projekt, das noch damit verlinkt ist, übernimmt die Änderung. In einem Projekt eine verlinkte Datei öffnen und auf **anpassen** klicken — der Link wird zu einer projektlokalen Kopie, und von da an geht dieses Projekt seinen eigenen Weg, während die anderen weiter dem globalen Default folgen. Der Dateibaum zeigt dir auf einen Blick, was was ist: verlinkte Dateien erscheinen *kursiv und gedämpft*, lokale Kopien normal.

Neue Skills, Rollen und Paradigmen, die in `~/enough/defaults/` abgelegt werden, erscheinen beim nächsten Start in jedem Projekt. Skills und Rollen kommen ausgeschaltet an, sodass sich nichts hinter deinem Rücken ändert; du aktivierst sie pro Projekt, wenn du sie willst. Ein Skill, den enough nicht mitgeliefert hat — heruntergeladen, von einem Freund geschickt, vom eigenen Agenten für dich geschrieben — wird gelesen, bevor er hereingelassen wird. Abschnitt 16.6 behandelt das.

### 3.2 Die drei Bausteinarten

| | Paradigma | Skill | Rolle |
|---|---|---|---|
| Was es ist | ein Denkgerüst — wie der Agent an Arbeit herangeht | eine fokussierte Fähigkeit — Vokabular, Rezepte, Abläufe | eine zweite Persona, die du herbeirufen kannst — mit eigener AGENT.md + MOTIVATION.md |
| Wie viele aktiv | immer genau eines | beliebig viele eingeschaltet | beliebig viele eingeschaltet |
| Liegt unter | `rness/paradigms/<name>.md` | `rness/skills/<name>/SKILL.md` | `rness/roles/<name>/` |
| Mitgelieferte Beispiele | default, text-planning, translation, workflow-design | analyzer, anything-finder, girraph-merirmaid, memoir-dialectic, translator | block-breaker, open-skeptic |

### 3.3 Eigene bauen

Du kannst diese Dateien von Hand schreiben — sie sind Markdown mit einem kleinen YAML-Block oben —, aber du musst nicht. Das mitgelieferte **workflow-design-Paradigma** (Abschnitt 14.4) existiert, damit der Agent sie mit dir bauen kann. Sag „bau mir einen Skill, der…“ oder „erstell eine Rolle, die…“ oder „mach ein Paradigma für…“, und der Agent wechselt in workflow-design, stellt seine klärenden Fragen (Umfang? Name? Auslösebedingungen? Begleitdateien?), und schreibt den Baustein richtig, einschließlich des `description:`-Frontmatters, das künftigen Zügen sagt, wann sie darauf zurückgreifen sollen.

Was Leute tatsächlich bauen:

- Ein **Paradigma** für jede eigene Arbeitsweise — Recherche, Entwurf, Überarbeitung — mit ausdrücklichen Regeln, wann gewechselt wird.
- Einen **Skill**, der die Stimme eines Newsletters, ein Zitierformat oder die Terminologie einer Dissertation kodiert.
- Eine **Rolle** als Gummiente, die sokratische Fragen stellt, oder als skeptischer Peer-Reviewer, oder als Fachexperte, gebaut aus deinen eigenen Wissensdateien.

Der Rest dieses Handbuchs beschreibt die eingebauten Bausteine. Lies jeden von ihnen als durchgearbeitetes Beispiel, das du kopieren, abzweigen und verbessern darfst.

---

## 4. Agenten-Gespräch — die Basis des Stapels

Öffne ein Projekt, und du landest in der Gesprächsansicht: die Unterhaltung mit deinem Agenten, plus die Seitenleiste, die dein Projekt zeigt. Das ist das Erdgeschoss. Jeder andere Modus stapelt sich darauf und schließt irgendwann wieder bis hierher herunter. (Der *Startbildschirm* aus Abschnitt 2 ist etwas völlig anderes — dort bist du, bevor ein Projekt offen ist; hier bist du, sobald eines offen ist.)

Was hier ist:

- **Der Chat.** Eine Nachricht tippen, ⌘Enter drücken (oder den Senden-Button). Antworten strömen live herein, und der Agent kann handeln, während er spricht — Dateien lesen und schreiben, Shell-Befehle ausführen, Seiten abrufen —, wobei jeder Tool-Aufruf im Transkript erscheint, sobald er passiert.
- **Der Mikrofon-Button.** Anklicken und diktieren. Sprache wird lokal von whisper.cpp transkribiert; deine Stimme verlässt nie den Rechner. Der Button pulsiert während der Aufnahme. Nochmal klicken zum Stoppen.
- **Die Seitenleiste.** Der Dateibaum des Projekts, plus die Steuerbereiche: das aktive **Paradigma**, Schalter für **Skills** und **Rollen**, und deine **Anfragen**. Option-klick auf eine Datei oder einen Ordner für ein Kontextmenü (neue Datei, neuer Ordner, Pfad kopieren, Name kopieren). ⌘\ blendet die ganze Seitenleiste ein und aus.
- **Die obere Leiste.** Buttons für das Modell-Fenster, den Broker, das UI-Fenster, wikisink (🚰) und cacheawl — und am rechten Rand die Indikatoren für alle Modi, die gerade im Stapel offen sind (Abschnitt 12).

### 4.1 AGENT.md und MOTIVATION.md

Jedes Projekt trägt seine eigene Kopie dieser beiden Dateien in `rness/`. Sie sind die Wurzel der Identität des Agenten, und beide werden bei jedem Zug geladen.

**`AGENT.md`** ist das *Wie*: Arbeitsanweisungen. Ton, Leitplanken, Konventionen, stehende Anweisungen. „Fließtext kleingeschrieben halten.“ „Nie Dateien in `archive/` anfassen.“ „Vor Shell-Befehlen länger als eine Zeile nachfragen.“

**`MOTIVATION.md`** ist das *Warum*: Werte und Prioritäten jenseits der gerade anstehenden Aufgabe. Wofür das Projekt da ist, wem es dient, welche Abwägungen zählen (Korrektheit vor Tempo? Kürze vor Gründlichkeit?), wie sich „fertig“ anfühlt.

Klick eine der beiden Dateien in der Seitenleiste an, um sie zu lesen; drück **anpassen**, um deine projektlokale Kopie abzuzweigen, oder bearbeite sie in einem beliebigen Editor. Änderungen wirken ab der nächsten Nachricht. Rollen nutzen dasselbe Zwei-Dateien-Muster (Abschnitt 15) — der Hauptagent ist nichts Besonderes, nur der Erste.

### 4.2 Der Richtlinien-Ordner und Positivlisten

`rness/policies/` enthält die festen Regeln des Agenten. Nicht Persönlichkeit — Gesetz. Vier Richtlinien werden standardmäßig mitgeliefert:

- **`allowlists.md`** — die Reichweiten-Regeln. Drei Listen:
  1. *Datei-Lese-Präfixe:* absolute Pfade, die der Agent außerhalb des Projekts lesen darf (Standard: `~/enough/`).
  2. *Datei-Lese-Schreib-Präfixe:* Pfade, in die er außerhalb des Projekts auch schreiben darf. Diese Liste kommt **leer**: von Haus aus schreibt der Agent nur innerhalb deines Projekts, und das bleibt so, bis du bewusst einen Pfad hinzufügst.
  3. *Internet-Domains:* Hosts, die direkt abgerufen werden (die Defaults umfassen `gutenberg.org`, `en.wikipedia.org`, `en.wikisource.org`, `archive.org`, `standardebooks.org`, und Kiwix' Download-Host). Eine Domain, die nicht auf der Liste steht, ist nicht blockiert — der Abruf wird stattdessen über einen lokalen Tor-Proxy geleitet, sodass ein Ad-hoc-Abruf deine Adresse nicht in irgendwelchen Server-Logs hinterlässt. Ein Broker-Schalter kann diesen Rückfall abschalten, sodass Abrufe außerhalb der Liste rundweg scheitern.
- **`context-management.md`** — wie der Agent ein sich füllendes Kontextfenster spürt und sauber zurücksetzt, ohne den Zustand zu verlieren (Abschnitt 7.3).
- **`requests.md`** — wann und wie der Agent lang laufende Arbeit als Anfrage-Dateien verfolgt (Abschnitt 7.3).
- **`profile-maintenance.md`** — was ins Projektprofil gehört und was nicht (Abschnitt 7.1).

Richtlinien sind wie alles andere aus den Defaults verlinkt, du kannst die Positivliste also global verschärfen oder sie für ein Projekt anpassen, das eine lockerere (oder strengere) Reichweite braucht. `allowlists.md` zu bearbeiten ist in der Praxis die mit Abstand häufigste Anpassung: die Doku-Seiten hinzufügen, denen du vertraust, einen gemeinsamen Ordner hinzufügen, in den der Agent schreiben können soll, und weiter geht's mit deinem Tag.

---

## 5. Lese-/Bearbeitungsmodus

Klick eine beliebige Datei im Baum an, und sie öffnet im einheitlichen Lese-/Bearbeitungsmodus: ein Modus mit zwei *Seiten* — einer **Leseseite** (das Auge) zum Durchsehen, einer **Bearbeitungsseite** (der Stift) zum Ändern von Text.

### 5.1 Voll vs. Mini, und zwischen allem wechseln

Lesen/Bearbeiten kommt in zwei Größen. **Mini** ist ein Seitenpanel neben dem Chat: ein Referenzdokument griffbereit halten, während du dich unterhältst. (Das Mini-Panel lässt die Review-Werkzeugleiste bewusst weg — es ist zum Lesen und für schnelle Änderungen da, nicht zum Markieren.) **Voll** nimmt den ganzen Rahmen ein, für lange Dokumente und ernsthaftes Bearbeiten.

Größe wechseln über den Mini↔Voll-Button im Panel-Rahmen. Seite wechseln über den Seiten-Umschalter daneben. ⌘S speichert auf der Bearbeitungsseite. Wenn das, was du ansiehst, der Zwilling eines konvertierten Dokuments ist, nennt der Rahmen auch das Original und trägt einen **Export**-Button, um deine Änderungen dorthin zurückzuschreiben (Abschnitt 6.5). Und alles ist schmutz-gesichert: hast du ungespeicherte Änderungen, fragt enough nach, bevor irgendetwas sie verwirft — zu einer anderen Datei navigieren, den Modus schließen, zu einem anderen Dokument springen. Du wirst keine Stunde Arbeit an einen verirrten Klick verlieren.

Während ein Dokument offen ist, erscheinen drei Zähler in der oberen Leiste und halten mit deinem Tippen Schritt: **¶** Absätze, **W** Wörter, **C** Zeichen. (Die Listenansicht des Startbildschirms zeigt dir dieselben drei Summen für ein ganzes Projekt — Abschnitt 2.1.)

Wie jeder Vollbild-Modus zeigt Lesen/Bearbeiten sein Symbol im Indikatorbereich oben rechts, mit einem kleinen rot-x-Band dran zum Schließen (Abschnitt 12).

### 5.2 Markieren

In der Leseseite jedes Markdown-Dokuments Text auswählen und in einer von vier Farben einfärben — **gelb, grün, blau, pink** — über die Werkzeugleiste oder das Popup, das über einer Auswahl erscheint. Dieselbe Werkzeugleiste bietet leichte Formatierung: fett, kursiv, unterstrichen (⌘B / ⌘I / ⌘U).

Markierungen sind dauerhaft, und sie leben außerhalb des Textstroms: jedes Dokument bekommt eine verborgene Begleitdatei (`.<dateiname>.highlights.json`) statt Markup, das in deinen Text gespleißt wird, sodass das Dokument selbst sauber bleibt. Ein farbiges Band am Rand markiert jede markierte Zeile. Markierungen überstehen Sitzungen, und überlappende Farben stapeln sich.

Und hier kommt der Teil, der ändert, wie du arbeitest: der Agent kann sie sehen. Sein `read_highlights`-Tool listet jede Markierung in einem Dokument nach Farbe auf, und `navigate_to_highlight` springt die Ansicht zu einer davon. Das macht Markieren zu einem Kanal. Färb die vier Absätze, die umgeschrieben werden sollen, gelb, und die zwei, die du liebst, grün, dann sag „schreib die gelben Teile um; behalt den Ton der grünen.“ Erwähnst du eine Farbe, weiß der Agent, dass du deine Markierungen meinst.

### 5.3 Unterstützte Dateitypen

- **Markdown (`.md`)** rendert formatiert in der Leseseite und als Quelltext in der Bearbeitungsseite. Markdown ist enoughs Muttersprache — fast alles, was das System selbst schreibt, ist Markdown.
- **Klartext**, und alles Textartige, öffnet in Lesen/Bearbeiten als Text.
- **`.girraph`**-Dateien öffnen stattdessen im girraph-Modus (Abschnitt 17).
- **`.merirmaid`**-Dateien öffnen stattdessen im merirmaid-Modus (Abschnitt 18).
- **Gespeicherte Wikipedia-Artikel** (`article.html` in einem `wiki/`-Ordner) öffnen im wikisink-Reader in voller Wiedergabetreue (Abschnitt 10.2).
- **Word-Dokumente, PDFs, E-Books, Präsentationen, Arbeitsmappen** öffnen als bearbeitbarer Markdown-**Zwilling** — eine Zeile im Baum, ein Klick, und ein **Export**-Button im Rahmen, um deine Änderungen zurückzuschreiben. Das ist Abschnitt 6, und das ist die ganze Geschichte.
- **Bilder** (`.png`, `.jpg`, `.gif`, `.webp`, `.bmp`, `.svg`) öffnen in einem schlichten Betrachter (Abschnitt 6.9). Bilder *innerhalb* eines Dokuments rendern in der Leseseite wie jedes andere Bild in Markdown.

enough ist immer noch ein Textsystem, und es bleibt eines: es rendert Markdown, kein Seitenlayout. Was es mit allem anderen macht, ist es zu konvertieren — verlustarm genug, um darin zu arbeiten, ehrlich genug, um dir zu sagen, was nicht überlebt hat.

---

## 6. Arbeiten mit PDFs, Word-Dokumenten und anderen Dateien

enough rendert kein PDF, layoutet kein Word-Dokument und zeichnet keine Tabelle, und es tut auch nicht so. Was es stattdessen macht, ist leiser und für die Art Arbeit, die du hier machst, nützlicher: es konvertiert das Dokument in Markdown, das du wirklich lesen, bearbeiten, markieren und deinem Agenten übergeben kannst — und es hält dieses Markdown an das Original gebunden, sodass deine Änderungen zurückgehen können.

Nichts daran ist ein eigener Modus oder eine eigene App. Du klickst die Datei an. Sie öffnet.

### 6.1 Der Zwilling

Öffne `memo.docx`, und enough schreibt `memo.docx.md` daneben. Diese zweite Datei ist der **Zwilling**: eine schlichte Markdown-Kopie des Dokuments, in deinem Projektordner, deine zum Bearbeiten wie alles andere. Sie zu erzeugen verändert nie das Original.

Im Dateibaum siehst du weiterhin eine Zeile — `memo.docx`. Der Zwilling, der Ordner mit den aus dem Dokument gelösten Bildern (`memo.docx.assets/`) und eine kleine verborgene Datei, die festhält, was aus was konvertiert wurde, sind alle in diese eine Zeile eingefaltet, sodass dein Projekt weiterhin so aussieht wie im Finder. Klick die Zeile an, und der Zwilling öffnet im Lese-/Bearbeitungsmodus (Abschnitt 5) mit allem, was dieser Modus gibt: zwei Seiten, ⌘S, der Schmutz-Schutz — und, sobald du ins Vollbild gehst, Markierungen.

Zwei Folgen, die zu kennen sich lohnt. Die Benennung kann nicht kollidieren: ein `memo.md`, das du selbst geschrieben hast, ist eine andere Datei als `memo.docx.md`, und enough verwechselt sie nie. Und löschst du `memo.docx` im Finder, bricht nichts — der Zwilling wird still zu einer gewöhnlichen Markdown-Datei in deinem Baum, was er ohnehin schon immer war.

Dein Agent sieht dasselbe wie du. Bitte ihn, `report.pdf` zu lesen, und er bekommt den Zwilling, wobei nötigenfalls erst einer konvertiert wird; bitte ihn, etwas zu ändern, und er bearbeitet den Zwilling, genau dort, wo auch deine eigenen Änderungen hingehen.

### 6.2 Was enough auf diese Weise öffnen kann

Diese Liste stammt aus der App selbst statt aus Fließtext, den irgendjemand aktuell halten muss — liest du das außerhalb von enough, öffne das Hilfe-Center in der App (Abschnitt 9), um sie ausgefüllt zu sehen:

{{convert-formats}}

### 6.3 Das Abzeichen im Baum

Jedes konvertierbare Dokument trägt ein kleines Abzeichen am rechten Rand seiner Zeile, und das Abzeichen hat genau eine Aufgabe: dir zu sagen, ob die beiden Hälften noch übereinstimmen.

- **Still** — konvertiert, und beide Seiten stimmen überein. Nichts zu tun.
- **Leuchtend, in deiner Farbe** — du hast den Zwilling bearbeitet. Diese Änderungen sind im Markdown und noch nicht im Original; exportieren, wenn du bereit bist (Abschnitt 6.5).
- **Leuchtend, in der Farbe des Agenten** — das Original hat sich außerhalb von enough geändert, seit es konvertiert wurde. Jemand hat es in Word bearbeitet; eine neue Kopie ist darübergelandet; es kam von einem gemeinsamen Laufwerk herunter.
- **Leuchtend, in der Fehlerfarbe** — beides zugleich. Das ist der einzige Fall, bei dem enough nachfragt, und das tut es auch (Abschnitt 6.7).
- **Hohl** — konvertierbar, noch nicht konvertiert. Anklicken, und es konvertiert.
- **Hohl, und ein Klick erklärt ein Extra** — ein PDF, eine Präsentation oder eine Arbeitsmappe auf einer Installation, die die noch nicht lesen kann (Abschnitt 6.8).

Über dem Abzeichen schweben, für dasselbe in einem Satz. Das Abzeichen anzuklicken tut genau das, was das Anklicken des Dateinamens tut.

### 6.4 Beim ersten Öffnen

Beim ersten Öffnen jedes Dokument-*Typs* erklärt ein kurzes Modal, was gleich passiert — was ein Zwilling ist, wohin er geht, dass das Original bleibt, wo es ist. Ein OK-Button. Das ist einmal pro Typ, nicht einmal pro Datei: dein zweites Word-Dokument öffnet einfach.

Die Konvertierung eines Office-Dokuments ist schnell, deutlich unter einer Sekunde für alles Typische. Du siehst währenddessen einen kleinen Toast in der Ecke, mit einem **Abbrechen**-Button bei den langsamen. PDFs dauern länger und bekommen einen ehrlichen Fortschrittsbalken (Abschnitt 6.8).

### 6.5 Deine Änderungen zurückexportieren

Ein offener Zwilling trägt einen **Export**-Button in seinem Rahmen. Ein Modal, drei Entscheidungen:

**Welches Format.** Das eigene Format des Originals ist vorausgewählt, und die übrigen Exportziele sind auch da — ein Word-Dokument kann als PDF, EPUB oder eigenständige HTML-Seite hinausgehen. Alles, was das Format nicht kann, wird grau mit dem Grund gezeigt, nie still weggelassen.

**Eine Kopie, oder das Original.** Die Vorgabe ist eine **datierte Kopie**, neben das Original geschrieben — `memo-2026-08-19-1042.docx` — und der genaue Dateiname wird im Modal angezeigt, bevor du bestätigst. Nichts steht auf dem Spiel: du bekommst eine neue Datei, die alte bleibt unangetastet. Die zweite Option überschreibt das Original an Ort und Stelle, und sie wird nur angeboten, wenn das Zielformat des Exports das eigene Format des Originals ist. Wählst du sie, bietet dir enough danach ein **Rückgängig**: die neue Datei behalten, oder die alten Bytes zurücklegen, Byte für Byte.

**Ob es ab jetzt synchron gehalten werden soll** — Abschnitt 6.6.

Ein Wort dazu, was die Reise übersteht. Das Überschreiben einer `.docx` oder `.odt` nutzt das Original als Stil-Referenz, sodass Seitengröße, Schriften und etwaige lebende Kopf- und Fußzeilen mit deinem Text zurückkommen — Dinge, die Markdown nicht ausdrücken kann und die sonst verloren gingen. Was Markdown wirklich nicht tragen kann, kommt nicht zurück: nachverfolgte Änderungen und Kommentare (beim Hereinkommen akzeptiert und fallengelassen), Textboxen, Felder, genaue Bildgrößen. Diese Asymmetrie ist, warum die datierte Kopie die Vorgabe ist, und warum enough ein Original nie aus eigenem Antrieb neu schreibt.

### 6.6 Das Original synchron halten

Hak **das Original synchron halten** im Export-Modal an, und jedes Speichern des Zwillings schreibt still auch das Original neu. Bearbeite in enough, und die `.docx` auf deiner Festplatte ist aktuell, wann immer ein Kollege danach fragt. Es ist eine Einstellung pro Datei, sie greift in dem Moment, in dem du sie ankreuzt, und eine kleine Bestätigung erscheint jedes Mal, wenn ein Speichern durchgeht.

Es wird für die Formate angeboten, die sich zurückschreiben lassen — Word, OpenDocument, Rich Text, EPUB; die Spalte „synchron halten“ in Abschnitt 6.2 hat das letzte Wort. PDFs können nicht mitmachen, und der Grund ist es wert, klar ausgesprochen zu werden: enough kann ein PDF aus Markdown *schreiben*, aber es setzt das Dokument von Grund auf neu. Ein synchronisiertes PDF würde dein sorgfältig gestaltetes Original bei jedem Speichern durch einen schlichten Neusatz seiner Worte ersetzen. Das ist kein Sync, das ist ein Abriss, also wird es nicht angeboten.

### 6.7 Wenn sich beide Seiten geändert haben

Das Original kann sich ohne dich weiterbewegen. Du bearbeitest den Zwilling hier; jemand bearbeitet die `.docx` in Word; jetzt gibt es zwei Versionen der Wahrheit.

enough bemerkt das. Es vergleicht das Original mit dem, was es zum Zeitpunkt der Konvertierung festgehalten hat, in jedem Moment, der zählt — wenn der Baum gezeichnet wird, wenn du das Dokument öffnest, wenn du speicherst, wenn du exportierst — und eine Datei, die nur *angefasst* wurde (kopiert, gesichert, geöffnet und geschlossen), zählt nicht: die Prüfung liest Inhalte, nicht nur Zeitstempel.

Haben sich beide Seiten wirklich geändert, bekommst du ein Modal mit drei Möglichkeiten in klaren Worten:

- **Meinen Zwilling behalten.** Es wird nichts geschrieben. Das Abzeichen geht zurück zu „du hast es geändert“, und du entscheidest später.
- **Über das Original exportieren.** Dein Markdown gewinnt; das Original wird neu geschrieben, mit einem Rückgängig wie üblich.
- **Vom Original neu konvertieren.** Das Original gewinnt; ein frischer Zwilling wird geschrieben — und dein alter Zwilling wird daneben als Rückgängig-Datei aufbewahrt statt gelöscht.

Keine Wahl in diesem Modal zerstört etwas, das du nicht zurückbekommen kannst. Das ist die Design-Regel, auf der die ganze Funktion aufgebaut ist.

### 6.8 PDFs, Präsentationen und Arbeitsmappen lesen: das PDF-Extra

Ein PDF zu lesen ist ein schwierigeres Problem als eine Word-Datei zu lesen. Eine `.docx` weiß immer noch, was eine Überschrift ist; ein PDF weiß nur, wohin die Tinte ging, und eine Tabelle, ein zweispaltiges Layout oder einen Scan wieder herauszuholen, braucht echte Dokumentmodelle. Diese Modelle sind groß, also sind sie nicht in der Basisinstallation — stattdessen sind sie einen Klick entfernt: **⚙ UI-Fenster → Extras → PDF-Extra installieren**.

Was es ehrlich kostet:

- rund **250 MB Download**, und rund **1 GB auf der Platte** nach der Installation;
- dazu etwa **0,7 GB Modellgewichte**, einmalig geholt und in `~/enough/weights/docling/` behalten;
- ein paar Minuten, das meiste davon Download. Der Installer streamt sein Log ins Fenster, damit du zuschauen kannst, und die Engines schalten sich live ein — kein Neustart.

Was du bekommst: **PDFs**, auch gescannte (der Text wird per OCR aus den Pixeln gelesen); **PowerPoint-Präsentationen**, deren Folien zu Abschnitten mit Überschrift werden; und **Excel-Arbeitsmappen**, deren Tabellenblätter zu Markdown-Tabellen werden.

Geschwindigkeit, gemessen statt geschätzt, auf Apple Silicon: etwa **0,9 Sekunden pro Seite** für ein digitales PDF, dazu ein einmaliges **~10-sekündiges** Modell-Laden pro Konvertierung. Ein einseitiges PDF dauert also etwa zehn Sekunden, ein hundertseitiges Buch etwa anderthalb Minuten, und eine Präsentation oder Arbeitsmappe ein paar Sekunden. Lange Konvertierungen zeigen Fortschritt und lassen sich abbrechen; Abbrechen hinterlässt nichts — kein halb geschriebener Zwilling, keine verirrten Ordner.

Zwei Dinge ersparen dir später einen ratlosen Moment. Erstens: **PDFs schreiben braucht nichts davon.** Jeder Zwilling exportiert auf jeder Installation zu PDF, mit oder ohne Extra, weil der Schriftsetzer dafür mit enough mitkommt. Das Extra ist zum *Lesen*. Zweitens: erscheint die Meldung „braucht ein Extra“ auf einem Rechner, auf dem du sicher bist, es installiert zu haben, lies genau, welchen Satz du bekommen hast — die Pakete und die Modellgewichte sind zwei getrennte Downloads, und eine Verbindung, die mitten im Abruf abgebrochen ist, kann dir den ersten ohne den zweiten hinterlassen. Die Installation erneut laufen zu lassen, beendet den Job und lädt nichts neu herunter, das du schon hast.

Updates behalten das Extra. `update-enough.command` (und `/update-enough`) merken sich, was du installiert hast, und fragen bei jedem Sync erneut danach, sodass ein Routine-Update PDF-Lesen nie still wieder wegnimmt.

### 6.9 Bilder, und einen Blick aufs Original werfen

Klick ein Bild an, und es öffnet in einem schlichten Betrachter: standardmäßig auf Breite eingepasst, anklicken zum Wechsel auf tatsächliche Größe und Herumscrollen, ein Schachbrettmuster hinter allem Transparenten, und Name, Pixelmaße und Dateigröße im Kopfbereich. Er ist nur lesbar. enough ist kein Bildeditor und hat dort keine Ambitionen.

Bilder *innerhalb* eines Dokuments sind eine andere Sache, und sie kommen mit herüber: das Foto in deiner Word-Datei wird nach `memo.docx.assets/` extrahiert und rendert in der Leseseite des Zwillings genau wie jedes andere Markdown-Bild.

Und wenn der Zwilling nicht reicht, trägt der Rahmen eines PDFs **Original ansehen**: er öffnet das tatsächliche PDF im Panel, sodass du den Zwilling gegen die echte Seite prüfen kannst. Schließen, und du bist zurück im Zwilling, wo du aufgehört hast.

### 6.10 Was Konvertierung dich kostet, in zwei Sätzen

Zwei Grenzen sind es wert, laut benannt zu werden, statt dich sie entdecken zu lassen. Die Tabellenblätter einer Arbeitsmappe kommen als Tabellen Rücken an Rücken an, **ohne Blattname-Überschriften** — der Reader gibt sie nicht aus, und enough lässt lieber eine Lücke, als eine Bezeichnung zu erfinden. Und ein aus einem PDF gezogenes Bild bekommt jedes Mal den Alt-Text „Image“: es gibt keine Bildunterschrift in der Datei, um ihm eine bessere zu geben.

Darüber hinaus das stehende Versprechen: **deine Originale werden nie verändert, außer du verlangst es.** Konvertieren schreibt immer nur neue Dateien daneben. Export-Überschreiben ist der einzige Weg, der ein Original anfasst, er braucht einen bewussten Klick, und er hinterlässt dir ein Rückgängig.

---

## 7. Der Projektordner und `rness/`

Ein Projekt ist ein Ordner. Jeder beliebige Ordner. enough fügt ihm genau eine Sache hinzu: `rness/`, das externalisierte Gehirn des Agenten für dieses Projekt. Alles, was der Agent hier ist, weiß und sich merkt, lebt in diesem Ordner als gewöhnliche Dateien. Du kannst alles davon lesen, alles davon bearbeiten, und es unter git stellen, falls das deine Gewohnheit ist.

Der Aufbau:

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

Verlinkte Einträge (kursiv im Baum) folgen den globalen Defaults; jeden davon anpassen, um eine lokale Kopie abzuzweigen (Abschnitt 3.1). Dateien, die du auf beliebige Weise ins Projekt legst — Finder, ein anderer Editor, der Agent — sind beim nächsten Zug für alle gleichermaßen sichtbar.

Ein konvertiertes Dokument (Abschnitt 6) fügt auch hier Dateien hinzu, immer neben dem Original und immer nach ihm benannt: `memo.docx` bekommt einen Zwilling unter `memo.docx.md`, seine Bilder in `memo.docx.assets/`, und eine verborgene `.memo.docx.convert.json`, die festhält, was wann aus was konvertiert wurde. Der Baum faltet alle drei in die Zeile des Originals, aber es sind gewöhnliche Dateien auf deiner Platte — du kannst das Paar auf einen anderen Rechner kopieren, unter git stellen, oder den Zwilling löschen und das Original nochmal anklicken, um einen frischen zu bekommen. Das verborgene Manifest ist enoughs Buchhaltung; lass es in Ruhe, und es bleibt korrekt. Lösch es, und enough behandelt das Dokument einfach so, als wäre es nie konvertiert worden.

### 7.1 Der Wissen-Ordner

`rness/knowledge/` ist projektbezogenes Gedächtnis.

**`project-profile.md`** ist die nützlichste Datei im Ordner. Ihr Inhalt wird bei jedem Zug in den System-Prompt des Agenten eingespeist: was auch immer hier steht, ist im Arbeitsgedächtnis des Agenten, kein Nachschlagen nötig. Der Agent pflegt sie, während ihr arbeitet — beobachtete Vorlieben, wiederkehrende Dateien und Personen, übernommene Konventionen, offen gelassene Fäden — und du kannst sie direkt bearbeiten. Eine stehende Vorliebe einmal im Profil festhalten, statt sie jede Sitzung zu wiederholen. Die profile-maintenance-Richtlinie hält die Datei diszipliniert: konkrete Beobachtungen statt vager Etiketten, Destillat statt Archiv.

**`session-logs/`** enthält ein datiertes Markdown-Protokoll der Züge jeder Sitzung, plus das Journal des Brokers (Abschnitt 8). Nur anhängende Historie. Durchstöbere sie, oder grep sie, wenn du rekonstruieren musst, was letzten Dienstag passiert ist.

Über diese beiden hinaus gehört der Ordner dir. Füg einen `glossary/`-Unterordner hinzu, eine Lessons-Learned-Datei, Hintergrundnotizen — der Agent kann alles zurate ziehen, was du hier ablegst.

### 7.2 Der io-Ordner

`rness/io/` ist der Durchgangs-Arbeitsbereich:

- **`input/`** — Dateien hier ablegen, damit der Agent sie verarbeitet. Abgerufene Webseiten landen auch automatisch hier, zu Markdown konvertiert und zwischengespeichert, sodass eine einmal abgerufene Seite für immer als Grundlage verfügbar bleibt.
- **`output/`** — wo erzeugte Artefakte landen. Sichten, behalten, was gut ist, den Rest löschen.
- **`cloud-cache/`** — nutzt du den Cloud-Modell-Slot, wird jeder Cloud-Austausch hier festgehalten (Abschnitt 13.2). Selbst Cloud-Arbeit hinterlässt eine lokale, mit grep durchsuchbare Papierspur.

### 7.3 Anfragen: wie lange Aufgaben überleben

Dieser Punkt schafft es selten in die Schnelleinstieg-Touren, aber er ist der Mechanismus, der Arbeit über mehrere Sitzungen hinweg möglich macht, also sind zwei Minuten gut investiert.

Bittest du um etwas, das mehr als ein, zwei Züge dauert, öffnet der Agent eine **Anfrage-Datei** in `rness/requests/`: ein Markdown-Protokoll des Ziels, der Fortschritts-Checkpoints und der unterwegs getroffenen Entscheidungen. Darum musst du nicht extra bitten. Die Form einer Aufgabe zu erkennen, ist der Job des Agenten.

Die Anfrage-Datei zählt, weil Kontextfenster sich füllen. enough beobachtet den Gesprächsdruck, und — gemäß der context-management-Richtlinie — checkpointet der Agent seinen Zustand in die aktive Anfrage-Datei, bevor es überläuft. Je nach deiner Orchestrator-Einstellung setzt enough dann entweder automatisch zurück (löscht das Gespräch im Arbeitsspeicher und setzt frisch vom Checkpoint fort) oder pausiert mit einem Banner, damit du zurücksetzen kannst, wenn du bereit bist. So oder so ist das Dateisystem das eigentliche Gedächtnis, nicht das Gespräch: eine frische Sitzung liest den Continuation-Block der Anfrage-Datei und macht dort weiter, wo der Stand war.

Erledigte Anfragen wandern nach `rness/requests/done/` — klick **erledigt markieren** bei einer offenen Anfrage, oder sag es dem Agenten. Der done-Ordner ist für den Agenten schreibgeschützt, und er dient zugleich als ehrliches Journal von allem, was ihr beide tatsächlich abgeliefert habt.

---

## 8. Das Broker-Fenster

Der Broker ist enoughs Vertrauensanker. Jeder Tool-Aufruf, den der Agent macht — jedes Dateilesen, Dateischreiben, jeder Shell-Befehl und Web-Abruf — läuft durch ihn hindurch. Das 🔀-Broker-Fenster ist, wo du das beobachtest und einstellst.

Elf Schalter, in Gruppen:

| Schalter | Was er steuert |
|---|---|
| trace log | ob der Broker sein Journal überhaupt schreibt |
| local models only | ob der Cloud-Slot (OPRO-API) in der Modellauswahl überhaupt angeboten wird |
| read_file / write_file / shell brokered | Protokollierung pro Tool, je ein Schalter — drei insgesamt (die Positivlisten gelten *immer*, unabhängig davon) |
| fetch_url enabled | ob das Web-Abruf-Tool des Agenten überhaupt funktioniert |
| Tor for off-list fetches | Domains außerhalb der Positivliste: über Tor leiten (an) oder verweigern (aus) |
| cache & convert fetches | abgerufene Seiten zu Markdown konvertieren und in `rness/io/input/` zwischenspeichern |
| wikisink tools | ob die vier Wiki-Tools des Agenten funktionieren (dein eigenes 🚰-Browsen wird nie gesperrt) |
| wikisink live updates | ob Update-Läufe überhaupt Wikipedia kontaktieren dürfen (aus = Bericht nur aus lokalem Zustand) |
| cacheawl tools | ob die Cachebox-Tools des Agenten funktionieren (dein eigener cacheawl-Modus wird nie gesperrt) |

Standardmäßig ist alles an: die Defaults vertrauen dem Agenten das Projekt an und halten ihn mit einer Papierspur ehrlich. Diese Spur — das **Trace-Journal** — landet in `rness/knowledge/session-logs/<datum>-broker.md`: Zeitstempel, Tool, Entscheidung, Argumente, Ergebnis, für jeden vermittelten Aufruf. Und blockiert ein Schalter oder eine Positivliste etwas, bekommt der Agent eine klare Ablehnungsmeldung, die sagt, was blockiert wurde und warum, sodass er es dir sagen kann, statt still zu scheitern.

Beachte das Design-Prinzip in dieser Tabelle: Schalter, die die Tools des Agenten sperren, sperren nie *deine* Oberfläche. cacheawl tools auszuschalten schließt dich nicht aus dem cacheawl-Modus aus. Es heißt, dass der Agent nicht von sich aus in den Speicher greifen kann.

---

## 9. Das UI-Fenster und die Hilfedokumente

Der ⚙-UI-Button öffnet die Anzeigeeinstellungen und das Referenzmaterial. Ein kleiner **Hilfe**-Button sitzt oben rechts in diesem Fenster, neben dem ×: er öffnet dieses Handbuch nur lesbar, in der App, als Vollbild-Modus wie jeder andere (Abschnitt 12).

Der Weg hinaus reitet jetzt auf der Titelleiste mit: **Projekt schließen → Start**, oben neben dem Hilfe-Button, das diese Sitzung beendet und dich zum Startbildschirm zurückbringt (Abschnitt 2.5). Es fragt, bevor es das tut, und es vermerkt, was es nicht tut — der Ordner auf der Festplatte bleibt unangetastet. In der App würdest du eher zu ⌘W greifen; dieser Button ist dasselbe, und er ist der *einzige*, wenn du enough im Browser laufen lässt. (Er ist nicht auf dem Startbildschirm selbst da, wo es kein Projekt zum Schließen gibt.)

Es enthält auch das eine Ding in enough, das du aus enough heraus installieren kannst: die **Extras**-Zeile für **PDF-Lesen** (Abschnitt 6.8). Die Zeile sagt, wo du stehst — nicht installiert, wird installiert, installiert, oder installiert, aber nicht fertig — und der Installieren-Button streamt sein ganzes Log ins Fenster, während er läuft, sodass ein langer Download etwas ist, dem du zusehen kannst, statt es nur abzuwarten. Ist er fertig, fangen PDFs an zu öffnen; nichts muss neu gestartet werden.

### 9.1 Themen

Vier werden mit enough mitgeliefert: **Enough Default** (tiefes Blauviolett-Dunkel), **Pastel** (blasses Papier, im Geiste des Terminal-Farbschemas „Man Page“), **Wireframe** und **Darknest**. Der Wechsel geschieht sofort, und jedes Symbol in der Oberfläche leitet seine helle oder dunkle Variante spontan neu ab.

Themen sind nicht fest verdrahtet. Sie leben in `~/enough/config/ui.json` als benannte Blöcke von Farbwerten, jeder als CSS Custom Property angewendet. Einen bestehenden Block kopieren, umbenennen, die Farben ändern, neu laden: dein Thema ist im Dropdown. Der `_doc`-Block oben in der Datei erklärt jeden Schlüssel.

### 9.2 Schriften

Dasselbe Muster. Vier mitgelieferte Stacks — SF Mono, System-Sans-Serif, Georgia Serif, Courier — und eigene Ergänzungen sind willkommen, in derselben `ui.json`. Für die Größe siehe die beiden Regler unten (Abschnitt 9.3) — und in einem Browser-Tab funktioniert obendrauf immer noch ganz gewöhnlicher Browser-Zoom (⌘+ / ⌘−).

### 9.3 Größe — UI-Größe und Textgröße

Browser-Zoom war hier immer die Antwort, bis die Desktop-App ohne einen Browser drumherum ankam. Also wuchs enough sich einen eigenen, und nutzte die Gelegenheit, es noch etwas besser zu machen: zwei Regler statt einem, in der Zeile unter dem Thema.

**UI-Größe** skaliert *alles* — Symbole, Beschriftungen, die Seitenleiste, den Chat, genau dieses Fenster — in Schritten von 0,1×. **Textgröße** skaliert nur das Dokument vor dir: die Seite in Lesen/Bearbeiten, einen wikisink-Artikel, die Dateivorschau, dieses Handbuch in seinem Referenzmodus. Sie multiplizieren sich, und sie stören sich nicht: eine 0,9×-Oberfläche um 1,5×-Text herum ist ein durchaus guter Weg, ein Manuskript zu lesen, und umgekehrt ein durchaus guter Weg, eines aus dem Weg deines Nachmittags zu schrumpfen. Auf eine der beiden Zahlen klicken, um diesen Regler auf 1,0× zurückschnappen zu lassen und den anderen in Ruhe zu lassen.

Beide werden **pro Projektordner** gemerkt — das Manuskript, das du quer durchs Zimmer liest, und die Notizen, die du am Schreibtisch führst, halten jeweils ihre eigenen Größen, und keine zieht die andere mit. Der Startbildschirm bleibt bei schlichter Größe, die Regler erscheinen dort also nicht.

Die Grenzen atmen mit deinem Bildschirm: grob 0,5× bis 2× auf heutigen Displays, enger in einem kleinen Fenster, damit die Oberfläche immer genug Raum behält, um sie selbst zu sein, weiter auf sehr großen, sehr dichten Bildschirmen (die 8K-Wand von 2046 bekommt 3×). Würde ein Schritt die Grenze überschreiten, wackelt der Button, die Zahl pulsiert rot, und nichts ändert sich — das ist die ganze Fehlermeldung.

### 9.4 Sprachen

Die Oberfläche spricht sechs: Englisch, Französisch, Spanisch, Deutsch, Chinesisch und Japanisch. Das Dropdown **UI-Sprache** in derselben Zeile schaltet alles um, was du gerade siehst — Beschriftungen, Tooltips, die `(?)`-Blasen, dieses Handbuch — live, ohne Neustart. Die Wahl gilt rechnerweit, sie reitet auf `ui.json` genau wie das Thema, sodass der Start und jedes Projekt sich darüber einig sind.

Was sie bewusst *nicht* anfasst: deine Dateien, deinen Chat, deinen Agenten. Sprich mit dem Agenten in welcher Sprache auch immer dir zusagt — die lokalen Modelle sind in allen sechs sicher unterwegs —, aber enough hält sein eigenes Gerüst (Skills, Paradigmen, Prompts, Projektdateien) auf Englisch, weil das die Sprache ist, die die Modelle am zuverlässigsten lesen. Ein paar erzeugte Dinge bleiben ebenfalls Englisch — Listen, live aus dem gezogen, was auf *deinem* Rechner installiert ist, wie die Skills in einer Blase oder die Dateiformat-Tabelle. Und überall, wo eine Übersetzung mit einer neuen englischen Beschriftung nicht mitgekommen ist, siehst du das Englische statt einer Leerstelle: weniger hübsch, nie kaputt. Eine entdeckt? Das ist ein Fehler — [enough.support](https://enough.support) freut sich darüber.

### 9.5 Spickzettel

Zwei Spalten Referenz, direkt im UI-Fenster.

**Tastenkürzel:**

| Tasten | Aktion |
|---|---|
| esc | den obersten offenen Modus schließen |
| ⌘ \ | Seitenleiste zeigen / verstecken |
| ⌘ K | die Chat-Eingabe fokussieren |
| ⌘ Enter | die Nachricht senden |
| shift Enter | Zeilenumbruch statt Senden |
| ⌘ B / I / U | Auswahl fett / kursiv / unterstrichen (Leseseite) |
| ⌘ S | speichern (Bearbeitungsseite) |
| ⌥ click | Kontextmenü des Dateibaums |

(Auf einer Nicht-Mac-Tastatur: Ctrl für ⌘, Alt für ⌥.)

Das sind die Tastenkürzel, die die Oberfläche selbst handhabt, sie funktionieren also in der App wie in einem Browser-Tab gleichermaßen. Die App fügt zwei eigene aus der Menüleiste hinzu: **⌘W** schließt das Projekt und bringt dich zurück zum Startbildschirm (Abschnitt 2.5) — es schließt das Fenster *nicht* mehr — und **⌘Q** beendet, wie es das immer schon tat.

**Der Markdown-Spickzettel:** Überschriften, Listen, Links, Code, Zitate — die ganze Kurzreferenz, für alle, die noch flüssig in Markdown werden. Was sich lohnt, denn enough spricht es überall nativ.

### 9.6 Eingebettete Hilfe (IHH)

Die `(?)`-Blasen, verstreut über die Oberfläche, sind das eingebaute Hilfesystem: eine Blase pro Konzept — Skills, Rollen, der Paradigmen-Wähler, rness, io, Wissen, cacheawl, wikisink, das Modus-System, konvertierte Dokumente, und so weiter — jede mit einem **Was**, einem **Wie** und einer **Ideen**-Liste. Die Skills-, Rollen- und Paradigmen-Blasen listen, was tatsächlich in *deinem* Projekt installiert ist, und die Blase zu konvertierten Dokumenten zieht ihre Dateitypen-Tabelle aus der eigenen Format-Registry der App — alles live erzeugt, sodass Hilfe nie aus dem Takt mit der Wirklichkeit gerät. (Dieselbe Tabelle erscheint in Abschnitt 6.2 dieses Handbuchs, aus derselben Quelle.)

Blasen werden pro Projektordner über die Checkbox „Hilfeblasen (?)“ im UI-Fenster gesteuert. Standardmäßig an für einen neuen Ordner, und die Einstellung bleibt pro Ordner haften — sodass dein eingespieltes Alltagsprojekt still werden kann, während ein frisches Experiment seine Stützräder behält.

Sogar die Hilfe selbst ist anpassbar. Der Inhalt lebt in einer Markdown-Datei (`enough/static/help-docs.md`); sie zu bearbeiten bearbeitet die Blasen.

---

## 10. Wikisink

Wikisink (🚰) legt eine Offline-Kopie der englischen Wikipedia auf deinem Rechner an: durchsuchbar in der App, volltextsuchbar, lesbar für den Agenten, kommentierbar, und auf Wunsch mit einem Änderungsbericht aktualisierbar. Nach der Einrichtung braucht es überhaupt kein Internet mehr.

### 10.1 Einrichtung

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

Einmal installiert, öffnet 🚰 den Reader: zurück und vor, live Titelvorschläge im Suchfeld (Enter führt eine Volltextsuche über das ganze Archiv aus), ein 🎲-Zufallsartikel-Würfel, und ein Quellen-Abzeichen, das dir sagt, ob du den Archiv-Snapshot liest (`ZIM <Datum>`), eine frischere Kopie aus einem Update-Lauf (`live <Datum>`), oder eine bewahrte Kopie (`preserved`). Interne Links bleiben in der App; externe Links öffnen in deinem Browser. Die Chat-Pille unten übergibt den aktuellen Artikel — oder deine ausgewählte Passage — direkt an den Agenten.

**Die Neuerer-Snapshot-Pille.** Kiwix baut diese Archive regelmäßig neu, und du solltest dafür nicht suchen müssen. Existiert ein neuerer Build *deiner* Variante, erscheint eine kleine Pille in der Reader-Werkzeugleiste — `neuerer Snapshot: <Datum> · <Größe>`. Anklicken, die Größe bestätigen, und das Upgrade läuft an Ort und Stelle: derselbe Speicherordner, erst heruntergeladen und erst eingetauscht, wenn es fertig ist, die alte Datei danach gelöscht und nicht vorher. Deine Kommentare, gespeicherten Artikel und 🛡-Overrides tragen unangetastet hinüber, weil keins von ihnen im Archiv selbst lebt. Die Pille wird zur Fortschrittsanzeige, während heruntergeladen wird, und verschwindet dann. enough prüft das höchstens einmal am Tag, nie während der Reader rendert, und bleibt still, wenn du offline bist — was der Normalzustand einer Offline-Wikipedia-Funktion ist. Dasselbe Upgrade ist auch auf dem langen Weg verfügbar, in der ⚙-Installationsliste, und die wikisink-Läufe des Agenten melden es ebenfalls (Abschnitt 10.3) — aber den Button zu drücken, ist immer deine Sache.

### 10.2 Artikel speichern und sperren

**Speichern.** Der Speichern-Button bietet zwei Ziele: den `wiki/`-Ordner dieses Projekts, oder die rechnerweite Wiki-Cachebox (`~/enough/cacheawl/wiki/`), geteilt von jedem Projekt. So oder so ist ein gespeicherter Artikel ein Ordner — `article.html`, der Artikel Byte für Byte, wie ihn das Archiv hatte, plus `_manifest.md` mit Titel, Quell-URL, Abrufdatum und der CC-BY-SA-Lizenzzeile. Jeder gespeicherte Artikel ist selbstbeschreibend, was heißt, dass die Zuordnung, die du brauchst, schon danebenliegt, falls sein Text je in etwas landet, das du veröffentlichst. Klick eine gespeicherte `article.html` im Baum an, und sie öffnet im Reader in voller Wiedergabetreue — Infoboxen, Tabellen, alles —, sogar wenn kein Archiv erreichbar ist. Zum Entfernen mit der Maus über den gespeicherten Ordner im Baum bleiben und auf das erscheinende 🗑 klicken.

Speichern ist für *dich*: Offline-Offline-Kopien, Zuordnung für Veröffentlichungen. Der Agent braucht keine gespeicherten Artikel — seine Tools lesen jeden Artikel im Archiv bei Bedarf als sauberen Text.

**Kommentare.** Text auswählen und 💬 drücken, oder das 💬 in der Werkzeugleiste für eine Notiz auf Absatzebene nutzen. Threads leben im 🗨-Panel: antworten, auflösen, wiedereröffnen, springen. Kommentare hängen am *Artikel*, nicht an einer Datei, und sie überstehen Artikel-Updates, indem sie sanft degradieren. Noch vorhandener Text bleibt **verankert**. Wegbearbeiteter Text wird an seinen Absatz **neu angeheftet**. Ein ganz gelöschter Absatz lässt den Kommentar **verwaist** im Panel zurück — markiert, aber nie automatisch gelöscht.

**Sperren (Löschungs-Overrides).** Manchmal löscht die echte Wikipedia einen Artikel, auf den du dich verlassen hast; der klassische Fall ist ein Nischenthema, gestrichen wegen „Relevanz“ statt Qualität. Der 🛡-Button bewahrt deine lokale Kopie für immer — von da an ausgeliefert mit einem `preserved`-Abzeichen, von künftigen Aktualisierungen ausgeschlossen, weiter durchsuchbar. Update-Lauf-Berichte bewerten erkannte Löschungen sogar (Relevanz-artige Begründungen gelten als verdächtig; Urheberrechtsverletzungen als harmlos), sodass du weißt, welche Löschungen einen Blick verdienen. Und das Übersteuern ist bewusst allein deine Sache: der Agent kann 🛡 empfehlen, aber er kann es nie selbst drücken.

### 10.3 Das wikisink-Update, mit Änderungsbericht

„Wikisink“ ist auch ein Verb. Jeder Artikel, den du gespeichert oder kommentiert hast, wird *beobachtet*, und den Agenten zu bitten, „einen wikisink zu laufen“ (oder ihn sein `wikisink`-Tool aufrufen zu lassen) prüft die beobachtete Menge gegen die echte Wikipedia und meldet zurück. Ein Lauf:

1. aktualisiert geänderte beobachtete Artikel in ein lokales Overlay (ihr Abzeichen springt auf `live`);
2. markiert **Bearbeitungsspitzen** — beobachtete Artikel, die plötzlich Dutzende Male am Tag bearbeitet werden, plus wikipediaweite Ausreißer-Kandidaten;
3. vergleicht die täglichen **Top-1000-Abrufzahlen-Ranglisten** mit dem letzten Lauf: Aufsteiger, Absteiger, Neueinsteiger, Aussteiger, und Abruftrends für deine beobachteten Artikel;
4. prüft auf **Löschungen** beobachteter oder kürzlich angesehener Artikel, bewertet nach Verdächtigkeit (Abschnitt 10.2);
5. vermerkt, wenn ein **neuerer Basis-Snapshot** verfügbar ist. Das mehrere GB große Basisarchiv zu ersetzen, ist immer deine Entscheidung — die Pille in der Reader-Werkzeugleiste drücken (Abschnitt 10.1) oder die ⚙-Installationsliste nutzen. Es gibt kein Agenten-Tool, das es austauscht.

Der Bericht kommt als Markdown im Chat an; die vollständige, ungekappte Version wird im wikisink-Zustandsordner aufbewahrt. Läufe sind höflich zu Wikipedia — gebündelt, ehrlicher User-Agent — und bei Unterbrechung fortsetzbar, und ein `report-only`-Lauf überspringt den Aktualisierungsschritt. Zwei Broker-Schalter regeln das alles: einer sperrt die Wiki-Tools des Agenten ganz, der andere kann Läufe vollständig offline erzwingen.

---

## 11. Cacheawl

Cacheawl ist der rechnerweite Textspeicher: der Ort für Dinge, die du für immer behalten willst und aus jedem Projekt erreichen können sollst. Er lebt unter `~/enough/cacheawl/`, verborgen vor dem Dateibaum jedes Projekts, geteilt über alle deine enough-Instanzen. (Hast du ein früheres enough genutzt, wurde deine alte `infoworld/`-Bibliothek beim ersten Start von 0.1.6 in cacheawl aufgelöst — `personal/`, `public/` und `wiki/` wurden deine ersten drei Cacheboxen. Nichts ging verloren.)

### 11.1 Cacheboxen und ihre merirmaid-Diagramme

Eine **Cachebox** ist ein Ordner oberster Ebene im Speicher, und es gibt sie in zwei Spielarten. **Schlichte Boxen** enthalten für immer behaltenen Text, den du selbst organisierst: eine `personal`-Box mit Referenznotizen, eine `press`-Box mit veröffentlichten Stücken, welche Struktur auch immer dir dient. **Cache-Kopien** sind Boxen, *importiert* aus einer Quelle — einem lokalen Ordner, einer Website, oder einer Reihe von Wikipedia-Artikeln —, die sich merken, woher sie kamen.

Jede Box trägt ein **merirmaid-Diagramm**: `_cachebox.merirmaid`, eine live Darstellung der Struktur der Box, neu erzeugt, wann immer sich der Inhalt ändert. Doppelklick, um die Form einer Box auf einen Blick zu sehen. Das Diagramm ist ein *Spiegel*, per Design nur lesbar, weil es die Wirklichkeit widerspiegelt — um das Diagramm zu ändern, die Box ändern. Ein günstiger Abgleich-Durchlauf hält Spiegel ehrlich, selbst wenn du Dateien vom Finder aus hinter enoughs Rücken hineinlegst.

Öffne den **cacheawl-Modus** aus der oberen Leiste für eine zweigeteilte Ansicht, Projekt auf der einen Seite, Speicher auf der anderen. Eine Datei rüberziehen, um sie zu kopieren. Shift-ziehen zum Verschieben. Shift-klick für ein Kontextmenü, und Doppelklick, um jede Datei in ihrem natürlichen Modus zu öffnen — girraph, merirmaid, Lesen/Bearbeiten, oder der Wiki-Reader — direkt aus dem Speicher.

### 11.2 Die Cachebox und lokale oder Web-Dokumente einfangen

Die **Import-Leiste** im cacheawl-Modus (oder eine schlichte Bitte im Gespräch) fängt Material von außen in eine Box ein:

- **Ein lokaler Pfad** — einen Ordner mit Notizen oder Dokumenten in den Speicher replizieren.
- **Eine Website** — eine Doku-Seite oder Referenzseite bis zu einer gewählten Tiefe crawlen (gedeckelt bei rund 500 Seiten) und als lokales Markdown behalten. Web-Importe respektieren deine Abruf-Schalter und Positivlisten, Tor-Routing eingeschlossen.
- **Wikipedia** — die Artikel eines Themas (gedeckelt bei rund 200) aus deinem wikisink-Archiv in dauerhaften, projektunabhängigen Text holen.

Importe laufen im Hintergrund. Die Box erscheint sofort mit einem Status „wird importiert“, dem du zusehen kannst, und ein gescheiterter Import sagt das auch, statt so zu tun, als wäre er fertig. Die Cachebox-Tools des Agenten (auflisten, anlegen, importieren) werden durch den cacheawl-Broker-Schalter gesperrt; deine eigene Nutzung des cacheawl-Modus nie.

Warum der Aufwand? Weil Projektordner Arbeitsraum sind und cacheawl Bibliotheksraum ist. Importier die Dokumentation eines Frameworks einmal, und jedes künftige Projekt kann sich offline darauf stützen. Halt deine zeitlosen Referenznotizen in einer Box, und jeder Agent, mit dem du je sprichst, kann sie erreichen. Ein Artefakt fertigstellen und in eine Box verschieben, wo es sein Projekt überlebt.

---

## 12. Mehrfach aktiver Modus-Stapel

enoughs Vollbild-Modi — Lesen/Bearbeiten, girraph, merirmaid, wikisink, cacheawl — ersetzen sich nicht gegenseitig. Sie **stapeln** sich, wie Blätter Papier. cacheawl öffnen, einen girraph von innerhalb einer Box öffnen, eine Notizdatei darüber öffnen: drei Modi tief, und jeden zu schließen legt den darunterliegenden genau so frei, wie du ihn verlassen hast. Dieselbe Scroll-Position, derselbe Abstieg, dieselben ungespeicherten Änderungen.

Die obere Leiste zeigt einen quadratischen Indikator pro offenem Modus, neuester links. Jeder trägt ein kleines rot-x-Band, das genau diesen Modus schließt, auch einen vergrabenen. Auf den Indikator eines vergrabenen Modus klicken, um ihn nach oben zu holen, ohne sonst etwas zu stören. Esc schließt immer den obersten Modus. Schließt der letzte, bist du zurück in der Gesprächsansicht — dem leeren Stapel (Abschnitt 4).

Zwei nützliche Dinge, die man kennen sollte:

- Das Mini-Lese-/Bearbeitungspanel schwebt *über* einem Vollbild-Modus, du kannst also ein Dokument griffbereit halten, während du darunter, sagen wir, im girraph-Modus arbeitest.
- Einen Modus zu öffnen, der schon irgendwo im Stapel steckt, verdoppelt ihn nicht. Es zielt den vorhandenen neu aus und holt ihn nach oben.

---

## 13. Das Modell-Fenster

Das Modell-Abzeichen in der oberen Leiste öffnet das Modell-Fenster: welches Gehirn dir gerade antwortet, was sonst noch verfügbar ist, und — wenn du willst — der Cloud-Slot.

### 13.1 Lokale Modelle: Überblick und Nutzungsempfehlungen

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

### 13.2 OpenRouter-Unterstützung (der OPRO-API-Slot)

enough ist local-first, nicht local-only. Ein fünfter Modell-Slot, **OPRO-API**, leitet über OpenRouter zu Cloud-Modellen. Er ist standardmäßig aus, bewusst aufwendig zu aktivieren, und ehrlich über den Tausch: deine Prompts und Outputs verlassen den Rechner, im Austausch für Frontier-Modell-Fähigkeiten und, manchmal, geringere Kosten als die Hardware und der Strom, die ein vergleichbares lokales Modell verlangen würden.

Ihn zu aktivieren: **local models only** im Broker ausschalten, dann OPRO-API im Modell-Fenster anklicken. Ein Assistent mit drei Bildschirmen führt dich durch — drei ausdrückliche Bestätigungs-Checkboxen (du hast ein Konto, du verstehst die Abrechnung, du verstehst den Datenschutz-Tausch), dann dein API-Schlüssel, dann eine Live-Gesundheitsprüfung. Der Schlüssel wird im macOS-Schlüsselbund gespeichert. Er wird nie in eine Datei geschrieben, der Agent hat keine Möglichkeit, ihn zu lesen, und der Broker verweigert Shell-Befehle, die auch nur so aussehen wie Versuche, an ihn heranzukommen. Einmal verifiziert, wird OPRO-API wählbar wie jedes andere Modell, und sein Einstellungspanel bietet erneutes Testen, Schlüssel aktualisieren, Schlüssel entfernen, und deine Wahl jeder beliebigen OpenRouter-Modell-ID.

Zwei Dinge halten Cloud-Nutzung rechenschaftspflichtig:

- **Alles wird lokal zwischengespeichert.** Jeder Cloud-Austausch wird in `rness/io/cloud-cache/` geschrieben, mit Token-Zahlen und einem Index — eine lokale Papierspur, die dein lokaler Agent später lesen kann.
- **`cloud_pipeline`** lässt den Agenten große Jobs gebündelt durch den Cloud-Slot schicken — bis zu 200 Schritte, mit Zwischenspeicherung pro Schritt, optionaler Zusammenfassung pro Schritt, und einem abschließenden Kompilierungsdurchgang — Ergebnisse werden auf die Platte geschrieben, statt das Gespräch zu fluten. Bitte um „eine Cloud-Pipeline, die alle zwölf Kapitelzusammenfassungen entwirft“, und die Schwerarbeit passiert außerhalb des Gesprächs, vollständig protokolliert.

---

## 14. Paradigmen

Ein Paradigma ist das Denkgerüst des Agenten — die Spielregeln dafür, wie Arbeit passiert. Immer genau eines ist aktiv (oben in der Seitenleiste angezeigt; auf ● klicken zum Wechseln), und der volle Text des aktiven Paradigmas reitet bei jedem Zug im System-Prompt mit. Der Agent sieht auch einen einzeiligen Katalog der anderen, damit er einen Wechsel vorschlagen kann — oder selbst vollziehen —, wenn deiner Bitte anderswo besser gedient wäre. Ein vom Agenten eingeleiteter Wechsel ist nichts Exotisches: er schreibt den Namen des Paradigmas nach `rness/active-paradigm` und sagt dir, dass er das getan hat.

### 14.1 default

Freies Ein-Agenten-Gespräch. Das Paradigma für die meiste Arbeit, und der Verteiler, der nach den Momenten Ausschau hält, in denen ein anderes Paradigma besser passt. Es trägt auch die stehenden Konventionen — wie zu wissen, dass „die gelben Teile“ deine Markierungen meint.

### 14.2 text-planning

Für die lange Startbahn vor der Prosa: einen Roman, eine Essaysammlung, ein Sachbuch oder ein Manifest von „ich glaube, ich will etwas schreiben“ zu einem brauchbaren Plan bringen. Der Agent baut mit dir ein Plandokument im Projekt-Wurzelverzeichnis — geduldig, iterativ, über so viele Sitzungen, wie es braucht — und erzeugt dann auf Anfrage *Gerüste* pro Abschnitt: strukturelle Leitfäden (Beats, Überschriften, Ton-Erinnerungen, Wortbudgets), die du selbst zu Prosa ausbaust. Die bestimmende Regel des Paradigmas: **es schreibt nie deine Prosa.** Gerüste enthalten nur Struktur. Deine Stimme bleibt deine Stimme. (Es aktiviert sich zusammen mit dem Skill `analyzer` oder `memoir-dialectic`; Memoiren werden an memoir-dialectic übergeben, das eigens dafür gebaut ist.)

### 14.3 translation

Erklärt Offline-Übersetzung zu einer Fähigkeit erster Klasse. Es paart sich mit dem Skill `translator` (Abschnitt 16.5): geht es bei einer Bitte darum, Text zwischen menschlichen Sprachen zu bewegen, wechselt der Agent hierher, und ist der Skill ausgeschaltet, sagt er dir, was dir fehlt — und sagt es dir weiter, bis du ihn einschaltest. Mit eingeschaltetem Skill hast du einen lokalen Übersetzer für ~419 Sprachen, ohne Konto, ohne Ratenlimit, ohne Netzwerkabhängigkeit.

### 14.4 workflow-design

Das Paradigma über enough selbst, aktiv, wann immer du den Workflow gestaltest oder änderst, statt in ihm zu arbeiten: neue Skills, neue Rollen, neue Paradigmen, Änderungen an AGENT.md oder MOTIVATION.md. Hier verhält sich der Agent wie ein nachdenklicher Mitgestalter — klärende Fragen vor dem Bauen (Umfang? Name? Auslösebedingungen?), Alternativen, wenn dein erster Instinkt schärfer sein könnte, und eine verfolgte Anfrage-Datei für jeden Bau, denn Workflow-Änderungen überleben die Gespräche, die sie hervorbringen. Das ist das Paradigma, das Abschnitt 3 wahr macht.

---

## 15. Rollen

Eine Rolle ist eine zweite Persona, die du ins Gespräch herbeirufen kannst: mit eigener `AGENT.md` und `MOTIVATION.md`, demselben Zwei-Dateien-Muster, das deinen Hauptagenten definiert, zugeschnitten auf einen ergänzenden — oder bewusst gegensätzlichen — Charakter. Rollen pro Projekt in der Seitenleiste ein- und ausschalten. Aktivierte Rollen reiten im System-Prompt mit, und du rufst sie beim Namen auf („was würde der open-skeptic zu diesem Plan sagen?“).

### 15.1 block-breaker

Ein Spezialist für Schreibblockaden, destilliert aus den Antworten einer echten Autorin darüber, wie sie das Feststecken auflöst. Er diagnostiziert, bevor er verschreibt — Ideenmangel, Mutmangel, Strukturmangel und Erlaubnismangel sind vier verschiedene Probleme —, und greift dann zu Beschränkungen, wiederholungsbasiertem Brainstorming („zehn Varianten, dann eindampfen“), seltsamen Umdeutungen, und, wenn gewünscht, echten nächsten Sätzen. Unnachgiebig anti-defätistisch. Seine Kernüberzeugung: für jeden, der freiwillig schreibt, ist eine Blockade immer lösbar, denn die Regeln wurden erfunden, und das Heilmittel kann genauso erfunden werden.

### 15.2 open-skeptic

Ein „erleuchtbarer Schwarzseher“: echt begeistert von KI, wo sie stark ist, professionell misstrauisch, wo sie überverkauft wird. Herbeirufen, wenn du gerade einen Workflow bauen willst und die Fehlerarten früh benannt haben willst. Er wehrt sich dagegen, KI menschliche Erfahrung nachbilden zu lassen, gegen sich aufschaukelnde Fehlerketten ohne menschliche Prüfung, und gegen flüssige Zuversicht, die die Arbeit von Fachwissen übernimmt — während er KI als Zusammenstellungs-Maschine, Wissens-Prothese und Probepartner bejubelt. Er aktualisiert sich an Belegen: zeig ihm einen Workflow, der funktioniert, und er sagt das, unverblümt.

### 15.3 Eigene bauen

Zwei Beispiele, ein Muster — Anweisungen plus Motivation, in zwei Markdown-Dateien. Rollen sind der günstigste Weg, eine Stimme hinzuzufügen, die dir fehlt: eine sokratische Gummiente, ein Compliance-Prüfer, eine Leser-Persona für deine Zielgruppe, ein Fachexperte, gespeist aus deinen eigenen Wissensdateien. Bitte im workflow-design-Paradigma um eine, und der Agent wird dich befragen und beide Dateien schreiben.

---

## 16. Skills

Ein Skill ist ein fokussiertes Fähigkeitspaket: ein Ordner mit einer `SKILL.md` (plus optionalen Referenzdokumenten und Skripten), der dem Agenten einen Ablauf, ein Vokabular oder eine Disziplin beibringt. Skills pro Projekt in der Seitenleiste ein- und ausschalten. Aus heißt wirklich aus — überhaupt nicht im Prompt — und neue Skills kommen deaktiviert an, sodass sich nichts hinter deinem Rücken ändert. Ein Skill, den enough nicht mitgeliefert hat, wird gelesen, bevor er überhaupt aktiviert werden kann (Abschnitt 16.6). Alles auszuschalten ist auch legitim: reines Gespräch, kein Gerüst, manchmal mehr Raum, damit das Modell dich überrascht.

### 16.1 analyzer

Vier Analysemodi in einem Skill.

**Summarize** erzeugt eine einseitige, ausgewogene Verdichtung jedes Textes: was er sagt, für wen er ist, Motivation und Schlagseiten der Autorin oder des Autors, Ton, Schlüsselzitate.

**Proofread** macht leichtes Lektorat — Tippfehler, Rechtschreibung — über ganze Dokumente bis zu ganzen Büchern, angetrieben von Harper, einem lokalen regelbasierten Grammatikprüfer. Es erzeugt auch einen separaten Korrektur-Bericht mit Vorschlägen und Funden wiederholter Formulierungen, sodass stille Korrekturen und Ermessensentscheidungen unterscheidbar bleiben.

**Decide** gibt dein Dilemma an drei archetypische Personas aus einem eingebauten Kader von zehn weiter, die es öffentlich diskutieren. Du bekommst eine Empfehlung *und* das Protokoll, sodass du die Argumentation abwägen kannst, statt einem Urteil zu vertrauen.

**Audit** liest etwas, dem du noch nicht zu vertrauen beschlossen hast — einen Skill, den dir jemand geschickt hat, eine Rolle, ein Paradigma — und sagt dir, was es ist. Zuerst eine Erklärung in klarem Deutsch, was das Ding tatsächlich tut und warum du es wollen würdest, dann ein Sicherheitsdurchgang: Prompt-Injection-Versuche, Anweisungen, die die Reichweite des Agenten still erweitern, epistemische Warnzeichen, und jeglicher gebündelter Code, der zusätzlich einen deterministischen Scan bekommt, der gar kein Modell einbezieht. Das Urteil ist eines von drei Worten — **pass**, **flag**, **fail** — gestützt von benannten Funden, nie eine Punktzahl. Es ist nur lesend: Audit führt nie aus, bearbeitet, installiert oder aktiviert nie das, was es liest.

Berichte landen in `rness/io/output/analyzer/audits/<skill-name>/`: eine datierte `.md`, die du wie jede andere Datei lesen kannst, plus eine kleine `verdict.json` daneben. Bitte jederzeit namentlich um ein Audit — „prüf das, bevor ich es aktiviere“, „was macht dieser Skill eigentlich“ — und enough lässt diesen Modus auch ungefragt für dich laufen, beim ersten Einschalten eines Skills, den es nicht mitgeliefert hat. Beide Türen schreiben denselben Bericht in denselben Ordner. Abschnitt 16.6 erzählt diese Geschichte.

### 16.2 anything-finder

Ein Suchtrupp für die Dinge, die nicht auf der ersten Seite auftauchen. Drei Gesichter, ein Skill.

**find** ist die Vorgabe, und es trägt ein Playbook für jede von zehn Arten schwer auffindbarer Dinge, plus eine elfte für Missionen, die ins Stocken geraten. **Texte** — gemeinfreie Bücher, Gedichte, historische Dokumente. **Video** — seltene, verlorene und vergriffene Film- und TV-Werke, mit Sichtungs-Links und ihrer angegebenen Rechtslage. **Bilder**, freigegeben für ein Cover oder ein Zine. **Produkte** — obskures Equipment, Synthesizer, Instrumente, und wo man tatsächlich eines kauft. **Artikel** — das Paper hinter einer Paywall, gefunden als seine legitime offene Kopie: Preprint, Repository, Archiv. **Code** — großzügig lizenzierte Repos, einschließlich Bibliotheken, die nie GitHub berührt haben. **Bücher** — Leseempfehlungen, ähnlich dem, was du schon geliebt hast. **Audio** — Notenblätter, MIDI, Samples, Geräte-Handbücher. **Assets** — Schriften, Texturen, 3D-Modelle, Stockmaterial. **Daten** — Datensätze, öffentliche APIs, Regierungsdokumente, Zeitungsarchive.

Ergebnisse kommen als *Find-Karten* zurück: der Link, warum es der richtige Fund ist, und — bei allem Urheberrechts-Sensiblen — warum es zur Nutzung frei ist, mit Erscheinungsdatum oder ausdrücklicher Lizenz ausbuchstabiert. Frag es „finde mir eine gemeinfreie Ausgabe von *The Moonstone*, sauber genug zum Setzen“, „wo kann ich legal die Fassung von 1974 sehen“, „gibt es eine MIT-lizenzierte Bibliothek, die das macht“. Die ehrlichen Antworten gehören zum Deal: „das existiert, ist aber nicht legal verfügbar“ und „drei Kandidaten, ich bin zu 70 % beim zweiten“ sind hier echte Ergebnisse, und wo der einzige Weg eine Piraterie-Seite ist, sagt es das und gibt dir stattdessen die Bibliothek, das Verleihsystem oder den Shop an die Hand.

**patents** ist das Stand-der-Technik-Gesicht. Gib ihm eine Erfindung, und es führt eine strukturierte Neuheitssuche über erteilte Patente, veröffentlichte Anmeldungen und die nicht-patentliche Literatur aus, und berichtet dann, was es gefunden hat und was das für Neuheit und erfinderische Tätigkeit bedeutet — mit einem Kein-Rechtsrat-Hinweis, der in jedem Bericht bleibt, weil das ist, was es ist. „Ist das schon patentiert?“ „Stand der Technik zu einem magnetischen Fahrradschloss, das…“ „Ist meine Idee patentierbar?“ Datenbanken, die es nicht erreichen konnte, kommen als *ungeprüft* markiert zurück, nie still als *leer*.

**venture** ist das „ist das ein Geschäft?“-Gesicht, und es setzt sich aus den anderen beiden zusammen. Eine Markt-Durchsicht dessen, was schon existiert, eine Stand-der-Technik-Prüfung, und ein Durchgang durch die Wettbewerbslandschaft über Firmen, Open-Source-Alternativen, angrenzende Produkte, und den Friedhof derer, die es versucht haben und dichtgemacht haben. Was du bekommst, ist eine ausgewogene Lesart — was überlaufen ist, was angrenzt, was wirklich offen ist, und die Nische, die die Belege tatsächlich stützen — gefolgt vom stärksten Argument *dafür* und dem stärksten *dagegen*, jeder Punkt an einem Link verankert, und eine kurze Liste von Fragen, die nur du beantworten gehen kannst. Frag es „sollte ich das bauen“, „gibt es das schon als Produkt“, „wo ist hier die Marktlücke“. Es wird deine Idee nicht bewerten, deinen Businessplan nicht schreiben, oder dir sagen, Geld einzusammeln. Und es behandelt ein leeres Feld als Frage, nicht als grünes Licht.

Output geht nach `rness/io/output/anything-finder/`. Alles, was es abruft, läuft wie jeder andere Web-Zugriff durch den Broker, eine Domain außerhalb der Positivliste wird also über Tor geleitet — und weigert sich eine Quelle zu antworten, nennt der Bericht den Host und sagt dir, was du zu `allowlists.md` hinzufügen sollst, statt ein stilles Loch in den Ergebnissen zu lassen.

### 16.3 girraph-merirmaid

Der Disziplin-Skill für enoughs zwei Diagramm-Grundformen (Abschnitte 17 und 18). Die girraph-Hälfte lehrt richtiges IBIS-Mapping: eine Frage pro Zug, kein Lösungssprung, deine Bestätigung als Stopp-Regel. Die merirmaid-Hälfte trägt die Mermaid-Schreibregeln, etwa Knotenbezeichnungen kurz genug zu halten, dass du sie bequem bearbeiten kannst. Die Modi funktionieren ohne den Skill; mit ihm wird der Agent zu einem wirklich disziplinierten Mapping-Partner.

### 16.4 memoir-dialectic

Ein geduldiger Memoiren-Mitgestalter über mehrere Sitzungen. Er befragt dich — ein, zwei Fragen zur Zeit, nie eine Flut — und legt alles ab: nummerierte Plandokumente in Gesprächsreihenfolge, ein Index für schnellen Wiedereinstieg, eine Notizdatei für unordentliche Gedanken-Dumps, und schließlich eine Gliederungs-Synthese und, nur wenn du es willst, Entwürfe. Der Ordner ist das Gedächtnis. Du kannst für Wochen oder Jahre verschwinden, und er macht dort weiter, wo du aufgehört hast. Gebaut für die volle Bandbreite von der kompletten Lebensgeschichte bis zu einem einzelnen Meilenstein, mit ausdrücklichem Umgang mit sensiblen Themen und Tabuzonen, und sorgfältiger Bewahrung deiner eigenen Formulierungen — Stimme zählt, besonders wenn ein Entwurf ansteht.

### 16.5 translator

Offline-Übersetzung über ~419 Sprachen via MADLAD-400 — ein einmaliger ~3-GB-Download, der auf CPU oder Apple Silicon läuft und nie nach Hause telefoniert. Von kurzen Phrasen bis zu ganzen Dokumenten, von großen Sprachen bis zu ressourcenarmen und indigenen. Einen Brief übersetzen, ein README lokalisieren, prüfen, was eine Passage bedeutet, eine Phrase als Bedeutungs-Erhaltungstest durch eine dritte Sprache hin- und zurückschicken — alles bei abgestecktem Netzwerk. Für bestimmte ressourcenarme Sprachen bietet eine optionale NLLB-200-Engine höhere Qualität; sie trägt eine nichtkommerzielle Lizenz, ist also über das translation-Paradigma zum Zuschalten.

### 16.6 Eigene schreiben, und fremden vertrauen

Die fünf oben sind Demonstrationen. Der Skill-*Mechanismus* — Markdown-Anweisungen, geladen beim Einschalten, mit einem `description:`, das dem Agenten sagt, wann er zugreifen soll — ist die eigentliche Funktion. Hausstil-Leitfäden, Fach-Checklisten, wiederkehrende Berichtsformate, Datenverarbeitungs-Abläufe: kannst du eine Kompetenz in Prosa beschreiben, kannst du sie deinem Agenten als Skill übergeben. Bau deine eigenen mit workflow-design (Abschnitt 14.4), oder zweig einen der fünf ab und mach ihn zu deinem.

Das andere Ende dieser Schleife sind die Skills, die von woanders herkommen. Ein Skill ist Anweisungen, denen dein Agent folgen wird, was heißt, dass ein Skill aus dem Internet genau so viel Misstrauen verdient wie jede andere Datei aus dem Internet. Also liest enough sie für dich:

- **Was enough mitliefert, ist vertrauenswürdig, und sieht aus wie immer.** Die fünf oben kommen als Links in die eigenen Defaults der Installation an. Sie schalten sofort um. Nichts auditiert sie.
- **Alles andere ist aus, bis es gelesen wurde.** Einen Skill-Ordner in `rness/skills/` fallen lassen — heruntergeladen, von einem Freund geschickt, aus einer `.skill` entpackt — und er sitzt dort deaktiviert, in der Seitenleiste als *ungeprüft* markiert. Beim ersten Einschalten lässt enough analyzers Audit-Modus darüber laufen (Abschnitt 16.1), bevor auch nur ein Wort davon den Agenten erreicht. Du siehst es in der Zeile passieren: *ungeprüft* → *Audit läuft…* → *geprüft*.
- **Markiert heißt nicht aktiviert.** Findet das Audit etwas, sagt die Zeile *markiert* (oder *fehlgeschlagen*), der Skill bleibt aus, und du bekommst zwei Buttons: **Bericht lesen** öffnet den vollständigen Bericht in der Leseansicht, und **trotzdem aktivieren** bittet um deine Bestätigung und vermerkt die Entscheidung dann als deine — der Fund wird nicht gelöscht, er wird überstimmt, und die Zeile liest von da an *von dir freigegeben*. Das Audit berät. Du entscheidest. (Arbeitest du lieber in der Datei, tut es dasselbe, die `verdict.json` dieses Skills auf `"verdict": "pass"` zu setzen.)
- **Einen Skill bearbeiten, und er wird neu gelesen.** Das Audit ist an die genauen Bytes gebunden, die es gelesen hat — Dateinamen wie Inhalte. Änderst du irgendetwas, wird er beim nächsten Einschalten erneut auditiert. Das gilt auch für einen, den du zuvor trotzdem aktiviert hattest: ein Override beschreibt eine bestimmte Dateimenge zu einem bestimmten Moment, und es übersteht keine Bearbeitung.
- **Skills, die dein Agent für dich schreibt, zählen auch als nicht vertrauenswürdig.** Das ist Absicht, kein Versehen. Wenn workflow-design eine neue `SKILL.md` nach `rness/skills/` schreibt, auditiert der Agent seine eigenen Hausaufgaben beim ersten Aktivieren. Das geht nahezu augenblicklich, wenn nichts zu finden ist.
- **Läuft kein Modell, kann ein Audit nicht fertig werden** — und es sagt das auch, markiert mit „die LLM-Hälfte des Audits konnte nicht laufen“, statt den Skill einfach durchzuwinken. Ein Modell einschalten und erneut umschalten, oder *trotzdem aktivieren* nutzen, wenn du schon weißt, was drinsteckt.

Berichte leben in `rness/io/output/analyzer/audits/<skill-name>/` — derselbe Ordner, in den analyzer schreibt, wenn du im Gespräch um ein Audit bittest. Zwei Türen, ein Dokument, und es ist eine gewöhnliche Markdown-Datei, die du öffnen, behalten oder löschen kannst.

---

## 17. Girraph-Modus und die Dateiendung `.girraph`

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

In der App öffnet ein Klick auf ein `.girraph` den girraph-Modus: einen einklappbaren Baum, den du direkt bearbeitest. Eine Bezeichnung anklicken, um sie umzuschreiben. Über einer Zeile schweben für Buttons zum Hinzufügen, Verknüpfen und Entfernen. Auf einen 🦒-Chip klicken, um in eine verschachtelte Karte abzusteigen — Breadcrumbs bringen dich zurück — und auf einen 📄-Chip klicken, um ein referenziertes Dokument an Ort und Stelle zu lesen. Im Chat „girraph this“ oder „map this out“ sagen, und der Agent bearbeitet dieselbe Datei über dieselben Operationen auf Knotenebene, die du nutzt, sodass ihr beide gleichzeitig an der Karte arbeiten könnt. Knoten zu löschen braucht immer deine Bestätigung, und Kinder werden nie still verwaist.

Ein girraph kann auch einen **merirmaid-Spiegel** wachsen lassen: ein Klick auf den merirmaid-Button in der girraph-Werkzeugleiste erzeugt ein verknüpftes, sich selbst neu erzeugendes Mermaid-Diagramm der Karte — Fragen als Sechsecke, Positionen als Stadion-Formen, Zustimmungen und Einwände in ihren Farben umrandet —, das sich aktuell hält, während sich der girraph ändert. Karten in girraph, Blick in merirmaid.

Drei Gewohnheiten lassen girraphs funktionieren. Fragen als Fragen formulieren („Wie finanzieren wir Jahr zwei?“, nicht „das Geldproblem“). Argumente an Positionen hängen, nicht an Fragen — Gründe sind Gründe für oder gegen eine *Antwort*. Und einen Zweig in eine eigene Datei aufspalten, bevor er ausufert. Den Skill girraph-merirmaid aktivieren, und der Agent wird dich an alle drei halten.

---

## 18. Merirmaid-Modus und die Dateiendung `.merirmaid`

Wo ein girraph ein Argument kartiert, bildet ein **merirmaid** eine Struktur ab. Eine `.merirmaid`-Datei ist ein [Mermaid](https://mermaid.js.org/)-Diagramm — Flussdiagramm, Sequenzdiagramm, Zustandsautomat, ER-Diagramm, alles, was Mermaid zeichnet — mit einem kleinen Frontmatter-Header, live im Browser gerendert. Lokal, natürlich; kein CDN, wie alles in enough.

Zwei Modalitäten, im Header deklariert:

- **wip** — ein Arbeits-Whiteboard. Auf den Text eines Knotens klicken und die Bezeichnung direkt bearbeiten, mit laufender Zeichenzählung; strukturelle Änderungen (eine Box hinzufügen, einen Pfeil neu verdrahten) laufen über den Agenten via Chat-Pille. Bitte um ein Diagramm deiner Pipeline, deiner Handlung, deiner Organisation, und der Agent schreibt die Quelle, der Browser zeichnet sie, und du feilst an den Worten.
- **mirror** — ein nur lesbares Spiegelbild einer Struktur, die anderswo lebt: der Inhalt einer Cachebox (Abschnitt 11.1) oder ein girraph (Abschnitt 17). Spiegel erzeugen sich neu, wenn sich ihre Quelle ändert. Um das Bild zu ändern, das Ding ändern.

Diagramme verlinken. Ein Knoten kann auf ein anderes `.merirmaid`, ein `.girraph`, oder ein Markdown-Dokument zeigen, und ihn anzuklicken navigiert dorthin, Breadcrumbs markieren den Weg zurück — sodass eine Reihe von Diagrammen zu einem navigierbaren Atlas deines Projekts wird. Und hat ein Diagramm einen Syntaxfehler, zeigt der merirmaid-Modus den Fehler plus die Rohquelle statt einer leeren Fläche. Es gibt immer etwas, wovon aus man reparieren kann.

Der Skill girraph-merirmaid (Abschnitt 16.3) trägt die Schreibdisziplin für beide Dateitypen. Eine Faustregel daraus ist es wert, hier wiederholt zu werden: wenn der ehrliche erste Schritt eine Frage ist, willst du einen girraph; wenn es eine Box und ein Pfeil sind, willst du ein merirmaid.

---

## 19. Wo es von hier aus weitergeht

Der schnellste Weg, dir enough zu eigen zu machen:

1. Starte es in einem echten Projekt — etwas, das dir tatsächlich wichtig ist.
2. Verbring eine Sitzung mit Reden, und lass das Projektprofil anfangen, sich anzuhäufen.
3. Bearbeite `MOTIVATION.md`, um zu sagen, wofür das Projekt eigentlich da ist.
4. Beim ersten Mal, dass du eine Anweisung wiederholst, halt inne. Steck sie stattdessen in `AGENT.md`.
5. Beim ersten Mal, dass deine Arbeit eine Form hat, die die Defaults nicht treffen, sag „lass uns dafür ein Paradigma entwerfen“ — oder einen Skill, oder eine Rolle — und lass workflow-design dich durchführen.

Diese Schleife — Reibung bemerken, die Lösung kodieren, weiterarbeiten — ist das ganze Spiel. Die eingebauten Bausteine bringen dich in Gang. Das System, bei dem du landest, liefert niemand mit. Das schreibst du.

---

*enough ist © 2026 Graham Smith, veröffentlicht unter der Apache License 2.0. Wikipedia-Inhalte, erreicht über wikisink, stehen unter CC BY-SA. Dieses Dokument: auch deins zum Bearbeiten.*
