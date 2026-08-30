from dataclasses import dataclass
from enum import Enum


class InformationSource(str, Enum):

    USER_PROVIDED = "user_provided"

    REMEMBERED = "remembered"

    OBSERVED = "observed"

    AGENT_RESULT = "agent_result"

    INFERRED = "inferred"

    SYSTEM = "system"


@dataclass
class InformationItem:

    content: str

    source: InformationSource