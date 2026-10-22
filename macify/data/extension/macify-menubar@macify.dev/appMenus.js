// Menús de app como los de macOS: el nombre de la app en negrita y File, Edit, View, Go,
// Window y Help. Sirven en cualquier app (apt, snap, flatpak, AppImage): las órdenes de
// edición mandan a la ventana activa sus atajos de siempre y las de ventana actúan
// directamente sobre ella. Cada menú se arma al abrirlo, así que no gasta nada cerrado.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

import {_} from './i18n.js';

const FILES_APP = 'org.gnome.Nautilus.desktop';
// En las terminales copiar y pegar llevan Mayúsculas (Ctrl+C interrumpe el programa).
const TERMINALS = new Set([
    'org.gnome.Ptyxis.desktop', 'org.gnome.Terminal.desktop', 'org.gnome.Console.desktop',
    'com.mitchellh.ghostty.desktop', 'kitty.desktop', 'Alacritty.desktop', 'org.wezfurlong.wezterm.desktop',
    'org.kde.konsole.desktop', 'terminator.desktop', 'com.gexperts.Tilix.desktop', 'xterm.desktop',
]);
const SEND_DELAY_MS = 120;      // espera a que el menú se cierre y la ventana recupere el teclado

const MODIFIERS = {
    Ctrl: Clutter.KEY_Control_L,
    Shift: Clutter.KEY_Shift_L,
    Alt: Clutter.KEY_Alt_L,
    Super: Clutter.KEY_Super_L,
};

let keyboard = null;

function virtualKeyboard() {
    keyboard ??= Clutter.get_default_backend().get_default_seat()
        .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
    return keyboard;
}

// '<Ctrl><Shift>z' → teclas para pulsar en orden.
function parseShortcut(accel) {
    const keys = [];
    const key = accel.replace(/<(\w+)>/g, (_m, name) => {
        keys.push(MODIFIERS[name]);
        return '';
    });
    keys.push(key.length === 1 ? Clutter.unicode_to_keysym(key.codePointAt(0)) : Clutter[`KEY_${key}`]);
    return keys;
}

function pressShortcut(accel) {
    const device = virtualKeyboard();
    const keys = parseShortcut(accel);
    let time = GLib.get_monotonic_time();
    for (const key of keys)
        device.notify_keyval(time++, key, Clutter.KeyState.PRESSED);
    for (const key of keys.reverse())
        device.notify_keyval(time++, key, Clutter.KeyState.RELEASED);
}

// Devuelve el foco a la ventana y le manda el atajo cuando el menú ya se cerró.
function sendShortcut(win, accel) {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, SEND_DELAY_MS, () => {
        if (win && !win.has_focus())
            win.activate(global.get_current_time());
        pressShortcut(accel);
        return GLib.SOURCE_REMOVE;
    });
}

function openUri(uri) {
    try {
        Gio.AppInfo.launch_default_for_uri(uri, global.create_app_launch_context(0, -1));
    } catch (e) {
        console.warn(`Macify: ${uri}: ${e.message}`);
    }
}

function folderUri(directory) {
    const path = directory === null ? GLib.get_home_dir() : GLib.get_user_special_dir(directory);
    return path ? Gio.File.new_for_path(path).get_uri() : null;
}

function otherMonitor(win) {
    const count = global.display.get_n_monitors();
    if (!win || count < 2)
        return -1;
    return (win.get_monitor() + 1) % count;
}

function monitorName(index) {
    return index === Main.layoutManager.primaryIndex ? _('Main Display') : _('Display {n}', {n: index + 1});
}

// Un menú de la barra con un título de texto.
const BarMenu = GObject.registerClass(
class BarMenu extends PanelMenu.Button {
    _init(title, build, bold = false) {
        super._init(0.0, title, false);
        this._build = build;
        this._label = new St.Label({
            text: title,
            y_align: Clutter.ActorAlign.CENTER,
            style_class: bold ? 'macify-app-title' : 'macify-menu-title',
        });
        this.add_child(this._label);
        this.add_style_class_name('macify-menu-button');
        this.menu.actor.add_style_class_name('macify-app-menu');
        this.menu.connect('open-state-changed', (_menu, open) => {
            if (open)
                this._refill();
        });
    }

    setTitle(text) {
        this._label.text = text;
    }

    _refill() {
        this.menu.removeAll();
        const target = currentTarget();
        for (const entry of this._build(target)) {
            if (entry === null) {
                this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
                continue;
            }
            const item = new PopupMenu.PopupMenuItem(entry.label);
            if (entry.shortcut) {
                item.add_child(new St.Label({
                    text: entry.shortcut, x_expand: true, x_align: Clutter.ActorAlign.END,
                    style_class: 'macify-menu-shortcut',
                }));
            }
            if (entry.checked)
                item.setOrnament(PopupMenu.Ornament.CHECK);
            item.setSensitive(entry.enabled !== false);
            item.connect('activate', () => entry.run());
            this.menu.addMenuItem(item);
        }
    }
});

