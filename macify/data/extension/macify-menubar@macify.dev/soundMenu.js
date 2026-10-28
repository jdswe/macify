// Menú de sonido, como el de macOS: volumen y dispositivos de salida (altavoces, auriculares,
// HDMI…) y de entrada (micrófonos), con el nivel del micrófono y un interruptor para
// silenciarlo. Usa el mismo control de audio que GNOME y, si está activada la
// sobreamplificación, el volumen sube por encima del 100 % con una marca en el 100 %.

import Clutter from 'gi://Clutter';
import St from 'gi://St';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Slider from 'resource:///org/gnome/shell/ui/slider.js';
import * as Volume from 'resource:///org/gnome/shell/ui/status/volume.js';

import {_} from './i18n.js';
import {header, separator, settingsItem} from './menuParts.js';
import {SystemVolume} from './systemVolume.js';

export class SoundMenu {
    constructor(menu, indicator) {
        this._menu = menu;
        this._control = Volume.getMixerControl();
        // El icono de la barra (el de GNOME, con los iconos de Macify) da un pequeño salto al
        // cambiar el volumen o silenciar, también con las teclas del equipo.
        this._barIcon = indicator?._indicator ?? null;
        this._barIcon?.set_pivot_point(0.5, 0.5);
        this._control.connectObject('default-sink-changed', () => this._watchSink(), this);
        this._watchSink();
        this._volume = new SystemVolume();
        header(menu, _('Sound'));
        const sliderItem = new PopupMenu.PopupBaseMenuItem({activate: false});
        this._slider = new Slider.Slider(0);
        this._slider.add_style_class_name('macify-slider');
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
        this._inputsTitle = new PopupMenu.PopupMenuItem(_('Input'), {reactive: false, can_focus: false});
        this._inputsTitle.add_style_class_name('macify-extra-section');
        menu.addMenuItem(this._inputsTitle);
        this._micSwitch = new PopupMenu.PopupSwitchMenuItem(_('Microphone'), true);
        this._micSwitch.connect('toggled', (_i, on) => this._control.get_default_source()?.change_is_muted(!on));
        menu.addMenuItem(this._micSwitch);
        this._micItem = new PopupMenu.PopupBaseMenuItem({activate: false});
        this._micItem.add_child(new St.Icon({icon_name: 'audio-input-microphone-symbolic', style_class: 'popup-menu-icon'}));
        this._micSlider = new Slider.Slider(0);
        this._micSlider.add_style_class_name('macify-slider');
        this._micSlider.connect('notify::value', () => {
            if (!this._syncing)
                this._setMicLevel(this._micSlider.value);
        });
        this._micItem.add_child(this._micSlider);
        menu.addMenuItem(this._micItem);
        this._inputs = new PopupMenu.PopupMenuSection();
        menu.addMenuItem(this._inputs);
        this._inputsSeparator = new PopupMenu.PopupSeparatorMenuItem();
        menu.addMenuItem(this._inputsSeparator);
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
        this._refreshInputs();
    }

    _watchSink() {
        this._sink?.disconnectObject(this);
        this._sink = this._control.get_default_sink();
        this._sink?.connectObject(
            'notify::volume', () => this._changed(),
            'notify::is-muted', () => this._changed(),
            this);
    }

    _changed() {
        if (this._menu.isOpen && !this._syncing && !this._slider._grab) {
            this._syncing = true;
            this._slider.value = this._volume.level;
            this._syncing = false;
        }
        const icon = this._barIcon;
        if (!icon?.mapped || icon._macifyBump)
            return;
        icon._macifyBump = true;
        icon.ease({
            scale_x: 1.22, scale_y: 1.22, duration: 90, mode: Clutter.AnimationMode.EASE_OUT_QUAD,
            onStopped: () => icon.ease({
                scale_x: 1, scale_y: 1, duration: 160, mode: Clutter.AnimationMode.EASE_OUT_BACK,
                onStopped: () => (icon._macifyBump = false),
            }),
        });
    }

    _setMicLevel(value) {
        const source = this._control.get_default_source();
        if (!source)
            return;
        source.volume = Math.round(value * this._control.get_vol_max_norm());
        if (source.is_muted && value > 0)
            source.change_is_muted(false);
        source.push_volume();
    }

    _refreshInputs() {
        const source = this._control.get_default_source();
        const devices = this._control.get_sources()
            .map(stream => this._control.lookup_device_from_stream(stream))
            .filter(Boolean);
        const shown = Boolean(source) || devices.length > 0;
        [this._inputsTitle, this._micSwitch, this._micItem, this._inputsSeparator].forEach(w => (w.visible = shown));
        this._inputs.removeAll();
        if (!shown)
            return;
        this._syncing = true;
        this._micSwitch.setToggleState(Boolean(source) && !source.is_muted);
        this._micSlider.value = source ? source.volume / this._control.get_vol_max_norm() : 0;
        this._syncing = false;
        this._micItem.visible = Boolean(source);
        if (devices.length < 2)
            return;         // con un solo micrófono no hay nada que elegir
        const active = source ? this._control.lookup_device_from_stream(source) : null;
        for (const device of devices) {
            const label = device.get_origin() ? `${device.get_description()} — ${device.get_origin()}` : device.get_description();
            const item = new PopupMenu.PopupMenuItem(label);
            if (active && device.get_id() === active.get_id())
                item.setOrnament(PopupMenu.Ornament.CHECK);
            item.connect('activate', () => this._control.change_input(device));
            this._inputs.addMenuItem(item);
        }
    }

    destroy() {
        this._control.disconnectObject(this);
        this._sink?.disconnectObject(this);
        if (this._barIcon) {
            this._barIcon.remove_all_transitions();
            this._barIcon.set_scale(1, 1);
            this._barIcon._macifyBump = false;
        }
    }
}
