// Pruebas de Macify Menubar dentro de un GNOME Shell aislado (ver tests/shell/run.sh).
// Abre apps de verdad, usa los menús como lo haría una persona y comprueba el resultado:
// portapapeles, pantalla completa, ventanas nuevas, minimizar, salir, avisos del dock.
// Escribe results.json y capturas en $MACIFY_TEST_OUT y luego cierra el Shell.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Shell from 'gi://Shell';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const OUT = GLib.getenv('MACIFY_TEST_OUT') ?? '/tmp';
const results = [];

const sleep = ms => new Promise(resolve => GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    resolve();
    return GLib.SOURCE_REMOVE;
}));

function check(name, ok, detail = '') {
    results.push({name, ok: Boolean(ok), detail: String(detail)});
    console.log(`MACIFY-TEST ${ok ? 'PASS' : 'FAIL'} ${name} ${detail}`);
}

async function until(condition, ms = 8000) {
    for (let waited = 0; waited < ms; waited += 100) {
        if (condition())
            return true;
        await sleep(100);
    }
    return condition();
}

function screenshot(name) {
    return new Promise(resolve => {
        const file = Gio.File.new_for_path(`${OUT}/${name}.png`);
        const stream = file.replace(null, false, Gio.FileCreateFlags.NONE, null);
        new Shell.Screenshot().screenshot(false, stream, (shooter, result) => {
            try {
                shooter.screenshot_finish(result);
            } catch (e) {
                console.log(`MACIFY-TEST screenshot ${name}: ${e.message}`);
            }
            stream.close(null);
            resolve();
        });
    });
}

function clipboard() {
    return new Promise(resolve => St.Clipboard.get_default()
        .get_text(St.ClipboardType.CLIPBOARD, (_c, text) => resolve(text ?? '')));
}

// El Shell de prueba no tiene teclado: se crea uno virtual antes de abrir apps, porque
// una ventana abierta antes de que exista un teclado no recibe el foco del teclado.
let keyboard = null;
function createKeyboard() {
    keyboard ??= Clutter.get_default_backend().get_default_seat()
        .create_virtual_device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
}

function type(text) {
    createKeyboard();
    let time = GLib.get_monotonic_time();
    for (const char of text) {
        const key = Clutter.unicode_to_keysym(char.codePointAt(0));
        keyboard.notify_keyval(time++, key, Clutter.KeyState.PRESSED);
        keyboard.notify_keyval(time++, key, Clutter.KeyState.RELEASED);
    }
}

// Abre el menú como un clic y pulsa la opción (un menú que no se abre falla aquí).
function choose(menuName, label) {
    const button = Main.panel.statusArea[menuName];
    button.menu.open();
    if (!button.menu.isOpen)
        throw new Error(`${menuName}: the menu does not open`);
    const item = button.menu._getMenuItems().find(i => i.label?.text === label);
    if (!item)
        throw new Error(`${menuName}: no item «${label}»`);
    if (!item.sensitive)
        throw new Error(`${menuName}: «${label}» disabled`);
    item.emit('activate', null);
    button.menu.close();
}

async function openApp(id) {
    const app = Shell.AppSystem.get_default().lookup_app(id);
    if (!app)
        return null;
    app.activate();
    const tracker = Shell.WindowTracker.get_default();
    await until(() => tracker.focus_app === app && global.display.focus_window, 10000);
    await sleep(800);
    return app;
}

