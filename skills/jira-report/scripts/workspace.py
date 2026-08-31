"""Résolution + bootstrap du répertoire de données (générique — aucune
référence à une organisation précise ne doit apparaître ici).

Le repo du skill reste du code distribuable ; les données privées (JQL réels,
contexte qualitatif d'équipe, .env, PPT générés) vivent dans un répertoire de
données séparé, jamais versionné avec le skill, choisi une fois par
l'utilisateur au premier lancement (voir bootstrap()).

Résolution du chemin, dans l'ordre :
  1. Variable d'environnement REPORT_DATA_HOME, si définie.
  2. Pointeur local .data-dir-path (à côté de ce fichier, gitignoré), écrit par
     bootstrap() lors du premier lancement.
  3. Ni l'un ni l'autre : DataDirNotConfigured — à l'agent (SKILL.md) de
     demander le chemin à l'utilisateur puis d'appeler bootstrap().
"""
import os
import shutil
from pathlib import Path

ENV_VAR = "REPORT_DATA_HOME"
SKILL_ROOT = Path(__file__).resolve().parent.parent
POINTER_FILE = SKILL_ROOT / ".data-dir-path"
SCAFFOLD_DIR = SKILL_ROOT / "scaffold"


class DataDirNotConfigured(RuntimeError):
    def __init__(self):
        super().__init__(
            "Aucun répertoire de données configuré. Demander à l'utilisateur où le "
            "créer (ex. à côté du skill dans son espace de travail), puis lancer "
            "scripts/bootstrap.py <chemin> une première fois — voir SKILL.md, "
            "section « Première utilisation »."
        )


def _read_pointer() -> Path | None:
    if POINTER_FILE.exists():
        raw = POINTER_FILE.read_text(encoding="utf-8").strip()
        if raw:
            return Path(raw)
    return None


def data_root() -> Path:
    raw = os.environ.get(ENV_VAR)
    if raw:
        return Path(raw).expanduser().resolve()
    pointer = _read_pointer()
    if pointer:
        return pointer
    raise DataDirNotConfigured()


def bootstrap(path) -> Path:
    """Crée le répertoire de données à l'emplacement choisi et y copie le
    scaffold (config d'exemple, contexte vide, template neutre). Idempotent :
    si le pointeur local existe déjà, refuse d'écraser silencieusement (dire
    à l'utilisateur ce qui existe plutôt que de re-bootstraper dessus)."""
    existing = _read_pointer()
    if existing:
        raise RuntimeError(
            f"Un répertoire de données est déjà configuré ({existing}). "
            f"Supprimer {POINTER_FILE} manuellement si tu veux vraiment en "
            "choisir un autre."
        )

    root = Path(path).expanduser().resolve()
    (root / "projects").mkdir(parents=True, exist_ok=True)
    (root / "contexte").mkdir(parents=True, exist_ok=True)
    (root / "templates").mkdir(parents=True, exist_ok=True)

    org_md = root / "contexte" / "organisation.md"
    if not org_md.exists():
        shutil.copy2(SCAFFOLD_DIR / "organisation.example.md", org_md)

    template = root / "templates" / "template.pptx"
    if not template.exists():
        shutil.copy2(SCAFFOLD_DIR / "template.pptx", template)

    env_file = root / ".env"
    if not env_file.exists():
        shutil.copy2(SKILL_ROOT / ".env.example", env_file)

    POINTER_FILE.write_text(str(root), encoding="utf-8")
    return root


def list_project_keys() -> list[str]:
    proj_root = data_root() / "projects"
    if not proj_root.is_dir():
        return []
    return sorted(p.parent.name for p in proj_root.glob("*/project.yaml"))


def load_project_config(key: str) -> dict:
    import yaml

    p = data_root() / "projects" / key / "project.yaml"
    if not p.exists():
        raise FileNotFoundError(
            f"{p} introuvable. Projets disponibles : {', '.join(list_project_keys()) or '(aucun)'}"
        )
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def project_dir(key: str) -> Path:
    return data_root() / "projects" / key


def output_dir(key: str) -> Path:
    d = project_dir(key) / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def template_path() -> Path:
    return data_root() / "templates" / "template.pptx"
