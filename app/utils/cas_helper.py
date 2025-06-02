# app/utils/cas_helper.py

import os
from xml.etree import ElementTree as ET

import requests
from dotenv import load_dotenv

from ..utils.logger import logger

load_dotenv()

CAS_SERVICE_VALIDATE_URL = os.getenv('CAS_SERVICE_VALIDATE_URL')


def validate_service_ticket(ticket, service_url):
    """
    Validate the Service Ticket (ST) with the CAS server.
    """
    params = {
        'ticket': ticket,
        'service': service_url,
        'format': 'json'
    }

    response = requests.get(CAS_SERVICE_VALIDATE_URL, params=params)

    logger.info(f"CAS Validation Response: {response.text}")

    if response.status_code == 200:
        try:
            data = response.json()
            if data.get('serviceResponse', {}).get('authenticationSuccess'):
                user_email: str | None = data['serviceResponse']['authenticationSuccess']['user']
                user_first_name: str | None = data['serviceResponse']['authenticationSuccess']['firstname']
                user_last_name: str | None = data['serviceResponse']['authenticationSuccess']['lastname']
                return {
                    "email": user_email,
                    "firstname": user_first_name,
                    "lastname": user_last_name
                } if user_email else None
        except ValueError:

            root = ET.fromstring(response.text)
            namespace = {'cas': 'http://www.yale.edu/tp/cas'}
            user_email = root.find('.//cas:authenticationSuccess/cas:email', namespace)
            user_first_name = root.find('.//cas:authenticationSuccess/cas:firstname', namespace)
            user_last_name = root.find('.//cas:authenticationSuccess/cas:lastname', namespace)
            return {
                "email": user_email.text,
                "firstname": user_first_name.text if user_first_name is not None else None,
                "lastname": user_last_name.text if user_last_name is not None else None
            } if user_email is not None else None
    return None
