"""Parallel preparation of application packets and tailored drafts."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.services.application_packet_service import application_packet_service
from app.services.application_service import application_service
from app.services.job_service import job_service
from app.services.tailoring_service import tailoring_service


class ApplicationPreparationService:
    def prepare_one(
        self, *, candidate_id: int, application_id: int, generate_tailored: bool = True
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"application_id": application_id, "packet": None, "tailored": None, "error": None}
        try:
            if generate_tailored:
                application = None
                from app.database.database import SessionLocal
                from app.database.models import Application, Job
                with SessionLocal() as db:
                    application = db.query(Application).filter(Application.id == application_id).first()
                    job_id = application.job_id if application else None
                if job_id is not None:
                    draft_data = tailoring_service.generate_draft(candidate_id, job_id)
                    draft_id = tailoring_service.save_draft(
                        candidate_id,
                        job_id,
                        None,
                        draft_data["draft_text"],
                        draft_data["suggestions"],
                        draft_data["limitations"],
                        draft_data["prompt"],
                        draft_data["raw_response"],
                    )
                    result["tailored"] = draft_id
            packet_dir = application_packet_service.prepare_packet(
                candidate_id=candidate_id, application_id=application_id
            )
            result["packet"] = str(packet_dir)
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
        return result

    def prepare_batch(
        self, *, candidate_id: int, application_ids: list[int], max_workers: int = 2
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self.prepare_one,
                    candidate_id=candidate_id,
                    application_id=application_id,
                    generate_tailored=True,
                ): application_id
                for application_id in application_ids
            }
            for future in as_completed(futures):
                results.append(future.result())
        return results


application_preparation_service = ApplicationPreparationService()
