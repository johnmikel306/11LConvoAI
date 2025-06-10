import os

import requests
from dotenv import load_dotenv

from app.utils.logger import logger

load_dotenv()

API_KEY = os.getenv('ELEVENLABS_API_KEY')
headers = {"Xi-Api-Key": API_KEY}


def get_signed_url(agent_id: str) -> str | None:
    try:
        params = {"agent_id": agent_id}
        r = requests.get(f"https://api.elevenlabs.io/v1/convai/conversation/get-signed-url", params=params,
                         headers=headers)
        data = r.json()
        signed_url = data.get('signed_url')
        logger.info(f"Signed URL for AgentID: {agent_id}: {signed_url}")

        return signed_url
    except Exception as e:
        logger.error(f"Failed to get signed URL for Agent ID: {agent_id}: {e}")
        return None


def get_conversation(conversation_id: str) -> dict | None:
    try:
        r = requests.get(f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}", headers=headers)
        data = r.json()
        return data
    except Exception as e:
        logger.error(f"Failed to get conversation ID: {conversation_id}: {e}")
        return None
