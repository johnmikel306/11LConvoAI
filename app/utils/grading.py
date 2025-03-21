import json
from typing import List, Dict
from elevenlabs.client import ElevenLabs
from pydantic import BaseModel, Field
import os

from app.models import ConversationLog, User, CaseStudy, Grade
from ..utils.logger import logger


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

from groq import Groq

groq_client = Groq(api_key=GROQ_API_KEY)

def infer(formatted_transcript):
    """
    Grade the conversation transcript using the Groq API.
    """
    grading_prompt = f"""
        You are a grading assistant for MBA students. Evaluate the following conversation transcript based on these criteria:
        1. **Critical Thinking**: Did the student demonstrate analytical depth and logical reasoning?
        2. **Communication**: Was the student's response clear, coherent, and well-structured?
        3. **Comprehension**: Did the student understand the case and respond appropriately?

        Provide:
        1. An overall summary of the student's performance.
        2. A final score (intgervalue between 0 and 100).
        3. Individual scores for each criterion (integervalue between 0 and 100).
        4. A performance summary with 3 strengths and 3 weaknesses, each with a title and description.

        Transcript:
        {formatted_transcript}

        Return the response in JSON format with the following structure replacing the example values with your evaluation:
        {{
            "overall_summary": "The student's performance was fair, demonstrating some understanding of the task but lacking in critical thinking and comprehension. The student's communication skills were clear, but the response was limited in scope.",
            "final_score": 60,
            "individual_scores": {{
                "critical_thinking": 40,
                "communication": 80,
                "comprehension": 50
            }},
            "performance_summary": {{
                "strengths": [
                    {{"title": "Clear communication", "description": "The student's response was easy to understand and well-structured."}},
                    {{"title": "Responsive to user input", "description": "The student engaged with the user's query and attempted to provide relevant information."}},
                    {{"title": "Demonstrated basic understanding", "description": "The student showed a basic grasp of the task and attempted to provide helpful tips."}}
                ],
                "weaknesses": [
                    {{"title": "Lack of critical thinking", "description": "The student failed to demonstrate deep analytical thinking and logical reasoning in their response."}},
                    {{"title": "Limited comprehension", "description": "The student's understanding of the task was limited, and they did not fully address the user's query."}},
                    {{"title": "Insufficient depth in response", "description": "The student's response was superficial and did not provide meaningful insights or suggestions."}}
                ]
            }}
        }}

        CRITICAL INSTRUCTION:
        No any additional text apart from the json object. 
        Do not add any ```json  or ```, return just the json object.
        """
    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": grading_prompt
            }
        ],
        temperature=0.5,
        max_completion_tokens=1024,
        top_p=1,
        stream=False,
        stop=None,
    )
    return completion.choices[0].message.content


def grade_conversation(conversation_id: str, user_email: str):
    """
    Fetch the conversation transcript, grade it, and return the structured JSON response.
    """
 
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    conversation = client.conversational_ai.get_conversation(conversation_id)
    transcript = conversation.transcript
    
    formatted_transcript = []
    for message in transcript:
        formatted_transcript.append({
            "role": message.role,
            "message": message.message
        })
    
    user = User.find_by_email(user_email)
    
    if not user:
        user = User.create(email=user_email)
        logger.info(f"Created user: {user}")

    ConversationLog.create_log(
        user=user,
        conversation_id=conversation_id,
        transcript=formatted_transcript
    )

    grading_response = infer(formatted_transcript)
    grading_data = json.loads(grading_response)
    
    Grade.create_grade(
        user=user,
        case_study=CaseStudy.objects(conversation_id=conversation_id).first(),
        conversation_id=conversation_id,
        final_score=grading_data['final_score'],
        individual_scores=grading_data['individual_scores'],
        performance_summary=grading_data['performance_summary']
    )
   
    return grading_response
    