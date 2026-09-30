# Sonos Redux

Ursprünglich von Ralf Kefferpuetz <novalis7747@live.com>.

Aktualisiert von J.J. Meddaugh <jj@bestmidi.com>.

## Tastenkürzel der Erweiterung

### Informationen

| Tastenkürzel | Funktion |
| --- | --- |
| Strg+1 | Aktuellen Titel vorlesen; zweimal drücken zum Kopieren. |
| Strg+2 | Informationen zur aktuellen Wiedergabe anzeigen. |
| Alt+Umschalt+G | Aktuelle Lautsprechergruppe und ihre Räume ansagen. |
| Alt+Umschalt+Q | Anzahl der Titel in der Warteschlange ansagen. |
| Alt+Umschalt+N | Nächsten Titel oder bei SiriusXM den Sender ansagen. |
| Alt+Umschalt+V | Lautstärke ansagen. |
| Alt+Umschalt+M | Stummschaltung ansagen. |
| Alt+Umschalt+R | Wiederholungsmodus ansagen. |
| Alt+Umschalt+E | Zufallswiedergabe ansagen. |
| Alt+Umschalt+T | Überblendung ansagen. |
| Alt+Umschalt+U | Verstrichene Zeit ansagen. |
| Alt+Umschalt+I | Titelposition, Dauer und Prozentwert ansagen. |
| Alt+Umschalt+O | Verbleibende Zeit ansagen. |
| Alt+Umschalt+S | Status des Schlaf-Timers ansagen. |

### Funktionen

| Tastenkürzel | Funktion |
| --- | --- |
| Umschalt+Pfeil links | Zurückspringen (standardmäßig fünf Sekunden). |
| Umschalt+Pfeil rechts | Vorspringen (standardmäßig fünf Sekunden). |
| Umschalt+Pfeil hoch | Positionsregler fokussieren. |
| Strg+J | Zu einer Zeit springen oder mit Plus oder Minus relativ springen. |
| Strg+V | Lautstärke der ausgewählten Lautsprechergruppe einstellen. |
| Strg+Umschalt+V | Lautstärke absenken, pausieren und wiederherstellen (standardmäßig fünf Sekunden). Sonos währenddessen im Vordergrund lassen. |
| Alt+Umschalt+L | Titelprotokollierung ein- oder ausschalten. |
| Alt+Umschalt+K | Titelansagen wechseln: Aus, Überall, nur wenn Sonos im Vordergrund ist. |
| Alt+Umschalt+J | Zu den letzten 30 Sekunden eines Titels springen (einstellbar). |
| Strg+3 | Auf YouTube nach dem aktuellen Titel suchen. |
| Alt+Umschalt+Y | Songtexte für den aktuellen Titel abrufen. |
| Alt+Umschalt+A | Angezeigtes Albumcover kopieren. |

### Schleifen

Sie können einen Titelabschnitt wiederholen. Aufgrund der Funktionsweise von Sonos sind Schleifen ungenau und haben eine Lücke zwischen den Wiederholungen. Schleifen funktionieren nur bei Titeln, zu denen gesprungen werden kann. Sonos muss währenddessen im Vordergrund bleiben. Ein Titel- oder Gruppenwechsel löscht die Schleife.

| Tastenkürzel | Funktion |
| --- | --- |
| Alt+Umschalt+F5 | Schleifenanfang setzen. |
| Alt+Umschalt+F6 | Schleifenende setzen. |
| Alt+Umschalt+F7 | Schleife starten. |
| Alt+Umschalt+F8 | Schleife beenden und Wiedergabe fortsetzen. |
| Alt+Umschalt+F9 | Schleifenanfang, Ende und Dauer ansagen. |

## Erweiterte Sonos-Tastenkürzel

Dies sind vorhandene Sonos-Tastenkürzel und können nicht geändert werden. Zusätzliche Sprachausgaben wurden hinzugefügt.

| Tastenkürzel | Funktion |
| --- | --- |
| Strg+M | Stummschaltung umschalten und Status ansagen. |
| Strg+R | Wiederholungsmodus wechseln und ansagen. |
| Strg+E | Zufallswiedergabe umschalten und Status ansagen. |
| Strg+T | Überblendung umschalten und Status ansagen. |
| Strg+8 | Sonos-Favoriten öffnen. |
| Strg+Komma | Zur vorherigen Gruppe wechseln und sie ansagen. |
| Strg+Punkt | Zur nächsten Gruppe wechseln und sie ansagen. |
| Strg+K | Sonos-Hilfe zu Tastenkürzeln öffnen. |

## Songtexte

