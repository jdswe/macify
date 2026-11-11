# Privacy and cookies — Macify

**Short version:** Macify runs on your computer. It sends nothing anywhere, has no account, no telemetry and no
analytics, and its website uses no cookies.

## What Macify does with your data

- Macify changes your GNOME desktop settings on your own computer. It opens no network ports, runs no system services
  and loads no kernel modules (see the README).
- The only network access is when you choose to update or install a component. Downloads are checked against the
  SHA-256 fingerprint published by the project before anything runs.
- Macify does not collect, store on a server or share personal data, usage data or crash reports.

## Website (jdswe.github.io/macify)

- No cookies, no local storage used for tracking, no analytics and no advertising.
- No third-party scripts: the page runs only its own code.
- The site is hosted on GitHub Pages and reads the list of releases from GitHub's public API. For those requests
  GitHub receives the usual request data (such as your IP address) and handles it under its own privacy statement;
  the Macify project has no access to it.
- The demo video is hosted with the site.

## Your rights

Because the project keeps no data about you, there is nothing to access, correct or delete. To remove Macify and
its settings, run `macify uninstall`.

## Contact

Questions about this notice: open an issue at https://github.com/jdswe/macify/issues.

*Last updated: 2026-11-11.*
