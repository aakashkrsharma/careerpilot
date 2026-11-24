"""Local Ollama-based resume information extraction."""
import json
import os
import re
from typing import Any

import httpx
import ollama
from pydantic import ValidationError

from app.models.extracted_info import ExtractedInfoBase


class LLMService:
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
        self.client = ollama.Client(host=self.base_url)

    def extract_information_from_resume(
        self,
        resume_text: str,
        candidate_id: int,
        resume_id: int,
    ) -> dict[str, Any]:
        if not resume_text or not resume_text.strip():
            raise ValueError("Resume text cannot be empty.")

        prompt = self._create_extraction_prompt(resume_text)
        raw_response = self._get_llm_response(prompt)
        extracted_data = self._parse_llm_response(raw_response)
        return {
            "candidate_id": candidate_id,
            "resume_id": resume_id,
            "extracted_data": extracted_data,
            "prompt_used": prompt,
            "llm_response": raw_response,
        }

    def _create_extraction_prompt(self, resume_text: str) -> str:
        return f"""
You are an expert resume parser. Extract the following information from the resume.
Return only a JSON object with string values or null for fields that are not present:
- full_name
- email
- phone
- location
- linkedin
- github
- summary
- experience
- skills
- education

Do not invent information.

Resume text:
{resume_text}
"""

    def _get_llm_response(self, prompt: str) -> str:
        try:
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False,
            )
        except (ollama.ResponseError, httpx.HTTPError) as exc:
            raise ValueError(f"Local Ollama extraction failed: {exc}") from exc

        return response.response

    def _parse_llm_response(self, response: str) -> dict[str, Any]:
        if not isinstance(response, str):
            raise ValueError("LLM response must be text.")

        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response must be a valid JSON object.") from exc

        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a valid JSON object.")

        for key, value in list(parsed.items()):
            if isinstance(value, (list, dict)):
                parsed[key] = json.dumps(value, ensure_ascii=False)

        try:
            validated = ExtractedInfoBase.model_validate(parsed)
        except ValidationError as exc:
            raise ValueError(
                "LLM response fields must contain text or null values."
            ) from exc

        extracted_data = validated.model_dump()
        if not any(
            value and value.strip()
            for value in extracted_data.values()
            if isinstance(value, str)
        ):
            raise ValueError("LLM response contains no candidate information to review.")

        return extracted_data


llm_service = LLMService()
