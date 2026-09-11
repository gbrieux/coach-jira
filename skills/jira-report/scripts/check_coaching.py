#!/usr/bin/env python3
"""Valide un bloc `coaching` avant injection — plafonds et cardinalités.

Usage:
    python scripts/check_coaching.py <coaching_utf8.json>

Source de vérité des plafonds : COACH_PROMPT.md, section « Contraintes de
rendu » — ne pas les recopier ailleurs sans les faire diverger, y renvoyer à
la place (voir CLAUDE.md, « Ajouter un indicateur »).

Ce script ne juge jamais le *contenu* (le fond du texte) — seulement ce qui
casserait le rendu à positions fixes : longueur, cardinalité, type. Sortie 0
si le coaching est injectable, 1 si au moins une erreur bloquante.

Importable depuis set_coaching.py : `validate_coaching(coaching) ->
(errors, warnings)`, deux listes de messages séparées.
"""
import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------- plafonds
# Un seul endroit faisant autorité (voir COACH_PROMPT.md, « Contraintes de
# rendu » — les deux doivent rester cohérents).
MAX_LEN = {
    "vue_ensemble": 380,
    "risque_principal": 150,
    "delta": 300,
    "burndown_lecture": 200,
    "velocity_lecture": 200,
    "tempo_conso_lecture": 200,
    "conso_corrective_lecture": 250,
    "cycle_time_lecture": 220,
    "types_lecture": 250,
    "epics_lecture": 250,
}
LECTURE_VALUE_MAX = 150
LECTURE_EXACT_COUNT = 5
RECO_MAX = 105
RECO_MAX_COUNT = 3
QUESTIONS_MAX = 110
QUESTIONS_MAX_COUNT = 3

SIMPLE_STR_FIELDS = set(MAX_LEN)
KNOWN_FIELDS = SIMPLE_STR_FIELDS | {"lecture", "recommandations", "questions"}


def _len_msg(label, value, cap):
    over = len(value) - cap
    return f"{label} : {len(value)} caractères > {cap} (dépassement de {over})"


def validate_coaching(coaching):
    """Retourne (errors, warnings) — deux listes de messages. Ne modifie pas
    `coaching`. `coaching` doit déjà être l'objet coaching (pas l'enveloppe
    {"coaching": {...}})."""
    errors, warnings = [], []

    if not isinstance(coaching, dict):
        errors.append("le coaching doit être un objet JSON")
        return errors, warnings

    for field in coaching:
        if field not in KNOWN_FIELDS:
            warnings.append(f"{field} : champ inconnu, ne sera pas rendu")

    for field, cap in MAX_LEN.items():
        if field not in coaching:
            continue
        value = coaching[field]
        if not isinstance(value, str):
            errors.append(f"{field} : doit être une chaîne (reçu {type(value).__name__})")
            continue
        if not value:
            warnings.append(f"{field} : présent mais vide")
            continue
        if len(value) > cap:
            errors.append(_len_msg(field, value, cap))

    if "lecture" in coaching:
        lecture = coaching["lecture"]
        if not isinstance(lecture, dict):
            errors.append(f"lecture : doit être un objet (reçu {type(lecture).__name__})")
        else:
            if not lecture:
                warnings.append("lecture : présent mais vide")
            elif len(lecture) > LECTURE_EXACT_COUNT:
                errors.append(
                    f"lecture : {len(lecture)} entrées > {LECTURE_EXACT_COUNT} "
                    f"(dépassement de {len(lecture) - LECTURE_EXACT_COUNT}) — une entrée en trop "
                    "dépasse la carte"
                )
            elif len(lecture) < LECTURE_EXACT_COUNT:
                warnings.append(
                    f"lecture : incomplète ({len(lecture)}/{LECTURE_EXACT_COUNT} entrées)"
                )
            for key, value in lecture.items():
                if not isinstance(value, str):
                    errors.append(
                        f"lecture[{key!r}] : doit être une chaîne (reçu {type(value).__name__})"
                    )
                elif not value:
                    warnings.append(f"lecture[{key!r}] : présent mais vide")
                elif len(value) > LECTURE_VALUE_MAX:
                    errors.append(_len_msg(f"lecture[{key!r}]", value, LECTURE_VALUE_MAX))

    if "recommandations" in coaching:
        recos = coaching["recommandations"]
        if not isinstance(recos, list):
            errors.append(f"recommandations : doit être une liste (reçu {type(recos).__name__})")
        else:
            if not recos:
                warnings.append("recommandations : présent mais vide")
            elif len(recos) > RECO_MAX_COUNT:
                errors.append(
                    f"recommandations : {len(recos)} items > {RECO_MAX_COUNT} maximum "
                    f"(dépassement de {len(recos) - RECO_MAX_COUNT}) — une item en trop sort de la slide"
                )
            for i, r in enumerate(recos):
                if not isinstance(r, str):
                    errors.append(f"recommandations[{i}] : doit être une chaîne (reçu {type(r).__name__})")
                elif not r:
                    warnings.append(f"recommandations[{i}] : vide")
                else:
                    if len(r) > RECO_MAX:
                        errors.append(_len_msg(f"recommandations[{i}]", r, RECO_MAX))
                    if r.rstrip().endswith("?"):
                        warnings.append(
                            f"recommandations[{i}] : se termine par '?' — les questions ont "
                            "leur propre champ ('questions')"
                        )

    if "questions" in coaching:
        questions = coaching["questions"]
        if not isinstance(questions, list):
            errors.append(f"questions : doit être une liste (reçu {type(questions).__name__})")
        else:
            if not questions:
                warnings.append("questions : présent mais vide")
            elif len(questions) > QUESTIONS_MAX_COUNT:
                errors.append(
                    f"questions : {len(questions)} items > {QUESTIONS_MAX_COUNT} maximum "
                    f"(dépassement de {len(questions) - QUESTIONS_MAX_COUNT})"
                )
            for i, q in enumerate(questions):
                if not isinstance(q, str):
                    errors.append(f"questions[{i}] : doit être une chaîne (reçu {type(q).__name__})")
                elif not q:
                    warnings.append(f"questions[{i}] : vide")
                elif len(q) > QUESTIONS_MAX:
                    errors.append(_len_msg(f"questions[{i}]", q, QUESTIONS_MAX))

    return errors, warnings


def load_coaching(path: Path):
    incoming = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(incoming, dict) and "coaching" in incoming:
        return incoming["coaching"]
    return incoming


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("coaching_json", type=Path)
    args = ap.parse_args()

    if not args.coaching_json.exists():
        print(f"ERREUR: fichier absent : {args.coaching_json}", file=sys.stderr)
        sys.exit(1)

    coaching = load_coaching(args.coaching_json)
    errors, warnings = validate_coaching(coaching)

    for w in warnings:
        print(f"AVERTISSEMENT: {w}")
    for e in errors:
        print(f"ERREUR: {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} erreur(s) bloquante(s) — coaching non injectable en l'état.",
              file=sys.stderr)
        sys.exit(1)

    print(f"OK — injectable ({len(warnings)} avertissement(s)).")


if __name__ == "__main__":
    main()
