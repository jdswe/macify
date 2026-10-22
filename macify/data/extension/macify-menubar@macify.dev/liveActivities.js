// Live Activities: una cápsula en el centro de la barra que crece con una animación
// elástica cuando pasa algo, como en macOS 27.
// - Música o video sonando en cualquier app (MPRIS): título, artista y barras que se
//   mueven. Clic: pausa o sigue.
// - Al enchufar o desenchufar el cargador, carga completa y batería baja.
// - Al perder o recuperar la conexión.
// Todo funciona por avisos del sistema (D-Bus): sin sondeos y sin animaciones si no hay nada.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Pango from 'gi://Pango';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {_} from './i18n.js';

const MPRIS_PREFIX = 'org.mpris.MediaPlayer2.';
const MPRIS_PATH = '/org/mpris/MediaPlayer2';
const PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player';
const EVENT_MS = 3500;          // lo que dura un aviso (carga, conexión)
const PAUSED_MS = 4000;         // lo que se queda la música en pausa antes de recogerse
const QUIET_START_MS = 6000;    // al iniciar sesión no se avisa de lo que ya estaba así
const MAX_TEXT = 44;

const UPOWER_STATE = {CHARGING: 1, DISCHARGING: 2, FULL: 4};

function clip(text) {
    return text.length > MAX_TEXT ? `${text.slice(0, MAX_TEXT - 1)}…` : text;
}

function unpack(variant) {
    return variant?.deepUnpack?.() ?? variant;
}

export class LiveActivities {
    constructor() {
        this._bus = Gio.DBus.session;
        this._players = new Map();       // nombre en el bus → {proxy, status, title, artist, art}
        this._event = null;
        this._startedAt = GLib.get_monotonic_time();

        this._build();
        this._watchPlayers();
        this._watchPower();
        this._watchNetwork();
    }

    // ---------- la cápsula ----------

    _build() {
        this._pill = new St.BoxLayout({
            style_class: 'macify-island',
            reactive: true,
            track_hover: true,
            y_align: Clutter.ActorAlign.CENTER,
            visible: false,
            opacity: 0,
        });
        this._pill.set_pivot_point(0.5, 0.5);
        this._icon = new St.Icon({style_class: 'macify-island-icon', icon_size: 16, y_align: Clutter.ActorAlign.CENTER});
        this._label = new St.Label({style_class: 'macify-island-label', y_align: Clutter.ActorAlign.CENTER});
        this._label.clutter_text.ellipsize = Pango.EllipsizeMode.END;
        this._bars = new St.BoxLayout({style_class: 'macify-island-bars', y_align: Clutter.ActorAlign.CENTER});
        this._barActors = [0, 1, 2, 3].map(() => {
            const bar = new St.Widget({style_class: 'macify-island-bar', y_align: Clutter.ActorAlign.END});
            bar.set_pivot_point(0.5, 1);
            this._bars.add_child(bar);
            return bar;
        });
        this._pill.add_child(this._icon);
        this._pill.add_child(this._label);
        this._pill.add_child(this._bars);
        this._pill.connect('button-press-event', () => {
            this._activePlayer()?.proxy.call('PlayPause', null, Gio.DBusCallFlags.NONE, -1, null, null);
            return Clutter.EVENT_STOP;
        });
        Main.panel._centerBox.insert_child_at_index(this._pill, 0);
    }

    _render() {
        const event = this._event;
        const player = this._activePlayer();
        if (event) {
            this._show(event.icon, event.text, false);
        } else if (player && (player.status === 'Playing' || player.lingering)) {
            const text = [player.title, player.artist].filter(Boolean).join(' — ') || player.name;
            this._show(player.art ?? 'audio-x-generic-symbolic', text, player.status === 'Playing');
        } else {
            this._hide();
        }
    }

