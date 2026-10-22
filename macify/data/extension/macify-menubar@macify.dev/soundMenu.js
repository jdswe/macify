// Menú de sonido, como el de macOS: volumen de salida y la lista de dispositivos de salida
// (altavoces, auriculares, HDMI…). Usa el mismo control de audio que GNOME.

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Slider from 'resource:///org/gnome/shell/ui/slider.js';
import * as Volume from 'resource:///org/gnome/shell/ui/status/volume.js';

import {_} from './i18n.js';
import {header, separator, settingsItem} from './menuParts.js';

export class SoundMenu {
    constructor(menu) {
        this._control = Volume.getMixerControl();
        header(menu, _('Sound'));
        const sliderItem = new PopupMenu.PopupBaseMenuItem({activate: false});
        this._slider = new Slider.Slider(0);
        this._slider.connect('notify::value', () => {
            if (!this._syncing)
                this._setVolume(this._slider.value);
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

    _setVolume(value) {
        const sink = this._control.get_default_sink();
        if (!sink)
            return;
        sink.volume = Math.round(value * this._control.get_vol_max_norm());
        if (sink.is_muted && value > 0)
            sink.change_is_muted(false);
        sink.push_volume();
    }

    _refresh() {
        const sink = this._control.get_default_sink();
        this._syncing = true;
        this._slider.value = sink && !sink.is_muted ? sink.volume / this._control.get_vol_max_norm() : 0;
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
