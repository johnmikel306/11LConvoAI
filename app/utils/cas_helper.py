# app/utils/cas_helper.py

from dotenv import load_dotenv
import requests
from xml.etree import ElementTree as ET
from flask import url_for
import os

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

    print("Tickate: \n", ticket, "CAS_SERVICE_VALIDATE_URL: \n", CAS_SERVICE_VALIDATE_URL)
    response = requests.get(CAS_SERVICE_VALIDATE_URL, params=params)
    
    logger.info(f"CAS Validation Response: {response.text}")

    if response.status_code == 200:
        try:
            data = response.json()
            if data.get('serviceResponse', {}).get('authenticationSuccess'):
                return data['serviceResponse']['authenticationSuccess']['user']
        except ValueError:
       
            root = ET.fromstring(response.text)
            namespace = {'cas': 'http://www.yale.edu/tp/cas'}
            user_element = root.find('.//cas:authenticationSuccess/cas:user', namespace)
            if user_element is not None:
                return user_element.text 
    return None 