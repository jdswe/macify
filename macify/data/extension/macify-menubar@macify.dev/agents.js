// Agentes de programación en la isla: cuando Claude Code, Codex/ChatGPT, Copilot, Cursor,
// Gemini u otro agente avisa que necesita tu respuesta, que terminó o que algo falló, la
// cápsula lo dice y se queda (si espera algo de ti) hasta que lo atiendes. Un clic abre la
// ventana del agente, como pulsar su aviso.
// No lee nada más que los avisos que esas apps ya envían a GNOME, y nada sale del equipo.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import * as Signals from 'resource:///org/gnome/shell/misc/signals.js';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Quién avisa: el nombre de la app o el título del aviso (no el texto, para no confundir un
// correo que menciona a Claude con el agente).
const AGENTS = [
    ['Claude Code', /claude[\s._-]*code/i],
    ['Claude', /\bclaude\b|anthropic/i],
    ['Codex', /\bcodex\b/i],
    ['ChatGPT', /chatgpt|openai/i],
    ['Copilot', /copilot/i],
    ['Cursor', /\bcursor\b/i],
    ['Gemini', /\bgemini\b/i],
    ['Aider', /\baider\b/i],
    ['Windsurf', /windsurf|codeium/i],
    ['OpenCode', /opencode/i],
];

const WAITING = /permission|approv|waiting|needs? (your )?(input|attention|answer|response)|question|confirm|respond|reply|idle|blocked|permiso|esperando|aprobar|confirmar|pregunta|responder/i;
const FAILED = /\b(error|failed|failure|crash(ed)?|exception)\b|fall[óo]|errores?/i;
const DONE = /\b(done|finished|complete(d)?|ready|succeeded|success)\b|termin[óo]|listo|completad[oa]/i;

// Claude Code connected with `macify claude connect` asks here (Allow / Deny) and tells when it
// finished. See macify/agent_hook.py: if nobody answers, Claude Code asks in its terminal.
const BRIDGE_XML = `<node><interface name="dev.macify.Agents">
  <method name="Ask"><arg type="s" direction="in"/><arg type="au" direction="in"/><arg type="u" direction="in"/>
    <arg type="s" direction="out"/></method>
  <method name="Tell"><arg type="s" direction="in"/><arg type="au" direction="in"/></method>
</interface></node>`;
const BRIDGE_PATH = '/dev/macify/Agents';
const RANK = {approve: 0, waiting: 1, failed: 2, done: 3};

const WAITING_MAX_MS = 30 * 60 * 1000;     // un aviso de espera olvidado se retira solo
const DONE_MS = 7000;                      // «terminó» y «falló» se ven unos segundos

export function agentName(...texts) {
    const text = texts.filter(Boolean).join(' ');
    return AGENTS.find(([, pattern]) => pattern.test(text))?.[0] ?? null;
}

export function agentState(title, body) {
    const text = `${title ?? ''} ${body ?? ''}`;
    if (WAITING.test(text))
        return 'waiting';
    if (FAILED.test(text))
        return 'failed';
    if (DONE.test(text))
        return 'done';
    return 'waiting';           // un agente que avisa sin decir qué, suele esperar algo
}

function plain(text) {
    return String(text ?? '').replace(/<[^>]+>/g, '').replace(/[ \t]+/g, ' ').trim();
}

// Lo que dice la cápsula: el agente y lo esencial del aviso, sin repetir el nombre.
function summary(name, title, body) {
    let text = (plain(body) || plain(title)).replace(/\s+/g, ' ');
    text = text.replace(new RegExp(`^${name}\\s*[:·-]?\\s*`, 'i'), '');
    return text ? `${name} · ${text}` : name;
}

export class Agents extends Signals.EventEmitter {
    constructor() {
        super();
        this._items = [];               // {notification, name, state, text, time}
        const watch = source => source.connectObject('notification-added',
            (_source, notification) => this._add(source, notification), this);
        Main.messageTray.connectObject('source-added', (_tray, source) => watch(source), this);
        Main.messageTray.getSources().forEach(watch);
        this._bridge = Gio.DBusExportedObject.wrapJSObject(BRIDGE_XML, this);
        try {
            this._bridge.export(Gio.DBus.session, BRIDGE_PATH);
        } catch (e) {
            console.warn(`Macify: agents bridge: ${e.message}`);
        }
    }

    // ¿Estás mirando la terminal del agente? Entonces responde allí, como siempre.
    _watching(pids) {
        const pid = global.display.focus_window?.get_pid?.() ?? 0;
        return pid > 0 && pids.includes(pid);
    }

    _bridgeItem(info, state, extra = {}) {
        const name = info.agent || 'Claude Code';
        const where = info.project ? ` · ${info.project}` : '';
        return {notification: null, source: null, name, state, project: info.project ?? '',
            text: `${name} · ${info.summary || info.text || ''}`.trim(), title: '',
            body: info.text ?? '', time: GLib.get_monotonic_time(), realTime: GLib.get_real_time(),
            where, ...extra};
    }

