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

from services.project_state import (
    get_project_snapshot,
    compare_project_snapshots,
)


def test_identical_snapshots_have_no_changes():

    snapshot = get_project_snapshot()

    result = compare_project_snapshots(
        snapshot,
        snapshot,
    )

    assert result["added"] == []
    assert result["modified"] == []
    assert result["deleted"] == []


def test_modified_file_is_detected():

    previous = {
        "files": {
            "router.py": ("old-signature",)
        }
    }

    current = {
        "files": {
            "router.py": ("new-signature",)
        }
    }

    result = compare_project_snapshots(
        previous,
        current,
    )

    assert result["modified"] == [
        "router.py"
    ]


def test_added_file_is_detected():

    previous = {
        "files": {}
    }

    current = {
        "files": {
            "router.py": ("signature",)
        }
    }

    result = compare_project_snapshots(
        previous,
        current,
    )

    assert result["added"] == [
        "router.py"
    ]


def test_deleted_file_is_detected():

    previous = {
        "files": {
            "router.py": ("signature",)
        }
    }

    current = {
        "files": {}
    }

    result = compare_project_snapshots(
        previous,
        current,
    )

    assert result["deleted"] == [
        "router.py"
    ]

def test_refresh_project_analysis_when_unchanged():

    from services.project_state import (
        refresh_project_analysis_if_changed,
    )

    result = refresh_project_analysis_if_changed()

    assert result["changed"] is False
    assert result["changes"]["added"] == []
    assert result["changes"]["modified"] == []
    assert result["changes"]["deleted"] == []


def test_refresh_project_analysis_detects_changes():

    from services.project_state import (
        refresh_project_analysis_if_changed,
    )

    import services.project_state as project_state

    previous = {
        "files": {
            "router.py": (
                "old-signature",
            )
        }
    }

    current = {
        "files": {
            "router.py": (
                "new-signature",
            )
        }
    }

    original_snapshot = (
        project_state._last_project_snapshot
    )

    try:

        project_state._last_project_snapshot = (
            previous
        )

        project_state.get_project_snapshot = (
            lambda: current
        )

        result = (
            refresh_project_analysis_if_changed()
        )

        assert result["changed"] is True
        assert result["changes"]["modified"] == [
            "router.py"
        ]

    finally:

        project_state._last_project_snapshot = (
            original_snapshot
        )

def test_non_python_change_does_not_require_analysis_refresh():

    from services.project_state import (
        should_refresh_project_analysis,
    )

    changes = {
        "added": [],
        "modified": [
            r"C:\Projects\JARVIS-AI\README.md"
        ],
        "deleted": [],
    }

    assert (
        should_refresh_project_analysis(changes)
        is False
    )


def test_python_change_requires_analysis_refresh():

    from services.project_state import (
        should_refresh_project_analysis,
    )

    changes = {
        "added": [],
        "modified": [
            r"C:\Projects\JARVIS-AI\commands\router.py"
        ],
        "deleted": [],
    }

    assert (
        should_refresh_project_analysis(changes)
        is True
    )


def test_added_python_file_requires_analysis_refresh():

    from services.project_state import (
        should_refresh_project_analysis,
    )

    changes = {
        "added": [
            r"C:\Projects\JARVIS-AI\services\new_service.py"
        ],
        "modified": [],
        "deleted": [],
    }

    assert (
        should_refresh_project_analysis(changes)
        is True
    )


def test_deleted_python_file_requires_analysis_refresh():

    from services.project_state import (
        should_refresh_project_analysis,
    )

    changes = {
        "added": [],
        "modified": [],
        "deleted": [
            r"C:\Projects\JARVIS-AI\services\old_service.py"
        ],
    }

    assert (
        should_refresh_project_analysis(changes)
        is True
    )