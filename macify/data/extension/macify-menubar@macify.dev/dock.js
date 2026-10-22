// Dock: correcciones al dock animado para que se comporte como el de macOS.

import Cairo from 'gi://cairo';
import GLib from 'gi://GLib';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

// Ajustes al dock animado (Dash2Dock Animated) para que se comporte como el de macOS
// sobre cualquier app. Si ese dock no está, esto no hace nada.
// - En pantalla completa se esconde del todo; aquí aparece al llevar el puntero al borde.
// - Mientras está visible no se esconde si el puntero sigue encima (iconos ampliados,
//   margen y hueco hasta el borde incluidos), y espera un momento antes de esconderse.
const DOCK_UUID = 'dash2dock-lite@icedman.github.com';
const HIDE_DELAY_MS = 300;
const REVEAL_MS = 700;          // tiempo en que se vigila que el dock termine de entrar
const KEEP_MARGIN = 28;

// Sobre una app maximizada que ocupa todo un monitor (Brave, VS Code y otras de Chromium o
// Electron), GNOME puede mandar la imagen de la app directo a la pantalla y no repintar la
// capa del dock: el dock "entra" pero no se ve hasta que algo fuerce un repintado. Durante
// la entrada se mantiene viva su animación y se pide repintar en cada cuadro.
function revealFully(dock) {
    if (dock._macifyRevealId)
        return;
    const started = GLib.get_monotonic_time();
    dock._macifyRevealId = GLib.timeout_add(GLib.PRIORITY_HIGH, 16, () => {
        const elapsed = (GLib.get_monotonic_time() - started) / 1000;
        if (dock._hidden || !dock.dash || elapsed > REVEAL_MS) {
            if (!dock._hidden && dock.dash)
                console.log(`Macify dock: revealed translation=${Math.round(dock.dash.translationY)} ` +
                    `opacity=${dock.opacity} after ${Math.round(elapsed)} ms`);
            dock._macifyRevealId = 0;
            return GLib.SOURCE_REMOVE;
        }
        if (Math.abs(dock.dash.translationY) > 0.5)
            dock._beginAnimation?.();
        dock.queue_redraw();
        global.stage.queue_redraw();
        return GLib.SOURCE_CONTINUE;
    });
}

// Globo rojo con el número de avisos, arriba a la derecha del icono, como en macOS.
// El dock lo dibuja con su lienzo de puntos: aquí se le añade este estilo. Su lienzo
// desplaza el dibujo hacia arriba (0.85 del alto) y a la derecha, de ahí las cuentas.
const BADGE_STYLES = ['macos', 'dot', 'dash', 'square', 'triangle', 'diamond'];

function drawMacBadge(ctx, state) {
    const [size] = this.get_surface_size();
    const text = state.count > 99 ? '99+' : String(state.count);
    const radius = size * 0.19;
    const half = radius * (1 + 0.42 * (text.length - 1));
    const cx = size * 0.24 + (half - radius);
    const cy = size * 0.85 + size * 0.21;
    ctx.setOperator(Cairo.Operator.OVER);
    ctx.newPath();
    ctx.arc(cx - (half - radius), cy, radius, Math.PI / 2, Math.PI * 1.5);
    ctx.arc(cx + (half - radius), cy, radius, -Math.PI / 2, Math.PI / 2);
    ctx.closePath();
    ctx.setSourceRGBA(1.0, 0.23, 0.19, 1.0);
    ctx.fill();
    ctx.selectFontFace('SF Pro Text', Cairo.FontSlant.NORMAL, Cairo.FontWeight.BOLD);
    ctx.setFontSize(radius * 1.3);
    const extents = ctx.textExtents(text);
    ctx.moveTo(cx - extents.width / 2 - extents.xBearing, cy - extents.height / 2 - extents.yBearing);
    ctx.setSourceRGBA(1, 1, 1, 1);
    ctx.showText(text);
}

function enableBadges(dock) {
    // El primer estilo del dock («default») no tiene dibujo: ahí va el globo de macOS.
    const extension = dock.extension;
    const options = extension?.notification_badge_style_options;
    if (extension && (!Array.isArray(options) || options[0] !== 'macos'))
        extension.notification_badge_style_options = ['macos', ...(Array.isArray(options) ? options.slice(1) : BADGE_STYLES.slice(1))];
    const canvas = dock.animator?._badges?.[0]?.renderer?._canvas;
    const proto = canvas && Object.getPrototypeOf(canvas);
    if (proto && typeof proto._draw_macos !== 'function')
        proto._draw_macos = drawMacBadge;
}

