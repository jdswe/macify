// Al dejar el puntero sobre un icono del dock, como en macOS: si la app tiene varias
// ventanas salen sus miniaturas (un clic lleva a esa ventana) y, en
// Archivos, las capturas y descargas de los últimos minutos) la lista para abrirlos o copiarlos. Copiar
// deja el archivo en el portapapeles: se pega (Ctrl+V) en Archivos, en un correo o en un chat.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import {AppMenu} from 'resource:///org/gnome/shell/ui/appMenu.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {_} from './i18n.js';

const HOVER_DELAY_MS = 350;      // el puntero debe quedarse un momento sobre el icono
const WATCH_MS = 150;            // mientras está abierto, se mira si el puntero sigue cerca
const MARGIN = 14;               // tolerancia entre el icono y el panel
const MAX_RECENTS = 8;
const THUMB_W = 210;
const THUMB_H = 130;
const FRESH_SECONDS = 120;       // en Archivos sólo salen las capturas y descargas de hace poco
const PARTIAL = /\.(crdownload|part|download|tmp)$/i;     // descargas que aún no terminan

// Miniatura de una ventana con su título (la misma en el dock y en el menú del clic derecho).
export function windowThumbnail(win) {
    const actor = win.get_compositor_private();
    if (!actor)
        return null;
    const [w, h] = actor.get_size();
    const scale = Math.min(1, THUMB_W / w, THUMB_H / h);
    const column = new St.BoxLayout({vertical: true});
    const clone = new Clutter.Clone({source: actor});
    clone.set_size(Math.round(w * scale), Math.round(h * scale));
    column.add_child(clone);
    column.add_child(new St.Label({text: win.get_title() ?? '', style_class: 'macify-dockpop-title'}));
    return column;
}

// Capturas, grabaciones y descargas de los últimos minutos, de la más nueva a la más vieja.
// Sólo para Archivos: al pasar por su icono justo después de capturar o descargar algo, está
// ahí para abrirlo o copiarlo; pasado ese rato, el icono vuelve a ser sólo un icono.
function freshFiles() {
    const pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES);
    const videos = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_VIDEOS);
    const downloads = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD);
    const dirs = [`${pictures}/Screenshots`, `${videos}/Screencasts`, downloads]
        .filter(dir => dir && dir !== GLib.get_home_dir());
    const since = GLib.get_real_time() / 1e6 - FRESH_SECONDS;
    const found = [];
    for (const dir of new Set(dirs)) {
        let list;
        try {
            list = Gio.File.new_for_path(dir).enumerate_children(
                'standard::name,standard::type,standard::is-hidden,time::modified', Gio.FileQueryInfoFlags.NONE, null);
        } catch (e) {
            continue;                                 // la carpeta no existe
        }
        for (let info = list.next_file(null); info; info = list.next_file(null)) {
            const time = info.get_modification_date_time()?.to_unix() ?? 0;
            if (time >= since && info.get_file_type() === Gio.FileType.REGULAR && !info.get_is_hidden() &&
                !PARTIAL.test(info.get_name()))
                found.push({time, file: list.get_child(info)});
        }
        list.close(null);
    }
    return found.sort((a, b) => b.time - a.time).slice(0, MAX_RECENTS).map(f => f.file);
}

// La pantalla donde está un punto (el menú o el icono), no la principal: con dos pantallas
// el panel sale junto al dock o al menú de esa pantalla.
export function monitorAt(x, y) {
    return Main.layoutManager.monitors.find(m => x >= m.x && x < m.x + m.width && y >= m.y && y < m.y + m.height) ??
        Main.layoutManager.primaryMonitor;
}

function isFiles(app) {
    return app.get_id() === 'org.gnome.Nautilus.desktop';
}

function copyFile(file) {
    const bytes = new GLib.Bytes(new TextEncoder().encode(`copy\n${file.get_uri()}`));
    St.Clipboard.get_default().set_content(St.ClipboardType.CLIPBOARD, 'x-special/gnome-copied-files', bytes);
}

// En el menú del clic derecho de un icono, «Ventanas abiertas»: al recorrer cada ventana
// (con el puntero o las flechas) sale su miniatura al lado, para saber cuál es antes de elegirla.
class WindowMenuPreviews {
    constructor() {
        this._proto = AppMenu.prototype;
        this._original = this._proto._updateWindowsSection;
        this._menus = new Set();
        this._card = null;
        const self = this;
        this._proto._updateWindowsSection = function () {
            self._original.call(this);
            try {
                self._decorate(this);
            } catch (e) {
                console.warn(`Macify: window previews: ${e.message}`);
            }
        };
    }

