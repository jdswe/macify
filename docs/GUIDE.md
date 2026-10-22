# Macify

Turn Ubuntu's GNOME desktop into a macOS-style desktop with one click — from the boot screen to the dock. Everything Macify changes can be checked, repaired, restored or uninstalled without leaving anything behind.

Tested on **Ubuntu 26.04.1 LTS, GNOME 50, Wayland**. The app follows your system language (English, or Spanish when the system is in Spanish).

## What it changes

| Area | Result |
|---|---|
| Boot | Black screen, white logo and a progress bar timed to your PC's real startup and shutdown, with “Welcome” and “See you soon” |
| Login | macOS-style login screen (WhiteSur GDM theme) |
| Windows | Traffic-light buttons, macOS title bars, light or dark (WhiteSur, GTK 3 and 4) |
| Menu bar | Logo menu, the app's name in bold and File, Edit, View, Window and Help menus for any app, following Apple's guidelines (Macify Menubar extension) |
| Status menus | Battery (Energy Mode: Low Power, Automatic, High Power; time left), Bluetooth (on/off, connect paired devices; shown only if the computer has Bluetooth), Wi‑Fi (networks, connect), Sound (volume up to 150 % when over‑amplification is on, output device) and Control Center, each its own menu |
| Control Center | Only what has no menu of its own, in Apple's order: Airplane Mode, Do Not Disturb, brightness, Dark Style, Night Light. Shut down, restart and lock are in the logo menu |
| Volume and brightness | The keys show a glass card at the top right with its name (Sound, Display…), like macOS |
| Screenshots | A thumbnail slides in at the bottom right; the image is already copied, so Ctrl+V pastes it. Click it to open the image |
| Calendar | The clock menu shows the month and today in red, with widget-style cards |
| Live Activities | Bubble at the top for music, charging and connection; Now Playing with cover, progress, controls, volume and source choice |
| Dock | Floating glass dock, magnification, bounce, red notification badges; reachable over maximized and full-screen apps (Dash2Dock Animated) |
| Apps view | Show Apps on frosted glass without workspaces, like macOS 27 |
| Effects | Magic lamp when minimizing, glass blur for Macify's window |
| Icons | WhiteSur icon set; Macify creates a macOS-shaped icon for any app that lacks one |
| Cursor & fonts | WhiteSur cursor, San Francisco fonts (SF Pro, SF Mono) |
| Wallpapers | Eight original 4K wallpapers, each with a light and a dark version; your folder's subfolders become sections; your own photos. The **Wallpaper** tile changes it (and the login screen) without reinstalling |
| One look | Accent color, dock glass and menu bar text follow the wallpaper and the appearance; Dark Style in Control Center switches everything. From a terminal: `macify look --appearance dark` or `macify look --wallpaper ~/Pictures/photo.jpg --login` |
| Displays | Super+P (Mirror, Join Displays, External Only, Built-in Only) as a glass panel; the dock rebuilds itself after any display change |
| Colors | Accent color taken from your wallpaper |
| Apps | Traffic-light buttons in apt, Flatpak and snap GTK apps (also ones installed later), VS Code and Firefox |
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
sudo /usr/lib/macify/macify/data/root/macify-root.sh revert
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
│   ├── apps.py         VS Code, Firefox and Flatpak title bars
│   ├── snaps.py        WhiteSur inside snap apps (hard links, no extra space)
│   ├── wallpapers.py   wallpaper catalog and cached thumbnails
│   ├── status_icons.py macOS-style battery, Wi‑Fi and Control Center icons
│   ├── boot.py         boot (Plymouth) and login (GDM) screens
│   ├── fonts.py        San Francisco fonts
│   ├── deps.py         system packages
│   ├── launcher.py     app menu entry and icon
│   ├── uninstall.py    clean removal
│   ├── assets.py, colors.py, info.py, i18n.py
│   └── data/           app icon and style, wallpapers, menubar extension, boot theme, root helper
├── tests/              unit tests; tests/shell runs a hidden GNOME Shell on several monitor layouts
├── scripts/            build.sh (.pyz), build_deb.sh (.deb), make_wallpapers.py, demo/ (video)
└── docs/               website, guide and screenshots
```

## Development

```bash
python3 -m unittest discover -s tests -v   # tests (nothing is changed on the system)
MACIFY_SHELL_TESTS=1 python3 -m unittest tests.test_shell   # real GNOME Shell, 7 monitor layouts
python3 -m macify install --dry-run        # see every change without applying it
./scripts/build.sh                         # dist/macify.pyz
./scripts/build_deb.sh                     # dist/macify_<version>_all.deb
```

## Credits and licenses

- WhiteSur GTK theme, icons and cursors by vinceliuice — GPL-3.0, downloaded from GitHub at install time.
- Extensions downloaded from extensions.gnome.org: User Themes, Blur my Shell, Just Perfection, Dash2Dock Animated, Compiz alike magic lamp effect — each under its own license.
- San Francisco fonts are Apple's and are never bundled: Macify uses your own copy or downloads them from Apple's developer site.
- macOS is a trademark of Apple Inc. Macify is not affiliated with Apple or Canonical.