async function testEditor() {
    const app = await openApp('org.gnome.TextEditor.desktop');
    if (!app) {
        check('editor: available', false, 'org.gnome.TextEditor.desktop missing');
        return;
    }
    check('app menu shows the focused app', Main.panel.statusArea['macify-app-menu']._label.text === app.get_name(),
        Main.panel.statusArea['macify-app-menu']._label.text);
    await sleep(1500);                   // el editor termina de abrir su documento
    type('macify-edit');
    await sleep(500);
    choose('macify-menu-edit', 'Select All');
    await sleep(400);
    choose('macify-menu-edit', 'Cut');
    await sleep(600);
    const cut = await clipboard();
    check('Edit › Select All + Cut', cut.includes('macify-edit'), JSON.stringify(cut));
    choose('macify-menu-edit', 'Paste');
    await sleep(400);
    choose('macify-menu-edit', 'Paste');
    await sleep(400);
    St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, '');
    choose('macify-menu-edit', 'Select All');
    await sleep(400);
    await sleep(400);
    choose('macify-menu-edit', 'Copy');
    await sleep(600);
    const copied = await clipboard();
    check('Edit › Paste twice + Copy', copied.includes('macify-editmacify-edit'), JSON.stringify(copied));

    // Reglas de Apple: lo que no aplica se ve desactivado, no se esconde.
    Main.panel.statusArea['macify-menu-file'].menu.open();
    const fileItems = Main.panel.statusArea['macify-menu-file'].menu._getMenuItems().map(i => i.label?.text).filter(Boolean);
    check('File menu keeps every item', ['New Window', 'New Tab', 'Open…', 'Close Window', 'Save', 'Print…']
        .every(l => fileItems.includes(l)), fileItems.join(','));

    const win = global.display.focus_window;
    choose('macify-menu-view', 'Enter Full Screen');
    await until(() => win.is_fullscreen(), 3000);
    check('View › Enter Full Screen', win.is_fullscreen());
    await screenshot('editor-fullscreen');
    choose('macify-menu-view', 'Exit Full Screen');
    await until(() => !win.is_fullscreen(), 3000);
    check('View › Exit Full Screen', !win.is_fullscreen());

    const wasMaximized = win.is_maximized();
    choose('macify-menu-window', 'Zoom');
    await until(() => win.is_maximized() !== wasMaximized, 3000);
    check('Window › Zoom', win.is_maximized() !== wasMaximized);

    const before = app.get_n_windows();
    choose('macify-menu-file', 'New Window');
    await until(() => app.get_n_windows() > before, 5000);
    check('File › New Window', app.get_n_windows() > before, `${before} → ${app.get_n_windows()}`);
    await sleep(800);

    choose('macify-menu-file', 'Close Window');
    await until(() => app.get_n_windows() === before, 5000);
    check('File › Close Window', app.get_n_windows() === before, `${app.get_n_windows()}`);

    win.activate(global.get_current_time());
    await sleep(500);
    choose('macify-menu-window', 'Minimize');
    await until(() => win.minimized, 3000);
    check('Window › Minimize', win.minimized);
}

async function testTerminal() {
    const app = await openApp('org.gnome.Ptyxis.desktop');
    if (!app) {
        check('terminal: available', false, 'org.gnome.Ptyxis.desktop missing');
        return;
    }
    await sleep(1500);
    type('macify-term');
    await sleep(500);
    choose('macify-menu-edit', 'Select All');
    await sleep(400);
    choose('macify-menu-edit', 'Copy');
    await sleep(600);
    const copied = await clipboard();
    check('Terminal: Edit › Select All + Copy (Ctrl+Shift)', copied.includes('macify-term'), JSON.stringify(copied.slice(-80)));
    await screenshot('terminal');
    Main.panel.statusArea['macify-menu-file'].menu.open();
    const save = Main.panel.statusArea['macify-menu-file'].menu._getMenuItems().find(i => i.label?.text === 'Save');
    check('Terminal: Save is shown disabled', save && !save.sensitive);
    choose('macify-app-menu', `Quit ${app.get_name()}`);
    await until(() => app.get_n_windows() === 0, 6000);
    check('App › Quit', app.get_n_windows() === 0);
}

function testParts() {
    const macify = Main.extensionManager.lookup('macify-menubar@macify.dev');
    const parts = (macify?.stateObj?._parts ?? []).map(p => p.constructor.name);
    check('extension active', macify?.state === 1, `state ${macify?.state}`);
    for (const name of ['Gnome50Fixes', 'AppMenus', 'StatusBar', 'LiveActivities', 'FullscreenDock'])
        check(`part ${name}`, parts.includes(name));
    const right = Main.panel._rightBox.get_children();
    const dateIndex = right.indexOf(Main.panel.statusArea.dateMenu.container);
    check('clock is last on the right', dateIndex === right.length - 1, `${dateIndex}/${right.length - 1}`);
    return macify?.stateObj;
}