// La app y la ventana a las que van las órdenes. Sin ventana activa, Archivos (como Finder).
function currentTarget() {
    const tracker = Shell.WindowTracker.get_default();
    const win = global.display.focus_window;
    const focused = tracker.focus_app;
    const app = focused ?? Shell.AppSystem.get_default().lookup_app(FILES_APP);
    const id = app?.get_id() ?? '';
    return {
        app,
        win: focused ? win : null,
        name: app?.get_name() ?? _('Files'),
        terminal: TERMINALS.has(id),
        files: id === FILES_APP,
    };
}

// Atajo que se ve en el menú, al estilo de macOS (⌘ es Ctrl en Ubuntu).
function display(accel) {
    return accel.replace('<Ctrl>', 'Ctrl+').replace('<Shift>', 'Shift+').replace('<Alt>', 'Alt+')
        .replace('<Super>', 'Super+').replace('plus', '+').replace('minus', '−').replace('comma', ',')
        .replace('period', '.').replace(/\+([a-z])$/, (_m, c) => `+${c.toUpperCase()}`);
}

function key(label, accel, t, extra = {}) {
    return {label, shortcut: display(accel), enabled: Boolean(t.win), run: () => sendShortcut(t.win, accel), ...extra};
}

function appMenu(t) {
    const others = () => global.display.list_all_windows()
        .filter(w => !w.minimized && w.can_minimize() && Shell.WindowTracker.get_default().get_window_app(w) !== t.app);
    return [
        {label: _('About {app}', {app: t.name}), enabled: Boolean(t.app),
            run: () => Util.spawn(['gnome-control-center', 'applications', t.app.get_id().replace(/\.desktop$/, '')])},
        null,
        key(_('Settings…'), '<Ctrl>comma', t),
        null,
        {label: _('Hide {app}', {app: t.name}), shortcut: 'Ctrl+H', enabled: Boolean(t.win),
            run: () => t.app.get_windows().forEach(w => w.can_minimize() && w.minimize())},
        {label: _('Hide Others'), run: () => others().forEach(w => w.minimize())},
        {label: _('Show All'), run: () => global.display.list_all_windows()
            .forEach(w => w.minimized && w.unminimize())},
        null,
        {label: _('Quit {app}', {app: t.name}), shortcut: 'Ctrl+Q', enabled: Boolean(t.app?.get_n_windows()),
            run: () => t.app.request_quit()},
    ];
}

function fileMenu(t) {
    const newWindow = {
        label: _('New Window'), shortcut: display(t.terminal ? '<Ctrl><Shift>n' : '<Ctrl>n'), enabled: Boolean(t.app),
        run: () => (t.app.can_open_new_window() ? t.app.open_new_window(-1)
            : sendShortcut(t.win, t.terminal ? '<Ctrl><Shift>n' : '<Ctrl>n')),
    };
    const entries = [newWindow];
    if (t.files)
        entries.push(key(_('New Folder'), '<Ctrl><Shift>n', t));
    else
        entries.push(key(_('New Tab'), t.terminal ? '<Ctrl><Shift>t' : '<Ctrl>t', t));
    if (!t.terminal && !t.files)
        entries.push(key(_('Open…'), '<Ctrl>o', t));
    if (!t.terminal && !t.files) {
        entries.push(null, key(_('Save'), '<Ctrl>s', t), key(_('Save As…'), '<Ctrl><Shift>s', t),
            null, key(_('Print…'), '<Ctrl>p', t));
    }
    entries.push(null, {label: _('Close Window'), shortcut: 'Ctrl+W', enabled: Boolean(t.win?.can_close()),
        run: () => t.win.delete(global.get_current_time())});
    return entries;
}

function editMenu(t) {
    const shift = t.terminal ? '<Shift>' : '';
    const entries = [key(_('Undo'), '<Ctrl>z', t), key(_('Redo'), '<Ctrl><Shift>z', t), null];
    if (!t.terminal)
        entries.push(key(_('Cut'), '<Ctrl>x', t));
    entries.push(key(_('Copy'), `<Ctrl>${shift}c`, t), key(_('Paste'), `<Ctrl>${shift}v`, t),
        key(_('Select All'), `<Ctrl>${shift}a`, t), null, key(_('Find…'), `<Ctrl>${shift}f`, t));
    if (!t.terminal)
        entries.push(null, key(_('Emoji & Symbols'), '<Ctrl>period', t));
    return entries;
}

