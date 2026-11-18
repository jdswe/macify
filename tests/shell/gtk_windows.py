"""Ventanas GTK 4 para la prueba del Shell aislado: un diálogo de archivos sin libadwaita (como
el de un navegador), uno con libadwaita (como el del portal de GNOME) y una ventana simple sin
libadwaita (como el aviso «Refreshing Apps» de snapd). Se quedan abiertas hasta que las cierra
la prueba. Uso: gtk_windows.py plain|chooser|adw"""

import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

kind = sys.argv[1]
if kind == "adw":
    gi.require_version("Adw", "1")
    from gi.repository import Adw  # noqa: E402
    app = Adw.Application(application_id="dev.macify.TestAdw")
else:
    app = Gtk.Application(application_id=f"dev.macify.Test{kind.title()}")


def activate(application):
    if kind == "plain":
        window = Gtk.ApplicationWindow(application=application, title="Refreshing Apps")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_top=24, margin_bottom=24,
                      margin_start=24, margin_end=24)
        box.append(Gtk.Label(label="Updating Visual Studio Code to the latest version."))
        bar = Gtk.ProgressBar(fraction=0.6)
        box.append(bar)
        box.append(Gtk.Button(label="Hide", halign=Gtk.Align.END))
        window.set_child(box)
        window.set_default_size(560, 180)
    else:
        window = Gtk.FileChooserDialog(title="example.org wants to open", action=Gtk.FileChooserAction.OPEN)
        window.add_button("Cancel", Gtk.ResponseType.CANCEL)
        window.add_button("Open", Gtk.ResponseType.ACCEPT)
        window.set_application(application)
        window.set_default_size(800, 480)
    window.present()


app.connect("activate", activate)
app.run([])
