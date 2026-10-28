// Selector de pantallas (Super+P o la tecla de proyectar del portátil). Con la tecla del
// portátil no hay modificador que soltar: cada pulsación debe pasar a la siguiente opción y,
// pasado un momento, se aplica la elegida. Dos cosas lo estropeaban:
// - El puntero, quieto bajo la tarjeta, «elegía» la opción que tenía debajo y deshacía el
//   cambio que hacía la tecla. Aquí el puntero sólo elige con un clic.
// - La repetición de la tecla pasaba por varias opciones de golpe. Aquí se ignoran las
//   pulsaciones que llegan casi a la vez.

import GLib from 'gi://GLib';

import * as SwitchMonitor from 'resource:///org/gnome/shell/ui/switchMonitor.js';

const MIN_GAP_MS = 160;

export class DisplaySwitcher {
    constructor() {
        const proto = SwitchMonitor.SwitchMonitorPopup.prototype;
        this._proto = proto;
        this._hover = proto._itemEnteredHandler;
        this._keys = proto._keyPressHandler;
        proto._itemEnteredHandler = function () {};
        const keys = this._keys;
        proto._keyPressHandler = function (keysym, action) {
            const now = GLib.get_monotonic_time() / 1000;
            if (this._macifyLastKey && now - this._macifyLastKey < MIN_GAP_MS)
                return true;                                 // repetición: se traga sin cambiar
            this._macifyLastKey = now;
            return keys.call(this, keysym, action);
        };
    }

    destroy() {
        this._proto._itemEnteredHandler = this._hover;
        this._proto._keyPressHandler = this._keys;
    }
}