// Un reproductor de música de mentira en el bus (como Brave o Spotify), para probar la
// cápsula y «Ahora suena» de punta a punta.
const MPRIS_XML = `<node>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="PlayPause"/><method name="Next"/><method name="Previous"/>
    <method name="SetPosition"><arg type="o" direction="in"/><arg type="x" direction="in"/></method>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Position" type="x" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
  </interface>
</node>`;

function fakePlayer(suffix = 'macifytest', title = 'Blinding Lights', artist = 'The Weeknd') {
    const player = {
        status: 'Playing', calls: [],
        get PlaybackStatus() {
            return this.status;
        },
        get Metadata() {
            return {
                'xesam:title': new GLib.Variant('s', title),
                'xesam:artist': new GLib.Variant('as', [artist]),
                'mpris:length': new GLib.Variant('x', 200000000),
                'mpris:trackid': new GLib.Variant('o', '/org/macify/track1'),
            };
        },
        Position: 42000000, CanSeek: true, CanGoNext: true, CanGoPrevious: true,
        PlayPause() {
            this.calls.push('PlayPause');
            this.status = this.status === 'Playing' ? 'Paused' : 'Playing';
            exported.emit_property_changed('PlaybackStatus', new GLib.Variant('s', this.status));
        },
        Next() {
            this.calls.push('Next');
        },
        Previous() {
            this.calls.push('Previous');
        },
        SetPosition(_track, position) {
            this.calls.push(`SetPosition ${position}`);
        },
    };
    const exported = Gio.DBusExportedObject.wrapJSObject(MPRIS_XML, player);
    // Cada reproductor en su propia conexión, como dos apps distintas.
    const bus = Gio.DBusConnection.new_for_address_sync(Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, null),
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, null, null);
    exported.export(bus, '/org/mpris/MediaPlayer2');
    player.ownerId = Gio.bus_own_name_on_connection(bus, `org.mpris.MediaPlayer2.${suffix}`,
        Gio.BusNameOwnerFlags.NONE, null, null);
    player.stop = () => {
        Gio.bus_unown_name(player.ownerId);
        exported.unexport();
        bus.close_sync(null);
    };
    return player;
}

async function testLiveActivities(macify) {
    const live = macify._parts.find(p => p.constructor.name === 'LiveActivities');
    const button = Main.panel.statusArea['macify-live'];
    const player = fakePlayer();
    await until(() => button.visible && button.pill.opacity > 200, 5000);
    check('Live Activity shows the playing song', button.visible && button.label.text.includes('Blinding Lights'),
        button.label.text);
    await sleep(6000);
    const resting = button.barActors.every(b => !b._moving);
    check('audio bars rest after a few seconds (no constant redraw)', resting);
    button.menu.open();
    await sleep(1600);
    const np = live._nowPlaying;
    check('Now Playing opens with title and artist', button.menu.isOpen && np._title.text === 'Blinding Lights'
        && np._artist.text === 'The Weeknd', `${np._title.text} / ${np._artist.text}`);
    check('Now Playing shows the position', np._elapsed.text === '0:42', np._elapsed.text);
    const [, npHeight] = button.menu.actor.get_preferred_height(-1);
    check('Now Playing has a sane height', npHeight > 100 && npHeight < 2000, `${Math.round(npHeight)} px`);
    await screenshot('now-playing');
    np._next.emit('clicked', 1);
    await sleep(400);
    np._play.emit('clicked', 1);
    await until(() => player.status === 'Paused', 3000);
    check('Next and Pause reach the player', player.calls.includes('Next') && player.calls.includes('PlayPause'),
        player.calls.join(','));
    await until(() => np._play.child.icon_name === 'media-playback-start-symbolic', 3000);
    check('play button shows Play when paused', np._play.child.icon_name === 'media-playback-start-symbolic',
        np._play.child.icon_name);
    button.menu.close();

    // Lo que pasó viendo un curso con música de fondo: dos apps sonando.
    np._play.emit('clicked', 1);                   // la música vuelve a sonar
    await until(() => player.status === 'Playing', 3000);
    await sleep(300);
    const course = fakePlayer('course', 'AI Fluency course');
    await until(() => button.label.text.includes('AI Fluency'), 5000);
    const before = [...course.calls];
    button.menu.open();
    await sleep(800);
    check('clicking the bubble pauses nothing (it opens Now Playing)',
        course.status === 'Playing' && player.status === 'Playing' && course.calls.length === before.length);
    const sources = np._sources.get_children();
    check('Now Playing lists both sources', np._sources.visible && sources.length === 2,
        sources.map(b => b.label).join(','));
    const music = sources.find(b => b.label !== sources[0].label && !b.checked) ?? sources[1];
    music.emit('clicked', 1);
    await sleep(600);
    np._play.emit('clicked', 1);
    await until(() => player.status === 'Paused', 3000);
    check('the chosen source is the one controlled', player.status === 'Paused' && course.status === 'Playing',
        `music ${player.status}, course ${course.status}`);
    button.menu.close();
    course.stop();
    player.stop();
    await until(() => !button.visible, 4000);
    check('Live Activity hides when the players quit', !button.visible);
}

