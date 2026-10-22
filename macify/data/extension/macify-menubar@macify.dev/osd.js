// Indicador de volumen y brillo como en macOS 27: una tarjeta de cristal arriba a la derecha,
// bajo la barra, con el nombre («Sonido», «Pantalla»…) sobre la barra de nivel. Es el mismo
// indicador de GNOME (teclas de volumen, brillo, micrófono), sólo que colocado y vestido
// como el de Apple; al desactivar la extensión vuelve a ser el de GNOME. Mientras el Centro
// de control está abierto no sale (sus deslizadores ya enseñan el cambio).

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {_} from './i18n.js';

// Prefijo del icono que pone GNOME → nombre de la tarjeta.
const TITLES = [
    ['audio-volume', 'Sound'],
    ['microphone', 'Microphone'],
    ['audio-input-microphone', 'Microphone'],
    ['display-brightness', 'Display'],
    ['keyboard-brightness', 'Keyboard Brightness'],
];

function titleFor(icon) {
    const name = icon?.get_names?.()[0] ?? '';
    const match = TITLES.find(([prefix]) => name.startsWith(prefix));
    return match ? _(match[1]) : null;
}

export class MacOsd {
    constructor() {
        this._manager = Main.osdWindowManager;
        this._interface = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this._windows = new Map();                              // ventana → su título
        const show = this._manager._showOsdWindow;
        // Cada vez que GNOME va a mostrar el indicador en un monitor (también en los que se
        // conectan después), se viste antes.
        this._manager._showOsdWindow = (index, icon, ...rest) => {
            // Con el Centro de control abierto, su propio deslizador ya muestra el cambio:
            // el indicador sólo saldría encima, repetido.
            if (Main.panel.statusArea.quickSettings?.menu?.isOpen)
                return;
            const window = this._manager._osdWindows[index];
            if (window)
                this._dress(window, icon);
            show.call(this._manager, index, icon, ...rest);
        };
    }

    _dress(window, icon) {
        let title = this._windows.get(window);
        if (!title) {
            title = new St.Label({style_class: 'macify-osd-title', x_align: Clutter.ActorAlign.START});
            window._vbox.insert_child_at_index(title, 0);
            window._hbox.add_style_class_name('macify-osd');
            window.x_align = Clutter.ActorAlign.END;
            window.y_align = Clutter.ActorAlign.START;
            window.connectObject('destroy', () => this._windows.delete(window), this);
            this._windows.set(window, title);
        }
        const dark = this._interface.get_string('color-scheme') === 'prefer-dark';
        window._hbox.remove_style_class_name(dark ? 'macify-osd-light' : 'macify-osd-dark');
        window._hbox.add_style_class_name(dark ? 'macify-osd-dark' : 'macify-osd-light');
        const text = titleFor(icon);
        title.visible = Boolean(text);
        title.text = text ?? '';
    }

    destroy() {
        delete this._manager._showOsdWindow;                    // vuelve el método de GNOME
        for (const [window, title] of this._windows) {
            window.disconnectObject(this);
            title.destroy();
            window._hbox.remove_style_class_name('macify-osd');
            window._hbox.remove_style_class_name('macify-osd-dark');
            window._hbox.remove_style_class_name('macify-osd-light');
            window.x_align = Clutter.ActorAlign.CENTER;
            window.y_align = Clutter.ActorAlign.END;
        }
        this._windows.clear();
    }
}
