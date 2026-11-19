"""Local eligibility and identity checks applied before discovered jobs are stored."""
import re

from app.models.workflow import SourceJob


_INDIA_TERMS = (
    "india",
    "bengaluru",
    "bangalore",
    "hyderabad",
    "pune",
    "delhi",
    "gurugram",
    "gurgaon",
    "noida",
    "mumbai",
    "bombay",
    "chennai",
    "madras",
    "kolkata",
    "calcutta",
    "ahmedabad",
    "jaipur",
    "coimbatore",
    "kochi",
    "thiruvananthapuram",
    "indore",
    "chandigarh",
    "mysore",
    "mangalore",
    "karnataka",
    "telangana",
    "maharashtra",
    "tamil nadu",
)
_APAC_TERMS = ("apac", "asia pacific", "asia-pacific")
_GLOBAL_TERMS = ("worldwide", "anywhere", "global")
_REMOTE_TERMS = ("remote", "work from home", "distributed")


def is_india_eligible(job: SourceJob) -> bool:
    location = (job.location or "").strip().lower()
    if not location:
        return False
    if _contains_any(location, _INDIA_TERMS):
        return True
    remote = _contains_any(location, _REMOTE_TERMS) or (
        (job.work_mode or "").strip().lower() == "remote"
    )
    if not remote:
        return False
    return _contains_any(location, _APAC_TERMS + _GLOBAL_TERMS)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", text) is not None
        for term in terms
    )
