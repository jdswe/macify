// Menú de sonido, como el de macOS: volumen de salida y la lista de dispositivos de salida
// (altavoces, auriculares, HDMI…). Usa el mismo control de audio que GNOME y, si está activada
// la sobreamplificación, sube por encima del 100 % con una marca en el 100 %.

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Slider from 'resource:///org/gnome/shell/ui/slider.js';
import * as Volume from 'resource:///org/gnome/shell/ui/status/volume.js';

import {_} from './i18n.js';
import {header, separator, settingsItem} from './menuParts.js';
import {SystemVolume} from './systemVolume.js';

export class SoundMenu {
    constructor(menu) {
        this._control = Volume.getMixerControl();
        this._volume = new SystemVolume();
        header(menu, _('Sound'));
        const sliderItem = new PopupMenu.PopupBaseMenuItem({activate: false});
        this._slider = new Slider.Slider(0);
        this._slider.connect('notify::value', () => {
            if (!this._syncing)
                this._volume.level = this._slider.value;
        });
        sliderItem.add_child(this._slider);
        menu.addMenuItem(sliderItem);
        separator(menu);
        this._outputsTitle = new PopupMenu.PopupMenuItem(_('Output'), {reactive: false, can_focus: false});
        this._outputsTitle.add_style_class_name('macify-extra-section');
        menu.addMenuItem(this._outputsTitle);
        this._outputs = new PopupMenu.PopupMenuSection();
        menu.addMenuItem(this._outputs);
        separator(menu);
        settingsItem(menu, _('Sound Settings…'), 'sound');
        menu.connect('open-state-changed', (_m, open) => {
            if (open)
                this._refresh();
        });
    }

    _refresh() {
        const sink = this._control.get_default_sink();
        this._syncing = true;
        this._slider.maximum_value = this._volume.maxLevel;
        this._slider.clearMarks?.();
        if (this._volume.maxLevel > 1)
            this._slider.addMark?.(1);         // el 100 %, como en el control de GNOME
        this._slider.value = this._volume.level;
        this._syncing = false;
        this._outputs.removeAll();
        const devices = this._control.get_sinks()
            .map(stream => this._control.lookup_device_from_stream(stream))
            .filter(Boolean);
        const active = sink ? this._control.lookup_device_from_stream(sink) : null;
        for (const device of devices) {
            const label = device.get_origin() ? `${device.get_description()} — ${device.get_origin()}` : device.get_description();
            const item = new PopupMenu.PopupMenuItem(label);
            if (active && device.get_id() === active.get_id())
                item.setOrnament(PopupMenu.Ornament.CHECK);
            item.connect('activate', () => this._control.change_output(device));
            this._outputs.addMenuItem(item);
        }
        this._outputsTitle.visible = devices.length > 0;
    }

    destroy() {}
}
