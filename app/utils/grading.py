import json
from typing import List, Dict
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnableSequence
import os
from ..models import Grade, CaseStudy, User, Session
from ..utils.logger import logger

# Load environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


from groq import Groq

groq_client = Groq(api_key=GROQ_API_KEY)

def infer(data):
    # Define grading prompt template
    grading_prompt =f"""
        You are a grading assistant for MBA students. Evaluate the following conversation transcript based on the following criteria:
        1. **Critical Thinking**: Did the student demonstrate analytical depth and logical reasoning?
        2. **Communication**: Was the student's response clear, coherent, and well-structured?
        3. **Comprehension**: Did the student understand the case and respond appropriately?

        Provide:
        1. A final score (out of 100).
        2. Individual scores for each criterion (out of 100).
        3. A performance summary with strengths and weaknesses.

        Transcript:
        {data}

        Return the response in JSON format with the following structure:
        {{
            "final_score": 77,
            "individual_scores": {{
                "Critical Thinking": 90,
                "Communication": 90,
                "Comprehension": 90
            }},
            "performance_summary": {{
                "Strengths": [
                    "Demonstrated a strong ability to critically analyze the economic implications of subsidy removal.",
                    "Clearly identified key stakeholders, including the government, businesses, and the general population."
                ],
                "Weaknesses": [
                    "Could improve in providing more detailed examples to support arguments.",
                    "Needs to address potential counterarguments more effectively."
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


# Define Pydantic models for validation (keep the existing ones)
class TranscriptMessage(BaseModel):
    role: str
    message: str
    tool_calls: List[Dict] = Field(default_factory=list)
    tool_results: List[Dict] = Field(default_factory=list)
    feedback: Dict = None
    time_in_call_secs: int
    conversation_turn_metrics: Dict = None

class Transcript(BaseModel):
    agent_id: str
    conversation_id: str
    status: str
    transcript: List[TranscriptMessage]
    metadata: Dict
    analysis: Dict
    conversation_initiation_client_data: Dict

class GradingResult(BaseModel):
    conversation_id: str
    agent_id: str = "unknown"  # Default value if not provided
    final_score: int
    individual_scores: Dict[str, int]  # e.g., {"Critical Thinking": 90, "Communication": 85}
    performance_summary: Dict[str, List[str]]  # e.g., {"Strengths": [...], "Weaknesses": [...]}

def grade_conversation(transcript_data, conversation_id):
    """
    Grade a conversation using Groq and LangChain.
    
    This function can handle both the ElevenLabs API transcript format 
    or our own stored transcript format.
    """
    # try:
        # # Check if we're dealing with ElevenLabs API format or our own format
        # if isinstance(transcript_data, Transcript):
        #     # It's the ElevenLabs API format
        #     conversation_id = transcript_data.conversation_id
        #     agent_id = transcript_data.agent_id
            
        #     # Extract the conversation text
        #     conversation_text = "\n".join([f"{msg.role}: {msg.message}" for msg in transcript_data.transcript])
        # else:
        #     # It's our own format (list of dict from Session.transcript)
        #     conversation_id = "unknown"  # This will be set separately in the service function
        #     agent_id = "unknown"
            
        #     # Extract the conversation text
        #     conversation_text = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in transcript_data])

        # Grade the conversation using the LLM
    grading_response = infer(transcript_data, )

    # Parse the grading response (assuming it returns a JSON-like string)
    # try:
        # import json
    grading_data = json.loads(grading_response)
    # except:
    #     # Fallback to eval if JSON parsing fails
    #     grading_data = eval(grading_response)

    # Create a GradingResult object
    grading_result = GradingResult(
        conversation_id=conversation_id,
        agent_id="agent_id",
        final_score=grading_data["final_score"],
        individual_scores=grading_data["individual_scores"],
        performance_summary=grading_data["performance_summary"],
    )

    return grading_result
    # except Exception as e:
    #     logger.error(f"Error in grade_conversation: {str(e)}")
    #     raise Exception(f"Error grading conversation: {str(e)}")