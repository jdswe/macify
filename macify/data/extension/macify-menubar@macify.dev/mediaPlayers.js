// Reproductores multimedia de cualquier app (MPRIS por D-Bus): qué suena, en qué app y
// sus controles. Sólo escucha avisos del bus; no consulta nada periódicamente.

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

import * as Signals from 'resource:///org/gnome/shell/misc/signals.js';

const NAMESPACE = 'org.mpris.MediaPlayer2';      // filtro del bus: sin punto final
const PREFIX = `${NAMESPACE}.`;
const PATH = '/org/mpris/MediaPlayer2';
const PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player';
const ROOT_IFACE = 'org.mpris.MediaPlayer2';
const PAUSED_MS = 30000;        // en pausa sigue a mano medio minuto para poder reanudar

function unpack(variant) {
    return variant?.deepUnpack?.() ?? variant;
}

class Player {
    constructor(busName, onChange) {
        this.busName = busName;
        this.status = 'Stopped';
        this.appName = busName.slice(PREFIX.length).split('.')[0];
        this._onChange = onChange;
        this._cancellable = new Gio.Cancellable();
        Gio.DBusProxy.new(Gio.DBus.session, Gio.DBusProxyFlags.GET_INVALIDATED_PROPERTIES, null, busName, PATH,
            PLAYER_IFACE, this._cancellable, (_o, result) => {
                try {
                    this._proxy = Gio.DBusProxy.new_finish(result);
                } catch (e) {
                    return;
                }
                this._proxy.connect('g-properties-changed', () => this._read());
                this._read();
            });
        Gio.DBus.session.call(busName, PATH, 'org.freedesktop.DBus.Properties', 'Get',
            new GLib.Variant('(ss)', [ROOT_IFACE, 'Identity']), null, Gio.DBusCallFlags.NONE, -1,
            this._cancellable, (bus, result) => {
                try {
                    this.appName = bus.call_finish(result).deepUnpack()[0].deepUnpack() || this.appName;
                    this._onChange();
                } catch (e) {
                    // sin nombre: se queda el del bus
                }
            });
    }

    _property(name) {
        return unpack(this._proxy?.get_cached_property(name));
    }

    _read() {
        const before = this.status;
        this.status = this._property('PlaybackStatus') ?? 'Stopped';
        const meta = this._property('Metadata') ?? {};
        const trackBefore = this.trackId;
        this.title = unpack(meta['xesam:title']) ?? '';
        const artist = unpack(meta['xesam:artist']);
        this.artist = Array.isArray(artist) ? artist.join(', ') : (artist ?? '');
        this.length = Number(unpack(meta['mpris:length']) ?? 0);
        this.trackId = unpack(meta['mpris:trackid']) ?? null;
        const art = unpack(meta['mpris:artUrl']);
        this.art = art?.startsWith('file://') ? new Gio.FileIcon({file: Gio.File.new_for_uri(art)}) : null;
        this.canSeek = Boolean(this._property('CanSeek')) && this.length > 0;
        this.canNext = this._property('CanGoNext') !== false;
        this.canPrevious = this._property('CanGoPrevious') !== false;
        this.trackChanged = trackBefore !== undefined && trackBefore !== this.trackId;
        if (this.status === 'Playing') {
            this.playedAt = GLib.get_monotonic_time();
            this._stopLinger();
        } else if (before === 'Playing') {
            this._stopLinger();
            this.lingering = true;
            this._lingerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, PAUSED_MS, () => {
                this._lingerId = 0;
                this.lingering = false;
                this._onChange();
                return GLib.SOURCE_REMOVE;
            });
        }
        this._onChange();
    }

    _stopLinger() {
        if (this._lingerId)
            GLib.source_remove(this._lingerId);
        this._lingerId = 0;
        this.lingering = false;
    }

    get ready() {
        return Boolean(this._proxy);
    }

    get visible() {
        return this.ready && (this.status === 'Playing' || this.lingering);
    }

    _call(method, args = null) {
        this._proxy?.call(method, args, Gio.DBusCallFlags.NONE, -1, null, null);
    }

    playPause() {
        this._call('PlayPause');
    }

    next() {
        this._call('Next');
    }

    previous() {
        this._call('Previous');
    }

    // Posición en microsegundos (Position no avisa al cambiar: hay que pedirla).
    fetchPosition(callback) {
        Gio.DBus.session.call(this.busName, PATH, 'org.freedesktop.DBus.Properties', 'Get',
            new GLib.Variant('(ss)', [PLAYER_IFACE, 'Position']), null, Gio.DBusCallFlags.NONE, -1,
            this._cancellable, (bus, result) => {
                try {
                    callback(Number(bus.call_finish(result).deepUnpack()[0].deepUnpack()));
                } catch (e) {
                    callback(null);
                }
            });
    }

    seek(fraction) {
        if (this.canSeek && this.trackId)
            this._call('SetPosition', new GLib.Variant('(ox)', [this.trackId, Math.round(fraction * this.length)]));
    }

    raise() {
        Gio.DBus.session.call(this.busName, PATH, ROOT_IFACE, 'Raise', null, null,
            Gio.DBusCallFlags.NONE, -1, null, null);
    }

    destroy() {
        this._stopLinger();
        this._cancellable.cancel();
        this._proxy = null;
    }
}

export class MediaPlayers extends Signals.EventEmitter {
    constructor() {
        super();
        this._players = new Map();
        this._subscription = Gio.DBus.session.signal_subscribe('org.freedesktop.DBus', 'org.freedesktop.DBus',
            'NameOwnerChanged', '/org/freedesktop/DBus', NAMESPACE, Gio.DBusSignalFlags.MATCH_ARG0_NAMESPACE,
            (_c, _s, _p, _i, _sig, params) => {
                const [name, , owner] = params.deepUnpack();
                if (!name.startsWith(PREFIX))
                    return;
                if (owner)
                    this._add(name);
                else
                    this._remove(name);
            });
        Gio.DBus.session.call('org.freedesktop.DBus', '/org/freedesktop/DBus', 'org.freedesktop.DBus', 'ListNames',
            null, null, Gio.DBusCallFlags.NONE, -1, null, (bus, result) => {
                try {
                    bus.call_finish(result).deepUnpack()[0].filter(n => n.startsWith(PREFIX)).forEach(n => this._add(n));
                } catch (e) {
                    console.warn(`Macify: MPRIS: ${e.message}`);
                }
            });
    }

    _add(name) {
        if (!this._players.has(name))
            this._players.set(name, new Player(name, () => this.emit('changed')));
    }

    _remove(name) {
        if (this._selected === this._players.get(name))
            this._selected = null;
        this._players.get(name)?.destroy();
        this._players.delete(name);
        this.emit('changed');
    }

    // Los que están sonando o en pausa reciente, el último que sonó primero.
    get visible() {
        return [...this._players.values()].filter(p => p.visible)
            .sort((a, b) => (b.playedAt ?? 0) - (a.playedAt ?? 0));
    }

    // El que se controla: el que eligió la persona, o el último que sonó.
    get active() {
        const visible = this.visible;
        return visible.includes(this._selected) ? this._selected : visible[0] ?? null;
    }

    select(player) {
        this._selected = player;
        this.emit('changed');
    }

    destroy() {
        Gio.DBus.session.signal_unsubscribe(this._subscription);
        this._players.forEach(player => player.destroy());
        this._players.clear();
    }
}
