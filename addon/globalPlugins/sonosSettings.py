# Sonos settings and background track logging for NVDA.
# Copyright (C) 2026 J.J. Meddaugh <jj@bestmidi.com>.
# SPDX-License-Identifier: GPL-2.0-only

from datetime import datetime
from pathlib import Path
import os

import addonHandler
import appModuleHandler
from comtypes import COMError
import config
import extensionPoints
import globalPluginHandler
from gui import guiHelper
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
from logHandler import log
from NVDAObjects.UIA import UIA
from NVDAState import shouldWriteToDisk
import ui
import UIAHandler
from winAPI.sessionTracking import isLockScreenModeActive
import winUser
import wx

addonHandler.initTranslation()

config.conf.spec["sonos"] = {
    "logTracks": "boolean(default=False)",
    "logFile": "string(default='sonos.log')",
}
# Use NVDA's base-only section support so app profiles cannot change logging.
config.conf.BASE_ONLY_SECTIONS.add("sonos")
_baseProfile = config.conf.profiles[0]
if "sonos" not in _baseProfile:
    _baseProfile["sonos"] = {}
_baseSection = _baseProfile["sonos"]
_baseSection.configspec = config.conf.spec["sonos"]
_baseProfile.validate(config.conf.validator, section=_baseSection)
settingsChanged = extensionPoints.Action()


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


class SonosSettingsPanel(SettingsPanel):
    title = _("Sonos")

    def makeSettings(self, settingsSizer):
        helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        self.enabled = helper.addItem(wx.CheckBox(self, label=_("&Log track titles")))
        self.enabled.SetValue(config.conf["sonos"]["logTracks"])
        self.filename = helper.addLabeledControl(_("Log &filename:"), wx.TextCtrl,
                                                value=config.conf["sonos"]["logFile"])
        self.browse = helper.addItem(wx.Button(self, label=_("&Browse...")))
        self.openLog = helper.addItem(wx.Button(self, label=_("&Open")))
        self.enabled.Bind(wx.EVT_CHECKBOX, self._enableFilename)
        self.browse.Bind(wx.EVT_BUTTON, self._browse)
        self.openLog.Bind(wx.EVT_BUTTON, self._openLog)
        self._enableFilename()

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
        config.conf["sonos"]["logTracks"] = self.enabled.IsChecked()
        config.conf["sonos"]["logFile"] = self.filename.GetValue().strip() or "sonos.log"
        settingsChanged.notify()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
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
        if state == self._state:
            return
        if not self._endSession():
            return
        self._state = state
        self._lastTrack = None
        if state[0] and shouldWriteToDisk():
            if self._writeLog(state[1], "### " + _("Log started") + " ###"):
                # ponytail: Polling can miss changes shorter than three seconds; use events if needed.
                self._timer.Start(3000)

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
        if not config.conf["sonos"]["logTracks"] or not shouldWriteToDisk() or isLockScreenModeActive():
            return
        from appModules.sonos import ControlUnavailable
        try:
            track = self._readTrack()
        except (ControlUnavailable, COMError, RuntimeError, OSError):
            return  # Sonos may be closed, restarting, or temporarily unable to expose metadata.
        if not track or track == self._lastTrack:
            return
        if self._writeLog(config.conf["sonos"]["logFile"], track):
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
            ui.message(_("Could not write the track log. Track logging off."))
            return False
        return True

    def terminate(self):
        self._endSession()
        settingsChanged.unregister(self._applySettings)
        config.post_configReset.unregister(self._applySettings)
        if SonosSettingsPanel in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.remove(SonosSettingsPanel)
        super().terminate()
