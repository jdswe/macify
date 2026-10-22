// Menú de Wi‑Fi, como el de macOS: interruptor, la red actual y las redes cercanas.
// Una red guardada se activa directamente; para una nueva, NetworkManager pide la
// contraseña con el diálogo propio de GNOME (Macify nunca ve contraseñas).
// La lista se arma al abrir el menú y entonces se pide una búsqueda de redes.

import GLib from 'gi://GLib';
import NM from 'gi://NM';
import St from 'gi://St';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

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

function isSecured(ap) {
    return ap.get_wpa_flags() !== SECURED.NONE || ap.get_rsn_flags() !== SECURED.NONE ||
        (ap.get_flags() & NM['80211ApFlags'].PRIVACY) !== 0;
}

export class WifiMenu {
    constructor(menu) {
        this._menu = menu;
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
            } catch (e) {
                console.warn(`Macify: NetworkManager: ${e.message}`);
            }
        });
        menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refresh(true);
        });
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

    _connect(device, ap, name) {
        const saved = device.filter_connections(this._client.get_connections())
            .find(c => ssidText(c.get_setting_wireless()?.get_ssid()) === name);
        if (saved)
            this._client.activate_connection_async(saved, device, null, null, null);
        else
            this._client.add_and_activate_connection_async(null, device, ap.get_path(), null, null);
    }

    destroy() {
        this._client = null;
    }
}
