"""Safe execution contract and manual-only application handoff."""
from typing import Protocol

from app.database.models import Application, Job
from app.models.workflow import ExecutionResult


class ApplicationExecutor(Protocol):
    def execute(
        self,
        application: Application,
        job: Job,
        *,
        candidate_approved: bool,
    ) -> ExecutionResult:
        """Prepare or perform an application only within the source's safe policy."""
        ...


class ManualApplicationExecutor:
    """Provide candidate-controlled steps without automating protected web flows."""

    def execute(
        self,
        application: Application,
        job: Job,
        *,
        candidate_approved: bool,
    ) -> ExecutionResult:
        if candidate_approved is not True:
            raise ValueError("Candidate approval is required before application handoff.")

        listing = job.source_url or "the job listing in CareerPilot"
        instructions = "\n".join((
            f"1. Open {listing}.",
            "2. Sign in directly on the job platform if needed; do not share "
            "passwords or one-time codes with CareerPilot.",
            "3. Complete and review the application yourself.",
            "4. If you encounter a CAPTCHA, authentication wall, or other "
            "platform restriction, stop automated activity and complete the "
            "required step directly with the platform.",
            "5. Return to the Application Tracker and confirm only after the "
            "application has actually been submitted.",
        ))
        return ExecutionResult(
            status="manual_required",
            execution_mode="manual",
            message=(
                f"Application {application.id} is paused for candidate-controlled "
                "completion."
            ),
            manual_instructions=instructions,
        )
