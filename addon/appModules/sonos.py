# Sonos desktop support for NVDA.
# Copyright (C) 2019 Ralf Kefferpuetz and contributors.
# Copyright (C) 2026 J.J. Meddaugh <jj@bestmidi.com>.
# SPDX-License-Identifier: GPL-2.0-only

from urllib.parse import urlencode
import webbrowser
import math
import re
from time import perf_counter

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

    def _scrubber(self):
        try:
            slider = self._transport("PART_Scrubber")
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

    def _transport(self, identifier):
        control = _find(_find(self._root(), "transportBar"), identifier)
        if controlTypes.State.UNAVAILABLE in control.states:
            raise ControlUnavailable(identifier)
        return control

    def _seek(self, seconds):
        slider, pattern = self._scrubber()
        self._setPosition(pattern, pattern.CurrentValue + seconds, self._root().windowHandle)

    def _setPosition(self, pattern, target, windowHandle):
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
            def validate(event):
                nonlocal target
                try:
                    # GetValue uses the stored value; transfer the edit before validating OK.
                    if not dialog.TransferDataFromWindow():
                        raise ValueError("Could not read the entered time")
                    target = _parse_time(dialog.GetValue())
                    if target > maximum:
                        raise ValueError("Beyond the end of the track")
                except ValueError:
                    ui.message(_("Enter seconds, minutes:seconds, or hours:minutes:seconds, up to {length}.").format(length=_format_seconds(maximum)))
                    return
                event.Skip()
            dialog.Bind(wx.EVT_BUTTON, validate, id=wx.ID_OK)
            if displayDialogAsModal(dialog) == wx.ID_OK and target is not None:
                core.callLater(100, self._run, lambda: self._jumpTo(target, windowHandle, trackInfo, maximum))
        finally:
            if dialog is not None:
                dialog.Destroy()
            self._jumpDialogOpen = False

    def _jumpTo(self, target, windowHandle, trackInfo, maximum):
        root = self._root()
        if root.windowHandle != windowHandle:
            raise ControlUnavailable("Sonos window changed")
        slider, pattern = self._scrubber()
        if self._trackInfo(includeGroup=True) != trackInfo or pattern.CurrentMaximum != maximum:
            ui.message(_("The track or room changed. Open Jump to Time again."))
            return
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
