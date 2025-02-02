from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI
from service.singleton import SingletonMeta
import re
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from service.logger import Logger

class GeminiTranscription(metaclass=SingletonMeta):
    def __init__(self,modelname, project_id):
        # Use Gemini 1.5 Pro
        self.project_id = project_id
        self.llm = ChatVertexAI(model_name=modelname)
        self.model = GenerativeModel(modelname)
        self.logger = Logger()

    def getResults(self,url):
        prompt = """
        You are a expert in understaning transcribed text and formatting to usefull format.
        Can you transcribe this interview, in the format of speaker, caption.
        Use speaker A, speaker B, etc. to identify speakers.
        """
        self.logger.log(url)
        audio_file_uri = url
        audio_file = Part.from_uri(audio_file_uri, mime_type="audio/mpeg")

        contents = [audio_file, prompt]
        print(url+" was started")

        response = self.model.generate_content(contents)
        if self.find_artifacts(response.text):
            response = self.model.generate_content(contents)
        print(url+" was ended")
        return response.text
    
    def getResultOldAudio(self, url):
        # Use Gemini 1.5 Pro
        llm = ChatVertexAI(model_name="gemini-1.5-flash-001")

        # Prepare input for model consumption
        media_message = {
            "type": "image_url",
            "image_url": {
                "url": url,
            },
        }

        text_message = {
            "type": "text",
            "text": """Транскрибуй текст аудіо""",
        }

        message = HumanMessage(content=[media_message, text_message])
        # invoke a model response
        result = llm.invoke([message])
        if self.find_artifacts(result.content):
            result = llm.invoke([message])

        return result.content
    
    def find_artifacts(self,text):
        """
        Пошук артефактів у тексті
        Артефактами є повторні беззмістовні куски тексту
        :param text:
        :return:
        """
        pattern = r"(\b\w+\b[^\w]*)\1{3,}"
        artifacts = re.findall(pattern, text, re.IGNORECASE)
        return artifacts
    
    def getResultsDoc(self,urls,text):
        """
        Обробка документів
        :param urls:
        :param text:
        :return:
        """
        media_messages = []
        for url in urls:
            media_messagecurrent = {
                "type": "image_url",
                "image_url": {
                    "url": url,
                },
            }
            media_messages.append(media_messagecurrent)

        text_message = {
            "type": "text",
            "text": """Ти - експерт з обробки файлів діалогів операторів і клиєнтів, """+text,
        }

        media_message = HumanMessage(content=media_messages+[text_message])
        # invoke a model response
        result = self.llm.invoke([media_message])

        return result.contentY
    
