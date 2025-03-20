import requests
from xml.etree import ElementTree as ET
import os
from ..utils.logger import logger

CAS_SERVICE_VALIDATE_URL = os.getenv('CAS_SERVICE_VALIDATE_URL')

def validate_service_ticket(ticket, service_url):
    params = {
        'ticket': ticket,
        'service': service_url,
        'format': 'json',
    }
    response = requests.get(CAS_SERVICE_VALIDATE_URL, params=params)
    
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