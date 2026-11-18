"""Optional: connect Claude Code to the menu bar island (Allow / Deny, finished, needs you).

Adds Macify's hooks to ~/.claude/settings.json and removes exactly those again. Every other
setting and hook in that file is kept as it was; a copy of the file is saved first.
"""

import json
import shutil
from pathlib import Path

from .i18n import _

SETTINGS = Path.home() / ".claude" / "settings.json"
COMMAND = "/usr/bin/macify agent-hook"
MARK = "macify agent-hook"
# Claude Code waits for the permission hook; Macify answers within 45 s and then steps aside.
HOOKS = {
    "PermissionRequest": {"matcher": "*", "hooks": [{"type": "command", "command": f"{COMMAND} permission",
                                                      "timeout": 60}]},
    "Notification": {"matcher": "", "hooks": [{"type": "command", "command": f"{COMMAND} notify",
                                                "timeout": 10, "async": True}]},
    "Stop": {"hooks": [{"type": "command", "command": f"{COMMAND} stop", "timeout": 10, "async": True}]},
}


def _load() -> dict:
    if not SETTINGS.is_file():
        return {}
    data = json.loads(SETTINGS.read_text() or "{}")
    if not isinstance(data, dict):
        raise ValueError(_("{path} is not a settings object.").format(path=SETTINGS))
    return data


def _ours(group: dict) -> bool:
    return any(MARK in str(hook.get("command", "")) for hook in group.get("hooks", []))


def _without_ours(data: dict) -> dict:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return data
    for event in list(hooks):
        groups = [group for group in hooks[event] if not (isinstance(group, dict) and _ours(group))]
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if not hooks:
        del data["hooks"]
    return data


def installed() -> bool:
    try:
        hooks = _load().get("hooks", {})
    except (ValueError, OSError):
        return False
    return any(_ours(group) for groups in hooks.values() if isinstance(groups, list)
               for group in groups if isinstance(group, dict))


def _save(data: dict) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS.is_file():
        shutil.copy2(SETTINGS, SETTINGS.with_name("settings.json.macify-backup"))
    tmp = SETTINGS.with_name("settings.json.macify-tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(SETTINGS)


def install(dry_run: bool, log) -> None:
    log(_("Connect Claude Code to the menu bar ({path})").format(path=SETTINGS))
    if dry_run:
        return
    data = _without_ours(_load())
    hooks = data.setdefault("hooks", {})
    for event, group in HOOKS.items():
        hooks.setdefault(event, []).append(json.loads(json.dumps(group)))
    _save(data)
    log(_("Claude Code asks in the menu bar from its next session."))


def remove(dry_run: bool, log) -> None:
    if not installed():
        return
    log(_("Disconnect Claude Code from the menu bar ({path})").format(path=SETTINGS))
    if dry_run:
        return
    try:
        _save(_without_ours(_load()))
    except (ValueError, OSError) as error:
        log(str(error))
