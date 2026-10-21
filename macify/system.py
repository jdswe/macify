"""Lectura, escritura y restauración de ajustes de GNOME con gsettings."""

import json
import subprocess
from pathlib import Path

from .i18n import _

BACKUP_FILE = Path.home() / ".config" / "macify" / "backup.json"
EXTENSIONS_DIR = Path.home() / ".local" / "share" / "gnome-shell" / "extensions"


def _extension_schema_dir(schema: str) -> Path | None:
    """Carpeta schemas/ de la extensión que define este esquema, si la hay."""
    if not schema.startswith("org.gnome.shell.extensions.") or not EXTENSIONS_DIR.is_dir():
        return None
    needle = f'id="{schema}"'
    for xml in EXTENSIONS_DIR.glob("*/schemas/*.gschema.xml"):
        if needle in xml.read_text(errors="ignore"):
            return xml.parent
    return None


def _gsettings(*args: str) -> list[str]:
    """Prefija --schemadir cuando el esquema vive dentro de una extensión."""
    folder = _extension_schema_dir(args[1]) if len(args) > 1 else None
    return ["gsettings", *(["--schemadir", str(folder)] if folder else []), *args]


def has_schema(schema: str) -> bool:
    return subprocess.run(_gsettings("list-keys", schema), capture_output=True).returncode == 0


def has_key(schema: str, key: str) -> bool:
    result = subprocess.run(_gsettings("list-keys", schema), capture_output=True, text=True)
    return result.returncode == 0 and key in result.stdout.split()


def read(schema: str, key: str) -> str:
    result = subprocess.run(_gsettings("get", schema, key), capture_output=True, text=True)
    return result.stdout.strip()


def write(schema: str, key: str, value: str, dry_run: bool, log) -> None:
    log(f"gsettings set {schema} {key} {value}")
    if not dry_run:
        subprocess.run(_gsettings("set", schema, key, value), check=True)


def load_backup() -> dict:
    if BACKUP_FILE.exists():
        return json.loads(BACKUP_FILE.read_text())
    return {}


def save_backup(data: dict) -> None:
    BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
    BACKUP_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def apply_settings(settings: dict, dry_run: bool, log) -> None:
    """Guarda el valor original de cada clave la primera vez y aplica el nuevo."""
    backup = load_backup()
    for schema, keys in settings.items():
        if not has_schema(schema):
            log(_("Skipped: schema {schema} does not exist on this system.").format(schema=schema))
            continue
        for key, value in keys.items():
            if not has_key(schema, key):
                log(_("Skipped: key {schema}/{key} does not exist.").format(schema=schema, key=key))
                continue
            backup.setdefault(schema, {}).setdefault(key, read(schema, key))
            write(schema, key, value, dry_run, log)
    if not dry_run:
        save_backup(backup)


def restore(dry_run: bool, log) -> None:
    """Devuelve cada clave a su valor original y borra la copia de seguridad."""
    backup = load_backup()
    if not backup:
        log(_("No backup: nothing to restore."))
        return
    for schema, keys in backup.items():
        for key, value in keys.items():
            write(schema, key, value, dry_run, log)
    if not dry_run:
        BACKUP_FILE.unlink(missing_ok=True)
    log(_("Restore dry run finished.") if dry_run else _("Restore complete."))