async function testDockScanout() {
    const dock = Main.extensionManager.lookup('dash2dock-lite@icedman.github.com')?.stateObj?.docks?.[0];
    const hider = dock?.autohider;
    if (!hider?._macifyOriginal) {
        check('dock patched for direct scanout', false, 'no patched autohider');
        return;
    }
    const enabled = hider._enabled;
    const overlap = hider._checkOverlap;
    hider._enabled = true;
    hider.show();
    check('showing the dock keeps the screen composited', dock._macifyNoScanout === true);
    hider._checkOverlap = () => true;            // como si una ventana maximizada lo tapara
    hider.hide();
    await sleep(1000);
    check('hiding the dock gives direct scanout back', dock._macifyNoScanout === false && dock._hidden);
    hider._checkOverlap = overlap;
    hider._enabled = enabled;
    hider.show();
    await sleep(500);
}

async function testBadges() {
    const dock = Main.extensionManager.lookup('dash2dock-lite@icedman.github.com')?.stateObj;
    if (!dock) {
        check('dock badges', false, 'dock extension missing');
        return;
    }
    const id = global.settings.get_strv('favorite-apps').find(f => Shell.AppSystem.get_default().lookup_app(f));
    const app = Shell.AppSystem.get_default().lookup_app(id);
    const source = new MessageTray.Source({title: app.get_name()});
    source.app = app;
    Main.messageTray.add(source);
    for (const n of [1, 2])
        source.addNotification(new MessageTray.Notification({source, title: `Test ${n}`, body: 'Badge'}));
    await sleep(6500);
    const badges = dock.docks[0]?.animator?._badges ?? [];
    check('dock badge appears', badges.some(b => b.visible), `${badges.filter(b => b.visible).length} visible`);
    await screenshot('badge');
    source.destroy();
}

async function testStatusExtras() {
    const area = Main.panel.statusArea;
    const qs = area.quickSettings;
    const right = Main.panel._rightBox.get_children();
    const order = ['macify-battery', 'macify-wifi', 'macify-sound', 'macify-spotlight']
        .map(role => right.indexOf(area[role]?.container));
    order.push(right.indexOf(qs.container), right.indexOf(area.dateMenu.container));
    check('right side in macOS order (battery, Wi‑Fi, sound, Spotlight, Control Center, clock)',
        order.every((v, i) => v >= 0 && (i === 0 || v > order[i - 1])), order.join(','));
    check('battery icon lives in its own button', qs._system.get_parent() === area['macify-battery']);
    check('power mode icon tucked into Control Center', !qs._indicators.contains(qs._powerProfiles));
    check('privacy indicators stay in the bar', qs._indicators.contains(qs._camera) &&
        qs._indicators.contains(qs._volumeInput) && qs._indicators.contains(qs._location));
    for (const role of ['macify-battery', 'macify-wifi', 'macify-sound']) {
        const button = area[role];
        button.menu.open();
        await sleep(400);
        const labels = button.menu._getMenuItems().map(i => i.label?.text ?? '').filter(Boolean);
        check(`${role} opens its own menu`, button.menu.isOpen && labels.length >= 1, labels.join(' | '));
        button.menu.close();
        await sleep(200);
    }
}

