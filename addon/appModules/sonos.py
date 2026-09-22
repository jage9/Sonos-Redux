# Sonos desktop support for NVDA.
# Copyright (C) 2019 Ralf Kefferpuetz and contributors.
# Copyright (C) 2026 J.J. Meddaugh <jj@bestmidi.com>.
# SPDX-License-Identifier: GPL-2.0-only

from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from html import escape
import json
from threading import Thread
import webbrowser
import math
import re
from time import perf_counter, sleep, time
from email.utils import parsedate_to_datetime

import addonHandler
import api
import appModuleHandler
from comtypes import COMError
import controlTypes
import core
import keyboardHandler
import inputCore
from logHandler import log
from NVDAObjects.UIA import UIA
from scriptHandler import script, getLastScriptRepeatCount
import UIAHandler
import ui

addonHandler.initTranslation()


class ControlUnavailable(Exception):
    """The current Sonos view does not expose the requested control."""


class NoTrackSlider(ControlUnavailable):
    pass


def _text(obj):
    return (obj.name or "").strip()


def _find(root, automationId):
    client = UIAHandler.handler.clientObject
    element = root.UIAElement if isinstance(root, UIA) else client.ElementFromHandle(root.windowHandle)
    condition = client.CreatePropertyCondition(UIAHandler.UIA_AutomationIdPropertyId, automationId)
    # Sonos omits some text from bulk searches; a filtered raw-tree walker finds it.
    walker = client.CreateTreeWalker(condition)
    found = walker.GetFirstChildElementBuildCache(element, UIAHandler.handler.baseCacheRequest)
    if not found:
        raise ControlUnavailable(automationId)
    obj = UIA(UIAElement=found)
    if not obj:
        raise ControlUnavailable(automationId)
    return obj


def _percent(pattern):
    minimum, maximum, current = pattern.CurrentMinimum, pattern.CurrentMaximum, pattern.CurrentValue
    if not all(math.isfinite(value) for value in (minimum, maximum, current)) or maximum <= minimum:
        raise ControlUnavailable("Invalid slider range")
    return round(100 * (current - minimum) / (maximum - minimum))


def _playbackIconState(width, height, pixels):
    """Recognize the white Sonos play triangle or pause bars; reject unclear images."""
    if width < 16 or height < 16 or len(pixels) != width * height * 3:
        return None
    rows = []
    for fraction in (.35, .5, .65):
        y = round((height - 1) * fraction)
        spans = []
        for x in range(round((width - 1) * .2), round((width - 1) * .8) + 1):
            offset = (y * width + x) * 3
            if min(pixels[offset:offset + 3]) >= 200:
                if spans and spans[-1][1] == x:
                    spans[-1][1] = x + 1
                else:
                    spans.append([x, x + 1])
        rows.append(spans)
    tolerance = max(1, width * .04)
    if all(len(row) == 1 for row in rows):
        lefts = [row[0][0] for row in rows]
        lengths = [row[0][1] - row[0][0] for row in rows]
        if (max(lefts) - min(lefts) <= tolerance
                and .25 * width <= min(lefts) <= .4 * width
                and .25 * width <= lengths[1] <= .5 * width
                and min(lengths) >= .1 * width
                and lengths[1] > 1.5 * max(lengths[0], lengths[2])):
            return "paused"
    if all(len(row) == 2 for row in rows):
        lengths = [end - start for row in rows for start, end in row]
        stable = all(
            max(row[bar][edge] for row in rows) - min(row[bar][edge] for row in rows) <= tolerance
            for bar in (0, 1) for edge in (0, 1)
        )
        if (stable and min(lengths) >= .025 * width and max(lengths) <= .13 * width
                and max(lengths) <= 2 * min(lengths)
                and all(.15 * width <= row[1][0] - row[0][1] <= .3 * width for row in rows)):
            return "playing"
    return None


def _format_seconds(value):
    seconds = max(0, round(value))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"


def _parse_time(text):
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3 or any(not part.isdecimal() for part in parts):
        raise ValueError("Use seconds, minutes:seconds or hours:minutes:seconds")
    numbers = [int(part) for part in parts]
    if any(number >= 60 for number in numbers[1:]):
        raise ValueError("Minutes and seconds after a colon must be below 60")
    seconds = 0
    for number in numbers:
        seconds = seconds * 60 + number
    return seconds


def _fetchLyrics(metadata, userAgent):
    """Look up a recording, then offer search candidates if no match exists."""
    def request(endpoint, params):
        req = Request("https://lrclib.net/api/" + endpoint + "?" + urlencode(params),
                      headers={"User-Agent": userAgent, "Accept": "application/json"})
        with urlopen(req, timeout=15) as response:
            payload = response.read(1024 * 1024 + 1)
        if len(payload) > 1024 * 1024:
            raise ValueError("Lyrics response is too large")
        return json.loads(payload)

    try:
        records = [request("get", metadata)]
        matched = True
    except HTTPError as error:
        if error.code != 404:
            raise
        error.close()
        sleep(.5)
        records = request("search", {key: metadata[key] for key in ("track_name", "artist_name")})
        matched = False
    if not isinstance(records, list) or len(records) > 20:
        raise ValueError("Invalid lyrics results")
    for record in records:
        if (not isinstance(record, dict)
                or any(not isinstance(record.get(key), str) for key in ("trackName", "artistName", "albumName"))
                or not isinstance(record.get("duration"), (int, float))
                or not math.isfinite(record["duration"]) or record["duration"] < 0
                or any(record.get(key) is not None and not isinstance(record[key], str)
                       for key in ("plainLyrics", "syncedLyrics"))
                or not isinstance(record.get("instrumental", False), bool)):
            raise ValueError("Invalid lyrics record")
    return records, matched


def _lyricsText(record):
    if record.get("plainLyrics"):
        return record["plainLyrics"].strip()
    lines = []
    for line in (record.get("syncedLyrics") or "").splitlines():
        if re.match(r"^\[[A-Za-z]+:", line):
            continue
        lines.append(re.sub(r"^(?:\[\d+:\d+(?:\.\d+)?\])+", "", line).strip())
    return "\n".join(lines).strip()


