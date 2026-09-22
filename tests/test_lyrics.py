"""Regression checks for lyrics matching, safe display and request lifecycle."""
import io
from contextlib import contextmanager, nullcontext
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

from test_sonos import sonos, nvda, Pattern


class LyricsTests(unittest.TestCase):
    metadata = {"track_name": "Test & track", "artist_name": "Artist", "album_name": "Album", "duration": 200}
    record = {"trackName": "Test track", "artistName": "Artist", "albumName": "Album",
              "duration": 200, "plainLyrics": "Example line", "syncedLyrics": None, "instrumental": False}

    def response(self, value):
        return io.BytesIO(json.dumps(value).encode())

    def test_match_and_404_fallback(self):
        with patch.object(sonos, "urlopen", return_value=self.response(self.record)) as request:
            self.assertEqual(sonos._fetchLyrics(self.metadata, "Test/1"), ([self.record], True))
            self.assertEqual(request.call_args.args[0].get_header("User-agent"), "Test/1")
            self.assertEqual(parse_qs(urlparse(request.call_args.args[0].full_url).query)["duration"], ["200"])
        missing = HTTPError("https://lrclib.net/api/get", 404, "Missing", {}, None)
        with patch.object(sonos, "urlopen", side_effect=[missing, self.response([self.record])]) as request, \
                patch.object(sonos, "sleep") as sleep:
            self.assertEqual(sonos._fetchLyrics(self.metadata, "Test/1"), ([self.record], False))
            query = parse_qs(urlparse(request.call_args.args[0].full_url).query)
            self.assertEqual(query, {"track_name": ["Test & track"], "artist_name": ["Artist"]})
            sleep.assert_called_once_with(.5)

    def test_invalid_response_and_rate_limit(self):
        for value in ({}, {**self.record, "duration": float("nan")}, {**self.record, "plainLyrics": []}):
            with self.subTest(value=value), patch.object(sonos, "urlopen", return_value=self.response(value)):
                with self.assertRaises(ValueError):
                    sonos._fetchLyrics(self.metadata, "Test/1")
        limited = HTTPError("https://lrclib.net/api/get", 429, "Busy", {"Retry-After": "120"}, None)
        with patch.object(sonos, "urlopen", side_effect=limited) as request:
            with self.assertRaises(HTTPError):
                sonos._fetchLyrics(self.metadata, "Test/1")
            self.assertEqual(request.call_count, 1)

    def test_timed_text_and_html_escaping(self):
        self.assertEqual(sonos._lyricsText({"syncedLyrics": "[ar:Artist]\n[00:01.00]Example one\n[00:03.50]Example two"}),
                         "Example one\nExample two")
        app = sonos.AppModule()
        gui = types.ModuleType("gui")
        message = types.ModuleType("gui.message")
        message.displayDialogAsModal = lambda dialog: None
        wx = types.ModuleType("wx")
        wx.GetTopLevelWindows = lambda: []
        with patch.dict(sys.modules, {"wx": wx, "gui": gui, "gui.message": message}), \
                patch.object(sonos.ui, "browseableMessage") as show:
            app._showLyrics(self.metadata, [{**self.record, "plainLyrics": "<script>example</script> & text"}], True)
            rendered = show.call_args.args[0]
            self.assertNotIn("<script>", rendered)
            self.assertIn("&lt;script&gt;", rendered)
            self.assertIn('href="https://lrclib.net/"', rendered)

    def test_open_lyrics_window_is_reused_and_closed_one_is_recreated(self):
        app = sonos.AppModule()
        wx = types.ModuleType("wx")
        wx.EVT_MENU, wx.ID_SAVE, wx.ID_CANCEL = "menu", 1, 2
        wx.ACCEL_CTRL, wx.ACCEL_NORMAL, wx.WXK_ESCAPE = 4, 0, 27
        wx.AcceleratorTable = lambda entries: entries
        windows = []
        wx.GetTopLevelWindows = lambda: windows[:]
        message = types.ModuleType("gui.message")
        message.displayDialogAsModal = Mock()
        def open_window(content, title, **kwargs):
            window = Mock()
            window.GetTitle.return_value = title
            windows.append(window)
        with patch.dict(sys.modules, {"wx": wx, "gui.message": message}), \
                patch.object(sonos.ui, "browseableMessage", side_effect=open_window) as show:
            app._showLyrics(self.metadata, [self.record], True)
            window = windows[0]
            self.assertEqual(window._sonosLyricsTrack, self.metadata)
            self.assertEqual(window.SetAcceleratorTable.call_args.args[0], [(4, ord("S"), 1), (0, 27, 2)])
            with patch.object(app, "_saveLyrics") as save:
                window.Bind.call_args_list[0].args[1](None)
                save.assert_called_once_with(window, self.record)
            window.Bind.call_args_list[1].args[1](None)
            window.Close.assert_called_once_with()
            # Reuse also skips the recording picker on a search result.
            app._showLyrics(self.metadata.copy(), [self.record], False)
            self.assertEqual(show.call_count, 1)
            window.Iconize.assert_called_once_with(False)
            window.Raise.assert_called_once_with()
            window.SetFocus.assert_called_once_with()
            message.displayDialogAsModal.assert_not_called()
            self.assertFalse(app._focusLyrics({**self.metadata, "track_name": "Other track"}))
            windows.clear()
            app._showLyrics(self.metadata, [self.record], True)
            self.assertEqual(show.call_count, 2)

    def test_save_lyrics_cancel_success_and_failure(self):
        app, parent = sonos.AppModule(), object()
        wx = types.ModuleType("wx")
        wx.ID_OK, wx.FD_SAVE, wx.FD_OVERWRITE_PROMPT = 1, 2, 4
        wx.StandardPaths = types.SimpleNamespace(Get=lambda: types.SimpleNamespace(GetDocumentsDir=lambda: "Documents"))
        dialog = Mock()
        dialog.GetPath.return_value = "chosen.txt"
        wx.FileDialog = Mock(side_effect=lambda *args, **kwargs: nullcontext(dialog))
        message = types.ModuleType("gui.message")
        message.displayDialogAsModal = Mock(return_value=0)
        files = types.ModuleType("fileUtils")
        saved = []
        @contextmanager
        def writer(path):
            output = io.BytesIO()
            yield output
            saved.append((path, output.getvalue().decode("utf-8")))
        files.FaultTolerantFile = Mock(side_effect=writer)
        record = {**self.record, "artistName": "Artist/Name", "trackName": "Test: title", "plainLyrics": "Example café"}
        with patch.dict(sys.modules, {"wx": wx, "gui.message": message, "fileUtils": files}):
            app._saveLyrics(parent, record)
            files.FaultTolerantFile.assert_not_called()
            message.displayDialogAsModal.return_value = 1
            app._saveLyrics(parent, record)
            self.assertEqual(wx.FileDialog.call_args.kwargs["defaultFile"], "Artist_Name - Test_ title.txt")
            self.assertEqual(wx.FileDialog.call_args.kwargs["style"], 6)
            self.assertEqual(saved[0][0], "chosen.txt")
            self.assertIn("Example café", saved[0][1])
            self.assertIn("https://lrclib.net/", saved[0][1])
            files.FaultTolerantFile.side_effect = PermissionError("Denied")
            app._saveLyrics(parent, record)
            self.assertEqual(nvda["ui"].messages[-1], "Could not save lyrics. Check the filename and folder.")

    def test_lyrics_uses_duration_from_disabled_scrubber(self):
        app = sonos.AppModule()
        app._root = lambda: object()
        app._metadataFields = lambda panel, limit: [("Song", "Title"), ("Artist", "Artist"), ("Album", "Album")]
        slider = types.SimpleNamespace(states={nvda["controlTypes"].State.UNAVAILABLE},
                                       UIARangeValuePattern=Pattern(0, 403, 330, read_only=True))
        settings = types.ModuleType("globalPlugins.sonosSettings")
        settings.lyricsUserAgent = lambda: "Test/1"
        wx = types.ModuleType("wx")
        wx.GetTopLevelWindows = lambda: []
        with patch.dict(sys.modules, {"wx": wx, "globalPlugins.sonosSettings": settings}), \
                patch.object(sonos, "_find", return_value=slider), patch.object(sonos, "Thread") as thread:
            app.script_lyrics(None)
            self.assertEqual(thread.call_args.kwargs["args"][1]["duration"], 403)
            thread.return_value.start.assert_called_once_with()

    def test_worker_cooldown_and_stale_completion(self):
        app = sonos.AppModule()
        token = app._lyricsRequestToken = object()
        callbacks = []
        wx = types.ModuleType("wx")
        wx.CallAfter = lambda *args: callbacks.append(args)
        limited = HTTPError("https://lrclib.net/api/get", 429, "Busy", {"Retry-After": "120"}, None)
        with patch.dict(sys.modules, {"wx": wx}), patch.object(sonos, "_fetchLyrics", side_effect=limited):
            app._fetchLyricsWorker(token, self.metadata, "Test/1")
        callback, *args = callbacks[0]
        with patch.object(sonos, "perf_counter", return_value=10):
            callback(*args)
        self.assertEqual(app._lyricsRetryAt, 130)
        self.assertIsNone(app._lyricsRequestToken)
        app._lyricsFetched(token, self.metadata, ([self.record], True), None, 0)
        self.assertFalse(hasattr(app, "_lyricsCache"))


if __name__ == "__main__":
    unittest.main()
