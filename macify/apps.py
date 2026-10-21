"""Apps que dibujan su propia barra de título: se les pide usar la del sistema.

Así muestran los botones de semáforo de WhiteSur como el resto del escritorio.
Cada cambio guarda el valor anterior en apps-backup.json para poder deshacerlo.
Si una app está abierta se deja para el próximo inicio de sesión (ver session.py),
porque los navegadores reescriben sus preferencias al cerrarse.
"""

import json
import subprocess
from pathlib import Path

from . import themes
from .assets import CONFIG_DIR, HOME
from .i18n import _

BACKUP = CONFIG_DIR / "apps-backup.json"
VSCODE_SETTINGS = HOME / ".config" / "Code" / "User" / "settings.json"
BRAVE_PREFERENCES = HOME / ".config" / "BraveSoftware" / "Brave-Browser" / "Default" / "Preferences"
FIREFOX_PROFILES = [HOME / "snap" / "firefox" / "common" / ".mozilla" / "firefox", HOME / ".mozilla" / "firefox"]
MISSING = "__missing__"


def _running(process: str) -> bool:
    return subprocess.run(["pgrep", "-x", process], capture_output=True).returncode == 0


def _load_backup() -> dict:
    return json.loads(BACKUP.read_text()) if BACKUP.exists() else {}


def _save_backup(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP.write_text(json.dumps(data, indent=2))


def _vscode(dry_run: bool, log, backup: dict) -> None:
    if not VSCODE_SETTINGS.parent.parent.exists():
        return
    settings = json.loads(VSCODE_SETTINGS.read_text() or "{}") if VSCODE_SETTINGS.exists() else {}
    if settings.get("window.titleBarStyle") == "native":
        return
    log(_("VS Code: use the system title bar"))
    if dry_run:
        return
    backup.setdefault("vscode", settings.get("window.titleBarStyle", MISSING))
    settings["window.titleBarStyle"] = "native"
    VSCODE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    VSCODE_SETTINGS.write_text(json.dumps(settings, indent=4))


def _brave(dry_run: bool, log, backup: dict) -> None:
    if not BRAVE_PREFERENCES.exists():
        return
    preferences = json.loads(BRAVE_PREFERENCES.read_text())
    if preferences.get("browser", {}).get("custom_chrome_frame") is False:
        return
    if _running("brave"):
        log(_("Brave is open: its title bar will change at your next login."))
        return
    log(_("Brave: use the system title bar"))
    if dry_run:
        return
    backup.setdefault("brave", preferences.get("browser", {}).get("custom_chrome_frame", MISSING))
    preferences.setdefault("browser", {})["custom_chrome_frame"] = False
    BRAVE_PREFERENCES.write_text(json.dumps(preferences))


def _firefox(dry_run: bool, log, backup: dict) -> None:
    if not any(folder.exists() for folder in FIREFOX_PROFILES) or backup.get("firefox"):
        return
    if _running("firefox"):
        log(_("Firefox is open: its macOS theme will be installed at your next login."))
        return
    log(_("Firefox: macOS theme with traffic-light buttons"))
    if dry_run:
        return
    themes.firefox_theme(True, log)
    backup["firefox"] = True


def apply(dry_run: bool, log) -> None:
    backup = _load_backup()
    for tweak in (_vscode, _brave, _firefox):
        try:
            tweak(dry_run, log, backup)
        except (OSError, ValueError, RuntimeError) as error:
            log(f"{tweak.__name__.strip('_')}: {error}")
    if not dry_run and backup:
        _save_backup(backup)


def restore(dry_run: bool, log) -> None:
    backup = _load_backup()
    if "vscode" in backup and VSCODE_SETTINGS.exists():
        log(_("VS Code: restore its title bar"))
        if not dry_run:
            settings = json.loads(VSCODE_SETTINGS.read_text() or "{}")
            if backup["vscode"] == MISSING:
                settings.pop("window.titleBarStyle", None)
            else:
                settings["window.titleBarStyle"] = backup["vscode"]
            VSCODE_SETTINGS.write_text(json.dumps(settings, indent=4))
    if "brave" in backup and BRAVE_PREFERENCES.exists() and not _running("brave"):
        log(_("Brave: restore its title bar"))
        if not dry_run:
            preferences = json.loads(BRAVE_PREFERENCES.read_text())
            if backup["brave"] == MISSING:
                preferences.get("browser", {}).pop("custom_chrome_frame", None)
            else:
                preferences.setdefault("browser", {})["custom_chrome_frame"] = backup["brave"]
            BRAVE_PREFERENCES.write_text(json.dumps(preferences))
    if backup.get("firefox") and themes.repo_dir("gtk").exists():
        log(_("Firefox: remove the macOS theme"))
        if not dry_run:
            themes.firefox_theme(False, log)
    if not dry_run:
        BACKUP.unlink(missing_ok=True)