    _show(icon, text, playing) {
        if (icon instanceof Gio.Icon)
            this._icon.gicon = icon;
        else
            this._icon.icon_name = icon;
        const changed = this._label.text !== clip(text);
        this._label.text = clip(text);
        this._bars.visible = playing;
        this._animateBars(playing);
        if (!this._pill.visible) {
            this._pill.visible = true;
            this._pill.opacity = 0;
            this._pill.scale_x = 0.55;
            this._pill.scale_y = 0.7;
            this._pill.ease({
                opacity: 255, scale_x: 1, scale_y: 1, duration: 420,
                mode: Clutter.AnimationMode.EASE_OUT_BACK,
            });
        } else if (changed) {
            this._label.opacity = 0;
            this._label.ease({opacity: 255, duration: 180, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
            this._pill.scale_x = 0.94;
            this._pill.ease({scale_x: 1, duration: 300, mode: Clutter.AnimationMode.EASE_OUT_BACK});
        }
    }

    _hide() {
        this._animateBars(false);
        if (!this._pill.visible)
            return;
        this._pill.ease({
            opacity: 0, scale_x: 0.6, scale_y: 0.8, duration: 220,
            mode: Clutter.AnimationMode.EASE_IN_QUAD,
            onComplete: () => {
                if (this._pill.opacity === 0)
                    this._pill.visible = false;
            },
        });
    }

    // Barras de audio: cada una sube y baja a su ritmo mientras algo suena.
    _animateBars(playing) {
        this._barsRunning = playing;
        for (const bar of this._barActors) {
            if (!playing) {
                bar.remove_all_transitions();
                bar.scale_y = 0.35;
                continue;
            }
            if (!bar._macifyMoving)
                this._moveBar(bar);
        }
    }

    _moveBar(bar) {
        if (!this._barsRunning || !this._pill.visible) {
            bar._macifyMoving = false;
            return;
        }
        bar._macifyMoving = true;
        bar.ease({
            scale_y: 0.25 + Math.random() * 0.75,
            duration: 160 + Math.floor(Math.random() * 220),
            mode: Clutter.AnimationMode.EASE_IN_OUT_SINE,
            onComplete: () => this._moveBar(bar),
        });
    }

    _flash(icon, text) {
        // Al iniciar sesión el estado ya era ese: no se avisa.
        if ((GLib.get_monotonic_time() - this._startedAt) / 1000 < QUIET_START_MS)
            return;
        this._event = {icon, text};
        this._render();
        if (this._eventId)
            GLib.source_remove(this._eventId);
        this._eventId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, EVENT_MS, () => {
            this._eventId = 0;
            this._event = null;
            this._render();
            return GLib.SOURCE_REMOVE;
        });
    }

    // ---------- música (MPRIS) ----------

    _watchPlayers() {
        this._nameSub = this._bus.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus',
            'NameOwnerChanged', '/org/freedesktop/DBus', null, Gio.DBusSignalFlags.NONE,
            (_c, _s, _p, _i, _sig, params) => {
                const [name, , owner] = params.deepUnpack();
                if (!name.startsWith(MPRIS_PREFIX))
                    return;
                if (owner)
                    this._addPlayer(name);
                else
                    this._removePlayer(name);
            });
        this._bus.call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'ListNames',
            null, null, Gio.DBusCallFlags.NONE, -1, null, (bus, result) => {
                try {
                    const [names] = bus.call_finish(result).deepUnpack();
                    names.filter(n => n.startsWith(MPRIS_PREFIX)).forEach(n => this._addPlayer(n));
                } catch (e) {
                    console.warn(`Macify: MPRIS: ${e.message}`);
                }
            });
    }

    _addPlayer(name) {
        if (this._players.has(name))
            return;
        const player = {name: name.slice(MPRIS_PREFIX.length).split('.')[0], status: 'Stopped'};
        this._players.set(name, player);
        Gio.DBusProxy.new(this._bus, Gio.DBusProxyFlags.GET_INVALIDATED_PROPERTIES, null, name, MPRIS_PATH,
            PLAYER_IFACE, null, (_o, result) => {
                try {
                    player.proxy = Gio.DBusProxy.new_finish(result);
                } catch (e) {
                    this._players.delete(name);
                    return;
                }
                if (!this._players.has(name))
                    return;
                player.proxy.connect('g-properties-changed', () => this._readPlayer(player));
                this._readPlayer(player);
            });
    }

    _readPlayer(player) {
        const proxy = player.proxy;
        const before = player.status;
        player.status = unpack(proxy.get_cached_property('PlaybackStatus')) ?? 'Stopped';
        const meta = unpack(proxy.get_cached_property('Metadata')) ?? {};
        player.title = unpack(meta['xesam:title']) ?? '';
        const artist = unpack(meta['xesam:artist']);
        player.artist = Array.isArray(artist) ? artist.join(', ') : (artist ?? '');
        const art = unpack(meta['mpris:artUrl']);
        player.art = art?.startsWith('file://') ? new Gio.FileIcon({file: Gio.File.new_for_uri(art)}) : null;
        if (player.status === 'Playing')
            player.playedAt = GLib.get_monotonic_time();
        // En pausa se queda un momento a la vista y luego se recoge.
        if (before === 'Playing' && player.status !== 'Playing') {
            player.lingering = true;
            if (player.lingerId)
                GLib.source_remove(player.lingerId);
            player.lingerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, PAUSED_MS, () => {
                player.lingerId = 0;
                player.lingering = false;
                this._render();
                return GLib.SOURCE_REMOVE;
            });
        } else if (player.status === 'Playing') {
            player.lingering = false;
        }
        this._render();
    }

    _removePlayer(name) {
        const player = this._players.get(name);
        if (player?.lingerId)
            GLib.source_remove(player.lingerId);
        this._players.delete(name);
        this._render();
    }

    _activePlayer() {
        let best = null;
        for (const player of this._players.values()) {
            if (!player.proxy || (player.status !== 'Playing' && !player.lingering))
                continue;
            if (!best || (player.playedAt ?? 0) > (best.playedAt ?? 0))
                best = player;
        }
        return best;
    }

    // ---------- batería (UPower) ----------

    _watchPower() {
        Gio.DBusProxy.new(Gio.DBus.system, Gio.DBusProxyFlags.NONE, null, 'org.freedesktop.UPower',
            '/org/freedesktop/UPower/devices/DisplayDevice', 'org.freedesktop.UPower.Device', null, (_o, result) => {
                try {
                    this._power = Gio.DBusProxy.new_finish(result);
                } catch (e) {
                    return;
                }
                this._powerState = unpack(this._power.get_cached_property('State'));
                this._powerId = this._power.connect('g-properties-changed', () => this._readPower());
            });
    }

    _readPower() {
        if (!unpack(this._power.get_cached_property('IsPresent')))
            return;
        const state = unpack(this._power.get_cached_property('State'));
        const percent = Math.round(unpack(this._power.get_cached_property('Percentage')) ?? 0);
        const level = Math.min(100, Math.round(percent / 10) * 10);
        const before = this._powerState;
        this._powerState = state;
        if (state !== before) {
            if (state === UPOWER_STATE.CHARGING)
                this._flash(`battery-level-${level}-charging-symbolic`, `${_('Charging')} · ${percent}%`);
            else if (state === UPOWER_STATE.FULL)
                this._flash('battery-level-100-charged-symbolic', _('Fully Charged'));
            else if (state === UPOWER_STATE.DISCHARGING && before !== undefined)
                this._flash(`battery-level-${level}-symbolic`, `${_('On Battery')} · ${percent}%`);
        }
        // Batería baja: un aviso al cruzar el 20 % y otro al 10 %.
        if (state === UPOWER_STATE.DISCHARGING) {
            const step = percent <= 10 ? 10 : percent <= 20 ? 20 : 0;
            if (step && step !== this._lowWarned) {
                this._lowWarned = step;
                this._flash(`battery-level-${step === 10 ? 10 : 20}-symbolic`, `${_('Battery Low')} · ${percent}%`);
            }
        } else {
            this._lowWarned = 0;
        }
    }

    // ---------- conexión ----------

    _watchNetwork() {
        this._monitor = Gio.NetworkMonitor.get_default();
        this._online = this._monitor.network_available;
        this._networkId = this._monitor.connect('network-changed', () => {
            // Espera a que se asiente: al cambiar de red llegan varios avisos seguidos.
            if (this._networkTimer)
                GLib.source_remove(this._networkTimer);
            this._networkTimer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1200, () => {
                this._networkTimer = 0;
                const online = this._monitor.network_available;
                if (online !== this._online) {
                    this._online = online;
                    this._flash(online ? 'network-wireless-signal-excellent-symbolic' : 'network-wireless-offline-symbolic',
                        online ? _('Connected') : _('Offline'));
                }
                return GLib.SOURCE_REMOVE;
            });
        });
    }

    destroy() {
        if (this._nameSub)
            this._bus.signal_unsubscribe(this._nameSub);
        for (const player of this._players.values()) {
            if (player.lingerId)
                GLib.source_remove(player.lingerId);
        }
        this._players.clear();
        for (const id of [this._eventId, this._networkTimer]) {
            if (id)
                GLib.source_remove(id);
        }
        if (this._powerId)
            this._power.disconnect(this._powerId);
        if (this._networkId)
            this._monitor.disconnect(this._networkId);
        this._barsRunning = false;
        this._pill.destroy();
    }
}
