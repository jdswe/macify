// Menú de Bluetooth, como el de macOS: interruptor, los dispositivos enlazados (pulsar uno
// lo conecta o desconecta) y los ajustes. Su icono en la barra sólo aparece si el equipo
// tiene Bluetooth, y muestra si está encendido. Usa el mismo cliente que GNOME.

import GnomeBluetooth from 'gi://GnomeBluetooth?version=3.0';
import St from 'gi://St';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {_} from './i18n.js';
import {header, infoRow, separator, settingsItem} from './menuParts.js';

const {AdapterState} = GnomeBluetooth;

export class BluetoothMenu {
    constructor(menu, indicator, button) {
        this._client = indicator._client;
        this._button = button;
        this.icon = new St.Icon({style_class: 'system-status-icon'});
        header(menu, _('Bluetooth'));
        this._switch = new PopupMenu.PopupSwitchMenuItem(_('Bluetooth'), false);
        this._switch.connect('toggled', (_i, on) => {
            if (on !== this._client.active)
                this._client.toggleActive();
        });
        menu.addMenuItem(this._switch);
        separator(menu);
        this._devicesTitle = new PopupMenu.PopupMenuItem(_('Devices'), {reactive: false, can_focus: false});
        this._devicesTitle.add_style_class_name('macify-extra-section');
        menu.addMenuItem(this._devicesTitle);
        this._devices = new PopupMenu.PopupMenuSection();
        menu.addMenuItem(this._devices);
        this._empty = infoRow(menu);
        separator(menu);
        settingsItem(menu, _('Bluetooth Settings…'), 'bluetooth');

        this._menu = menu;
        this._client.connectObject(
            'notify::available', () => this._sync(),
            'notify::adapter-state', () => this._sync(),
            'notify::active', () => this._sync(),
            'devices-changed', () => this._sync(),
            this);
        menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refresh();
        });
        this._sync();
    }

    get _present() {
        return this._client.available || this._client.adapter_state !== AdapterState.ABSENT;
    }

    // Lo de la barra se actualiza siempre (es barato); la lista, sólo con el menú abierto.
    _sync() {
        const state = this._client.adapter_state;
        this._button.visible = this._present;
        this.icon.icon_name = state === AdapterState.TURNING_ON || state === AdapterState.TURNING_OFF
            ? 'bluetooth-acquiring-symbolic'
            : this._client.active ? 'bluetooth-active-symbolic' : 'bluetooth-disabled-symbolic';
        if (this._menu.isOpen)
            this._refresh();
    }

    _refresh() {
        const active = this._client.active;
        this._switch.setToggleState(active);
        this._devices.removeAll();
        const devices = [...this._client.getDevices()]
            .filter(device => device.connectable)
            .sort((a, b) => b.connected - a.connected || a.alias.localeCompare(b.alias));
        for (const device of devices) {
            const item = new PopupMenu.PopupImageMenuItem(device.alias, device.icon || 'bluetooth-active-symbolic');
            if (device.connected)
                item.setOrnament(PopupMenu.Ornament.CHECK);
            item.connect('activate', () => this._client.toggleDevice(device));
            this._devices.addMenuItem(item);
        }
        this._devicesTitle.visible = active && devices.length > 0;
        this._empty.visible = !devices.length;
        this._empty.label.text = active ? _('No devices') : _('Turn on Bluetooth to connect devices');
    }

    destroy() {
        this._client.disconnectObject(this);
    }
}
