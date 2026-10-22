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
