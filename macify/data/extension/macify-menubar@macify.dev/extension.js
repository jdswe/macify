// Macify Menubar: la barra de menús de macOS en GNOME. Logo con el menú del sistema,
// menús de la app activa, iconos de estado, Centro de control, Live Activities, indicador de
// volumen y brillo, miniatura de capturas y arreglos del dock.

import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Shell from 'gi://Shell';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

import {AppMenus} from './appMenus.js';
import {ControlCenter} from './controlCenter.js';
import {FullscreenDock, Gnome50Fixes} from './dock.js';
import {LiveActivities} from './liveActivities.js';
import {BarLook} from './look.js';
import {DisplaySwitcher} from './displaySwitcher.js';
import {MacOsd} from './osd.js';
import {ScreenshotPreview} from './screenshotPreview.js';
import {StatusBar} from './statusBar.js';
import {WindowGuard} from './windowGuard.js';
import {_} from './i18n.js';


function launchApp(ids, fallback) {
    const system = Shell.AppSystem.get_default();
    for (const id of ids) {
        const app = system.lookup_app(id);
        if (app) {
            app.activate();
            return;
        }
    }
    if (fallback)
        Util.spawn(fallback);
}

const LogoMenu = GObject.registerClass(
class LogoMenu extends PanelMenu.Button {
    _init(path) {
        super._init(0.0, 'Macify', false);
        this.add_style_class_name('macify-logo-button');
        const file = Gio.File.new_for_path(`${path}/icons/macify-logo-symbolic.svg`);
        this.add_child(new St.Icon({
            gicon: new Gio.FileIcon({file}),
            style_class: 'system-status-icon macify-logo',
        }));

        this._add(_('About This Computer'), () => Util.spawn(['gnome-control-center', 'system']));
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._add(_('System Settings…'), () => Util.spawn(['gnome-control-center']));
        this._add(_('App Center…'), () => launchApp(['snap-store_snap-store.desktop', 'org.gnome.Software.desktop']));
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._add(_('Force Quit…'), () => launchApp(
            ['net.nokyan.Resources.desktop', 'org.gnome.SystemMonitor.desktop'], ['gnome-system-monitor']));
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._add(_('Sleep'), () => Util.spawn(['systemctl', 'suspend']));
        this._add(_('Restart…'), () => Util.spawn(['gnome-session-quit', '--reboot']));
        this._add(_('Shut Down…'), () => Util.spawn(['gnome-session-quit', '--power-off']));
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._add(_('Lock Screen'), () => Main.screenShield.lock(true));
        this._add(_('Log Out…'), () => Util.spawn(['gnome-session-quit', '--logout']));
    }

    _add(label, callback) {
        const item = new PopupMenu.PopupMenuItem(label);
        item.connect('activate', callback);
        this.menu.addMenuItem(item);
    }
});

// Cada parte arranca por separado: si una falla en alguna versión de GNOME, el resto sigue.
const PARTS = [
    ['fixes', () => new Gnome50Fixes()],
    ['look', () => new BarLook()],
    ['menus', () => new AppMenus()],
    ['status', () => new StatusBar()],
    ['control', () => new ControlCenter()],
    ['live', () => new LiveActivities()],
    ['osd', () => new MacOsd()],
    ['screenshots', () => new ScreenshotPreview()],
    ['windows', () => new WindowGuard()],
    ['displays', () => new DisplaySwitcher()],
    ['dock', () => new FullscreenDock()],
];

export default class MacifyMenubar extends Extension {
    enable() {
        this._logo = new LogoMenu(this.path);
        Main.panel.addToStatusArea('macify-logo', this._logo, 0, 'left');
        this._parts = [];
        for (const [name, create] of PARTS) {
            try {
                this._parts.push(create());
            } catch (e) {
                console.error(`Macify: ${name}: ${e.message}`);
            }
        }
    }

    disable() {
        for (const part of (this._parts ?? []).reverse()) {
            try {
                part.destroy();
            } catch (e) {
                console.error(`Macify: ${e.message}`);
            }
        }
        this._parts = null;
        this._logo?.destroy();
        this._logo = null;
    }
}
