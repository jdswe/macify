// Menús de app como los de macOS: el nombre de la app en negrita y File, Edit, View, Go,
// Window y Help, con el orden y las reglas de las Human Interface Guidelines de Apple:
// - Siempre las mismas opciones; las que no aplican se ven desactivadas, no se esconden.
// - Atajos con los símbolos de macOS e iconos en cada grupo.
// - Con Alt (la Opción de macOS): «Minimize All» y «Close All».
// Sirven en cualquier app (apt, snap, flatpak, AppImage): las órdenes de edición mandan los
// atajos de siempre de esa clase de app y las de ventana actúan sobre la ventana. Cada menú
// se arma al abrirlo, así que cerrado no gasta nada.

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
import * as Keys from './keys.js';

const FILES_APP = 'org.gnome.Nautilus.desktop';
const WEBSITE = 'https://jdswe.github.io/macify/';
const TERMINALS = new Set([
    'org.gnome.Ptyxis.desktop', 'org.gnome.Terminal.desktop', 'org.gnome.Console.desktop',
    'com.mitchellh.ghostty.desktop', 'kitty.desktop', 'Alacritty.desktop', 'org.wezfurlong.wezterm.desktop',
    'org.kde.konsole.desktop', 'terminator.desktop', 'com.gexperts.Tilix.desktop', 'xterm.desktop',
]);

// Atajo de cada orden según la clase de app. null: esa clase de app no la tiene.
// En las terminales copiar y pegar llevan Mayúsculas (Ctrl+C interrumpe el programa).
const SHORTCUTS = {
    settings: {app: '<Ctrl>comma'},
    newTab: {app: '<Ctrl>t', terminal: '<Ctrl><Shift>t'},
    newFolder: {app: null, files: '<Ctrl><Shift>n'},
    open: {app: '<Ctrl>o', terminal: null, files: null},
    closeTab: {app: '<Ctrl>w', terminal: '<Ctrl><Shift>w'},
    save: {app: '<Ctrl>s', terminal: null, files: null},
    saveAs: {app: '<Ctrl><Shift>s', terminal: null, files: null},
    print: {app: '<Ctrl>p', terminal: null, files: null},
    undo: {app: '<Ctrl>z', terminal: null},
    redo: {app: '<Ctrl><Shift>z', terminal: null},
    cut: {app: '<Ctrl>x', terminal: null},
    copy: {app: '<Ctrl>c', terminal: '<Ctrl><Shift>c'},
    paste: {app: '<Ctrl>v', terminal: '<Ctrl><Shift>v'},
    delete: {app: 'Delete', terminal: null},
    selectAll: {app: '<Ctrl>a', terminal: '<Ctrl><Shift>a'},
    find: {app: '<Ctrl>f', terminal: '<Ctrl><Shift>f'},
    findNext: {app: '<Ctrl>g', terminal: '<Ctrl><Shift>g'},
    findPrevious: {app: '<Ctrl><Shift>g', terminal: '<Ctrl><Shift>h'},
    emoji: {app: '<Ctrl>period', terminal: null},
    zoomIn: {app: '<Ctrl>plus'},
    zoomOut: {app: '<Ctrl>minus'},
    actualSize: {app: '<Ctrl>0'},
    reload: {app: '<Ctrl>r', terminal: null},
    back: {app: null, files: '<Alt>Left'},
    forward: {app: null, files: '<Alt>Right'},
    up: {app: null, files: '<Alt>Up'},
    tileLeft: {app: '<Super>Left'},
    tileRight: {app: '<Super>Right'},
    help: {app: 'F1'},
    keyboardShortcuts: {app: '<Ctrl>question'},
};

function accelFor(action, kind) {
    const table = SHORTCUTS[action];
    return kind in table ? table[kind] : table.app;
}

// ---------- a quién van las órdenes ----------

// La app y la ventana activas. Sin ventana activa, Archivos (como el Finder en macOS).
function currentTarget() {
    const focused = Shell.WindowTracker.get_default().focus_app;
    const app = focused ?? Shell.AppSystem.get_default().lookup_app(FILES_APP);
    const id = app?.get_id() ?? '';
    const kind = TERMINALS.has(id) ? 'terminal' : id === FILES_APP ? 'files' : 'app';
    return {
        app,
        win: focused ? global.display.focus_window : null,
        name: app?.get_name() ?? _('Files'),
        kind,
        option: Keys.optionPressed(),
    };
}

