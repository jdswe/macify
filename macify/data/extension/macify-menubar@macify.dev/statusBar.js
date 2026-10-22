// Lado derecho de la barra en el orden de macOS: Spotlight, batería, Wi‑Fi, Centro de
// control y reloj. Los iconos de batería y Wi‑Fi son los del tema Macify; aquí sólo se
// reordena lo que GNOME ya muestra y se añaden los botones que faltan.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

import {_} from './i18n.js';

const SETUP_TRIES = 20;         // los indicadores de GNOME se crean un poco después del panel

export class StatusBar {
    constructor() {
        this._spotlight = new PanelMenu.Button(0.0, _('Spotlight'), true);
        this._spotlight.add_child(new St.Icon({
            icon_name: 'macify-spotlight-symbolic',
            fallback_icon_name: 'system-search-symbolic',
            style_class: 'system-status-icon',
        }));
        this._spotlight.connect('button-press-event', () => {
            Main.overview.toggle();
            return Clutter.EVENT_STOP;
        });
        this._controlCenter = new St.Icon({
            icon_name: 'macify-control-center-symbolic',
            fallback_icon_name: 'emblem-system-symbolic',
            style_class: 'system-status-icon macify-control-center',
        });
        this._tries = 0;
        this._setup();
    }

    _setup() {
        const qs = Main.panel.statusArea.quickSettings;
        if (!qs?._indicators || !qs._system) {
            if (this._tries++ < SETUP_TRIES) {
                this._retryId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
                    this._retryId = 0;
                    this._setup();
                    return GLib.SOURCE_REMOVE;
                });
            }
            return;
        }
        this._qs = qs;
        // Batería primero, luego Wi‑Fi y lo demás; el icono del Centro de control al final.
        this._systemIndex = qs._indicators.get_children().indexOf(qs._system);
        qs._indicators.set_child_at_index(qs._system, 0);
        qs._indicators.add_child(this._controlCenter);
        const index = Main.panel._rightBox.get_children().indexOf(qs.container);
        Main.panel.addToStatusArea('macify-spotlight', this._spotlight, Math.max(index, 0), 'right');
    }

    destroy() {
        if (this._retryId)
            GLib.source_remove(this._retryId);
        if (this._qs && this._systemIndex >= 0)
            this._qs._indicators.set_child_at_index(this._qs._system, this._systemIndex);
        this._controlCenter.destroy();
        this._spotlight.destroy();
    }
}
