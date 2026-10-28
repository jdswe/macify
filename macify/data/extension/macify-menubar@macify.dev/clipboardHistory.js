// Historial del portapapeles, como el de macOS: Super+V abre una tarjeta de cristal con lo
// último que copiaste; elige con el puntero, las flechas + Intro o los números 1–9 y se pega
// solo. Privacidad: sólo texto, sólo en memoria (nada se guarda en disco y se borra al cerrar
// la sesión), no se anota lo que se copia desde un gestor de contraseñas, y «Clear» lo vacía.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {_} from './i18n.js';

const MAX_ITEMS = 20;
const MAX_CHARS = 20000;                    // un texto enorme no se guarda
const LABEL_CHARS = 64;
const PASSWORD_APPS = /keepass|bitwarden|1password|seahorse|enpass|proton.?pass|gnome-keyring/i;
const TERMINALS = /terminal|ptyxis|kgx|konsole|tilix|alacritty|kitty|wezterm|xterm|console/i;
const KEYBINDINGS = 'org.gnome.shell.keybindings';
const FREED = ['<Super>m'];                 // Super+V lo usaba GNOME para el centro de avisos

export class ClipboardHistory {
    constructor() {
        this._items = [];
        this._card = null;
        this._clipboard = St.Clipboard.get_default();
        this._keys = new Gio.Settings({schema_id: KEYBINDINGS});
        // GNOME usa Super+V para mostrar los avisos; se le deja Super+M mientras Macify está activo.
        this._savedTray = this._keys.get_strv('toggle-message-tray');
        if (this._savedTray.includes('<Super>v') || this._savedTray.includes('<Super>V'))
            this._keys.set_strv('toggle-message-tray', FREED);
        else
            this._savedTray = null;
        global.display.get_selection().connectObject('owner-changed', (_selection, type) => {
            if (type === Meta.SelectionType.SELECTION_CLIPBOARD)
                this._read();
        }, this);
        global.stage.connectObject('captured-event', (_stage, event) => this._key(event), this);
    }

    _key(event) {
        if (event.type() !== Clutter.EventType.KEY_PRESS || this._card)
            return Clutter.EVENT_PROPAGATE;
        const super_ = event.get_state() & Clutter.ModifierType.SUPER_MASK;
        const symbol = event.get_key_symbol();
        if (super_ && (symbol === Clutter.KEY_v || symbol === Clutter.KEY_V) && !Main.sessionMode.isLocked) {
            this.open();
            return Clutter.EVENT_STOP;
        }
        return Clutter.EVENT_PROPAGATE;
    }

    _read() {
        const focus = global.display.focus_window;
        if (PASSWORD_APPS.test(focus?.get_wm_class() ?? '') || Main.sessionMode.isLocked)
            return;
        this._clipboard.get_text(St.ClipboardType.CLIPBOARD, (_clipboard, text) => this._add(text));
    }

    _add(text) {
        if (!text?.trim() || text.length > MAX_CHARS)
            return;
        this._items = [text, ...this._items.filter(t => t !== text)].slice(0, MAX_ITEMS);
    }

