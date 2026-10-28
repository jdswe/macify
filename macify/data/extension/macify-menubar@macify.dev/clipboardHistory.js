// Historial del portapapeles, como el de macOS: Super+V abre una tarjeta de cristal con lo
// último que copiaste (texto e imágenes). Elige con el puntero, las flechas + Intro o los
// números 1–9 y se pega solo. Al pasar el puntero sobre una fila salen los botones de copiar y
// borrar, y la vista grande de la imagen o del texto completo. «Clear Clipboard» lo vacía.
// Privacidad: todo vive sólo en memoria (nada va a disco, se borra al cerrar la sesión) y no se
// anota lo que se copia desde un gestor de contraseñas.

import Clutter from 'gi://Clutter';
import GdkPixbuf from 'gi://GdkPixbuf';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {imageContent} from './cropEditor.js';
import {monitorAt} from './dockPreview.js';
import {_} from './i18n.js';

const MAX_ITEMS = 20;
const MAX_CHARS = 20000;                    // un texto enorme no se guarda
const MAX_IMAGE_BYTES = 6 * 1024 * 1024;    // ni una imagen enorme
const MAX_IMAGES = 5;
const LABEL_CHARS = 56;
const THUMB_W = 140;
const THUMB_H = 64;
const BIG_W = 480;
const BIG_H = 340;
const PREVIEW_DELAY_MS = 250;
const PASSWORD_APPS = /keepass|bitwarden|1password|seahorse|enpass|proton.?pass|gnome-keyring/i;
const TERMINALS = /terminal|ptyxis|kgx|konsole|tilix|alacritty|kitty|wezterm|xterm|console/i;
const KEYBINDINGS = 'org.gnome.shell.keybindings';
const FREED = ['<Super>m'];                 // Super+V lo usaba GNOME para el centro de avisos
const IMAGE_TYPE = 'image/png';

// Una entrada del historial: texto, o una imagen PNG con su miniatura.
function textItem(text) {
    return {kind: 'text', key: `t:${text}`, text, time: GLib.get_real_time()};
}

// «ahora», «hace 5 min», «hace 2 h»: cuándo se copió.
function ago(time) {
    const minutes = Math.floor((GLib.get_real_time() - time) / 60e6);
    if (minutes < 1)
        return _('now');
    if (minutes < 60)
        return _('{n} min ago', {n: minutes});
    return _('{n} h ago', {n: Math.floor(minutes / 60)});
}

// La imagen se guarda como PNG (para pegarla igual) y, para verla, sólo una copia del tamaño
// de la vista grande: una captura de 1920×1080 decodificada entera ocuparía 8 MB más.
function imageItem(bytes) {
    const loader = new GdkPixbuf.PixbufLoader();
    let width = 0, height = 0;
    loader.connect('size-prepared', (_loader, w, h) => {
        width = w;
        height = h;
        const scale = Math.min(1, BIG_W / w, BIG_H / h);
        loader.set_size(Math.max(1, Math.round(w * scale)), Math.max(1, Math.round(h * scale)));
    });
    try {
        loader.write_bytes(bytes);
        loader.close();
    } catch (e) {
        return null;
    }
    const pixbuf = loader.get_pixbuf();
    if (!pixbuf)
        return null;
    return {kind: 'image', key: `i:${GLib.compute_checksum_for_bytes(GLib.ChecksumType.SHA256, bytes)}`,
        bytes, pixbuf, width, height, time: GLib.get_real_time()};
}

export class ClipboardHistory {
    constructor() {
        this._items = [];
        this._card = null;
        this._clipboard = St.Clipboard.get_default();
        this._keys = new Gio.Settings({schema_id: KEYBINDINGS});
        // GNOME usa Super+V para mostrar los avisos; se le deja Super+M mientras Macify está activo.
        this._savedTray = this._keys.get_strv('toggle-message-tray');
        if (this._savedTray.some(k => k.toLowerCase() === '<super>v'))
            this._keys.set_strv('toggle-message-tray', FREED);
        else
            this._savedTray = null;
        global.display.get_selection().connectObject('owner-changed', (_selection, type) => {
            if (type === Meta.SelectionType.SELECTION_CLIPBOARD)
                this._read();
        }, this);
        this._grab(3);
    }

