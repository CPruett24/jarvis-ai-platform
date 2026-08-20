from services.project_state import get_project_state


def test_project_state_contains_project_root():

    state = get_project_state()

    assert state is not None
    assert "root" in state
    assert state["root"]


def test_project_state_contains_files():

    state = get_project_state()

    assert "files" in state
    assert isinstance(
        state["files"],
        list,
    )

    assert len(
        state["files"]
    ) > 0


def test_project_state_contains_python_files():

    state = get_project_state()

    assert "python_files" in state
    assert isinstance(
        state["python_files"],
        list,
    )

    assert any(
        path.endswith(".py")
        for path in state["python_files"]
    )


def test_project_state_file_count_matches_files():

    state = get_project_state()

    assert state["file_count"] == len(
        state["files"]
    )


def test_project_state_python_file_count_matches():

    state = get_project_state()

    assert state["python_file_count"] == len(
        state["python_files"]
    )