// El puntero está sobre el dock visible o en el camino entre él y el borde inferior.
function pointerOnDock(dock) {
    const monitor = dock._monitor;
    const struts = dock.struts;
    if (!monitor || !struts || dock._hidden || dock.isVertical?.() || dock._position === 'top')
        return false;
    const [px, py] = global.get_pointer();
    const [x, y] = struts.get_transformed_position();
    const lift = struts.height * 0.9 + KEEP_MARGIN;          // espacio de los iconos ampliados
    return px >= x - KEEP_MARGIN && px <= x + struts.width + KEEP_MARGIN &&
        py >= y - lift && py <= monitor.y + monitor.height;
}

export class FullscreenDock {
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
        enableBadges(dock);
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
        hider._macifyOriginal = {show: hider.show, hide: hider.hide, checkOverlap: hider._checkOverlap};
        hider.show = function () {
            if (this._macifyHideId) {
                GLib.source_remove(this._macifyHideId);
                this._macifyHideId = 0;
            }
            if (!this.dock._monitor)
                return;
            this._dwell = 0;
            this.frameDelay = 0;
            this._shown = true;
            this.dock.slideIn();
            revealFully(this.dock);
            enableBadges(this.dock);
        };
        hider._checkOverlap = function () {
            if (this._shown && pointerOnDock(this.dock))
                return false;
            // En pantalla completa sólo se queda mientras el puntero está sobre el dock.
            if (this.dock._monitor?.inFullscreen && !this.extension?._inOverview)
                return true;
            return this._macifyOriginal.checkOverlap.call(this);
        };
        hider.hide = function () {
            if (this._macifyHideId)
                return;
            this._macifyHideId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, HIDE_DELAY_MS, () => {
                this._macifyHideId = 0;
                if (this._enabled && this._checkOverlap()) {
                    if (this._shown) {
                        const [px, py] = global.get_pointer();
                        const [x, y] = this.dock.struts?.get_transformed_position() ?? [0, 0];
                        console.log(`Macify dock: hide on monitor ${this.dock._monitor?.index} pointer=${px},${py} ` +
                            `dock=${Math.round(x)},${Math.round(y)} ${this.dock.struts?.width}x${this.dock.struts?.height} ` +
                            `fullscreen=${this.dock._monitor?.inFullscreen} ` +
                            `focus=${global.display.focus_window?.get_wm_class() ?? '-'}`);
                    }
                    this._macifyOriginal.hide.call(this);
                }
                return GLib.SOURCE_REMOVE;
            });
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
                if (dock._macifyRevealId) {
                    GLib.source_remove(dock._macifyRevealId);
                    dock._macifyRevealId = 0;
                }
                if (hider?._macifyOriginal) {
                    if (hider._macifyHideId)
                        GLib.source_remove(hider._macifyHideId);
                    hider._macifyHideId = 0;
                    hider.show = hider._macifyOriginal.show;
                    hider.hide = hider._macifyOriginal.hide;
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

// Arreglos de compatibilidad con GNOME 50 que necesitan el dock y Magic Lamp. Sólo
// completan lo que falta; si GNOME o las extensiones lo corrigen, no hacen nada.
// - El menú del clic derecho en los iconos del dock llama a ignoreRelease(), que
//   GNOME 50 quitó: el menú fallaba.
// - Magic Lamp y el dock le piden posiciones al dash de la vista general, que en GNOME 50
//   falla con «firstIcon.icon is null» y corta la animación a la mitad.
export class Gnome50Fixes {
    constructor() {
        const proto = PopupMenu.PopupMenuManager.prototype;
        if (typeof proto.ignoreRelease !== 'function') {
            proto.ignoreRelease = function () {};
            this._addedIgnoreRelease = true;
        }
        const dash = Main.overview.dash;
        if (typeof dash?._adjustIconSize === 'function') {
            const original = dash._adjustIconSize;
            this._dash = dash;
            this._hadOwn = Object.prototype.hasOwnProperty.call(dash, '_adjustIconSize');
            this._original = original;
            dash._adjustIconSize = function (...args) {
                try {
                    return original.apply(this, args);
                } catch (e) {
                    return undefined;    // sin icono todavía: se recalcula en el siguiente cambio
                }
            };
        }
    }

    destroy() {
        if (this._addedIgnoreRelease)
            delete PopupMenu.PopupMenuManager.prototype.ignoreRelease;
        if (this._dash) {
            if (this._hadOwn)
                this._dash._adjustIconSize = this._original;
            else
                delete this._dash._adjustIconSize;
        }
    }
}
