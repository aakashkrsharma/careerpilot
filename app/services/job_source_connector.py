"""Extension contracts for compliant job-source integrations."""
from typing import Iterable, Protocol

from app.models.workflow import JobDiscoveryCriteria, SourceJob


class JobSourceConnector(Protocol):
    """Discover normalized jobs without owning persistence or application history."""

    @property
    def source_name(self) -> str:
        ...

    def discover(
        self,
        criteria: JobDiscoveryCriteria,
    ) -> Iterable[SourceJob]:
        """Return normalized records collected within the source's permitted use."""
        ...
