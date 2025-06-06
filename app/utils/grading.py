import json
import os

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from google import genai
from google.genai import types

from app.models import ConversationLog, User, Grade, CaseStudy
from app.utils.perser import extract_json
from ..utils.logger import logger

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

from groq import Groq

groq_client = Groq(api_key=GROQ_API_KEY)


def infer(formatted_transcript, case_study_summary):
    """
    Grade the conversation transcript using the Groq API.
    """

    weights = {
        "critical_thinking": 0.40,
        "comprehension": 0.30,
        "communication": 0.30
    }
    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > 1e-9:
        print(f"Warning: Weights do not sum to 1.0 (sum is {total_weight}). Adjusting prompt.")
        adjusted_weights = {k: v / total_weight for k, v in weights.items()}
        weights = adjusted_weights

    grading_prompt = f"""
      You are an advanced senior grading lecturer for Miva Open University. Your role is to conduct a rigorous academic assessment of the following conversation transcript submitted by a user. You are to evaluate the response of the "user" to the agent's questions. Your evaluation must be aligned with the analytical and conceptual standards expected at the Masters level.

      **Context:**
      {case_study_summary}

      **Grading Criteria (Masters Level):**
      Evaluate the user's responses based on these criteria:
      - "Critical Thinking": How well did the user analyze the problem, draw logical conclusions, and demonstrate strategic insight?
      - "Comprehension": How well did the user understand the context and intent of the professional's questions?
      - "Communication": How clearly and persuasively did the user communicate their ideas?

      **Scoring Guidance (Qualitative Anchors for 0-100 Scale):**
      Use these descriptions as qualitative anchors when assigning a score on the 0-100 scale for each criterion:
        "0-10": Minimal or vague response with little relevance to the case. Concepts may be mentioned but not clearly explained or applied (like a 0-1 on a 5-point scale).
        "11-20": Partial or underdeveloped response that identifies a few relevant concepts but lacks clarity, depth, or proper contextual application (like a 2 on a 5-point scale).
        "21-40": Basic understanding demonstrated with some relevant points covered. Response shows limited depth or analysis, and application to the case may be somewhat surface-level or generic (like a 3 on a 5-point scale).
        "41-70": Good understanding of the subject matter with clear identification of key elements. Demonstrates logical analysis and applies concepts well, though may lack some depth or precision in certain areas (like a 4 on a 5-point scale).
        "71-100": Comprehensive and insightful analysis of the subject matter, clearly identifying relevant components, stakeholders, or frameworks. Demonstrates deep understanding through well-structured arguments, critical thinking, and detailed application to the case study context (like a 5 on a 5-point scale).

      **Internal Reasoning Process (Chain of Thought - Do NOT include this in the final output):**
      1.  Carefully read and understand the provided case study summary and the conversation transcript.
      2.  Review the Masters-level grading criteria and the 0-100 scoring guidance with qualitative anchors.
      3.  Go through the transcript turn by turn, specifically identifying the professional's questions and the user's subsequent responses.
      4.  For each user response (or lack thereof), analyze its quality against each of the three criteria: Critical Thinking, Comprehension, and Communication.
      5.  Based on the analysis and the scoring guidance, assign a preliminary qualitative level (like 0-5) for each criterion.
      6.  Convert this qualitative assessment into a precise 0-100 integer score for each criterion, ensuring it aligns with the qualitative anchors (e.g., if it feels like a strong '4', assign a score in the 70s). Justify each score by referencing specific parts of the transcript and the scoring guidance.
      7.  Calculate the final overall score as a weighted average of the three 0-100 individual scores using the specified weights: Critical Thinking ({weights['critical_thinking']:.0%}), Comprehension ({weights['comprehension']:.0%}), Communication ({weights['communication']:.0%}). Round the final score to the nearest integer.
      8.  Synthesize the individual scores, justifications, and the weighted final score into a concise overall summary of the user's performance.
      9.  Identify the top 3 strengths and top 3 weaknesses based on the detailed analysis for each criterion. Ensure each has a clear title and description.
      10. Format the final output *strictly* as the requested JSON object. Double-check that *only* the JSON is present in the final output.

      **Transcript:**
      {formatted_transcript}

      **Output Format:**
      Return the response strictly in JSON string format with the following structure. Do NOT include any text before or after the JSON string (no ```json or ```).

      {{
          "overall_summary": provide analytical feedback as a lecturer would after scrutinizing the conversation based on the grading criteria and context,
          "final_score": int,
          "individual_scores": {{
              "critical_thinking": int,
              "comprehension": int,
              "communication": int
          }},
          "individual_score_justifications": {{
              "critical_thinking": "Justification for the 0-100 Critical Thinking score, referencing transcript and qualitative anchors based on the grading criteria and context..",
              "comprehension": "Justification for the 0-100 Comprehension score, referencing transcript and qualitative anchors based on the grading criteria and context..",
              "communication": "Justification for the 0-100 Communication score, referencing transcript and qualitative anchors based on the grading criteria and context."
          }},
          "performance_summary": {{
              "strengths": [
                  {{"title": "Clear communication", "description": provide analytical feedback as a lecturer would after scrutinizing the conversation based on the grading criteria and context}}
              ],
              "weaknesses": [
                  {{"title": "Lack of critical thinking", "description": provide analytical feedback as a lecturer would after scrutinizing the conversation based on the grading criteria and context}}
              ]
          }}
      }}

      **CRITICAL INSTRUCTIONS:**
      - Do not add any ```json  or ```, return just the json object.
      - Apply a strict and rigorous grading approach that reflects Masters-level expectations.
      - Don't be generous with allocating marks for the evaluation.
      - Don't give generic feedback but focus on the how the conversation stands against the grading criteria and the context.
      - Focus *only* on the user's responses to the professional's questions.
      - If there is no relevant user response to a question, note it in the feedback and assign a score of 0 for relevant criteria.
      - Report feedback directly to the user using "you" & "your".
      - Do not refer to the professional as "agent"; use their title from the transcript if available, or a neutral term like "the professional".
      - Return *only* the JSON object. No additional text.
      - Ensure the `final_score` is calculated precisely using the specified weighted average formula and rounded to the nearest integer.
      - Follow the "Internal Reasoning Process" steps *before* generating the final JSON.
      """

    client = genai.Client(api_key=GOOGLE_API_KEY)

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-04-17",
        contents=grading_prompt,
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=2048),
            response_mime_type="application/json"
        )
    )

    return response.text


def grade_conversation(conversation_id: str, user_email: str, case_study: CaseStudy = None,
                       transcript_from_user: str = None):
    """
    Fetch the conversation transcript, grade it, and return the structured JSON response.
    """

    transcript = transcript_from_user

    try:
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        conversation = elevenlabs_client.conversational_ai.conversations.get(conversation_id)
        transcript = conversation.transcript
    except:
        logger.error(f"Failed to fetch conversation transcript for conversation ID {conversation_id}")

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
        case_study=case_study,
        transcript=formatted_transcript
    )
    grading_response = infer(formatted_transcript, case_study.description)

    try:
        grading_result = json.loads(grading_response)
    except:
        print(grading_response)
        grading_result = next(extract_json(grading_response))

    Grade.create_grade(user=user, conversation_id=conversation_id, overall_summary=grading_result["overall_summary"],
                       final_score=int(grading_result["final_score"]),
                       individual_scores=grading_result["individual_scores"],
                       performance_summary=grading_result["performance_summary"], case_study=case_study)

    return grading_response
