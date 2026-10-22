// Atajos de teclado: mandarlos a una ventana y mostrarlos con los símbolos de macOS.
// Un atajo se escribe como en GTK: '<Ctrl><Shift>z', 'F11', '<Alt>Left'.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';

const SEND_DELAY_MS = 120;      // espera a que el menú se cierre y la ventana recupere el teclado

const MODIFIERS = {
    Ctrl: {key: Clutter.KEY_Control_L, glyph: '⌃'},
    Alt: {key: Clutter.KEY_Alt_L, glyph: '⌥'},
    Shift: {key: Clutter.KEY_Shift_L, glyph: '⇧'},
    Super: {key: Clutter.KEY_Super_L, glyph: '⌘'},
};
const MODIFIER_ORDER = ['Ctrl', 'Alt', 'Shift', 'Super'];      // el orden de macOS: ⌃⌥⇧⌘
const KEY_GLYPHS = {
    plus: '+', minus: '−', comma: ',', period: '.', question: '?', Left: '←', Right: '→', Up: '↑',
    Down: '↓', Delete: '⌦', BackSpace: '⌫', Return: '↩', Escape: '⎋', Tab: '⇥',
};

let device = null;

function parse(accel) {
    const modifiers = [];
    const key = accel.replace(/<(\w+)>/g, (_m, name) => {
        modifiers.push(name);
        return '';
    });
    return {modifiers, key};
}

function keyval(key) {
    return key.length === 1 ? Clutter.unicode_to_keysym(key.codePointAt(0)) : Clutter[`KEY_${key}`];
}

function press(accel) {
    device ??= Clutter.get_default_backend().get_default_seat()
        .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
    const {modifiers, key} = parse(accel);
    const keys = [...modifiers.map(m => MODIFIERS[m].key), keyval(key)];
    let time = GLib.get_monotonic_time();
    for (const k of keys)
        device.notify_keyval(time++, k, Clutter.KeyState.PRESSED);
    for (const k of keys.reverse())
        device.notify_keyval(time++, k, Clutter.KeyState.RELEASED);
}

// Devuelve el foco a la ventana y le manda el atajo cuando el menú ya se cerró.
export function sendShortcut(win, accel) {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, SEND_DELAY_MS, () => {
        if (win && !win.has_focus())
            win.activate(global.get_current_time());
        press(accel);
        return GLib.SOURCE_REMOVE;
    });
}

// '<Ctrl><Shift>z' → '⌃⇧Z'
export function glyphs(accel) {
    const {modifiers, key} = parse(accel);
    const ordered = MODIFIER_ORDER.filter(m => modifiers.includes(m)).map(m => MODIFIERS[m].glyph).join('');
    return ordered + (KEY_GLYPHS[key] ?? (key.length === 1 ? key.toUpperCase() : key));
}

// ¿Está pulsada la tecla Alt (la Opción de macOS)?
export function optionPressed() {
    const [, , mods] = global.get_pointer();
    return Boolean(mods & Clutter.ModifierType.MOD1_MASK);
}

export function dispose() {
    device?.run_dispose?.();
    device = null;
}
