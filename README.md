<p align="center">
  <img src="docs/icon.svg" width="112" alt="Macify">
</p>

<h1 align="center">Macify</h1>

<p align="center">A one-click macOS look for Ubuntu — from the boot screen to the dock. Fully reversible.</p>

<p align="center"><a href="https://jdswe.github.io/macify/"><b>Website</b></a> · <a href="../../releases/latest"><b>Download</b></a></p>

<p align="center">
  <img src="docs/welcome.png" width="720" alt="Macify welcome screen">
</p>

## Features

- **Boot and login** — the progress bar tracks real startup (“Welcome”) and shutdown (“See you soon”); macOS-style login.
- **Windows** — traffic-light buttons and macOS title bars, light or dark.
- **Menu bar** — transparent, with a system menu and the active app's name.
- **Dock** — floating glass, magnification, bounce and magic-lamp minimize.
- **Icons** — macOS icon set; missing icons are generated in the macOS shape.
- **Wallpaper colors** — the accent color follows your wallpaper.
- **Customize** — change look, wallpaper and dock live, without reinstalling.
- **Doctor** — finds outdated or broken pieces and fixes them.
- **Software Update** — checks GitHub, downloads and installs new versions from inside the app.
- **Clean removal** — restore or uninstall everything in one click.

<p align="center">
  <img src="docs/dock-icons.png" width="720" alt="Dock icons after Macify">
</p>

## Install

```bash
curl -fsSL https://jdswe.github.io/macify/install.sh | bash
```

Or download the `.deb` from [Releases](../../releases/latest) and run `sudo apt install ./macify_*_all.deb`.

Open **Macify**, follow the steps, press **Install** and restart.

Built for Ubuntu with GNOME 45–50. Tested on Ubuntu 26.04.1 (GNOME 50, Wayland).

## Screenshots

| Dock, live preview | Manage |
|---|---|
| ![](docs/dock.png) | ![](docs/manage.png) |
| **Doctor** | **Boot** |
| ![](docs/doctor.png) | ![](docs/boot.png) |

## Command line

```bash
macify install --dry-run   # preview every change
macify doctor --fix        # check for problems and fix them
macify uninstall           # remove everything
```

More in the [guide](docs/GUIDE.md).

## Credits

© 2026 Jose David Carranza Angarita · [GPL-3.0](LICENSE).

Built on [WhiteSur](https://github.com/vinceliuice/WhiteSur-gtk-theme) by vinceliuice and GNOME extensions from [extensions.gnome.org](https://extensions.gnome.org). Apple fonts are never bundled. Not affiliated with Apple or Canonical.
