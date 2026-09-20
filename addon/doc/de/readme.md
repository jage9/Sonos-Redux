# Sonos Redux

Ursprünglich von Ralf Kefferpuetz <novalis7747@live.com>.

Aktualisiert von J.J. Meddaugh <jj@bestmidi.com>.

## Tastenkürzel der Erweiterung

| Tastenkürzel | Funktion |
| --- | --- |
| Strg+1 | Aktuellen Titel vorlesen; zweimal drücken zum Kopieren. |
| Strg+2 | Titelinformationen anzeigen. |
| Strg+3 | Auf YouTube nach dem aktuellen Titel suchen. |
| Strg+J | Zu einer Zeit im Titel springen. |
| Alt+Umschalt+L | Titelprotokollierung ein- oder ausschalten. |
| Alt+Umschalt+G | Aktuelle Lautsprechergruppe und ihre Räume ansagen. |
| Alt+Umschalt+Q | Anzahl der Titel in der Warteschlange ansagen. |
| Alt+Umschalt+N | Nächsten Titel ansagen. |
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

## Einstellungen

**Sprungweite in Sekunden** legt die Schrittweite für Umschalt+Pfeil links und Umschalt+Pfeil rechts fest: 1–999 Sekunden, standardmäßig 5.

In den NVDA-Einstellungen unter Sonos lässt sich **Titel protokollieren** einschalten und eine Protokolldatei auswählen. Diese Einstellungen gelten für alle NVDA-Profile. Die Protokollierung ist standardmäßig ausgeschaltet. Die Standarddatei heißt `sonos.log` und liegt im Dokumente-Ordner. Über Durchsuchen lässt sich ein anderer Speicherort wählen; Öffnen öffnet das Protokoll in der Standardanwendung.

Titel und Interpret werden mit einem Zeitstempel aufgezeichnet. Bei Änderungen wird ein neuer Eintrag angehängt. Die Prüfung erfolgt alle drei Sekunden und läuft auch beim Arbeiten in anderen Anwendungen weiter, solange Sonos geöffnet bleibt. Protokolliert wird die ausgewählte Lautsprechergruppe. Start- und Endmarkierungen trennen die Protokollierungssitzungen. Alt+Umschalt+L schaltet die Protokollierung in Sonos um.

## Änderungen

### 2026.1

- Optionale Titelprotokollierung hinzugefügt, umschaltbar mit Alt+Umschalt+L.
- Sonos-Einstellungskategorie hinzugefügt. Die Einstellungen gelten global.
- Rückmeldung für den Sonos-Favoritenbefehl Strg+8 hinzugefügt.
- Ansage der Titelanzahl in der Warteschlange hinzugefügt (Alt+Umschalt+Q).
- Einstellbares Vor- und Zurückspringen (standardmäßig fünf Sekunden) (Umschalt+Pfeil rechts und Umschalt+Pfeil links) und den Positionsregler fokussieren (Umschalt+Pfeil hoch).
- Zu einer Zeit im Titel springen (Strg+J).
- Angezeigtes Albumcover in die Zwischenablage kopieren (Alt+Umschalt+A).
- Nächsten Titel ansagen (Alt+Umschalt+N) und die aktuelle Lautsprechergruppe mit Raumnamen separat ansagen (Alt+Umschalt+G).
- Rückmeldung beim Wechseln der Lautsprechergruppe mit Strg+Komma und Strg+Punkt.
- Für NVDA ab 2026.1 aktualisiert, mit modernen Erweiterungs-APIs und übersetzbaren Meldungen.
- Tastenkürzel der Erweiterung lassen sich in NVDAs Dialog für Eingaben zuweisen; erweiterte Sonos-Tastenkürzel behalten ihre Tasten.
- Der Positionsregler liest Minuten und Sekunden vor; doppelte Beschriftungen wurden bereinigt und Ansagen gekürzt.
- Lautsprechernamen im Musik-EQ-Menü korrigiert und das Kontrollkästchen zum Aktivieren eines Weckers beschriftet.

### Frühere Versionen

- 1.4: NVDA 2019.3 kompatibel.
- 1.3: NVDA 2019.1 kompatibel.
- 1.2: Unterstützung für Sonos Desktop 9.2 hinzugefügt. Für ältere Versionen die Erweiterung 1.1 verwenden.
- 1.1: Die Ansicht der Tastenkürzel wird vorgelesen.
- 1.0: Erste Veröffentlichung.

## Ursprüngliche Erweiterung

- [Ursprüngliches Projekt](https://github.com/Novalis7747/sonos)
- [Originalversion 1.4 herunterladen](https://github.com/Novalis7747/sonos/raw/master/sonos-1.4.nvda-addon)

Lizenz: GNU GPL v2.
