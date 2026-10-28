// Miniatura de captura como en macOS: al hacer una captura aparece abajo a la derecha, se
// desliza fuera a los pocos segundos y, si se pulsa, abre la imagen. GNOME ya la copia al
// portapapeles, así que se puede pegar enseguida (Ctrl+V) en cualquier documento.
// Sustituye al aviso «Captura de pantalla realizada» (como macOS, no queda en la lista de
// avisos); las grabaciones de pantalla siguen avisando como siempre.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';

import {CropEditor} from './cropEditor.js';
import {_} from './i18n.js';

const SOURCE_ICON = 'screenshooter-symbolic';
const WIDTH = 220;
const MARGIN = 20;
const SHOW_MS = 2200;                // se va pronto; con el puntero encima se queda
const DOCK_CLEARANCE = 110;          // por encima del dock, no tapándolo
const SLIDE_MS = 250;

export class ScreenshotPreview {
    constructor() {
        Main.messageTray.connectObject('source-added', (_tray, source) => this._watch(source), this);
        Main.messageTray.getSources().forEach(source => this._watch(source));
    }

    _watch(source) {
        // El aviso de capturas de GNOME es el de este icono («Captura de pantalla»).
        if (!(source.icon?.get_names?.() ?? []).includes(SOURCE_ICON))
            return;
        source.connectObject('notification-added', (_source, notification) => {
            // Sólo las capturas llevan la imagen; las grabaciones conservan su aviso.
            if (notification.gicon instanceof St.ImageContent)
                this._show(notification);
        }, this);
    }

    _show(notification) {
        // Sin el aviso: la miniatura lo sustituye y se lo lleva al irse.
        notification.urgency = MessageTray.Urgency.LOW;
        this._hide(true);
        this._notification = notification;
        notification.connectObject('destroy', () => {
            if (this._notification === notification)
                this._notification = null;
        }, this);

        const content = notification.gicon;
        const [, width, height] = content.get_preferred_size();
        const imageHeight = Math.round(WIDTH * Math.min(1, height / Math.max(1, width)));
        const image = new St.Widget({
            style_class: 'macify-shot-image',
            content,
            content_gravity: Clutter.ContentGravity.RESIZE_ASPECT,
            width: WIDTH,
            height: imageHeight,
        });
        const hint = new St.Label({style_class: 'macify-shot-hint', text: _('Copied · Ctrl+V to paste')});
        const box = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL, style_class: 'macify-shot-box'});
        box.add_child(image);
        box.add_child(hint);
        const actions = new St.BoxLayout({style_class: 'macify-shot-actions', x_align: Clutter.ActorAlign.CENTER});
        const crop = new St.Button({label: _('Crop'), style_class: 'macify-shot-action'});
        crop.connect('clicked', () => this._crop());
        actions.add_child(crop);
        box.add_child(actions);
        const actor = new St.Button({style_class: 'macify-shot', child: box, reactive: true, can_focus: false});
        actor.connect('clicked', () => {
            this._notification?.activate();                     // abre la imagen
            this._hide();
        });
        // Con el puntero encima no se va; al salir, espera de nuevo.
        actor.connect('notify::hover', () => {
            if (actor !== this._actor)
                return;
            if (actor.hover)
                this._stopTimer();
            else
                this._startTimer();
        });
        this._actor = actor;
        Main.layoutManager.addTopChrome(actor);

        const monitor = Main.layoutManager.monitors[global.display.get_current_monitor()] ??
            Main.layoutManager.primaryMonitor;
        const area = Main.layoutManager.getWorkAreaForMonitor(monitor.index);
        const [, natWidth] = actor.get_preferred_width(-1);
        const [, natHeight] = actor.get_preferred_height(natWidth);
        actor.set_position(area.x + area.width - natWidth - MARGIN, area.y + area.height - natHeight - DOCK_CLEARANCE);
        // Sobre una app a pantalla completa también se ve.
        global.compositor.disable_unredirect();
        actor.translation_x = natWidth + MARGIN;
        actor.ease({translation_x: 0, duration: SLIDE_MS, mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
        this._startTimer();
    }

    // Abre el recortador con la captura más reciente (la que GNOME acaba de guardar).
    _crop() {
        const path = this._latestFile();
        this._hide(true);
        if (!path)
            return;
        try {
            this._editor = new CropEditor(path, () => {
                this._editor = null;
            });
        } catch (e) {
            console.warn(`Macify: crop: ${e.message}`);
        }
    }

    _latestFile() {
        const pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES);
        let newest = null;
        for (const dir of [`${pictures}/Screenshots`, pictures]) {
            const folder = Gio.File.new_for_path(dir);
            if (!folder.query_exists(null))
                continue;
            const list = folder.enumerate_children('standard::name,time::modified', Gio.FileQueryInfoFlags.NONE, null);
            for (let info = list.next_file(null); info; info = list.next_file(null)) {
                if (!info.get_name().toLowerCase().endsWith('.png'))
                    continue;
                const time = info.get_modification_date_time().to_unix();
                if (!newest || time > newest.time)
                    newest = {time, path: `${dir}/${info.get_name()}`};
            }
            if (newest)
                break;
        }
        return newest && GLib.get_real_time() / 1e6 - newest.time < 30 ? newest.path : null;
    }

    _startTimer() {
        this._stopTimer();
        this._timerId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, SHOW_MS, () => {
            this._timerId = 0;
            this._hide();
            return GLib.SOURCE_REMOVE;
        });
    }

    _stopTimer() {
        if (this._timerId)
            GLib.source_remove(this._timerId);
        this._timerId = 0;
    }

    _hide(now = false) {
        this._stopTimer();
        const actor = this._actor;
        if (!actor)
            return;
        this._actor = null;
        const notification = this._notification;
        this._notification = null;
        notification?.destroy();
        const done = () => {
            Main.layoutManager.removeChrome(actor);
            actor.destroy();
            global.compositor.enable_unredirect();
        };
        if (now) {
            actor.remove_all_transitions();
            done();
            return;
        }
        actor.ease({
            translation_x: actor.width + MARGIN,
            duration: SLIDE_MS,
            mode: Clutter.AnimationMode.EASE_IN_CUBIC,
            onStopped: done,
        });
    }

    destroy() {
        this._editor?.close();
        this._hide(true);
        Main.messageTray.disconnectObject(this);
        Main.messageTray.getSources().forEach(source => source.disconnectObject(this));
    }
}
