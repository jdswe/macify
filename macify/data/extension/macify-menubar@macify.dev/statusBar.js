// Lado derecho de la barra como en macOS: cada icono es su propio botón con su menú.
//     Batería · Wi‑Fi · Sonido · Spotlight · Centro de control · Reloj
// Los iconos son los indicadores de GNOME, prestados de sus ajustes rápidos: así siempre
// muestran el estado real. El Centro de control son esos ajustes rápidos.
// Lo que macOS no pone en la barra (modo de energía, luz nocturna…) queda dentro del Centro
// de control; los avisos de privacidad (cámara, micrófono, ubicación, acceso remoto) siguen
// a la vista. Al desactivar la extensión todo vuelve a su sitio.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

import {BatteryMenu} from './batteryMenu.js';
import {_} from './i18n.js';
import {SoundMenu} from './soundMenu.js';
import {WifiMenu} from './wifiMenu.js';

const SETUP_TRIES = 20;         // los indicadores de GNOME se crean un poco después del panel

// [indicador de GNOME, nombre en la barra, menú, nombre accesible]
const EXTRAS = [
    ['_system', 'macify-battery', BatteryMenu, 'Battery'],
    ['_network', 'macify-wifi', WifiMenu, 'Wi‑Fi'],
    ['_volumeOutput', 'macify-sound', SoundMenu, 'Sound'],
];
const TUCKED = ['_powerProfiles', '_nightLight', '_darkMode', '_backlight', '_brightness', '_autoRotate'];

const StatusExtra = GObject.registerClass(
class StatusExtra extends PanelMenu.Button {
    _init(name) {
        super._init(0.5, name, false);
        this.add_style_class_name('macify-extra');
        this.menu.actor.add_style_class_name('macify-app-menu');
    }
});

export class StatusBar {
    constructor() {
        this._loans = [];
        this._extras = [];
        this._tries = 0;
        this._spotlight = new PanelMenu.Button(0.5, _('Spotlight'), true);
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
        this._tucked = new St.BoxLayout({visible: false});    // fuera de la pantalla: siguen al día, sin verse
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
        for (const [key, role, Menu, name] of EXTRAS) {
            const indicator = qs[key];
            if (!indicator)
                continue;
            const button = new StatusExtra(_(name));
            const menu = new Menu(button.menu);
            this._lend(indicator, button);
            // Sin batería o sin audio, GNOME oculta su indicador: el botón también.
            indicator.bind_property('visible', button, 'visible', GObject.BindingFlags.SYNC_CREATE);
            this._addBeforeControlCenter(role, button);
            this._extras.push({button, menu});
        }
        this._addBeforeControlCenter('macify-spotlight', this._spotlight);
        for (const key of TUCKED) {
            if (qs[key])
                this._lend(qs[key], this._tucked);
        }
        qs._indicators.add_child(this._controlCenter);
    }

    _addBeforeControlCenter(role, button) {
        const qs = Main.panel.statusArea.quickSettings;
        const index = Main.panel._rightBox.get_children().indexOf(qs.container);
        Main.panel.addToStatusArea(role, button, Math.max(index, 0), 'right');
    }

    // Mueve un indicador de GNOME a otro sitio, recordando de dónde vino.
    _lend(actor, target) {
        const parent = actor.get_parent();
        this._loans.push({actor, parent, index: parent.get_children().indexOf(actor)});
        parent.remove_child(actor);
        target.add_child(actor);
    }

    destroy() {
        if (this._retryId)
            GLib.source_remove(this._retryId);
        for (const {actor, parent, index} of this._loans.reverse()) {
            actor.get_parent()?.remove_child(actor);
            parent.insert_child_at_index(actor, index);
        }
        this._loans = [];
        for (const {button, menu} of this._extras) {
            menu.destroy();
            button.destroy();
        }
        this._controlCenter.destroy();
        this._spotlight.destroy();
        this._tucked.destroy();
    }
}
