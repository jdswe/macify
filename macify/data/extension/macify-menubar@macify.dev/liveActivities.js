// Live Activities: una cápsula en el centro de la barra que crece con una animación
// elástica cuando pasa algo, como en macOS 27.
// - Música o video sonando en cualquier app: carátula, título y barras de audio. Al pulsar
//   se abre «Ahora suena» (controles y volumen); con la rueda se cambia el volumen.
// - Al enchufar o desenchufar el cargador, carga completa y batería baja.
// - Al perder o recuperar la conexión.
// Todo funciona por avisos del sistema. Las barras se mueven unos segundos al empezar una
// canción o al pasar el puntero, y luego descansan: sin redibujar la barra sin necesidad.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Pango from 'gi://Pango';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

import {_} from './i18n.js';
import {MediaPlayers} from './mediaPlayers.js';
import {NowPlaying} from './nowPlaying.js';
import {SystemVolume} from './systemVolume.js';

const EVENT_MS = 3500;          // lo que dura un aviso (carga, conexión)
const QUIET_START_MS = 6000;    // al iniciar sesión no se avisa de lo que ya estaba así
const VOLUME_STEP = 0.05;
const MAX_TEXT = 44;
// GNOME da a cada lado de la barra como mucho la mitad de lo que deja el centro: si la
// cápsula crece, el lado derecho se aprieta y el reloj se corta. El título se ajusta al
// espacio que queda libre de verdad (entre estos límites, en píxeles lógicos).
const LABEL_MAX_PX = 320;
const LABEL_MIN_PX = 48;
const BARS_STEP_MS = 125;
const RESTING_BARS = [0.55, 0.95, 0.7, 0.45];
const UPOWER_STATE = {CHARGING: 1, DISCHARGING: 2, FULL: 4};

function clip(text) {
    return text.length > MAX_TEXT ? `${text.slice(0, MAX_TEXT - 1)}…` : text;
}

function unpack(variant) {
    return variant?.deepUnpack?.() ?? variant;
}

const LiveButton = GObject.registerClass(
class LiveButton extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'Live Activities', false);
        this.add_style_class_name('macify-live-button');
        this.menu.actor.add_style_class_name('macify-np-menu');

        this.pill = new St.BoxLayout({style_class: 'macify-island', y_align: Clutter.ActorAlign.CENTER});
        this.pill.set_pivot_point(0.5, 0.5);
        this.icon = new St.Icon({style_class: 'macify-island-icon', icon_size: 16, y_align: Clutter.ActorAlign.CENTER});
        this.label = new St.Label({style_class: 'macify-island-label', y_align: Clutter.ActorAlign.CENTER});
        this.label.clutter_text.ellipsize = Pango.EllipsizeMode.END;
        this.bars = new St.BoxLayout({style_class: 'macify-island-bars', y_align: Clutter.ActorAlign.CENTER});
        this.barActors = RESTING_BARS.map(scale => {
            const bar = new St.Widget({style_class: 'macify-island-bar', y_align: Clutter.ActorAlign.END});
            bar.set_pivot_point(0.5, 1);
            bar.scale_y = scale;
            this.bars.add_child(bar);
            return bar;
        });
        [this.icon, this.label, this.bars].forEach(w => this.pill.add_child(w));
        this.add_child(this.pill);
    }
});

export class LiveActivities {
    constructor() {
        this._startedAt = GLib.get_monotonic_time();
        this._event = null;
        this._volume = new SystemVolume();
        this._players = new MediaPlayers();

        this._button = new LiveButton();
        this._button.visible = false;
        this._nowPlaying = new NowPlaying(this._button.menu, this._volume, player => this._players.select(player));
        this._button.connect('scroll-event', (_a, event) => this._onScroll(event));
        Main.panel.addToStatusArea('macify-live', this._button, 0, 'center');
        // Si cambia lo que hay a los lados (otra app, más iconos), el título se reajusta.
        for (const box of [Main.panel._leftBox, Main.panel._rightBox])
            box.connectObject('notify::allocation', () => this._queueFit(), this);
        // Las barras descansan mientras la barra no se ve (pantalla completa o bloqueo).
        global.display.connectObject('in-fullscreen-changed', () => this._wakeBars(), this);
        Main.screenShield?.connectObject?.('locked-changed', () => this._wakeBars(), this);

        this._players.connectObject('changed', () => this._render(), this);
        this._watchPower();
        this._watchPowerNotices();
        this._watchNetwork();
    }

