"""
LLM service for CareerPilot - handles interaction with local LLM (Ollama)
"""
import json
import os
from typing import Dict, Any, Optional
from app.database.models import ExtractedInfo, Resume
from app.database.database import get_db

class LLMService:
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model_name = os.getenv("OLLAMA_MODEL", "llama3")
    
    def extract_information_from_resume(self, resume_text: str, candidate_id: int, resume_id: int) -> Dict[str, Any]:
        """
        Extract structured information from resume text using LLM
        
        Args:
            resume_text (str): Text content of resume
            candidate_id (int): ID of the candidate
            resume_id (int): ID of the resume
            
        Returns:
            Dict[str, Any]: Extracted information
        """
        try:
            # Create prompt for LLM extraction
            prompt = self._create_extraction_prompt(resume_text)
            
            # Get response from LLM
            extracted_data = self._get_llm_response(prompt)
            
            # Parse and validate the response
            parsed_data = self._parse_llm_response(extracted_data)
            
            return {
                "candidate_id": candidate_id,
                "resume_id": resume_id,
                "extracted_data": parsed_data,
                "prompt_used": prompt,
                "llm_response": extracted_data
            }
        except Exception as e:
            print(f"Error in LLM extraction: {e}")
            return {
                "candidate_id": candidate_id,
                "resume_id": resume_id,
                "extracted_data": {},
                "prompt_used": prompt,
                "llm_response": str(e),
                "error": True
            }
    
    def _create_extraction_prompt(self, resume_text: str) -> str:
        """
        Create a prompt for extracting information from resume
        
        Args:
            resume_text (str): Text content of resume
            
        Returns:
            str: Prompt for LLM
        """
        prompt = f"""
        You are an expert resume parser. Extract the following structured information from this resume text:

        Please extract and return ONLY the following information in JSON format:
        - full_name
        - email 
        - phone
        - location
        - linkedin
        - github
        - summary
        - experience (detailed work history)
        - skills (technical skills)
        - education (degrees, institutions)

        Resume text:
        {resume_text}

        Return only valid JSON with these fields. Do not include any additional text or explanation.
        """
        return prompt
    
    def _get_llm_response(self, prompt: str) -> str:
        """
        Get response from local LLM (Ollama)
        
        Args:
            prompt (str): Prompt to send to LLM
            
        Returns:
            str: Response from LLM
        """
        try:
            import ollama
            
            # Send request to Ollama
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                stream=False
            )
            
            return response['response']
        except ImportError:
            print("Ollama not installed. Please install ollama package.")
            return json.dumps({
                "full_name": "Sample Name",
                "email": "sample@example.com", 
                "phone": "123-456-7890",
                "location": "Sample Location",
                "linkedin": "",
                "github": "",
                "summary": "Sample summary from resume.",
                "experience": "Sample experience details.",
                "skills": "Sample skills.",
                "education": "Sample education details."
            })
        except Exception as e:
            print(f"Error communicating with Ollama: {e}")
            # Return sample data for development purposes
            return json.dumps({
                "full_name": "Sample Name",
                "email": "sample@example.com", 
                "phone": "123-456-7890",
                "location": "Sample Location",
                "linkedin": "",
                "github": "",
                "summary": "Sample summary from resume.",
                "experience": "Sample experience details.",
                "skills": "Sample skills.",
                "education": "Sample education details."
            })
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response and extract structured data
        
        Args:
            response (str): Raw response from LLM
            
        Returns:
            Dict[str, Any]: Parsed structured data
        """
        try:
            # Try to parse as JSON first
            if response.strip().startswith('{'):
                return json.loads(response)
            else:
                # If not valid JSON, extract data using regex or other methods
                # For now, we'll return a basic structure
                return {
                    "full_name": "Sample Name",
                    "email": "sample@example.com", 
                    "phone": "123-456-7890",
                    "location": "Sample Location",
                    "linkedin": "",
                    "github": "",
                    "summary": response[:200] if len(response) > 200 else response,
                    "experience": response[:300] if len(response) > 300 else response,
                    "skills": response[:150] if len(response) > 150 else response,
                    "education": response[:200] if len(response) > 200 else response
                }
        except json.JSONDecodeError:
            # If JSON parsing fails, return default structure with the raw response
            return {
                "full_name": "Sample Name",
                "email": "sample@example.com", 
                "phone": "123-456-7890",
                "location": "Sample Location",
                "linkedin": "",
                "github": "",
                "summary": response,
                "experience": response,
                "skills": response,
                "education": response
            }

# Initialize service instance
llm_service = LLMService()