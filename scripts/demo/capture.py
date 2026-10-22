"""Captura las pantallas reales de Macify para el video."""
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from macify import doctor, gui, installer, updates

RELEASE = {"version": "0.7.1", "size": 300_000, "date": "2026-10-22",
           "notes": "- Startup bar fills in your PC's real boot time and ends with Welcome\n"
                    "- Shutdown bar empties with See you soon\n"
                    "- Software Update inside the app\n"
                    "- Website: icons for GitHub, Releases and License"}


def main():
    app = Adw.Application(application_id="dev.macify.Capture")
    shots = []

    def snap(window, name):
        w = window.get_child()
        paintable = Gtk.WidgetPaintable(widget=w)
        snapshot = Gtk.Snapshot()
        paintable.snapshot(snapshot, w.get_width(), w.get_height())
        texture = window.get_renderer().render_texture(snapshot.to_node(), None)
        texture.save_to_png(str(OUT / f"{name}.png"))
        print("shot", name)

    def activate(application):
        gui.install_style(Gdk.Display.get_default())
        window = gui.MacifyWindow(application)
        # Fondo original de Macify detrás de la ventana (no el de la persona).
        window.choices.wallpaper = str(Path(__file__).resolve().parents[2] / "macify" / "data" / "wallpapers" / "lilac.jpg")
        window._update_backdrop()
        window._fill_wallpapers()
        window.set_default_size(1120, 720)
        window.present()

        def progress_page(done_until):
            gui.clear(window.steps_box)
            steps = installer.steps(window.choices)
            window.step_rows = []
            for step in steps:
                status = window._status_widget()
                row = Adw.ActionRow(title=step.title)
                row.add_prefix(status)
                window.steps_box.append(row)
                window.step_rows.append(status)
            for i in range(done_until):
                window.step_rows[i].set_visible_child_name("done")
            if done_until < len(steps):
                window._mark(done_until, len(steps), steps[done_until], "running")
            window.progress.set_fraction(done_until / len(steps))
            window._show("progress")

        def update_downloading():
            window._show_update(RELEASE, None)
            window.update_button.set_visible(False)
            window.update_bar.set_visible(True)
            window.update_bar.set_fraction(0.62)
            window.update_title.set_label("Downloading Macify 0.7.1…")
            window.update_detail.set_label("Downloading macify_0.7.1_all.deb from GitHub")
            window._show("update")

        def update_installed():
            window.release = RELEASE
            window._update_done(None)

        def doctor_page():
            window._show_checks(doctor.run(online=False))
            window._show("doctor")

        def manage_with_update():
            window._mark_update_tile(RELEASE)
            window._show("manage")

        only = os.environ.get("ONLY")
        plan_all = [
            ("01-welcome", lambda: window._show("welcome")),
            ("02-appearance", lambda: window._show("appearance")),
            ("03-wallpaper", lambda: window._show("wallpaper")),
            ("04-dock", lambda: window._show("dock")),
            ("05-summary", lambda: window._show("summary")),
            ("06-progress-a", lambda: progress_page(3)),
            ("07-progress-b", lambda: progress_page(8)),
            ("08-done", lambda: window._show("done")),
            ("09-manage", manage_with_update),
            ("10-update-available", lambda: (window._show_update(RELEASE, None), window._show("update"))),
            ("11-update-downloading", update_downloading),
            ("12-update-installed", update_installed),
            ("13-doctor", doctor_page),
        ]
        plan = [p for p in plan_all if not only or p[0] == only]

        def run(index=0):
            if index >= len(plan):
                application.quit()
                return False
            name, action = plan[index]
            action()
            GLib.timeout_add(900, lambda: (snap(window, name), run(index + 1))[1] or False)
            return False

        GLib.timeout_add(1200, run)

    app.connect("activate", activate)
    with mock.patch.object(updates, "latest", return_value=None):
        app.run(None)


main()
