# Macify

Turn Ubuntu's GNOME desktop into a macOS-style desktop with one click — from the boot screen to the dock. Everything Macify changes can be checked, repaired, restored or uninstalled without leaving anything behind.

Tested on **Ubuntu 26.04.1 LTS, GNOME 50, Wayland**. The app follows your system language (English, or Spanish when the system is in Spanish).

## What it changes

| Area | Result |
|---|---|
| Boot | Black screen, white logo and a thin progress bar (Plymouth theme *Macify*) |
| Login | macOS-style login screen (WhiteSur GDM theme) |
| Windows | Traffic-light buttons, macOS title bars, light or dark (WhiteSur, GTK 3 and 4) |
| Menu bar | Transparent bar with the system logo menu and the active app name (Macify Menubar extension) |
| Dock | Floating glass dock, magnification on hover, bounce on launch, dot indicators (Dash2Dock Animated) |
| Effects | Magic lamp when minimizing, glass blur for Macify's window |
| Icons | WhiteSur icon set; Macify creates a macOS-shaped icon for any app that lacks one |
| Cursor & fonts | WhiteSur cursor, San Francisco fonts (SF Pro, SF Mono) |
| Colors | Accent color taken from your wallpaper |
| Apps | VS Code, Brave and Firefox use the macOS title bar and buttons |
| Upkeep | New apps (apt, snap, Flatpak) get their icon automatically; a health check runs at login |

## Install

```bash
sudo apt install ./macify_*_all.deb
```

Open **Macify** from the app grid, follow the assistant and press **Install**. It asks for your password once (for the boot and login screens) and, at the end, to restart.

## Check and repair

Open Macify → **Check for Problems**, or from a terminal:

```bash
macify doctor          # what is fine, outdated or broken
macify doctor --fix    # update and repair what can be fixed
```

It checks system tools, theme and extension updates, extensions that fail to load, settings changed since install, broken icons, fonts, the boot screen and the automatic upkeep.

## Restore and uninstall

- **Restore Original Settings** (in the app) or `macify restore`: GNOME settings go back to how they were before Macify.
- **Uninstall Everything** or `macify uninstall`: also removes themes, icons, extensions, fonts, the boot and login screens and the upkeep. Then `sudo apt remove macify`.

### If the login screen ever fails

Press `Ctrl` + `Alt` + `F3`, sign in, and run:

```bash
sudo /usr/lib/macify/macify/data/root/macify-root.sh revert ~/.cache/macify/WhiteSur-gtk-theme
sudo reboot
```

## Project layout

```
app/
├── macify/
│   ├── __main__.py     command line (install, doctor, restore, uninstall…) and app entry point
│   ├── gui.py          the assistant window (GTK 4 + libadwaita)
│   ├── installer.py    the installation, as an ordered list of named steps
│   ├── profile.py      user choices → GNOME and extension settings
│   ├── doctor.py       health check: problems, updates and fixes
│   ├── session.py      upkeep at login and when apps are installed
│   ├── system.py       gsettings read/write with backup and restore
│   ├── themes.py       WhiteSur window theme, icons, cursor, Firefox theme
│   ├── extensions.py   GNOME extensions, including Macify Menubar
│   ├── icons.py        Macify icon theme, icon generator and audit
│   ├── apps.py         VS Code, Brave and Firefox title bars
│   ├── boot.py         boot (Plymouth) and login (GDM) screens
│   ├── fonts.py        San Francisco fonts
│   ├── deps.py         system packages
│   ├── launcher.py     app menu entry and icon
│   ├── uninstall.py    clean removal
│   ├── assets.py, colors.py, info.py, i18n.py
│   └── data/           app icon, wallpapers, menubar extension, boot theme, root helper
├── tests/              automated tests
└── scripts/            build.sh (.pyz) and build_deb.sh (.deb)
```

## Development

```bash
python3 -m unittest discover -s tests -v   # tests (nothing is changed on the system)
python3 -m macify install --dry-run        # see every change without applying it
./scripts/build.sh                         # dist/macify.pyz
./scripts/build_deb.sh                     # dist/macify_<version>_all.deb
```

## Credits and licenses

- WhiteSur GTK theme, icons and cursors by vinceliuice — GPL-3.0, downloaded from GitHub at install time.
- Extensions downloaded from extensions.gnome.org: User Themes, Blur my Shell, Just Perfection, Dash2Dock Animated, Compiz alike magic lamp effect — each under its own license.
- San Francisco fonts are Apple's and are never bundled: Macify uses your own copy or downloads them from Apple's developer site.
- macOS is a trademark of Apple Inc. Macify is not affiliated with Apple or Canonical.
