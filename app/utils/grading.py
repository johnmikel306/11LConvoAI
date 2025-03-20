import json
from typing import List, Dict
from elevenlabs.client import ElevenLabs
from pydantic import BaseModel, Field
import os

from app.models import ConversationLog, User
from ..utils.logger import logger

# Load environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

from groq import Groq

groq_client = Groq(api_key=GROQ_API_KEY)

def infer(formatted_transcript):
    """
    Grade the conversation transcript using the Groq API.
    """
    # Define grading prompt template
    grading_prompt = f"""
        You are a grading assistant for MBA students. Evaluate the following conversation transcript based on these criteria:
        1. **Critical Thinking**: Did the student demonstrate analytical depth and logical reasoning?
        2. **Communication**: Was the student's response clear, coherent, and well-structured?
        3. **Comprehension**: Did the student understand the case and respond appropriately?

        Provide:
        1. An overall summary of the student's performance.
        2. A final score (out of 100).
        3. Individual scores for each criterion (out of 100).
        4. A performance summary with strengths and weaknesses, each with a title and description.

        Transcript:
        {formatted_transcript}

        Return the response in JSON format with the following structure:
        {{
            "overall_summary": "Brief overview of the student's performance",
            "final_score": 85,
            "individual_scores": {{
                "Critical Thinking": 90,
                "Communication": 80,
                "Comprehension": 85
            }},
            "performance_summary": {{
                "strengths": [
                    {{"title": "Strong analytical skills", "description": "The student demonstrated excellent ability to analyze complex situations."}},
                ],
                "weaknesses": [
                    {{"title": "Room for improvement in communication", "description": "The student could enhance clarity in expressing ideas."}},
                ]
            }}
        }}
        """
    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": grading_prompt
            }
        ],
        temperature=1,
        max_completion_tokens=1024,
        top_p=1,
        response_format={"type": "json_object"},
        stream=False,
        stop=None,
    )

    return completion.choices[0].message.content

# Define Pydantic models for validation
class GradingResult(BaseModel):
    overall_summary: str
    final_score: int
    individual_scores: Dict[str, int]
    performance_summary: Dict[str, List[Dict[str, str]]]

async def grade_conversation(conversation_id: str, user_email: str) -> GradingResult:
    """
    Fetch the conversation transcript, grade it, and return the structured JSON response.
    """
    try:
        # Fetch the conversation transcript
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        conversation = client.conversational_ai.get_conversation(conversation_id)
        transcript = conversation.transcript
        
        # Format the transcript for grading
        formatted_transcript = []
        for message in transcript:
            formatted_transcript.append({
                "role": message.role,
                "message": message.message
            })
        
        logger.info(f"Fetched transcript for conversation ID: {conversation_id}")
        logger.info(f"Transcript: {formatted_transcript}")

        # save the transcript to the database
        user = await User.find_by_email(user_email)
        logger.info(f"Found user: {user}")
        if not user:
            user = await User.create(email=user_email)
            logger.info(f"Created user: {user}")

        await ConversationLog.create_log(
            user=user,
            conversation_id=conversation_id,
            transcript=formatted_transcript
        )

        # Grade the conversation using the LLM
        grading_response = infer(formatted_transcript)
        grading_data = json.loads(grading_response)

        # Validate the grading result using Pydantic
        grading_result = GradingResult(**grading_data)
        
        return grading_result
    
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing grading response: {str(e)}")
        raise ValueError("Invalid grading response format")
    except Exception as e:
        logger.error(f"Error grading conversation: {str(e)}")
        raise e