class ShortcutItem(UIA):
    # Shortcut rows and speaker menu items label themselves through their first children.
    def _get_name(self):
        first = self.firstChild
        second = first.next if first else None
        name = " ".join(filter(None, (_text(child) for child in (first, second) if child)))
        return name or super()._get_name()


class ButtonLabels(UIA):
    description = ""
    keyboardShortcut = ""

    def _get_name(self):
        name = super()._get_name()
        if not name and self.UIAAutomationId == "equalizerMenuButton":
            return super()._get_description() or name
        return name


class AlarmEnabledCheckbox(UIA):
    def _get_name(self):
        return super()._get_name() or _("Enabled")


class Scrubber(UIA):
    def _get_value(self):
        try:
            value = self.UIARangeValue
            if value is None or not math.isfinite(value):
                return super()._get_value()
        except (COMError, TypeError, ValueError):
            return super()._get_value()
        return _format_seconds(value)


class AppModule(appModuleHandler.AppModule):
    scriptCategory = _("Sonos")

    def chooseNVDAObjectOverlayClasses(self, obj, clsList):
        if not isinstance(obj, UIA):
            return
        if obj.role == controlTypes.Role.SLIDER and obj.UIAAutomationId == "PART_Scrubber":
            clsList.insert(0, Scrubber)
        elif obj.role in (controlTypes.Role.BUTTON, controlTypes.Role.TOGGLEBUTTON) and (
            obj.UIAAutomationId in (
                "muteButton", "repeatToggleButton", "shuffleToggleButton", "crossfadeToggleButton",
                "playButton", "sleepTimerButton_1", "equalizerButton", "equalizerMenuButton",
                "pauseAllButton_1", "alarmsButton_1",
            )
            # Button_1 is reused elsewhere; only these confirmed action markers identify our buttons.
            or (obj.UIAAutomationId == "Button_1"
                and UIA._get_keyboardShortcut(obj) in ("Back", "Info", "Now Playing Button"))
        ):
            clsList.insert(0, ButtonLabels)
        elif (
            obj.role == controlTypes.Role.CHECKBOX
            and not obj.name
            and not obj.UIAAutomationId
            and obj.windowText in ("Alarms", "Wecker")
        ):
            clsList.insert(0, AlarmEnabledCheckbox)
        elif (
            obj.role == controlTypes.Role.DATAITEM
            and (obj.name or "").startswith("Sonos.Controller.Desktop.Main.KeyboardShortcut")
        ):
            clsList.insert(0, ShortcutItem)
        elif (
            obj.role == controlTypes.Role.MENUITEM
            and obj.name == "Sonos.Controller.Desktop.SCLib.ViewModel.ZonePlayerViewModel"
        ):
            clsList.insert(0, ShortcutItem)

    def _root(self):
        root = api.getForegroundObject()
        if root.processID != self.processID:
            raise ControlUnavailable("Sonos is not in the foreground")
        return root

    def _run(self, action):
        try:
            action()
        except NoTrackSlider:
            ui.message(_("No track slider"))
        except ControlUnavailable:
            ui.message(_("This control is unavailable in the current Sonos view."))
        except COMError:
            log.debugWarning("Sonos control is no longer available", exc_info=True)
            ui.message(_("Sonos is not responding or the control is unavailable."))
        except Exception:
            log.exception("Sonos command failed")
            ui.message(_("Sonos command failed. See the NVDA log for details."))

    def _scrubber(self, root=None):
        try:
            slider = self._transport("PART_Scrubber", root=root)
            pattern = slider.UIARangeValuePattern
            if not pattern:
                raise ControlUnavailable("Scrubber has no range pattern")
            _percent(pattern)  # Validate before reporting or seeking.
        except ControlUnavailable as error:
            raise NoTrackSlider() from error
        return slider, pattern

    @script(description=_("Report the current track position."), gesture="kb:alt+shift+i", speakOnDemand=True)
    def script_reportScrub(self, gesture):
        def report():
            slider, pattern = self._scrubber()
            ui.message(_("{elapsed} of {total}, {percent}%").format(
                elapsed=_format_seconds(pattern.CurrentValue),
                total=_format_seconds(pattern.CurrentMaximum),
                percent=_percent(pattern),
            ))
        self._run(report)

    @script(description=_("Focus the track scrubber."), gesture="kb:shift+upArrow")
    def script_focusScrub(self, gesture):
        def focus():
            slider, pattern = self._scrubber()
            if not slider.UIAElement.CurrentIsKeyboardFocusable:
                ui.message(_("The track scrubber does not accept keyboard focus."))
                return
            slider.setFocus()
        self._scrubGesture(gesture, focus)

    def _scrubGesture(self, gesture, action):
        focus = api.getFocusObject()
        try:
            root = self._root()
            if (
                not focus
                or focus.role == controlTypes.Role.EDITABLETEXT
                or controlTypes.State.EDITABLE in focus.states
                or root.role == controlTypes.Role.DIALOG
            ):
                gesture.send()
                return
            _find(root, "transportBar")
        except (ControlUnavailable, COMError):
            gesture.send()
            return
        self._run(action)

    def _transport(self, identifier, root=None):
        control = _find(_find(root if root is not None else self._root(), "transportBar"), identifier)
        if controlTypes.State.UNAVAILABLE in control.states:
            raise ControlUnavailable(identifier)
        return control

    def _seek(self, seconds):
        slider, pattern = self._scrubber()
        self._setPosition(pattern, pattern.CurrentValue + seconds, self._root().windowHandle)

    def _setPosition(self, pattern, target, windowHandle, report=True):
        if pattern.CurrentIsReadOnly:
            raise NoTrackSlider("Scrubber is read-only")
        _percent(pattern)
        target = max(pattern.CurrentMinimum, min(target, pattern.CurrentMaximum))
        focus = api.getFocusObject()
        pattern.SetValue(target)
        # Sonos focuses the slider from SetValue. Keep keyboard navigation where it was.
        if focus and focus.processID == self.processID:
            try:
                focusedElement = UIAHandler.handler.clientObject.GetFocusedElement()
                if (
                    focusedElement
                    and focusedElement.CurrentProcessId == self.processID
                    and focusedElement.CurrentAutomationId == "PART_Scrubber"
                    and not (isinstance(focus, UIA) and focus.UIAAutomationId == "PART_Scrubber")
                ):
                    focus.setFocus()
            except (COMError, RuntimeError, NotImplementedError):
                log.debugWarning("Could not restore Sonos focus after seeking", exc_info=True)
        self._seekSequence = getattr(self, "_seekSequence", 0) + 1
        if report:
            core.callLater(250, self._reportSeekResult, windowHandle, self._seekSequence)

    def _reportSeekResult(self, windowHandle, sequence):
        if sequence != self._seekSequence or api.getForegroundObject().windowHandle != windowHandle:
            return
        def report():
            slider, pattern = self._scrubber()
            ui.message(_format_seconds(pattern.CurrentValue))
        self._run(report)

    @script(description=_("Seek backward."), gesture="kb:shift+leftArrow", speakOnDemand=True)
    def script_adjustScrubBackward(self, gesture):
        import config
        self._scrubGesture(gesture, lambda: self._seek(-config.conf["sonos"]["seekSeconds"]))

    @script(description=_("Seek forward."), gesture="kb:shift+rightArrow", speakOnDemand=True)
    def script_adjustScrubForward(self, gesture):
        import config
        self._scrubGesture(gesture, lambda: self._seek(config.conf["sonos"]["seekSeconds"]))

    @script(description=_("Jump to the last seconds of the track."), gesture="kb:alt+shift+j", speakOnDemand=True)
    def script_jumpNearEnd(self, gesture):
        import config

        def jump():
            slider, pattern = self._scrubber()
            self._setPosition(pattern, pattern.CurrentMaximum - config.conf["sonos"]["endJumpSeconds"],
                              self._root().windowHandle)
        self._scrubGesture(gesture, jump)

    def _loopContext(self, saved=None):
        if saved is None:
            root = self._root()
        else:
            element = UIAHandler.handler.clientObject.ElementFromHandleBuildCache(
                saved["window"], UIAHandler.handler.baseCacheRequest)
            if not element:
                raise NoTrackSlider()
            root = UIA(UIAElement=element)
        slider, pattern = self._scrubber(root=root)
        if pattern.CurrentIsReadOnly:
            raise NoTrackSlider()
        track = self._trackInfo(includeGroup=True, root=root)
        if not track[1]:
            raise ControlUnavailable("No track identity for loop")
        return root, pattern, (track, pattern.CurrentMaximum)

    def _currentLoop(self):
        saved = getattr(self, "_loop", None)
        if saved is not None:
            root, pattern, track = self._loopContext()
            if root.windowHandle == saved["window"] and track == saved["track"]:
                return saved, pattern
            self._loop = None
        ui.message(_("No loop bookmark"))
        return None, None

    @script(description=_("Set loop start."), gesture="kb:alt+shift+f5", speakOnDemand=True)
    def script_setLoopStart(self, gesture):
        def mark():
            root, pattern, track = self._loopContext()
            saved = self._loop = dict(window=root.windowHandle, track=track,
                                      start=pattern.CurrentValue, end=None, active=False)
            ui.message(_("Loop start {time}").format(time=_format_seconds(saved["start"])))
            core.callLater(1000, self._watchLoop, saved)
        self._scrubGesture(gesture, mark)

    @script(description=_("Set loop end."), gesture="kb:alt+shift+f6", speakOnDemand=True)
    def script_setLoopEnd(self, gesture):
        def mark():
            saved, pattern = self._currentLoop()
            if saved is None:
                return
            if pattern.CurrentValue <= saved["start"]:
                ui.message(_("Loop end must be after loop start"))
                return
            saved["end"] = pattern.CurrentValue
            saved["active"] = False
            ui.message(_("Loop end {time}").format(time=_format_seconds(saved["end"])))
        self._scrubGesture(gesture, mark)

    @script(description=_("Start looping."), gesture="kb:alt+shift+f7", speakOnDemand=True)
    def script_startLoop(self, gesture):
        def start():
            saved, pattern = self._currentLoop()
            if saved is None:
                return
            if saved["end"] is None:
                ui.message(_("Set loop end first"))
                return
            self._setPosition(pattern, saved["start"], saved["window"], report=False)
            saved["active"] = True
            ui.message(_("Loop on"))
        self._scrubGesture(gesture, start)

    @script(description=_("Stop looping and continue playback."),
            gesture="kb:alt+shift+f8", speakOnDemand=True)
    def script_stopLoop(self, gesture):
        def stop():
            saved, pattern = self._currentLoop()
            if saved is None:
                return
            saved["active"] = False
            ui.message(_("Loop off"))
        self._scrubGesture(gesture, stop)

    @script(description=_("Report loop start, end, and duration."),
            gesture="kb:alt+shift+f9", speakOnDemand=True)
    def script_reportLoop(self, gesture):
        def report():
            saved, pattern = self._currentLoop()
            if saved is None:
                return
            if saved["end"] is None:
                ui.message(_("Loop start {time}").format(time=_format_seconds(saved["start"])))
            else:
                ui.message(_("Loop start {start}, end {end}, duration {duration}").format(
                    start=_format_seconds(saved["start"]), end=_format_seconds(saved["end"]),
                    duration=_format_seconds(saved["end"] - saved["start"])))
        self._run(report)

    def _watchLoop(self, saved):
        if saved is not getattr(self, "_loop", None):
            return
        try:
            root, pattern, track = self._loopContext(saved)
            if track != saved["track"]:
                self._loop = None
                return
            if saved["active"]:
                foreground = api.getForegroundObject()
                if not foreground or foreground.windowHandle != saved["window"]:
                    saved["active"] = False
                elif pattern.CurrentValue >= saved["end"]:
                    self._setPosition(pattern, saved["start"], saved["window"], report=False)
        except (ControlUnavailable, COMError, RuntimeError, OSError):
            self._loop = None
            return
        # ponytail: UIA polling and network seeks make loops approximate, not sample-accurate.
        core.callLater(250 if saved["active"] else 1000, self._watchLoop, saved)

    def terminate(self):
        super().terminate()
        self._loop = None
        self._lyricsRequestToken = None

    @script(description=_("Report elapsed track time."), gesture="kb:alt+shift+u", speakOnDemand=True)
    def script_reportCurrent(self, gesture):
        self._run(lambda: ui.message(_("{time} elapsed").format(time=_format_seconds(self._scrubber()[1].CurrentValue))))

    @script(description=_("Report remaining track time."), gesture="kb:alt+shift+o", speakOnDemand=True)
    def script_reportRemaining(self, gesture):
        def report():
            slider, pattern = self._scrubber()
            ui.message(_("{time} remaining").format(time=_format_seconds(pattern.CurrentMaximum - pattern.CurrentValue)))
        self._run(report)

    @script(description=_("Report the active room volume."), gesture="kb:alt+shift+v", speakOnDemand=True)
    def script_reportVolume(self, gesture):
        def report():
            slider = self._transport("PART_VolumeSlider")
            pattern = slider.UIARangeValuePattern
            if not pattern:
                raise ControlUnavailable("Volume has no range pattern")
            ui.message(_("Volume {percent}%").format(percent=_percent(pattern)))
        self._run(report)

    @script(description=_("Set the selected speaker group's volume."), gesture="kb:control+v", speakOnDemand=True)
    def script_setVolume(self, gesture):
        if getattr(self, "_volumeDialogOpen", False):
            return

        def prepare():
            import wx

            slider = self._transport("PART_VolumeSlider")
            pattern = slider.UIARangeValuePattern
            if not pattern or pattern.CurrentIsReadOnly:
                raise ControlUnavailable("Volume cannot be adjusted")
            percent = _percent(pattern)
            group = self._groupInfo()
            focus = api.getFocusObject()
            self._volumeSequence = getattr(self, "_volumeSequence", 0) + 1
            self._volumeDialogOpen = True
            wx.CallAfter(self._run, lambda: self._showVolumeDialog(
                self._root().windowHandle, group, percent, focus
            ))
        self._scrubGesture(gesture, prepare)

    def _showVolumeDialog(self, windowHandle, group, percent, focus):
        import wx
        from gui.message import displayDialogAsModal

        dialog = None
        try:
            dialog = wx.NumberEntryDialog(
                None, "", _("Volume for {group}:").format(group=group), _("Set volume"),
                percent, 0, 100,
            )
            if displayDialogAsModal(dialog) == wx.ID_OK:
                target = dialog.GetValue()
                if 0 <= target <= 100:
                    core.callLater(100, self._run, lambda: self._setVolume(target, windowHandle, group, focus))
        finally:
            if dialog is not None:
                dialog.Destroy()
            self._volumeDialogOpen = False

    def _setVolume(self, percent, windowHandle, group, focus):
        self._volumeSequence = getattr(self, "_volumeSequence", 0) + 1
        if self._root().windowHandle != windowHandle or self._groupInfo() != group:
            ui.message(_("The speaker group changed. Open Set Volume again."))
            return
        slider = self._transport("PART_VolumeSlider")
        pattern = slider.UIARangeValuePattern
        if not pattern or pattern.CurrentIsReadOnly:
            raise ControlUnavailable("Volume cannot be adjusted")
        _percent(pattern)
        pattern.SetValue(pattern.CurrentMinimum + (pattern.CurrentMaximum - pattern.CurrentMinimum) * percent / 100)
        if focus and focus.processID == self.processID:
            try:
                focus.setFocus()
            except (COMError, RuntimeError, NotImplementedError):
                log.debugWarning("Could not restore Sonos focus after setting volume", exc_info=True)
        core.callLater(250, self._reportSetVolume, windowHandle, group)

    def _reportSetVolume(self, windowHandle, group):
        def report():
            if self._root().windowHandle != windowHandle or self._groupInfo() != group:
                return
            pattern = self._transport("PART_VolumeSlider").UIARangeValuePattern
            if not pattern:
                raise ControlUnavailable("Volume has no range pattern")
            ui.message(_("Volume for {group}: {percent}%").format(group=group, percent=_percent(pattern)))
        self._run(report)

    def _visiblePlayButton(self):
        button = self._transport("playButton")
        if not button.location or controlTypes.State.OFFSCREEN in button.states:
            raise ControlUnavailable("Play button is not visible")
        x, y, width, height = button.location
        if width < 16 or height < 16:
            raise ControlUnavailable("Play button has invalid bounds")
        hit = api.getDesktopObject().objectFromPoint(x + width // 2, y + height // 2)
        if not hit or hit.processID != self.processID or not any(
            getattr(obj, "UIAAutomationId", None) == "playButton" for obj in (hit, hit.parent)
        ):
            raise ControlUnavailable("Play button is covered")
        return button

    def _playbackState(self):
        import wx
        try:
            button = self._visiblePlayButton()
            x, y, width, height = button.location
            bitmap = wx.Bitmap(width, height)
            memory = wx.MemoryDC(bitmap)
            try:
                if not memory.Blit(0, 0, width, height, wx.ScreenDC(), x, y):
                    return None
            finally:
                memory.SelectObject(wx.NullBitmap)
            image = bitmap.ConvertToImage()
            return _playbackIconState(width, height, image.GetData())
        except (ControlUnavailable, COMError, RuntimeError, OSError):
            return None

    def _clickPlayPause(self):
        import mouseHandler
        import winUser
        button = self._visiblePlayButton()
        x, y, width, height = button.location
        oldPosition = winUser.getCursorPos()
        try:
            winUser.setCursorPos(x + width // 2, y + height // 2)
            mouseHandler.executeMouseEvent(winUser.MOUSEEVENTF_LEFTDOWN, 0, 0)
            mouseHandler.executeMouseEvent(winUser.MOUSEEVENTF_LEFTUP, 0, 0)
        finally:
            winUser.setCursorPos(*oldPosition)

    @script(description=_("Fade out the selected speaker group."),
            gesture="kb:control+shift+v", speakOnDemand=True)
    def script_fadeVolume(self, gesture):
        import config

        def fade():
            windowHandle = self._root().windowHandle
            group = self._groupInfo()
            pattern = self._transport("PART_VolumeSlider").UIARangeValuePattern
            if not pattern or pattern.CurrentIsReadOnly:
                raise ControlUnavailable("Volume cannot be adjusted")
            initial = _percent(pattern)
            if self._playbackState() == "paused":
                ui.message(_("Playback is already paused"))
                return
            # An unclear starting icon is treated as playing, as with the fade command.
            focusBeforeFade = api.getFocusObject()
            self._volumeSequence = getattr(self, "_volumeSequence", 0) + 1
            sequence = self._volumeSequence
            duration = config.conf["sonos"]["fadeSeconds"]
            started = perf_counter()

            def stillCurrent():
                foreground = api.getForegroundObject()
                return (sequence == self._volumeSequence and foreground
                        and foreground.windowHandle == windowHandle and self._groupInfo() == group)

            def finish(deadline, clicked=False, pausedChecks=0):
                if not stillCurrent():
                    return
                state = self._playbackState()
                if state == "paused":
                    pausedChecks += 1
                    if pausedChecks >= 2:
                        self._setVolume(initial, windowHandle, group, focusBeforeFade)
                        return
                else:
                    pausedChecks = 0
                    if not clicked:
                        self._clickPlayPause()
                        clicked = True
                if perf_counter() < deadline:
                    core.callLater(250, self._run, lambda: finish(deadline, clicked, pausedChecks))
                else:
                    ui.message(_("Could not confirm pause. Volume remains at zero."))

            def step():
                if not stillCurrent():
                    return
                pattern = self._transport("PART_VolumeSlider").UIARangeValuePattern
                if not pattern or pattern.CurrentIsReadOnly:
                    raise ControlUnavailable("Volume cannot be adjusted")
                _percent(pattern)
                remaining = max(0, duration - (perf_counter() - started))
                percent = initial * remaining / duration
                focus = api.getFocusObject()
                pattern.SetValue(pattern.CurrentMinimum
                                 + (pattern.CurrentMaximum - pattern.CurrentMinimum) * percent / 100)
                if focus and focus.processID == self.processID:
                    try:
                        focus.setFocus()
                    except (COMError, RuntimeError, NotImplementedError):
                        log.debugWarning("Could not restore Sonos focus during fade", exc_info=True)
                if remaining:
                    core.callLater(max(1, min(250, round(remaining * 1000))), self._run, step)
                else:
                    core.callLater(250, self._run, lambda: finish(perf_counter() + 5))

            ui.message(_("Fading out {group}").format(group=group))
            core.callLater(250, self._run, step)
        self._scrubGesture(gesture, fade)

    def _reportState(self, identifier):
        # Sonos supplies localized state text, including its repeat modes.
        control = self._transport(identifier)
        # Explicit commands still use provider text when focus descriptions are suppressed.
        description = control.UIAFullDescription or control.UIAHelpText
        if not description:
            raise ControlUnavailable("No playback-state description")
        ui.message(description)

    def _toggle(self, gesture, description, identifier, nativeKey):
        # Empty script descriptions hide native shortcuts from Input Gestures.
        # Handle Input Help here so it describes the shortcut without activating it.
        if inputCore.manager.isInputHelpActive:
            ui.message(f"{gesture.displayName}: {description}")
            return
        self._transport(identifier)
        windowHandle = self._root().windowHandle
        keyboardHandler.KeyboardInputGesture.fromName(nativeKey).send()
        def report():
            if api.getForegroundObject().windowHandle == windowHandle:
                self._run(lambda: self._reportState(identifier))
        core.callLater(250, report)

    @script(description=_("Report mute state."), gesture="kb:alt+shift+m", speakOnDemand=True)
    def script_reportMute(self, gesture):
        self._run(lambda: self._reportState("muteButton"))

    @script(gesture="kb:control+m", bypassInputHelp=True, speakOnDemand=True)
    def script_toggleMute(self, gesture):
        self._run(lambda: self._toggle(gesture, _("Toggle mute and report its state."), "muteButton", "control+m"))

    @script(description=_("Report repeat mode."), gesture="kb:alt+shift+r", speakOnDemand=True)
    def script_reportRepeat(self, gesture):
        self._run(lambda: self._reportState("repeatToggleButton"))

    @script(gesture="kb:control+r", bypassInputHelp=True, speakOnDemand=True)
    def script_toggleRepeat(self, gesture):
        self._run(lambda: self._toggle(gesture, _("Toggle repeat and report its mode."), "repeatToggleButton", "control+r"))

    @script(description=_("Report shuffle state."), gesture="kb:alt+shift+e", speakOnDemand=True)
    def script_reportShuffle(self, gesture):
        self._run(lambda: self._reportState("shuffleToggleButton"))

    @script(gesture="kb:control+e", bypassInputHelp=True, speakOnDemand=True)
    def script_toggleShuffle(self, gesture):
        self._run(lambda: self._toggle(gesture, _("Toggle shuffle and report its state."), "shuffleToggleButton", "control+e"))

    @script(description=_("Report crossfade state."), gesture="kb:alt+shift+t", speakOnDemand=True)
    def script_reportCrossfade(self, gesture):
        self._run(lambda: self._reportState("crossfadeToggleButton"))

    @script(gesture="kb:control+t", bypassInputHelp=True, speakOnDemand=True)
    def script_toggleCrossfade(self, gesture):
        self._run(lambda: self._toggle(gesture, _("Toggle crossfade and report its state."), "crossfadeToggleButton", "control+t"))

    @script(gesture="kb:control+8", bypassInputHelp=True, speakOnDemand=True)
    def script_favorites(self, gesture):
        if inputCore.manager.isInputHelpActive:
            ui.message(f"{gesture.displayName}: {_('Favorites')}")
            return
        keyboardHandler.KeyboardInputGesture.fromName("control+8").send()
        ui.message(_("Favorites"))

    @script(
        description=_("Read the current track. Press twice quickly to copy track information."),
        gesture="kb:control+1",
        speakOnDemand=True,
    )
    def script_speakInfo(self, gesture):
        def report():
            info, track = self._trackInfo()
            if getLastScriptRepeatCount() == 1:
                if track:
                    api.copyToClip(track, notify=True)
                else:
                    ui.message(_("No track information is available."))
            else:
                ui.message(info)
        self._run(report)

    @script(description=_("Show current track information in a browseable message."), gesture="kb:control+2", speakOnDemand=True)
    def script_browseInfo(self, gesture):
        def show():
            info, track = self._trackInfo(limit=4)
            ui.browseableMessage(info, title=_("Now playing"), isHtml=False)
        self._run(show)

    @script(description=_("Search YouTube for the current track."), gesture="kb:control+3")
    def script_openInYoutube(self, gesture):
        def search():
            info, track = self._trackInfo()
            if not track:
                ui.message(_("No track information is available."))
                return
            url = "https://www.youtube.com/results?" + urlencode({"search_query": track})
            if not webbrowser.open_new_tab(url):
                ui.message(_("Could not open the web browser."))
        self._run(search)

    @script(description=_("Fetch lyrics for the current track."), gesture="kb:alt+shift+y", speakOnDemand=True)
    def script_lyrics(self, gesture):
        if getattr(self, "_lyricsDialogOpen", False):
            return
        def fetch():
            import wx
            from globalPlugins.sonosSettings import lyricsUserAgent
            if getattr(self, "_lyricsRequestToken", None) is not None:
                ui.message(_("Fetching lyrics"))
                return
            panel = _find(self._root(), "nowPlayingPanel")
            fields = self._metadataFields(panel, 3)
            if len(fields) < 2 or not fields[0][1] or not fields[1][1]:
                ui.message(_("No track title or artist is available."))
                return
            metadata = {"track_name": fields[0][1], "artist_name": fields[1][1]}
            if len(fields) > 2 and fields[2][1]:
                metadata["album_name"] = fields[2][1]
            try:
                duration = self._scrubber()[1].CurrentMaximum
                if 1 <= duration <= 3600:
                    metadata["duration"] = round(duration)
            except (ControlUnavailable, COMError):
                pass
            cached = getattr(self, "_lyricsCache", None)
            if cached and cached[0] == metadata:
                wx.CallAfter(self._run, lambda: self._showLyrics(metadata, *cached[1]))
                return
            wait = getattr(self, "_lyricsRetryAt", 0) - perf_counter()
            if wait > 0:
                ui.message(_("Lyrics service is busy. Try again in {seconds} seconds.").format(seconds=math.ceil(wait)))
                return
            userAgent = lyricsUserAgent()
            token = self._lyricsRequestToken = object()
            ui.message(_("Fetching lyrics"))
            Thread(target=self._fetchLyricsWorker, args=(token, metadata, userAgent), daemon=True).start()
        self._run(fetch)

    def _fetchLyricsWorker(self, token, metadata, userAgent):
        import wx
        result, errorMessage, retry = None, None, 0
        try:
            result = _fetchLyrics(metadata, userAgent)
        except HTTPError as error:
            if error.code in (429, 503):
                header = error.headers.get("Retry-After", "60")
                try:
                    retry = float(header)
                except ValueError:
                    try:
                        retry = parsedate_to_datetime(header).timestamp() - time()
                    except (TypeError, ValueError, OverflowError):
                        retry = 60
                retry = max(1, retry) if math.isfinite(retry) else 60
                errorMessage = _("Lyrics service is busy. Try again in {seconds} seconds.").format(seconds=math.ceil(retry))
            else:
                errorMessage = _("Could not fetch lyrics. Try again later.")
            error.close()
        except Exception:
            log.debugWarning("Sonos lyrics lookup failed", exc_info=True)
            errorMessage = _("Could not fetch lyrics. Try again later.")
        wx.CallAfter(self._lyricsFetched, token, metadata, result, errorMessage, retry)

    def _lyricsFetched(self, token, metadata, result, errorMessage, retry):
        if getattr(self, "_lyricsRequestToken", None) is not token:
            return
        self._lyricsRequestToken = None
        self._lyricsRetryAt = perf_counter() + retry
        if errorMessage:
            ui.message(errorMessage)
            return
        self._lyricsCache = (metadata, result)
        foreground = api.getForegroundObject()
        if not foreground or foreground.processID != self.processID:
            ui.message(_("Lyrics lookup finished. Press the lyrics command in Sonos to view the results."))
            return
        self._run(lambda: self._showLyrics(metadata, *result))

    def _showLyrics(self, metadata, records, matched):
        import wx
        from gui.message import displayDialogAsModal
        if not records:
            ui.message(_("No lyrics found."))
            return
        self._lyricsDialogOpen = True
        dialog = None
        try:
            if matched:
                record = records[0]
            else:
                choices = [_("{title} - {artist} - {album} - {duration}").format(
                    title=record["trackName"], artist=record["artistName"],
                    album=record["albumName"], duration=_format_seconds(record["duration"]),
                ) for record in records]
                dialog = wx.SingleChoiceDialog(None,
                    _("Choose a recording for {title} by {artist}. Results from LRCLIB.").format(
                        title=metadata["track_name"], artist=metadata["artist_name"]),
                    _("Lyrics matches"), choices)
                if displayDialogAsModal(dialog) != wx.ID_OK:
                    return
                record = records[dialog.GetSelection()]
                dialog.Destroy()
                dialog = None
            lyrics = _lyricsText(record)
            if not lyrics:
                ui.message(_("This recording is marked as instrumental.") if record.get("instrumental")
                           else _("No lyrics found for this recording."))
                return
            title = _("Lyrics for {title} by {artist}").format(title=record["trackName"], artist=record["artistName"])
            content = (f"<h1>{escape(title)}</h1><p>{escape(record['albumName'])}</p>"
                       f"<pre>{escape(lyrics)}</pre>"
                       f'<p><a href="https://lrclib.net/">{escape(_("Lyrics provided by LRCLIB"))}</a></p>')
            ui.browseableMessage(content, title=title, isHtml=True)
        finally:
            if dialog is not None:
                dialog.Destroy()
            self._lyricsDialogOpen = False

    @script(description=_("Jump to a time in the current track."), gesture="kb:control+j", speakOnDemand=True)
    def script_jumpToTime(self, gesture):
        if getattr(self, "_jumpDialogOpen", False):
            return
        def prepare():
            import wx
            root = self._root()
            slider, pattern = self._scrubber()
            if pattern.CurrentIsReadOnly:
                raise NoTrackSlider("Scrubber is read-only")
            trackInfo = self._trackInfo(includeGroup=True)
            maximum, current = pattern.CurrentMaximum, pattern.CurrentValue
            self._jumpDialogOpen = True
            wx.CallAfter(self._run, lambda: self._showJumpDialog(
                root.windowHandle, trackInfo, maximum, current
            ))
        self._run(prepare)

    def _showJumpDialog(self, windowHandle, trackInfo, maximum, current):
        import wx
        from gui.message import displayDialogAsModal
        dialog = None
        try:
            dialog = wx.TextEntryDialog(
                None,
                _("Track length {length}. Jump to:").format(length=_format_seconds(maximum)),
                _("Jump to time"),
                _format_seconds(current),
            )
            target = None
            relative = False
            def validate(event):
                nonlocal target, relative
                try:
                    # GetValue uses the stored value; transfer the edit before validating OK.
                    if not dialog.TransferDataFromWindow():
                        raise ValueError("Could not read the entered time")
                    value = dialog.GetValue().strip()
                    relative = value.startswith(("+", "-"))
                    target = _parse_time(value[1:] if relative else value)
                    if value.startswith("-"):
                        target = -target
                    if not relative and target > maximum:
                        raise ValueError("Beyond the end of the track")
                except ValueError:
                    ui.message(_("Enter seconds, minutes:seconds, or hours:minutes:seconds, up to {length}. Use + or - for a relative jump.").format(length=_format_seconds(maximum)))
                    return
                event.Skip()
            dialog.Bind(wx.EVT_BUTTON, validate, id=wx.ID_OK)
            if displayDialogAsModal(dialog) == wx.ID_OK and target is not None:
                core.callLater(100, self._run, lambda: self._jumpTo(target, windowHandle, trackInfo, maximum, relative=relative))
        finally:
            if dialog is not None:
                dialog.Destroy()
            self._jumpDialogOpen = False

    def _jumpTo(self, target, windowHandle, trackInfo, maximum, relative=False):
        root = self._root()
        if root.windowHandle != windowHandle:
            raise ControlUnavailable("Sonos window changed")
        slider, pattern = self._scrubber()
        if self._trackInfo(includeGroup=True) != trackInfo or pattern.CurrentMaximum != maximum:
            ui.message(_("The track or room changed. Open Jump to Time again."))
            return
        if relative:
            target += pattern.CurrentValue
        self._setPosition(pattern, target, windowHandle)

    @script(description=_("Report the current speaker group."), gesture="kb:alt+shift+g", speakOnDemand=True)
    def script_reportGroup(self, gesture):
        def report():
            group = self._groupInfo()
            try:
                members = self._groupMembers()
            except (ControlUnavailable, COMError):
                members = ""
            ui.message(_("Group {group} ({members})").format(group=group, members=members) if members
                       else _("Group {group}").format(group=group))
        self._run(report)

    @script(description=_("Select the previous speaker group."), gesture="kb:control+,", speakOnDemand=True)
    def script_previousGroup(self, gesture):
        self._changeGroup("control+,")

    @script(description=_("Select the next speaker group."), gesture="kb:control+.", speakOnDemand=True)
    def script_nextGroup(self, gesture):
        self._changeGroup("control+.")

    def _groupMembers(self):
        groups = _find(self._root(), "zoneGroupScrollViewer").UIAElement
        client = UIAHandler.handler.clientObject
        selectedCondition = client.CreateAndCondition(
            client.CreatePropertyCondition(UIAHandler.UIA_AutomationIdPropertyId, "RadioButton_1"),
            client.CreatePropertyCondition(UIAHandler.UIA_SelectionItemIsSelectedPropertyId, True),
        )
        selected = client.CreateTreeWalker(selectedCondition).GetFirstChildElementBuildCache(
            groups, UIAHandler.handler.baseCacheRequest)
        if not selected:
            raise ControlUnavailable("No selected speaker group")
        condition = client.CreatePropertyCondition(UIAHandler.UIA_AutomationIdPropertyId, "name_1")
        cache = client.CreateCacheRequest()
        cache.AddProperty(UIAHandler.UIA_NamePropertyId)
        # Room labels support bulk lookup. Cache only names; NVDA objects/states made this slow.
        rooms = selected.FindAllBuildCache(UIAHandler.TreeScope_Descendants, condition, cache)
        names = ((rooms.GetElement(index).CachedName or "").strip() for index in range(rooms.Length))
        return ", ".join(dict.fromkeys(filter(None, names)))

    def _groupInfo(self, panel=None):
        if panel is None:
            panel = _find(self._root(), "nowPlayingPanel")
        group = _find(panel, "headerParens_1").name or ""
        try:
            group += _find(panel, "headerParens2_1").name or ""
        except ControlUnavailable:
            pass  # A single room need not have a second header part.
        group = group.strip("() \u00a0")
        if not group:
            raise ControlUnavailable("No speaker group")
        return group

    def _changeGroup(self, nativeKey):
        started = perf_counter()
        windowHandle = None
        oldGroup = None
        try:
            root = self._root()
            windowHandle = root.windowHandle
            oldGroup = self._groupInfo()
        except (ControlUnavailable, COMError):
            pass
        except Exception:
            log.exception("Could not read the Sonos speaker group before navigation")
        keyboardHandler.KeyboardInputGesture.fromName(nativeKey).send()
        self._groupSequence = getattr(self, "_groupSequence", 0) + 1
        core.callLater(75, self._reportGroupChange, windowHandle, oldGroup, self._groupSequence, 0, started)

    def _reportGroupChange(self, windowHandle, oldGroup, sequence, attempt, started):
        if sequence != getattr(self, "_groupSequence", 0):
            return
        try:
            if api.getForegroundObject().windowHandle != windowHandle:
                return
        except (AttributeError, COMError):
            return
        try:
            group = self._groupInfo()
        except (ControlUnavailable, COMError):
            group = oldGroup
        if group != oldGroup:
            ui.message(_("Group {group}, {milliseconds} milliseconds").format(
                group=group, milliseconds=round((perf_counter() - started) * 1000),
            ))
            return
        if attempt < 11 and perf_counter() - started < 1.2:
            core.callLater(75, self._reportGroupChange, windowHandle, oldGroup, sequence, attempt + 1, started)

    @script(description=_("Copy the displayed album artwork to the clipboard."), gesture="kb:alt+shift+a", speakOnDemand=True)
    def script_copyArtwork(self, gesture):
        self._run(self._copyArtwork)

    def _copyArtwork(self):
        import wx
        panel = _find(self._root(), "nowPlayingPanel")
        # The album-art button has incorrect bounds. Use the visible image sibling.
        art = panel.firstChild
        while art:
            if (
                isinstance(art, UIA)
                and art.role == controlTypes.Role.GRAPHIC
                and not art.UIAAutomationId
                and controlTypes.State.OFFSCREEN not in art.states
                and art.location and art.location.width > 0 and art.location.height > 0
            ):
                break
            art = art.next
        if not art:
            raise ControlUnavailable("No displayed album artwork")
        x, y, width, height = art.location
        if any(wx.Display.GetFromPoint(wx.Point(px, py)) == wx.NOT_FOUND
               for px, py in ((x, y), (x + width - 1, y + height - 1))):
            raise ControlUnavailable("Artwork is outside the visible screen")
        bitmap = wx.Bitmap(width, height)
        memory = wx.MemoryDC(bitmap)
        try:
            if not memory.Blit(0, 0, width, height, wx.ScreenDC(), x, y):
                raise ControlUnavailable("Could not capture displayed artwork")
        finally:
            memory.SelectObject(wx.NullBitmap)
        if not wx.TheClipboard.Open():
            ui.message(_("Could not open the clipboard."))
            return
        try:
            copied = wx.TheClipboard.SetData(wx.BitmapDataObject(bitmap))
            if copied:
                wx.TheClipboard.Flush()
        finally:
            wx.TheClipboard.Close()
        ui.message(_("Album artwork copied.") if copied else _("Could not copy album artwork."))

    @script(description=_("Report sleep timer status."), gesture="kb:alt+shift+s", speakOnDemand=True)
    def script_reportSleepTimer(self, gesture):
        def report():
            label = _text(_find(self._root(), "sleepTimerButton_1"))
            time = re.search(r"\b\d+(?::\d{2}){1,2}\b", label)
            ui.message(_("Sleep timer {time}").format(time=time.group()) if time
                       else _("Sleep timer off"))
        self._run(report)

    @script(description=_("Report the next track."), gesture="kb:alt+shift+n", speakOnDemand=True)
    def script_reportNext(self, gesture):
        def report():
            panel = _find(self._root(), "nowPlayingPanel")
            fields = self._metadataFields(panel, 4)
            if len(fields) == 4 and fields[3][0].casefold() == "siriusxm":
                channel = fields[3][1]
                ui.message(_("SiriusXM {channel}").format(channel=channel) if channel
                           else _("No channel information is available."))
                return
            nextTrack = fields[3][1] if len(fields) == 4 else ""
            ui.message(_("Next {track}").format(track=nextTrack) if nextTrack
                       else _("No next track information is available."))
        self._run(report)

    @script(description=_("Report the number of tracks in the queue."), gesture="kb:alt+shift+q", speakOnDemand=True)
    def script_reportQueue(self, gesture):
        def report():
            label = _text(_find(_find(self._root(), "queuePanel"), "trackCount_1"))
            match = re.fullmatch(r"(\d+(?:[.,\s]\d{3})*)\s*[^\d]*", label)
            if not match:
                raise ControlUnavailable("No queue count")
            count = int("".join(char for char in match[1] if char.isdecimal()))
            ui.message(ngettext("{count} track in queue", "{count} tracks in queue", count).format(count=count))
        self._run(report)

    def _metadataFields(self, panel, limit):
        client = UIAHandler.handler.clientObject
        condition = client.CreateOrCondition(
            client.CreatePropertyCondition(UIAHandler.UIA_AutomationIdPropertyId, "PART_Header"),
            client.CreatePropertyCondition(UIAHandler.UIA_AutomationIdPropertyId, "PART_MetadataProperty"),
        )
        walker = client.CreateTreeWalker(condition)
        cache = UIAHandler.handler.baseCacheRequest
        child = walker.GetFirstChildElementBuildCache(panel.UIAElement, cache)
        fields = []
        label = ""
        # Sonos reuses metadata IDs; a fourth row can be Next or a station.
        while child:
            value = (child.CachedName or "").strip()
            if child.CachedAutomationId == "PART_Header":
                label = value
            else:
                fields.append((label, value))
                if len(fields) == limit:
                    break
            child = walker.GetNextSiblingElementBuildCache(child, cache)
        return fields

    def _trackInfo(self, includeGroup=False, root=None, limit=3):
        panel = _find(root if root is not None else self._root(), "nowPlayingPanel")
        fields = self._metadataFields(panel, limit)
        details = [f"{label}: {value}" if label else value for label, value in fields if value]
        if not details:
            details = [_("No track information is available.")]
        if includeGroup:
            details.insert(0, self._groupInfo(panel))
        info = "\n".join(details)
        track = " - ".join(value for label, value in fields[:2] if value) if fields and fields[0][1] else ""
        return info, track

    @script(description=_("Toggle track title announcements."), gesture="kb:alt+shift+k", speakOnDemand=True)
    def script_toggleTrackAnnouncements(self, gesture):
        from globalPlugins.sonosSettings import toggleAnnouncements

        toggleAnnouncements()

    @script(description=_("Toggle track logging."), gesture="kb:alt+shift+l", speakOnDemand=True)
    def script_toggleTrackLogging(self, gesture):
        from globalPlugins.sonosSettings import toggleLogging
        toggleLogging()
