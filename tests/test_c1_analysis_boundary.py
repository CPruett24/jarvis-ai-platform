import pytest
from services import project_access as access
from services.project_analysis_cache import get_source_tree, clear_analysis_cache
from services.project_analysis_index import get_project_analysis_index
from services.project_execution import trace_execution


def test_authorized_ast_reads_and_cache_isolation(tmp_path):
    old = access._projects.copy(), access._active, access._revision
    try:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        (first / "module.py").write_text("def first():\n    pass\n")
        (second / "module.py").write_text("def second():\n    pass\n")
        access.register_project("one", first)
        access.register_project("two", second)
        access.select_project("one")
        assert get_source_tree(first / "module.py").body[0].name == "first"
        access.select_project("two")
        assert get_source_tree(first / "module.py") is None
        assert get_source_tree(second / "module.py").body[0].name == "second"
        with pytest.raises(access.ProjectAccessError):
            get_project_analysis_index()
        with pytest.raises(access.ProjectAccessError):
            trace_execution("module.py", "second")
        access.revoke_project("two")
        assert get_source_tree(second / "module.py") is None
    finally:
        access._projects, access._active, access._revision = old
        clear_analysis_cache()
