"""Small stdlib-only regression checks for the Sonos app module."""

from __future__ import annotations

import builtins
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]


def _module(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    return module


def _install_nvda_stubs():
    builtins._ = lambda text: text
    addon = _module("addonHandler", initTranslation=lambda: None)
    api = _module("api", getForegroundObject=lambda: None, getFocusObject=lambda: None, copy_calls=[])
    def copy_to_clip(text, notify=False):
        api.copy_calls.append((text, notify))
        return True
    api.copyToClip = copy_to_clip

    class AppModule:
        processID = 1
    _module("appModuleHandler", AppModule=AppModule)
    _module("comtypes", COMError=type("COMError", (Exception,), {}))
    roles = types.SimpleNamespace(DATAITEM="dataitem", EDITABLETEXT="edit", DIALOG="dialog", SLIDER="slider", GRAPHIC="graphic", TOGGLEBUTTON="toggle", BUTTON="button", MENUITEM="menuitem", CHECKBOX="checkbox")
    states = types.SimpleNamespace(UNAVAILABLE="unavailable", PRESSED="pressed", EDITABLE="editable", OFFSCREEN="offscreen")
    _module("controlTypes", Role=roles, State=states)

    _module("inputCore", manager=types.SimpleNamespace(isInputHelpActive=False))
    core = _module("core", calls=[])
    core.callLater = lambda delay, callback, *args, **kwargs: core.calls.append(
        (delay, callback, args, kwargs)
    )

    class KeyboardInputGesture:
        created = []
        def __init__(self, name):
            self.name, self.sent = name, False
        @classmethod
        def fromName(cls, name):
            gesture = cls(name)
            cls.created.append(gesture)
            return gesture
        def send(self):
            self.sent = True
    _module("keyboardHandler", KeyboardInputGesture=KeyboardInputGesture)

    no_op = lambda *args, **kwargs: None
    _module("logHandler", log=types.SimpleNamespace(debugWarning=no_op, exception=no_op))

    class UIA:
        def __init__(self, *args, UIAElement=None, **kwargs):
            self.UIAElement = UIAElement
            self.name = kwargs.get("name", "")
            self.role = kwargs.get("role")
            self.UIAAutomationId = kwargs.get("UIAAutomationId", "")
            self.states = kwargs.get("states", set())
            self.children = kwargs.get("children", [])
        def _get_name(self):
            return self.name
        def _get_value(self):
            return "fallback"
        def _get_description(self):
            return getattr(self, "rawDescription", "")
        def _get_keyboardShortcut(self):
            return getattr(self, "rawShortcut", "")
        def setFocus(self):
            self.focused = True
    _module("NVDAObjects")
    _module("NVDAObjects.UIA", UIA=UIA)

    def decorate(**metadata):
        def apply(function):
            function.__doc__ = metadata.get("description", "")
            function.scriptMetadata = metadata
            return function
        return apply
    _module(
        "scriptHandler",
        script=decorate,
        getLastScriptRepeatCount=lambda: 0,
    )

    class Handler:
        clientObject = None
        baseCacheRequest = object()
    _module(
        "UIAHandler",
        handler=Handler(),
        TreeScope_Descendants=4,
        UIA_AutomationIdPropertyId=30005,
    )

    ui = _module("ui", messages=[])
    ui.message = lambda message: ui.messages.append(message)
    ui.browseableMessage = lambda message, **kwargs: ui.messages.append(message)
    return {name: sys.modules[name] for name in (
        "api", "controlTypes", "core", "keyboardHandler", "NVDAObjects.UIA",
        "UIAHandler", "ui",
    )}


def _load_sonos():
    modules = _install_nvda_stubs()
    spec = importlib.util.spec_from_file_location(
        "sonos_under_test", ROOT / "addon" / "appModules" / "sonos.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, modules


sonos, nvda = _load_sonos()


class Pattern:
    def __init__(self, minimum, maximum, value, read_only=False):
        self.CurrentMinimum = minimum
        self.CurrentMaximum = maximum
        self.CurrentValue = value
        self.CurrentIsReadOnly = read_only
        self.set_values = []
    def SetValue(self, value):
        self.set_values.append(value)
        self.CurrentValue = value


class Walker:
    def __init__(self, result):
        self.result, self.calls, self.condition = result, [], None
    def GetFirstChildElementBuildCache(self, element, cache_request):
        self.calls.append((element, cache_request))
        return self.result


class Client:
    def __init__(self, element, result):
        self.element, self.conditions = element, []
        self.walker = Walker(result)
    def ElementFromHandle(self, handle):
        return self.element
    def CreatePropertyCondition(self, property_id, value):
        condition = (property_id, value)
        self.conditions.append(condition)
        return condition
    def CreateTreeWalker(self, condition):
        self.walker.condition = condition
        return self.walker


class SonosTests(unittest.TestCase):
    def test_percent_uses_nonzero_minimum_and_rejects_invalid_range(self):
        self.assertEqual(sonos._percent(Pattern(10, 30, 15)), 25)
        with self.assertRaises(sonos.ControlUnavailable):
            sonos._percent(Pattern(10, 10, 10))

    def test_find_searches_raw_descendants_with_tree_walker(self):
        found, element = object(), object()
        client = Client(element, found)
        nvda["UIAHandler"].handler.clientObject = client
        root = nvda["NVDAObjects.UIA"].UIA(UIAElement=element)

        result = sonos._find(root, "PART_Scrubber")

        self.assertIsInstance(result, nvda["NVDAObjects.UIA"].UIA)
        self.assertIs(result.UIAElement, found)
        self.assertEqual(client.conditions, [(30005, "PART_Scrubber")])
        self.assertEqual(client.walker.condition, (30005, "PART_Scrubber"))
        self.assertEqual(
            client.walker.calls[0],
            (element, nvda["UIAHandler"].handler.baseCacheRequest),
        )

    def test_shortcut_overlay_is_scoped_to_sonos_shortcut_items(self):
        app = sonos.AppModule()
        UIA = nvda["NVDAObjects.UIA"].UIA
        role = nvda["controlTypes"].Role.DATAITEM
        shortcut = UIA(role=role, name="Sonos.Controller.Desktop.Main.KeyboardShortcut.Copy")
        other = UIA(role=role, name="Other.DataItem")
        shortcut_classes, other_classes = [], []

        app.chooseNVDAObjectOverlayClasses(shortcut, shortcut_classes)
        app.chooseNVDAObjectOverlayClasses(other, other_classes)

        self.assertEqual(shortcut_classes, [sonos.ShortcutItem])
        self.assertEqual(other_classes, [])
        item = sonos.ShortcutItem(name="fallback")
        item.firstChild = types.SimpleNamespace(name="Play/Pause", next=types.SimpleNamespace(name="Space"))
        self.assertEqual(item._get_name(), "Play/Pause Space")
        item.firstChild = None
        self.assertEqual(item._get_name(), "fallback")

    def test_seek_clamps_in_both_directions(self):
        app, pattern = sonos.AppModule(), Pattern(0, 100, 2)
        app._scrubber = lambda: (object(), pattern)
        nvda["api"].getForegroundObject = lambda: types.SimpleNamespace(
            processID=app.processID, windowHandle=99
        )

        app._seek(-10)
        app._seek(200)

        self.assertEqual(pattern.set_values, [0, 100])

    def test_seek_does_not_write_read_only_or_nan_scrubber(self):
        for pattern in (Pattern(0, 100, 50, read_only=True), Pattern(0, float("nan"), 50)):
            app = sonos.AppModule()
            app._scrubber = lambda pattern=pattern: (object(), pattern)
            with self.assertRaises(sonos.ControlUnavailable):
                app._seek(5)
            self.assertEqual(pattern.set_values, [])

    def test_set_position_restores_focus_after_provider_focuses_scrubber(self):
        app, pattern = sonos.AppModule(), Pattern(0, 300, 12)
        app.processID = 1
        app._scrubber = lambda: (object(), pattern)
        original = nvda["NVDAObjects.UIA"].UIA(UIAAutomationId="title")
        original.processID = app.processID
        nvda["api"].getFocusObject = lambda: original
        focused = types.SimpleNamespace(
            CurrentProcessId=app.processID, CurrentAutomationId="PART_Scrubber"
        )
        client = types.SimpleNamespace(GetFocusedElement=lambda: focused)
        old_client = nvda["UIAHandler"].handler.clientObject
        nvda["UIAHandler"].handler.clientObject = client
        try:
            app._setPosition(pattern, 42, 99)
        finally:
            nvda["UIAHandler"].handler.clientObject = old_client

        self.assertTrue(original.focused)

    def test_rapid_seek_callbacks_only_report_latest_request(self):
        app, pattern = sonos.AppModule(), Pattern(0, 300, 12)
        app._scrubber = lambda: (object(), pattern)
        root = types.SimpleNamespace(processID=app.processID, windowHandle=99)
        nvda["api"].getForegroundObject = lambda: root
        nvda["api"].getFocusObject = lambda: None
        nvda["core"].calls.clear()
        nvda["ui"].messages.clear()

        app._setPosition(pattern, 20, 99)
        app._setPosition(pattern, 30, 99)
        old_call, latest_call = nvda["core"].calls[-2:]
        latest_call[1](*latest_call[2], **latest_call[3])
        self.assertEqual(len(nvda["ui"].messages), 1)
        self.assertEqual("0:30", nvda["ui"].messages[0])
        app.script_reportScrub(None)
        self.assertEqual(nvda["ui"].messages[-1], "0:30 of 5:00, 10%")

        nvda["ui"].messages.clear()
        old_call[1](*old_call[2], **old_call[3])
        self.assertEqual(nvda["ui"].messages, [])

    def test_jump_dialog_transfers_edited_value_and_rejects_invalid_or_cancel(self):
        wx = types.ModuleType("wx")
        wx.ID_OK, wx.ID_CANCEL, wx.EVT_BUTTON = 1, 0, object()
        mode = {"typed": "1:44", "result": wx.ID_OK, "validate": True}

        class Event:
            def __init__(self):
                self.skipped = False
            def Skip(self):
                self.skipped = True

        class TextEntryDialog:
            def __init__(self, parent, message, title, value):
                self.value, self.edited, self.callback = value, mode["typed"], None
            def Bind(self, event, callback, id=None):
                self.callback = callback
            def TransferDataFromWindow(self):
                self.value = self.edited
                return True
            def GetValue(self):
                return self.value
            def Destroy(self):
                pass

        wx.TextEntryDialog = TextEntryDialog
        gui = types.ModuleType("gui")
        gui_message = types.ModuleType("gui.message")
        def display(dialog):
            if mode["validate"]:
                dialog.callback(Event())
            return mode["result"]
        gui_message.displayDialogAsModal = display
        sys.modules.update({"wx": wx, "gui": gui, "gui.message": gui_message})
        app = sonos.AppModule()
        jumps = []
        app._jumpTo = lambda *args: jumps.append(args)
        nvda["core"].calls.clear()
        try:
            app._showJumpDialog(99, ("room", "track"), 300, 12)
            scheduled = nvda["core"].calls[-1]
            scheduled[1](*scheduled[2], **scheduled[3])
            self.assertEqual(jumps, [(104, 99, ("room", "track"), 300)])

            mode.update(typed="1:60", result=wx.ID_OK, validate=True)
            nvda["core"].calls.clear()
            nvda["ui"].messages.clear()
            app._showJumpDialog(99, ("room", "track"), 300, 12)
            self.assertEqual(nvda["core"].calls, [])
            self.assertTrue(nvda["ui"].messages)

            mode.update(typed="1:44", result=wx.ID_CANCEL, validate=False)
            nvda["core"].calls.clear()
            app._showJumpDialog(99, ("room", "track"), 300, 12)
            self.assertEqual(nvda["core"].calls, [])
        finally:
            for name in ("wx", "gui", "gui.message"):
                sys.modules.pop(name, None)

    def test_parse_time_accepts_bounded_clock_forms(self):
        self.assertEqual(sonos._parse_time("90"), 90)
        self.assertEqual(sonos._parse_time("1:30"), 90)
        self.assertEqual(sonos._parse_time("1:02:30"), 3750)
        for text in ("", "-1", "text", "1:60", "1:2:3:4"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                sonos._parse_time(text)

    def test_jump_to_seeks_exact_position(self):
        app, pattern = sonos.AppModule(), Pattern(0, 300, 12)
        root = types.SimpleNamespace(processID=app.processID, windowHandle=99)
        app._root = lambda: root
        app._scrubber = lambda: (object(), pattern)
        app._trackInfo = lambda includeGroup=False: ("room", "track")
        nvda["core"].calls.clear()

        app._jumpTo(90, 99, ("room", "track"), 300)

        self.assertEqual(pattern.set_values, [90])

    def test_jump_to_refuses_a_changed_track(self):
        app, pattern = sonos.AppModule(), Pattern(0, 300, 12)
        root = types.SimpleNamespace(processID=app.processID, windowHandle=99)
        app._root = lambda: root
        app._scrubber = lambda: (object(), pattern)
        app._trackInfo = lambda includeGroup=False: ("room", "new track")
        nvda["ui"].messages.clear()

        app._jumpTo(90, 99, ("room", "old track"), 300)

        self.assertEqual(pattern.set_values, [])
        self.assertTrue(nvda["ui"].messages)
        app._trackInfo = lambda includeGroup=False: ("new room" if includeGroup else "room", "old track")
        app._jumpTo(90, 99, ("room", "old track"), 300)
        self.assertEqual(pattern.set_values, [])

    def test_format_seconds_is_readable_for_short_and_long_tracks(self):
        self.assertEqual(sonos._format_seconds(0), "0:00")
        self.assertEqual(sonos._format_seconds(65), "1:05")
        self.assertEqual(sonos._format_seconds(3661), "1:01:01")
        self.assertEqual(sonos._format_seconds(-1), "0:00")

    def test_toggle_uses_fixed_native_key_and_defers_state_report(self):
        app = sonos.AppModule()
        app._transport = lambda identifier: object()
        app._root = lambda: types.SimpleNamespace(windowHandle=77)
        keyboard = nvda["keyboardHandler"].KeyboardInputGesture
        keyboard.created.clear()
        nvda["core"].calls.clear()

        class RemappedGesture:
            mainKeyName = "q"
            def send(self):
                raise AssertionError("toggle must use its documented native key")

        app.script_toggleMute(RemappedGesture())

        self.assertEqual([gesture.name for gesture in keyboard.created], ["control+m"])
        self.assertTrue(keyboard.created[0].sent)
        self.assertEqual(nvda["core"].calls[-1][0], 250)

    def test_favorites_passes_native_key_speaks_and_skips_input_help_action(self):
        app = sonos.AppModule()
        keyboard = nvda["keyboardHandler"].KeyboardInputGesture
        keyboard.created.clear()
        nvda["ui"].messages.clear()
        gesture = types.SimpleNamespace(displayName="control+8")

        app.script_favorites(gesture)

        self.assertEqual([key.name for key in keyboard.created], ["control+8"])
        self.assertTrue(keyboard.created[0].sent)
        self.assertEqual(nvda["ui"].messages, ["Favorites"])

        keyboard.created.clear()
        nvda["ui"].messages.clear()
        sonos.inputCore.manager.isInputHelpActive = True
        try:
            app.script_favorites(gesture)
        finally:
            sonos.inputCore.manager.isInputHelpActive = False
        self.assertEqual(keyboard.created, [])
        self.assertEqual(nvda["ui"].messages, ["control+8: Favorites"])
        self.assertFalse(app.script_favorites.__doc__)
        self.assertTrue(app.script_favorites.scriptMetadata["bypassInputHelp"])

    def test_info_commands_work_with_remapped_gesture_and_copy_result(self):
        app = sonos.AppModule()
        app._trackInfo = lambda includeGroup=False: ("Room - Artist - Title", "Artist - Title")
        gesture = types.SimpleNamespace(mainKeyName="q")
        ui = nvda["ui"]
        ui.messages.clear()
        sonos.getLastScriptRepeatCount = lambda: 0

        app.script_speakInfo(gesture)
        self.assertEqual(ui.messages, ["Room - Artist - Title"])
        ui.messages.clear()
        app.script_browseInfo(gesture)
        self.assertEqual(ui.messages, ["Room - Artist - Title"])

        nvda["api"].copy_calls.clear()
        sonos.getLastScriptRepeatCount = lambda: 1
        app.script_speakInfo(gesture)
        self.assertEqual(nvda["api"].copy_calls, [("Artist - Title", True)])

        def failed_copy(text, notify=False):
            nvda["api"].copy_calls.append((text, notify))
            return False
        original_copy = nvda["api"].copyToClip
        nvda["api"].copyToClip = failed_copy
        try:
            app.script_speakInfo(gesture)
        finally:
            nvda["api"].copyToClip = original_copy
            sonos.getLastScriptRepeatCount = lambda: 0
        self.assertEqual(nvda["api"].copy_calls[-1], ("Artist - Title", True))

    def test_youtube_query_escapes_track_text_and_skips_missing_track(self):
        app = sonos.AppModule()
        app._trackInfo = lambda includeGroup=False: ("", "Artist & Title/#")
        opened, original_open = [], sonos.webbrowser.open_new_tab
        sonos.webbrowser.open_new_tab = opened.append
        try:
            app.script_openInYoutube(types.SimpleNamespace(mainKeyName="q"))
        finally:
            sonos.webbrowser.open_new_tab = original_open

        query = parse_qs(urlparse(opened[0]).query)
        self.assertEqual(query["search_query"], ["Artist & Title/#"])

        app._trackInfo = lambda includeGroup=False: ("", "")
        opened.clear()
        sonos.webbrowser.open_new_tab = opened.append
        try:
            app.script_openInYoutube(types.SimpleNamespace(mainKeyName="q"))
        finally:
            sonos.webbrowser.open_new_tab = original_open
        self.assertEqual(opened, [])

    def test_metadata_uses_ids_and_ignores_decorations_truncated_text_and_next(self):
        rows = [
            ("headerParens_1", "(Office"), ("headerParens2_1", " + 2)"),
            ("PART_Header", "Song [19/50]"), ("newDecoration", "unrelated"),
            ("PART_MetadataProperty", "Video"), ("PART_TruncatedMetadataProperty", "Vid..."),
            ("PART_Header", "Artist"), ("PART_MetadataProperty", "India.Arie"),
            ("PART_Header", "Album"), ("PART_MetadataProperty", "Acoustic Soul"),
            ("PART_Header", "Next"), ("PART_MetadataProperty", "Another track"),
        ]
        nodes = [types.SimpleNamespace(CachedAutomationId=identifier, CachedName=name)
                 for identifier, name in rows if identifier in ("PART_Header", "PART_MetadataProperty")]
        class MetadataWalker:
            def GetFirstChildElementBuildCache(self, element, cache):
                return nodes[0]
            def GetNextSiblingElementBuildCache(self, element, cache):
                index = nodes.index(element) + 1
                return nodes[index] if index < len(nodes) else None
        client = types.SimpleNamespace(
            CreatePropertyCondition=lambda prop, value: value,
            CreateOrCondition=lambda first, second: (first, second),
            CreateTreeWalker=lambda condition: MetadataWalker(),
        )
        app = sonos.AppModule()
        app._root = lambda: object()
        original_find = sonos._find
        original_client = nvda["UIAHandler"].handler.clientObject
        nvda["UIAHandler"].handler.clientObject = client
        sonos._find = lambda root, identifier: types.SimpleNamespace(
            UIAElement=object(), name=dict(rows).get(identifier, ""))
        try:
            info, track = app._trackInfo()
            self.assertEqual(app._trackInfo(includeGroup=True)[0], "Office + 2\n" + info)
            nvda["ui"].messages.clear()
            app.script_reportGroup(None)
            self.assertEqual(nvda["ui"].messages, ["Group Office + 2"])
            app.script_reportNext(None)
            self.assertEqual(nvda["ui"].messages[-1], "Next Another track")
            del nodes[6:]
            app.script_reportNext(None)
            self.assertEqual(nvda["ui"].messages[-1], "No next track information is available.")
        finally:
            sonos._find = original_find
            nvda["UIAHandler"].handler.clientObject = original_client
        self.assertEqual(info, "Song [19/50]: Video\nArtist: India.Arie\nAlbum: Acoustic Soul")
        self.assertEqual(track, "Video - India.Arie")

    def test_shift_commands_pass_through_edits_and_other_windows(self):
        app = sonos.AppModule()
        root = types.SimpleNamespace(role="window", processID=1)
        focus = types.SimpleNamespace(role="button", states=set())
        app._root = lambda: root
        nvda["api"].getFocusObject = lambda: focus
        original_find = sonos._find
        calls = []
        gesture = types.SimpleNamespace(send=lambda: calls.append("native"))
        app._seek = lambda seconds: calls.append(seconds)
        sonos._find = lambda *args: object()
        try:
            app.script_adjustScrubBackward(gesture)
            app.script_adjustScrubForward(gesture)
            self.assertEqual(calls, [-5, 5])
            for role, states, root_role in (("edit", set(), "window"), ("button", {"editable"}, "window"), ("button", set(), "dialog")):
                focus.role, focus.states, root.role = role, states, root_role
                for command in (app.script_adjustScrubBackward, app.script_adjustScrubForward, app.script_focusScrub):
                    command(gesture)
                    self.assertEqual(calls[-1], "native")
            root.role = "window"
            def missing(*args):
                raise sonos.ControlUnavailable()
            sonos._find = missing
            app.script_adjustScrubForward(gesture)
            self.assertEqual(calls[-1], "native")
        finally:
            sonos._find = original_find
            nvda["api"].getFocusObject = lambda: None

    def test_slider_overlay_formats_time_and_leaves_other_sliders_alone(self):
        app = sonos.AppModule()
        slider = sonos.Scrubber(role="slider", UIAAutomationId="PART_Scrubber")
        slider.UIARangeValue = 164
        self.assertEqual(slider._get_value(), "2:44")
        slider.UIARangeValue = None
        self.assertEqual(slider._get_value(), "fallback")
        for identifier, expected in (("PART_Scrubber", [sonos.Scrubber]), ("PART_VolumeSlider", [])):
            slider.UIAAutomationId = identifier
            classes = []
            app.chooseNVDAObjectOverlayClasses(slider, classes)
            self.assertEqual(classes, expected)
        app._scrubber = lambda: (object(), Pattern(0, 100, 41))
        nvda["ui"].messages.clear()
        app.script_reportCurrent(None)
        app.script_reportRemaining(None)
        self.assertEqual(nvda["ui"].messages, ["0:41 elapsed", "0:59 remaining"])

    def test_native_toggle_help_describes_without_sending_or_querying_sonos(self):
        app = sonos.AppModule()
        keyboard = nvda["keyboardHandler"].KeyboardInputGesture
        keyboard.created.clear()
        nvda["ui"].messages.clear()
        sonos.inputCore.manager.isInputHelpActive = True
        try:
            for name in ("Mute", "Repeat", "Shuffle", "Crossfade"):
                command = getattr(app, "script_toggle" + name)
                self.assertFalse(command.__doc__)
                self.assertTrue(command.scriptMetadata["bypassInputHelp"])
                command(types.SimpleNamespace(displayName="control+key"))
            self.assertEqual(keyboard.created, [])
            self.assertEqual(len(nvda["ui"].messages), 4)
            self.assertIn("Toggle mute", nvda["ui"].messages[0])
        finally:
            sonos.inputCore.manager.isInputHelpActive = False

    def test_group_navigation_announces_changes_and_ignores_stale_requests(self):
        app = sonos.AppModule()
        root = types.SimpleNamespace(windowHandle=99)
        app._root = lambda: root
        nvda["api"].getForegroundObject = lambda: root
        group = ["Office"]
        app._groupInfo = lambda: group[0]
        keyboard = nvda["keyboardHandler"].KeyboardInputGesture
        keyboard.created.clear()
        nvda["core"].calls.clear()
        nvda["ui"].messages.clear()
        app.script_previousGroup(None)
        old = nvda["core"].calls[-1]
        app.script_nextGroup(None)
        latest = nvda["core"].calls[-1]
        self.assertEqual([key.name for key in keyboard.created], ["control+,", "control+."])
        self.assertTrue(all(key.sent for key in keyboard.created))
        group[0] = "Kitchen"
        old[1](*old[2])
        self.assertEqual(nvda["ui"].messages, [])
        from unittest.mock import patch
        self.assertEqual(latest[0], 75)
        with patch.object(sonos, "perf_counter", return_value=latest[2][-1] + 0.22):
            latest[1](*latest[2])
        self.assertEqual(nvda["ui"].messages, ["Group Kitchen, 220 milliseconds"])
        nvda["ui"].messages.clear()
        app.script_nextGroup(None)
        while nvda["core"].calls:
            call = nvda["core"].calls.pop()
            call[1](*call[2])
        # Older callbacks were already exercised; only the newest sequence can speak.
        self.assertEqual(nvda["ui"].messages, [])
        def unavailable():
            raise sonos.ControlUnavailable()
        app._groupInfo = unavailable
        app.script_nextGroup(None)
        self.assertTrue(keyboard.created[-1].sent)

    def test_artwork_uses_visible_image_bounds_and_closes_clipboard(self):
        from collections import namedtuple
        Rect = namedtuple("Rect", "left top width height")
        image = sonos.UIA(role="graphic")
        image.location, image.next = Rect(20, 30, 225, 225), None
        button = sonos.UIA(role="button", UIAAutomationId="albumArtButton_1")
        button.next = image
        panel = types.SimpleNamespace(firstChild=button)
        app = sonos.AppModule()
        app._root = lambda: object()
        calls = []
        wx = types.SimpleNamespace(
            Bitmap=lambda w, h: (w, h), ScreenDC=lambda: object(), NullBitmap=None,
            BitmapDataObject=lambda bitmap: bitmap, Point=lambda x, y: (x, y), NOT_FOUND=-1,
            Display=types.SimpleNamespace(GetFromPoint=lambda point: 0),
        )
        class Memory:
            def __init__(self, bitmap):
                pass
            def Blit(self, dx, dy, w, h, screen, x, y):
                calls.append((x, y, w, h))
                return True
            def SelectObject(self, bitmap):
                calls.append("released")
        wx.MemoryDC = Memory
        wx.TheClipboard = types.SimpleNamespace(
            Open=lambda: True, SetData=lambda data: True, Flush=lambda: True,
            Close=lambda: calls.append("closed"),
        )
        original_find = sonos._find
        sonos._find = lambda *args: panel
        sys.modules["wx"] = wx
        nvda["ui"].messages.clear()
        try:
            app._copyArtwork()
            self.assertEqual(calls, [(20, 30, 225, 225), "released", "closed"])
            self.assertEqual(nvda["ui"].messages, ["Album artwork copied."])
            calls.clear()
            image.states = {"offscreen"}
            with self.assertRaises(sonos.ControlUnavailable):
                app._copyArtwork()
            self.assertEqual(calls, [])
            image.states = set()
            wx.TheClipboard.SetData = lambda data: False
            app._copyArtwork()
            self.assertEqual(calls[-1], "closed")
            self.assertEqual(nvda["ui"].messages[-1], "Could not copy album artwork.")
        finally:
            sonos._find = original_find
            sys.modules.pop("wx", None)

    def test_art_capture_uses_foreground_after_console_closes(self):
        import runpy
        sys.modules["buildVersion"] = types.SimpleNamespace(version="test")
        sys.modules["wx"] = types.SimpleNamespace()
        old_foreground = nvda["api"].getForegroundObject
        calls = []
        nvda["api"].getForegroundObject = lambda: calls.append("foreground") or types.SimpleNamespace(appModule=None)
        nvda["core"].calls.clear()
        nvda["ui"].messages.clear()
        try:
            capture = runpy.run_path(str(ROOT / "tools" / "capture_sonos.py"))["capture_art"]
            capture(types.SimpleNamespace(appModule=None))
            self.assertEqual(calls, [])
            delay, callback, args, kwargs = nvda["core"].calls[-1]
            self.assertEqual(delay, 5000)
            callback(*args, **kwargs)
            self.assertEqual(calls, ["foreground"])
            self.assertIn("return to Sonos", nvda["ui"].messages[-1])
        finally:
            nvda["api"].getForegroundObject = old_foreground
            sys.modules.pop("buildVersion", None)
            sys.modules.pop("wx", None)

    def test_playback_toggles_remove_only_redundant_description_and_shortcut(self):
        app = sonos.AppModule()
        toggle = sonos.ButtonLabels(name="Crossfade", role="toggle", states={"pressed"},
                                      UIAAutomationId="crossfadeToggleButton")
        classes = []
        app.chooseNVDAObjectOverlayClasses(toggle, classes)
        self.assertEqual(classes, [sonos.ButtonLabels])
        self.assertEqual((toggle.name, toggle.role, toggle.states), ("Crossfade", "toggle", {"pressed"}))
        self.assertEqual(toggle.description, "")
        self.assertEqual(toggle.keyboardShortcut, "")
        toggle.UIAFullDescription = "Crossfade is on"
        toggle.UIAHelpText = "fallback"
        app._transport = lambda identifier: toggle
        nvda["ui"].messages.clear()
        app.script_reportCrossfade(None)
        self.assertEqual(nvda["ui"].messages, ["Crossfade is on"])
        toggle.UIAFullDescription = ""
        toggle.UIAHelpText = "Crossfade is off"
        app._reportState("crossfadeToggleButton")
        self.assertEqual(nvda["ui"].messages[-1], "Crossfade is off")
        for identifier in ("muteButton", "repeatToggleButton", "shuffleToggleButton"):
            toggle.UIAAutomationId = identifier
            classes = []
            app.chooseNVDAObjectOverlayClasses(toggle, classes)
            self.assertEqual(classes, [sonos.ButtonLabels])
        for identifier in ("otherToggle", "zoneGroupScrollViewer"):
            toggle.UIAAutomationId = identifier
            classes = []
            app.chooseNVDAObjectOverlayClasses(toggle, classes)
            self.assertEqual(classes, [])

    def test_missing_slider_has_concise_message_for_all_time_commands(self):
        app = sonos.AppModule()
        def missing(identifier):
            raise sonos.ControlUnavailable(identifier)
        app._transport = missing
        nvda["ui"].messages.clear()
        for command in (app.script_reportCurrent, app.script_reportRemaining, app.script_reportScrub):
            command(None)
        app._run(lambda: app._seek(5))
        self.assertEqual(nvda["ui"].messages, ["No track slider"] * 4)
        app._transport = lambda identifier: types.SimpleNamespace(UIARangeValuePattern=None)
        app.script_reportScrub(None)
        self.assertEqual(nvda["ui"].messages[-1], "No track slider")
        app._run(lambda: missing("volume"))
        self.assertEqual(nvda["ui"].messages[-1], "This control is unavailable in the current Sonos view.")

    def test_button_cleanup_is_limited_to_confirmed_controls(self):
        app = sonos.AppModule()
        button = sonos.ButtonLabels(name="Back", role="button", UIAAutomationId="Button_1")
        button.rawShortcut = "Back"
        classes = []
        app.chooseNVDAObjectOverlayClasses(button, classes)
        self.assertEqual(classes, [sonos.ButtonLabels])
        self.assertEqual((button.description, button.keyboardShortcut), ("", ""))
        self.assertEqual((button.name, button.role), ("Back", "button"))
        for identifier, shortcut in (("otherButton", "Back"), ("Button_1", "Alt+LeftArrow")):
            other = sonos.UIA(name="Other", role="button", UIAAutomationId=identifier)
            other.rawDescription, other.rawShortcut = "Useful help", shortcut
            classes = []
            app.chooseNVDAObjectOverlayClasses(other, classes)
            self.assertEqual(classes, [])
            self.assertEqual(other._get_description(), "Useful help")
            self.assertEqual(other._get_keyboardShortcut(), shortcut)

    def test_sonos_action_labels_and_eq_name(self):
        for identifier, name, description, shortcut in (
            ("playButton", "Play/Pause", "", "Toggle Play"),
            ("pauseAllButton_1", "Pause All", "Pause All", "Pause All"),
            ("alarmsButton_1", "Alarms", "Alarms", "Alarms"),
            ("Button_1", "Save to Your Music", "", "Now Playing Button"),
            ("Button_1", "Remove from Your Music", "", "Now Playing Button"),
            ("Button_1", "Info and Options", "Info & Options", "Info"),
        ):
            button = sonos.ButtonLabels(name=name, role="button", UIAAutomationId=identifier)
            button.rawDescription, button.rawShortcut = description, shortcut
            classes = []
            sonos.AppModule().chooseNVDAObjectOverlayClasses(button, classes)
            self.assertEqual(classes, [sonos.ButtonLabels])
            self.assertEqual(button._get_name(), name)
            self.assertEqual(button.description, "")
            self.assertEqual(button.keyboardShortcut, "")
        eq = sonos.ButtonLabels(role="button", UIAAutomationId="equalizerMenuButton")
        eq.rawDescription = "Music EQ"
        self.assertEqual(eq._get_name(), "Music EQ")
        eq.name = eq._get_name()  # Simulate NVDA's automatic name property.
        self.assertEqual(eq.description, "")

    def test_eq_speaker_menu_uses_child_room_names(self):
        app = sonos.AppModule()
        for room in ("Office", "Bedroom"):
            item = sonos.ShortcutItem(role="menuitem", name="Sonos.Controller.Desktop.SCLib.ViewModel.ZonePlayerViewModel")
            item.firstChild = types.SimpleNamespace(name="", next=types.SimpleNamespace(name=room))
            classes = []
            app.chooseNVDAObjectOverlayClasses(item, classes)
            self.assertEqual(classes, [sonos.ShortcutItem])
            self.assertEqual(item._get_name(), room)
            self.assertEqual(item.role, "menuitem")
        item.name = "Ordinary menu item"
        classes = []
        app.chooseNVDAObjectOverlayClasses(item, classes)
        self.assertEqual(classes, [])


    def test_alarm_enabled_label_is_scoped_and_preserves_checkbox_state(self):
        app = sonos.AppModule()
        checkbox = sonos.AlarmEnabledCheckbox(role="checkbox", states={"checked"})
        checkbox.windowText = "Alarms"
        classes = []
        app.chooseNVDAObjectOverlayClasses(checkbox, classes)
        self.assertEqual(classes, [sonos.AlarmEnabledCheckbox])
        self.assertEqual(checkbox._get_name(), "Enabled")
        checkbox.windowText = "Wecker"
        classes = []
        app.chooseNVDAObjectOverlayClasses(checkbox, classes)
        self.assertEqual(classes, [sonos.AlarmEnabledCheckbox])
        self.assertEqual((checkbox.role, checkbox.states), ("checkbox", {"checked"}))
        for name, window, identifier in (("Repeat", "Alarms", ""), ("", "Settings", ""), ("", "Alarms", "otherCheckbox")):
            checkbox.name, checkbox.windowText, checkbox.UIAAutomationId = name, window, identifier
            classes = []
            app.chooseNVDAObjectOverlayClasses(checkbox, classes)
            self.assertEqual(classes, [])
        self.assertFalse(hasattr(app, "script_saveMusic"))

    def test_sleep_timer_keeps_countdown_without_repeating_base_label(self):
        for label in ("Sleep Timer", "Schlummermodus"):
            button = sonos.ButtonLabels(name=label + " (0:30)", role="button", UIAAutomationId="sleepTimerButton_1")
            button.rawDescription = button.rawShortcut = label
            self.assertEqual(button._get_name(), label + " (0:30)")
            self.assertEqual(button.description, "")
            self.assertEqual(button.keyboardShortcut, "")
            classes = []
            sonos.AppModule().chooseNVDAObjectOverlayClasses(button, classes)
            self.assertEqual(classes, [sonos.ButtonLabels])


if __name__ == "__main__":
    unittest.main()
