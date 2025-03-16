# app/utils/cas_helper.py

import requests
from xml.etree import ElementTree as ET
from flask import url_for
import os

CAS_SERVICE_VALIDATE_URL = os.getenv('CAS_SERVICE_VALIDATE_URL')

def validate_service_ticket(ticket, service_url):
    """
    Validate the Service Ticket (ST) with the CAS server.
    """
    params = {
        'ticket': ticket,
        'service': service_url,
    }
    response = requests.get(CAS_SERVICE_VALIDATE_URL, params=params)
    
    print(response.text)

    if response.status_code == 200:
        # Parse the XML response
        root = ET.fromstring(response.text)
        namespace = {'cas': 'http://www.yale.edu/tp/cas'}
        user_element = root.find('.//cas:authenticationSuccess/cas:user', namespace)

        if user_element is not None:
            return user_element.text  # Return the user's email
    return None  # Return None if validation fails