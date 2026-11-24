"""Assemble a ready-to-use application packet for manual submission."""
import json
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.database.models import Application, Candidate, Job, TailoredResume
from app.services.answer_bank_service import answer_bank_service
from app.services.clarification_queue_service import clarification_queue_service


PACKET_ROOT = Path("data/application_packets")


class ApplicationPacketService:
    def prepare_packet(
        self, *, candidate_id: int, application_id: int
    ) -> Path:
        with SessionLocal() as db:
            application = db.query(Application).filter(
                Application.id == application_id,
                Application.candidate_id == candidate_id,
            ).first()
            if application is None:
                raise ValueError("Application was not found for this candidate.")
            candidate = db.query(Candidate).filter(
                Candidate.id == candidate_id
            ).first()
            job = db.query(Job).filter(Job.id == application.job_id).first()
            if candidate is None or job is None:
                raise ValueError("Candidate or job was not found.")
            tailored = None
            if application.tailored_resume_id is not None:
                tailored = db.query(TailoredResume).filter(
                    TailoredResume.id == application.tailored_resume_id,
                    TailoredResume.candidate_id == candidate_id,
                ).first()
            clarification_rows = db.query(
                __import__("app.database.models", fromlist=["ClarificationRequest"]).ClarificationRequest
            ).filter(
                __import__("app.database.models", fromlist=["ClarificationRequest"]).ClarificationRequest.application_id == application_id
            ).all()

            packet_dir = PACKET_ROOT / str(application_id)
            packet_dir.mkdir(parents=True, exist_ok=True)

            # Job summary
            (packet_dir / "job.txt").write_text(
                "\n".join(
                    [
                        f"Title: {job.title}",
                        f"Company: {job.company}",
                        f"Location: {job.location or ''}",
                        f"Work mode: {job.work_mode or ''}",
                        f"Source: {job.source}",
                        f"Source URL: {job.source_url or ''}",
                        "",
                        "Description:",
                        job.description or "",
                    ]
                ),
                encoding="utf-8",
            )

            # Tailored resume
            if tailored is not None and tailored.draft_text:
                (packet_dir / "resume.txt").write_text(
                    tailored.draft_text, encoding="utf-8"
                )
            elif candidate.summary:
                (packet_dir / "resume.txt").write_text(
                    candidate.summary or "", encoding="utf-8"
                )

            # Answer sheet from clarification queue
            lines = ["Screening answers (review before pasting):", ""]
            for row in clarification_rows:
                lines.append(f"Q: {row.question_text}")
                lines.append(f"Answer: {row.answer_text or '(unresolved)'}")
                lines.append(f"Status: {'resolved' if row.is_resolved else 'needs answer'}")
                lines.append("")
            (packet_dir / "answers.txt").write_text(
                "\n".join(lines), encoding="utf-8"
            )

            # Handoff instructions
            instructions = [
                "Manual submission checklist (CareerPilot never submits for you):",
                "1. Open the job link and sign in on the source site.",
                "2. Upload data/application_packets/{}/resume.txt as your resume.".format(
                    application_id
                ),
                "3. Copy answers from answers.txt into the application form.",
                "4. Review everything, solve any CAPTCHA yourself, and click Submit.",
                "5. Return to CareerPilot and confirm 'Applied'.",
            ]
            (packet_dir / "handoff.txt").write_text(
                "\n".join(instructions), encoding="utf-8"
            )

            # Metadata
            (packet_dir / "packet.json").write_text(
                json.dumps(
                    {
                        "application_id": application_id,
                        "candidate_id": candidate_id,
                        "job_id": job.id,
                        "tailored_resume_id": application.tailored_resume_id,
                        "status": application.status,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return packet_dir


application_packet_service = ApplicationPacketService()