// Cambia la escala de todas las pantallas con el servicio de pantallas de GNOME, como lo
// haría Ajustes › Pantallas. Las pantallas quedan una al lado de la otra.
function displayCall(method, args = null) {
    return new Promise((resolve, reject) => Gio.DBus.session.call('org.gnome.Mutter.DisplayConfig',
        '/org/gnome/Mutter/DisplayConfig', 'org.gnome.Mutter.DisplayConfig', method, args, null,
        Gio.DBusCallFlags.NONE, -1, null, (bus, result) => {
            try {
                resolve(bus.call_finish(result).deepUnpack());
            } catch (e) {
                reject(e);
            }
        }));
}

async function applyScale(wanted) {
    const [serial, monitors] = await displayCall('GetCurrentState');
    let x = 0;
    const logical = monitors.map(([[connector], modes], i) => {
        const mode = modes.find(m => m[6]['is-current']?.deepUnpack()) ?? modes[0];
        const [id, width, height, , , scales] = mode;
        const scale = scales.reduce((best, s) => (Math.abs(s - wanted) < Math.abs(best - wanted) ? s : best), 1);
        const entry = [x, 0, scale, 0, i === 0, [[connector, id, {}]]];
        x += Math.round(width / scale);
        void height;
        return entry;
    });
    await displayCall('ApplyMonitorsConfig', new GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})', [serial, 1, logical, {}]));
    await sleep(2500);
    return logical.map(l => l[2]);
}

function testLayout() {
    const monitors = Main.layoutManager.monitors;
    check(`layout: ${monitors.length} monitor(s)`, monitors.length >= 1,
        monitors.map(m => `${m.width}x${m.height}@${m.geometry_scale}`).join(' + '));
    const dockExt = Main.extensionManager.lookup('dash2dock-lite@icedman.github.com')?.stateObj;
    if (dockExt) {
        const docks = dockExt.docks ?? [];
        check('one dock per monitor', docks.length === monitors.length, `${docks.length} docks`);
        check('every dock has the Macify fixes (also after monitor or scale changes)',
            docks.length > 0 && docks.every(d => d.autohider?._macifyOriginal), `${docks.filter(d => d.autohider?._macifyOriginal).length}/${docks.length}`);
        for (const dock of docks) {
            const m = dock._monitor;
            const [x, y] = dock.get_transformed_position();
            const inside = m && x >= m.x - 1 && x + dock.width <= m.x + m.width + 1 && y + dock.height <= m.y + m.height + 1;
            check(`dock inside monitor ${m?.index}`, inside, `${Math.round(x)},${Math.round(y)} ${Math.round(dock.width)}x${Math.round(dock.height)}`);
        }
    }
    const panel = Main.panel;
    const used = panel._leftBox.width + panel._centerBox.width + panel._rightBox.width;
    check('menu bar fits the screen', used <= panel.width + 1, `${Math.round(used)} of ${Math.round(panel.width)}`);
}

// En la sesión invisible GNOME calcula mal el alto máximo de los menús (no hay área de
// trabajo); para poder fotografiarlos se les da uno a mano.
async function captureMenu(role, name) {
    const button = Main.panel.statusArea[role];
    button.menu.open();
    await sleep(200);
    button.menu.actor.style = 'max-height: 900px;';
    button.menu.actor.queue_relayout();
    await sleep(700);
    const [, natural] = button.menu.actor.get_preferred_height(-1);
    check(`${role} opens with a sane height`, natural > 40 && natural < 2000, `${Math.round(natural)} px`);
    const items = button.menu._getMenuItems();
    console.log(`MACIFY-TEST menu ${role} height=${Math.round(natural)} items=${items.length} open=${button.menu.isOpen} ` +
        `labels=${items.slice(0, 4).map(i => i.label?.text).join('|')}`);
    await screenshot(name);
    button.menu.close();
    await sleep(300);
}

