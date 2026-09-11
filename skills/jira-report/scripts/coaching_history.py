#!/usr/bin/env python3
"""Historique des synthèses coach — indépendant de data.json.

data.json est réécrit en entier à chaque fetch_jira.py, donc tout `coaching`
qui y vit est perdu au refresh suivant : impossible d'en tirer un `delta`
(voir COACH_PROMPT.md, étape 3). Ce script conserve les synthèses archivées
dans un fichier séparé (projects/<clé>/output/coaching_history.json), jamais
touché par fetch_jira.py.

Usage:
    python scripts/coaching_history.py archive <clé>   # archive le coaching courant de data.json
    python scripts/coaching_history.py last <clé>       # affiche la dernière synthèse archivée
    python scripts/coaching_history.py list <clé>        # liste les dates archivées

`archive` est idempotent (ne réarchive pas un coaching identique au dernier
déjà présent) et purge au-delà de MAX_ENTRIES. Un fichier d'historique
corrompu ou illisible ne fait jamais échouer une commande — repart d'un
historique vide plutôt que de planter (voir _read_history).
"""
import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from workspace import output_dir, DataDirNotConfigured

MAX_ENTRIES = 12

# Sortie/erreurs toujours en UTF-8 quel que soit le codepage de la console.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def die(msg):
    print(f"ERREUR: {msg}", file=sys.stderr)
    sys.exit(1)


def _history_path(key) -> Path:
    try:
        return output_dir(key) / "coaching_history.json"
    except DataDirNotConfigured as e:
        die(str(e))


def _read_history(path: Path) -> list:
    """Tolérant : un fichier absent, vide, corrompu ou mal formé redonne un
    historique vide plutôt que de faire échouer la commande appelante."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, list) else []


def _write_history(path: Path, entries: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False,
        dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp",
    ) as tmp:
        json.dump({"entries": entries}, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def cmd_archive(key):
    data_path = output_dir(key) / "data.json"
    if not data_path.exists():
        die(f"fichier de données absent : {data_path}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    coaching = data.get("coaching")
    if not coaching:
        print(f"[{key}] aucune synthèse coach dans data.json — rien à archiver.")
        return

    history_path = _history_path(key)
    entries = _read_history(history_path)

    if entries and entries[-1].get("coaching") == coaching:
        print(f"[{key}] synthèse identique à la dernière archivée "
              f"({entries[-1].get('archived_at', '?')}) — pas de doublon.")
        return

    entries.append({
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "generated_at": data.get("generated_at"),
        "coaching": coaching,
    })
    entries = entries[-MAX_ENTRIES:]
    _write_history(history_path, entries)
    print(f"[{key}] synthèse archivée dans {history_path} ({len(entries)} entrée(s)).")


def cmd_last(key):
    history_path = _history_path(key)
    entries = _read_history(history_path)
    if not entries:
        print(f"[{key}] aucun historique de synthèse — pas de delta possible pour ce refresh.")
        return

    last = entries[-1]
    print(json.dumps({
        "archived_at": last.get("archived_at"),
        "generated_at": last.get("generated_at"),
        "coaching": last.get("coaching"),
    }, ensure_ascii=False, indent=2))


def cmd_list(key):
    history_path = _history_path(key)
    entries = _read_history(history_path)
    if not entries:
        print(f"[{key}] aucun historique de synthèse.")
        return

    print(f"[{key}] {len(entries)} synthèse(s) archivée(s) (plus récente en dernier) :")
    for e in entries:
        print(f"  - archivée le {e.get('archived_at', '?')}  "
              f"(données du {e.get('generated_at', '?')})")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["archive", "last", "list"])
    ap.add_argument("project_key")
    args = ap.parse_args()

    {"archive": cmd_archive, "last": cmd_last, "list": cmd_list}[args.command](args.project_key)


if __name__ == "__main__":
    main()
