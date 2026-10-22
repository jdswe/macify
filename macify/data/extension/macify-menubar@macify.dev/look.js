// La barra de menús y el aspecto van juntos, como en macOS:
// · sobre un fondo claro, texto e iconos oscuros; sobre uno oscuro, claros. Macify mide el brillo
//   de la franja de arriba de cada versión del fondo (clara y oscura) al aplicarlo y lo deja en
//   ~/.config/macify/look.json; aquí sólo se lee y se vigila.
// · si se cambia a oscuro o claro desde el Centro de control, Macify aplica el resto del aspecto
//   (ventanas, fondo, cristal del dock) con «macify look», como si se eligiera en la app.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

const DARK_TEXT = 'macify-bar-dark-text';
const FOLLOW_DELAY_MS = 600;    // un cambio rápido de ida y vuelta no aplica nada
// Ruta fija (no se busca en el PATH): sólo el Macify instalado por el paquete, de root.
const MACIFY = '/usr/bin/macify';

export class BarLook {
    constructor() {
        this._look = {};
        // Se vigila la carpeta (no el archivo): así se nota también cuando look.json aparece
        // por primera vez o se reemplaza entero.
        const folder = GLib.build_filenamev([GLib.get_user_config_dir(), 'macify']);
        GLib.mkdir_with_parents(folder, 0o700);
        this._file = Gio.File.new_for_path(GLib.build_filenamev([folder, 'look.json']));
        this._monitor = Gio.File.new_for_path(folder).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, null);
        this._monitor.connect('changed', (_m, file, other) => {
            if (file?.get_basename() === 'look.json' || other?.get_basename() === 'look.json')
                this._load();
        });
        this._interface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._interface.connectObject('changed::color-scheme', () => this._schemeChanged(), this);
        this._load();
    }

    get _scheme() {
        return this._interface.get_string('color-scheme') === 'prefer-dark' ? 'dark' : 'light';
    }

    _load() {
        try {
            const [, bytes] = this._file.load_contents(null);
            this._look = JSON.parse(new TextDecoder().decode(bytes));
        } catch {
            this._look = {};      // Macify aún no aplicó un fondo: texto claro, como siempre
        }
        this._apply();
    }

    _apply() {
        const bar = this._look.bar;
        const text = typeof bar === 'object' && bar ? bar[this._scheme] : bar;
        if (text === 'dark-text')
            Main.panel.add_style_class_name(DARK_TEXT);
        else
            Main.panel.remove_style_class_name(DARK_TEXT);
    }

    _schemeChanged() {
        this._apply();
        if (this._followId)
            GLib.source_remove(this._followId);
        this._followId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, FOLLOW_DELAY_MS, () => {
            this._followId = 0;
            if (GLib.file_test(MACIFY, GLib.FileTest.IS_EXECUTABLE) && this._look.appearance &&
                this._look.appearance !== this._scheme)
                Util.spawn([MACIFY, 'look', '--appearance', this._scheme]);
            return GLib.SOURCE_REMOVE;
        });
    }

    destroy() {
        if (this._followId)
            GLib.source_remove(this._followId);
        this._interface.disconnectObject(this);
        this._monitor.cancel();
        Main.panel.remove_style_class_name(DARK_TEXT);
    }
}