// Capturas para el video de presentación (scripts/demo/make_video.sh).
// En el video no deben salir las redes Wi‑Fi reales que hay cerca: se muestran de ejemplo.
function sampleWifiNetworks() {
    const macify = Main.extensionManager.lookup('macify-menubar@macify.dev').stateObj;
    const status = macify._parts.find(p => p.constructor.name === 'StatusBar');
    const wifi = status._extras.map(e => e.menu).find(m => m.constructor.name === 'WifiMenu');
    wifi._refresh = function () {
        this._switch.setToggleState(true);
        this._networks.removeAll();
        for (const [name, level, current] of [['Home', 'excellent', true], ['Studio 5G', 'good', false],
            ['Café Guest', 'ok', false]]) {
            const item = new PopupMenu.PopupImageMenuItem(name, `network-wireless-signal-${level}-symbolic`);
            if (current)
                item.setOrnament(PopupMenu.Ornament.CHECK);
            this._networks.addMenuItem(item);
        }
    };
}

async function captureDemo() {
    sampleWifiNetworks();
    await sleep(1500);
    await screenshot('desktop');
    await openApp('org.gnome.TextEditor.desktop');
    for (const [role, name] of [['macify-menu-edit', 'menu-edit'], ['macify-menu-window', 'menu-window'],
        ['macify-battery', 'menu-battery'], ['macify-wifi', 'menu-wifi'], ['macify-sound', 'menu-sound']])
        await captureMenu(role, name);
    global.display.focus_window?.minimize();
    const player = fakePlayer('demo', 'Golden Hour', 'Macify Radio');
    await sleep(2500);

    await captureMenu('macify-live', 'now-playing');
    player.stop();
    await captureAppGrid();
    await testBadges();
}

async function captureAppGrid() {
    Main.overview.showApps();
    await sleep(1800);
    await screenshot('app-grid');
    Main.overview.hide();
    await sleep(800);
}

async function run() {
    createKeyboard();
    await sleep(4000);
    const scale = Number(GLib.getenv('MACIFY_SCALE') ?? '1');
    if (scale !== 1) {
        try {
            check(`scale ${scale} applied`, true, (await applyScale(scale)).join(','));
        } catch (e) {
            check(`scale ${scale} applied`, false, e.message);
        }
    }
    testLayout();
    try {
        const macify = testParts();
        await screenshot('bar');
        if (GLib.getenv('MACIFY_TEST_ONLY') === 'appgrid') {
            await captureAppGrid();
            throw new Error('only app grid requested');
        }
        if (GLib.getenv('MACIFY_TEST_ONLY') === 'demo') {
            await captureDemo();
            throw new Error('only demo captures requested');
        }
        if (GLib.getenv('MACIFY_TEST_ONLY') === 'menus') {
            await openApp('org.gnome.TextEditor.desktop');
            for (const [role, name] of [['macify-app-menu', 'menu-app'], ['macify-menu-edit', 'menu-edit'],
                ['macify-menu-window', 'menu-window'], ['macify-battery', 'menu-battery'],
                ['macify-wifi', 'menu-wifi'], ['macify-sound', 'menu-sound']])
                await captureMenu(role, name);
            throw new Error('only menus requested');
        }
        await testStatusExtras();
        await testLiveActivities(macify);
        await testDockScanout();
        await testBadges();
        await testEditor();
        await testTerminal();
    } catch (e) {
        check('unexpected error', false, `${e.message} ${e.stack}`);
    }
    const file = Gio.File.new_for_path(`${OUT}/results.json`);
    file.replace_contents(JSON.stringify(results, null, 2), null, false, Gio.FileCreateFlags.NONE, null);
    console.log('MACIFY-TEST DONE');
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 300, () => {
        global.context.terminate();
        return GLib.SOURCE_REMOVE;
    });
}

export default class MacifyShellTests extends Extension {
    enable() {
        run();
    }

    disable() {}
}