// ---------- acciones ----------

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

function nextMonitor(win) {
    const count = global.display.get_n_monitors();
    return win && count > 1 ? (win.get_monitor() + 1) % count : -1;
}

function monitorName(index) {
    return index === Main.layoutManager.primaryIndex ? _('Main Display') : _('Display {n}', {n: index + 1});
}

function appWindows(t) {
    return t.app?.get_windows() ?? [];
}

const now = () => global.get_current_time();

// ---------- entradas de menú ----------

// Orden que se hace con el atajo de la app.
function shortcut(t, label, icon, action) {
    const accel = accelFor(action, t.kind);
    return {label, icon, accel, enabled: Boolean(t.win && accel), run: () => Keys.sendShortcut(t.win, accel)};
}

// Orden que Macify hace directamente.
function command(label, icon, run, enabled = true, accel = null) {
    return {label, icon, accel, enabled: Boolean(enabled), run};
}

const SEPARATOR = null;

function appMenu(t) {
    const tracker = Shell.WindowTracker.get_default();
    const others = () => global.display.list_all_windows()
        .filter(w => !w.minimized && w.can_minimize() && tracker.get_window_app(w) !== t.app);
    return [
        command(_('About {app}', {app: t.name}), 'help-about-symbolic',
            () => Util.spawn(['gnome-control-center', 'applications', t.app.get_id().replace(/\.desktop$/, '')]), t.app),
        SEPARATOR,
        shortcut(t, _('Settings…'), 'preferences-system-symbolic', 'settings'),
        SEPARATOR,
        command(_('Hide {app}', {app: t.name}), 'view-conceal-symbolic',
            () => appWindows(t).forEach(w => w.can_minimize() && w.minimize()), t.win),
        command(_('Hide Others'), 'view-conceal-symbolic', () => others().forEach(w => w.minimize()), others().length),
        command(_('Show All'), 'view-reveal-symbolic',
            () => global.display.list_all_windows().forEach(w => w.minimized && w.unminimize())),
        SEPARATOR,
        command(_('Quit {app}', {app: t.name}), 'application-exit-symbolic', () => t.app.request_quit(),
            appWindows(t).length, '<Ctrl>q'),
    ];
}

function fileMenu(t) {
    const newWindow = command(_('New Window'), 'window-new-symbolic', () => {
        if (t.app.can_open_new_window())
            t.app.open_new_window(-1);
        else
            Keys.sendShortcut(t.win, t.kind === 'terminal' ? '<Ctrl><Shift>n' : '<Ctrl>n');
    }, t.app, t.kind === 'terminal' ? '<Ctrl><Shift>n' : '<Ctrl>n');
    const close = t.option
        ? command(_('Close All'), 'window-close-symbolic',
            () => appWindows(t).forEach(w => w.can_close() && w.delete(now())), appWindows(t).length)
        : command(_('Close Window'), 'window-close-symbolic', () => t.win.delete(now()), t.win?.can_close());
    return [
        newWindow,
        t.kind === 'files'
            ? shortcut(t, _('New Folder'), 'folder-new-symbolic', 'newFolder')
            : shortcut(t, _('New Tab'), 'tab-new-symbolic', 'newTab'),
        shortcut(t, _('Open…'), 'document-open-symbolic', 'open'),
        SEPARATOR,
        shortcut(t, _('Close Tab'), 'tab-close-symbolic', 'closeTab'),
        close,
        SEPARATOR,
        shortcut(t, _('Save'), 'document-save-symbolic', 'save'),
        shortcut(t, _('Save As…'), 'document-save-as-symbolic', 'saveAs'),
        SEPARATOR,
        shortcut(t, _('Print…'), 'document-print-symbolic', 'print'),
    ];
}

