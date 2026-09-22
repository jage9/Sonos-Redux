# Sonos settings and background track logging for NVDA.
# Copyright (C) 2026 J.J. Meddaugh <jj@bestmidi.com>.
# SPDX-License-Identifier: GPL-2.0-only

from datetime import datetime
from pathlib import Path
import os
from uuid import UUID, uuid4

import addonHandler
import api
import appModuleHandler
from comtypes import COMError
import config
import extensionPoints
import globalPluginHandler
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
from logHandler import log
from NVDAObjects.UIA import UIA
from NVDAState import shouldWriteToDisk
from scriptHandler import script
import ui
import UIAHandler
from winAPI.sessionTracking import isLockScreenModeActive
import winUser
import wx

addonHandler.initTranslation()

config.conf.spec["sonos"] = {
    "lyricsInstallationId": "string(default='')",
    "logTracks": "boolean(default=False)",
    "announcementMode": "integer(default=0, min=0, max=2)",
    "logFile": "string(default='sonos.log')",
    "seekSeconds": "integer(default=5, min=1, max=999)",
    "endJumpSeconds": "integer(default=30, min=1, max=999)",
    "fadeSeconds": "integer(default=5, min=1, max=999)",
}
# Sonos settings apply globally, independent of configuration profiles.
config.conf.BASE_ONLY_SECTIONS.add("sonos")
_baseProfile = config.conf.profiles[0]
if "sonos" not in _baseProfile:
    _baseProfile["sonos"] = {}
_baseSection = _baseProfile["sonos"]
_baseSection.configspec = config.conf.spec["sonos"]
_baseProfile.validate(config.conf.validator, section=_baseSection)
settingsChanged = extensionPoints.Action()
lyricsSaveHandlers = {}


def registerLyricsSave(window, callback):
    handle = window.GetHandle()
    lyricsSaveHandlers[handle] = callback
    def destroyed(event):
        if event.GetEventObject() is window:
            lyricsSaveHandlers.pop(handle, None)
        event.Skip()
    window.Bind(wx.EVT_WINDOW_DESTROY, destroyed)


def lyricsUserAgent():
    settings = config.conf["sonos"]
    try:
        identifier = str(UUID(settings["lyricsInstallationId"]))
    except ValueError:
        identifier = str(uuid4())
        settings["lyricsInstallationId"] = identifier
    return f"Sonos-Redux/2026.1 (https://github.com/jage9/Sonos-Redux; installation={identifier})"


def logPath(filename):
    path = Path(filename).expanduser()
    return path if path.is_absolute() else Path(wx.StandardPaths.Get().GetDocumentsDir()) / path


def toggleLogging():
    if not shouldWriteToDisk():
        return
    enabled = not config.conf["sonos"]["logTracks"]
    config.conf["sonos"]["logTracks"] = enabled
    settingsChanged.notify()
    if config.conf["sonos"]["logTracks"] == enabled:
        ui.message(_("Track logging on") if enabled else _("Track logging off"))


def toggleAnnouncements():
    if not shouldWriteToDisk():
        return
    mode = (config.conf["sonos"]["announcementMode"] + 1) % 3
    config.conf["sonos"]["announcementMode"] = mode
    settingsChanged.notify()
    ui.message((
        _("Track announce off"),
        _("Track announce everywhere"),
        _("Track announce only while Sonos is focused"),
    )[mode])


