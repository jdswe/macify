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
             mock.patch.object(icons, "mac_theme_ready", return_value=False), \
             mock.patch.object(doctor, "run", side_effect=lambda online: calls.append(online) or []), \
             mock.patch.object(doctor, "notify_if_needed"):
            session.refresh(lambda _m: None, login=True)
        self.assertEqual(calls, [False])

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
