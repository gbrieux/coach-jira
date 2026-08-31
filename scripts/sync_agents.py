#!/usr/bin/env python3
"""Régénère .agents/skills/ (entrées Codex) à partir de .claude/commands/*.md.

Usage:
    python scripts/sync_agents.py

Codex n'a pas de slash commands ; les mêmes commandes sont exposées comme
skills relais dans .agents/skills/<nom>/ (SKILL.md + agents/openai.yaml).
`.claude/commands/*.md` reste la source de vérité unique — ce script ne fait
que la refléter, jamais l'inverse. Écrase entièrement .agents/skills/ à chaque
lancement (à relancer après toute modification de .claude/commands/).
"""
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = ROOT / ".claude" / "commands"
AGENTS_SKILLS_DIR = ROOT / ".agents" / "skills"

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_command(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER.match(text)
    if not m:
        raise ValueError(f"{path}: pas de frontmatter YAML en tête de fichier")
    meta = yaml.safe_load(m.group(1)) or {}
    meta["description"] = meta.get("description", "")
    return meta


def title_from_name(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").capitalize()


def write_skill(name: str, description: str, source_rel: str):
    skill_dir = AGENTS_SKILLS_DIR / name
    (skill_dir / "agents").mkdir(parents=True, exist_ok=True)

    skill_md = f"""---
name: {name}
description: "{description}"
---

# {title_from_name(name)} (Codex — relais vers la commande Claude Code)

Contenu source, identique pour Claude Code et Codex : voir
`{source_rel}`. `$1`/`$2` y désignent les arguments fournis par
l'utilisateur dans sa demande (ex. la clé de projet, la question). Ne pas
dupliquer cette logique ici — la lire et l'appliquer directement depuis ce
fichier source.

Régénéré automatiquement par `scripts/sync_agents.py` à partir de
`{source_rel}` — ne pas éditer à la main.
"""
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    openai_yaml = f"""interface:
  display_name: "{title_from_name(name)}"
  short_description: "{description}"
  default_prompt: "Utilise ${name} pour : {description[0].lower()}{description[1:]}"

policy:
  allow_implicit_invocation: true
"""
    (skill_dir / "agents" / "openai.yaml").write_text(openai_yaml, encoding="utf-8")


def main():
    if not COMMANDS_DIR.is_dir():
        print(f"ERREUR: {COMMANDS_DIR} introuvable", file=sys.stderr)
        sys.exit(1)

    if AGENTS_SKILLS_DIR.exists():
        shutil.rmtree(AGENTS_SKILLS_DIR)

    written = []
    for cmd_path in sorted(COMMANDS_DIR.glob("*.md")):
        name = cmd_path.stem
        meta = parse_command(cmd_path)
        source_rel = f".claude/commands/{cmd_path.name}"
        write_skill(name, meta["description"], source_rel)
        written.append(name)

    print(f"Régénéré {AGENTS_SKILLS_DIR} depuis {COMMANDS_DIR} :")
    for name in written:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
