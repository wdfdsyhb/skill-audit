import skill_audit as sa

FM = "---\nname: foo\ndescription: Does foo things.\n---\n\n# Foo\nBody here.\n"


def test_parse_frontmatter_extracts_meta_and_body():
    meta, body = sa.parse_frontmatter(FM)
    assert meta["name"] == "foo"
    assert meta["description"] == "Does foo things."
    assert body.startswith("# Foo")


def test_parse_frontmatter_missing_returns_empty_meta():
    meta, body = sa.parse_frontmatter("# no frontmatter here")
    assert meta == {}


def test_audit_skill_flags_name_mismatch(tmp_path):
    d = tmp_path / "bar"
    d.mkdir()
    meta, body = sa.parse_frontmatter(FM)
    issues = sa.audit_skill(d, meta, body)
    assert any("name mismatch" in i for i in issues)


def test_audit_skill_flags_missing_description(tmp_path):
    d = tmp_path / "foo"
    d.mkdir()
    meta, body = sa.parse_frontmatter("---\nname: foo\n---\nbody")
    issues = sa.audit_skill(d, meta, body)
    assert any("description" in i for i in issues)


def test_estimate_tokens_rough():
    assert sa.estimate_tokens("a" * 400) == 100


def test_find_duplicates_by_same_name():
    skills = [
        {"name": "foo", "dir": "foo", "description": "a", "tokens": 10, "path": "p1", "issues": []},
        {"name": "foo", "dir": "bar", "description": "b", "tokens": 10, "path": "p2", "issues": []},
        {"name": "baz", "dir": "baz", "description": "c", "tokens": 10, "path": "p3", "issues": []},
    ]
    dupes = sa.find_duplicates(skills)
    assert any(d["kind"] == "same-name" and "p1" in d["paths"] and "p2" in d["paths"] for d in dupes)


def test_find_duplicates_by_similar_description():
    skills = [
        {"name": "a", "dir": "a", "description": "Read files from disk and summarize their contents",
         "tokens": 10, "path": "p1", "issues": []},
        {"name": "b", "dir": "b", "description": "Read files from disk and summarize the contents",
         "tokens": 10, "path": "p2", "issues": []},
        {"name": "c", "dir": "c", "description": "Totally different thing entirely",
         "tokens": 10, "path": "p3", "issues": []},
    ]
    dupes = sa.find_duplicates(skills)
    assert any(d["kind"] == "similar" and {t for t in d["paths"]} == {"p1", "p2"} for d in dupes)


def test_audit_tree_counts_and_tokens(tmp_path):
    for name in ("foo", "bar"):
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text(FM.replace("name: foo", f"name: {name}"), encoding="utf-8")
    report = sa.audit_tree(tmp_path)
    assert report["total"] == 2
    assert report["total_tokens"] > 0
    assert len(report["skills"]) == 2
