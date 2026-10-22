// Menú de Wi‑Fi, como el de macOS: interruptor, la red actual y las redes cercanas.
// Una red guardada se activa directamente; para una nueva, NetworkManager pide la
// contraseña con el diálogo propio de GNOME (Macify nunca ve contraseñas).
// La lista se arma al abrir el menú y entonces se pide una búsqueda de redes.
// El icono sigue en la barra con el Wi‑Fi apagado o sin señal (tachado o vacío): desde aquí
// mismo se vuelve a encender, como en macOS.

import GLib from 'gi://GLib';
import NM from 'gi://NM';
import St from 'gi://St';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

import {_} from './i18n.js';
import {header, separator, settingsItem} from './menuParts.js';

const MAX_NETWORKS = 8;
const SECURED = NM['80211ApSecurityFlags'];

function ssidText(ssid) {
    return ssid ? NM.utils_ssid_to_utf8(ssid.get_data()) : '';
}

function signalIcon(strength) {
    const level = strength < 20 ? 'none' : strength < 40 ? 'weak' : strength < 50 ? 'ok' : strength < 80 ? 'good' : 'excellent';
    return `network-wireless-signal-${level}-symbolic`;
}

function isEnterprise(ap) {
    const enterprise = SECURED.KEY_MGMT_802_1X;
    return (ap.get_wpa_flags() & enterprise) !== 0 || (ap.get_rsn_flags() & enterprise) !== 0;
}

function isSecured(ap) {
    return ap.get_wpa_flags() !== SECURED.NONE || ap.get_rsn_flags() !== SECURED.NONE ||
        (ap.get_flags() & NM['80211ApFlags'].PRIVACY) !== 0;
}

export class WifiMenu {
    constructor(menu) {
        this._menu = menu;
        // Lo que se ve cuando GNOME no muestra nada (Wi‑Fi apagado o sin red).
        this.fallbackIcon = new St.Icon({style_class: 'system-status-icon', visible: false});
        header(menu, _('Wi‑Fi'));
        this._switch = new PopupMenu.PopupSwitchMenuItem(_('Wi‑Fi'), false);
        this._switch.connect('toggled', (_i, on) => this._setEnabled(on));
        menu.addMenuItem(this._switch);
        separator(menu);
        this._networks = new PopupMenu.PopupMenuSection();
        menu.addMenuItem(this._networks);
        separator(menu);
        settingsItem(menu, _('Wi‑Fi Settings…'), 'wifi');

        NM.Client.new_async(null, (_o, result) => {
            try {
                this._client = NM.Client.new_finish(result);
                this._client.connectObject(
                    'notify::wireless-enabled', () => this._syncPresence(),
                    'device-added', () => this._syncPresence(),
                    'device-removed', () => this._syncPresence(),
                    this);
                this._syncPresence();
            } catch (e) {
                console.warn(`Macify: NetworkManager: ${e.message}`);
            }
        });
        menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refresh(true);
        });
    }

    // El botón se ve si GNOME muestra algo (Wi‑Fi, cable, VPN…) o si el equipo tiene Wi‑Fi.
    watchPresence(indicator, button) {
        this._indicator = indicator;
        this._button = button;
        indicator.connectObject('notify::visible', () => this._syncPresence(), this);
        this._syncPresence();
    }

    _syncPresence() {
        if (!this._button)
            return;
        const gnomeShows = this._indicator.visible;
        const wifi = Boolean(this._device);
        this.fallbackIcon.icon_name = this._client?.wireless_enabled
            ? 'network-wireless-offline-symbolic' : 'network-wireless-disabled-symbolic';
        this.fallbackIcon.visible = !gnomeShows && wifi;
        this._button.visible = gnomeShows || wifi;
        if (this._menu.isOpen)
            this._refresh();
    }

    get _device() {
        return this._client?.get_devices().find(d => d instanceof NM.DeviceWifi) ?? null;
    }

    _setEnabled(on) {
        this._client?.dbus_set_property(NM.DBUS_PATH, NM.DBUS_INTERFACE, 'WirelessEnabled',
            new GLib.Variant('b', on), -1, null, null);
    }

    _refresh(scan = false) {
        const device = this._device;
        this._switch.setToggleState(Boolean(this._client?.wireless_enabled));
        this._networks.removeAll();
        if (!device || !this._client.wireless_enabled)
            return;
        if (scan)
            device.request_scan_async(null, () => this._refresh(false));
        const active = device.get_active_access_point();
        const seen = new Map();
        for (const ap of device.get_access_points()) {
            const name = ssidText(ap.get_ssid());
            if (name && (!seen.has(name) || seen.get(name).get_strength() < ap.get_strength()))
                seen.set(name, ap);
        }
        const activeName = active ? ssidText(active.get_ssid()) : null;
        const networks = [...seen.entries()]
            .sort(([a, x], [b, y]) => (b === activeName) - (a === activeName) || y.get_strength() - x.get_strength())
            .slice(0, MAX_NETWORKS);
        for (const [name, ap] of networks) {
            const item = new PopupMenu.PopupImageMenuItem(name, signalIcon(ap.get_strength()));
            if (isSecured(ap))
                item.add_child(new St.Icon({icon_name: 'network-wireless-encrypted-symbolic', style_class: 'popup-menu-icon'}));
            if (name === activeName)
                item.setOrnament(PopupMenu.Ornament.CHECK);
            item.connect('activate', () => this._connect(device, ap, name));
            this._networks.addMenuItem(item);
        }
    }

    // Igual que el menú de GNOME: una red guardada se activa; una nueva se crea sólo para esta
    // persona (sin pedir permisos de administrador) y NetworkManager pide la contraseña con su
    // diálogo; las de empresa (802.1X) se configuran en Ajustes. Cancelar la contraseña es un
    // error normal: se recoge aquí (sin esto, GNOME Shell llegó a cerrarse).
    _connect(device, ap, name) {
        const saved = device.filter_connections(this._client.get_connections())
            .find(c => ssidText(c.get_setting_wireless()?.get_ssid()) === name);
        const done = (client, result, finish) => {
            try {
                client[finish](result);
            } catch (e) {
                console.log(`Macify: Wi‑Fi ${name}: ${e.message}`);
            }
        };
        if (saved) {
            this._client.activate_connection_async(saved, device, null, null,
                (client, result) => done(client, result, 'activate_connection_finish'));
        } else if (isEnterprise(ap)) {
            Util.spawn(['gnome-control-center', 'wifi', 'connect-8021x-wifi',
                NM.Object.prototype.get_path.call(device), ap.get_path()]);
        } else {
            const connection = new NM.SimpleConnection();
            const setting = new NM.SettingConnection();
            setting.add_permission('user', GLib.get_user_name(), null);
            connection.add_setting(setting);
            this._client.add_and_activate_connection_async(connection, device, ap.get_path(), null,
                (client, result) => done(client, result, 'add_and_activate_connection_finish'));
        }
    }

    destroy() {
        this._client?.disconnectObject(this);
        this._indicator?.disconnectObject(this);
        this._client = null;
    }
}
