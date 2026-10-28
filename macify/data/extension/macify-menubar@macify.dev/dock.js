// Dock: correcciones al dock animado para que se comporte como el de macOS.

import Cairo from 'gi://cairo';
import GLib from 'gi://GLib';
import Mtk from 'gi://Mtk';

import {ExtensionState} from 'resource:///org/gnome/shell/misc/extensionUtils.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

import {DockPreview} from './dockPreview.js';

// Ajustes al dock animado (Dash2Dock Animated) para que se comporte como el de macOS
// sobre cualquier app. Si ese dock no está, esto no hace nada.
// - En pantalla completa se esconde del todo; aquí aparece al llevar el puntero al borde.
// - Mientras está visible no se esconde si el puntero sigue encima (iconos ampliados,
//   margen y hueco hasta el borde incluidos), y espera un momento antes de esconderse.
const DOCK_UUID = 'dash2dock-lite@icedman.github.com';
const HIDE_DELAY_MS = 120;
const LEAVE_POLL_MS = 80;      // mientras el puntero sigue cerca del dock, se mira si ya salió
const REVEAL_MS = 700;          // tiempo en que se vigila que el dock termine de entrar
const KEEP_MARGIN = 28;
// Al poner o quitar una pantalla (o Super+P: duplicar, sólo el portátil…) el dock rehace sus
// docks y a veces queda roto: sin dash, de 0×0 o con docks viejos que siguen animándose
// («this.dash is null»). Pasado este tiempo se revisa y, si hace falta, se reinicia.
const DISPLAYS_SETTLE_MS = 1500;

// Sobre una app maximizada que ocupa todo un monitor (Brave, VS Code y otras de Chromium o
// Electron), GNOME puede mandar la imagen de la app directo a la pantalla y no repintar la
// capa del dock: el dock "entra" pero no se ve. Mientras entra, se mantiene viva su
// animación y se repinta sólo su zona. Si ya está a la vista no se hace nada: el dock
// llama a show() cada pocos segundos y repintar entonces sólo gastaría GPU.
function queueDockRedraw(dock) {
    const [x, y] = dock.get_transformed_position();
    const clip = new Mtk.Rectangle({x: Math.floor(x), y: Math.floor(y),
        width: Math.ceil(dock.width), height: Math.ceil(dock.height)});
    if (typeof global.stage.queue_redraw_with_clip === 'function')
        global.stage.queue_redraw_with_clip(clip);
    else
        global.stage.queue_redraw();
}

