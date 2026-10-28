// Recortar una captura: la imagen a gran tamaño, se arrastra un rectángulo y se guarda
// (Intro o «Crop»). El recorte reemplaza al archivo de la captura y queda copiado al
// portapapeles; Esc cancela.

import Clutter from 'gi://Clutter';
import Cogl from 'gi://Cogl';
import GdkPixbuf from 'gi://GdkPixbuf';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {_} from './i18n.js';

const MIN_SIZE = 8;

// Un GdkPixbuf como contenido de un actor de St.
export function imageContent(pixbuf) {
    const image = new St.ImageContent({preferred_width: pixbuf.width, preferred_height: pixbuf.height});
    image.set_bytes(global.stage.context.get_backend().get_cogl_context(), pixbuf.read_pixel_bytes(),
        pixbuf.has_alpha ? Cogl.PixelFormat.RGBA_8888 : Cogl.PixelFormat.RGB_888,
        pixbuf.width, pixbuf.height, pixbuf.rowstride);
    return image;
}

export class CropEditor {
    constructor(path, onDone) {
        this._path = path;
        this._onDone = onDone;
        this._pixbuf = GdkPixbuf.Pixbuf.new_from_file(path);
        const monitor = Main.layoutManager.currentMonitor ?? Main.layoutManager.primaryMonitor;
        this._root = new St.Widget({style_class: 'macify-crop', reactive: true, can_focus: true,
            x: monitor.x, y: monitor.y, width: monitor.width, height: monitor.height});
        const scale = Math.min(1, (monitor.width * 0.84) / this._pixbuf.width, (monitor.height * 0.74) / this._pixbuf.height);
        this._w = Math.round(this._pixbuf.width * scale);
        this._h = Math.round(this._pixbuf.height * scale);
        this._ox = Math.round((monitor.width - this._w) / 2);
        this._oy = Math.round((monitor.height - this._h) / 2) - 24;
        const picture = new St.Widget({x: this._ox, y: this._oy, width: this._w, height: this._h,
            style_class: 'macify-crop-picture'});
        picture.set_content(this._content());
        picture.content_gravity = Clutter.ContentGravity.RESIZE_FILL;
        this._root.add_child(picture);
        this._box = new St.Widget({style_class: 'macify-crop-box', x: this._ox, y: this._oy, width: this._w, height: this._h});
        this._root.add_child(this._box);

        const bar = new St.BoxLayout({style_class: 'macify-crop-bar', x_align: Clutter.ActorAlign.CENTER});
        const cancel = new St.Button({label: _('Cancel'), style_class: 'macify-crop-button'});
        const save = new St.Button({label: _('Crop'), style_class: 'macify-crop-button macify-crop-save'});
        cancel.connect('clicked', () => this.close());
        save.connect('clicked', () => this._save());
        bar.add_child(cancel);
        bar.add_child(save);
        this._root.add_child(bar);
        bar.set_position(Math.round((monitor.width - 220) / 2), this._oy + this._h + 22);

        this._sel = {x: 0, y: 0, w: this._w, h: this._h};
        this._root.connect('button-press-event', (_a, event) => this._press(event));
        this._root.connect('motion-event', (_a, event) => this._motion(event));
        this._root.connect('button-release-event', () => {
            this._start = null;
            return Clutter.EVENT_STOP;
        });
        this._root.connect('key-press-event', (_a, event) => {
            const key = event.get_key_symbol();
            if (key === Clutter.KEY_Escape)
                this.close();
            else if (key === Clutter.KEY_Return || key === Clutter.KEY_KP_Enter)
                this._save();
            return Clutter.EVENT_STOP;
        });
        Main.uiGroup.add_child(this._root);
        this._grab = Main.pushModal(this._root);
        this._root.grab_key_focus();
    }

    _content() {
        return imageContent(this._pixbuf);
    }

    _local(event) {
        const [x, y] = event.get_coords();
        return [Math.max(0, Math.min(this._w, x - this._root.x - this._ox)),
            Math.max(0, Math.min(this._h, y - this._root.y - this._oy))];
    }

    _press(event) {
        this._start = this._local(event);
        this._select(this._start, this._start);
        return Clutter.EVENT_STOP;
    }

    _motion(event) {
        if (this._start)
            this._select(this._start, this._local(event));
        return Clutter.EVENT_STOP;
    }

    _select([x1, y1], [x2, y2]) {
        this._sel = {x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1)};
        this._box.set_position(this._ox + this._sel.x, this._oy + this._sel.y);
        this._box.set_size(Math.max(1, this._sel.w), Math.max(1, this._sel.h));
    }

    _save() {
        const ratio = this._pixbuf.width / this._w;
        const x = Math.round(this._sel.x * ratio);
        const y = Math.round(this._sel.y * ratio);
        const w = Math.min(this._pixbuf.width - x, Math.round(this._sel.w * ratio));
        const h = Math.min(this._pixbuf.height - y, Math.round(this._sel.h * ratio));
        if (w >= MIN_SIZE && h >= MIN_SIZE) {
            const cropped = this._pixbuf.new_subpixbuf(x, y, w, h);
            cropped.savev(this._path, 'png', [], []);
            const [, buffer] = cropped.save_to_bufferv('png', [], []);
            St.Clipboard.get_default().set_content(St.ClipboardType.CLIPBOARD, 'image/png', new GLib.Bytes(buffer));
        }
        this.close();
    }

    close() {
        if (this._grab)
            Main.popModal(this._grab);
        this._grab = null;
        this._root?.destroy();
        this._root = null;
        this._onDone?.();
    }
}
