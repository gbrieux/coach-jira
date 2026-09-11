import json

import coaching_history as ch


def _setup_project(tmp_path, monkeypatch, coaching=None, generated_at="2026-01-01T00:00:00Z"):
    out_dir = tmp_path / "output"
    out_dir.mkdir(exist_ok=True)
    data = {"generated_at": generated_at, "coaching": coaching}
    (out_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ch, "output_dir", lambda key: out_dir)
    return out_dir


def test_archive_without_coaching_is_noop(tmp_path, monkeypatch):
    out_dir = _setup_project(tmp_path, monkeypatch, coaching=None)
    ch.cmd_archive("KEY")
    assert not (out_dir / "coaching_history.json").exists()


def test_archive_writes_one_entry(tmp_path, monkeypatch):
    out_dir = _setup_project(tmp_path, monkeypatch, coaching={"vue_ensemble": "x"})
    ch.cmd_archive("KEY")
    history = json.loads((out_dir / "coaching_history.json").read_text(encoding="utf-8"))
    assert len(history["entries"]) == 1
    assert history["entries"][0]["coaching"] == {"vue_ensemble": "x"}
    assert history["entries"][0]["generated_at"] == "2026-01-01T00:00:00Z"


def test_archive_is_idempotent_on_identical_coaching(tmp_path, monkeypatch):
    out_dir = _setup_project(tmp_path, monkeypatch, coaching={"vue_ensemble": "x"})
    ch.cmd_archive("KEY")
    ch.cmd_archive("KEY")
    history = json.loads((out_dir / "coaching_history.json").read_text(encoding="utf-8"))
    assert len(history["entries"]) == 1


def test_archive_appends_when_coaching_changes(tmp_path, monkeypatch):
    out_dir = _setup_project(tmp_path, monkeypatch, coaching={"vue_ensemble": "x"})
    ch.cmd_archive("KEY")
    _setup_project(tmp_path, monkeypatch, coaching={"vue_ensemble": "y"}, generated_at="2026-01-02T00:00:00Z")
    ch.cmd_archive("KEY")
    history = json.loads((out_dir / "coaching_history.json").read_text(encoding="utf-8"))
    assert len(history["entries"]) == 2
    assert history["entries"][-1]["coaching"] == {"vue_ensemble": "y"}


def test_archive_purges_beyond_max_entries(tmp_path, monkeypatch):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    monkeypatch.setattr(ch, "output_dir", lambda key: out_dir)
    for i in range(ch.MAX_ENTRIES + 5):
        data = {"generated_at": f"2026-01-{i + 1:02d}T00:00:00Z", "coaching": {"vue_ensemble": f"v{i}"}}
        (out_dir / "data.json").write_text(json.dumps(data), encoding="utf-8")
        ch.cmd_archive("KEY")
    history = json.loads((out_dir / "coaching_history.json").read_text(encoding="utf-8"))
    assert len(history["entries"]) == ch.MAX_ENTRIES
    assert history["entries"][-1]["coaching"]["vue_ensemble"] == f"v{ch.MAX_ENTRIES + 4}"


def test_read_history_tolerates_corrupted_file(tmp_path):
    p = tmp_path / "coaching_history.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert ch._read_history(p) == []


def test_read_history_tolerates_missing_file(tmp_path):
    assert ch._read_history(tmp_path / "absent.json") == []


def test_last_with_no_history_does_not_raise(tmp_path, monkeypatch, capsys):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    monkeypatch.setattr(ch, "output_dir", lambda key: out_dir)
    ch.cmd_last("KEY")
    captured = capsys.readouterr()
    assert "aucun historique" in captured.out
