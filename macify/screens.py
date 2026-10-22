"""Tamaño de las pantallas conectadas, para no cargar imágenes más grandes de lo que se ve."""

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

FALLBACK = (3840, 2160)


def largest() -> tuple[int, int]:
    """El modo actual más grande (en píxeles reales) de las pantallas encendidas."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig",
                              "org.gnome.Mutter.DisplayConfig", "GetCurrentState", None, None,
                              Gio.DBusCallFlags.NONE, 3000, None)
    except GLib.Error:
        return FALLBACK
    _serial, monitors, _logical, _props = reply.unpack()
    sizes = [(mode[1], mode[2]) for _info, modes, _props in monitors for mode in modes
             if mode[6].get("is-current")]
    return max(sizes, key=lambda s: s[0] * s[1]) if sizes else FALLBACK
