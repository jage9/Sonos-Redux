# Sonos

Originally by Ralf Kefferpuetz <novalis7747@live.com>.

Updated by J.J. Meddaugh <jj@bestmidi.com>.

## Add-on shortcuts

| Shortcut | Action |
| --- | --- |
| Control+1 | Read the current track; press twice to copy. |
| Control+2 | Show track information. |
| Control+3 | Search YouTube for the current track. |
| Control+J | Jump to a time in the track. |
| Alt+Shift+G | Read the current speaker group. |
| Alt+Shift+N | Read the next track. |
| Alt+Shift+A | Copy the displayed album artwork. |
| Alt+Shift+V | Read volume. |
| Alt+Shift+M | Read mute state. |
| Alt+Shift+R | Read repeat mode. |
| Alt+Shift+E | Read shuffle state. |
| Alt+Shift+T | Read crossfade state. |
| Alt+Shift+U | Read elapsed time. |
| Alt+Shift+I | Read track position, duration, and percentage. |
| Alt+Shift+O | Read remaining time. |
| Shift+Left Arrow | Seek backward five seconds. |
| Shift+Right Arrow | Seek forward five seconds. |
| Shift+Up Arrow | Focus the track scrubber. |

## Enhanced Sonos shortcuts

| Shortcut | Action |
| --- | --- |
| Control+M | Toggle mute and announce its state. |
| Control+R | Cycle repeat mode and announce it. |
| Control+E | Toggle shuffle and announce its state. |
| Control+T | Toggle crossfade and announce its state. |
| Control+, | Switch to the previous group and announce it. |
| Control+. | Switch to the next group and announce it. |
| Control+K | Open Sonos keyboard shortcut help. |

## Changelog

### 2026.1

- Added five-second track seeking (Shift+Right Arrow and Shift+Left Arrow) and scrubber focus (Shift+Up Arrow).
- Added Jump to Time (Ctrl+J).
- Added copying displayed album art to the clipboard (Alt+Shift+A).
- Added next-track announcements (Alt+Shift+N) and a separate current speaker group command (Alt+Shift+G).
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
