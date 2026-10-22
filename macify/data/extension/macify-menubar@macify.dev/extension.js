// Macify Menubar: logo con el menú del sistema y nombre de la app activa,
// como la barra de menús de macOS.

import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Shell from 'gi://Shell';
import Clutter from 'gi://Clutter';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

// Textos en inglés; en español si el idioma del sistema es español.
const SPANISH = {
    'About This Computer': 'Acerca de este equipo',
    'System Settings…': 'Ajustes del sistema…',
    'App Center…': 'App Center…',
    'Force Quit…': 'Forzar salida…',
    'Sleep': 'Suspender',
    'Restart…': 'Reiniciar…',
    'Shut Down…': 'Apagar…',
    'Lock Screen': 'Bloquear pantalla',
    'Log Out…': 'Cerrar sesión…',
};
const IS_SPANISH = GLib.get_language_names()[0].startsWith('es');
const _ = text => (IS_SPANISH && SPANISH[text]) || text;


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

const AppTitle = GObject.registerClass(
class AppTitle extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'Macify App Title', true);
        this._label = new St.Label({
            text: '',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'macify-app-title',
        });
        this.add_child(this._label);
        this._tracker = Shell.WindowTracker.get_default();
        this._focusId = this._tracker.connect('notify::focus-app', () => this._update());
        this._update();
    }

    _update() {
        // Sin app activa no se muestra nada: en Ubuntu, Archivos no está siempre abierto como Finder.
        const app = this._tracker.focus_app;
        this._label.text = app ? app.get_name() : '';
        this.visible = Boolean(app);
    }

    destroy() {
        if (this._focusId) {
            this._tracker.disconnect(this._focusId);
            this._focusId = 0;
        }
        super.destroy();
    }
});

// El dock animado (Dash2Dock Animated) se esconde del todo cuando una ventana está en
// pantalla completa. Como en macOS, aquí sigue a mano: escondido, y aparece al llevar
// el puntero al borde inferior. Si ese dock no está, esto no hace nada.
const DOCK_UUID = 'dash2dock-lite@icedman.github.com';

class FullscreenDock {
    constructor() {
        global.display.connectObject('in-fullscreen-changed', () => this._update(), this);
        Main.extensionManager.connectObject('extension-state-changed', () => this._update(), this);
        Main.layoutManager.connectObject('monitors-changed', () => this._update(), this);
        // El dock puede crearse después que esta extensión.
        this._startId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => {
            this._startId = 0;
            this._update();
            return GLib.SOURCE_REMOVE;
        });
        this._update();
    }

    _docks() {
        return Main.extensionManager.lookup(DOCK_UUID)?.stateObj?.docks ?? [];
    }

    _tracked(dock) {
        return Main.layoutManager._trackedActors?.find(data => data.actor === dock);
    }

    _update() {
        try {
            for (const dock of this._docks())
                this._patch(dock);
        } catch (e) {
            console.warn(`Macify: fullscreen dock: ${e.message}`);
        }
    }

    _patch(dock) {
        if (dock.dwell && !dock.dwell._macifyLog) {
            // Una línea en el registro cada vez que el puntero llega al borde: sirve para
            // saber por qué el dock no aparece sobre alguna app (journalctl --user -g "Macify dock").
            dock.dwell._macifyLog = true;
            dock.dwell.connectObject('enter-event', () => {
                const monitor = dock._monitor;
                console.log(`Macify dock: edge on monitor ${monitor?.index} fullscreen=${monitor?.inFullscreen} ` +
                    `shown=${dock.autohider?._shown} hidden=${dock._hidden} visible=${dock.visible} ` +
                    `focus=${global.display.focus_window?.get_wm_class() ?? '-'}`);
            }, this);
        }
        const tracked = this._tracked(dock);
        if (tracked?.trackFullscreen) {
            tracked.trackFullscreen = false;
            dock.visible = true;
        }
        const hider = dock.autohider;
        if (!hider || hider._macifyOriginal)
            return;
        hider._macifyOriginal = {show: hider.show, checkOverlap: hider._checkOverlap};
        hider.show = function () {
            if (!this.dock._monitor)
                return;
            this._dwell = 0;
            this.frameDelay = 0;
            this._shown = true;
            this.dock.slideIn();
        };
        hider._checkOverlap = function () {
            // En pantalla completa sólo se queda mientras el puntero está sobre el dock.
            if (this.dock._monitor?.inFullscreen && !this.extension?._inOverview)
                return !this.dock._isWithinDash(global.get_pointer());
            return this._macifyOriginal.checkOverlap.call(this);
        };
        hider._debounceCheckHide?.();
    }

    destroy() {
        if (this._startId)
            GLib.source_remove(this._startId);
        global.display.disconnectObject(this);
        Main.extensionManager.disconnectObject(this);
        Main.layoutManager.disconnectObject(this);
        try {
            for (const dock of this._docks()) {
                dock.dwell?.disconnectObject(this);
                if (dock.dwell)
                    delete dock.dwell._macifyLog;
                const hider = dock.autohider;
                if (hider?._macifyOriginal) {
                    hider.show = hider._macifyOriginal.show;
                    hider._checkOverlap = hider._macifyOriginal.checkOverlap;
                    delete hider._macifyOriginal;
                }
                const tracked = this._tracked(dock);
                if (tracked)
                    tracked.trackFullscreen = true;
            }
            Main.layoutManager._updateVisibility?.();
        } catch (e) {
            console.warn(`Macify: fullscreen dock: ${e.message}`);
        }
    }
}

export default class MacifyMenubar extends Extension {
    enable() {
        this._logo = new LogoMenu(this.path);
        this._title = new AppTitle();
        Main.panel.addToStatusArea('macify-logo', this._logo, 0, 'left');
        Main.panel.addToStatusArea('macify-app-title', this._title, 1, 'left');
        this._fullscreenDock = new FullscreenDock();
    }

    disable() {
        this._fullscreenDock?.destroy();
        this._fullscreenDock = null;
        this._title?.destroy();
        this._logo?.destroy();
        this._title = null;
        this._logo = null;
    }
}