function editMenu(t) {
    return [
        shortcut(t, _('Undo'), 'edit-undo-symbolic', 'undo'),
        shortcut(t, _('Redo'), 'edit-redo-symbolic', 'redo'),
        SEPARATOR,
        shortcut(t, _('Cut'), 'edit-cut-symbolic', 'cut'),
        shortcut(t, _('Copy'), 'edit-copy-symbolic', 'copy'),
        shortcut(t, _('Paste'), 'edit-paste-symbolic', 'paste'),
        shortcut(t, _('Delete'), 'edit-delete-symbolic', 'delete'),
        shortcut(t, _('Select All'), 'edit-select-all-symbolic', 'selectAll'),
        SEPARATOR,
        shortcut(t, _('Find…'), 'edit-find-symbolic', 'find'),
        shortcut(t, _('Find Next'), 'go-down-symbolic', 'findNext'),
        shortcut(t, _('Find Previous'), 'go-up-symbolic', 'findPrevious'),
        SEPARATOR,
        shortcut(t, _('Emoji & Symbols'), 'face-smile-symbolic', 'emoji'),
    ];
}

function viewMenu(t) {
    const fullscreen = t.win?.is_fullscreen();
    return [
        shortcut(t, _('Zoom In'), 'zoom-in-symbolic', 'zoomIn'),
        shortcut(t, _('Zoom Out'), 'zoom-out-symbolic', 'zoomOut'),
        shortcut(t, _('Actual Size'), 'zoom-original-symbolic', 'actualSize'),
        shortcut(t, _('Reload'), 'view-refresh-symbolic', 'reload'),
        SEPARATOR,
        command(fullscreen ? _('Exit Full Screen') : _('Enter Full Screen'),
            fullscreen ? 'view-restore-symbolic' : 'view-fullscreen-symbolic',
            () => (fullscreen ? t.win.unmake_fullscreen() : t.win.make_fullscreen()), t.win, 'F11'),
    ];
}

function goMenu(t) {
    const places = [
        [_('Home'), 'user-home-symbolic', null],
        [_('Desktop'), 'user-desktop-symbolic', GLib.UserDirectory.DIRECTORY_DESKTOP],
        [_('Documents'), 'folder-documents-symbolic', GLib.UserDirectory.DIRECTORY_DOCUMENTS],
        [_('Downloads'), 'folder-download-symbolic', GLib.UserDirectory.DIRECTORY_DOWNLOAD],
        [_('Pictures'), 'folder-pictures-symbolic', GLib.UserDirectory.DIRECTORY_PICTURES],
        [_('Music'), 'folder-music-symbolic', GLib.UserDirectory.DIRECTORY_MUSIC],
        [_('Videos'), 'folder-videos-symbolic', GLib.UserDirectory.DIRECTORY_VIDEOS],
    ];
    return [
        shortcut(t, _('Back'), 'go-previous-symbolic', 'back'),
        shortcut(t, _('Forward'), 'go-next-symbolic', 'forward'),
        shortcut(t, _('Enclosing Folder'), 'go-up-symbolic', 'up'),
        SEPARATOR,
        ...places.map(([label, icon, dir]) => command(label, icon, () => openUri(folderUri(dir)), folderUri(dir))),
        SEPARATOR,
        command(_('Computer'), 'computer-symbolic', () => openUri('computer:///')),
        command(_('Trash'), 'user-trash-symbolic', () => openUri('trash:///')),
    ];
}

function windowMenu(t) {
    const target = nextMonitor(t.win);
    const minimize = t.option
        ? command(_('Minimize All'), 'window-minimize-symbolic',
            () => appWindows(t).forEach(w => w.can_minimize() && w.minimize()), appWindows(t).length)
        : command(_('Minimize'), 'window-minimize-symbolic', () => t.win.minimize(), t.win?.can_minimize());
    const entries = [
        minimize,
        command(_('Zoom'), 'window-maximize-symbolic',
            () => (t.win.is_maximized() ? t.win.unmaximize() : t.win.maximize()), t.win?.can_maximize()),
        SEPARATOR,
        shortcut(t, _('Tile Window to Left of Screen'), 'view-dual-symbolic', 'tileLeft'),
        shortcut(t, _('Tile Window to Right of Screen'), 'view-dual-symbolic', 'tileRight'),
        command(_('Move to {display}', {display: monitorName(Math.max(target, 0))}), 'video-display-symbolic',
            () => t.win.move_to_monitor(target), target >= 0),
        SEPARATOR,
        command(_('Bring All to Front'), 'focus-windows-symbolic',
            () => appWindows(t).slice().reverse().forEach(w => w.activate(now())), appWindows(t).length),
    ];
    // Ventanas abiertas de la app, en orden alfabético.
    const windows = appWindows(t)
        .map(w => ({w, title: w.get_title() || t.name}))
        .sort((a, b) => a.title.localeCompare(b.title));
    if (windows.length)
        entries.push(SEPARATOR);
    for (const {w, title} of windows)
        entries.push({...command(title, null, () => w.activate(now())), checked: w === t.win});
    return entries;
}