    _decorate(menu) {
        if (!menu._app)
            return;
        const windows = menu._app.get_windows().filter(w => !w.skip_taskbar);
        const items = menu._windowSection._getMenuItems();
        if (items.length !== windows.length)
            return;
        items.forEach((item, i) => item.connectObject('notify::active', () => {
            if (item.active)
                this._show(menu, windows[i], item);
            else
                this._hide();
        }, this));
        if (!this._menus.has(menu)) {
            this._menus.add(menu);
            menu.connectObject('open-state-changed', (_menu, open) => {
                if (!open)
                    this._hide();
            }, this);
        }
    }

    _show(menu, win, item) {
        this._hide();
        const content = windowThumbnail(win);
        if (!content)
            return;
        const card = new St.BoxLayout({style_class: 'macify-dockpop', reactive: false});
        card.add_child(content);
        Main.uiGroup.add_child(card);
        const [mx, my] = menu.actor.get_transformed_position();
        const [mw] = menu.actor.get_transformed_size();
        const [, iy] = item.get_transformed_position();
        const [width, height] = card.get_size();
        const monitor = monitorAt(mx + mw / 2, iy);
        const right = mx + mw + 8;
        const x = right + width <= monitor.x + monitor.width ? right : mx - width - 8;
        card.set_position(Math.round(Math.max(monitor.x, x)),
            Math.round(Math.max(monitor.y + 34, Math.min(iy - height / 2, monitor.y + monitor.height - height - 8))));
        this._card = card;
    }

    _hide() {
        this._card?.destroy();
        this._card = null;
    }

    destroy() {
        this._hide();
        this._proto._updateWindowsSection = this._original;
        for (const menu of this._menus)
            menu.disconnectObject(this);
        this._menus.clear();
    }
}

export class DockPreview {
    constructor() {
        this._docks = new Set();
        this._menus = new WindowMenuPreviews();
        this._popup = null;
        this._candidate = null;
    }

    attach(dock) {
        if (this._docks.has(dock) || !dock.dash)
            return;
        this._docks.add(dock);
        // El dock animado calcula por su cuenta qué icono está bajo el puntero (dock._hoveredIcon):
        // mientras el puntero está cerca del dock se le pregunta eso, sin escuchar cada movimiento.
        dock.dash.connectObject('enter-event', () => {
            this._poll(dock);
            return Clutter.EVENT_PROPAGATE;
        }, this);
        dock.connectObject('destroy', () => {
            this._docks.delete(dock);
            this._close();
        }, this);
        dock._macifyKeepOpen = () => Boolean(this._popup) && this._pointerIn(this._popup);
    }

