#!/usr/bin/env python3
"""Rendu visuel des slides PPT en JPEG, via automation PowerPoint (Windows uniquement).

Alternative locale à /mnt/skills/public/pptx/scripts/office/soffice.py +
pdftoppm (indisponibles hors sandbox cloud) : pilote l'application PowerPoint
installée sur le poste pour exporter chaque slide en JPEG, sans dépendance
externe. Nécessite `pywin32` (pip install pywin32) et Microsoft PowerPoint
installés sur le poste.

Usage:
    python scripts/render_slides_windows.py <project_key>

Écrit les images dans projects/<clé>/output/slides/Diapositive1.JPG, etc.
(dossier recréé à chaque appel).
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

from workspace import output_dir, DataDirNotConfigured

PP_SAVE_AS_JPG = 17  # PpSaveAsFileType.ppSaveAsJPG


def render(pptx_path: Path, dest_dir: Path) -> None:
    import win32com.client

    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    app = win32com.client.gencache.EnsureDispatch("PowerPoint.Application")
    app.DisplayAlerts = 0  # ppAlertsNone
    presentation = app.Presentations.Open(str(pptx_path), 0, 0, 0)  # ReadOnly, Untitled, WithWindow = False
    try:
        presentation.SaveAs(str(dest_dir), PP_SAVE_AS_JPG)
    finally:
        presentation.Close()
        app.Quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_key")
    args = parser.parse_args()

    try:
        out = output_dir(args.project_key)
    except DataDirNotConfigured as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        sys.exit(1)

    pptx_path = out / "indicateurs.pptx"
    if not pptx_path.exists():
        print(f"ERREUR: {pptx_path} introuvable — lancer build_ppt.py d'abord.", file=sys.stderr)
        sys.exit(1)

    dest_dir = out / "slides"
    render(pptx_path, dest_dir)

    def slide_number(p: Path) -> int:
        m = re.search(r"(\d+)", p.stem)
        return int(m.group(1)) if m else 0

    images = sorted(dest_dir.glob("*.jpg"), key=slide_number)
    print(f"[{args.project_key}] {len(images)} slide(s) exportée(s) dans {dest_dir}")
    for img in images:
        print(f"  - {img.name}")


if __name__ == "__main__":
    main()
