"""Claude Code in the menu bar island: Allow / Deny and "finished" without switching windows.

Claude Code runs `macify agent-hook <event>` as a hook (see claude_hooks.py):
- `permission` (PermissionRequest): sends the request to Macify's island and waits for Allow or
  Deny. If you are looking at the terminal where Claude Code runs, if Macify is not running, or
  if nobody answers in time, it returns nothing and Claude Code asks in the terminal as always.
- `stop` (Stop) and `notify` (Notification): shows that Claude finished or needs you, unless you
  are already looking at its terminal.
Nothing leaves the computer: everything goes over the local session bus to GNOME Shell.
"""

import json
import os
import sys
from pathlib import Path

BUS_NAME = "org.gnome.Shell"
PATH = "/dev/macify/Agents"
IFACE = "dev.macify.Agents"
ANSWER_SECONDS = 45            # then Claude Code's own prompt takes over
MAX_TEXT = 4000
# Notification types worth a bubble; permission_prompt is covered by PermissionRequest.
NOTIFY_TYPES = {"idle_prompt", "elicitation_dialog", "elicitation_url_dialog", "agent_needs_input",
                "agent_completed", "quota_auto_resume_stale", "quota_auto_resume_disabled"}


def ancestors(pid: int | None = None) -> list[int]:
    """This process and its parents: the terminal window running Claude Code is one of them."""
    pids, pid = [], pid or os.getpid()
    while pid > 1 and len(pids) < 64:
        pids.append(pid)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
            pid = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return pids


def _clip(text: str, limit: int = MAX_TEXT) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe(tool: str, tool_input: dict) -> tuple[str, str]:
    """A short line for the island and the detail for the card (the exact command or file)."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if tool in ("Bash", "Monitor"):
        command = tool_input.get("command", "")
        first = command.splitlines()[0] if command else ""
        return tool_input.get("description") or first or tool, command
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit", "Read"):
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return f"{tool} {Path(path).name}" if path else tool, path
    if tool == "WebFetch":
        return f"Fetch {tool_input.get('url', '')}", tool_input.get("url", "")
    if tool == "WebSearch":
        return f"Search “{tool_input.get('query', '')}”", tool_input.get("query", "")
    detail = json.dumps(tool_input, indent=2, ensure_ascii=False) if tool_input else ""
    return tool, detail


def request(data: dict) -> dict:
    tool = data.get("tool_name", "")
    summary, detail = describe(tool, data.get("tool_input") or {})
    return {
        "agent": "Claude Code",
        "project": Path(data.get("cwd") or "").name,
        "tool": tool,
        "summary": _clip(summary, 200),
        "detail": _clip(detail),
        "canAlways": bool(data.get("permission_suggestions")),
    }


def decision(answer: str, data: dict) -> dict | None:
    """Claude Code's PermissionRequest output for the answer given in the island."""
    if answer == "allow":
        result = {"behavior": "allow"}
    elif answer == "always":
        result = {"behavior": "allow", "updatedPermissions": data.get("permission_suggestions") or []}
    elif answer == "deny":
        result = {"behavior": "deny", "message": "The user denied this from the menu bar."}
    else:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": result}}


def _call(method: str, args, reply: str, seconds: int):
    from gi.repository import Gio, GLib

    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    variant = GLib.Variant(f"({''.join(a for a, _ in args)})", tuple(v for _, v in args))
    result = bus.call_sync(BUS_NAME, PATH, IFACE, method, variant, GLib.VariantType(reply),
                           Gio.DBusCallFlags.NO_AUTO_START, seconds * 1000, None)
    return result.unpack()


def run(event: str, stdin=sys.stdin, stdout=sys.stdout) -> int:
    try:
        data = json.load(stdin)
    except (ValueError, OSError):
        return 0
    pids = ancestors()
    try:
        if event == "permission":
            payload = json.dumps(request(data), ensure_ascii=False)
            (answer,) = _call("Ask", [("s", payload), ("au", pids), ("u", ANSWER_SECONDS)], "(s)",
                              ANSWER_SECONDS + 5)
            output = decision(answer, data)
            if output:
                json.dump(output, stdout)
        elif event in ("stop", "notify"):
            if event == "notify" and data.get("notification_type") not in NOTIFY_TYPES:
                return 0
            if event == "stop" and data.get("stop_hook_active"):
                return 0
            state = "done" if event == "stop" or data.get("notification_type") == "agent_completed" else "waiting"
            text = data.get("last_assistant_message") if event == "stop" else data.get("message")
            payload = json.dumps({"agent": "Claude Code", "project": Path(data.get("cwd") or "").name,
                                  "state": state, "text": _clip(text or ("Finished" if state == "done" else
                                                                         "Needs your attention"), 600)},
                                 ensure_ascii=False)
            _call("Tell", [("s", payload), ("au", pids)], "()", 5)
    except Exception:       # Macify not running, old version, timeout: Claude Code carries on as usual
        return 0
    return 0
