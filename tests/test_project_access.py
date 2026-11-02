import pytest

from services import project_access as access


@pytest.fixture(autouse=True)
def authorization_state():
    projects, active, revision = access._projects.copy(), access._active, access._revision
    yield
    access._projects, access._active, access._revision = projects, active, revision


def test_default_is_explicit_and_cwd_does_not_authorize(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert access.get_project().root == access.DEFAULT_ROOT
    with pytest.raises(access.ProjectAccessError):
        access.select_project(str(tmp_path))


def test_registration_selection_revision_and_revocation(tmp_path):
    first = access.register_project("fixture", tmp_path)
    assert access.select_project("fixture") == first
    second = access.register_project("fixture", tmp_path)
    assert second.revision > first.revision
    with pytest.raises(access.ProjectAccessError):
        access.validate_project(first)
    access.revoke_project("fixture")
    assert access.get_project().project_id == "jarvis"


@pytest.mark.parametrize("target", ["../secret.py", "a/../../secret.py", "C:/secret.py",
    "file.py:secret", "//server/share/a.py", r"\\?\C:\secret.py", "/secret.py"])
def test_unsafe_paths_denied(tmp_path, target):
    context = access.register_project("fixture", tmp_path)
    with pytest.raises(access.ProjectAccessError):
        access.resolve_project_path(context, target)


def test_valid_relative_path(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    context = access.register_project("fixture", tmp_path)
    assert access.resolve_project_path(context, "a.py") == tmp_path / "a.py"


def test_missing_and_relative_roots_are_not_authorized(tmp_path):
    with pytest.raises((access.ProjectAccessError, FileNotFoundError)):
        access.register_project("missing", tmp_path / "missing")
    with pytest.raises(access.ProjectAccessError):
        access.register_project("relative", "relative")
