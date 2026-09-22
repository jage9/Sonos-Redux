# Sonos Redux

Originally by Ralf Kefferpuetz <novalis7747@live.com>.

Updated by J.J. Meddaugh <jj@bestmidi.com>.

## Add-on shortcuts

### Information

| Shortcut | Action |
| --- | --- |
| Control+1 | Read the current track; press twice to copy. |
| Control+2 | Show Now Playing information. |
| Alt+Shift+G | Read the current speaker group and its rooms. |
| Alt+Shift+Q | Read the number of tracks in the queue. |
| Alt+Shift+N | Read the next track, or the SiriusXM channel when playing SiriusXM. |
| Alt+Shift+V | Read volume. |
| Alt+Shift+M | Read mute state. |
| Alt+Shift+R | Read repeat mode. |
| Alt+Shift+E | Read shuffle state. |
| Alt+Shift+T | Read crossfade state. |
| Alt+Shift+U | Read elapsed time. |
| Alt+Shift+I | Read track position, duration, and percentage. |
| Alt+Shift+O | Read remaining time. |
| Alt+Shift+S | Read sleep timer status. |

### Functions

| Shortcut | Action |
| --- | --- |
| Shift+Left Arrow | Seek backward (default five seconds). |
| Shift+Right Arrow | Seek forward (default five seconds). |
| Shift+Up Arrow | Focus the track scrubber. |
| Control+J | Jump to a time or seek by an amount plus or minus. |
| Control+V | Set the selected speaker group's volume. |
| Control+Shift+V | Fade out, pause, and restore volume (default five seconds). Note: keep the Sonos window focused during the fade. |
| Alt+Shift+L | Toggle track logging. |
| Alt+Shift+K | Cycle track announce: Off, Everywhere, Only while Sonos is focused. |
| Alt+Shift+J | Jump to the last 30 seconds of a track (configurable). |
| Control+3 | Search YouTube for the current track. |
| Alt+Shift+Y | Fetch lyrics for the current track. |
| Alt+Shift+A | Copy the displayed album artwork. |

### Looping

You can loop a portion of a track to hear it on repeat. Due to the nature of Sonos, loops are approximate, and will have a gap between loops. Looping only works for seekable tracks. Keep Sonos focused while looping. Changing tracks or speaker groups clears your loop.

| Shortcut | Action |
| --- | --- |
| Alt+Shift+F5 | Set loop start. |
| Alt+Shift+F6 | Set loop end. |
| Alt+Shift+F7 | Start looping. |
| Alt+Shift+F8 | Stop looping and continue playback. |
| Alt+Shift+F9 | Read loop start, end, and duration. |

## Enhanced Sonos shortcuts

These are existing Sonos keyboard shortcuts and cannot be changed. Additional speech feedback has been added.

| Shortcut | Action |
| --- | --- |
| Control+M | Toggle mute and announce its state. |
| Control+R | Cycle repeat mode and announce it. |
| Control+E | Toggle shuffle and announce its state. |
| Control+T | Toggle crossfade and announce its state. |
| Control+8 | Open Sonos Favorites. |
| Control+Comma | Switch to the previous group and announce it. |
| Control+Period | Switch to the next group and announce it. |
| Control+K | Open Sonos keyboard shortcut help. |

## Lyrics

Press Alt+Shift+Y to fetch lyrics from [LRCLIB](https://lrclib.net/). A matching recording opens directly; otherwise, choose from the available recordings by title, artist, album, and length. Lyrics open in an accessible window where you can read and copy them. In the lyrics window, press Control+S to save a text file.

The lookup sends the current title, artist, album and track length when available, along with the add-on version and a random installation ID. This ID contains no personal or device information but lets LRCLIB recognize requests from the same installation. It is saved with NVDA's global settings. No account or API key is needed. Only requesting lyrics contacts the service; repeated requests for the same track reuse the last result while Sonos remains open.

## Jump to Time

Ctrl+J by default, this command will let you jump to a place in the track. Use a time like 03:22 to jump directly to it. You can also put plus or minus before the time to jump forward or backward by hours, minutes, or seconds.

## Settings

To access Settings, go to the NVDA Menu with NVDA+N, then Preferences -> Settings and look for the Sonos group.

**Fade seconds** sets the fade length for Control+Shift+V: 1–999 seconds, default 5.

**Track seek seconds** sets how far Shift+Left Arrow and Shift+Right Arrow move: 1–999 seconds, default 5.

**Seek seconds from end of track** sets the Alt+Shift+J jump: 1–999 seconds, default 30. A shorter track jumps to its start.

In NVDA Settings, choose Sonos to turn on **Log track titles** and choose a log filename. These settings apply across all NVDA profiles. Logging is off by default. The default file is `sonos.log` in your Documents folder. Browse lets you choose another location; Open opens the log in your default application.

Logging records the current track title and artist with a timestamp, then appends an entry when they change. It checks every three seconds and continues while you use other apps, as long as Sonos remains open. It follows the selected speaker group. Start and end markers separate logging sessions. Press Alt+Shift+L in Sonos to toggle logging.

**Track announce** offers Off (the default), Everywhere, and Only while Sonos is focused. It speaks the new title and artist when the selected group changes tracks and works without logging. Alt+Shift+K cycles these choices in Sonos. The first check establishes the current track; changes shorter than three seconds may be missed.

**Advanced** opens the randomly generated lyrics key. This identifies the installation to LRCLIB; it is not an API credential. You can edit it or clear the field to generate a new key. Changes apply when you save NVDA Settings.

## Other Features

Various menus and dialogs read more cleanly. Extraneous button text is cleaned up, and dialogs like keyboard shortcuts read correctly.

## Original add-on

- [Original project](https://github.com/Novalis7747/sonos)
- [Original version 1.4 download](https://github.com/Novalis7747/sonos/raw/master/sonos-1.4.nvda-addon)

Licensed under GNU GPL v2.
