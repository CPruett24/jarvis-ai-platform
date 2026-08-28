from services.capability_manager import (
    get_all_capabilities,
    get_available_capability_names,
    get_disabled_capability_names,
    get_unavailable_capability_names,
    get_capability_details,
    get_capability_summary,
)


def test_get_all_capabilities_returns_registered_capabilities():

    capabilities = get_all_capabilities()

    assert capabilities
    assert all(
        capability.name
        for capability in capabilities
    )


def test_available_capabilities_are_registered():

    available = (
        get_available_capability_names()
    )

    assert isinstance(
        available,
        list,
    )


def test_disabled_capabilities_are_list():

    disabled = (
        get_disabled_capability_names()
    )

    assert isinstance(
        disabled,
        list,
    )


def test_unavailable_capabilities_are_list():

    unavailable = (
        get_unavailable_capability_names()
    )

    assert isinstance(
        unavailable,
        list,
    )


def test_calendar_details_are_available():

    details = get_capability_details(
        "calendar"
    )

    assert details is not None
    assert details["name"] == "Calendar"
    assert details["available"] is False
    assert details["reason"]


def test_unknown_capability_returns_none():

    details = get_capability_details(
        "does_not_exist"
    )

    assert details is None


def test_capability_summary_has_expected_structure():

    summary = get_capability_summary()

    assert summary["total"] >= 1
    assert isinstance(
        summary["available"],
        list,
    )
    assert isinstance(
        summary["unavailable"],
        list,
    )
    assert isinstance(
        summary["disabled"],
        list,
    )


def test_calendar_is_reported_unavailable():

    details = get_capability_details(
        "calendar"
    )

    assert details is not None
    assert details["name"] == "Calendar"
    assert details["available"] is False
    assert details["enabled"] is False
    assert (
        details["reason"]
        == "Calendar integration has not been configured yet."
    )

def test_hermes_is_reported_available():
    capability = get_capability_details(
        "hermes_agent"
    )

    assert capability is not None
    assert capability["available"] is True
    assert capability["enabled"] is True
    assert capability["reason"] is None