    open() {
        if (this._card)
            return;
        const card = new St.BoxLayout({style_class: 'macify-clip', vertical: true, reactive: true, can_focus: true});
        const header = new St.BoxLayout({style_class: 'macify-clip-header'});
        header.add_child(new St.Label({text: _('Clipboard'), style_class: 'macify-clip-title', x_expand: true}));
        const clear = new St.Button({label: _('Clear'), style_class: 'macify-clip-clear'});
        clear.connect('clicked', () => {
            this._items = [];
            this._close();
        });
        header.add_child(clear);
        card.add_child(header);
        this._rows = [];
        if (this._items.length === 0)
            card.add_child(new St.Label({text: _('Nothing copied yet'), style_class: 'macify-clip-empty'}));
        this._items.forEach((text, i) => {
            const row = new St.Button({style_class: 'macify-clip-row', x_expand: true, x_align: Clutter.ActorAlign.FILL});
            const line = new St.BoxLayout({x_expand: true, x_align: Clutter.ActorAlign.START});
            line.add_child(new St.Label({text: i < 9 ? `${i + 1}` : '', style_class: 'macify-clip-number'}));
            line.add_child(new St.Label({text: this._label(text), y_align: Clutter.ActorAlign.CENTER}));
            row.set_child(line);
            row.connect('clicked', () => this._choose(text));
            card.add_child(row);
            this._rows.push(row);
        });
        card.connect('key-press-event', (_actor, event) => this._navigate(event));
        Main.uiGroup.add_child(card);
        const monitor = Main.layoutManager.currentMonitor ?? Main.layoutManager.primaryMonitor;
        const [width, height] = card.get_size();
        card.set_position(Math.round(monitor.x + (monitor.width - width) / 2),
            Math.round(monitor.y + monitor.height * 0.28 - height / 4));
        this._grab = Main.pushModal(card);
        this._previous = global.display.focus_window;
        this._card = card;
        this._selected = 0;
        this._mark();
        // Un clic fuera la cierra.
        card.connectObject('button-press-event', () => Clutter.EVENT_STOP, this);
        this._outside = global.stage.connect('captured-event', (_stage, event) => {
            if (event.type() === Clutter.EventType.BUTTON_PRESS) {
                const target = global.stage.get_actor_at_pos(Clutter.PickMode.REACTIVE, ...event.get_coords());
                if (!card.contains(target))
                    this._close();
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    _label(text) {
        const line = text.trim().replace(/\s+/g, ' ');
        return line.length > LABEL_CHARS ? `${line.slice(0, LABEL_CHARS - 1)}…` : line;
    }

    _mark() {
        this._rows.forEach((row, i) => {
            if (i === this._selected)
                row.add_style_pseudo_class('selected');
            else
                row.remove_style_pseudo_class('selected');
        });
    }

    _navigate(event) {
        const symbol = event.get_key_symbol();
        const count = this._rows.length;
        if (symbol === Clutter.KEY_Escape) {
            this._close();
        } else if (symbol === Clutter.KEY_Down && count) {
            this._selected = (this._selected + 1) % count;
            this._mark();
        } else if (symbol === Clutter.KEY_Up && count) {
            this._selected = (this._selected + count - 1) % count;
            this._mark();
        } else if ((symbol === Clutter.KEY_Return || symbol === Clutter.KEY_KP_Enter) && count) {
            this._choose(this._items[this._selected]);
        } else if (symbol >= Clutter.KEY_1 && symbol <= Clutter.KEY_9 && symbol - Clutter.KEY_1 < count) {
            this._choose(this._items[symbol - Clutter.KEY_1]);
        }
        return Clutter.EVENT_STOP;
    }

    // Deja el texto elegido en el portapapeles, vuelve a la ventana de antes y lo pega.
    _choose(text) {
        const target = this._previous;
        this._close();
        this._clipboard.set_text(St.ClipboardType.CLIPBOARD, text);
        this._add(text);
        this._pasteId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 160, () => {
            this._pasteId = 0;
            this._paste(target);
            return GLib.SOURCE_REMOVE;
        });
    }

    _paste(target) {
        const window = global.display.focus_window ?? target;
        const terminal = TERMINALS.test(window?.get_wm_class() ?? '');
        this._device ??= Clutter.get_default_backend().get_default_seat()
            .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        const keys = terminal ? [Clutter.KEY_Control_L, Clutter.KEY_Shift_L, Clutter.KEY_v]
            : [Clutter.KEY_Control_L, Clutter.KEY_v];
        const press = (key, state) => this._device.notify_keyval(GLib.get_monotonic_time(), key, state);
        keys.forEach(key => press(key, Clutter.KeyState.PRESSED));
        [...keys].reverse().forEach(key => press(key, Clutter.KeyState.RELEASED));
    }

    _close() {
        if (this._outside)
            global.stage.disconnect(this._outside);
        this._outside = 0;
        if (this._grab) {
            Main.popModal(this._grab);
            this._grab = null;
        }
        this._card?.destroy();
        this._card = null;
        this._rows = [];
    }

    destroy() {
        this._close();
        if (this._pasteId)
            GLib.source_remove(this._pasteId);
        global.display.get_selection().disconnectObject(this);
        global.stage.disconnectObject(this);
        if (this._savedTray)
            this._keys.set_strv('toggle-message-tray', this._savedTray);
        this._items = [];
    }
}