Drücken Sie Alt+Umschalt+Y, um Songtexte von [LRCLIB](https://lrclib.net/) abzurufen. Wird eine passende Aufnahme gefunden, öffnet sie sich direkt. Andernfalls können Sie aus den gefundenen Aufnahmen anhand von Titel, Interpret, Album und Länge auswählen. Die Songtexte werden in einem barrierefreien Fenster geöffnet, in dem Sie sie lesen und kopieren können. Drücken Sie dort Strg+S, um eine Textdatei zu speichern.

Bei der Suche werden, falls verfügbar, aktueller Titel, Interpret, Album und Titellänge sowie die Erweiterungsversion und eine zufällige Installations-ID übermittelt. Diese ID enthält keine persönlichen Daten oder Geräteinformationen, ermöglicht LRCLIB aber, Anfragen derselben Installation zuzuordnen. Sie wird in den globalen NVDA-Einstellungen gespeichert. Konto und API-Schlüssel sind nicht erforderlich. Nur beim Abrufen von Songtexten wird der Dienst kontaktiert. Wiederholte Anfragen für denselben Titel verwenden das letzte Ergebnis erneut, solange Sonos geöffnet bleibt.

## Zu einer Zeit springen

Strg+J öffnet standardmäßig den Sprungdialog. Geben Sie eine Zeit wie 03:22 ein, um direkt dorthin zu springen. Mit einem Plus oder Minus vor der Zeit springen Sie um Stunden, Minuten oder Sekunden vor oder zurück.

## Einstellungen

Öffnen Sie zum Aufrufen der Einstellungen das NVDA-Menü mit NVDA+N, dann Einstellungen und wählen Sie die Gruppe Sonos.

**Absenkdauer in Sekunden** legt die Dauer für Strg+Umschalt+V fest: 1–999 Sekunden, standardmäßig 5.

**Sprungweite in Sekunden** legt fest, wie weit Umschalt+Pfeil links und Umschalt+Pfeil rechts springen: 1–999 Sekunden, standardmäßig 5.

**Sprungweite vor Titelende in Sekunden** legt den Sprung mit Alt+Umschalt+J fest: 1–999 Sekunden, standardmäßig 30. Bei kürzeren Titeln wird zum Anfang gesprungen.

Wählen Sie in den NVDA-Einstellungen die Gruppe Sonos, um **Titel protokollieren** einzuschalten und einen Dateinamen für das Protokoll festzulegen. Diese Einstellungen gelten für alle NVDA-Profile. Die Protokollierung ist standardmäßig ausgeschaltet. Die Standarddatei heißt `sonos.log` und liegt im Dokumente-Ordner. Über Durchsuchen lässt sich ein anderer Speicherort wählen; Öffnen öffnet das Protokoll in der Standardanwendung.

Die Protokollierung zeichnet den aktuellen Titel und Interpreten mit Zeitstempel auf und hängt bei Änderungen einen Eintrag an. Die Prüfung erfolgt alle drei Sekunden und läuft auch bei der Verwendung anderer Anwendungen weiter, solange Sonos geöffnet bleibt. Protokolliert wird die ausgewählte Lautsprechergruppe. Start- und Endmarkierungen trennen die Protokollierungssitzungen. Drücken Sie in Sonos Alt+Umschalt+L, um die Protokollierung umzuschalten.

**Titelwechsel ansagen** bietet Aus (Standard), Überall und Nur wenn Sonos im Vordergrund ist. Bei einem Titelwechsel in der ausgewählten Gruppe werden Titel und Interpret angesagt; die Funktion arbeitet auch ohne Protokollierung. Alt+Umschalt+K wechselt in Sonos zwischen diesen Optionen. Bei der ersten Prüfung wird der aktuelle Titel ermittelt; Wechsel innerhalb von drei Sekunden können übersehen werden.

**Erweitert** öffnet den zufällig erzeugten Songtextschlüssel. Er dient zur Identifizierung der Installation bei LRCLIB und ist kein API-Schlüssel. Sie können ihn bearbeiten oder das Feld leeren, um einen neuen Schlüssel zu erzeugen. Änderungen werden beim Speichern der NVDA-Einstellungen übernommen.

## Weitere Funktionen

Verschiedene Menüs und Dialoge werden verständlicher vorgelesen. Überflüssiger Schaltflächentext wird bereinigt und Dialoge wie die Tastenkürzelhilfe werden korrekt vorgelesen.

## Ursprüngliche Erweiterung

- [Ursprüngliches Projekt](https://github.com/Novalis7747/sonos)
- [Originalversion 1.4 herunterladen](https://github.com/Novalis7747/sonos/raw/master/sonos-1.4.nvda-addon)

Lizenziert unter GNU GPL v2.
