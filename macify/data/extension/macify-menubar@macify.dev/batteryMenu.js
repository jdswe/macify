// Menú de la batería, como el de macOS: porcentaje, fuente de energía, tiempo restante,
// «Modo de bajo consumo» y acceso a los ajustes. Datos de UPower; el modo, de
// power-profiles-daemon (el mismo que usa GNOME, sin pedir contraseña).

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {_} from './i18n.js';
import {header, infoRow, separator, settingsItem} from './menuParts.js';

const UPOWER = ['org.freedesktop.UPower', '/org/freedesktop/UPower/devices/DisplayDevice', 'org.freedesktop.UPower.Device'];
const PROFILES = ['org.freedesktop.UPower.PowerProfiles', '/org/freedesktop/UPower/PowerProfiles',
    'org.freedesktop.UPower.PowerProfiles'];
const STATE = {CHARGING: 1, DISCHARGING: 2, EMPTY: 3, FULL: 4, PENDING_CHARGE: 5, PENDING_DISCHARGE: 6};

function proxy([name, path, iface], cancellable, callback) {
    Gio.DBusProxy.new(Gio.DBus.system, Gio.DBusProxyFlags.NONE, null, name, path, iface, cancellable,
        (_o, result) => {
            try {
                callback(Gio.DBusProxy.new_finish(result));
            } catch (e) {
                // sin batería o sin power-profiles-daemon: esa parte no se muestra
            }
        });
}

// 3570 s → «1:00» (se redondea el total de minutos, no cada parte por separado).
function duration(seconds) {
    const minutes = Math.round(seconds / 60);
    return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`;
}

export class BatteryMenu {
    constructor(menu) {
        this._cancellable = new Gio.Cancellable();
        this._percent = header(menu, _('Battery'));
        this._source = infoRow(menu);
        this._time = infoRow(menu);
        separator(menu);
        this._lowPower = new PopupMenu.PopupSwitchMenuItem(_('Low Power Mode'), false);
        this._lowPower.connect('toggled', (_i, on) => this._setLowPower(on));
        menu.addMenuItem(this._lowPower);
        separator(menu);
        settingsItem(menu, _('Battery Settings…'), 'power');

        proxy(UPOWER, this._cancellable, p => {
            this._battery = p;
            p.connectObject('g-properties-changed', () => this.update(), this);
            this.update();
        });
        proxy(PROFILES, this._cancellable, p => {
            this._profiles = p;
            p.connectObject('g-properties-changed', () => this.update(), this);
            this.update();
        });
    }

    _get(proxyObject, name) {
        return proxyObject?.get_cached_property(name)?.deepUnpack();
    }

    get present() {
        return Boolean(this._get(this._battery, 'IsPresent'));
    }

    update() {
        const state = this._get(this._battery, 'State');
        const percent = Math.round(this._get(this._battery, 'Percentage') ?? 0);
        this._percent.text = this.present ? `${percent}%` : '';
        const plugged = [STATE.CHARGING, STATE.FULL, STATE.PENDING_CHARGE].includes(state);
        this._source.label.text = `${_('Power Source:')} ${plugged ? _('Power Adapter') : _('Battery')}`;
        const toEmpty = this._get(this._battery, 'TimeToEmpty') ?? 0;
        const toFull = this._get(this._battery, 'TimeToFull') ?? 0;
        if (state === STATE.FULL)
            this._time.label.text = _('Fully Charged');
        else if (state === STATE.CHARGING && toFull > 0)
            this._time.label.text = _('{time} until full', {time: duration(toFull)});
        else if (state === STATE.DISCHARGING && toEmpty > 0)
            this._time.label.text = _('{time} remaining', {time: duration(toEmpty)});
        else
            this._time.label.text = '';
        this._time.visible = Boolean(this._time.label.text);
        const profile = this._get(this._profiles, 'ActiveProfile');
        this._lowPower.visible = Boolean(this._profiles);
        this._lowPower.setToggleState(profile === 'power-saver');
    }

    _setLowPower(on) {
        this._profiles?.call('org.freedesktop.DBus.Properties.Set',
            new GLib.Variant('(ssv)', [PROFILES[2], 'ActiveProfile', new GLib.Variant('s', on ? 'power-saver' : 'balanced')]),
            Gio.DBusCallFlags.NONE, -1, null, null);
    }

    destroy() {
        this._cancellable.cancel();
        this._battery?.disconnectObject(this);
        this._profiles?.disconnectObject(this);
    }
}
