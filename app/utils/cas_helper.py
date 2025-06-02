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
            logger.info("Response was not JSON, attempting XML parsing.")
            try:
                root = ET.fromstring(response.text)
                namespace = {'cas': 'http://www.yale.edu/tp/cas'}

                auth_success_node = root.find('cas:authenticationSuccess', namespace) # More direct path from root
                if auth_success_node is None: # Try with .// if structure can be deeper
                    auth_success_node = root.find('.//cas:authenticationSuccess', namespace)

                if auth_success_node is not None:
                    user_email_node = auth_success_node.find('cas:user', namespace)
                    user_email_text = user_email_node.text if user_email_node is not None else None

                    attributes_node = auth_success_node.find('cas:attributes', namespace)
                    user_first_name_text = None
                    user_last_name_text = None

                    if attributes_node is not None:
                        first_name_node = attributes_node.find('cas:firstname', namespace)
                        if first_name_node is not None:
                            user_first_name_text = first_name_node.text

                        last_name_node = attributes_node.find('cas:lastname', namespace)
                        if last_name_node is not None:
                            user_last_name_text = last_name_node.text

                    if user_email_text:
                        return {
                            "email": user_email_text,
                            "firstname": user_first_name_text,
                            "lastname": user_last_name_text
                        }
            except ET.ParseError:
                logger.error("Failed to parse XML response.")

    return None
