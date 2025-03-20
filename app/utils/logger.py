import logging
import json
import os

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(log_record)

def setup_logger():
  
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

  
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

 
    logger.addHandler(handler)

    return logger


logger = setup_logger()