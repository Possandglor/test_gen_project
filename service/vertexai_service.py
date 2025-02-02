import vertexai
from langchain_google_vertexai import VertexAI
from langchain_google_vertexai import HarmBlockThreshold, HarmCategory
from service.singleton import SingletonMeta

class VertexAIService(metaclass=SingletonMeta):
    def __init__(self, project_id, max_output_tokens=4192):
        self.project_id = project_id
        self.max_output_tokens = max_output_tokens
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
        }

    def get_llm_model(self, model_name, region, temperature=0):
        self._change_vertexai_region(region)
        return VertexAI(model_name=model_name, temperature=temperature, project=self.project_id, verbose=False,
                            max_output_tokens=self.max_output_tokens, location=region, stop=[],
                            safety_settings=self.safety_settings, max_retries=0)

    def _change_vertexai_region(self, region):
        vertexai.init(project=self.project_id, location=region)
