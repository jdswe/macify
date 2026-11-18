// Dictado en la isla (si está instalado): mientras dictas, un micrófono con barras que siguen
// tu voz; mientras convierte la voz en texto, «Escribiendo…»; durante una transcripción,
// «REC» con el tiempo. Un clic detiene lo que esté en marcha.
// Sólo se escuchan las señales que Dictado publica en D-Bus: no se arranca su servicio, no se
// toca el audio y el texto lo escribe la propia extensión de Dictado.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Signals from 'resource:///org/gnome/shell/misc/signals.js';

const BUS_NAME = 'dev.dictado.Dictado';
const PATH = '/dev/dictado/Dictado';
const IFACE = 'dev.dictado.Dictado1';

export class DictadoStatus extends Signals.EventEmitter {
    constructor() {
        super();
        this.dictation = 'idle';            // idle | recording | processing
        this.transcription = 'idle';        // idle | recording
        this.started = 0;                   // inicio de la transcripción, ms Unix
        this.level = 0;
        const bus = Gio.DBus.session;
        this._signals = [
            bus.signal_subscribe(BUS_NAME, IFACE, 'StateChanged', PATH, null, Gio.DBusSignalFlags.NONE,
                (...args) => this._onState(args[5].deepUnpack())),
            bus.signal_subscribe(BUS_NAME, IFACE, 'Level', PATH, null, Gio.DBusSignalFlags.NONE,
                (...args) => {
                    this.level = Math.max(0, Math.min(1, args[5].deepUnpack()[0]));
                    this.emit('level');
                }),
        ];
        // Al aparecer el servicio (o si ya estaba), se lee su estado una vez.
        this._watch = Gio.bus_watch_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameWatcherFlags.NONE,
            () => this._readState(), () => this._onState(['idle', 'idle']));
    }

    _readState() {
        Gio.DBus.session.call(BUS_NAME, PATH, 'org.freedesktop.DBus.Properties', 'GetAll',
            new GLib.Variant('(s)', [IFACE]), null, Gio.DBusCallFlags.NO_AUTO_START, 3000, null,
            (bus, result) => {
                try {
                    const props = bus.call_finish(result).deepUnpack()[0];
                    this.started = Number(props.TranscriptionStarted?.deepUnpack?.() ?? 0);
                    this._onState([props.Dictation?.deepUnpack?.() ?? 'idle',
                        props.Transcription?.deepUnpack?.() ?? 'idle']);
                } catch (e) {
                    // sin servicio: queda en reposo
                }
            });
    }

    _onState([dictation, transcription]) {
        if (transcription === 'recording' && this.transcription !== 'recording' && !this.started) {
            // La hora real de inicio la da Dictado; mientras llega, la de ahora.
            this.started = Date.now();
            this._readStarted();
        }
        if (transcription !== 'recording')
            this.started = 0;
        if (dictation !== 'recording')
            this.level = 0;
        this.dictation = dictation;
        this.transcription = transcription;
        this.emit('changed');
    }

    _readStarted() {
        Gio.DBus.session.call(BUS_NAME, PATH, 'org.freedesktop.DBus.Properties', 'Get',
            new GLib.Variant('(ss)', [IFACE, 'TranscriptionStarted']), null, Gio.DBusCallFlags.NO_AUTO_START,
            3000, null, (bus, result) => {
                try {
                    const started = Number(bus.call_finish(result).deepUnpack()[0].deepUnpack());
                    if (started > 0 && this.transcription === 'recording') {
                        this.started = started;
                        this.emit('changed');
                    }
                } catch (e) {
                    // se queda la hora local
                }
            });
    }

    get busy() {
        return this.dictation !== 'idle' || this.transcription === 'recording';
    }

    // Clic en la isla: termina el dictado (y lo escribe) o detiene la transcripción.
    stop() {
        const method = this.dictation === 'recording' ? 'StopDictation'
            : this.transcription === 'recording' ? 'StopTranscription' : null;
        if (!method)
            return;
        Gio.DBus.session.call(BUS_NAME, PATH, IFACE, method, null, null, Gio.DBusCallFlags.NO_AUTO_START,
            5000, null, (bus, result) => {
                try {
                    bus.call_finish(result);
                } catch (e) {
                    console.warn(`Macify: Dictado ${method}: ${e.message}`);
                }
            });
    }

    destroy() {
        this._signals.forEach(id => Gio.DBus.session.signal_unsubscribe(id));
        Gio.bus_unwatch_name(this._watch);
    }
}
