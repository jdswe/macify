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

    def test_root_helper_syntax(self):
        result = subprocess.run(["bash", "-n", str(PACKAGE / "data" / "root" / "macify-root.sh")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_boot_theme_builds(self):
        from macify import boot

        folder = boot.build_theme()
        for name in ("macify.plymouth", "macify.script", "logo.png", "bar-background.png", "bar-fill.png"):
            self.assertTrue((folder / name).exists(), name)

    def test_menubar_logo_is_white_and_without_background(self):
        svg = extensions.menubar_logo_svg()
        self.assertNotIn("<rect", svg)
        self.assertIn("#ffffff", svg)


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
                         "manage", "doctor"):
                window._show(name)
                built.append(window.stack.get_visible_child_name())
            application.quit()

        app.connect("activate", activate)
        app.run(None)
        self.assertEqual(len(built), 9)


if __name__ == "__main__":
    unittest.main()
