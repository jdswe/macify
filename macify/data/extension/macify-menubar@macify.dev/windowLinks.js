// Every window shows its app's icon in the dock. GNOME links a window to its launcher only
// when the window's class matches the launcher exactly; many apps ship a launcher that does
// not (Kilo: StartupWMClass=Kilo, window class "kilo"), and their windows get a generic icon.
// When a window ends up without an app, Macify ("macify link-window") looks for its launcher
// and writes a copy with the right class; once GNOME reloads the launchers, the window that is
// already open is linked again, so the right icon appears without reopening the app.

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';

// Fixed path (not looked up in PATH): only the Macify installed by the package, owned by root.
const MACIFY = '/usr/bin/macify';
const SETTLE_MS = 1500;     // apps (Electron) set their class a moment after the window appears

export class WindowLinks {
    constructor() {
        this._tracker = Shell.WindowTracker.get_default();
        this._tried = new Set();
        this._timers = new Map();
        for (const actor of global.get_window_actors())
            this._watch(actor.meta_window);
        global.display.connectObject('window-created', (_display, win) => this._watch(win), this);
        Shell.AppSystem.get_default().connectObject('installed-changed', () => this._relink(), this);
    }

    _watch(win) {
        if (win.window_type !== Meta.WindowType.NORMAL)
            return;
        win.connectObject(
            'notify::wm-class', () => this._later(win),
            'unmanaged', () => this._forget(win), this);
        this._later(win);
    }

    _later(win) {
        if (this._timers.has(win))
            return;
        this._timers.set(win, GLib.timeout_add(GLib.PRIORITY_DEFAULT, SETTLE_MS, () => {
            this._timers.delete(win);
            this._check(win);
            return GLib.SOURCE_REMOVE;
        }));
    }

    _forget(win) {
        const id = this._timers.get(win);
        if (id)
            GLib.source_remove(id);
        this._timers.delete(win);
        win.disconnectObject(this);
    }

    _unlinked(win) {
        return this._tracker.get_window_app(win)?.is_window_backed() && !win.get_sandboxed_app_id();
    }

    _check(win) {
        const wmClass = win.get_wm_class();
        if (!wmClass || !this._unlinked(win) || this._tried.has(wmClass))
            return;
        this._tried.add(wmClass);       // once per class and session: never a loop
        if (!GLib.file_test(MACIFY, GLib.FileTest.IS_EXECUTABLE))
            return;
        const argv = [MACIFY, 'link-window', wmClass];
        const pid = win.get_pid();
        if (pid > 0)
            argv.push('--pid', String(pid));
        try {
            Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE);
        } catch (e) {
            console.error(`Macify: link-window: ${e.message}`);
        }
    }

    // New launchers are loaded: windows still without an app look for theirs again.
    _relink() {
        for (const actor of global.get_window_actors()) {
            const win = actor.meta_window;
            if (this._unlinked(win))
                win.notify('wm-class');
        }
    }

    destroy() {
        global.display.disconnectObject(this);
        Shell.AppSystem.get_default().disconnectObject(this);
        for (const actor of global.get_window_actors())
            actor.meta_window.disconnectObject(this);
        for (const id of this._timers.values())
            GLib.source_remove(id);
        this._timers.clear();
    }
}