function revealFully(dock) {
    const offscreen = () => Math.abs(dock.dash?.translationY ?? 0) > 0.5;
    if (dock._macifyRevealId || !offscreen())
        return;
    const started = GLib.get_monotonic_time();
    dock._macifyRevealId = GLib.timeout_add(GLib.PRIORITY_HIGH, 16, () => {
        const elapsed = (GLib.get_monotonic_time() - started) / 1000;
        if (dock._hidden || !dock.dash || !offscreen() || elapsed > REVEAL_MS) {
            if (!dock._hidden && dock.dash && offscreen())
                console.log(`Macify dock: reveal unfinished translation=${Math.round(dock.dash.translationY)}`);
            if (dock.dash)
                queueDockRedraw(dock);      // un último cuadro con el dock ya en su sitio
            dock._macifyRevealId = 0;
            return GLib.SOURCE_REMOVE;
        }
        dock._beginAnimation?.();
        queueDockRedraw(dock);
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

// Con una app maximizada que ocupa todo un monitor, GNOME manda su imagen directo a la
// pantalla («direct scanout») y no dibuja nada encima: el dock queda «visible» pero no se ve.
// Mientras el dock está a la vista se pide componer la pantalla, como hacen los menús de
// GNOME (por eso un clic derecho lo hacía aparecer). Al esconderse se devuelve.
const SCANOUT_BACK_MS = 400;    // tras esconderse, deja terminar la animación de salida

function keepComposited(dock, on) {
    if (dock._macifyScanoutId) {
        GLib.source_remove(dock._macifyScanoutId);
        dock._macifyScanoutId = 0;
    }
    if (on && !dock._macifyNoScanout) {
        global.compositor.disable_unredirect();
        dock._macifyNoScanout = true;
    } else if (!on && dock._macifyNoScanout) {
        dock._macifyScanoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, SCANOUT_BACK_MS, () => {
            dock._macifyScanoutId = 0;
            if (dock._macifyNoScanout) {
                global.compositor.enable_unredirect();
                dock._macifyNoScanout = false;
            }
            return GLib.SOURCE_REMOVE;
        });
    }
}

function releaseComposited(dock) {
    if (dock._macifyScanoutId)
        GLib.source_remove(dock._macifyScanoutId);
    dock._macifyScanoutId = 0;
    if (dock._macifyNoScanout)
        global.compositor.enable_unredirect();
    dock._macifyNoScanout = false;
}

// El puntero está sobre el dock visible o en el camino entre él y el borde inferior.
function pointerOnDock(dock) {
    const monitor = dock._monitor;
    const struts = dock.struts;
    if (!monitor || !struts || dock._hidden || dock.isVertical?.() || dock._position === 'top')
        return false;
    if (dock._macifyKeepOpen?.())
        return true;                                          // el panel de ventanas y archivos está abierto
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
        Main.layoutManager.connectObject('monitors-changed', () => {
            this._update();
            this._checkAfterDisplayChange();
        }, this);
        this._displays = Main.layoutManager.monitors.length;
        this._preview = new DockPreview();
        // El dock puede crearse después que esta extensión.
        this._startId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 3, () => {
            this._startId = 0;
            this._update();
            return GLib.SOURCE_REMOVE;
        });
        this._update();
    }

    _checkAfterDisplayChange() {
        if (this._checkId)
            GLib.source_remove(this._checkId);
        this._checkId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, DISPLAYS_SETTLE_MS, () => {
            this._checkId = 0;
            this._repair().catch(e => console.warn(`Macify: dock repair: ${e.message}`));
            return GLib.SOURCE_REMOVE;
        });
    }

    async _repair() {
        const extension = Main.extensionManager.lookup(DOCK_UUID);
        if (extension?.state !== ExtensionState.ACTIVE)
            return;
        const displays = Main.layoutManager.monitors.length;
        const changed = displays !== this._displays;
        this._displays = displays;
        const docks = this._docks();
        const wanted = Number(extension.stateObj?.multi_monitor_preference) === 1 ? displays : 1;
        const broken = docks.length !== wanted || docks.some(d => !d.dash || d.width < 1 || d.height < 1);
        if (!changed && !broken)
            return;
        // Igual que desactivarlo y activarlo: docks nuevos, sin animaciones viejas.
        console.log(`Macify dock: restarting after a display change (${docks.length} docks, ${displays} displays)`);
        await Main.extensionManager._callExtensionDisable(DOCK_UUID);
        await Main.extensionManager._callExtensionEnable(DOCK_UUID);
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
            this._watchCreation();
            for (const dock of this._docks())
                this._patch(dock);
        } catch (e) {
            console.warn(`Macify: fullscreen dock: ${e.message}`);
        }
    }

    // El dock rehace sus docks al cambiar las pantallas o la escala: cada dock nuevo se
    // ajusta en cuanto se crea, no al siguiente aviso.
    _watchCreation() {
        const extension = Main.extensionManager.lookup(DOCK_UUID)?.stateObj;
        if (!extension || extension._macifyCreateDock || typeof extension.createDock !== 'function')
            return;
        const self = this;
        extension._macifyCreateDock = extension.createDock;
        extension.createDock = function (...args) {
            const dock = this._macifyCreateDock(...args);
            const patch = () => {
                try {
                    if (dock && !dock._macifyDestroyed)
                        self._patch(dock);
                } catch (e) {
                    console.warn(`Macify: new dock: ${e.message}`);
                }
                return GLib.SOURCE_REMOVE;
            };
            patch();
            GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, patch);     // ya ubicado en su pantalla
            return dock;
        };
        this._watched = extension;
    }

    _patch(dock) {
        enableBadges(dock);
        this._preview.attach(dock);
        if (typeof dock.animate === 'function' && !dock._macifyAnimate) {
            // Un dock quitado (sin dash) que aún se anima sólo daría errores en cada cuadro.
            dock._macifyAnimate = dock.animate;
            dock.animate = function (...args) {
                return this.dash ? this._macifyAnimate(...args) : undefined;
            };
        }
        if (!dock._macifyWatched) {
            // Si el dock se rehace (al cambiar su tamaño), suelta lo que tenía pedido.
            dock._macifyWatched = true;
            dock.connectObject('destroy', () => {
                dock._macifyDestroyed = true;
                releaseComposited(dock);
            }, this);
        }
        // Con ocultación automática el dock se alcanza también en pantalla completa (como en
        // macOS); sin ella, GNOME lo esconde en pantalla completa para no tapar un video.
        const tracked = this._tracked(dock);
        const reachable = Boolean(dock.extension?.autohide_dash);
        if (tracked && tracked.trackFullscreen === reachable) {
            tracked.trackFullscreen = !reachable;
            if (reachable)
                dock.visible = true;
            else
                Main.layoutManager._updateVisibility?.();
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
            keepComposited(this.dock, true);
            revealFully(this.dock);
            enableBadges(this.dock);
        };
        hider._checkOverlap = function () {
            if (this._shown && pointerOnDock(this.dock)) {
                // El dock no vuelve a mirar hasta otro evento: aquí se vigila cuándo sale el
                // puntero, para esconderlo enseguida y no dejarlo «esperando».
                this._macifyLeaveId ??= GLib.timeout_add(GLib.PRIORITY_DEFAULT, LEAVE_POLL_MS, () => {
                    if (this.dock._macifyDestroyed) {
                        this._macifyLeaveId = null;
                        return GLib.SOURCE_REMOVE;
                    }
                    if (this._shown && pointerOnDock(this.dock))
                        return GLib.SOURCE_CONTINUE;
                    this._macifyLeaveId = null;
                    if (this._shown)
                        this.hide();
                    return GLib.SOURCE_REMOVE;
                });
                return false;
            }
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
                    this._macifyOriginal.hide.call(this);
                    keepComposited(this.dock, false);
                }
                return GLib.SOURCE_REMOVE;
            });
        };
        if (hider._shown && !dock._hidden)
            keepComposited(dock, true);
        hider._debounceCheckHide?.();
    }

    destroy() {
        this._preview.destroy();
        if (this._startId)
            GLib.source_remove(this._startId);
        if (this._checkId)
            GLib.source_remove(this._checkId);
        if (this._watched?._macifyCreateDock) {
            this._watched.createDock = this._watched._macifyCreateDock;
            delete this._watched._macifyCreateDock;
        }
        global.display.disconnectObject(this);
        Main.extensionManager.disconnectObject(this);
        Main.layoutManager.disconnectObject(this);
        try {
            for (const dock of this._docks()) {
                releaseComposited(dock);
                dock.disconnectObject(this);
                delete dock._macifyWatched;
                if (dock._macifyAnimate) {
                    dock.animate = dock._macifyAnimate;
                    delete dock._macifyAnimate;
                }
                const hider = dock.autohider;
                if (dock._macifyRevealId) {
                    GLib.source_remove(dock._macifyRevealId);
                    dock._macifyRevealId = 0;
                }
                if (hider?._macifyOriginal) {
                    if (hider._macifyHideId)
                        GLib.source_remove(hider._macifyHideId);
                    hider._macifyHideId = 0;
                    if (hider._macifyLeaveId)
                        GLib.source_remove(hider._macifyLeaveId);
                    hider._macifyLeaveId = null;
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
