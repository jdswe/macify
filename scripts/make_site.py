#!/usr/bin/env python3
"""Páginas del sitio web hechas a partir de los documentos del proyecto.

La guía, la política de privacidad, la licencia y los avisos de terceros se leen en el propio
sitio, con su mismo aspecto, en vez de mandar a GitHub. Este guion las escribe en docs/ a partir
de docs/GUIDE.md, PRIVACY.md, LICENSE y NOTICE, y pone el mismo pie de página en la portada.

Uso: python3 scripts/make_site.py     (después de cambiar cualquiera de esos documentos)
"""

import html
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
GITHUB = "https://github.com/jdswe/macify"

GITHUB_MARK = ('<svg class="gl" viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M8 0C3.58 0 0 '
               '3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-'
               '.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66'
               '.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 '
               '.67-.21 2.2.82a7.6 7.6 0 0 1 4 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 '
               '2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 '
               '8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>')


def footer(home: str) -> str:
    """El pie de página. «home» es "" en la portada e "index.html" en las demás páginas."""
    return f'''<footer>
  <div class="wrap">
    <div class="foot-grid">
      <div class="foot-brand">
        <a class="brand" href="{home or '#'}"><img src="icon.svg" alt="">Macify</a>
        <p>A one-click macOS look for Ubuntu, from the boot screen to the dock. Free software, fully reversible.</p>
        <a class="foot-source" href="{GITHUB}">{GITHUB_MARK}Source on GitHub</a>
      </div>
      <div class="foot-col">
        <h4>Product</h4>
        <a href="{home}#features">Features</a>
        <a href="{home}#install">Install</a>
        <a href="{home}#screenshots">Screenshots</a>
        <a href="{home}#releases">Releases</a>
      </div>
      <div class="foot-col">
        <h4>Help</h4>
        <a href="guide.html">Guide</a>
        <a href="{home}#faq">Questions</a>
        <a href="{GITHUB}/issues/new">Report a problem</a>
      </div>
      <div class="foot-col">
        <h4>Legal</h4>
        <a href="privacy.html">Privacy &amp; cookies</a>
        <a href="license.html">License (GPL v3)</a>
        <a href="notices.html">Third-party notices</a>
      </div>
    </div>
    <div class="foot-bottom">
      <span>© 2026 Jose David Carranza Angarita. Macify is free software under the GNU GPL v3.</span>
      <span>No cookies · No tracking · No account</span>
    </div>
    <p class="foot-note">Built on <a href="https://github.com/vinceliuice/WhiteSur-gtk-theme">WhiteSur</a> and
      <a href="https://extensions.gnome.org">GNOME extensions</a>, each under its own license. macOS is a trademark of
      Apple Inc. Macify is an independent project, not affiliated with Apple or Canonical.</p>
  </div>
</footer>'''


# ----- Markdown (sólo lo que usan los documentos del proyecto) -----

def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)
    return re.sub(r'(?<![">])(https?://[^\s<)]+[^\s<).,;])', r'<a href="\1">\1</a>', text)


def markdown(source: str) -> str:
    out, paragraph, items = [], [], []
    lines = source.splitlines()

    def flush():
        if paragraph:
            out.append(f"<p>{inline(' '.join(paragraph))}</p>")
            paragraph.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(item)}</li>" for item in items) + "</ul>")
            items.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            flush()
            block = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index])
                index += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(block), quote=False)}</code></pre>")
        elif line.startswith("|"):
            flush()
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            head, body = rows[0], rows[2:]
            out.append('<div class="table"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>" for row in body)
                       + "</tbody></table></div>")
            continue
        elif match := re.match(r"(#{1,3}) (.+)", line):
            flush()
            level = len(match.group(1))
            out.append(f"<h{level}>{inline(match.group(2))}</h{level}>")
        elif line.startswith("- "):
            if paragraph:
                flush()
            items.append(line[2:])
        elif line.startswith("  ") and items:
            items[-1] += " " + line.strip()
        elif not line.strip():
            flush()
        else:
            if items:
                flush()
            paragraph.append(line.strip())
        index += 1
    flush()
    return "\n".join(out)


def plain(source: str) -> str:
    """Texto legal tal cual, con su propio formato de líneas."""
    return f'<pre class="legal">{html.escape(source, quote=False)}</pre>'


def notices(source: str) -> str:
    title, _, rest = source.partition("\n")
    return markdown(f"# {title.split('—')[-1].strip().capitalize()}\n{rest}")


# ----- páginas -----

PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>{title} — Macify</title>
<meta name="description" content="{description}">
<link rel="icon" href="icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="site.css">
</head>
<body>
<nav>
  <div class="wrap">
    <a class="brand" href="index.html"><img src="icon.svg" alt="">Macify</a>
    <div class="links">
      <a href="index.html#features">Features</a>
      <a href="index.html#install">Install</a>
      <a href="guide.html"{guide}>Guide</a>
      <a href="privacy.html"{privacy}>Privacy</a>
      <a href="index.html#releases" class="optional">Releases</a>
    </div>
  </div>
</nav>
<main class="wrap doc">
<a class="back" href="index.html">← Macify</a>
{body}
</main>
{footer}
</body>
</html>
'''

PAGES = [
    ("guide", "Guide", "What Macify changes, how to install, check, restore and uninstall it.",
     lambda: markdown((DOCS / "GUIDE.md").read_text().replace("# Macify\n", "# Guide\n", 1))),
    ("privacy", "Privacy & cookies", "Macify collects nothing; its website uses no cookies.",
     lambda: markdown((REPO / "PRIVACY.md").read_text().replace(" — Macify\n", "\n", 1))),
    ("license", "License", "Macify is free software under the GNU General Public License, version 3.",
     lambda: "<h1>License</h1>\n<p>Macify is free software under the GNU General Public License, version 3. "
             "You may use, study, share and change it under these terms.</p>\n" + plain((REPO / "LICENSE").read_text())),
    ("notices", "Third-party notices", "Fonts, themes and extensions Macify uses, each under its own license.",
     lambda: notices((REPO / "NOTICE").read_text())),
]


def build() -> list[Path]:
    written = []
    for name, title, description, body in PAGES:
        current = {key: ' aria-current="page"' if key == name else "" for key in ("guide", "privacy")}
        page = PAGE.format(title=html.escape(title), description=html.escape(description), body=body(),
                           footer=footer("index.html"), **current)
        target = DOCS / f"{name}.html"
        target.write_text(page)
        written.append(target)
    index = DOCS / "index.html"
    text = index.read_text()
    start, end = text.index("<footer>"), text.index("</footer>") + len("</footer>")
    index.write_text(text[:start] + footer("") + text[end:])
    return written + [index]


if __name__ == "__main__":
    for path in build():
        print(path.relative_to(REPO))
