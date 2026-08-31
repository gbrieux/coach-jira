#!/usr/bin/env python3
"""Injecte un objet ``coaching`` UTF-8 dans un JSON de données JIRA.

Usage:
    python scripts/set_coaching.py NOS_R1 chemin/vers/NOS_R1_coaching.json

Le fichier d'entrée doit contenir soit l'objet coaching directement, soit un
objet racine avec une clé ``coaching``. Cette étape évite les pertes d'accents
causées par ``$OutputEncoding=us-ascii`` dans Windows PowerShell 5.1.
"""
import argparse
import json
import re
import tempfile
from pathlib import Path

from workspace import output_dir, DataDirNotConfigured


def _iter_text_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _iter_text_values(key)
            yield from _iter_text_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_text_values(item)


def validate(coaching):
    if not isinstance(coaching, dict):
        raise ValueError("le coaching doit être un objet JSON")

    texts = list(_iter_text_values(coaching))
    replacement_chars = sum(text.count("\ufffd") for text in texts)
    question_marks = sum(text.count("?") for text in texts)
    embedded_question_mark = any(
        re.search(r"[^\W\d_]\?[^\W\d_]", text, re.UNICODE) for text in texts
    )
    if replacement_chars or embedded_question_mark or question_marks > 3:
        raise ValueError(
            "le coaching contient des '?' suspects ou des caractères de remplacement ; "
            "vérifier que le fichier source est réellement encodé en UTF-8"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_key")
    parser.add_argument("coaching_json", type=Path)
    args = parser.parse_args()

    try:
        data_path = output_dir(args.project_key) / "data.json"
    except DataDirNotConfigured as e:
        parser.error(str(e))
    if not data_path.exists():
        parser.error(f"fichier de données absent : {data_path}")
    if not args.coaching_json.exists():
        parser.error(f"fichier de coaching absent : {args.coaching_json}")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    incoming = json.loads(args.coaching_json.read_text(encoding="utf-8-sig"))
    coaching = incoming.get("coaching") if isinstance(incoming, dict) and "coaching" in incoming else incoming
    validate(coaching)
    data["coaching"] = coaching

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False,
        dir=data_path.parent, prefix=f".{data_path.stem}.", suffix=".tmp",
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(data_path)
    print(f"[{args.project_key}] coaching UTF-8 injecté dans {data_path}")


if __name__ == "__main__":
    main()
