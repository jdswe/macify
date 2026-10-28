// Ninguna ventana se queda debajo de la barra de menús: si una ventana crece (o cambia de
// pantalla, o la app la coloca por su cuenta) y su borde de arriba queda bajo la barra, se
// baja hasta el área de trabajo. No toca las que se arrastran, las de pantalla completa ni
// las que no son ventanas normales.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const SETTLE_MS = 150;       // espera a que la app termine de cambiar de tamaño

export class WindowGuard {
    constructor() {
        this._timers = new Map();
        for (const actor of global.get_window_actors())
            this._watch(actor.meta_window);
        global.display.connectObject('window-created', (_display, win) => this._watch(win), this);
    }

    _watch(win) {
        if (win.window_type !== Meta.WindowType.NORMAL)
            return;
        win.connectObject(
            'size-changed', () => this._later(win),
            'position-changed', () => this._later(win),
            'notify::maximized-vertically', () => this._later(win),
            'unmanaged', () => this._forget(win), this);
    }

    _later(win) {
        if (this._timers.has(win))
            return;
        this._timers.set(win, GLib.timeout_add(GLib.PRIORITY_DEFAULT, SETTLE_MS, () => {
            this._timers.delete(win);
            this._fit(win);
            return GLib.SOURCE_REMOVE;
        }));
    }

    _forget(win) {
        const id = this._timers.get(win);
        if (id)
            GLib.source_remove(id);
        this._timers.delete(win);
    }

    _fit(win) {
        if (win.is_fullscreen())
            return;
        // Con el botón del ratón pulsado se arrastra o se redimensiona: se espera a que suelte.
        if (global.get_pointer()[2] & Clutter.ModifierType.BUTTON1_MASK) {
            this._later(win);
            return;
        }
        const monitor = win.get_monitor();
        if (monitor < 0)
            return;
        const area = Main.layoutManager.getWorkAreaForMonitor(monitor);
        const frame = win.get_frame_rect();
        if (frame.y >= area.y || frame.y + frame.height <= area.y)
            return;                          // bien colocada, o fuera de esta pantalla
        const height = Math.min(frame.height, area.height);
        win.move_resize_frame(false, frame.x, area.y, frame.width, height);
    }

    destroy() {
        global.display.disconnectObject(this);
        for (const actor of global.get_window_actors())
            actor.meta_window.disconnectObject(this);
        for (const id of this._timers.values())
            GLib.source_remove(id);
        this._timers.clear();
    }
}
