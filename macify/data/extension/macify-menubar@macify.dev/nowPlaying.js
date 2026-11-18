// «Ahora suena»: el panel que se abre al pulsar la cápsula de música, como en el Centro de
// control de macOS. Carátula, título, progreso (se puede adelantar), anterior / pausa /
// siguiente y volumen del sistema. La posición sólo se consulta mientras está abierto.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
import Shell from 'gi://Shell';
import St from 'gi://St';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Slider from 'resource:///org/gnome/shell/ui/slider.js';

import {_} from './i18n.js';
import {AppVolume} from './systemVolume.js';

const VERTICAL = Clutter.Orientation.VERTICAL;

function clock(microseconds) {
    const seconds = Math.max(0, Math.floor(microseconds / 1e6));
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = String(seconds % 60).padStart(2, '0');
    return h ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

function label(style, text = '') {
    const widget = new St.Label({text, style_class: style, x_expand: true});
    widget.clutter_text.ellipsize = Pango.EllipsizeMode.END;
    return widget;
}

function iconButton(icon, name, action) {
    const button = new St.Button({
        style_class: 'macify-np-button',
        child: new St.Icon({icon_name: icon, icon_size: 20}),
        accessible_name: name,
        can_focus: true,
    });
    button.connect('clicked', action);
    return button;
}

export class NowPlaying {
    constructor(menu, volume, onSelect) {
        this._menu = menu;
        this._volume = volume;
        this._onSelect = onSelect;
        this._player = null;

        const item = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
        item.add_style_class_name('macify-np');
        // Es información, no una opción: sin el gris de «no disponible» que le pone el tema.
        item.remove_style_class_name('popup-inactive-menu-item');
        item.remove_style_pseudo_class('insensitive');
        const box = new St.BoxLayout({orientation: VERTICAL, x_expand: true, style_class: 'macify-np-box'});

        // Con varias apps sonando (un curso y la música), se elige cuál controlar.
        this._sources = new St.BoxLayout({style_class: 'macify-np-sources', x_expand: true});

        const header = new St.BoxLayout({style_class: 'macify-np-header'});
        this._art = new St.Icon({style_class: 'macify-np-art', icon_size: 56, fallback_icon_name: 'audio-x-generic-symbolic'});
        const titles = new St.BoxLayout({orientation: VERTICAL, x_expand: true, y_align: Clutter.ActorAlign.CENTER});
        this._title = label('macify-np-title');
        this._artist = label('macify-np-artist');
        this._app = label('macify-np-app');
        titles.add_child(this._title);
        titles.add_child(this._artist);
        titles.add_child(this._app);
        header.add_child(this._art);
        header.add_child(titles);

        this._progress = new Slider.Slider(0);
        this._progress.add_style_class_name('macify-slider');
        this._progress.add_style_class_name('macify-np-progress');
        this._progress.connect('drag-end', () => this._player?.seek(this._progress.value));
        const times = new St.BoxLayout({style_class: 'macify-np-times'});
        this._elapsed = new St.Label({style_class: 'macify-np-time', x_expand: true});
        this._remaining = new St.Label({style_class: 'macify-np-time'});
        times.add_child(this._elapsed);
        times.add_child(this._remaining);

        const controls = new St.BoxLayout({style_class: 'macify-np-controls', x_align: Clutter.ActorAlign.CENTER});
        this._previous = iconButton('media-skip-backward-symbolic', _('Previous'), () => this._player?.previous());
        this._play = iconButton('media-playback-pause-symbolic', _('Play/Pause'), () => this._player?.playPause());
        this._next = iconButton('media-skip-forward-symbolic', _('Next'), () => this._player?.next());
        this._play.add_style_class_name('macify-np-play');
        [this._previous, this._play, this._next].forEach(b => controls.add_child(b));

        // Volumen sólo de esta app (Spotify, el navegador con YouTube...), sin tocar el general.
        this._appVolume = new AppVolume();
        this._appVolumeRow = new St.BoxLayout({style_class: 'macify-np-volume macify-np-app-volume'});
        this._appVolumeIcon = new St.Icon({icon_name: 'audio-x-generic-symbolic', icon_size: 16,
            style_class: 'macify-np-app-icon'});
        this._appVolumeSlider = new Slider.Slider(0);
        this._appVolumeSlider.add_style_class_name('macify-slider');
        this._appVolumeSlider.add_style_class_name('macify-np-app-slider');
        this._appVolumeSlider.accessible_name = _('App volume');
        this._appVolumeSlider.connect('notify::value', () => {
            if (!this._syncing)
                this._appVolume.setLevel(this._player, this._appVolumeSlider.value);
        });
        this._appVolumeLabel = new St.Label({text: _('App'), style_class: 'macify-np-volume-label',
            y_align: Clutter.ActorAlign.CENTER});
        this._appVolumeRow.add_child(this._appVolumeIcon);
        this._appVolumeRow.add_child(this._appVolumeSlider);
        this._appVolumeRow.add_child(this._appVolumeLabel);

        this._volumeRow = new St.BoxLayout({style_class: 'macify-np-volume'});
        this._volumeSlider = new Slider.Slider(0);
        this._volumeSlider.add_style_class_name('macify-slider');
        this._volumeSlider.connect('notify::value', () => {
            if (!this._syncing)
                this._volume.level = this._volumeSlider.value;
        });
        this._volumeRow.add_child(new St.Icon({icon_name: 'audio-volume-low-symbolic', icon_size: 16}));
        this._volumeRow.add_child(this._volumeSlider);
        this._volumeRow.add_child(new St.Label({text: _('System'), style_class: 'macify-np-volume-label',
            y_align: Clutter.ActorAlign.CENTER}));

        [this._sources, header, this._progress, times, controls, this._appVolumeRow, this._volumeRow].forEach(w => box.add_child(w));
        item.add_child(box);
        menu.addMenuItem(item);
        this.item = item;

        menu.connect('open-state-changed', (_m, open) => (open ? this._startTicking() : this._stopTicking()));
    }

    show(player, players = []) {
        this._player = player;
        if (!player)
            return;
        this._showSources(player, players);
        if (player.art)
            this._art.gicon = player.art;
        else
            this._art.icon_name = 'audio-x-generic-symbolic';
        this._title.text = player.title || player.appName;
        this._artist.text = player.artist;
        this._artist.visible = Boolean(player.artist);
        this._app.text = player.appName;
        this._play.child.icon_name = player.status === 'Playing'
            ? 'media-playback-pause-symbolic' : 'media-playback-start-symbolic';
        this._previous.reactive = player.canPrevious;
        this._next.reactive = player.canNext;
        this._previous.opacity = player.canPrevious ? 255 : 90;
        this._next.opacity = player.canNext ? 255 : 90;
        this._progress.reactive = player.canSeek;
        this._volumeRow.visible = this._volume.available;
        this._syncAppVolume();
    }

    _syncAppVolume() {
        const player = this._player;
        const found = this._appVolume.available(player);
        this._appVolumeRow.visible = found;
        if (!found)
            return;
        const system = Shell.AppSystem.get_default();
        const name = player.appName ?? '';
        const app = system.lookup_desktop_wmclass(name) ?? system.lookup_startup_wmclass(name) ??
            system.lookup_heuristic_basename?.(`${name.toLowerCase()}.desktop`) ?? null;
        this._appVolumeIcon.gicon = app?.get_icon() ?? null;
        if (!app)
            this._appVolumeIcon.icon_name = 'audio-x-generic-symbolic';
        this._appVolumeLabel.text = player.appName || _('App');
        const syncing = this._syncing;
        this._syncing = true;
        this._appVolumeSlider.value = this._appVolume.level(player);
        this._syncing = syncing;
    }

    _showSources(active, players) {
        this._sources.destroy_all_children();
        this._sources.visible = players.length > 1;
        for (const player of players) {
            const button = new St.Button({
                label: player.appName,
                style_class: 'macify-np-source',
                toggle_mode: true,
                checked: player === active,
                can_focus: true,
            });
            button.connect('clicked', () => this._onSelect(player));
            this._sources.add_child(button);
        }
    }

    _syncVolume() {
        this._syncing = true;
        this._volumeSlider.maximum_value = this._volume.maxLevel;
        this._volumeSlider.clearMarks?.();
        if (this._volume.maxLevel > 1)
            this._volumeSlider.addMark?.(1);
        this._volumeSlider.value = this._volume.level;
        this._syncing = false;
    }

    _tick() {
        const player = this._player;
        if (!player || !player.length) {
            this._progress.visible = false;
            this._elapsed.text = this._remaining.text = '';
            return;
        }
        this._progress.visible = true;
        player.fetchPosition(position => {
            if (position === null || this._progress._grab)
                return;
            this._progress.value = Math.min(1, position / player.length);
            this._elapsed.text = clock(position);
            this._remaining.text = `−${clock(player.length - position)}`;
        });
    }

    _startTicking() {
        this._syncVolume();
        if (this._player)
            this._syncAppVolume();
        this._tick();
        this._tickId ??= GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._tick();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _stopTicking() {
        if (this._tickId)
            GLib.source_remove(this._tickId);
        this._tickId = null;
    }

    destroy() {
        this._stopTicking();
    }
}
