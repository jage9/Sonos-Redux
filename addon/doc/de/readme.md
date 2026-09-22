# Sonos Redux

Ursprünglich von Ralf Kefferpuetz <novalis7747@live.com>.

Aktualisiert von J.J. Meddaugh <jj@bestmidi.com>.

## Tastenkürzel der Erweiterung

| Tastenkürzel | Funktion |
| --- | --- |
| Strg+1 | Aktuellen Titel vorlesen; zweimal drücken zum Kopieren. |
| Strg+2 | Informationen zur aktuellen Wiedergabe anzeigen, einschließlich Senderdetails, falls vorhanden. |
| Strg+3 | Auf YouTube nach dem aktuellen Titel suchen. |
| Strg+J | Zu einer Zeit im Titel springen. |
| Strg+V | Lautstärke der ausgewählten Lautsprechergruppe einstellen. |
| Strg+Umschalt+V | Lautstärke absenken, pausieren und wiederherstellen (standardmäßig fünf Sekunden). |
| Alt+Umschalt+L | Titelprotokollierung ein- oder ausschalten. |
| Alt+Umschalt+K | Titelansagen umschalten: Aus, Überall, Sonos im Vordergrund. |
| Alt+Umschalt+S | Status des Schlaf-Timers ansagen. |
| Alt+Umschalt+J | Zu den letzten 30 Sekunden eines Titels springen (einstellbar). |
| Alt+Umschalt+F5 | Schleifenanfang setzen. |
| Alt+Umschalt+F6 | Schleifenende setzen. |
| Alt+Umschalt+F7 | Schleife starten. |
| Alt+Umschalt+F8 | Schleife beenden und Wiedergabe fortsetzen. |
| Alt+Umschalt+F9 | Schleifenanfang, Ende und Dauer ansagen. |
| Alt+Umschalt+G | Aktuelle Lautsprechergruppe und ihre Räume ansagen. |
| Alt+Umschalt+Q | Anzahl der Titel in der Warteschlange ansagen. |
| Alt+Umschalt+N | Nächsten Titel oder bei SiriusXM den Sender ansagen. |
| Alt+Umschalt+A | Angezeigtes Albumcover kopieren. |
| Alt+Umschalt+V | Lautstärke ansagen. |
| Alt+Umschalt+M | Stummschaltung ansagen. |
| Alt+Umschalt+R | Wiederholungsmodus ansagen. |
| Alt+Umschalt+E | Zufallswiedergabe ansagen. |
| Alt+Umschalt+T | Überblendung ansagen. |
| Alt+Umschalt+U | Verstrichene Zeit ansagen. |
| Alt+Umschalt+I | Titelposition, Dauer und Prozentwert ansagen. |
| Alt+Umschalt+O | Verbleibende Zeit ansagen. |
| Umschalt+Pfeil links | Zurückspringen (standardmäßig fünf Sekunden). |
| Umschalt+Pfeil rechts | Vorspringen (standardmäßig fünf Sekunden). |
| Umschalt+Pfeil hoch | Positionsregler fokussieren. |

## Erweiterte Sonos-Tastenkürzel

| Tastenkürzel | Funktion |
| --- | --- |
| Strg+M | Stummschaltung umschalten und Status ansagen. |
| Strg+R | Wiederholungsmodus wechseln und ansagen. |
| Strg+E | Zufallswiedergabe umschalten und Status ansagen. |
| Strg+T | Überblendung umschalten und Status ansagen. |
| Strg+8 | Sonos-Favoriten öffnen und ansagen. |
| Strg+, | Zur vorherigen Gruppe wechseln und sie ansagen. |
| Strg+. | Zur nächsten Gruppe wechseln und sie ansagen. |
| Strg+K | Sonos-Hilfe zu Tastenkürzeln öffnen. |

Strg+V öffnet ein Lautstärkefeld von 0 bis 100. Einen Wert eingeben oder mit Pfeil hoch und runter ändern, dann mit Eingabe übernehmen. Strg+Umschalt+V senkt die Lautstärke auf null ab, pausiert die Wiedergabe und stellt die ursprüngliche Lautstärke wieder her. Sonos und die Wiedergabe/Pause-Schaltfläche müssen sichtbar bleiben. Bei unklarem Startsymbol wird laufende Wiedergabe angenommen. Lässt sich die Pause danach nicht bestätigen, bleibt die Lautstärke bei null.

Bei einem Titel mit Positionsregler Anfang und Ende markieren. Alt+Umschalt+F7 springt zum Anfang und wiederholt den Abschnitt. Bei pausierter Wiedergabe mit Sonos Wiedergabe/Pause fortsetzen. Alt+Umschalt+F8 beendet die Schleife und setzt an der aktuellen Position fort. Beim Verlassen von Sonos endet die Schleife; ein Titel- oder Gruppenwechsel löscht die Marken. Die Schleifenzeit ist nicht exakt.

Strg+J akzeptiert Sekunden, Minuten:Sekunden oder Stunden:Minuten:Sekunden. Mit + oder - wird relativ gesprungen, etwa +30 oder -1:15. Maßgeblich ist die Position beim Bestätigen; Sprünge enden spätestens am Titelanfang oder -ende.

## Einstellungen

**Absenkdauer in Sekunden** legt die Dauer für Strg+Umschalt+V fest: 1–999 Sekunden, standardmäßig 5.

**Sprungweite in Sekunden** legt die Schrittweite für Umschalt+Pfeil links und Umschalt+Pfeil rechts fest: 1–999 Sekunden, standardmäßig 5. **Sprungweite vor Titelende in Sekunden** legt den Sprung mit Alt+Umschalt+J fest: 1–999 Sekunden, standardmäßig 30. Bei kürzeren Titeln wird zum Anfang gesprungen.

In den NVDA-Einstellungen unter Sonos lässt sich **Titel protokollieren** einschalten und eine Protokolldatei auswählen. Diese Einstellungen gelten für alle NVDA-Profile. Die Protokollierung ist standardmäßig ausgeschaltet. Die Standarddatei heißt `sonos.log` und liegt im Dokumente-Ordner. Über Durchsuchen lässt sich ein anderer Speicherort wählen; Öffnen öffnet das Protokoll in der Standardanwendung.

Titel und Interpret werden mit einem Zeitstempel aufgezeichnet. Bei Änderungen wird ein neuer Eintrag angehängt. Die Prüfung erfolgt alle drei Sekunden und läuft auch beim Arbeiten in anderen Anwendungen weiter, solange Sonos geöffnet bleibt. Protokolliert wird die ausgewählte Lautsprechergruppe. Start- und Endmarkierungen trennen die Protokollierungssitzungen. Alt+Umschalt+L schaltet die Protokollierung in Sonos um.

**Titelwechsel ansagen** bietet Aus (Standard), Überall und Nur wenn Sonos im Vordergrund ist. Titel und Interpret werden beim Titelwechsel in der ausgewählten Lautsprechergruppe angesagt, auch ohne Protokollierung. Alt+Umschalt+K wechselt zwischen diesen Optionen. Die erste Prüfung merkt sich den aktuellen Titel; Wechsel innerhalb von drei Sekunden können übersehen werden.

## Ursprüngliche Erweiterung

- [Ursprüngliches Projekt](https://github.com/Novalis7747/sonos)
- [Originalversion 1.4 herunterladen](https://github.com/Novalis7747/sonos/raw/master/sonos-1.4.nvda-addon)

Lizenz: GNU GPL v2.
