"""Punto de entrada: `macify` abre la app; con argumentos funciona por terminal."""

import argparse
import sys
from pathlib import Path

from .i18n import _
from . import boot, doctor, icons, installer, profile, session, system
from .uninstall import uninstall


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="macify", description="Turn Ubuntu into a Mac.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install", help="Install and apply everything with the saved choices.")
    p_install.add_argument("--dry-run", action="store_true", help="Only show what would be done.")
    sub.add_parser("steps", help="List the installation steps.")
    sub.add_parser("audit", help="Check that no icon is broken.")
    p_doctor = sub.add_parser("doctor", help="Check the installation for problems and updates.")
    p_doctor.add_argument("--fix", action="store_true", help="Fix what can be fixed.")
    p_doctor.add_argument("--offline", action="store_true", help="Skip update checks.")
    p_refresh = sub.add_parser("refresh", help="Upkeep: icons for new apps (and dock switch at login).")
    p_refresh.add_argument("--login", action="store_true")
    sub.add_parser("upgrade", help="After installing a new version: apply only what changed and clean up.")
    p_look = sub.add_parser("look", help="Apply the look again (appearance, wallpaper, dock) without reinstalling.")
    p_look.add_argument("--appearance", choices=["light", "dark"])
    p_look.add_argument("--wallpaper", help="An image to use as wallpaper (its -dark twin is used in dark mode).")
    p_look.add_argument("--login", action="store_true", help="Also put it on the login screen (asks for a password).")
    p_restore = sub.add_parser("restore", help="Restore the original GNOME settings.")
    p_restore.add_argument("--dry-run", action="store_true")
    p_uninstall = sub.add_parser("uninstall", help="Revert everything and remove what Macify installed.")
    p_uninstall.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    choices = profile.load_choices()

    if args.command == "install":
        installer.run(choices, args.dry_run, print)
    elif args.command == "steps":
        for number, step in enumerate(installer.steps(choices, dry_run=True), 1):
            print(f"{number}. {step.title} — {step.detail}")
    elif args.command == "audit":
        result = icons.audit()
        print(_("Theme chain:"), " → ".join(result["chain"]))
        print(_("No broken icons.") if not result["missing_apps"] else "\n".join(result["missing_apps"]))
        return 1 if result["missing_apps"] else 0
    elif args.command == "doctor":
        marks = {doctor.OK: "✓", doctor.WARN: "!", doctor.FAIL: "✗"}
        checks = doctor.run(online=not args.offline)
        for check in checks:
            print(f" {marks[check.status]} {check.name:22} {check.detail}")
        if args.fix:
            fixed = doctor.fix(checks, print)
            print(_("Fixed: {count}").format(count=fixed))
            checks = doctor.run(online=False)
        return 0 if all(c.status == doctor.OK for c in checks) else 1
    elif args.command == "refresh":
        session.refresh(print, login=args.login)
    elif args.command == "upgrade":
        from . import upgrade
        upgrade.run(print)
    elif args.command == "look":
        if args.appearance:
            choices.appearance = args.appearance
        if args.wallpaper:
            wallpaper = Path(args.wallpaper).expanduser().resolve()
            if not wallpaper.is_file():
                print(_("Not found: {path}").format(path=wallpaper))
                return 1
            choices.wallpaper = str(wallpaper)
        profile.save_choices(choices)
        installer.apply_look(choices, print)
        if args.login:
            boot.apply(profile.desktop_wallpaper(choices), False, print)
    elif args.command == "restore":
        system.restore(args.dry_run, print)
    elif args.command == "uninstall":
        uninstall(args.dry_run, print)
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        return cli(sys.argv[1:])
    from .gui import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
