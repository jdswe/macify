"""Apps que dibujan su propia barra de título: se les pide usar la del sistema.

Así muestran los botones de semáforo de WhiteSur como el resto del escritorio.
Cada cambio guarda el valor anterior en apps-backup.json para poder deshacerlo.
Si una app está abierta se deja para el próximo inicio de sesión (ver session.py),
porque los navegadores reescriben sus preferencias al cerrarse.
"""

import json
import shutil
import subprocess
from pathlib import Path

from . import themes
from .assets import CONFIG_DIR, HOME
from .i18n import _

BACKUP = CONFIG_DIR / "apps-backup.json"
VSCODE_SETTINGS = HOME / ".config" / "Code" / "User" / "settings.json"
GTK_THEME = 1   # valor de Chromium para «apariencia GTK» (0 = clásica, 2 = Qt)
CHROMIUM_BROWSERS = [
    ("Brave", "brave", HOME / ".config" / "BraveSoftware" / "Brave-Browser" / "Default" / "Preferences"),
    ("Google Chrome", "chrome", HOME / ".config" / "google-chrome" / "Default" / "Preferences"),
    ("Chromium", "chromium", HOME / "snap" / "chromium" / "common" / "chromium" / "Default" / "Preferences"),
    ("Microsoft Edge", "msedge", HOME / ".config" / "microsoft-edge" / "Default" / "Preferences"),
    ("Vivaldi", "vivaldi-bin", HOME / ".config" / "vivaldi" / "Default" / "Preferences"),
]
FLATPAK_ACCESS = ["--filesystem=xdg-config/gtk-3.0:ro", "--filesystem=xdg-config/gtk-4.0:ro",
                  "--filesystem=~/.themes:ro", "--filesystem=~/.local/share/icons:ro"]
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


def _chromium_browsers(dry_run: bool, log, backup: dict) -> None:
    """Navegadores Chromium: modo de apariencia GTK, que dibuja los botones con el tema del sistema."""
    for name, process, preferences_path in CHROMIUM_BROWSERS:
        if not preferences_path.exists():
            continue
        preferences = json.loads(preferences_path.read_text())
        theme = preferences.get("extensions", {}).get("theme", {})
        frame = preferences.get("browser", {}).get("custom_chrome_frame", MISSING)
        if theme.get("system_theme") == GTK_THEME and frame in (MISSING, True):
            continue
        if _running(process):
            log(_("{name} is open: its buttons will change at your next login.").format(name=name))
            continue
        log(_("{name}: use the system theme for its buttons").format(name=name))
        if dry_run:
            continue
        saved = backup.setdefault("chromium", {}).setdefault(name, {})
        saved.setdefault("system_theme", theme.get("system_theme", MISSING))
        saved.setdefault("custom_chrome_frame", frame)
        preferences.setdefault("extensions", {}).setdefault("theme", {})["system_theme"] = GTK_THEME
        preferences.get("browser", {}).pop("custom_chrome_frame", None)   # su propia barra, con botones GTK
        preferences_path.write_text(json.dumps(preferences))


def _flatpak(dry_run: bool, log, backup: dict) -> None:
    """Apps Flatpak: acceso de solo lectura al tema, los iconos y la configuración GTK."""
    if shutil.which("flatpak") is None or backup.get("flatpak"):
        return
    log(_("Flatpak apps: use the system theme and icons"))
    if dry_run:
        return
    subprocess.run(["flatpak", "override", "--user", *FLATPAK_ACCESS], check=False, capture_output=True)
    backup["flatpak"] = True


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
    for tweak in (_vscode, _chromium_browsers, _firefox, _flatpak):
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
    for name, process, preferences_path in CHROMIUM_BROWSERS:
        saved = backup.get("chromium", {}).get(name)
        if not saved or not preferences_path.exists() or _running(process):
            continue
        log(_("{name}: restore its buttons").format(name=name))
        if dry_run:
            continue
        preferences = json.loads(preferences_path.read_text())
        theme = preferences.setdefault("extensions", {}).setdefault("theme", {})
        if saved["system_theme"] == MISSING:
            theme.pop("system_theme", None)
        else:
            theme["system_theme"] = saved["system_theme"]
        if saved["custom_chrome_frame"] != MISSING:
            preferences.setdefault("browser", {})["custom_chrome_frame"] = saved["custom_chrome_frame"]
        preferences_path.write_text(json.dumps(preferences))
    if backup.get("flatpak") and shutil.which("flatpak"):
        log(_("Flatpak apps: restore their default theme access"))
        if not dry_run:
            subprocess.run(["flatpak", "override", "--user", "--reset"], check=False, capture_output=True)
    if backup.get("firefox") and themes.repo_dir("gtk").exists():
        log(_("Firefox: remove the macOS theme"))
        if not dry_run:
            themes.firefox_theme(False, log)
    if not dry_run:
        BACKUP.unlink(missing_ok=True)
