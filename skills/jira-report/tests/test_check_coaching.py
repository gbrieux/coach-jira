import check_coaching as cc


def test_ok_within_all_caps():
    coaching = {
        "vue_ensemble": "x" * 380,
        "risque_principal": "x" * 150,
        "delta": "x" * 300,
        "lecture": {k: "y" * 150 for k in ["Vélocité", "Cycle time", "Périmètre", "Flux", "Sprint 12"]},
        "recommandations": ["x" * 105, "y" * 10],
        "questions": ["x" * 110],
    }
    errors, _ = cc.validate_coaching(coaching)
    assert errors == []


def test_vue_ensemble_over_cap_is_error():
    errors, _ = cc.validate_coaching({"vue_ensemble": "x" * 381})
    assert any("vue_ensemble" in e and "381" in e for e in errors)


def test_lecture_more_than_5_is_error():
    lecture = {str(i): "x" for i in range(6)}
    errors, _ = cc.validate_coaching({"lecture": lecture})
    assert any("lecture" in e for e in errors)


def test_lecture_fewer_than_5_is_warning_not_error():
    lecture = {str(i): "x" for i in range(3)}
    errors, warnings = cc.validate_coaching({"lecture": lecture})
    assert errors == []
    assert any("incomplète" in w for w in warnings)


def test_lecture_value_over_cap_is_error():
    lecture = {"Vélocité": "x" * 151}
    errors, _ = cc.validate_coaching({"lecture": lecture})
    assert any("Vélocité" in e and "151" in e for e in errors)


def test_recommandations_over_3_is_error():
    errors, _ = cc.validate_coaching({"recommandations": ["a", "b", "c", "d"]})
    assert any("recommandations" in e for e in errors)


def test_recommandation_over_cap_is_error():
    errors, _ = cc.validate_coaching({"recommandations": ["x" * 106]})
    assert any("recommandations[0]" in e for e in errors)


def test_questions_over_3_is_error():
    errors, _ = cc.validate_coaching({"questions": ["a", "b", "c", "d"]})
    assert any("questions" in e for e in errors)


def test_question_over_cap_is_error():
    errors, _ = cc.validate_coaching({"questions": ["x" * 111]})
    assert any("questions[0]" in e for e in errors)


def test_recommandation_ending_in_question_mark_is_warning():
    _, warnings = cc.validate_coaching({"recommandations": ["Fait ceci ?"]})
    assert any("?" in w for w in warnings)


def test_unknown_field_is_warning():
    _, warnings = cc.validate_coaching({"foo": "bar"})
    assert any("champ inconnu" in w for w in warnings)


def test_empty_field_is_warning():
    _, warnings = cc.validate_coaching({"vue_ensemble": ""})
    assert any("vide" in w for w in warnings)


def test_wrong_type_is_error():
    errors, _ = cc.validate_coaching({"vue_ensemble": 123})
    assert any("vue_ensemble" in e for e in errors)


def test_recommandations_wrong_type_is_error():
    errors, _ = cc.validate_coaching({"recommandations": "pas une liste"})
    assert any("recommandations" in e for e in errors)


def test_recette_last_generated_ppt_overflow():
    """Cas de recette du brief : le coaching du dernier PPT généré (NOS_R2)
    doit remonter au minimum ces quatre dépassements."""
    coaching = {
        "vue_ensemble": "x" * 493,
        "risque_principal": "x" * 195,
        "recommandations": ["x" * 156],
        "lecture": {"Vélocité": "x" * 180, "B": "y", "C": "y", "D": "y", "E": "y"},
    }
    errors, _ = cc.validate_coaching(coaching)
    assert any("vue_ensemble" in e and "493" in e for e in errors)
    assert any("risque_principal" in e and "195" in e for e in errors)
    assert any("recommandations[0]" in e and "156" in e for e in errors)
    assert any("Vélocité" in e and "180" in e for e in errors)


def test_accepts_bare_object_or_wrapped():
    assert cc.validate_coaching({"vue_ensemble": "ok"}) == ([], [])


def test_non_dict_coaching_is_error():
    errors, _ = cc.validate_coaching(["not", "a", "dict"])
    assert errors
