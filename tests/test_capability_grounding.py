from services.capability_executor import (
    CapabilityExecutionResult,
    get_observed_information,
)

from models.information import (
    InformationSource,
)


def test_successful_capability_result_creates_observed_information():

    result = CapabilityExecutionResult(
        success=True,
        capability="git",
        message="Git executed successfully.",
        data={
            "branch": "main",
        },
    )

    information = (
        get_observed_information(
            result
        )
    )

    assert len(
        information
    ) == 2

    assert (
        information[0].content
        == "Git executed successfully."
    )

    assert (
        information[0].source
        == InformationSource.OBSERVED
    )

    assert (
        information[1].content
        == "branch: main"
    )

    assert (
        information[1].source
        == InformationSource.OBSERVED
    )


def test_failed_capability_result_creates_no_observed_information():

    result = CapabilityExecutionResult(
        success=False,
        capability="git",
        error="Capability failed.",
    )

    information = (
        get_observed_information(
            result
        )
    )

    assert information == []