# Macify release notes

## 0.17.1

- The dock stops animating as soon as it is still. Dash2Dock Animated redraws both docks about 62 times a second for three quarters of a second after every focus change or window restack, even while hidden; with many apps open that happens constantly. Macify now ends that animation after about 90 ms without changes. Measured in an isolated GNOME Shell 50 with two displays and windows switching 2.4 times a second: 125 → 33 dock updates per second and 176–198 → 52–58 ms of shell main-thread time per second. Hover magnification, bounces, drags and slide in/out are unchanged.

## 0.17.0

- Generated icons no longer come out tiny or blurry: Macify uses the largest version of an app's artwork that sits next to the one its launcher names (Spotify's 512 px image instead of the 128 px one), trims empty margins and scales the drawing to fill the macOS shape. Icons made by earlier versions are redrawn once.
- Website: a Privacy & cookies section (no cookies, no tracking, and which GitHub services the page contacts) and a new footer with product, help and legal links. The privacy policy now states the GitHub Pages and GitHub API requests.
- Includes everything prepared in 0.16.1–0.16.5 below, which was never published separately.

## 0.16.5 — included in 0.17.0

- Match GitHub Copilot's AppImage window to its existing launcher so the dock uses the correct app logo instead of a generic window icon.
- Preserve the user's launcher icon and command; only add `StartupWMClass=github` when the launcher has no window-class association.

## 0.16.4 — included in 0.17.0

- Generate app-specific Macify icons from each app's original artwork rather than guessing from ambiguous theme aliases.
- Fix Visual Studio Code resolving to a text-editor icon and Kiro resolving to the VS Code logo; use Kiro's installed original icon and VS Code's launcher artwork.
- Resolve each app's icon from its own launcher or package assets where possible; use explicit Visual Studio Code, Kiro and GitHub Desktop identity mappings across installed apps.
- If an app's original artwork is unavailable, leave the launcher's icon unchanged rather than substitute a generic or lookalike logo.

## 0.16.3 — included in 0.17.0

- Replace the install-time Apple font download with bundled Inter and JetBrains Mono fonts, including their license notices (SIL Open Font License 1.1 and Apache-2.0).
- Install and check these fonts locally without network access; update GNOME, Ptyxis, the app UI and dock badges to use them.
- Remove legacy Macify-managed SF Pro/SF Mono font files during font installation and uninstall.

## 0.16.2 — included in 0.17.0

- Reduce dock hover and preview pointer checks from 8.3/6.7 Hz to 5 Hz while the pointer is over the dock or preview. Checks stop when the interaction ends.
- Reduce Live Activities audio-bar refreshes from 8 Hz to about 6 Hz while media is playing; refreshes still stop when the bars are hidden, paused, locked or in fullscreen.
- Remove an unsupported fixed idle CPU estimate from the website FAQ; resource use varies by hardware, extensions and workload. No GPU or whole-desktop performance reduction is claimed.

## 0.16.1 — included in 0.17.0

- Stop adding Flatpak filesystem permissions to expose the host theme. A Flatpak GTK app uses the system theme only if its runtime already makes it available; other apps are left alone.
- Older installations did not save the original Flatpak permissions. Their legacy overrides are left untouched on restore rather than risk removing permissions that predated Macify.
- Clarify that GTK apps can use the provided theme while apps built with other toolkits keep their own appearance.
- Keep the Ubuntu/GNOME Show Apps icon inherited and unchanged while styling the app grid.

Background: [Flatpak sandbox permissions](https://docs.flatpak.org/en/latest/sandbox-permissions.html) and [Flatpak override storage and precedence](https://docs.flatpak.org/en/latest/flatpak-command-reference.html#flatpak-override).
