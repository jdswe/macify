"""Diagnóstico de Macify: revisa la instalación, detecta lo roto o desactualizado y lo arregla.

Cada revisión devuelve un Check con su estado y, si hay arreglo, la función que lo aplica.
Se usa desde la app (botón «Check for problems»), la terminal (`macify doctor --fix`)
y al iniciar sesión (aviso si hay algo pendiente).
"""

import json
import shutil
import subprocess
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

from gi.repository import GLib

from . import deps, extensions, fonts, icons, profile, session, system, themes
from .assets import busy, load_config
from .i18n import _

OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: Callable[[Callable[[str], None]], None] | None = None


def _same(current: str, expected: str) -> bool:
    """Compara valores GVariant sin depender del formato (48 vs uint32 48, 0.35 vs 0.34999…)."""
    try:
        a, b = GLib.Variant.parse(None, current, None, None), GLib.Variant.parse(None, expected, None, None)
    except GLib.Error:
        return current.strip() == expected.strip()

    def close(x, y) -> bool:
        if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            return len(x) == len(y) and all(close(i, j) for i, j in zip(x, y))
        if isinstance(x, float) or isinstance(y, float):
            return abs(float(x) - float(y)) < 1e-3
        return x == y

    return close(a.unpack(), b.unpack())


# Estados de extensión de GNOME Shell (org.gnome.Shell.Extensions → «state»).
SHELL_STATES = {1: "ACTIVE", 2: "INACTIVE", 3: "ERROR", 4: "OUT OF DATE", 5: "DOWNLOADING",
                6: "INITIALIZED", 7: "DEACTIVATING", 8: "ACTIVATING"}


def _shell_state(uuid: str) -> str:
    """Estado de una extensión preguntando al Shell por D-Bus (sin lanzar procesos)."""
    from gi.repository import Gio

    try:
        reply = Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            "org.gnome.Shell.Extensions", "/org/gnome/Shell/Extensions", "org.gnome.Shell.Extensions",
            "GetExtensionInfo", GLib.Variant("(s)", (uuid,)), GLib.VariantType("(a{sv})"),
            Gio.DBusCallFlags.NONE, 5000, None)
    except GLib.Error:
        return "NOT LOADED"
    info = reply.unpack()[0]
    return SHELL_STATES.get(int(info["state"]), "NOT LOADED") if "state" in info else "NOT LOADED"


def _remote_extension_version(uuid: str) -> int | None:
    url = f"https://extensions.gnome.org/extension-info/?uuid={uuid}&shell_version=50"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return int(json.load(response)["version"])
    except (OSError, ValueError, KeyError):
        return None


def _local_extension_version(uuid: str) -> int | None:
    metadata = extensions.INSTALL_DIR / uuid / "metadata.json"
    try:
        return int(json.loads(metadata.read_text()).get("version", 0))
    except (OSError, ValueError):
        return None


# ----- revisiones -----

def check_macify(online: bool) -> Check:
    from . import __version__, updates

    name = "Macify"
    if not online:
        return Check(name, OK, _("Version {version} (update check skipped).").format(version=__version__))
    try:
        release = updates.latest()
    except (OSError, ValueError, KeyError):
        return Check(name, WARN, _("Could not reach GitHub to check for updates."))
    if release and updates.is_newer(release["version"]):
        return Check(name, WARN, _("Version {version} is available.").format(version=release["version"]),
                     lambda log: updates.install(release, log))
    return Check(name, OK, _("Version {version}, the latest.").format(version=__version__))


def check_tools() -> Check:
    missing = deps.missing_packages()
    if not missing:
        return Check(_("System tools"), OK, _("All installed."))
    return Check(_("System tools"), FAIL, ", ".join(missing), lambda log: deps.install(missing, log))


