"""Rend `scripts/` importable (import indicators, from indicators.common
import ...) sans dépendre du répertoire de données (.data-dir-path/.env) —
les modules indicators/*.py sont purs vis-à-vis de fetch_jira.py, seul le
sys.path doit être préparé, comme le fait implicitement `python
scripts/fetch_jira.py` en tant que script direct."""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
