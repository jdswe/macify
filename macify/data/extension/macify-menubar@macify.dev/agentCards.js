// La tarjeta de los agentes: al pulsar la cápsula con un agente, se ve cada aviso completo
// (quién, qué pasa, hace cuánto y el texto entero) con «Abrir» y «Descartar». Si además suena
// música, «Ahora suena» sigue debajo.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
import St from 'gi://St';

import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {_} from './i18n.js';

const VERTICAL = Clutter.Orientation.VERTICAL;
const MAX_TEXT = 600;
const LOOK = {
    waiting: ['dialog-question-symbolic', 'Needs you'],
    failed: ['dialog-error-symbolic', 'Failed'],
    done: ['object-select-symbolic', 'Done'],
};

function ago(microseconds) {
    const minutes = Math.floor((GLib.get_real_time() - microseconds) / 60e6);
    if (minutes < 1)
        return _('now');
    if (minutes < 60)
        return _('{n} min ago', {n: minutes});
    return _('{n} h ago', {n: Math.floor(minutes / 60)});
}

function wrapped(text, style) {
    const label = new St.Label({text, style_class: style, x_expand: true});
    label.clutter_text.line_wrap = true;
    label.clutter_text.line_wrap_mode = Pango.WrapMode.WORD_CHAR;
    label.clutter_text.ellipsize = Pango.EllipsizeMode.NONE;
    return label;
}

export class AgentCards {
    constructor(menu, agents) {
        this._menu = menu;
        this._agents = agents;
        this.section = new PopupMenu.PopupMenuSection();
        menu.addMenuItem(this.section, 0);
    }

    get count() {
        return this._agents.items.length;
    }

    fill() {
        this.section.removeAll();
        const items = this._agents.items;
        this.section.actor.visible = items.length > 0;
        if (!items.length)
            return;
        const holder = new PopupMenu.PopupBaseMenuItem({reactive: false, can_focus: false});
        holder.add_style_class_name('macify-agents');
        holder.remove_style_class_name('popup-inactive-menu-item');
        holder.remove_style_pseudo_class('insensitive');
        const list = new St.BoxLayout({orientation: VERTICAL, x_expand: true, style_class: 'macify-agents-list'});
        items.forEach(item => list.add_child(this._card(item)));
        holder.add_child(list);
        this.section.addMenuItem(holder);
    }

    _card(item) {
        const [icon, state] = LOOK[item.state] ?? LOOK.waiting;
        const card = new St.BoxLayout({orientation: VERTICAL, style_class: `macify-agent-card macify-agent-${item.state}`,
            x_expand: true});
        const header = new St.BoxLayout({style_class: 'macify-agent-header'});
        header.add_child(new St.Icon({icon_name: icon, icon_size: 16, style_class: 'macify-agent-icon',
            y_align: Clutter.ActorAlign.CENTER}));
        header.add_child(new St.Label({text: item.name, style_class: 'macify-agent-name', y_align: Clutter.ActorAlign.CENTER}));
        header.add_child(new St.Label({text: `${_(state)} · ${ago(item.realTime)}`, style_class: 'macify-agent-meta',
            x_expand: true, y_align: Clutter.ActorAlign.CENTER}));
        card.add_child(header);
        if (item.title)
            card.add_child(wrapped(item.title, 'macify-agent-title'));
        const body = item.body.length > MAX_TEXT ? `${item.body.slice(0, MAX_TEXT - 1)}…` : item.body;
        if (body)
            card.add_child(wrapped(body, 'macify-agent-body'));

        const actions = new St.BoxLayout({style_class: 'macify-agent-actions', x_align: Clutter.ActorAlign.END});
        const dismiss = new St.Button({label: _('Dismiss'), style_class: 'macify-agent-button', can_focus: true});
        dismiss.connect('clicked', () => {
            this._agents.dismiss(item);
            if (this.count)
                this.fill();
            else
                this._menu.close();
        });
        const open = new St.Button({label: _('Open'), style_class: 'macify-agent-button macify-agent-open', can_focus: true});
        open.connect('clicked', () => {
            this._menu.close();
            this._agents.open(item);
        });
        actions.add_child(dismiss);
        actions.add_child(open);
        card.add_child(actions);
        card._openButton = open;
        card._dismissButton = dismiss;
        return card;
    }

    destroy() {
        this.section.destroy();
    }
}