function viewMenu(t) {
    const fullscreen = t.win?.is_fullscreen();
    const entries = [
        {label: fullscreen ? _('Exit Full Screen') : _('Enter Full Screen'), shortcut: 'F11',
            enabled: Boolean(t.win), run: () => (fullscreen ? t.win.unmake_fullscreen() : t.win.make_fullscreen())},
        null,
        key(_('Zoom In'), '<Ctrl>plus', t), key(_('Zoom Out'), '<Ctrl>minus', t), key(_('Actual Size'), '<Ctrl>0', t),
    ];
    if (!t.terminal)
        entries.push(null, key(_('Reload'), '<Ctrl>r', t));
    return entries;
}

function goMenu(t) {
    const places = [
        [_('Home'), null], [_('Documents'), GLib.UserDirectory.DIRECTORY_DOCUMENTS],
        [_('Downloads'), GLib.UserDirectory.DIRECTORY_DOWNLOAD], [_('Desktop'), GLib.UserDirectory.DIRECTORY_DESKTOP],
        [_('Pictures'), GLib.UserDirectory.DIRECTORY_PICTURES], [_('Music'), GLib.UserDirectory.DIRECTORY_MUSIC],
        [_('Videos'), GLib.UserDirectory.DIRECTORY_VIDEOS],
    ];
    return [
        key(_('Back'), '<Alt>Left', t), key(_('Forward'), '<Alt>Right', t), key(_('Enclosing Folder'), '<Alt>Up', t),
        null,
        ...places.map(([label, dir]) => ({label, enabled: Boolean(folderUri(dir)), run: () => openUri(folderUri(dir))})),
        null,
        {label: _('Computer'), run: () => openUri('computer:///')},
        {label: _('Trash'), run: () => openUri('trash:///')},
    ];
}

function windowMenu(t) {
    const target = otherMonitor(t.win);
    const maximized = t.win?.is_maximized();
    const entries = [
        {label: _('Minimize'), shortcut: 'Ctrl+M', enabled: Boolean(t.win?.can_minimize()), run: () => t.win.minimize()},
        {label: _('Zoom'), enabled: Boolean(t.win?.can_maximize()),
            run: () => (maximized ? t.win.unmaximize() : t.win.maximize())},
        null,
        key(_('Tile Window to Left of Screen'), '<Super>Left', t),
        key(_('Tile Window to Right of Screen'), '<Super>Right', t),
    ];
    if (target >= 0) {
        entries.push({label: _('Move to {display}', {display: monitorName(target)}),
            run: () => t.win.move_to_monitor(target)});
    }
    entries.push(null, {label: _('Bring All to Front'), enabled: Boolean(t.app?.get_n_windows()),
        run: () => t.app.get_windows().slice().reverse().forEach(w => w.activate(global.get_current_time()))});
    const windows = t.app?.get_windows() ?? [];
    if (windows.length) {
        entries.push(null);
        for (const w of windows) {
            entries.push({label: w.get_title() || t.name, checked: w === t.win,
                run: () => w.activate(global.get_current_time())});
        }
    }
    return entries;
}

function helpMenu(t) {
    return [
        key(_('{app} Help', {app: t.name}), 'F1', t),
        key(_('Keyboard Shortcuts'), '<Ctrl>question', t),
        null,
        {label: _('Macify Website'), run: () => openUri('https://jdswe.github.io/macify/')},
    ];
}

// El grupo completo: nombre de la app y sus menús, siguiendo a la app activa.
export class AppMenus {
    constructor() {
        this._appMenu = new BarMenu('', appMenu, true);
        this._menus = [
            ['file', new BarMenu(_('File'), fileMenu)],
            ['edit', new BarMenu(_('Edit'), editMenu)],
            ['view', new BarMenu(_('View'), viewMenu)],
            ['go', new BarMenu(_('Go'), goMenu)],
            ['window', new BarMenu(_('Window'), windowMenu)],
            ['help', new BarMenu(_('Help'), helpMenu)],
        ];
        Main.panel.addToStatusArea('macify-app-menu', this._appMenu, 1, 'left');
        this._menus.forEach(([name, menu], i) => Main.panel.addToStatusArea(`macify-menu-${name}`, menu, 2 + i, 'left'));
        this._tracker = Shell.WindowTracker.get_default();
        this._tracker.connectObject('notify::focus-app', () => this._update(), this);
        this._update();
    }

    _update() {
        const t = currentTarget();
        this._appMenu.setTitle(t.name);
        // «Ir» sólo tiene sentido en Archivos, como en el Finder.
        const go = this._menus.find(([name]) => name === 'go')[1];
        go.visible = t.files;
    }

    destroy() {
        this._tracker.disconnectObject(this);
        this._appMenu.destroy();
        this._menus.forEach(([, menu]) => menu.destroy());
        keyboard?.run_dispose?.();
        keyboard = null;
    }
}
