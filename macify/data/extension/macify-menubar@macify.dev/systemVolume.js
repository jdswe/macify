// Volumen del sistema (la salida de audio por defecto), con el mismo control que usa GNOME.
// Si la persona activó «Sobreamplificación» en Ajustes › Sonido, llega hasta el máximo
// amplificado (150 %), como el control de GNOME; si no, hasta el 100 %.

import Gio from 'gi://Gio';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Volume from 'resource:///org/gnome/shell/ui/status/volume.js';

const AMPLIFIED_KEY = 'allow-volume-above-100-percent';
const ICONS = ['audio-volume-muted-symbolic', 'audio-volume-low-symbolic',
    'audio-volume-medium-symbolic', 'audio-volume-high-symbolic'];

export class SystemVolume {
    constructor() {
        this._control = Volume.getMixerControl();
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.sound'});
    }

    get _sink() {
        return this._control?.get_default_sink() ?? null;
    }

    get available() {
        return Boolean(this._sink);
    }

    get amplified() {
        return this._settings.get_boolean(AMPLIFIED_KEY);
    }

    // 1 es el 100 %; con sobreamplificación, el máximo es mayor que 1.
    get maxLevel() {
        const norm = this._control.get_vol_max_norm();
        return (this.amplified ? this._control.get_vol_max_amplified() : norm) / norm;
    }

    get level() {
        const sink = this._sink;
        if (!sink)
            return 0;
        return sink.is_muted ? 0 : sink.volume / this._control.get_vol_max_norm();
    }

    set level(value) {
        const sink = this._sink;
        if (!sink)
            return;
        const level = Math.max(0, Math.min(this.maxLevel, value));
        sink.volume = Math.round(level * this._control.get_vol_max_norm());
        if (sink.is_muted && level > 0)
            sink.change_is_muted(false);
        sink.push_volume();
    }

    get icon() {
        const level = this.level;
        return ICONS[level <= 0 ? 0 : Math.min(3, Math.ceil(level * 3))];
    }

    // Cambia el volumen y lo muestra en pantalla como las teclas de volumen.
    nudge(delta) {
        this.level += delta;
        Main.osdWindowManager.showAll(new Gio.ThemedIcon({name: this.icon}), null, this.level, this.maxLevel);
    }

    // La sobreamplificación puede cambiar mientras tanto en Ajustes.
    onAmplifiedChanged(callback, owner) {
        this._settings.connectObject(`changed::${AMPLIFIED_KEY}`, callback, owner);
    }

    disconnect(owner) {
        this._settings.disconnectObject(owner);
    }
}

// Volumen de una sola app (como el mezclador de macOS/Windows): baja Spotify o YouTube sin
// tocar el volumen general. El reproductor (MPRIS) se empareja con sus flujos de audio por
// nombre: el nombre del bus («spotify», «chromium.instance42»), su Identity («Brave», «Spotify»)
// y lo que la app declara a PipeWire (nombre, id de app, icono).
function words(text) {
    return String(text ?? '').toLowerCase().replace(/\.instance[\w-]*$/, '').split(/[^a-z0-9]+/)
        .filter(w => w.length > 2 && !['org', 'com', 'mpris', 'mediaplayer2', 'instance', 'desktop', 'browser',
            'stable', 'media', 'player'].includes(w));
}

// Navegadores Chromium se anuncian como «chromium» en el bus aunque sean Brave, Chrome o Edge.
const ALIASES = {chromium: ['brave', 'chrome', 'chromium', 'edge', 'vivaldi', 'opera'], brave: ['chromium']};

export class AppVolume {
    constructor() {
        this._control = Volume.getMixerControl();
    }

    _streams(player) {
        if (!player || !this._control)
            return [];
        const wanted = new Set([...words(player.busName?.replace(/^org\.mpris\.MediaPlayer2\./, '')),
            ...words(player.appName)]);
        const streams = this._control.get_sink_inputs().filter(stream => !stream.is_event_stream);
        const matching = names => streams.filter(stream => [...words(stream.get_name()),
            ...words(stream.get_application_id()), ...words(stream.get_icon_name())].some(w => names.has(w)));
        const found = matching(wanted);
        if (found.length || !wanted.size)
            return found;
        // Sólo si su propio nombre no encontró nada: otro navegador de la familia Chromium.
        const aliases = new Set([...wanted].flatMap(word => ALIASES[word] ?? []));
        return aliases.size ? matching(aliases) : [];
    }

    available(player) {
        return this._streams(player).length > 0;
    }

    // 1 es el 100 % del volumen propio de la app (el general aparte).
    level(player) {
        const stream = this._streams(player)[0];
        if (!stream)
            return 0;
        return stream.is_muted ? 0 : stream.volume / this._control.get_vol_max_norm();
    }

    setLevel(player, value) {
        const level = Math.max(0, Math.min(1, value));
        for (const stream of this._streams(player)) {
            stream.volume = Math.round(level * this._control.get_vol_max_norm());
            if (stream.is_muted && level > 0)
                stream.change_is_muted(false);
            stream.push_volume();
        }
    }
}