class SonosSettingsPanel(SettingsPanel):
    title = _("Sonos")

    def makeSettings(self, settingsSizer):
        helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        self.seekSeconds = helper.addLabeledControl(
            _("Track &seek seconds:"), nvdaControls.SelectOnFocusSpinCtrl,
            min=1, max=999, initial=config.conf["sonos"]["seekSeconds"],
        )
        self.endJumpSeconds = helper.addLabeledControl(
            _("Seek seconds from &end of track:"), nvdaControls.SelectOnFocusSpinCtrl,
            min=1, max=999, initial=config.conf["sonos"]["endJumpSeconds"],
        )
        self.fadeSeconds = helper.addLabeledControl(
            _("&Fade seconds:"), nvdaControls.SelectOnFocusSpinCtrl,
            min=1, max=999, initial=config.conf["sonos"]["fadeSeconds"],
        )
        self.announce = helper.addLabeledControl(
            _("Track &announce:"), wx.Choice,
            choices=[_("Off"), _("Everywhere"), _("Only while Sonos is focused")],
        )
        self.announce.SetSelection(config.conf["sonos"]["announcementMode"])
        self.enabled = helper.addItem(wx.CheckBox(self, label=_("&Log track titles")))
        self.enabled.SetValue(config.conf["sonos"]["logTracks"])
        self.filename = helper.addLabeledControl(_("Log &filename:"), wx.TextCtrl,
                                                value=config.conf["sonos"]["logFile"])
        self.browse = helper.addItem(wx.Button(self, label=_("&Browse...")))
        self.openLog = helper.addItem(wx.Button(self, label=_("&Open")))
        self.enabled.Bind(wx.EVT_CHECKBOX, self._enableFilename)
        self.browse.Bind(wx.EVT_BUTTON, self._browse)
        self.openLog.Bind(wx.EVT_BUTTON, self._openLog)
        self._lyricsKey = None
        self.advanced = helper.addItem(wx.Button(self, label=_("Ad&vanced...")))
        self.advanced.Bind(wx.EVT_BUTTON, self._advanced)
        self._enableFilename()

    def _advanced(self, event):
        from gui.message import displayDialogAsModal
        current = self._lyricsKey if self._lyricsKey is not None else config.conf["sonos"]["lyricsInstallationId"]
        dialog = wx.TextEntryDialog(self,
            _("Lyrics key (random installation ID). Leave blank to generate a new key:"),
            _("Advanced Sonos settings"), current or str(uuid4()))
        key = None
        try:
            def validate(event):
                nonlocal key
                if not dialog.TransferDataFromWindow():
                    return
                value = dialog.GetValue().strip()
                try:
                    key = str(UUID(value)) if value else str(uuid4())
                except ValueError:
                    ui.message(_("Enter a valid lyrics key, or leave it blank to generate one."))
                    return
                event.Skip()
            dialog.Bind(wx.EVT_BUTTON, validate, id=wx.ID_OK)
            if displayDialogAsModal(dialog) == wx.ID_OK and key is not None:
                self._lyricsKey = key
        finally:
            dialog.Destroy()

    def _enableFilename(self, event=None):
        self.filename.Enable(self.enabled.IsChecked())
        self.browse.Enable(self.enabled.IsChecked())

    def _browse(self, event):
        path = logPath(self.filename.GetValue().strip() or "sonos.log")
        with wx.FileDialog(self, _("Choose track log file"), defaultDir=str(path.parent),
                           defaultFile=path.name, style=wx.FD_SAVE) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.filename.SetValue(dialog.GetPath())

    def _openLog(self, event):
        try:
            path = logPath(self.filename.GetValue().strip() or "sonos.log")
            if not path.is_file():
                ui.message(_("No track log file yet."))
                return
            os.startfile(str(path))
        except (OSError, ValueError):
            ui.message(_("Could not open the track log."))

    def isValid(self):
        if self.enabled.IsChecked():
            filename = self.filename.GetValue().strip()
            try:
                path = logPath(filename)
                valid = bool(filename) and path.parent.is_dir() and not path.is_dir()
            except (OSError, ValueError):
                valid = False
            if not valid:
                self._validationErrorMessageBox(_("Choose a log filename in an existing folder."),
                                                _("Log filename"))
                return False
        return True

    def onSave(self):
        if self._lyricsKey is not None:
            config.conf["sonos"]["lyricsInstallationId"] = self._lyricsKey
        config.conf["sonos"]["seekSeconds"] = self.seekSeconds.GetValue()
        config.conf["sonos"]["endJumpSeconds"] = self.endJumpSeconds.GetValue()
        config.conf["sonos"]["fadeSeconds"] = self.fadeSeconds.GetValue()
        config.conf["sonos"]["logTracks"] = self.enabled.IsChecked()
        config.conf["sonos"]["announcementMode"] = self.announce.GetSelection()
        config.conf["sonos"]["logFile"] = self.filename.GetValue().strip() or "sonos.log"
        settingsChanged.notify()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def getScript(self, gesture):
        # Handle the key before the embedded browser consumes it, only in our viewer.
        if "kb:control+s" in gesture.normalizedIdentifiers and winUser.getForegroundWindow() in lyricsSaveHandlers:
            return self.script_saveLyrics
        return super().getScript(gesture)

    @script(description=_("Save lyrics in the current Sonos lyrics window."), category=_("Sonos"))
    def script_saveLyrics(self, gesture):
        save = lyricsSaveHandlers.get(winUser.getForegroundWindow())
        if save is not None:
            wx.CallAfter(save)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timer = wx.PyTimer(self._poll)
        self._state = None
        self._lastTrack = None
        if not shouldWriteToDisk():
            return
        NVDASettingsDialog.categoryClasses.append(SonosSettingsPanel)
        settingsChanged.register(self._applySettings)
        config.post_configReset.register(self._applySettings)
        self._applySettings()

    def _applySettings(self):
        state = (config.conf["sonos"]["logTracks"], config.conf["sonos"]["logFile"])
        if state != self._state:
            if not self._endSession():
                return
            self._state = state
            self._lastTrack = None
            if state[0] and shouldWriteToDisk():
                if not self._writeLog(state[1], "### " + _("Log started") + " ###"):
                    return
        if state[0] or config.conf["sonos"]["announcementMode"]:
            # ponytail: Polling can miss changes shorter than three seconds; use events if needed.
            self._timer.Start(3000)
        else:
            self._timer.Stop()
            self._lastTrack = None

    def _endSession(self):
        state = self._state
        self._state = None
        self._timer.Stop()
        if state and state[0] and shouldWriteToDisk():
            return self._writeLog(state[1], "### " + _("Log ended") + " ###")
        return True

    def _readTrack(self):
        # Sonos keeps its main WPF window available when another app has focus.
        handle = winUser.findTopLevelWindow(lambda hwnd:
            winUser.getWindowText(hwnd) == "Sonos"
            and winUser.getClassName(hwnd).startswith("HwndWrapper["))
        if not handle:
            return ""
        app = appModuleHandler.getAppModuleFromProcessID(winUser.getWindowThreadProcessID(handle)[0])
        if app.appName != "sonos":
            return ""
        element = UIAHandler.handler.clientObject.ElementFromHandleBuildCache(
            handle, UIAHandler.handler.baseCacheRequest)
        root = UIA(UIAElement=element) if element else None
        if not root:
            return ""
        return app._trackInfo(root=root)[1]

    def _poll(self):
        if not (config.conf["sonos"]["logTracks"] or config.conf["sonos"]["announcementMode"]):
            return
        if not shouldWriteToDisk() or isLockScreenModeActive():
            return
        from appModules.sonos import ControlUnavailable
        try:
            track = self._readTrack()
        except (ControlUnavailable, COMError, RuntimeError, OSError):
            return  # Sonos may be closed, restarting, or temporarily unable to expose metadata.
        if not track:
            self._lastTrack = ""
            return
        if track == self._lastTrack:
            return
        if config.conf["sonos"]["logTracks"] and not self._writeLog(config.conf["sonos"]["logFile"], track):
            return
        mode = config.conf["sonos"]["announcementMode"]
        if mode and self._lastTrack is not None:
            if mode == 1:
                ui.message(track)
            else:
                foreground = api.getForegroundObject()
                app = (appModuleHandler.getAppModuleFromProcessID(foreground.processID)
                       if foreground else None)
                if getattr(app, "appName", None) == "sonos":
                    ui.message(track)
        self._lastTrack = track

    def _writeLog(self, filename, text):
        try:
            with logPath(filename).open("a", encoding="utf-8") as stream:
                stream.write(datetime.now().isoformat(timespec="seconds") + "\t"
                             + " ".join(text.splitlines()) + "\n")
        except (OSError, ValueError, UnicodeError):
            log.exception("Could not append to the Sonos track log")
            config.conf["sonos"]["logTracks"] = False
            self._timer.Stop()
            self._state = (False, config.conf["sonos"]["logFile"])
            self._lastTrack = None
            if config.conf["sonos"]["announcementMode"]:
                self._timer.Start(3000)
            ui.message(_("Could not write the track log. Track logging off."))
            return False
        return True

    def terminate(self):
        lyricsSaveHandlers.clear()
        self._endSession()
        settingsChanged.unregister(self._applySettings)
        config.post_configReset.unregister(self._applySettings)
        if SonosSettingsPanel in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.remove(SonosSettingsPanel)
        super().terminate()
