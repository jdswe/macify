"""Quita los ganchos de Claude Code que dejaron Macify 0.21 y 0.22.

Esas versiones podían añadir `macify agent-hook` a ~/.claude/settings.json. La función se
retiró en 0.23: si los ganchos se quedaran, Claude Code llamaría a un comando que ya no
existe. Sólo se quitan esos ganchos; todo lo demás del archivo queda igual y antes se guarda
una copia (settings.json.macify-backup).
"""

import json
import shutil
from pathlib import Path

from .i18n import _

SETTINGS = Path.home() / ".claude" / "settings.json"
MARK = "macify agent-hook"


def _ours(group) -> bool:
    return isinstance(group, dict) and any(
        isinstance(hook, dict) and MARK in str(hook.get("command", "")) for hook in group.get("hooks", []))


def remove(dry_run: bool, log, settings: Path | None = None) -> bool:
    """Devuelve True si había ganchos de Macify (y, sin dry_run, los quita)."""
    path = settings or SETTINGS
    try:
        data = json.loads(path.read_text() or "{}")
    except (OSError, ValueError):
        return False
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict) or not any(
            _ours(group) for groups in hooks.values() if isinstance(groups, list) for group in groups):
        return False
    log(_("Removing Macify's old Claude Code hooks ({path})").format(path=path))
    if dry_run:
        return True
    for event in list(hooks):
        if not isinstance(hooks[event], list):
            continue
        kept = [group for group in hooks[event] if not _ours(group)]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    if not hooks:
        del data["hooks"]
    shutil.copy2(path, path.with_name("settings.json.macify-backup"))
    tmp = path.with_name("settings.json.macify-tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return True
