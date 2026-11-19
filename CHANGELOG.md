# Macify release notes

## 0.24.0

- **Choose your accent color.** The wallpaper page has a row of color circles, like Appearance on a Mac: blue, purple, pink, red, orange, yellow, green, teal and graphite. The first circle, **Automatic**, keeps taking the color from your wallpaper, as before. The color you pick is used for buttons, switches, selections and highlights across GNOME and its apps, and in **Customize** it changes live. Doctor and updates keep your choice.

## 0.23.0

- **Removed: coding agents and Claude Code approvals in the island.** The menu bar island no longer shows notifications from Claude Code, Codex, ChatGPT, Copilot or Cursor, and the **Claude Code in the menu bar** option, `macify claude` and `macify agent-hook` are gone. If you had connected it, updating removes Macify's hooks from `~/.claude/settings.json` and leaves every other setting as it was. Notifications from those apps show like any other app's. The island keeps music, the volume of just the playing app, charging, connection and Dictado.
- Fixed: the island's stylesheet no longer has a stray rule left over from the agent cards.
- The demo video shows the clipboard history, per-app volume and Dictado in the island.

## 0.22.0

- **Every app shows its own logo in the dock.** GNOME links a window to its app only when the window's name matches the app's launcher exactly. Some apps ship a launcher that doesn't match (Kilo says `Kilo`, its window says `kilo`), so the dock showed a generic icon even though the right one was installed. Now, when a window opens without an app, Macify finds its launcher — by the program that runs the window and by its name, and only when exactly one launcher fits — and writes a copy in `~/.local/share/applications` with the right window name. The window that is already open switches to the real icon at once; you don't have to reopen the app. System launchers are never edited, the copy keeps everything else (icon, command, actions), and Uninstall Everything removes it. From a terminal: `macify link-window <window-class> --pid <pid>`.

## 0.21.0

- **Approve Claude Code from the menu bar.** Turn on **Claude Code in the menu bar** on the last setup page (or run `macify claude connect`). When Claude Code asks for permission, the island shows what it wants to do, with the project, the tool and the exact command or file, and **Allow**, **Deny** and, when Claude Code offers to remember the rule, **Always**. Your answer reaches Claude Code at once, so you never have to switch to its terminal. If you are already looking at that terminal, if Macify is not running, or if nobody answers within 45 seconds, Claude Code asks in its terminal as always. The island also tells you when Claude Code finished, with the start of its last message, and when it is waiting for you. Macify adds only its own hooks to `~/.claude/settings.json`, keeps every other setting, saves a backup first, and removes exactly those hooks with `macify claude disconnect` or Uninstall Everything. Everything stays on the computer.
- Fixed: after answering an agent, the island's card could not be opened again until music played.

## 0.20.0

- **Voice dictation, optional.** The last setup page offers **Voice dictation (Dictado)**, off by default. [Dictado](https://jdswe.github.io/dictado/) is a separate open-source app: speak and it types where the cursor is, and it transcribes calls (what you hear and what you say, labelled “Me” and “Others”) and audio or video files. Speech is recognised locally by Whisper; about 350 MB of models download once and no audio leaves the computer. Macify runs Dictado's verified installer (no sudo; it only asks for your password if `ffmpeg` or Python's venv module are missing), the Doctor checks it when you chose it, and Uninstall Everything removes it too (your dictations and transcripts are kept). If Dictado is already installed, the option shows it.
- **Dictado in the island.** While you dictate, the bubble shows a red microphone with bars that follow your voice, then “Writing…” while it turns speech into text; during a transcription it shows **REC** and the elapsed time. A click finishes the dictation or stops the transcription. Macify only listens to Dictado's status: it never touches the audio, and Dictado types the text itself.
- **Read and open agent notifications from the island.** Clicking the island when an agent has news opens a card with each notification in full — who, what happened, how long ago and the whole text — with **Open** and **Dismiss**. Open brings the agent to the front, even for terminal agents whose notification has no action: Macify finds the window running it. If music is playing, Now Playing stays below.
- The island's menu is now opaque, light or dark like the system, so it is readable over any wallpaper (Blur my Shell made it 65 % transparent).
- The island no longer stays hidden when something new appears while it is closing.

## 0.19.0

- **Coding agents in the island.** When Claude Code, Codex/ChatGPT, Copilot, Cursor, Gemini, Aider, Windsurf or OpenCode sends a notification, the island in the menu bar shows it: orange while the agent waits for you (a permission, a question), a green check when it finished, red when it failed. Waiting agents stay until you deal with them; with several, the island says how many are waiting. Clicking the island opens the agent, like clicking its notification. Only the notifications those apps already send are read; agents are recognised by their app name or notification title, never by the text, so an email that mentions Claude is ignored. Nothing leaves the computer.

## 0.18.0

- **No window is see-through any more.** WhiteSur's "normal" style paints window backgrounds, title bars, sidebars and menus at 92–96 % opacity so Blur my Shell can turn them into glass. Windows that nothing blurs — the file picker browsers open, snap notices such as “Refreshing Apps” — showed whatever was behind them, and on some GPUs that small transparency turned into an almost invisible window with floating text. Every near-opaque background in the GTK 3 and GTK 4 theme is now fully opaque; soft tints (hover, selection) and shadows are unchanged. The Doctor detects and repairs this on existing installations; reopen the browser afterwards.
- **The dock no longer freezes when an app opens.** Since 0.17.1 Macify ended the dock animation once it looked still, but the bounce of a launching app moves actors that check did not see, so the animation was cut after about 90 ms and the dock stood still. The dock now keeps animating for the whole bounce and still settles right after it.
- **Per-app volume in Now Playing.** Under the playback controls there is a new slider for the app that is playing (Spotify, the browser with YouTube…): it lowers only that app, while the System slider below still changes everything.
- **Clipboard history, tidier.** It keeps the last 10 copies (4 images at most) instead of 20, shows at most six rows and scrolls the rest, so it never covers the screen. New header with the number of items, file or link icons, a highlighted selection that follows the arrow keys, and a close button in addition to Esc and clicking outside.

## 0.17.2

- File dialogs in web browsers (the “wants to open” window when you upload a file) and windows of some snap apps, such as snap's “Refreshing Apps” notice, no longer come out transparent with white, unreadable text. WhiteSur's GTK 4 style used colors that only libadwaita apps define; every other GTK 4 window got no background at all. Those colors now fall back to WhiteSur's own, and libadwaita apps keep exactly the colors they had (checked pixel by pixel). Nothing is forced on apps that set their own style. The Doctor detects and repairs this on existing installations.
- Snap apps now also receive the GTK 4 part of the WhiteSur theme, not only the GTK 3 part.

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
