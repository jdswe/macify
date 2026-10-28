// Al dejar el puntero sobre un icono del dock, como en macOS: si la app tiene varias
// ventanas salen sus miniaturas (un clic lleva a esa ventana) y, si hay archivos recientes de
// esa app (en Archivos, los de todo el sistema), la lista para abrirlos o copiarlos. Copiar
// deja el archivo en el portapapeles: se pega (Ctrl+V) en Archivos, en un correo o en un chat.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {_} from './i18n.js';

const HOVER_DELAY_MS = 350;      // el puntero debe quedarse un momento sobre el icono
const WATCH_MS = 150;            // mientras está abierto, se mira si el puntero sigue cerca
const MARGIN = 14;               // tolerancia entre el icono y el panel
const MAX_RECENTS = 8;
const THUMB_W = 210;
const THUMB_H = 130;
const RECENT_FILE = `${GLib.get_user_data_dir()}/recently-used.xbel`;

const unescapeXml = text => text.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'").replace(/&amp;/g, '&');

// Archivos usados hace poco, del más nuevo al más viejo: [{uri, apps: [nombres], modified}].
export function parseRecents(xml) {
    const items = [];
    for (const block of xml.split('<bookmark ').slice(1)) {
        const href = /^href="([^"]*)"/.exec(block);
        const modified = /modified="([^"]*)"/.exec(block);
        if (!href?.[1].startsWith('file://'))
            continue;
        const apps = [...block.matchAll(/<bookmark:application name="([^"]*)"/g)].map(m => unescapeXml(m[1]));
        items.push({uri: unescapeXml(href[1]), apps, modified: modified?.[1] ?? ''});
    }
    return items.sort((a, b) => b.modified.localeCompare(a.modified));
}

function recentFor(app) {
    let xml;
    try {
        xml = new TextDecoder().decode(Gio.File.new_for_path(RECENT_FILE).load_contents(null)[1]);
    } catch (e) {
        return [];
    }
    const name = app.get_name().toLowerCase();
    const files = app.get_id() === 'org.gnome.Nautilus.desktop' || name === 'files';
    const found = [];
    for (const item of parseRecents(xml)) {
        if (!files && !item.apps.some(a => a.toLowerCase() === name))
            continue;
        const file = Gio.File.new_for_uri(item.uri);
        if (!file.query_exists(null))
            continue;
        found.push(file);
        if (found.length >= MAX_RECENTS)
            break;
    }
    return found;
}

function copyFile(file) {
    const bytes = new GLib.Bytes(new TextEncoder().encode(`copy\n${file.get_uri()}`));
    St.Clipboard.get_default().set_content(St.ClipboardType.CLIPBOARD, 'x-special/gnome-copied-files', bytes);
}

export class DockPreview {
    constructor() {
        this._docks = new Set();
        this._popup = null;
        this._candidate = null;
    }

    attach(dock) {
        if (this._docks.has(dock) || !dock.dash)
            return;
        this._docks.add(dock);
        dock.dash.connectObject('motion-event', (actor, event) => {
            this._hover(dock, event.get_source());
            return Clutter.EVENT_PROPAGATE;
        }, this);
        dock.connectObject('destroy', () => {
            this._docks.delete(dock);
            this._close();
        }, this);
        dock._macifyKeepOpen = () => Boolean(this._popup) && this._pointerIn(this._popup);
    }

    _appOf(dock, actor) {
        for (let a = actor; a && a !== dock.dash; a = a.get_parent()) {
            const app = a.app ?? a.child?.app;
            if (app?.get_id && app.get_windows)
                return {app, icon: a};
        }
        return null;
    }

    _hover(dock, source) {
        const found = this._appOf(dock, source);
        if (!found || found.app === this._candidate?.app)
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
        const windows = app.get_windows() ?? [];
        const recents = app.get_id() ? recentFor(app) : [];
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
        const monitor = Main.layoutManager.findMonitorForActor(icon) ?? Main.layoutManager.primaryMonitor;
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
            const actor = win.get_compositor_private();
            if (!actor)
                continue;
            const [w, h] = actor.get_size();
            const scale = Math.min(1, THUMB_W / w, THUMB_H / h);
            const card = new St.Button({style_class: 'macify-dockpop-window', reactive: true, can_focus: true});
            const column = new St.BoxLayout({vertical: true});
            const clone = new Clutter.Clone({source: actor});
            clone.set_size(Math.round(w * scale), Math.round(h * scale));
            column.add_child(clone);
            column.add_child(new St.Label({text: win.get_title() ?? '', style_class: 'macify-dockpop-title'}));
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
        column.add_child(new St.Label({text: _('Recent Files'), style_class: 'macify-dockpop-heading'}));
        for (const file of files) {
            const row = new St.BoxLayout({style_class: 'macify-dockpop-file'});
            const open = new St.Button({style_class: 'macify-dockpop-open', x_expand: true, x_align: Clutter.ActorAlign.FILL});
            const info = file.query_info('standard::display-name,standard::icon', Gio.FileQueryInfoFlags.NONE, null);
            const line = new St.BoxLayout();
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

    _pointerIn(actor, loose = false) {
        const [px, py] = global.get_pointer();
        const [x, y] = actor.get_transformed_position();
        const [w, h] = actor.get_transformed_size();
        const m = loose ? MARGIN : 2;
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
        this._close();
        for (const dock of this._docks) {
            dock.dash?.disconnectObject(this);
            dock.disconnectObject(this);
            delete dock._macifyKeepOpen;
        }
        this._docks.clear();
    }
}