def _parallel(function, items) -> dict:
    """Consultas de red a la vez: el diagnóstico espera a la más lenta, no a la suma."""
    from concurrent.futures import ThreadPoolExecutor

    def safe(item):
        try:
            return function(item)
        except (OSError, ValueError, KeyError):
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(items, pool.map(safe, items)))


def check_themes(online: bool) -> list[Check]:
    choices = profile.load_choices()
    present = [key for key in themes.REPOS if themes.repo_dir(key).exists()]
    latest_commits = _parallel(lambda key: themes.latest_commit(key)[1], present) if online else {}
    result = []
    installers = {"gtk": lambda log: themes.install_gtk(choices.appearance, False, log),
                  "icons": lambda log: themes.install_icons(False, log),
                  "cursors": lambda log: themes.install_cursors(False, log)}
    names = {"gtk": _("Windows theme"), "icons": _("Icon set"), "cursors": _("Cursor")}
    for key, install in installers.items():
        name = names[key]

        def refresh(log, key=key, install=install) -> None:
            shutil.rmtree(themes.repo_dir(key), ignore_errors=True)
            themes.fetch(key, log)
            install(log)

        if not themes.repo_dir(key).exists():
            result.append(Check(name, FAIL, _("Not downloaded."), refresh))
            continue
        installed = themes.installed_commit(key)
        if not online:
            result.append(Check(name, OK, _("Installed (update check skipped).")))
            continue
        latest = latest_commits.get(key)
        if latest is None:
            result.append(Check(name, WARN, _("Could not reach GitHub to check for updates.")))
            continue
        if installed == latest:
            result.append(Check(name, OK, _("Up to date.")))
        else:
            result.append(Check(name, WARN, _("Update available."), refresh))
    return result


def check_extensions(online: bool) -> list[Check]:
    result = []
    wanted = list(extensions.EXTENSIONS) + [extensions.MENUBAR]
    remote_versions = _parallel(_remote_extension_version, list(extensions.EXTENSIONS)) if online else {}
    for uuid in wanted:
        name = extensions.EXTENSIONS.get(uuid, "Macify Menubar")
        if not (extensions.INSTALL_DIR / uuid).exists():
            result.append(Check(name, FAIL, _("Not installed."),
                                lambda log: (extensions.fetch(log), extensions.install(False, log),
                                             extensions.install_menubar(False, log))))
            continue
        state = _shell_state(uuid)
        if state in ("ERROR", "OUT OF DATE"):
            result.append(Check(name, FAIL, _("GNOME reports: {state}.").format(state=state)))
            continue
        if state != "ACTIVE":
            result.append(Check(name, WARN, _("Installed; it starts after you log in again.")))
            continue
        remote = remote_versions.get(uuid)
        local = _local_extension_version(uuid)
        if remote and local and remote > local:
            def update(log, uuid=uuid) -> None:
                extensions.zip_path(uuid).unlink(missing_ok=True)
                extensions.fetch(log)
                extensions.install(False, log)
            result.append(Check(name, WARN, _("Update available: version {local} → {remote}.").format(
                local=local, remote=remote), update))
        else:
            result.append(Check(name, OK, _("Running.")))
    return result


def check_settings() -> Check:
    choices = profile.load_choices()
    expected = profile.settings(choices)
    drifted: dict[str, dict[str, str]] = {}
    for schema, keys in expected.items():
        if not system.has_schema(schema):
            continue
        for key, value in keys.items():
            if system.has_key(schema, key) and not _same(system.read(schema, key), value):
                drifted.setdefault(schema, {})[key] = value
    if not drifted:
        return Check(_("Settings"), OK, _("Everything as Macify left it."))
    keys = sorted(f"{schema.split('.')[-1]}/{key}" for schema, values in drifted.items() for key in values)
    return Check(_("Settings"), WARN, _("Changed since install: {keys}").format(keys=", ".join(keys)),
                 lambda log: system.apply_settings(drifted, False, log))


