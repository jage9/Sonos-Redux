# Sonos Redux

Updated support and enhancements for the Sonos desktop app with NVDA. Requires NVDA 2026.1 or later.

[Download the latest add-on](https://github.com/jage9/Sonos-Redux/releases/latest/download/sonos-redux.nvda-addon)

Originally by Ralf Kefferpuetz <novalis7747@live.com>.

Updated by J.J. Meddaugh <jj@bestmidi.com>.

## Add-on shortcuts

| Shortcut | Action |
| --- | --- |
| Control+1 | Read the current track; press twice to copy. |
| Control+2 | Show Now Playing information, including station details when available. |
| Control+3 | Search YouTube for the current track. |
| Alt+Shift+Y | Fetch lyrics for the current track. |
| Control+J | Jump to a time or seek by a signed amount. |
| Control+V | Set the selected speaker group's volume. |
| Control+Shift+V | Fade out, pause, and restore volume (default five seconds). |
| Alt+Shift+L | Toggle track logging. |
| Alt+Shift+K | Cycle track title announcements: Off, Everywhere, Sonos focused. |
| Alt+Shift+S | Read sleep timer status. |
| Alt+Shift+J | Jump to the last 30 seconds of a track (configurable). |
| Alt+Shift+F5 | Set loop start. |
| Alt+Shift+F6 | Set loop end. |
| Alt+Shift+F7 | Start looping. |
| Alt+Shift+F8 | Stop looping and continue playback. |
| Alt+Shift+F9 | Read loop start, end, and duration. |
| Alt+Shift+G | Read the current speaker group and its rooms. |
| Alt+Shift+Q | Read the number of tracks in the queue. |
| Alt+Shift+N | Read the next track, or the SiriusXM channel when playing SiriusXM. |
| Alt+Shift+A | Copy the displayed album artwork. |
| Alt+Shift+V | Read volume. |
| Alt+Shift+M | Read mute state. |
| Alt+Shift+R | Read repeat mode. |
| Alt+Shift+E | Read shuffle state. |
| Alt+Shift+T | Read crossfade state. |
| Alt+Shift+U | Read elapsed time. |
| Alt+Shift+I | Read track position, duration, and percentage. |
| Alt+Shift+O | Read remaining time. |
| Shift+Left Arrow | Seek backward (default five seconds). |
| Shift+Right Arrow | Seek forward (default five seconds). |
| Shift+Up Arrow | Focus the track scrubber. |

## Enhanced Sonos shortcuts

| Shortcut | Action |
| --- | --- |
| Control+M | Toggle mute and announce its state. |
| Control+R | Cycle repeat mode and announce it. |
| Control+E | Toggle shuffle and announce its state. |
| Control+T | Toggle crossfade and announce its state. |
| Control+8 | Open Sonos Favorites and announce it. |
| Control+, | Switch to the previous group and announce it. |
| Control+. | Switch to the next group and announce it. |
| Control+K | Open Sonos keyboard shortcut help. |

Control+V opens a volume field from 0 to 100. Type a value or use Up and Down Arrow, then press Enter to apply it. Control+Shift+V fades to zero, pauses playback, and restores the original volume. Keep Sonos in front with the Play/Pause button visible until it finishes. An unclear starting icon is treated as playing; if pause cannot be confirmed afterward, volume stays at zero.

Set loop start and end on a seekable track, then press Alt+Shift+F7 to jump to the start and repeat that section. If playback is paused, use Sonos Play/Pause to resume it. Alt+Shift+F8 turns looping off and continues from the current position. Leaving Sonos stops looping; changing tracks or groups clears the markers. Loop timing is approximate.

Control+J accepts seconds, minutes:seconds, or hours:minutes:seconds. Start with + or - for a relative jump, such as +30 or -1:15. Relative jumps use the current position when confirmed and stop at the track boundaries.

Time announcements and lyrics matching also use timing from non-seekable tracks when Sonos provides it. Seeking remains unavailable for those tracks.

## Lyrics

Press Alt+Shift+Y to fetch lyrics from [LRCLIB](https://lrclib.net/). A matching recording opens directly; otherwise, choose from the available recordings by title, artist, album, and length. Lyrics open in an accessible window where you can read and copy them. In the lyrics window, press Control+S to save a text file. Timed lyrics are displayed as ordinary text for now.

The lookup sends the current title, artist, album and track length when available, along with the add-on version and a random installation ID. This ID contains no personal or device information but lets LRCLIB recognize requests from the same installation. It is saved with NVDA's global settings. No account or API key is needed. Only requesting lyrics contacts the service; repeated requests for the same track reuse the last result while Sonos remains open.

## Settings

**Fade seconds** sets the fade length for Control+Shift+V: 1–999 seconds, default 5.

**Track seek seconds** sets how far Shift+Left Arrow and Shift+Right Arrow move: 1–999 seconds, default 5. **Seek seconds from end of track** sets the Alt+Shift+J jump: 1–999 seconds, default 30. A shorter track jumps to its start.

In NVDA Settings, choose Sonos to turn on **Log track titles** and choose a log filename. These settings apply across all NVDA profiles. Logging is off by default. The default file is `sonos.log` in your Documents folder. Browse lets you choose another location; Open opens the log in your default application.

Logging records the current track title and artist with a timestamp, then appends an entry when they change. It checks every three seconds and continues while you use other apps, as long as Sonos remains open. It follows the selected speaker group. Start and end markers separate logging sessions. Press Alt+Shift+L in Sonos to toggle logging.

**Track title announcements** offers Off (the default), Everywhere, and Only while Sonos is focused. It speaks the new title and artist when the selected group changes tracks and works without logging. Alt+Shift+K cycles these choices in Sonos. The first check establishes the current track; changes shorter than three seconds may be missed.

**Advanced** opens the randomly generated lyrics key. This identifies the installation to LRCLIB; it is not an API credential. You can edit it or clear the field to generate a new key. Changes apply when you save NVDA Settings.

## Changelog

### 2026.1

- Added lyrics lookup from LRCLIB (Alt+Shift+Y).

- Added signed relative times in Jump to Time (+30, -1:15).
- Added temporary looping bookmarks (Alt+Shift+F5–F9).

- Added optional track logging, toggled with Alt+Shift+L.
- Added optional track title announcements (Alt+Shift+K) and sleep timer status (Alt+Shift+S).
- Expanded detailed Now Playing information; Alt+Shift+N reports the SiriusXM channel when available.
- Added a configurable jump to the end portion of a track (Alt+Shift+J).
- Added a Sonos settings panel. Settings are global.
- Added Favorites feedback for Sonos Ctrl+8.
- Added queue count reporting (Alt+Shift+Q).
- Added adjustable track seeking (default five seconds) (Shift+Right Arrow and Shift+Left Arrow) and scrubber focus (Shift+Up Arrow).
- Added Jump to Time (Ctrl+J), a numeric volume dialog (Ctrl+V), and an adjustable fade out with pause and volume restoration (Ctrl+Shift+V).
- Added copying displayed album art to the clipboard (Alt+Shift+A).
- Added next-track announcements (Alt+Shift+N) and a separate current speaker group command with room names (Alt+Shift+G).
- Added feedback when switching speaker groups with Ctrl+Comma and Ctrl+Period.
- Updated for NVDA 2026.1 and later, using modern add-on APIs and translatable messages.
- Made add-on shortcuts assignable through NVDA's Input Gestures dialog; enhanced native Sonos shortcuts retain their keys.
- Made the scrubber report minutes and seconds, cleaned up duplicate control labels, and shortened speech.
- Fixed speaker names in the Music EQ menu and labeled the alarm Enabled checkbox.

### Earlier versions

- 1.4: NVDA 2019.3 compatible.
- 1.3: NVDA 2019.1 compatible.
- 1.2: Added support for Sonos Desktop 9.2. For versions before 9.2, use add-on version 1.1.
- 1.1: Made the keyboard shortcuts screen speak.
- 1.0: Initial release.

## Original add-on

- [Original project](https://github.com/Novalis7747/sonos)
- [Original version 1.4 download](https://github.com/Novalis7747/sonos/raw/master/sonos-1.4.nvda-addon)

Licensed under GNU GPL v2.
