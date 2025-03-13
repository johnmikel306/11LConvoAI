from typing import List, Dict
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnableSequence
import os
from ..models import Grade, CaseStudy, User
from ..utils.logger import logger

# Load environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Define Pydantic models for validation
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
    agent_id: str
    final_score: int
    individual_scores: Dict[str, int]  # e.g., {"Critical Thinking": 90, "Communication": 85}
    performance_summary: Dict[str, List[str]]  # e.g., {"Strengths": [...], "Weaknesses": [...]}

# Initialize Groq LLM
groq_llm = ChatGroq(temperature=0, model_name="mixtral-8x7b-32768", groq_api_key=GROQ_API_KEY)

# Define grading prompt template
grading_prompt = PromptTemplate(
    input_variables=["transcript"],
    template="""
    You are a grading assistant for MBA students. Evaluate the following conversation transcript based on the following criteria:
    1. **Critical Thinking**: Did the student demonstrate analytical depth and logical reasoning?
    2. **Communication**: Was the student's response clear, coherent, and well-structured?
    3. **Comprehension**: Did the student understand the case and respond appropriately?

    Provide:
    1. A final score (out of 100).
    2. Individual scores for each criterion (out of 100).
    3. A performance summary with strengths and weaknesses.

    Transcript:
    {transcript}

    Return the response in JSON format with the following structure:
    {
        "final_score": 77,
        "individual_scores": {
            "Critical Thinking": 90,
            "Communication": 90,
            "Comprehension": 90
        },
        "performance_summary": {
            "Strengths": [
                "Demonstrated a strong ability to critically analyze the economic implications of subsidy removal.",
                "Clearly identified key stakeholders, including the government, businesses, and the general population."
            ],
            "Weaknesses": [
                "Could improve in providing more detailed examples to support arguments.",
                "Needs to address potential counterarguments more effectively."
            ]
        }
    }
    """
)

# Create a RunnableSequence
grading_chain: RunnableSequence = grading_prompt | groq_llm

def grade_conversation(transcript):
    """
    Grade a conversation using Groq and LangChain.
    """
    try:
        # Extract the conversation text
        conversation_text = "\n".join([f"{msg['role']}: {msg['message']}" for msg in transcript])

        # Grade the conversation using the LLM
        grading_response = grading_chain.run(transcript=conversation_text)

        # Parse the grading response (assuming it returns a JSON-like string)
        grading_data = eval(grading_response)  # Convert JSON string to dictionary

        # Create a GradingResult object
        grading_result = GradingResult(
            conversation_id=transcript.conversation_id,
            agent_id=transcript.agent_id,
            final_score=grading_data["final_score"],
            individual_scores=grading_data["individual_scores"],
            performance_summary=grading_data["performance_summary"],
        )

        return grading_result
    except Exception as e:
        raise Exception(f"Error grading conversation: {e}")