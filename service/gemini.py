from service.logger import Logger
from service.vertexai_service import VertexAIService
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from service.singleton import SingletonMeta


class Gemini(metaclass=SingletonMeta):
    """
    Окремий клас для обробки текстових запитів.
    """
    def __init__(self, project_id) -> None:
        self.vertex_ai_service = VertexAIService(project_id=project_id)
        self.logger = Logger()

    def get_llm_chain_custom_prompt(self, custom_prompt, model_name):
        region = 'europe-west3'
        llm = self.vertex_ai_service.get_llm_model(model_name=model_name, region=region)
        gen_intents_from_predefined_prompt = PromptTemplate(input_variables=["text"], template=custom_prompt)

        return gen_intents_from_predefined_prompt | llm | StrOutputParser()

    def summarize_request(self, custom_prompt, transcription, model="gemini-1.5-flash-001"):
        # if intents == 'custom' and custom_prompt:
        self.logger.info(custom_prompt)
        self.logger.info(transcription)
        chain = self.get_llm_chain_custom_prompt(custom_prompt=f"{custom_prompt}", model_name=model)
        result_roots = chain.invoke({'text': transcription})

        return result_roots
