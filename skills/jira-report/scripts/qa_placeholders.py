#!/usr/bin/env python3
"""QA : vérifie qu'aucun placeholder `{{...}}` ne subsiste dans un PPT généré.

Usage:
    python scripts/qa_placeholders.py <clé>                 # dernier PPT du projet
    python scripts/qa_placeholders.py <fichier.pptx> [...]  # fichier(s) explicite(s)

Lit chaque zone de texte et chaque cellule de tableau via python-pptx (pas
besoin de markitdown). Sortie 0 si aucun placeholder, 1 sinon.
"""
from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation

from util import PLACEHOLDER_RE, die
from workspace import latest_report, DataDirNotConfigured


def remaining_placeholders(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for slide_number, slide in enumerate(Presentation(path).slides, 1):
        for shape in slide.shapes:
            if shape.has_text_frame:
                found.extend((slide_number, m) for m in PLACEHOLDER_RE.findall(shape.text_frame.text))
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        found.extend((slide_number, m) for m in PLACEHOLDER_RE.findall(cell.text))
    return found


def _resolve(arg: str) -> Path:
    path = Path(arg)
    if path.suffix.lower() == ".pptx":
        if not path.exists():
            die(f"fichier introuvable : {path}")
        return path
    try:
        latest = latest_report(arg)
    except DataDirNotConfigured as e:
        die(str(e))
    if latest is None:
        die(f"aucun PPT généré pour le projet '{arg}' — lancer build_ppt.py d'abord.")
    return latest


def main():
    if len(sys.argv) < 2:
        die(__doc__)
    failed = False
    for arg in sys.argv[1:]:
        path = _resolve(arg)
        found = remaining_placeholders(path)
        print(f"{'PLACEHOLDERS RESTANTS' if found else 'OK'} {path} {found if found else ''}".rstrip())
        failed |= bool(found)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
