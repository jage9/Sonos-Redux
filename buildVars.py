# Sonos add-on build metadata.

from site_scons.site_tools.NVDATool.typings import (
	AddonInfo,
	BrailleTables,
	SpeechDictionaries,
	SymbolDictionaries,
)
from site_scons.site_tools.NVDATool.utils import _


addon_info = AddonInfo(
	addon_name="Sonos",
	addon_summary=_("Sonos"),
	addon_description=_("Accessibility enhancements for the Sonos Desktop app."),
	addon_version="2026.1",
	addon_changelog=_("Updated for NVDA 2026.1 with many new features (see ReadMe)"),
	addon_author="Ralf Kefferpuetz <novalis7747@live.com>, J.J. Meddaugh <jj@bestmidi.com>",
	addon_url="https://github.com/jage9/Sonos-Redux",
	addon_sourceURL="https://github.com/jage9/Sonos-Redux",
	addon_docFileName="readme.html",
	addon_minimumNVDAVersion="2026.1.0",
	# Development target; runtime compatibility and documentation metadata are unverified.
	addon_lastTestedNVDAVersion="2026.3.0",
	addon_updateChannel="dev",
	addon_license="GPL v2",
	addon_licenseURL="https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
)


pythonSources: list[str] = ["addon/appModules/*.py"]
i18nSources: list[str] = pythonSources + ["buildVars.py"]
excludedFiles: list[str] = ["**/__pycache__/**", "**/*.pyc", "**/*.pyo"]
baseLanguage: str = "en"
markdownExtensions: list[str] = ["markdown.extensions.tables"]
brailleTables: BrailleTables = {}
symbolDictionaries: SymbolDictionaries = {}
speechDictionaries: SpeechDictionaries = {}