    AskAsync([json, pids, seconds], invocation) {
        let info;
        try {
            info = JSON.parse(json);
        } catch (e) {
            invocation.return_value(new GLib.Variant('(s)', ['']));
            return;
        }
        if (this._watching(pids)) {
            invocation.return_value(new GLib.Variant('(s)', ['']));
            return;
        }
        const item = this._bridgeItem(info, 'approve', {request: info, invocation, pids});
        item.text = `${item.name} · ${info.summary || info.tool}`;
        this._items.push(item);
        this._expire(item, Math.max(5, Math.min(seconds, 300)) * 1000);
        this.emit('changed');
    }

    TellAsync([json, pids], invocation) {
        invocation.return_value(null);
        let info;
        try {
            info = JSON.parse(json);
        } catch (e) {
            return;
        }
        if (this._watching(pids))
            return;
        const state = ['done', 'waiting', 'failed'].includes(info.state) ? info.state : 'waiting';
        const item = this._bridgeItem(info, state, {pids});
        this._items = this._items.filter(i => !(i.name === item.name && i.project === item.project && i.state !== 'approve'));
        this._items.push(item);
        this._expire(item, state === 'waiting' ? WAITING_MAX_MS : DONE_MS);
        this.emit('changed');
    }

    // Allow / Always / Deny desde la tarjeta: la respuesta vuelve a Claude Code al momento.
    answer(item, value) {
        if (!this._items.includes(item) || !item.invocation)
            return;
        item.invocation.return_value(new GLib.Variant('(s)', [value]));
        item.invocation = null;
        this._remove(item);
    }

    _add(source, notification) {
        const name = agentName(source.title, source.policy?.id, source.app?.get_id?.(), notification.title);
        if (!name)
            return;
        const state = agentState(notification.title, notification.body);
        // Un aviso nuevo del mismo agente sustituye al anterior (terminó lo que esperaba).
        this._items = this._items.filter(item => item.name !== name || item.notification === notification);
        const title = plain(notification.title);
        const body = plain(notification.body);
        const item = {notification, source, name, state, text: summary(name, notification.title, notification.body),
            title: title && title.toLowerCase() !== name.toLowerCase() ? title : '', body,
            time: GLib.get_monotonic_time(), realTime: GLib.get_real_time()};
        this._items.push(item);
        notification.connectObject('destroy', () => this._remove(item), this);
        this._expire(item, state === 'waiting' ? WAITING_MAX_MS : DONE_MS);
        this.emit('changed');
    }

    _expire(item, ms) {
        item.timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            item.timer = 0;
            this._remove(item);
            return GLib.SOURCE_REMOVE;
        });
    }

    _remove(item) {
        if (!this._items.includes(item))
            return;
        if (item.timer)
            GLib.source_remove(item.timer);
        item.notification?.disconnectObject(this);
        if (item.invocation) {         // sin respuesta: Claude Code pregunta en su terminal
            item.invocation.return_value(new GLib.Variant('(s)', ['']));
            item.invocation = null;
        }
        this._items = this._items.filter(i => i !== item);
        this.emit('changed');
    }

    // Lo más importante primero: lo que espera tu respuesta, luego un fallo, luego lo terminado.
    get current() {
        return this.items[0] ?? null;
    }

    // Todos, en el mismo orden que la cápsula: para la tarjeta que se abre con un clic.
    get items() {
        return [...this._items].sort((a, b) => RANK[a.state] - RANK[b.state] || b.time - a.time);
    }

    get waitingCount() {
        return this._items.filter(i => i.state === 'waiting' || i.state === 'approve').length;
    }

    // «Abrir»: lo mismo que pulsar su aviso. Muchos agentes (los de terminal) no dicen qué abrir;
    // si la ventana activa no cambió, se trae al frente la ventana del agente: la de su app, o
    // una cuyo título o clase lo nombre (la terminal donde corre Claude Code, por ejemplo).
    open(item = this.current) {
        if (!item)
            return;
        const before = global.display.focus_window;
        try {
            item.notification?.activate();
        } catch (e) {
            // sin acción: se busca su ventana
        }
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
            if (global.display.focus_window === before)
                this._focusWindow(item);
            return GLib.SOURCE_REMOVE;
        });
        this._remove(item);
    }

    _focusWindow(item) {
        const pattern = AGENTS.find(([name]) => name === item.name)?.[1];
        const windows = global.display.get_tab_list(Meta.TabList.NORMAL_ALL, null);
        const app = item.source?.app;
        // La terminal (o el editor) donde corre el agente: su proceso es uno de los del hook.
        const own = item.pids ? windows.find(win => item.pids.includes(win.get_pid?.() ?? 0)) : null;
        const match = own ?? windows.find(win => app && Shell.WindowTracker.get_default().get_window_app(win) === app) ??
            windows.find(win => pattern?.test(`${win.get_title() ?? ''} ${win.get_wm_class() ?? ''}`));
        if (match)
            Main.activateWindow(match);
        else
            app?.activate?.();
    }

    dismiss(item) {
        if (!this._items.includes(item))
            return;
        this._remove(item);
        try {
            item.notification?.destroy();
        } catch (e) {
            // ya no estaba
        }
    }

    destroy() {
        for (const item of this._items) {
            if (item.timer)
                GLib.source_remove(item.timer);
            item.notification?.disconnectObject(this);
            item.invocation?.return_value(new GLib.Variant('(s)', ['']));
        }
        this._bridge?.unexport();
        this._items = [];
        Main.messageTray.disconnectObject(this);
        Main.messageTray.getSources().forEach(source => source.disconnectObject(this));
    }
}
