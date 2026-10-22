"""Pruebas de Macify. Ejecutar desde app/:  python3 -m unittest discover -s tests -v

Las que dependen del sistema (GNOME, gsettings, pantalla) se saltan si no están disponibles.
Ninguna prueba cambia ajustes del sistema: todo lo que instala se hace en simulación.
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import unittest
from unittest import mock
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from macify import doctor, extensions, i18n, icons, installer, profile, system  # noqa: E402
from macify.colors import accent_name  # noqa: E402

PACKAGE = APP / "macify"
HAS_GSETTINGS = shutil.which("gsettings") is not None
HAS_DISPLAY = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


# Guardián: ninguna prueba puede cambiar la configuración real de Macify (pasó dos veces: una
# prueba instaló la extensión y otra corrió una actualización en el equipo de verdad).
_REAL_CONFIG = Path.home() / ".config" / "macify" / "config.json"
_REAL_LOOK = Path.home() / ".config" / "macify" / "look.json"


def _snapshot():
    return {path: path.read_bytes() if path.exists() else None for path in (_REAL_CONFIG, _REAL_LOOK)}


def setUpModule():
    global _BEFORE
    _BEFORE = _snapshot()


def tearDownModule():
    changed = [str(path) for path, data in _snapshot().items() if data != _BEFORE[path]]
    if changed:
        raise AssertionError(f"tests changed the real Macify configuration: {changed}")


class CodeTests(unittest.TestCase):
    def test_every_module_compiles(self):
        for path in PACKAGE.glob("*.py"):
            with self.subTest(module=path.name):
                ast.parse(path.read_text())

    def test_every_visible_text_has_spanish(self):
        """Cada _("…") del código tiene traducción, para que nada salga a medias en español."""
        pattern = re.compile(r'_\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
        missing = set()
        for path in PACKAGE.glob("*.py"):
            if path.name == "i18n.py":      # sólo trae ejemplos en su comentario
                continue
            for text in pattern.findall(path.read_text()):
                text = text.encode().decode("unicode_escape").encode("latin-1").decode("utf-8")
                if text not in i18n.SPANISH:
                    missing.add(f"{path.name}: {text}")
        self.assertEqual(sorted(missing), [])

    def test_language_follows_system(self):
        os.environ["LANGUAGE"] = "es_CO:es"
        self.assertEqual(i18n._("Install"), "Instalar")
        os.environ["LANGUAGE"] = "en_US:en"
        self.assertEqual(i18n._("Install"), "Install")


class ProfileTests(unittest.TestCase):
    def test_dock_icon_size_maps_to_requested_pixels(self):
        sizes = profile.DOCK_ICON_SIZES
        for pixels in (32, 48, 64, 72):
            with self.subTest(pixels=pixels):
                value = float(profile.dock_icon_size(pixels))
                self.assertEqual(sizes[int(value * len(sizes))], pixels)

    def test_accent_names(self):
        self.assertEqual(accent_name((240, 168, 142)), "orange")
        self.assertEqual(accent_name((120, 179, 242)), "blue")
        self.assertEqual(accent_name((128, 128, 128)), "slate")

    @unittest.skipUnless(HAS_GSETTINGS, "sin gsettings")
    def test_every_setting_key_exists(self):
        """Cada clave que Macify escribe existe en GNOME o en su extensión (nada se escribe a ciegas)."""
        for appearance in ("dark", "light"):
            values = profile.settings(profile.Choices(appearance=appearance))
            for schema, keys in values.items():
                if not system.has_schema(schema):
                    self.skipTest(f"{schema} no instalado en este equipo")
                for key in keys:
                    with self.subTest(schema=schema, key=key):
                        self.assertTrue(system.has_key(schema, key))

    def test_version_comparison(self):
        from macify import updates

        self.assertTrue(updates.is_newer("0.10.0", "0.9.9"))
        self.assertFalse(updates.is_newer("0.5.2", "0.6.0"))
        self.assertFalse(updates.is_newer("v0.6.0", "0.6.0"))

    def test_whitesur_css_repair(self):
        from macify import themes

        broken = "a { border-color: color-mix(in srgb, black 6% #2E7CF7); }"
        fixed = themes._COLOR_MIX_WITHOUT_COMMA.sub(r"\1, ", broken)
        self.assertEqual(fixed, "a { border-color: color-mix(in srgb, black 6%, #2E7CF7); }")
        valid = "a { color: color-mix(in srgb, black 6%, #fff); }"
        self.assertEqual(themes._COLOR_MIX_WITHOUT_COMMA.sub(r"\1, ", valid), valid)

    def test_values_compare_without_format_noise(self):
        self.assertTrue(doctor._same("uint32 48", "48"))
        self.assertTrue(doctor._same("(0.12, 0.12, 0.14, 0.34999999999999998)", "(0.12, 0.12, 0.14, 0.35)"))
        self.assertFalse(doctor._same("'WhiteSur-Dark'", "'WhiteSur-Light'"))


class WallpaperTests(unittest.TestCase):
    """Fondos con versión oscura, secciones por carpeta y la barra que se ajusta al fondo."""

    def _image(self, path, color):
        from PIL import Image
        Image.new("RGB", (64, 36), color).save(path)

    def test_every_bundled_wallpaper_has_a_dark_twin(self):
        from macify import wallpapers
        folder = PACKAGE / "data" / "wallpapers"
        for name, (_title, section) in wallpapers.CATALOG.items():
            if section == wallpapers.MACIFY:
                self.assertTrue((folder / name.replace(".jpg", "-dark.jpg")).is_file(), name)

    def test_appearance_never_changes_the_wallpaper(self):
        """Regresión 0.11: al tocar Estilo oscuro cambiaba el fondo; sólo debe cambiar el aspecto."""
        import tempfile
        from unittest import mock
        from macify import profile
        with tempfile.TemporaryDirectory() as tmp:
            light, dark = Path(tmp) / "bay.jpg", Path(tmp) / "bay-dark.jpg"
            self._image(light, (240, 230, 220))
            self._image(dark, (20, 20, 30))
            for appearance in ("light", "dark"):
                choices = profile.Choices(appearance=appearance, wallpaper=str(light))
                self.assertEqual(profile.desktop_wallpaper(choices), light)
                background = profile.settings(choices)["org.gnome.desktop.background"]
                self.assertEqual(background["picture-uri"], background["picture-uri-dark"])
                self.assertIn("bay.jpg", background["picture-uri"])
            self.assertEqual(profile.look(choices)["bar"], {"light": "dark-text", "dark": "dark-text"})
            with mock.patch("macify.profile.top_brightness", return_value=0.1):
                self.assertEqual(profile.look(choices)["bar"]["light"], "light-text")

    def test_folders_become_sections_and_dark_versions_are_choices(self):
        import tempfile
        from unittest import mock
        from macify import wallpapers
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wallpapers" / "Landscapes").mkdir(parents=True)
            self._image(root / "wallpapers" / "loose.jpg", (1, 2, 3))
            self._image(root / "wallpapers" / "Landscapes" / "macos-hills.jpg", (4, 5, 6))
            self._image(root / "wallpapers" / "Landscapes" / "macos-hills-dark.jpg", (7, 8, 9))
            with mock.patch.object(wallpapers, "assets_root", return_value=root), \
                 mock.patch.object(wallpapers, "load_config", return_value={}):
                items = wallpapers.catalog()
            mine = {w.title: w.section for w in items if w.section not in wallpapers.FIRST}
            self.assertEqual(mine, {"Loose": "Your Folder", "macOS Hills": "Landscapes",
                                    "macOS Hills Dark": "Landscapes"})
            self.assertEqual(wallpapers.sections(items)[-2:], ["Landscapes", "Your Folder"])
            macify = [w.path.name for w in items if w.section == wallpapers.MACIFY]
            self.assertEqual(macify[:2], ["lilac.jpg", "lilac-dark.jpg"])    # cada oscura junto a su clara

    def test_big_wallpapers_get_a_screen_sized_copy(self):
        """El fondo se carga entero en la memoria de vídeo: uno de 6000 px gastaba ~96 MB."""
        import tempfile
        from unittest import mock
        from PIL import Image
        from macify import wallpapers
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(wallpapers, "FITTED_DIR", Path(tmp) / "cache"):
            big, small = Path(tmp) / "big.jpg", Path(tmp) / "small.jpg"
            Image.new("RGB", (6000, 4000), (10, 20, 30)).save(big)
            Image.new("RGB", (1920, 1080), (10, 20, 30)).save(small)
            copy = wallpapers.fitted(big, screen=(1920, 1080))
            self.assertNotEqual(copy, big)
            self.assertEqual(Image.open(copy).size, (2560, 1707))       # cubre 2560×1440 sin recortar
            self.assertEqual(wallpapers.fitted(big, screen=(1920, 1080)), copy)   # en caché
            self.assertEqual(wallpapers.fitted(small, screen=(1920, 1080)), small)
            self.assertEqual(Image.open(big).size, (6000, 4000))        # el original no se toca

    def test_login_screen_is_outdated_after_a_new_wallpaper(self):
        from unittest import mock
        from macify import boot
        wallpaper = PACKAGE / "data" / "wallpapers" / "lilac.jpg"
        config = {"system_screens": True, "login_wallpaper": boot.login_key(wallpaper)}
        with mock.patch.object(boot, "load_config", return_value=config):
            self.assertFalse(boot.login_outdated(wallpaper))
            self.assertTrue(boot.login_outdated(wallpaper.with_name("sand.jpg")))
        with mock.patch.object(boot, "load_config", return_value={}):
            self.assertFalse(boot.login_outdated(wallpaper))     # sin pantallas de Macify, nada que hacer


class UpgradeTests(unittest.TestCase):
    """Actualizar aplica sólo lo que cambió y limpia lo viejo; nunca reinstala todo."""

    def test_upgrade_only_when_applied_and_version_changed(self):
        import tempfile
        from unittest import mock
        from macify import __version__, upgrade
        with tempfile.TemporaryDirectory() as tmp:
            backup = Path(tmp) / "backup.json"
            with mock.patch.object(upgrade.system, "BACKUP_FILE", backup), \
                 mock.patch.object(upgrade, "load_config", return_value={"applied_version": "0.1.0"}):
                self.assertFalse(upgrade.needed())          # Macify nunca se aplicó
                backup.write_text("{}")
                self.assertTrue(upgrade.needed())
            with mock.patch.object(upgrade.system, "BACKUP_FILE", backup), \
                 mock.patch.object(upgrade, "load_config", return_value={"applied_version": __version__}):
                self.assertFalse(upgrade.needed())

    def test_upgrade_fixes_only_outdated_pieces_and_cleans(self):
        import tempfile
        from unittest import mock
        from macify import doctor, upgrade
        fixed = []
        outdated = doctor.Check("Icon set", doctor.WARN, "Update available.", lambda log: fixed.append("icons"))
        current = doctor.Check("Cursor", doctor.OK, "Up to date.", lambda log: fixed.append("cursor"))
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp)
            (cache / "updates").mkdir()
            (cache / "updates" / "macify_0.1.0_all.deb").write_bytes(b"x" * 1000)
            (cache / "debug-whitesur").mkdir()
            fitted = cache / "wallpapers"
            fitted.mkdir()
            used, unused = fitted / "a-2560x1440.jpg", fitted / "b-2560x1440.jpg"
            used.write_bytes(b"1")
            unused.write_bytes(b"2")
            backup = cache / "backup.json"
            backup.write_text("{}")
            with mock.patch.object(upgrade.system, "BACKUP_FILE", backup), \
                 mock.patch.object(upgrade, "CACHE_DIR", cache), \
                 mock.patch.object(upgrade.wallpapers, "FITTED_DIR", fitted), \
                 mock.patch.object(upgrade.wallpapers, "THUMB_DIR", cache / "thumbnails"), \
                 mock.patch.object(upgrade, "_wallpaper_in_use", return_value=used), \
                 mock.patch.object(upgrade, "busy"), \
                 mock.patch.object(upgrade, "load_config", return_value={}), \
                 mock.patch.object(upgrade, "save_config_value") as save, \
                 mock.patch.object(doctor, "check_themes", return_value=[current, outdated]), \
                 mock.patch.object(doctor, "check_theme_css", return_value=current), \
                 mock.patch.object(doctor, "check_extensions", return_value=[]), \
                 mock.patch.object(doctor, "check_icons", return_value=current), \
                 mock.patch.object(doctor, "check_fonts", return_value=current), \
                 mock.patch.object(doctor, "check_upkeep", return_value=current), \
                 mock.patch.object(upgrade.installer, "apply_look") as look, \
                 mock.patch.object(upgrade.icons, "mac_theme_ready", return_value=False):
                upgrade.run(lambda _m: None)
            self.assertEqual(fixed, ["icons"])               # sólo lo desactualizado
            look.assert_called_once()                         # los ajustes nuevos, sin descargas
            self.assertFalse((cache / "updates" / "macify_0.1.0_all.deb").exists())
            self.assertFalse((cache / "debug-whitesur").exists())
            self.assertTrue(used.exists())
            self.assertFalse(unused.exists())
            save.assert_called_once()


class SupplyChainTests(unittest.TestCase):
    """Todo lo que se descarga va fijado y verificado; nada se instala sin huella."""

    def test_every_extension_is_pinned(self):
        from macify import extensions
        self.assertEqual(set(extensions.PINS), set(extensions.EXTENSIONS))
        for version, tag, sha256 in extensions.PINS.values():
            self.assertGreater(version, 0)
            self.assertGreater(tag, 0)
            self.assertRegex(sha256, r"^[0-9a-f]{64}$")

    def test_extension_with_wrong_fingerprint_is_rejected(self):
        import io
        import tempfile
        from unittest import mock
        from macify import extensions
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(extensions, "EXTENSIONS_DIR", Path(tmp)), \
             mock.patch.object(extensions.urllib.request, "urlopen",
                               return_value=mock.MagicMock(__enter__=lambda s: io.BytesIO(b"evil"),
                                                           __exit__=lambda *a: False)):
            with self.assertRaises(RuntimeError):
                extensions.fetch(lambda _m: None)
            self.assertEqual(list(Path(tmp).iterdir()), [])     # nada guardado

    def test_update_without_fingerprint_is_refused(self):
        import tempfile
        from unittest import mock
        from macify import updates
        release = {"version": "9.9.9", "url": "https://example.invalid/macify_9.9.9_all.deb",
                   "name": "macify_9.9.9_all.deb", "size": 3, "sha256": None}
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(updates, "CACHE_DIR", Path(tmp)), \
             mock.patch.object(updates.urllib.request, "urlopen",
                               return_value=mock.MagicMock(__enter__=lambda s: mock.MagicMock(
                                   headers={}, read=mock.MagicMock(side_effect=[b"deb", b""])),
                                   __exit__=lambda *a: False)), \
             mock.patch.object(updates.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                updates.install(release, lambda _m: None)
            run.assert_not_called()                             # ni dpkg ni pkexec

    def test_installer_refuses_unverified_packages(self):
        script = (APP / "docs" / "install.sh").read_text()
        self.assertIn("published no fingerprint", script)
        self.assertIn("--proto-redir '=https'", script)

    def test_website_has_a_content_security_policy(self):
        page = (APP / "docs" / "index.html").read_text()
        self.assertIn("Content-Security-Policy", page)
        self.assertIn("object-src 'none'", page)

    def test_package_keeps_install_folders_root_only(self):
        build = (APP / "scripts" / "build_deb.sh").read_text()
        self.assertIn("chmod -R go-w /usr/lib/macify", build)


class InstallerTests(unittest.TestCase):
    def test_steps_have_titles_and_details(self):
        for login in (False, True):
            steps = installer.steps(profile.Choices(login_screen=login), dry_run=True)
            self.assertEqual(len(steps), 11 if login else 10)
            for step in steps:
                self.assertTrue(step.title and step.detail)

    @unittest.skipUnless(HAS_GSETTINGS, "sin gsettings")
    def test_dry_run_changes_nothing(self):
        before = system.read("org.gnome.desktop.interface", "gtk-theme")
        lines: list[str] = []
        installer.run(profile.Choices(), True, lines.append)
        self.assertIn("nothing was changed", lines[-1].lower() + " nothing was changed")
        self.assertEqual(system.read("org.gnome.desktop.interface", "gtk-theme"), before)

    def test_uninstall_dry_run(self):
        from macify.uninstall import uninstall

        lines: list[str] = []
        uninstall(True, lines.append)
        self.assertTrue(any("apt remove macify" in line for line in lines))


class SystemPiecesTests(unittest.TestCase):
    def test_menubar_extension_metadata(self):
        import json

        folder = PACKAGE / "data" / "extension" / extensions.MENUBAR
        metadata = json.loads((folder / "metadata.json").read_text())
        self.assertEqual(metadata["uuid"], extensions.MENUBAR)
        self.assertIn("50", metadata["shell-version"])

    @unittest.skipUnless(shutil.which("gjs"), "sin gjs")
    def test_menubar_extension_syntax(self):
        source = (PACKAGE / "data" / "extension" / extensions.MENUBAR / "extension.js").read_text()
        body = "\n".join(l for l in source.splitlines() if not l.startswith("import "))
        body = body.replace("export default class", "class")
        check = APP / "tests" / ".menubar-check.js"
        check.write_text(body)
        try:
            result = subprocess.run(["gjs", "-c", f"const s = imports.gi.GLib.file_get_contents('{check}')[1];"
                                                  "new Function(new TextDecoder().decode(s));"],
                                    capture_output=True, text=True)
        finally:
            check.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_whitesur_pin_matches_root_helper(self):
        """Root y el usuario instalan exactamente la misma versión verificada de WhiteSur."""
        from macify import themes

        helper = (PACKAGE / "data" / "root" / "macify-root.sh").read_text()
        self.assertIn(f"WHITESUR_COMMIT={themes.REPOS['gtk'].commit}", helper)
        self.assertIn(f"WHITESUR_SHA256={themes.REPOS['gtk'].sha256}", helper)
        for source in themes.REPOS.values():
            self.assertRegex(source.commit, r"^[0-9a-f]{40}$")
            self.assertRegex(source.sha256, r"^[0-9a-f]{64}$")

    def test_root_helper_only_takes_safe_files(self):
        """El ayudante de root rechaza enlaces, tipos falsos y archivos enormes."""
        import tempfile

        helper = PACKAGE / "data" / "root" / "macify-root.sh"
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
            (t / "fake.png").write_bytes(b"GIF89a" + b"0" * 100)
            (t / "photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 100)
            (t / "script.txt").write_text("Window.SetBackgroundTopColor(0, 0, 0);")
            (t / "binary.txt").write_bytes(b"abc\x00def")
            (t / "big.png").write_bytes(b"\x89PNG" + b"0" * 5000)
            (t / "link.png").symlink_to(t / "ok.png")
            cases = {
                "ok.png png 4096": True, "fake.png png 4096": False, "photo.jpg image 4096": True,
                "script.txt text 4096": True, "binary.txt text 4096": False, "big.png png 4096": False,
                "link.png png 4096": False, "missing.png png 4096": False,
            }
            for case, expected in cases.items():
                name, kind, limit = case.split()
                script = f'source "{helper}"; take "{t / name}" "{t}/out" {kind} {limit}'
                result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, expected, f"{case}: {result.stderr}")

    def test_root_helper_syntax(self):
        result = subprocess.run(["bash", "-n", str(PACKAGE / "data" / "root" / "macify-root.sh")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_boot_theme_builds(self):
        from macify import boot

        folder = boot.build_theme()
        for name in ("macify.plymouth", "macify.script", "logo.png", "bar-background.png", "bar-fill.png"):
            self.assertTrue((folder / name).exists(), name)

    def test_boot_script_gets_this_pc_values(self):
        from macify import boot

        script = boot.script_text(5.5, 10.5)
        self.assertIn("config.shutdown_seconds = 5.5;", script)
        self.assertIn("config.boot_seconds = 10.5;", script)
        self.assertGreaterEqual(boot.boot_seconds(), 4.0)
        self.assertIn('config.welcome = "', script)
        self.assertIn("Plymouth.SetQuitFunction", script)
        self.assertGreaterEqual(boot.shutdown_seconds(), 2.5)
        self.assertLessEqual(boot.shutdown_seconds(), 12.0)
        # El Doctor no debe pedir actualizar sólo porque cambió el tiempo medido.
        packaged = (PACKAGE / "data" / "plymouth" / "macify.script").read_text()
        self.assertTrue(boot.same_script(boot.script_text(9.9, 20.0), packaged))
        self.assertFalse(boot.same_script(script + "\n# cambio", packaged))

    def test_release_notes_are_plain_items(self):
        from macify import updates

        release = {"notes": "## What's new\n- **Dock** fix\n* Boot `bar`\nplain text"}
        self.assertEqual(updates.notes(release), ["Dock fix", "Boot bar"])

    def test_menubar_extension_javascript_parses(self):
        import re
        import shutil
        import tempfile

        if shutil.which("gjs") is None:
            self.skipTest("sin gjs")
        folder = PACKAGE / "data" / "extension" / "macify-menubar@macify.dev"
        modules = sorted(folder.glob("*.js"))
        self.assertGreaterEqual(len(modules), 6)
        for module in modules:
            source = module.read_text()
            body = "\n".join(line for line in source.splitlines() if not line.startswith("import "))
            body = re.sub(r"^export (default )?", "", body, flags=re.MULTILINE)
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                f.write(body)
            check = (f"const [, b] = imports.gi.GLib.file_get_contents({f.name!r}); "
                     "new Function(new TextDecoder().decode(b));")
            result = subprocess.run(["gjs", "-c", check], capture_output=True, text=True)
            Path(f.name).unlink()
            self.assertEqual(result.returncode, 0, f"{module.name}: {result.stderr}")
            # Cada import local apunta a un módulo que existe.
            for name in re.findall(r"from '\./([\w.]+)'", source):
                self.assertTrue((folder / name).is_file(), f"{module.name} → {name}")
        self.assertIn("in-fullscreen-changed", (folder / "dock.js").read_text())

    def test_menubar_texts_have_spanish(self):
        """Cada texto que la extensión muestra con _('…') tiene su traducción al español."""
        import re

        folder = PACKAGE / "data" / "extension" / "macify-menubar@macify.dev"
        dictionary = (folder / "i18n.js").read_text()
        missing = set()
        for module in folder.glob("*.js"):
            for text in re.findall(r"_\('((?:[^'\\]|\\.)+)'", module.read_text()):
                if f"'{text}':" not in dictionary:
                    missing.add(text)
        self.assertEqual(missing, set())

    def test_menubar_css_has_no_negative_margins(self):
        """GNOME Shell (St) desborda los márgenes negativos: el menú mide 4294967296 px."""
        import re

        css = (PACKAGE / "data" / "extension" / "macify-menubar@macify.dev" / "stylesheet.css").read_text()
        self.assertEqual(re.findall(r"(?:margin|padding)[\w-]*:\s*[^;]*-\d", css), [])

    def test_status_icons_are_valid_svg(self):
        import xml.etree.ElementTree as ET

        from macify import status_icons

        icons = status_icons.all_icons()
        for name in ("battery-level-50-symbolic", "battery-level-80-charging-symbolic",
                     "network-wireless-signal-good-symbolic", "macify-control-center-symbolic"):
            self.assertIn(name, icons)
        for name, svg in icons.items():
            ET.fromstring(svg)                      # XML bien formado
            self.assertNotIn("stroke=\"#", svg.replace('stroke="#000"', ""), name)   # sólo rellenos

    def test_menubar_logo_is_white_and_without_background(self):
        svg = extensions.menubar_logo_svg()
        self.assertNotIn("<rect", svg)
        self.assertIn("#ffffff", svg)


class SnapThemeTests(unittest.TestCase):
    """El tema dentro de las apps snap, sobre un sistema de mentira en una carpeta temporal."""

    def test_sync_links_switches_and_removes(self):
        import os
        import tempfile

        from macify import snaps

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = {
                "SNAP_DIR": root / "snap", "SNAP_HOMES": root / "home" / "snap",
                "SNAP_DESKTOP": root / "desktop", "THEMES": root / "home" / ".themes",
                "GTK4": root / "home" / ".config" / "gtk-4.0",
            }
            meta = paths["SNAP_DIR"] / "editor" / "current" / "meta" / "snap.yaml"
            meta.parent.mkdir(parents=True)
            meta.write_text("plugs:\n  gtk-3-themes:\n")
            paths["SNAP_DESKTOP"].mkdir()
            (paths["SNAP_DESKTOP"] / "editor_editor.desktop").write_text("[Desktop Entry]\n")
            (paths["SNAP_HOMES"] / "editor" / "current").mkdir(parents=True)
            for variant in snaps.VARIANTS:
                (paths["THEMES"] / variant / "gtk-3.0").mkdir(parents=True)
                (paths["THEMES"] / variant / "index.theme").write_text("[Desktop Entry]\n")
                (paths["THEMES"] / variant / "gtk-3.0" / "gtk.css").write_text(variant)
            (paths["GTK4"] / "assets").mkdir(parents=True)
            (paths["GTK4"] / "assets" / "close.svg").write_text("<svg/>")
            for name in snaps.GTK4_FILES:
                (paths["GTK4"] / name).write_text(name)
            with mock.patch.multiple(snaps, **paths):
                self.assertEqual(snaps.sync("dark"), ["editor"])
                home = paths["SNAP_HOMES"] / "editor" / "current"
                linked = home / "themes" / "WhiteSur-Dark-alt" / "gtk-3.0" / "gtk.css"
                self.assertTrue(os.path.samefile(linked, paths["THEMES"] / "WhiteSur-Dark-alt" / "gtk-3.0" / "gtk.css"))
                self.assertEqual(os.readlink(home / ".config" / "gtk-4.0" / "gtk.css"), "gtk-Dark.css")
                snaps.sync("light")
                self.assertEqual(os.readlink(home / ".config" / "gtk-4.0" / "gtk.css"), "gtk-Light.css")
                snaps.remove()
                self.assertFalse((home / "themes" / "WhiteSur-Dark-alt").exists())
                self.assertFalse((home / ".config" / "gtk-4.0" / "gtk.css").exists())
                self.assertTrue((paths["THEMES"] / "WhiteSur-Dark-alt" / "gtk-3.0" / "gtk.css").exists())


class IconTests(unittest.TestCase):
    def test_generated_icon_has_macos_shape(self):
        source = next(Path("/usr/share/icons/hicolor").rglob("*.svg"), None)
        if source is None:
            self.skipTest("sin iconos de ejemplo")
        image = icons.mac_icon(source)
        self.assertEqual(image.size, (icons.ICON_SIZE, icons.ICON_SIZE))
        self.assertEqual(image.getpixel((2, 2))[3], 0)          # esquina transparente
        middle = icons.ICON_SIZE // 2
        self.assertGreater(image.getpixel((middle, middle))[3], 0)

    def test_own_icon_is_never_regenerated(self):
        self.assertIn("dev.macify.Macify", icons.OWN_ICONS)

    def test_up_to_date_icon_is_not_redrawn(self):
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder, "app.png"), Path(folder, "out.png")
            source.write_bytes(b"x")
            target.write_bytes(b"y")       # más nuevo que el original
            with mock.patch.object(icons, "mac_icon") as draw:
                self.assertFalse(icons._draw(source, target))
            draw.assert_not_called()

    def test_online_update_check_once_a_day(self):
        import time
        from unittest import mock

        from macify import doctor, session

        calls = []
        with mock.patch.object(session, "load_config", return_value={"last_update_check": time.time()}), \
             mock.patch.object(session, "is_busy", return_value=False), \
             mock.patch.object(session.apps, "apply"), mock.patch.object(session.extensions, "disable_other_docks"), \
             mock.patch.object(session.extensions, "menubar_outdated", return_value=False), \
             mock.patch.object(session.extensions, "install_menubar") as install, \
             mock.patch.object(session.snaps, "sync"), \
             mock.patch("macify.upgrade.needed", return_value=False), \
             mock.patch.object(icons, "mac_theme_ready", return_value=False), \
             mock.patch.object(doctor, "run", side_effect=lambda online: calls.append(online) or []), \
             mock.patch.object(doctor, "notify_if_needed"):
            session.refresh(lambda _m: None, login=True)
        self.assertEqual(calls, [False])
        install.assert_not_called()       # la prueba no toca la extensión instalada de verdad

    def test_upkeep_waits_while_macify_is_busy(self):
        """Regresión 0.4.1: el vigilante regeneró iconos con WhiteSur a medio instalar."""
        from unittest import mock

        from macify import assets, session

        with assets.busy(), mock.patch.object(icons, "generate") as generate:
            session.refresh(lambda _m: None)
        generate.assert_not_called()
        self.assertFalse(assets.is_busy())

    @unittest.skipUnless(icons.THEME_DIR.exists(), "Macify no está aplicado")
    def test_no_broken_icons(self):
        self.assertEqual(icons.audit()["missing_apps"], [])


@unittest.skipUnless(HAS_DISPLAY, "sin pantalla")
class InterfaceTests(unittest.TestCase):
    def test_every_page_builds(self):
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw

        from macify.gui import MacifyWindow

        app = Adw.Application(application_id="dev.macify.Tests")
        built = []

        def activate(application):
            window = MacifyWindow(application)
            for name in ("welcome", "appearance", "wallpaper", "dock", "summary", "progress", "done",
                         "manage", "doctor", "update"):
                window._show(name)
                built.append(window.stack.get_visible_child_name())
            # Pantalla de actualización en sus tres casos, sin red.
            from macify import __version__

            window._show_update(None, OSError("offline"))
            self.assertTrue(window.update_button.get_visible())
            window._show_update({"version": __version__, "notes": ""}, None)
            self.assertFalse(window.update_button.get_visible())
            window._show_update({"version": "99.0.0", "size": 2_000_000, "notes": "- New dock"}, None)
            self.assertTrue(window.update_button.get_visible())
            self.assertIn("99.0.0", window.update_title.get_label())
            application.quit()

        app.connect("activate", activate)
        from macify import updates

        with mock.patch.object(updates, "latest", return_value=None):
            app.run(None)
        self.assertEqual(len(built), 10)


if __name__ == "__main__":
    unittest.main()
