"""Instalación completa como lista de pasos.

La interfaz y la terminal usan la misma lista, así el progreso que ve el usuario
es el real. Cada paso tiene un título y una explicación en lenguaje simple.
"""

from dataclasses import dataclass
from typing import Callable

from .i18n import _
from . import __version__, apps, boot, deps, extensions, fonts, icons, profile, session, snaps, system, themes
from .assets import busy, install_bundled_data, save_config_value
from .profile import Choices

Log = Callable[[str], None]


@dataclass(frozen=True)
class Step:
    title: str
    detail: str
    run: Callable[[Log], None]


def _prepare(dry_run: bool, log: Log) -> None:
    missing = deps.missing_packages()
    log(_("Tools: all set.") if not missing else _("Tools to install: {packages}").format(packages=" ".join(missing)))
    if not dry_run:
        install_bundled_data()
        deps.ensure(log)


def _icons(dry_run: bool, log: Log) -> None:
    icons.ensure_theme(dry_run, log)
    created = icons.generate(dry_run, log)
    log(_("Icons created for apps without a macOS style: {count}").format(count=created))
    if not dry_run:
        missing = icons.audit()["missing_apps"]
        log(_("Audit: no broken icons.") if not missing else _("Audit: {count} missing: {apps}").format(count=len(missing), apps=missing))


def _settings(choices: Choices, dry_run: bool, log: Log) -> None:
    log(_("Accent color from your wallpaper: {color}").format(color=_(profile.accent(choices))))
    values = profile.settings(choices)
    values.update(extensions.enabled_settings(magic_lamp=choices.magic_lamp))
    system.apply_settings(values, dry_run, log)
    if not dry_run:
        profile.write_look(choices)      # la barra ajusta su texto al fondo, al momento


def steps(choices: Choices, dry_run: bool = False) -> list[Step]:
    result = [
        Step(_("Preparing the system"), _("Checks and installs the tools that are needed."),
             lambda log: _prepare(dry_run, log)),
        Step(_("Installing San Francisco fonts"), _("The same typefaces as macOS across the whole system."),
             lambda log: fonts.install(dry_run, log)),
        Step(_("macOS windows and buttons"), _("Title bars, colored buttons and apps in macOS style."),
             lambda log: themes.install_gtk(choices.appearance, dry_run, log)),
        Step(_("macOS icons"), _("Installs the macOS-style icon set."),
             lambda log: themes.install_icons(dry_run, log)),
        Step(_("macOS cursor"), _("The macOS mouse pointer."),
             lambda log: themes.install_cursors(dry_run, log)),
        Step(_("Dock, menu bar and effects"),
             _("Animated dock, macOS menu bar and minimize effect."),
             lambda log: (None if dry_run else extensions.fetch(log), extensions.install(dry_run, log),
                          extensions.install_menubar(dry_run, log))),
        Step(_("Checking every icon"), _("Creates missing icons and makes sure none is broken."),
             lambda log: _icons(dry_run, log)),
        Step(_("Your apps"), _("VS Code, Firefox and Flatpak apps use the macOS buttons."),
             lambda log: apps.apply(dry_run, log)),
        Step(_("Automatic upkeep"), _("New apps get their macOS icon on their own; the dock switches at login."),
             lambda log: session.install(dry_run, log)),
        Step(_("Applying wallpaper, colors and settings"),
             _("Wallpaper, accent color, fonts, keyboard shortcuts and lock screen."),
             lambda log: _settings(choices, dry_run, log)),
    ]
    if choices.login_screen:
        result.append(Step(_("Startup and login screens"),
                           _("macOS style from the moment you turn on your computer. Asks for your password once."),
                           lambda log: boot.apply(profile.desktop_wallpaper(choices), dry_run, log)))
    return result


def apply_look(choices: Choices, log: Log) -> None:
    """Sólo el aspecto (apariencia, fondo, dock): sin descargas ni reinstalaciones."""
    if not themes.variant_installed(choices.appearance):
        themes.install_gtk(choices.appearance, False, log)   # sólo si falta esa variante
    themes.link_libadwaita(choices.appearance, log)
    snaps.sync(choices.appearance, log)
    _settings(choices, False, log)


def run(choices: Choices, dry_run: bool, log: Log) -> None:
    all_steps = steps(choices, dry_run)
    log(_("== Macify: {count} steps").format(count=len(all_steps)) + (_(" (dry run)") if dry_run else ""))
    with busy():
        for step in all_steps:
            log(f"-- {step.title}")
            step.run(log)
    if not dry_run:
        save_config_value("applied_version", __version__)     # las actualizaciones parten de aquí
    log(_("== Dry run finished: nothing was changed.") if dry_run else _("== Done. Restart to see all the changes."))
