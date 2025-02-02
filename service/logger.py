from service.singleton import SingletonMeta
from google.cloud import logging as cloud_logging
import logging
from service.pws import PowerStone

class Logger(metaclass=SingletonMeta):
    """
    Логер у стандартні логи додатку на GCP
    """
    def __init__(self):
        self.pws = PowerStone()
        self.client = cloud_logging.Client(project=self.pws.config.project_id)
        self.client.setup_logging()
        self.logger = logging.getLogger("cloudLogger")

    def log(self, text):
        self.logger.log(0,text)

    def info(self, text):
        self.logger.info(text)

    def error(self, text):
        self.logger.error(text)