function helpMenu(t) {
    return [
        shortcut(t, _('{app} Help', {app: t.name}), 'help-browser-symbolic', 'help'),
        shortcut(t, _('Keyboard Shortcuts'), 'input-keyboard-symbolic', 'keyboardShortcuts'),
        SEPARATOR,
        command(_('Macify Website'), 'web-browser-symbolic', () => openUri(WEBSITE)),
    ];
}

// ---------- menús de la barra ----------

function menuItem(entry) {
    const item = entry.icon
        ? new PopupMenu.PopupImageMenuItem(entry.label, entry.icon)
        : new PopupMenu.PopupMenuItem(entry.label);
    if (entry.accel) {
        item.add_child(new St.Label({
            text: Keys.glyphs(entry.accel),
            x_expand: true,
            x_align: Clutter.ActorAlign.END,
            style_class: 'macify-menu-shortcut',
        }));
    }
    if (entry.checked)
        item.setOrnament(PopupMenu.Ornament.CHECK);
    item.setSensitive(entry.enabled);
    item.connect('activate', () => entry.run());
    return item;
}

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
        // GNOME no abre un menú vacío: siempre tiene las opciones de la app activa, y al
        // abrirse se rehace para mostrar el estado del momento (pantalla completa, Alt…).
        this.menu.connect('open-state-changed', (_menu, open) => {
            if (open)
                this._refill();
        });
        this._refill();
    }

    setTitle(text) {
        this._label.text = text;
    }

    refresh() {
        if (!this.menu.isOpen)
            this._refill();
    }

    _refill() {
        this.menu.removeAll();
        for (const entry of this._build(currentTarget())) {
            this.menu.addMenuItem(entry === SEPARATOR
                ? new PopupMenu.PopupSeparatorMenuItem()
                : menuItem(entry));
        }
    }
});

// El grupo completo: nombre de la app y sus menús, siguiendo a la app activa.
export class AppMenus {
    constructor() {
        this._appMenu = new BarMenu('', appMenu, true);
        this._goMenu = new BarMenu(_('Go'), goMenu);
        const menus = [
            ['file', new BarMenu(_('File'), fileMenu)],
            ['edit', new BarMenu(_('Edit'), editMenu)],
            ['view', new BarMenu(_('View'), viewMenu)],
            ['go', this._goMenu],
            ['window', new BarMenu(_('Window'), windowMenu)],
            ['help', new BarMenu(_('Help'), helpMenu)],
        ];
        this._menus = [this._appMenu, ...menus.map(([, menu]) => menu)];
        Main.panel.addToStatusArea('macify-app-menu', this._appMenu, 1, 'left');
        menus.forEach(([name, menu], i) => Main.panel.addToStatusArea(`macify-menu-${name}`, menu, 2 + i, 'left'));
        Shell.WindowTracker.get_default().connectObject('notify::focus-app', () => this._update(), this);
        this._update();
    }

    _update() {
        const t = currentTarget();
        this._appMenu.setTitle(t.name);
        this._goMenu.visible = t.kind === 'files';      // «Go» es el menú propio de Archivos
        this._menus.forEach(menu => menu.refresh());
    }

    destroy() {
        Shell.WindowTracker.get_default().disconnectObject(this);
        this._menus.forEach(menu => menu.destroy());
        Keys.dispose();
    }
}
