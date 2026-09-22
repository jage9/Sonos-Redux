"""Checks for background logging without a running NVDA instance."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from test_sonos import ROOT, sonos, nvda, _module, Pattern


class Action:
    def __init__(self):
        self.handlers = []
    def register(self, handler):
        self.handlers.append(handler)
    def unregister(self, handler):
        if handler in self.handlers:
            self.handlers.remove(handler)
    def notify(self):
        for handler in self.handlers[:]:
            handler()


class Section(dict):
    pass


class BaseProfile(dict):
    def __setitem__(self, key, value):
        super().__setitem__(key, Section(value))
    def validate(self, validator, section):
        section.setdefault("logTracks", False)
        section.setdefault("announceTracks", False)
        section.setdefault("logFile", "sonos.log")
        section.setdefault("seekSeconds", 5)
        section.setdefault("endJumpSeconds", 30)
        return True


class Conf(dict):
    spec = {}
    BASE_ONLY_SECTIONS = set()
    validator = object()
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.profiles = [BaseProfile()]
    def __getitem__(self, key):
        if key in self.BASE_ONLY_SECTIONS:
            return self.profiles[0][key]
        return super().__getitem__(key)


class Timer:
    def __init__(self, callback):
        self.callback = callback
        self.running = False
    def Start(self, delay):
        self.running = True
        self.delay = delay
    def Stop(self):
        self.running = False


class PluginBase:
    def terminate(self):
        pass


_module("config", conf=Conf(sonos={"logTracks": False, "announceTracks": False, "logFile": "sonos.log", "seekSeconds": 5, "endJumpSeconds": 30}),
        post_configProfileSwitch=Action(), post_configReset=Action())
_module("extensionPoints", Action=Action)
_module("globalPluginHandler", GlobalPlugin=PluginBase)
_module("gui", guiHelper=types.SimpleNamespace(), nvdaControls=types.SimpleNamespace())
_module("gui.settingsDialogs", SettingsPanel=object,
        NVDASettingsDialog=types.SimpleNamespace(categoryClasses=[]))
_module("NVDAState", WritePaths=types.SimpleNamespace(configDir="."), shouldWriteToDisk=lambda: True)
_module("winAPI.sessionTracking", isLockScreenModeActive=lambda: False)
_module("winUser")
_module("wx", PyTimer=Timer)
_module("appModules")
sys.modules["appModules.sonos"] = sonos
spec = importlib.util.spec_from_file_location("sonos_settings_test", ROOT / "addon/globalPlugins/sonosSettings.py")
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        documents = patch.object(settings.wx, "StandardPaths", types.SimpleNamespace(
            Get=lambda: types.SimpleNamespace(GetDocumentsDir=lambda: self.folder.name)), create=True)
        documents.start()
        self.addCleanup(documents.stop)
        settings.config.conf.profiles[0]["sonos"] = {"logTracks": False, "announceTracks": False, "logFile": "sonos.log", "seekSeconds": 5, "endJumpSeconds": 30}
        self.plugin = settings.GlobalPlugin()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(self.plugin.terminate)

    def test_seek_shortcuts_use_saved_step_in_both_directions(self):
        app = sonos.AppModule()
        app._scrubGesture = lambda gesture, action: action()
        steps = []
        app._seek = steps.append
        for seconds in (5, 1, 999, 42):
            panel = settings.SonosSettingsPanel()
            panel.seekSeconds = types.SimpleNamespace(GetValue=lambda: seconds)
            panel.endJumpSeconds = types.SimpleNamespace(GetValue=lambda: 42)
            panel.enabled = types.SimpleNamespace(IsChecked=lambda: False)
            panel.announce = types.SimpleNamespace(IsChecked=lambda: False)
            panel.filename = types.SimpleNamespace(GetValue=lambda: "sonos.log")
            panel.onSave()
            app.script_adjustScrubBackward(None)
            app.script_adjustScrubForward(None)
        self.assertEqual(steps, [-5, 5, -1, 1, -999, 999, -42, 42])
        self.assertEqual(settings.config.conf.spec["sonos"]["seekSeconds"],
                         "integer(default=5, min=1, max=999)")
        self.assertEqual(settings.config.conf["sonos"]["endJumpSeconds"], 42)
        self.assertEqual(settings.config.conf.spec["sonos"]["endJumpSeconds"],
                         "integer(default=30, min=1, max=999)")

    def test_jump_near_end_uses_setting_and_clamps_short_tracks(self):
        app = sonos.AppModule()
        app._root = lambda: types.SimpleNamespace(windowHandle=99)
        app._scrubGesture = lambda gesture, action: action()
        pattern = Pattern(0, 100, 20)
        app._scrubber = lambda: (None, pattern)
        settings.config.conf["sonos"]["endJumpSeconds"] = 30
        with patch.object(nvda["api"], "getFocusObject", return_value=None):
            app.script_jumpNearEnd(None)
            self.assertEqual(pattern.set_values, [70])
            pattern = Pattern(0, 20, 10)
            app.script_jumpNearEnd(None)
            self.assertEqual(pattern.set_values, [0])
        self.assertEqual(app.script_jumpNearEnd.scriptMetadata["gesture"], "kb:alt+shift+j")

    def test_default_log_uses_documents_and_preserves_custom_absolute_path(self):
        self.assertEqual(settings.logPath("sonos.log"), Path(self.folder.name) / "sonos.log")
        custom = Path(self.folder.name) / "custom" / "chosen.log"
        self.assertEqual(settings.logPath(str(custom)), custom)

    def test_open_log_handles_missing_file_and_uses_default_application(self):
        panel = settings.SonosSettingsPanel()
        panel.filename = types.SimpleNamespace(GetValue=lambda: "sonos.log")
        path = Path(self.folder.name) / "sonos.log"
        with patch.object(settings.os, "startfile", create=True) as launch:
            panel._openLog(None)
            launch.assert_not_called()
            self.assertFalse(path.exists())
            self.assertEqual(nvda["ui"].messages[-1], "No track log file yet.")
            path.write_text("Existing log", encoding="utf-8")
            panel._openLog(None)
            launch.assert_called_once_with(str(path))
            launch.side_effect = OSError("No associated application")
            panel._openLog(None)
            self.assertEqual(nvda["ui"].messages[-1], "Could not open the track log.")

    def test_default_off_toggle_deduplicates_and_appends_changes(self):
        self.assertFalse(self.plugin._timer.running)
        self.assertEqual(settings.config.conf.spec["sonos"]["logTracks"], "boolean(default=False)")
        path = Path(self.folder.name) / "sonos.log"
        path.write_text("Existing entry\n", encoding="utf-8")
        settings.toggleLogging()
        self.assertTrue(self.plugin._timer.running)
        self.assertEqual(self.plugin._timer.delay, 3000)
        with patch.object(self.plugin, "_readTrack", side_effect=["Title - Artist", "Title - Artist", "", "Second\nTitle - Artist"]):
            for _ in range(4):
                self.plugin._poll()
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], "Existing entry")
        self.assertTrue(lines[1].endswith("\t### Log started ###"))
        self.assertTrue(lines[2].endswith("\tTitle - Artist"))
        self.assertTrue(lines[3].endswith("\tSecond Title - Artist"))
        settings.toggleLogging()
        self.assertFalse(self.plugin._timer.running)
        self.assertTrue(path.read_text(encoding="utf-8").splitlines()[-1].endswith("\t### Log ended ###"))
        with patch.object(self.plugin, "_readTrack") as read:
            self.plugin._poll()
            read.assert_not_called()

    def test_track_announcements_use_background_poll_without_logging(self):
        path = Path(self.folder.name) / "sonos.log"
        self.assertFalse(settings.config.conf["sonos"]["announceTracks"])
        settings.toggleAnnouncements()
        self.assertTrue(self.plugin._timer.running)
        self.assertEqual(nvda["ui"].messages[-1], "Track title announcements on")
        nvda["ui"].messages.clear()
        with patch.object(self.plugin, "_readTrack",
                          side_effect=["First - Artist", "First - Artist", "", "Second - Artist", "Third - Artist"]):
            for _ in range(5):
                self.plugin._poll()
        self.assertEqual(nvda["ui"].messages, ["Second - Artist", "Third - Artist"])
        self.assertFalse(path.exists())
        settings.toggleAnnouncements()
        self.assertFalse(self.plugin._timer.running)
        self.assertEqual(nvda["ui"].messages[-1], "Track title announcements off")

    def test_toggling_announcements_does_not_restart_log_session(self):
        path = Path(self.folder.name) / "sonos.log"
        settings.toggleLogging()
        settings.toggleAnnouncements()
        with patch.object(self.plugin, "_readTrack", side_effect=["First - Artist", "Second - Artist"]):
            self.plugin._poll()
            self.plugin._poll()
        settings.toggleAnnouncements()
        settings.toggleLogging()
        entries = [line.split("\t", 1)[1] for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(entries, ["### Log started ###", "First - Artist",
                                   "Second - Artist", "### Log ended ###"])
        self.assertEqual(nvda["ui"].messages.count("Second - Artist"), 1)

    def test_background_lookup_never_uses_foreground_and_passes_root(self):
        root = object()
        app = types.SimpleNamespace(appName="sonos", _trackInfo=lambda **kw: ("", "Song") if kw["root"] is root else None)
        element = object()
        client = types.SimpleNamespace(ElementFromHandleBuildCache=lambda hwnd, cache: element)
        def getApp(pid):
            self.assertEqual(pid, 9)
            return app
        def makeUIA(**kwargs):
            self.assertIs(kwargs["UIAElement"], element)
            return root
        with patch.object(settings.winUser, "findTopLevelWindow", lambda predicate: 42, create=True), \
             patch.object(settings.winUser, "getWindowThreadProcessID", lambda hwnd: (9, 8), create=True), \
             patch.object(settings.appModuleHandler, "getAppModuleFromProcessID", getApp, create=True), \
             patch.object(settings.UIAHandler.handler, "clientObject", client), \
             patch.object(settings, "UIA", makeUIA), \
             patch.object(nvda["api"], "getForegroundObject", side_effect=AssertionError("Must not use foreground")):
            self.assertEqual(self.plugin._readTrack(), "Song")
        app = sonos.AppModule()
        app._metadataFields = lambda panel, limit: [("Song", "Title"), ("Artist", "Artist")]
        with patch.object(sonos, "_find", return_value=root) as find, \
             patch.object(app, "_root", side_effect=AssertionError("Must not use foreground")):
            self.assertEqual(app._trackInfo(root=root)[1], "Title - Artist")
            find.assert_called_once_with(root, "nowPlayingPanel")

    def test_unavailable_metadata_retries_and_write_failure_disables_once(self):
        settings.toggleLogging()
        with patch.object(self.plugin, "_readTrack", side_effect=sonos.ControlUnavailable):
            self.plugin._poll()
        self.assertTrue(self.plugin._timer.running)
        settings.config.conf["sonos"]["logFile"] = str(Path(self.folder.name) / "missing" / "sonos.log")
        with patch.object(self.plugin, "_readTrack", return_value="Song"):
            self.plugin._poll()
        self.assertFalse(settings.config.conf["sonos"]["logTracks"])
        self.assertFalse(self.plugin._timer.running)
        self.assertEqual(nvda["ui"].messages[-1], "Could not write the track log. Track logging off.")

    def test_settings_are_global_and_reset_and_shutdown_manage_timer(self):
        settings.toggleLogging()
        self.plugin._lastTrack = "Song"
        self.assertIn("sonos", settings.config.conf.BASE_ONLY_SECTIONS)
        # A profile override must not change the enabled state or filename.
        settings.config.conf["sonos"] = {"logTracks": False, "logFile": "profile.log"}
        settings.config.post_configProfileSwitch.notify()
        self.assertTrue(settings.config.conf["sonos"]["logTracks"])
        self.assertEqual(settings.config.conf["sonos"]["logFile"], "sonos.log")
        self.assertTrue(self.plugin._timer.running)
        self.assertEqual(self.plugin._lastTrack, "Song")
        settings.config.conf["sonos"]["logFile"] = "other.log"
        settings.settingsChanged.notify()
        self.assertIsNone(self.plugin._lastTrack)
        settings.config.conf["sonos"]["logTracks"] = False
        settings.config.post_configReset.notify()
        self.assertFalse(self.plugin._timer.running)
        self.plugin.terminate()
        self.assertNotIn(settings.SonosSettingsPanel, settings.NVDASettingsDialog.categoryClasses)
        self.assertNotIn(self.plugin._applySettings, settings.settingsChanged.handlers)

    def test_session_markers_follow_file_changes_and_shutdown(self):
        settings.toggleLogging()
        self.plugin._applySettings()  # Reapplying unchanged settings must not add markers.
        settings.config.conf["sonos"]["logFile"] = "second.log"
        settings.settingsChanged.notify()
        first = (Path(self.folder.name) / "sonos.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual([line.split("\t")[1] for line in first], ["### Log started ###", "### Log ended ###"])
        self.plugin.terminate()
        self.plugin.terminate()  # Cleanup must not append a second end marker.
        second = (Path(self.folder.name) / "second.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual([line.split("\t")[1] for line in second], ["### Log started ###", "### Log ended ###"])

    def test_failed_start_does_not_announce_logging_on(self):
        settings.config.conf["sonos"]["logFile"] = str(Path(self.folder.name) / "missing" / "sonos.log")
        nvda["ui"].messages.clear()
        settings.toggleLogging()
        self.assertFalse(self.plugin._timer.running)
        self.assertEqual(nvda["ui"].messages, ["Could not write the track log. Track logging off."])

    def test_locked_and_secure_sessions_do_not_read_or_write(self):
        settings.toggleLogging()
        with patch.object(self.plugin, "_readTrack") as read:
            with patch.object(settings, "isLockScreenModeActive", return_value=True):
                self.plugin._poll()
            with patch.object(settings, "shouldWriteToDisk", return_value=False):
                self.plugin._poll()
            read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