def check_theme_css() -> Check:
    broken = themes.broken_css()
    if not broken:
        return Check(_("Theme styles"), OK, _("No style errors."))
    return Check(_("Theme styles"), WARN, _("{count} files with style errors from WhiteSur.").format(count=len(broken)),
                 lambda log: themes.repair_css(log))


def check_icons() -> Check:
    if not icons.THEME_DIR.exists():
        return Check(_("Icons"), FAIL, _("Macify icon theme missing."),
                     lambda log: (icons.ensure_theme(False, log), icons.generate(False, log)))
    missing = icons.audit()["missing_apps"]
    if not missing:
        return Check(_("Icons"), OK, _("No broken icons."))
    return Check(_("Icons"), WARN, ", ".join(missing),
                 lambda log: (icons.ensure_theme(False, log), icons.generate(False, log)))


def check_fonts() -> Check:
    result = subprocess.run(["fc-list", ":family=SF Pro Text"], capture_output=True, text=True)
    if result.stdout.strip():
        return Check(_("SF fonts"), OK, _("Installed."))
    return Check(_("SF fonts"), FAIL, _("Not found."), lambda log: fonts.install(False, log))


def check_upkeep() -> Check:
    active = subprocess.run(["systemctl", "--user", "is-active", session.PATH_UNIT],
                            capture_output=True, text=True).stdout.strip() == "active"
    if active and session.AUTOSTART.exists():
        return Check(_("Automatic upkeep"), OK, _("Watching for new apps."))
    return Check(_("Automatic upkeep"), WARN, _("Not running."), lambda log: session.install(False, log))


def check_boot() -> Check | None:
    if not load_config().get("system_screens"):
        return None
    from importlib import resources

    from . import boot

    result = subprocess.run(["update-alternatives", "--query", "default.plymouth"], capture_output=True, text=True)
    if "macify.plymouth" not in next((l for l in result.stdout.splitlines() if l.startswith("Value:")), ""):
        return Check(_("Startup screen"), WARN, _("Another boot screen is active."))
    installed = Path("/usr/share/plymouth/themes/macify")
    packaged = resources.files("macify").joinpath("data", "plymouth")
    outdated = any(not (installed / item.name).exists() or (installed / item.name).read_bytes() != item.read_bytes()
                   for item in packaged.iterdir())
    if not outdated:
        return Check(_("Startup screen"), OK, _("Macify boot screen active."))
    return Check(_("Startup screen"), WARN, _("Update available (asks for your password)."),
                 lambda log: boot.apply(profile.wallpaper_path(profile.load_choices()), False, log))


def run(online: bool = True) -> list[Check]:
    checks = [check_macify(online), check_tools(), *check_themes(online), check_theme_css(), *check_extensions(online), check_settings(),
              check_icons(), check_fonts(), check_upkeep()]
    boot = check_boot()
    if boot:
        checks.append(boot)
    return checks


def fix(checks: list[Check], log) -> int:
    """Aplica los arreglos disponibles. Devuelve cuántos se aplicaron."""
    fixed = 0
    with busy():
        for check in checks:
            if check.status != OK and check.fix:
                log(_("Fixing: {name}").format(name=check.name))
                check.fix(log)
                fixed += 1
        if fixed and icons.THEME_DIR.exists() and icons.mac_theme_ready():
            # Los temas pudieron cambiar: los iconos se rehacen con el set ya completo.
            icons.ensure_theme(False, log)
            icons.generate(False, log)
    return fixed


def notify_if_needed(checks: list[Check]) -> None:
    """Aviso de escritorio al iniciar sesión cuando hay algo que arreglar."""
    pending = [c for c in checks if c.status != OK and c.fix]
    if pending and shutil.which("notify-send"):
        subprocess.run(["notify-send", "--app-name=Macify", "--icon=dev.macify.Macify", "Macify",
                        _("{count} items need attention. Open Macify → Check for problems.").format(count=len(pending))],
                       check=False)
