#!/usr/bin/env python3
"""Ajoute un bloc de contexte horodaté en fin de contexte/<team_id>.md.

Usage:
    python scripts/append_context.py NOS bloc_utf8.md

``bloc_utf8.md`` contient le bloc déjà formaté et horodaté par l'appelant
(ex. ``## 2026-08-06 — Priorisation NOS_R2\n\nContenu...``) — ce script ne
devine ni ne génère de date, il se contente d'ajouter tel quel.

Toujours en fin de fichier (append strict, jamais de réécriture de
l'existant). Si contexte/<team_id>.md n'existe pas encore, il est créé avec
ce premier bloc. AUCUNE confirmation n'est demandée ici : le garde-fou
« montrer le texte et attendre confirmation » est une règle de comportement
respectée en amont par l'appelant (voir CLAUDE.md / COACH_PROMPT.md), pas
quelque chose que ce script peut vérifier.
"""
import argparse
import re
import sys
import tempfile
from pathlib import Path

from workspace import data_root, DataDirNotConfigured

try:
    CONTEXTE_DIR = data_root() / "contexte"
except DataDirNotConfigured as e:
    print(f"ERREUR: {e}", file=sys.stderr)
    sys.exit(1)

# Sortie/erreurs toujours en UTF-8 quel que soit le codepage de la console.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def die(msg):
    print(f"ERREUR: {msg}", file=sys.stderr)
    sys.exit(1)


def validate_utf8(text):
    """Même heuristique anti-corruption que set_coaching.py : des '?' ou
    caractères de remplacement suspects trahissent un encodage cassé en
    amont (ex. $OutputEncoding=us-ascii sous PowerShell)."""
    replacement_chars = text.count("�")
    embedded_question_mark = bool(re.search(r"[^\W\d_]\?[^\W\d_]", text, re.UNICODE))
    question_marks = text.count("?")
    if replacement_chars or embedded_question_mark or question_marks > 3:
        die("le bloc contient des '?' suspects ou des caractères de remplacement ; "
            "vérifier que le fichier source est réellement encodé en UTF-8.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("team_id")
    ap.add_argument("block_file", type=Path)
    args = ap.parse_args()

    if not args.block_file.exists():
        die(f"fichier de bloc absent : {args.block_file}")

    block = args.block_file.read_text(encoding="utf-8-sig").strip()
    if not block:
        die("le bloc de contexte est vide.")
    validate_utf8(block)

    CONTEXTE_DIR.mkdir(parents=True, exist_ok=True)
    team_path = CONTEXTE_DIR / f"{args.team_id}.md"

    if team_path.exists():
        existing = team_path.read_text(encoding="utf-8").rstrip("\n")
        new_content = f"{existing}\n\n{block}\n"
        created = False
    else:
        new_content = f"{block}\n"
        created = True

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False,
        dir=CONTEXTE_DIR, prefix=f".{args.team_id}.", suffix=".tmp",
    ) as tmp:
        tmp.write(new_content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(team_path)

    verb = "créé" if created else "mis à jour (ajout en fin de fichier)"
    print(f"[{args.team_id}] {team_path} {verb}.")


if __name__ == "__main__":
    main()