    // ---------- la cápsula ----------

    _render() {
        const player = this._players.active;
        const event = this._event;
        this._button.setSensitive(Boolean(player) && !event);
        if (!player && this._button.menu.isOpen)
            this._button.menu.close();
        if (event) {
            this._show(event.icon, event.text, false);
        } else if (player) {
            this._nowPlaying.show(player, this._players.visible);
            const text = [player.title, player.artist].filter(Boolean).join(' — ') || player.appName;
            this._show(player.art ?? 'audio-x-generic-symbolic', text, player.status === 'Playing');
            this._wakeBars();
            this._lastPlaying = player;
        } else {
            this._lastPlaying = null;
            this._hide();
        }
    }

    _queueFit() {
        this._fitId ??= GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._fitId = null;
            this._fitIsland();
            return GLib.SOURCE_REMOVE;
        });
    }

    _fitIsland() {
        const button = this._button;
        if (!button.visible)
            return;
        const panel = Main.panel;
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const [, left] = panel._leftBox.get_preferred_width(-1);
        const [, right] = panel._rightBox.get_preferred_width(-1);
        const [, center] = panel._centerBox.get_preferred_width(-1);
        const [, label] = button.label.get_preferred_width(-1);
        const room = (panel.width - 2 * Math.max(left, right) - (center - label)) / scale - 8;
        const width = Math.min(LABEL_MAX_PX, Math.floor(room));
        const style = `max-width: ${Math.max(width, 0)}px;`;
        if (button.label.style !== style)
            button.label.style = style;
        button.label.visible = width >= LABEL_MIN_PX;      // sin sitio: sólo icono y barras
    }

    _show(icon, text, playing) {
        const button = this._button;
        if (icon instanceof Gio.Icon)
            button.icon.gicon = icon;
        else
            button.icon.icon_name = icon;
        const changed = button.label.text !== clip(text);
        button.label.text = clip(text);
        this._queueFit();
        button.bars.visible = playing;
        if (!playing)
            this._restBars();
        if (!button.visible) {
            button.visible = true;
            button.pill.opacity = 0;
            button.pill.scale_x = 0.55;
            button.pill.scale_y = 0.7;
            button.pill.ease({
                opacity: 255, scale_x: 1, scale_y: 1, duration: 420,
                mode: Clutter.AnimationMode.EASE_OUT_BACK,
            });
        } else if (changed) {
            button.label.opacity = 0;
            button.label.ease({opacity: 255, duration: 180, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
            button.pill.scale_x = 0.94;
            button.pill.ease({scale_x: 1, duration: 300, mode: Clutter.AnimationMode.EASE_OUT_BACK});
        }
    }

    _hide() {
        this._restBars();
        const button = this._button;
        if (!button.visible)
            return;
        button.pill.ease({
            opacity: 0, scale_x: 0.6, scale_y: 0.8, duration: 220,
            mode: Clutter.AnimationMode.EASE_IN_QUAD,
            onComplete: () => {
                if (button.pill.opacity === 0)
                    button.visible = false;
            },
        });
    }

    // ---------- barras de audio ----------
    // Se mueven todo el tiempo que suena algo, como en macOS (también con otra app delante).
    // Un solo temporizador las cambia 8 veces por segundo, sin animar entre medias: la barra
    // se repinta 8 veces y no 60, y en pausa o con la barra oculta (pantalla completa,
    // bloqueo) se paran del todo.

    get _barsLive() {
        const button = this._button;
        return button.visible && button.bars.visible && !Main.screenShield?.locked &&
            !Main.layoutManager.primaryMonitor?.inFullscreen;
    }

    _wakeBars() {
        if (!this._barsLive || this._barsId)
            return;
        this._button.barActors.forEach(bar => (bar._moving = true));
        this._barsId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, BARS_STEP_MS, () => {
            if (!this._barsLive) {
                this._barsId = 0;
                this._restBars();
                return GLib.SOURCE_REMOVE;
            }
            for (const bar of this._button.barActors)
                bar.scale_y = 0.25 + Math.random() * 0.75;
            return GLib.SOURCE_CONTINUE;
        });
    }

    _restBars() {
        if (this._barsId)
            GLib.source_remove(this._barsId);
        this._barsId = 0;
        this._button.barActors.forEach((bar, i) => {
            bar.remove_all_transitions();
            bar._moving = false;
            bar.scale_y = RESTING_BARS[i];
        });
    }

    // ---------- volumen con la rueda ----------

    _onScroll(event) {
        if (!this._volume.available || !this._players.active)
            return Clutter.EVENT_PROPAGATE;
        const direction = event.get_scroll_direction();
        let delta = 0;
        if (direction === Clutter.ScrollDirection.UP)
            delta = VOLUME_STEP;
        else if (direction === Clutter.ScrollDirection.DOWN)
            delta = -VOLUME_STEP;
        else if (direction === Clutter.ScrollDirection.SMOOTH)
            delta = -event.get_scroll_delta()[1] * VOLUME_STEP;
        if (delta)
            this._volume.nudge(delta);
        return Clutter.EVENT_STOP;
    }

    // ---------- avisos del sistema ----------

    _flash(icon, text) {
        // Al iniciar sesión el estado ya era ese: no se avisa.
        if ((GLib.get_monotonic_time() - this._startedAt) / 1000 < QUIET_START_MS)
            return false;
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
        return true;
    }

    _watchPower() {
        this._powerCancellable = new Gio.Cancellable();
        Gio.DBusProxy.new(Gio.DBus.system, Gio.DBusProxyFlags.NONE, null, 'org.freedesktop.UPower',
            '/org/freedesktop/UPower/devices/DisplayDevice', 'org.freedesktop.UPower.Device',
            this._powerCancellable, (_o, result) => {
                try {
                    this._power = Gio.DBusProxy.new_finish(result);
                } catch (e) {
                    return;
                }
                this._powerState = unpack(this._power.get_cached_property('State'));
                this._power.connectObject('g-properties-changed', () => this._readPower(), this);
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
                this._flash(`battery-level-${step}-symbolic`, `${_('Battery Low')} · ${percent}%`);
            }
        } else {
            this._lowWarned = 0;
        }
    }

    // GNOME avisa «Batería baja» con una notificación; aquí ya lo dice la cápsula, así que el
    // aviso de GNOME se quita y se muestra en la cápsula. Los críticos (el equipo se va a
    // suspender) siguen saliendo como aviso, para no perderlos.
    _watchPowerNotices() {
        const watch = source => {
            const id = `${source.policy?.id ?? ''} ${source.title ?? ''}`;
            if (!/power/i.test(id))
                return;
            source.connectObject('notification-added', (_source, notification) => {
                if (notification.urgency === MessageTray.Urgency.CRITICAL)
                    return;
                const percent = /(\d+)\s*%/.exec(`${notification.body ?? ''} ${notification.title ?? ''}`)?.[1];
                const step = Number(percent) <= 10 ? 10 : 20;
                // Recién iniciada la sesión la cápsula calla: entonces queda el aviso de GNOME.
                if (this._flash(`battery-level-${step}-symbolic`,
                    percent ? `${_('Battery Low')} · ${percent}%` : notification.title ?? _('Battery Low')))
                    notification.destroy();
            }, this);
        };
        Main.messageTray.connectObject('source-added', (_tray, source) => watch(source), this);
        Main.messageTray.getSources().forEach(watch);
    }

    _watchNetwork() {
        this._monitor = Gio.NetworkMonitor.get_default();
        this._online = this._monitor.network_available;
        this._monitor.connectObject('network-changed', () => {
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
        }, this);
    }

    destroy() {
        for (const id of [this._eventId, this._networkTimer]) {
            if (id)
                GLib.source_remove(id);
        }
        global.display.disconnectObject(this);
        Main.screenShield?.disconnectObject?.(this);
        Main.panel._leftBox.disconnectObject(this);
        Main.panel._rightBox.disconnectObject(this);
        if (this._fitId)
            GLib.source_remove(this._fitId);
        this._powerCancellable.cancel();
        this._power?.disconnectObject(this);
        this._monitor.disconnectObject(this);
        Main.messageTray.disconnectObject(this);
        Main.messageTray.getSources().forEach(source => source.disconnectObject(this));
        this._players.disconnectObject(this);
        this._players.destroy();
        this._nowPlaying.destroy();
        this._restBars();
        this._button.destroy();
    }
}
