from types import SimpleNamespace
import pytest

from services.project_retrieval import SUPPORTED_EXTENSIONS
from services.source_answer import validate_answer


def evidence(path="router.py", start=1, end=2):
    return SimpleNamespace(excerpts=[SimpleNamespace(source_id="Sreal", path=path,
                                                    start_line=start, end_line=end)])


@pytest.mark.parametrize("answer", [
    "See invented.yaml:999 for the implementation. [Sreal]",
    "See ROUTER.PY:999 for the implementation. [Sreal]",
    "See `router.py`:999. [Sreal]", "See **router.py**:999. [Sreal]",
    "See router.py#L999-L1000. [Sreal]", "See router.py lines 1–999. [Sreal]",
    "See router.py:2-1. [Sreal]", "See router.py:0. [Sreal]",
    "See router.py：９９９. [Sreal]", "See router.py&#58;999. [Sreal]",
    "See router%2Epy%3A999. [Sreal]", "See rou\u200bter.py:999. [Sreal]",
    "See router . PY : 999. [Sreal]", "See ../router.py:1. [Sreal]",
    "See services\\router.py:1. [Sreal]", "See router.py:1—999. [Sreal]",
    "See router.py:1−999. [Sreal]", "See router.py:1-999x. [Sreal]",
    "See router.py 999. [Sreal]", "See router.py at line 999. [Sreal]",
    "See unknown.blob:999. [Sreal]", "Claim [Sfake] [Sreal]",
    "See router.py@999. [Sreal]", "See router.py line999. [Sreal]",
    "See .env:999. [Sreal]", "See C:router.py:1. [Sreal]",
    "See lines 999-1000 of router.py. [Sreal]", "See router.py:one. [Sreal]",
    "See [router.py:999] [Sreal]", "See [router.py](https://example.com/router.py#L999). [Sreal]",
])
def test_adversarial_references_are_rejected(answer):
    assert validate_answer(answer, evidence()) is None


@pytest.mark.parametrize("extension", sorted(SUPPORTED_EXTENSIONS))
def test_every_supported_extension_and_case_is_checked(extension):
    path = "source" + extension
    assert validate_answer(f"Claim {path.upper()}:999. [Sreal]", evidence(path)) is None
    assert validate_answer(f"Claim [{path.upper()}:1-2].", evidence(path)) is not None


@pytest.mark.parametrize("answer", [
    "Claim [Sreal]", "Claim [router.py:1–2]", "Claim [ROUTER.PY:1-2]",
    "Claim router.py:1. [Sreal]", "Claim router.py#L1-L2. [Sreal]",
    "Claim router.py lines 1 through 2. [Sreal]",
])
def test_legitimate_references_and_source_ids_survive(answer):
    assert validate_answer(answer, evidence()) is not None


def test_paths_and_ranges_must_be_in_retrieved_excerpts():
    records = evidence("services/router.py", 20, 30)
    assert validate_answer("Claim [services\\router.py:20-25]", records) is not None
    assert validate_answer("Claim [services/router.py:1-2] [Sreal]", records) is None
    assert validate_answer("Claim [router.py:20-25] [Sreal]", records) is None
    assert validate_answer("Claim [services/router.py:25-35] [Sreal]", records) is None


def test_each_paragraph_needs_a_valid_reference():
    assert validate_answer("Claim [Sreal]\n\nUnsupported paragraph", evidence()) is None
