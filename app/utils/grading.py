import json
import time
from typing import List, Dict
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from pydantic import BaseModel, Field
import os

from app.models import ConversationLog, User, CaseStudy, Grade
from app.utils.perser import extract_json
from ..utils.logger import logger

load_dotenv()

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
        1. Critical Thinking: Did the student demonstrate analytical depth and logical reasoning?
        2. Communication: Was the student's response clear, coherent, and well-structured?
        3. Comprehension: Did the student understand the case and respond appropriately?

        Provide:
        1. An overall summary of the student's performance.
        2. A final score (intgervalue between 0 and 100).
        3. Individual scores for each criterion (integervalue between 0 and 100).
        4. A performance summary with 3 strengths and 3 weaknesses, each with a title and description.
        5. Be strict in grading the student's performance.

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
                    {{"title": "Clear communication", "description": "The student's response was easy to understand and well-structured."}}
                ],
                "weaknesses": [
                    {{"title": "Lack of critical thinking", "description": "The student failed to demonstrate deep analytical thinking and logical reasoning in their response."}}
                ]
            }}
        }}

        CRITICAL INSTRUCTION: \n
        Craft your feedback in a way that demonstrates you've carefully analyzed the student's work. Address the student directly using "you" (avoiding phrases like "the student" or "their"). 
        Think of this feedback as a direct conversation with the student to help them understand their strengths and areas for improvement. Be specific, offer concrete examples from their work, and suggest clear steps they can take to improve in the future.
        No any additional text apart from the json object. 
        """
    completion = groq_client.chat.completions.create(
        model="qwen-2.5-32b",
        messages=[
            {
                "role": "user",
                "content": grading_prompt
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
       
    )
    return completion.choices[0].message.content


def grade_conversation(conversation_id: str, user_email: str):
    """
    Fetch the conversation transcript, grade it, and return the structured JSON response.
    """

    graded_result = Grade.find_by_conversation_id(conversation_id)
    if graded_result:
        return graded_result.to_json()
 
    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    try:
        conversation = client.conversational_ai.get_conversation(conversation_id)
    except:
        logger.info("sleeeepinggg.......  " +  conversation_id)
        time.sleep(10)
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
        user = User.create(name=user_email.split("@")[0], email=user_email, role="student")
        logger.info(f"Created user: {user}")

    ConversationLog.create_log(
        user=user,
        conversation_id=conversation_id,
        transcript=formatted_transcript
    )
    grading_response = infer(formatted_transcript)

    try:
        grading_result = json.loads(grading_response)
    except:
        print(grading_response)
        grading_result = next(extract_json(grading_response))
        
    Grade.create_grade(user=user, conversation_id=conversation_id, final_score=int(grading_result["final_score"]), individual_scores=grading_result["individual_scores"], performance_summary=grading_result["performance_summary"])
    
    return grading_response
    