    // Un atajo del sistema (como las teclas de volumen): llega aunque una app tenga el foco.
    // GNOME suelta su Super+V un instante después de cambiar el ajuste: si aún lo tiene, se
    // vuelve a intentar.
    _grab(tries) {
        const action = global.display.grab_accelerator('<Super>v', Meta.KeyBindingFlags.NONE);
        if (action === Meta.KeyBindingAction.NONE) {
            if (tries > 1) {
                this._grabId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
                    this._grabId = 0;
                    this._grab(tries - 1);
                    return GLib.SOURCE_REMOVE;
                });
            } else {
                console.warn('Macify: Super+V is taken by another shortcut');
            }
            return;
        }
        this._accelerator = action;
        Main.wm.allowKeybinding(Meta.external_binding_name_for_action(action),
            Shell.ActionMode.NORMAL | Shell.ActionMode.OVERVIEW);
        global.display.connectObject('accelerator-activated', (_display, activated) => {
            if (activated === this._accelerator && !this._card && !Main.sessionMode.isLocked)
                this.open();
        }, this);
    }

    _read() {
        const focus = global.display.focus_window;
        if (PASSWORD_APPS.test(focus?.get_wm_class() ?? '') || Main.sessionMode.isLocked)
            return;
        const types = this._clipboard.get_mimetypes(St.ClipboardType.CLIPBOARD);
        if (types.includes(IMAGE_TYPE)) {
            this._clipboard.get_content(St.ClipboardType.CLIPBOARD, IMAGE_TYPE, (_clipboard, bytes) => {
                if (bytes && bytes.get_size() <= MAX_IMAGE_BYTES)
                    this._add(imageItem(bytes));
            });
        } else {
            this._clipboard.get_text(St.ClipboardType.CLIPBOARD, (_clipboard, text) => {
                if (text?.trim() && text.length <= MAX_CHARS)
                    this._add(textItem(text));
            });
        }
    }

    _add(item) {
        if (!item)
            return;
        const rest = this._items.filter(i => i.key !== item.key);
        let images = 0;
        this._items = [item, ...rest].filter(i => i.kind !== 'image' || ++images <= MAX_IMAGES).slice(0, MAX_ITEMS);
    }

    // ---------- tarjeta ----------

    open() {
        if (this._card)
            return;
        const card = new St.BoxLayout({style_class: 'macify-clip', vertical: true, reactive: true, can_focus: true});
        const header = new St.BoxLayout({style_class: 'macify-clip-header'});
        header.add_child(new St.Icon({icon_name: 'edit-paste-symbolic', icon_size: 16, style_class: 'macify-clip-icon'}));
        header.add_child(new St.Label({text: _('Clipboard'), style_class: 'macify-clip-title', x_expand: true,
            y_align: Clutter.ActorAlign.CENTER}));
        const clear = new St.Button({label: _('Clear Clipboard'), style_class: 'macify-clip-clear'});
        clear.connect('clicked', () => {
            this._items = [];
            this._close();
        });
        header.add_child(clear);
        card.add_child(header);
        this._rows = [];
        if (this._items.length === 0)
            card.add_child(new St.Label({text: _('Nothing copied yet'), style_class: 'macify-clip-empty'}));
        this._items.forEach((item, i) => card.add_child(this._row(item, i)));
        if (this._items.length)
            card.add_child(new St.Label({text: _('↑↓ choose · Enter paste · Delete remove · Esc close'),
                style_class: 'macify-clip-hint'}));
        card.connect('key-press-event', (_actor, event) => this._navigate(event));
        Main.uiGroup.add_child(card);
        this._card = card;
        const monitor = Main.layoutManager.currentMonitor ?? Main.layoutManager.primaryMonitor;
        const [width, height] = card.get_size();
        card.set_position(Math.round(monitor.x + (monitor.width - width) / 2),
            Math.round(Math.max(monitor.y + 40, monitor.y + monitor.height * 0.28 - height / 4)));
        this._grab = Main.pushModal(card);
        this._previous = global.display.focus_window;
        this._selected = 0;
        this._mark();
        // Un clic fuera la cierra.
        this._outside = global.stage.connect('captured-event', (_stage, event) => {
            if (event.type() === Clutter.EventType.BUTTON_PRESS) {
                const target = global.stage.get_actor_at_pos(Clutter.PickMode.REACTIVE, ...event.get_coords());
                if (!card.contains(target) && !this._big?.contains(target))
                    this._close();
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    _row(item, index) {
        const row = new St.BoxLayout({style_class: 'macify-clip-row', track_hover: true, reactive: true});
        const open = new St.Button({style_class: 'macify-clip-open', x_expand: true, x_align: Clutter.ActorAlign.FILL});
        const line = new St.BoxLayout({x_expand: true, x_align: Clutter.ActorAlign.START});
        line.add_child(new St.Label({text: index < 9 ? `${index + 1}` : '', style_class: 'macify-clip-number',
            y_align: Clutter.ActorAlign.CENTER}));
        if (item.kind === 'image') {
            const {width, height} = item.pixbuf;          // copia reducida; el tamaño real va en item
            const scale = Math.min(THUMB_W / width, THUMB_H / height, 1);
            line.add_child(new St.Widget({
                style_class: 'macify-clip-thumb', content: imageContent(item.pixbuf),
                content_gravity: Clutter.ContentGravity.RESIZE_ASPECT,
                width: Math.round(width * scale), height: Math.round(height * scale),
            }));
            line.add_child(this._describe(_('Image'), `${item.width} × ${item.height} · ${ago(item.time)}`));
        } else {
            const chars = item.text.length;
            line.add_child(this._describe(this._label(item.text),
                `${chars === 1 ? _('1 character') : _('{n} characters', {n: chars})} · ${ago(item.time)}`));
        }
        open.set_child(line);
        open.connect('clicked', () => this._choose(item));
        row.add_child(open);

        // Copiar y borrar, a la vista sólo con el puntero encima.
        const actions = new St.BoxLayout({style_class: 'macify-clip-actions', y_align: Clutter.ActorAlign.CENTER, opacity: 0});
        const copy = this._action('edit-copy-symbolic', () => {
            this._close();
            this._set(item);
        });
        const trash = this._action('user-trash-symbolic', () => {
            this._items = this._items.filter(i => i !== item);
            this._close();
            this.open();
        });
        actions.add_child(copy);
        actions.add_child(trash);
        row.add_child(actions);
        row.connect('notify::hover', () => {
            actions.opacity = row.hover ? 255 : 0;
            if (row.hover) {
                this._selected = this._rows.indexOf(row);
                this._mark();
                this._schedulePreview(item, row);
            } else {
                this._hidePreview();
            }
        });
        this._rows.push(row);
        return row;
    }

    _describe(title, detail) {
        const column = new St.BoxLayout({vertical: true, y_align: Clutter.ActorAlign.CENTER});
        column.add_child(new St.Label({text: title, style_class: 'macify-clip-text'}));
        column.add_child(new St.Label({text: detail, style_class: 'macify-clip-detail'}));
        return column;
    }

    _action(icon, callback) {
        const button = new St.Button({style_class: 'macify-clip-action', child: new St.Icon({icon_name: icon, icon_size: 14})});
        button.connect('clicked', callback);
        return button;
    }

    _label(text) {
        const line = text.trim().replace(/\s+/g, ' ');
        return line.length > LABEL_CHARS ? `${line.slice(0, LABEL_CHARS - 1)}…` : line;
    }

    // Vista grande al lado: la imagen entera, o el texto completo si no cabía en una línea.
    _schedulePreview(item, row) {
        this._hidePreview();
        if (item.kind === 'text' && this._label(item.text) === item.text.trim())
            return;
        this._previewId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, PREVIEW_DELAY_MS, () => {
            this._previewId = 0;
            this._showPreview(item, row);
            return GLib.SOURCE_REMOVE;
        });
    }

    _showPreview(item, row) {
        if (!this._card)
            return;
        const big = new St.BoxLayout({style_class: 'macify-clip-big', reactive: false});
        if (item.kind === 'image') {
            const {width, height} = item.pixbuf;
            const scale = Math.min(BIG_W / width, BIG_H / height, 1);
            big.add_child(new St.Widget({
                content: imageContent(item.pixbuf), content_gravity: Clutter.ContentGravity.RESIZE_ASPECT,
                width: Math.round(width * scale), height: Math.round(height * scale),
            }));
        } else {
            const label = new St.Label({text: item.text.slice(0, 1200), style_class: 'macify-clip-fulltext'});
            label.clutter_text.line_wrap = true;
            big.add_child(label);
        }
        Main.uiGroup.add_child(big);
        const [cx, cy] = this._card.get_transformed_position();
        const [cw] = this._card.get_transformed_size();
        const [, ry] = row.get_transformed_position();
        const [bw, bh] = big.get_size();
        const monitor = monitorAt(cx + cw / 2, cy);
        const right = cx + cw + 10;
        const x = right + bw <= monitor.x + monitor.width ? right : cx - bw - 10;
        big.set_position(Math.round(x), Math.round(Math.max(monitor.y + 36,
            Math.min(ry - bh / 2, monitor.y + monitor.height - bh - 12))));
        this._big = big;
    }

    _hidePreview() {
        if (this._previewId)
            GLib.source_remove(this._previewId);
        this._previewId = 0;
        this._big?.destroy();
        this._big = null;
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
        } else if (symbol === Clutter.KEY_Delete && count) {
            this._items.splice(this._selected, 1);
            this._close();
            this.open();
        } else if (symbol >= Clutter.KEY_1 && symbol <= Clutter.KEY_9 && symbol - Clutter.KEY_1 < count) {
            this._choose(this._items[symbol - Clutter.KEY_1]);
        }
        return Clutter.EVENT_STOP;
    }

    _set(item) {
        if (item.kind === 'image')
            this._clipboard.set_content(St.ClipboardType.CLIPBOARD, IMAGE_TYPE, item.bytes);
        else
            this._clipboard.set_text(St.ClipboardType.CLIPBOARD, item.text);
        this._add(item);
    }

    // Deja lo elegido en el portapapeles, vuelve a la ventana de antes y lo pega.
    _choose(item) {
        const target = this._previous;
        this._close();
        this._set(item);
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
        this._hidePreview();
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
        global.display.disconnectObject(this);
        if (this._grabId)
            GLib.source_remove(this._grabId);
        if (this._accelerator) {
            Main.wm.allowKeybinding(Meta.external_binding_name_for_action(this._accelerator), Shell.ActionMode.NONE);
            global.display.ungrab_accelerator(this._accelerator);
        }
        if (this._savedTray)
            this._keys.set_strv('toggle-message-tray', this._savedTray);
        this._items = [];
    }
}
