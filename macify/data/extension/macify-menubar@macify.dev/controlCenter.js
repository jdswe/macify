// Centro de control como en macOS: sólo lo que no tiene su propio sitio, en el orden de Apple.
//     Conexiones: Bluetooth, Modo avión · Concentración: No molestar · Pantalla: brillo,
//     Estilo oscuro, Luz nocturna
// Se quita lo que ya está aparte: Wi‑Fi, sonido y batería (con sus modos) tienen su menú en la
// barra, y apagar, reiniciar, bloquear y ajustes están en el menú del logo. Al desactivar la
// extensión todo vuelve a su sitio.

import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const SETUP_TRIES = 20;

// Lo que se quita del Centro de control.
const TUCKED = [
    qs => qs._system?.quickSettingsItems ?? [],                 // batería, captura, ajustes, bloquear, apagar
    qs => qs._volumeOutput?.quickSettingsItems ?? [],           // volumen (menú Sonido)
    qs => qs._powerProfiles?.quickSettingsItems ?? [],          // modo de energía (menú Batería)
    qs => (qs._network?.quickSettingsItems ?? []).filter(i => i.constructor.name === 'NMWirelessToggle'),
];
// Lo que queda, en el orden de macOS (lo que no esté en el equipo se salta).
const ORDER = ['_bluetooth', '_rfkill', '_doNotDisturb', '_brightness', '_darkMode', '_nightLight'];

export class ControlCenter {
    constructor() {
        this._loans = [];
        this._holder = new St.BoxLayout({visible: false});      // fuera de la pantalla
        this._tries = 0;
        this._setup();
    }

    _setup() {
        const qs = Main.panel.statusArea.quickSettings;
        const grid = qs?.menu?._grid;
        if (!grid || !qs._system) {
            if (this._tries++ < SETUP_TRIES) {
                this._retryId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
                    this._retryId = 0;
                    this._setup();
                    return GLib.SOURCE_REMOVE;
                });
            }
            return;
        }
        this._grid = grid;
        for (const items of TUCKED) {
            for (const item of items(qs))
                this._tuck(item);
        }
        this._sort(qs);
    }

    _span(item) {
        return this._grid.layout_manager.get_child_meta(this._grid, item)?.column_span ?? 1;
    }

    _tuck(item) {
        if (item.get_parent() !== this._grid)
            return;
        this._loans.push({item, index: this._grid.get_children().indexOf(item), span: this._span(item)});
        this._grid.remove_child(item);
        this._holder.add_child(item);
    }

    _sort(qs) {
        const items = ORDER.flatMap(key => qs[key]?.quickSettingsItems ?? [])
            .filter(item => item.get_parent() === this._grid);
        if (!items.length)
            return;
        this._order = this._grid.get_children().slice();
        let index = Math.min(...items.map(item => this._grid.get_children().indexOf(item)));
        for (const item of items)
            this._grid.set_child_at_index(item, index++);
    }

    destroy() {
        if (this._retryId)
            GLib.source_remove(this._retryId);
        if (this._order)
            this._order.forEach((item, i) => item.get_parent() === this._grid && this._grid.set_child_at_index(item, i));
        for (const {item, index, span} of this._loans.reverse()) {
            this._holder.remove_child(item);
            this._grid.insert_child_at_index(item, index);
            const meta = this._grid.layout_manager.get_child_meta(this._grid, item);
            if (meta)
                meta.column_span = span;
        }
        this._loans = [];
        this._holder.destroy();
    }
}
