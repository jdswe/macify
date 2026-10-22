// Piezas comunes de los menús de la barra al estilo macOS: un encabezado en negrita con un
// valor a la derecha, filas de acción y el acceso a la página de Ajustes correspondiente.

import Clutter from 'gi://Clutter';
import St from 'gi://St';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

export function header(menu, title) {
    const item = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false, style_class: 'macify-extra-header'});
    // Es información, no una opción: sin el gris de «no disponible» que le pone el tema.
    item.remove_style_class_name('popup-inactive-menu-item');
    item.remove_style_pseudo_class('insensitive');
    const label = new St.Label({text: title, style_class: 'macify-extra-title', x_expand: true});
    const value = new St.Label({style_class: 'macify-extra-value', x_align: Clutter.ActorAlign.END});
    item.add_child(label);
    item.add_child(value);
    menu.addMenuItem(item);
    return value;
}

export function infoRow(menu) {
    const item = new PopupMenu.PopupMenuItem('', {reactive: false, can_focus: false});
    item.add_style_class_name('macify-extra-info');
    menu.addMenuItem(item);
    return item;
}

export function separator(menu) {
    menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
}

export function settingsItem(menu, label, panel) {
    const item = new PopupMenu.PopupMenuItem(label);
    item.connect('activate', () => Util.spawn(['gnome-control-center', panel]));
    menu.addMenuItem(item);
    return item;
}
