"""Asistente de Macify (GTK4 + libadwaita), al estilo del asistente de bienvenida de macOS."""

import subprocess
import threading
from importlib import resources

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__, boot, doctor, info, installer, launcher, profile, system, updates, wallpapers  # noqa: E402
from .assets import install_bundled_data, load_config, save_config_value  # noqa: E402
from .colors import accent_for_wallpaper, accent_label, dominant_rgb  # noqa: E402
from .i18n import _, language  # noqa: E402
from .uninstall import uninstall  # noqa: E402

APP_ID = launcher.APP_ID
GREETINGS = ["Hello", "Hola", "Bonjour", "Ciao", "Olá", "Hallo", "こんにちは", "안녕하세요"]
PAGES = ["welcome", "appearance", "wallpaper", "dock", "summary"]
DOCK_PREVIEW_ICONS = ["firefox", "org.gnome.Nautilus", "org.gnome.Ptyxis", "org.gnome.Settings",
                      "org.gnome.TextEditor", "org.gnome.Calculator"]
STEP_ICONS = ["emblem-system-symbolic", "preferences-desktop-font-symbolic", "preferences-desktop-appearance-symbolic",
              "view-app-grid-symbolic", "input-mouse-symbolic", "view-grid-symbolic", "emblem-ok-symbolic",
              "applications-system-symbolic", "view-refresh-symbolic", "preferences-desktop-wallpaper-symbolic",
              "computer-symbolic"]



def text(label: str, css: str, center: bool = False) -> Gtk.Label:
    return Gtk.Label(label=label, wrap=True, xalign=0.5 if center else 0,
                     justify=Gtk.Justification.CENTER if center else Gtk.Justification.LEFT, css_classes=[css])


def vbox(spacing: int = 16, **kwargs) -> Gtk.Box:
    return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing, **kwargs)


def clear(container: Gtk.Widget) -> None:
    child = container.get_first_child()
    while child:
        container.remove(child)
        child = container.get_first_child()


class MacifyWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Macify", default_width=920, default_height=700)
        self.choices = profile.load_choices()
        self.busy = False
        self.quick = False          # «Customize»: sólo aspecto, en vivo, sin reinstalar
        self._live_pending = 0
        self.step_rows: list[Gtk.Stack] = []

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
                               transition_duration=450, vexpand=True)
        for name, page in (("welcome", self._welcome_page()), ("appearance", self._appearance_page()),
                           ("wallpaper", self._wallpaper_page()), ("dock", self._dock_page()),
                           ("summary", self._summary_page()), ("progress", self._progress_page()),
                           ("done", self._done_page()), ("manage", self._manage_page()),
                           ("doctor", self._doctor_page()), ("update", self._update_page())):
            self.stack.add_named(page, name)

        self.back = Gtk.Button(label=_("Back"), css_classes=["mf-ghost"])
        self.back.connect("clicked", lambda _b: self._go(-1))
        self.next = Gtk.Button(label=_("Continue"), css_classes=["mf-cta"])
        self.next.connect("clicked", lambda _b: self._go(+1))
        self.dots = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
        self.nav = Gtk.Box(spacing=12, margin_start=28, margin_end=28, margin_bottom=22, margin_top=8)
        for widget in (self.back, self.dots, self.next):
            self.nav.append(widget)

        body = vbox(0)
        body.append(self.stack)
        body.append(self.nav)
        self.backdrop = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True, css_classes=["mf-backdrop"])
        self._update_backdrop()
        overlay = Gtk.Overlay(child=self.backdrop)
        overlay.add_overlay(Gtk.Box(css_classes=["mf-tint"]))
        overlay.add_overlay(body)
        toolbar = Adw.ToolbarView(content=overlay, top_bar_style=Adw.ToolbarStyle.FLAT,
                                  extend_content_to_top_edge=True)
        toolbar.add_top_bar(Adw.HeaderBar(title_widget=Gtk.Label(label="")))
        self.set_content(toolbar)

        self._show("manage" if system.BACKUP_FILE.exists() else "welcome")

    # ----- navegación -----

    def _show(self, name: str) -> None:
        self.stack.set_visible_child_name(name)
        in_flow = name in PAGES
        self.nav.set_visible(in_flow and name != "welcome")
        if in_flow:
            index = PAGES.index(name)
            self.next.set_label((_("Apply") if self.quick else _("Install")) if name == "summary" else _("Continue"))
            clear(self.dots)
            for i in range(1, len(PAGES)):
                self.dots.append(Gtk.Box(css_classes=["mf-dot", "mf-dot-on"] if i == index else ["mf-dot"]))
        if name == "summary":
            self._fill_summary()

    def _go(self, delta: int) -> None:
        current = self.stack.get_visible_child_name()
        if current == "summary" and delta > 0:
            self._apply_look() if self.quick else self._start_install()
            return
        # «Wallpaper» va directo: elegir el fondo y aplicar, sin pasar por el dock.
        if self.quick and getattr(self, "first_page", "") == "wallpaper":
            if current == "wallpaper" and delta > 0:
                self._show("summary")
                return
            if current == "summary" and delta < 0:
                self._show("wallpaper")
                return
        if current == getattr(self, "first_page", "appearance") and delta < 0 and self.quick:
            self._show("manage")
            return
        index = PAGES.index(current) + delta
        if 0 <= index < len(PAGES):
            self._show(PAGES[index])

    def _page(self, *children: Gtk.Widget, center: bool = False) -> Gtk.Widget:
        box = vbox(18, margin_top=56, margin_bottom=10, margin_start=28, margin_end=28,
                   valign=Gtk.Align.CENTER if center else Gtk.Align.START)
        for child in children:
            box.append(child)
        return Gtk.ScrolledWindow(child=Adw.Clamp(maximum_size=760, child=box),
                                  hscrollbar_policy=Gtk.PolicyType.NEVER)

    def _fade_in(self, widget: Gtk.Widget) -> None:
        widget.set_opacity(0)
        animation = Adw.TimedAnimation.new(widget, 0, 1, 1100, Adw.PropertyAnimationTarget.new(widget, "opacity"))
        animation.set_easing(Adw.Easing.EASE_OUT_CUBIC)
        GLib.idle_add(lambda: animation.play() or False)

    # ----- páginas -----

    def _welcome_page(self) -> Gtk.Widget:
        self.hello = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=700)
        first = "Hola" if language() == "es" else "Hello"
        for word in [first] + [w for w in GREETINGS if w != first]:
            self.hello.add_named(text(word, "mf-hello", center=True), word)
        GLib.timeout_add(1800, self._next_greeting)
        system_info = info.summary()
        start = Gtk.Button(label=_("Get Started"), halign=Gtk.Align.CENTER, margin_top=12, css_classes=["mf-cta"])
        start.connect("clicked", lambda _b: self._start_flow(quick=False))
        icon = Gtk.Image.new_from_icon_name(APP_ID)
        icon.set_pixel_size(112)
        icon.add_css_class("mf-float")
        system_line = Gtk.Label(label=f"{system_info['os']}  ·  {system_info['desktop']}  ·  {system_info['session']}",
                                halign=Gtk.Align.CENTER, css_classes=["mf-pill"])
        content = vbox(14, halign=Gtk.Align.CENTER)
        for widget in (icon, self.hello,
                       text(_("Goodbye, Ubuntu style. Hello, macOS style."), "mf-subtitle", center=True),
                       system_line, start,
                       text(_("Everything can be undone from Macify."), "mf-small", center=True)):
            content.append(widget)
        self._fade_in(content)
        return self._page(content, center=True)

    def _next_greeting(self) -> bool:
        current = GREETINGS.index(self.hello.get_visible_child_name())
        self.hello.set_visible_child_name(GREETINGS[(current + 1) % len(GREETINGS)])
        return GLib.SOURCE_CONTINUE

    def _appearance_page(self) -> Gtk.Widget:
        row = Gtk.Box(spacing=18, halign=Gtk.Align.CENTER)
        first = None
        for value, name in (("light", _("Light")), ("dark", _("Dark"))):
            preview = Gtk.Box(css_classes=["mf-preview", f"mf-preview-{value}"])
            preview.append(Gtk.Box(css_classes=["mf-preview-window"], hexpand=True))
            card = vbox(10)
            card.append(preview)
            card.append(text(name, "mf-step", center=True))
            button = Gtk.ToggleButton(child=card, css_classes=["mf-choice"], group=first)
            first = first or button
            button.set_active(self.choices.appearance == value)
            button.connect("toggled", self._on_appearance, value)
            row.append(button)
        return self._page(text(_("Choose your look"), "mf-title"),
                          text(_("Windows, menus and apps will switch to this style."), "mf-subtitle"), row)

    def _on_appearance(self, button: Gtk.ToggleButton, value: str) -> None:
        if button.get_active():
            self.choices.appearance = value
            self._live()

    def _update_dock_preview(self) -> None:
        for image in self.dock_icons:
            image.set_pixel_size(self.choices.dock_size)
        (self.dock_preview.add_css_class if self.choices.magnify else self.dock_preview.remove_css_class)("mf-magnify")

    def _update_backdrop(self) -> None:
        wallpaper = profile.desktop_wallpaper(self.choices)
        if wallpaper.exists():
            self.backdrop.set_filename(str(wallpaper))

    def _set_choice(self, name: str, value) -> None:
        setattr(self.choices, name, value)
        self._live()

    def _live(self) -> None:
        """En «Customize», cada cambio se ve en el escritorio al momento (con una pequeña espera)."""
        if not self.quick:
            return
        self._live_pending += 1
        ticket = self._live_pending

        def apply_if_latest() -> bool:
            if ticket == self._live_pending:
                choices = profile.Choices(**vars(self.choices))
                threading.Thread(target=installer.apply_look, args=(choices, lambda _m: None), daemon=True).start()
            return GLib.SOURCE_REMOVE

        GLib.timeout_add(350, apply_if_latest)

    def _wallpaper_page(self) -> Gtk.Widget:
        self.wallpaper_sections = vbox(12)
        self.wallpaper_flows: list[Gtk.FlowBox] = []
        self.accent_dot = Gtk.Box(css_classes=["mf-accent"], valign=Gtk.Align.CENTER)
        self.accent_dot.set_size_request(18, 18)
        self.accent_css = Gtk.CssProvider()
        self.accent_dot.get_style_context().add_provider(self.accent_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.accent_label = text("", "mf-subtitle")
        accent_row = Gtk.Box(spacing=10)
        accent_row.append(self.accent_dot)
        accent_row.append(self.accent_label)
        add = Gtk.Button(label=_("Add Photos…"), halign=Gtk.Align.START, css_classes=["mf-ghost"])
        add.connect("clicked", self._on_add_photos)
        install_bundled_data()
        self._fill_wallpapers()
        return self._page(text(_("Choose your wallpaper"), "mf-title"),
                          text(_("Buttons and system colors come from your wallpaper."), "mf-subtitle"),
                          accent_row, self.wallpaper_sections, add)

    def _fill_wallpapers(self) -> None:
        """Galería por secciones; las miniaturas se cargan aparte para no frenar la ventana."""
        clear(self.wallpaper_sections)
        self.wallpaper_flows = []
        current = profile.wallpaper_path(self.choices).resolve()
        items = wallpapers.catalog()
        pending = []
        for section in wallpapers.sections(items):
            members = [w for w in items if w.section == section]
            if not members:
                continue
            flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.SINGLE, max_children_per_line=4,
                               min_children_per_line=4, row_spacing=14, column_spacing=14, homogeneous=True,
                               css_classes=["mf-wallpapers"])
            flow.connect("child-activated", self._on_wallpaper)
            for wallpaper in members:
                picture = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True, css_classes=["mf-thumb"])
                picture.set_size_request(-1, 84)
                tile = vbox(6)
                tile.append(picture)
                tile.append(text(wallpaper.title, "mf-thumb-title", center=True))
                tile.wallpaper_path = wallpaper.path
                flow.append(tile)
                if wallpaper.path.resolve() == current:
                    flow.select_child(tile.get_parent())
                pending.append((picture, wallpaper.path))
            self.wallpaper_sections.append(text(_(section), "mf-section"))
            self.wallpaper_sections.append(flow)
            self.wallpaper_flows.append(flow)
        self._update_accent()

        def load() -> None:
            for picture, path in pending:
                thumb = wallpapers.thumbnail(path)
                GLib.idle_add(picture.set_filename, str(thumb))

        threading.Thread(target=load, daemon=True).start()

    def _on_wallpaper(self, flow: Gtk.FlowBox, child: Gtk.FlowBoxChild) -> None:
        for other in self.wallpaper_flows:
            if other is not flow:
                other.unselect_all()
        self.choices.wallpaper = str(child.get_child().wallpaper_path)
        self._update_accent()
        self._update_backdrop()
        self._live()

    def _update_accent(self) -> None:
        wallpaper = profile.desktop_wallpaper(self.choices)
        if not wallpaper.exists():
            return
        r, g, b = dominant_rgb(wallpaper)
        self.accent_css.load_from_string(f".mf-accent {{ background: rgb({r}, {g}, {b}); border-radius: 999px; }}")
        self.accent_label.set_label(_("Accent color: {color}").format(color=accent_label(accent_for_wallpaper(wallpaper))))

    def _on_add_photos(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title=_("Add your photos"))
        images = Gtk.FileFilter()
        images.set_name(_("Images"))
        for mime in ("image/jpeg", "image/png", "image/webp"):
            images.add_mime_type(mime)
        dialog.set_default_filter(images)
        dialog.open_multiple(self, None, self._photos_chosen)

    def _photos_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            files = dialog.open_multiple_finish(result)
        except GLib.Error:
            return
        added = load_config().get("user_wallpapers", [])
        for index in range(files.get_n_items()):
            path = files.get_item(index).get_path()
            if path and path not in added:
                added.append(path)
        save_config_value("user_wallpapers", added)
        if added:
            self.choices.wallpaper = added[-1]
        self._fill_wallpapers()

    def _dock_page(self) -> Gtk.Widget:
        size = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 32, 72, 4)
        size.set_value(self.choices.dock_size)
        size.set_hexpand(True)
        size.set_size_request(220, -1)
        size.set_round_digits(0)
        size.connect("value-changed", lambda s: self._set_choice("dock_size", 4 * round(s.get_value() / 4)))
        size_row = Adw.ActionRow(title=_("Icon size"))
        size_row.add_suffix(size)
        magnify = Adw.SwitchRow(title=_("Magnify on hover"), subtitle=_("Icons grow like on macOS"))
        magnify.set_active(self.choices.magnify)
        magnify.connect("notify::active", lambda r, _p: self._set_choice("magnify", r.get_active()))
        lamp = Adw.SwitchRow(title=_("Magic lamp effect"), subtitle=_("Animation when minimizing windows"))
        lamp.set_active(self.choices.magic_lamp)
        lamp.connect("notify::active", lambda r, _p: self._set_choice("magic_lamp", r.get_active()))
        autohide = Adw.SwitchRow(title=_("Hide automatically"),
                                 subtitle=_("When a window covers it. Move the pointer to the bottom edge to show it."))
        autohide.set_active(self.choices.dock_autohide)
        autohide.connect("notify::active", lambda r, _p: self._set_choice("dock_autohide", r.get_active()))
        group = Adw.PreferencesGroup()
        for row in (size_row, magnify, lamp, autohide):
            group.add(row)
        self.dock_preview = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER, margin_top=6, margin_bottom=6,
                                    css_classes=["mf-dock-preview"])
        self.dock_icons = []
        for name in DOCK_PREVIEW_ICONS:
            image = Gtk.Image.new_from_icon_name(name)
            image.add_css_class("mf-dock-icon")
            self.dock_preview.append(image)
            self.dock_icons.append(image)
        self._update_dock_preview()
        for widget, signal in ((size, "value-changed"), (magnify, "notify::active")):
            widget.connect(signal, lambda *_a: self._update_dock_preview())
        return self._page(text(_("Your Dock"), "mf-title"),
                          text(_("Bottom, floating and glass, like on macOS."), "mf-subtitle"),
                          self.dock_preview, text(_("Try it: move the pointer over the icons."), "mf-small", center=True),
                          group)

    def _summary_page(self) -> Gtk.Widget:
        self.summary = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        login = Adw.SwitchRow(title=_("macOS-style startup and login screens"),
                              subtitle=_("Black boot screen with your logo and the macOS login screen. "
                                         "Asks for your password once."))
        login.set_active(self.choices.login_screen)
        login.connect("notify::active", self._on_login_toggle)
        self.summary_options = Adw.PreferencesGroup()
        self.summary_options.add(login)
        self.summary_title = text(_("Ready to begin"), "mf-title")
        self.summary_detail = text(_("Takes a few minutes. You'll be asked to restart at the end."), "mf-subtitle")
        return self._page(self.summary_title, self.summary_detail, self.summary, self.summary_options)

    def _on_login_toggle(self, row: Adw.SwitchRow, _param) -> None:
        self.choices.login_screen = row.get_active()
        self._fill_summary()

    def _fill_summary(self) -> None:
        clear(self.summary)
        self.summary_options.set_visible(not self.quick)
        if self.quick:
            self.summary_title.set_label(_("Apply your look"))
            self.summary_detail.set_label(_("You're seeing the changes live. Press Apply to keep them."))
            self.summary.append(Adw.ActionRow(title=_("Apply your look"),
                                              subtitle=_("Appearance, wallpaper and dock. Nothing is downloaded or reinstalled.")))
            if self._login_outdated():
                self.summary.append(Adw.ActionRow(
                    title=_("Login screen"),
                    subtitle=_("It takes your new wallpaper too. Asks for your password; then restart.")))
            return
        self.summary_title.set_label(_("Ready to begin"))
        self.summary_detail.set_label(_("Takes a few minutes. You'll be asked to restart at the end."))
        for number, step in enumerate(installer.steps(self.choices, dry_run=True)):
            row = Adw.ActionRow(title=step.title, subtitle=step.detail)
            row.add_prefix(Gtk.Image.new_from_icon_name(STEP_ICONS[number % len(STEP_ICONS)]))
            self.summary.append(row)

    def _progress_page(self) -> Gtk.Widget:
        self.progress_title = text(_("Preparing…"), "mf-title")
        self.progress_detail = text("", "mf-subtitle")
        self.progress = Gtk.ProgressBar()
        self.steps_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        self.log_buffer = Gtk.TextBuffer()
        self.log_view = Gtk.TextView(buffer=self.log_buffer, editable=False, monospace=True,
                                     wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=10, bottom_margin=10,
                                     left_margin=10, right_margin=10, css_classes=["mf-log"])
        log_scroll = Gtk.ScrolledWindow(child=self.log_view, min_content_height=160)
        return self._page(self.progress_title, self.progress_detail, self.progress, self.steps_box,
                          Gtk.Expander(label=_("What's happening, in detail"), child=log_scroll))

    def _done_page(self) -> Gtk.Widget:
        icon = Gtk.Image.new_from_icon_name(APP_ID)
        icon.set_pixel_size(128)
        reboot = Gtk.Button(label=_("Restart Now"), halign=Gtk.Align.CENTER,
                            css_classes=["mf-cta"])
        reboot.connect("clicked", lambda _b: subprocess.Popen(["gnome-session-quit", "--reboot"]))
        later = Gtk.Button(label=_("Later"), halign=Gtk.Align.CENTER, css_classes=["mf-ghost"])
        later.connect("clicked", lambda _b: self.close())
        self.done_title = text(_("Welcome to your new Mac"), "mf-title", center=True)
        self.done_detail = text(_("Restart your computer to see all the changes."), "mf-subtitle", center=True)
        content = vbox(16, halign=Gtk.Align.CENTER)
        for widget in (icon, self.done_title, self.done_detail, reboot, later):
            content.append(widget)
        return self._page(content, center=True)

    def _tile(self, icon: str, title: str, subtitle: str, action, *classes: str) -> Gtk.Button:
        box = vbox(6, halign=Gtk.Align.START)
        image = Gtk.Image.new_from_icon_name(icon)
        image.set_pixel_size(28)
        image.set_halign(Gtk.Align.START)
        box.append(image)
        box.append(text(title, "mf-step"))
        box.append(text(subtitle, "mf-small"))
        button = Gtk.Button(child=box, hexpand=True, css_classes=["mf-tile", *classes])
        button.connect("clicked", lambda _b: action())
        return button

    def _manage_page(self) -> Gtk.Widget:
        icon = Gtk.Image.new_from_icon_name(APP_ID)
        icon.set_pixel_size(96)
        icon.add_css_class("mf-float")
        tiles = Gtk.Grid(column_spacing=14, row_spacing=14, column_homogeneous=True, margin_top=10)
        tiles.attach(self._tile("preferences-desktop-appearance-symbolic", _("Customize"),
                                _("Look, wallpaper and dock, live."), lambda: self._start_flow(quick=True),
                                "mf-tile-primary"), 0, 0, 1, 1)
        tiles.attach(self._tile("preferences-desktop-wallpaper-symbolic", _("Wallpaper"),
                                _("Pick one or add yours. Nothing is reinstalled."),
                                lambda: self._start_flow(quick=True, page="wallpaper"), "mf-tile-primary"), 1, 0, 1, 1)
        self.update_tile = self._tile("software-update-available-symbolic", _("Software Update"),
                                      _("Version {version}").format(version=__version__), self._check_updates)
        tiles.attach(self.update_tile, 0, 1, 1, 1)
        tiles.attach(self._tile("emblem-ok-symbolic", _("Check for Problems"),
                                _("Updates, errors and repairs."), self._run_doctor), 1, 1, 1, 1)
        tiles.attach(self._tile("view-refresh-symbolic", _("Reinstall Everything"),
                                _("Every step again, from the start."), lambda: self._start_flow(quick=False)), 0, 2, 1, 1)
        tiles.attach(self._tile("edit-undo-symbolic", _("Restore Original Settings"),
                                _("Ubuntu settings as they were."),
                                lambda: self._run_maintenance(_("Restoring…"), lambda log: system.restore(False, log))), 1, 2, 1, 1)
        tiles.attach(self._tile("user-trash-symbolic", _("Uninstall Everything"),
                                _("Remove all of Macify's changes."),
                                lambda: self._run_maintenance(_("Uninstalling…"), lambda log: uninstall(False, log)),
                                "mf-tile-danger"), 0, 3, 2, 1)
        self._quiet_update_check()
        content = vbox(14)
        header = vbox(10, halign=Gtk.Align.CENTER)
        for widget in (icon, text(_("Macify is active"), "mf-title", center=True),
                       text(_("Change your style, go back to the original, or remove everything."), "mf-subtitle", center=True)):
            header.append(widget)
        content.append(header)
        content.append(tiles)
        return self._page(content, center=True)

    # ----- actualizaciones -----

    def _update_page(self) -> Gtk.Widget:
        icon = Gtk.Image.new_from_icon_name(APP_ID)
        icon.set_pixel_size(96)
        self.update_title = text(_("Software Update"), "mf-title", center=True)
        self.update_detail = text("", "mf-subtitle", center=True)
        self.update_spinner = Gtk.Spinner(halign=Gtk.Align.CENTER)
        self.update_bar = Gtk.ProgressBar(visible=False)
        self.update_notes = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"], visible=False)
        self.update_button = Gtk.Button(label=_("Update Now"), halign=Gtk.Align.CENTER, css_classes=["mf-cta"])
        self.update_button.connect("clicked", lambda _b: self._install_update())
        back = Gtk.Button(label=_("Back"), halign=Gtk.Align.CENTER, css_classes=["mf-ghost"])
        back.connect("clicked", lambda _b: self.busy or self._show("manage"))
        self.update_back = back
        buttons = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        buttons.append(back)
        buttons.append(self.update_button)
        content = vbox(16)
        header = vbox(10, halign=Gtk.Align.CENTER)
        for widget in (icon, self.update_title, self.update_detail, self.update_spinner):
            header.append(widget)
        for widget in (header, self.update_bar, self.update_notes, buttons):
            content.append(widget)
        return self._page(content, center=True)

    def _quiet_update_check(self) -> None:
        """Al abrir: si hay una versión nueva, la ficha de actualización lo dice."""
        def work() -> None:
            try:
                release = updates.latest()
            except Exception:  # noqa: BLE001 - sin conexión: la ficha queda como está
                return
            if release and updates.is_newer(release["version"]):
                GLib.idle_add(self._mark_update_tile, release)

        threading.Thread(target=work, daemon=True).start()

    def _mark_update_tile(self, release: dict) -> bool:
        self.update_tile.add_css_class("mf-tile-primary")
        label = self.update_tile.get_child().get_last_child()
        label.set_label(_("Version {version} is available").format(version=release["version"]))
        return GLib.SOURCE_REMOVE

    def _check_updates(self) -> None:
        if self.busy:
            return
        self.release = None
        self.update_title.set_label(_("Checking for updates…"))
        self.update_detail.set_label(_("Looking for a new version on GitHub."))
        self.update_spinner.set_visible(True)
        self.update_spinner.start()
        self.update_bar.set_visible(False)
        self.update_notes.set_visible(False)
        self.update_button.set_visible(False)
        self._show("update")

        def work() -> None:
            try:
                release = updates.latest()
                GLib.idle_add(self._show_update, release, None)
            except Exception as error:  # noqa: BLE001
                GLib.idle_add(self._show_update, None, error)

        threading.Thread(target=work, daemon=True).start()

    def _show_update(self, release: dict | None, error: Exception | None) -> bool:
        self.update_spinner.stop()
        self.update_spinner.set_visible(False)
        if error is not None:
            self.update_title.set_label(_("Could not check for updates"))
            self.update_detail.set_label(_("Check your internet connection and try again."))
            self.update_button.set_label(_("Try Again"))
            self.update_button.set_visible(True)
            return GLib.SOURCE_REMOVE
        if not release or not updates.is_newer(release["version"]):
            self.update_title.set_label(_("Macify is up to date"))
            self.update_detail.set_label(_("You have the latest version, {version}.").format(version=__version__))
            self.update_button.set_visible(False)
            return GLib.SOURCE_REMOVE
        self.release = release
        size = release.get("size", 0) / 1_048_576
        self.update_title.set_label(_("Macify {version} is available").format(version=release["version"]))
        self.update_detail.set_label(_("You have version {current}. Download size: {size:.1f} MB.")
                                     .format(current=__version__, size=size))
        clear(self.update_notes)
        for item in updates.notes(release)[:8]:
            row = Adw.ActionRow(title=GLib.markup_escape_text(item))
            row.add_prefix(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"))
            self.update_notes.append(row)
        self.update_notes.set_visible(bool(updates.notes(release)))
        self.update_button.set_label(_("Update Now"))
        self.update_button.set_visible(True)
        return GLib.SOURCE_REMOVE

    def _install_update(self) -> None:
        if self.busy:
            return
        release = getattr(self, "release", None)
        if release is None:            # «Try Again» tras un error de conexión
            self._check_updates()
            return
        if release == "reopen":        # ya instalada: abre la versión nueva y cierra esta
            # Espera a que esta ventana suelte su nombre en el bus; si no, la nueva sólo la activaría.
            subprocess.Popen(["/bin/sh", "-c", 'sleep 1; exec "$@"', "macify", *launcher.command()],
                             start_new_session=True)
            self.get_application().quit()
            return
        self.busy = True
        self.update_button.set_visible(False)
        self.update_back.set_sensitive(False)
        self.update_bar.set_visible(True)
        self.update_bar.set_fraction(0)
        self.update_title.set_label(_("Downloading Macify {version}…").format(version=release["version"]))

        def progress(fraction: float) -> None:
            GLib.idle_add(self.update_bar.set_fraction, fraction)

        def log(message: str) -> None:
            GLib.idle_add(self.update_detail.set_label, message)

        def work() -> None:
            try:
                updates.install(release, log, progress)
                GLib.idle_add(self._update_done, None)
            except Exception as error:  # noqa: BLE001
                GLib.idle_add(self._update_done, error)

        threading.Thread(target=work, daemon=True).start()

    def _update_done(self, error: Exception | None) -> bool:
        self.busy = False
        self.update_back.set_sensitive(True)
        self.update_bar.set_visible(False)
        if error is not None:
            self.update_title.set_label(_("The update was not installed"))
            self.update_detail.set_label(str(error))
            self.update_button.set_label(_("Try Again"))
            self.update_button.set_visible(True)
            return GLib.SOURCE_REMOVE
        self.update_title.set_label(_("Macify {version} is installed").format(version=self.release["version"]))
        self.update_detail.set_label(_("Reopen Macify to use the new version."))
        self.update_notes.set_visible(False)
        self.update_button.set_label(_("Reopen Macify"))
        self.update_button.set_visible(True)
        self.release = "reopen"
        return GLib.SOURCE_REMOVE

    # ----- diagnóstico -----

    def _doctor_page(self) -> Gtk.Widget:
        self.doctor_title = text(_("Checking your Mac…"), "mf-title")
        self.doctor_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        self.doctor_fix = Gtk.Button(label=_("Fix All"), halign=Gtk.Align.START,
                                     css_classes=["mf-cta"])
        self.doctor_fix.connect("clicked", lambda _b: self._fix_doctor())
        back = Gtk.Button(label=_("Back"), halign=Gtk.Align.START, css_classes=["mf-ghost"])
        back.connect("clicked", lambda _b: self._show("manage"))
        buttons = Gtk.Box(spacing=12)
        buttons.append(back)
        buttons.append(self.doctor_fix)
        return self._page(self.doctor_title, self.doctor_list, buttons)

    def _run_doctor(self) -> None:
        if self.busy:
            return
        self.busy = True
        clear(self.doctor_list)
        self.doctor_title.set_label(_("Checking your Mac…"))
        self.doctor_fix.set_visible(False)
        spinner = Gtk.Spinner(margin_top=20, margin_bottom=20)
        spinner.start()
        self.doctor_list.append(spinner)
        self._show("doctor")

        def work() -> None:
            checks = doctor.run(online=True)
            GLib.idle_add(self._show_checks, checks)

        threading.Thread(target=work, daemon=True).start()

    def _show_checks(self, checks: list) -> bool:
        self.busy = False
        self.checks = checks
        clear(self.doctor_list)
        icons_by_status = {doctor.OK: "emblem-ok-symbolic", doctor.WARN: "dialog-warning-symbolic",
                           doctor.FAIL: "dialog-error-symbolic"}
        for check in checks:
            row = Adw.ActionRow(title=check.name, subtitle=check.detail)
            row.add_prefix(Gtk.Image.new_from_icon_name(icons_by_status[check.status]))
            self.doctor_list.append(row)
        fixable = any(c.status != doctor.OK and c.fix for c in checks)
        all_ok = all(c.status == doctor.OK for c in checks)
        self.doctor_title.set_label(_("Everything is fine") if all_ok else _("Some things need attention"))
        self.doctor_fix.set_visible(fixable)
        return GLib.SOURCE_REMOVE

    def _fix_doctor(self) -> None:
        checks = getattr(self, "checks", [])
        self._run_maintenance(_("Fix All"), lambda log: (doctor.fix(checks, log), None)[1])

    # ----- instalación -----

    def _log(self, message: str) -> None:
        GLib.idle_add(self._append_log, message)

    def _append_log(self, message: str) -> bool:
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, message + "\n")
        self.log_view.scroll_to_mark(self.log_buffer.get_insert(), 0, False, 0, 0)
        return GLib.SOURCE_REMOVE

    @staticmethod
    def _status_widget() -> Gtk.Stack:
        status = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        status.add_named(Gtk.Image.new_from_icon_name("content-loading-symbolic"), "pending")
        spinner = Gtk.Spinner()
        spinner.start()
        status.add_named(spinner, "running")
        status.add_named(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"), "done")
        status.add_named(Gtk.Image.new_from_icon_name("dialog-error-symbolic"), "error")
        return status

    def _start_install(self) -> None:
        if self.busy:
            return
        self.busy = True
        profile.save_choices(self.choices)
        steps = installer.steps(self.choices)
        clear(self.steps_box)
        self.step_rows = []
        for step in steps:
            status = self._status_widget()
            row = Adw.ActionRow(title=step.title)
            row.add_prefix(status)
            self.steps_box.append(row)
            self.step_rows.append(status)
        self.log_buffer.set_text("")
        self._show("progress")

        def work() -> None:
            current = 0
            try:
                for current, step in enumerate(steps):
                    GLib.idle_add(self._mark, current, len(steps), step, "running")
                    self._log(f"-- {step.title}")
                    step.run(self._log)
                    GLib.idle_add(self._mark, current, len(steps), step, "done")
                GLib.idle_add(self._finished, True)
            except Exception as error:  # noqa: BLE001 - mostrar cualquier fallo al usuario
                self._log(f"ERROR: {error}")
                GLib.idle_add(self._mark, current, len(steps), steps[current], "error")
                GLib.idle_add(self._finished, False)

        threading.Thread(target=work, daemon=True).start()

    def _mark(self, index: int, total: int, step: installer.Step, state: str) -> bool:
        self.step_rows[index].set_visible_child_name(state)
        if state == "running":
            self.progress_title.set_label(step.title)
            self.progress_detail.set_label(step.detail)
            self.progress.set_fraction(index / total)
        elif state == "done":
            self.progress.set_fraction((index + 1) / total)
        return GLib.SOURCE_REMOVE

    def _finished(self, ok: bool) -> bool:
        self.busy = False
        if ok:
            self.done_title.set_label(_("Welcome to your new Mac"))
            self.done_detail.set_label(_("Restart your computer to see all the changes."))
            self._show("done")
        else:
            self.progress_title.set_label(_("Something went wrong"))
            self.progress_detail.set_label(_("Open “What's happening, in detail” to see the error. "
                                             "You can retry or restore your settings."))
        return GLib.SOURCE_REMOVE

    def _start_flow(self, quick: bool, page: str = "appearance") -> None:
        self.quick = quick
        self.first_page = page
        self._show(page)

    def _login_outdated(self) -> bool:
        """La pantalla de inicio de sesión de Macify se queda con otro fondo si no se actualiza."""
        return self.choices.login_screen and boot.login_outdated(profile.desktop_wallpaper(self.choices))

    def _apply_look(self) -> None:
        profile.save_choices(self.choices)
        login = self._login_outdated()

        def action(log) -> None:
            installer.apply_look(self.choices, log)
            if login:
                boot.apply(profile.desktop_wallpaper(self.choices), False, log)

        if login:
            self._run_maintenance(_("Apply your look"), action, _("Applied"),
                                  _("Restart to see your wallpaper on the login screen too."))
        else:
            self._run_maintenance(_("Apply your look"), action, _("Applied"),
                                  _("Your new look is ready. No restart needed."))

    def _run_maintenance(self, title: str, action, done_title: str | None = None, done_detail: str | None = None) -> None:
        if self.busy:
            return
        self.busy = True
        clear(self.steps_box)
        self.log_buffer.set_text("")
        self.progress_title.set_label(title)
        self.progress_detail.set_label(_("One moment."))
        self.progress.pulse()
        self._show("progress")

        def work() -> None:
            try:
                action(self._log)
                GLib.idle_add(self._maintenance_done, done_title or _("Done"),
                              done_detail or _("Restart your computer to see the change."))
            except Exception as error:  # noqa: BLE001
                self._log(f"ERROR: {error}")
                GLib.idle_add(self._maintenance_done, _("Something went wrong"), _("Check the details to see the error."))

        threading.Thread(target=work, daemon=True).start()

    def _maintenance_done(self, title: str, detail: str) -> bool:
        self.busy = False
        self.progress.set_fraction(1.0)
        self.done_title.set_label(title)
        self.done_detail.set_label(detail)
        self._show("done")
        return GLib.SOURCE_REMOVE


def install_style(display: Gdk.Display) -> None:
    """Estilo e iconos propios de la app."""
    data = resources.files("macify").joinpath("data")
    provider = Gtk.CssProvider()
    provider.load_from_string(data.joinpath("gui.css").read_text())
    # El tema del usuario (~/.config/gtk-4.0/gtk.css) carga con prioridad USER: hay que superarla.
    Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
    Gtk.IconTheme.get_for_display(display).add_search_path(str(data))


class MacifyApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)

    def _on_startup(self, _app: Adw.Application) -> None:
        launcher.ensure()
        install_bundled_data()
        install_style(Gdk.Display.get_default())

    def _on_activate(self, app: Adw.Application) -> None:
        window = app.get_active_window() or MacifyWindow(app)
        window.present()


def run() -> int:
    return MacifyApp().run(None)
