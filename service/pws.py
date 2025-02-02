from enum import Enum
from requests.exceptions import RequestException
from service.singleton import SingletonMeta

class PowerStoneParams(Enum):
    BUCKET_NAME = "bucket_name"
    PROJECT_ID = "project_id"


class Config:
    """
    Перелік параметрів
    """
    def __init__(self, params):
        self._params = params

    def get(self, key, default=""):
        return self._params.get(key.value, default)

    @property
    def bucket_name(self):
        return self.get(PowerStoneParams.BUCKET_NAME)

    @property
    def project_id(self):
        return self.get(PowerStoneParams.PROJECT_ID)



class PowerStone(metaclass=SingletonMeta):
    """
    Клас необхідний для отримання налаштувань з системи зберігання сек'юрних даних
    Для тестового проєкту дані прописані статично
    """
    def __init__(self):
        self.config = self._initialize_config()

    def _initialize_config(self):
        try:
            params = {
                      'project_id': 'itt-cc-miu',
                      'bucket_name': 'bucket_audio_euwest3'
            }
            return Config(params)
        except RequestException as e:
            print(f"Error fetching parameters: {e}")
            return Config({})  # empty config in case of error