    _poll(dock) {
        if (this._pollId)
            return;
        this._pollId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 120, () => {
            if (dock._macifyDestroyed || !dock.dash || !this._pointerIn(dock.dash, 40)) {
                this._pollId = 0;
                if (!this._popup && this._timer) {
                    GLib.source_remove(this._timer);
                    this._timer = 0;
                }
                this._candidate = null;
                return GLib.SOURCE_REMOVE;
            }
            const found = this._appOf(this._iconUnderPointer(dock));
            if (found)
                this._hover(found);
            return GLib.SOURCE_CONTINUE;
        });
    }

    // El icono bajo el puntero, mirado aquí mismo: el dock sólo anota el suyo (_hoveredIcon)
    // mientras anima, y en la segunda pantalla a veces no lo hace.
    _iconUnderPointer(dock) {
        const [px, py] = global.get_pointer();
        for (const icon of dock._icons ?? dock.dash._box.get_children()) {
            const [x, y] = icon.get_transformed_position();
            const [w, h] = icon.get_transformed_size();
            if (Number.isFinite(x) && Number.isFinite(y) && px >= x && px <= x + w && py >= y && py <= y + h)
                return icon;
        }
        return null;
    }

    _appOf(icon) {
        const app = icon?._appwell?.app ?? icon?.child?.app ?? icon?.app;
        return app?.get_id && app.get_windows ? {app, icon} : null;
    }

    _hover(found) {
        if (found.app === this._candidate?.app)
            return;
        this._candidate = found;
        if (this._timer)
            GLib.source_remove(this._timer);
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, HOVER_DELAY_MS, () => {
            this._timer = 0;
            this._open(found);
            return GLib.SOURCE_REMOVE;
        });
    }

    _open({app, icon}) {
        this._close(false);
        const windows = (app.get_windows() ?? []).filter(w => !w.skip_taskbar);
        const recents = isFiles(app) ? freshFiles() : [];
        if (windows.length < 2 && recents.length === 0)
            return;
        const box = new St.BoxLayout({style_class: 'macify-dockpop', vertical: true, reactive: true});
        if (windows.length >= 2)
            box.add_child(this._windows(windows));
        if (recents.length)
            box.add_child(this._recents(recents));
        Main.uiGroup.add_child(box);
        const [x, y] = icon.get_transformed_position();
        const [iconWidth] = icon.get_transformed_size();
        const [width, height] = box.get_size();
        const monitor = monitorAt(x + iconWidth / 2, y);
        box.set_position(
            Math.round(Math.max(monitor.x + 8, Math.min(x + iconWidth / 2 - width / 2, monitor.x + monitor.width - width - 8))),
            Math.round(Math.max(monitor.y + 34, y - height - 6)));
        this._popup = box;
        this._icon = icon;
        this._watch = GLib.timeout_add(GLib.PRIORITY_DEFAULT, WATCH_MS, () => {
            if (this._pointerIn(this._popup) || this._pointerIn(this._icon, true))
                return GLib.SOURCE_CONTINUE;
            this._watch = 0;
            this._close();
            return GLib.SOURCE_REMOVE;
        });
    }

    _windows(windows) {
        const row = new St.BoxLayout({style_class: 'macify-dockpop-windows'});
        for (const win of windows) {
            const column = windowThumbnail(win);
            if (!column)
                continue;
            const card = new St.Button({style_class: 'macify-dockpop-window', reactive: true, can_focus: true});
            card.set_child(column);
            card.connect('clicked', () => {
                this._close();
                Main.activateWindow(win);
            });
            row.add_child(card);
        }
        return row;
    }

    _recents(files) {
        const column = new St.BoxLayout({vertical: true, style_class: 'macify-dockpop-recents'});
        column.add_child(new St.Label({text: _('Just Added'), style_class: 'macify-dockpop-heading'}));
        for (const file of files) {
            const row = new St.BoxLayout({style_class: 'macify-dockpop-file'});
            const open = new St.Button({style_class: 'macify-dockpop-open', x_expand: true, x_align: Clutter.ActorAlign.FILL});
            const info = file.query_info('standard::display-name,standard::icon', Gio.FileQueryInfoFlags.NONE, null);
            const line = new St.BoxLayout({x_expand: true, x_align: Clutter.ActorAlign.START});
            line.add_child(new St.Icon({gicon: info.get_icon(), icon_size: 18}));
            line.add_child(new St.Label({text: info.get_display_name(), y_align: Clutter.ActorAlign.CENTER}));
            open.set_child(line);
            open.connect('clicked', () => {
                this._close();
                Gio.AppInfo.launch_default_for_uri(file.get_uri(), global.create_app_launch_context(0, -1));
            });
            const copy = new St.Button({
                style_class: 'macify-dockpop-copy',
                child: new St.Icon({icon_name: 'edit-copy-symbolic', icon_size: 14}),
            });
            copy.connect('clicked', () => {
                copyFile(file);
                Main.osdWindowManager.show(-1, Gio.ThemedIcon.new('edit-copy-symbolic'), _('Copied'), null);
            });
            row.add_child(open);
            row.add_child(copy);
            column.add_child(row);
        }
        return column;
    }

    _pointerIn(actor, margin = 2) {
        const [px, py] = global.get_pointer();
        const [x, y] = actor.get_transformed_position();
        const [w, h] = actor.get_transformed_size();
        const m = margin === true ? MARGIN : margin;
        return px >= x - m && px <= x + w + m && py >= y - m && py <= y + h + m;
    }

    _close(forget = true) {
        if (this._watch)
            GLib.source_remove(this._watch);
        this._watch = 0;
        this._popup?.destroy();
        this._popup = null;
        this._icon = null;
        if (forget) {
            if (this._timer)
                GLib.source_remove(this._timer);
            this._timer = 0;
            this._candidate = null;
        }
    }

    destroy() {
        this._menus.destroy();
        if (this._pollId)
            GLib.source_remove(this._pollId);
        this._pollId = 0;
        this._close();
        for (const dock of this._docks) {
            dock.dash?.disconnectObject(this);
            dock.disconnectObject(this);
            delete dock._macifyKeepOpen;
        }
        this._docks.clear();
    }
}
