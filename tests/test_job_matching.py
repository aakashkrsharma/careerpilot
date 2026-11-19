import unittest

from app.database.models import Candidate, Job
from app.services.matching_service import MatchingService


class JobMatchingTests(unittest.TestCase):
    def setUp(self):
        self.service = MatchingService()
        self.candidate = Candidate(
            id=1,
            full_name="Matching Candidate",
            email="match@example.com",
            skills="Python, SQL, Docker",
            years_of_experience=5,
            preferred_roles="Python Developer, Backend Engineer",
            preferred_locations="Toronto, Remote",
            work_modes="Remote, Hybrid",
            minimum_salary=90000,
        )
        self.job = Job(
            id=10,
            source="manual",
            source_job_key="match-key",
            title="Senior Python Developer",
            company="Example Labs",
            location="Toronto",
            work_mode="Remote",
            required_skills="Python, SQL, AWS",
            minimum_experience=3,
            salary_min=95000,
            salary_max=130000,
        )

    def test_calculate_returns_transparent_component_scores(self):
        match = self.service.calculate(self.candidate, self.job)

        self.assertGreater(match.total_score, 70)
        self.assertEqual(match.skill_score, 33)
        self.assertEqual(match.matched_skills, ["python", "sql"])
        self.assertEqual(match.missing_skills, ["aws"])
        self.assertEqual(match.experience_score, 20)
        self.assertEqual(match.location_score, 15)
        self.assertEqual(match.work_mode_score, 10)
        self.assertEqual(match.role_score, 5)
        self.assertIn("Skills matched", match.explanation[0])

    def test_missing_profile_data_receives_neutral_or_low_scores(self):
        incomplete_candidate = Candidate(
            id=2,
            full_name="Incomplete Candidate",
            email="incomplete@example.com",
            skills=None,
            years_of_experience=None,
            preferred_roles=None,
            preferred_locations=None,
            work_modes=None,
        )
        match = self.service.calculate(incomplete_candidate, self.job)

        self.assertEqual(match.skill_score, 0)
        self.assertEqual(match.experience_score, 0)
        self.assertEqual(match.location_score, 10)
        self.assertEqual(match.work_mode_score, 5)
        self.assertEqual(match.role_score, 0)
        self.assertEqual(match.missing_skills, ["python", "sql", "aws"])

    def test_jobs_are_ranked_by_total_score_then_matched_skill_count(self):
        weaker_job = Job(
            id=11,
            source="manual",
            source_job_key="weaker-key",
            title="Java Engineer",
            company="Other Labs",
            location="Vancouver",
            work_mode="On-site",
            required_skills="Java, Kubernetes",
            minimum_experience=8,
        )
        ranked = self.service.rank_jobs(
            self.candidate,
            [weaker_job, self.job],
        )

        self.assertEqual(ranked[0].job_id, self.job.id)
        self.assertGreater(ranked[0].total_score, ranked[1].total_score)

    def test_description_skills_are_used_when_required_skills_are_missing(self):
        job = Job(
            id=12,
            source="manual",
            source_job_key="description-key",
            title="Python Developer",
            company="Example",
            description="Build APIs with Python and Docker on AWS.",
            required_skills=None,
        )
        skills = self.service.get_job_skills(job)

        self.assertIn("python", skills)
        self.assertIn("docker", skills)
        self.assertIn("aws", skills)

    def test_experience_below_requirement_is_partially_scored(self):
        candidate = Candidate(
            id=3,
            full_name="Junior Candidate",
            email="junior@example.com",
            years_of_experience=2,
        )
        score, explanation = self.service.experience_match(
            candidate,
            Job(
                id=13,
                source="manual",
                source_job_key="experience-key",
                title="Developer",
                company="Example",
                minimum_experience=4,
            ),
        )

        self.assertEqual(score, 10)
        self.assertIn("2 year", explanation)


if __name__ == "__main__":
    unittest.main()
