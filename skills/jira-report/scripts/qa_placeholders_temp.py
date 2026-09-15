from __future__ import annotations

import re
import sys
from pathlib import Path

from pptx import Presentation


PATTERN = re.compile(r"\{\{[^}]+\}\}")


def inspect(path: Path) -> list[tuple[int, str]]:
    presentation = Presentation(path)
    found: list[tuple[int, str]] = []
    for slide_number, slide in enumerate(presentation.slides, 1):
        for shape in slide.shapes:
            if shape.has_text_frame:
                found.extend(
                    (slide_number, match)
                    for match in PATTERN.findall(shape.text_frame.text)
                )
            if shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        found.extend(
                            (slide_number, match)
                            for match in PATTERN.findall(cell.text)
                        )
    print(f"{path}: slides={len(presentation.slides)} placeholders={found}")
    return found


if __name__ == "__main__":
    failures = [path for arg in sys.argv[1:] if inspect(path := Path(arg))]
    raise SystemExit(1 if failures else 0)
