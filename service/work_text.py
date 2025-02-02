import json 
from google.cloud import storage
from google.cloud.speech_v2 import (SpeechClient,
                                    SpeechAsyncClient,
                                    GetRecognizerRequest,
                                    UpdateRecognizerRequest, 
                                    DeleteRecognizerRequest,
                                    ListRecognizersRequest,
                                    RecognizeRequest,
                                   )
from google.cloud.speech_v2.types import (cloud_speech, 
                                          RecognitionConfig, 
                                          RecognitionFeatures, 
                                          SpeakerDiarizationConfig,
                                          AutoDetectDecodingConfig
                                         )
from google.protobuf.json_format import MessageToDict

from service.logger import Logger
from service.singleton import SingletonMeta


class WorkText(metaclass=SingletonMeta):
    """
    Обробка відповіді від моделей STT
    """
    def parseText(self,jsonObject):
        results = jsonObject["results"]
        logger = Logger()
        logger.info(results)
        resultText = ""
        for i in results:
            if "alternatives" in i:
                text = i["alternatives"][0]['transcript']
                resultText+=text
        return resultText

    def make_transcript(self,uri_input_audio,
                        project_id,
                        uri_results_folder,
                        recognizer_name,
                        recognizer_location,
                    ):
        """
        Transcription of longer files via batch_recognize.
        Example:
        uri_results_folder="gs://speech-recognition-pb/results/"
        recognizer="speech-rcg",
        Pure text can be extracted via:
        transcript = result["results"][0]["alternatives"][0]["transcript"].strip()
        """

        reco = self.get_recognizer(recognizer_name, project_id, recognizer_location)
        operation = self.batch_recognize(reco, uri_input_audio, uri_results_folder)
        response = operation.result(timeout=15000)
        result = self.get_speech_v2_results(response, project_id)
        # transcript = result["results"][0]["alternatives"][0]["transcript"].strip()
        # words_ts, text = json_to_words(res_json, version=2)
        # print(result)
        return self.parseText(result)


    def get_recognizer(self,recognizer, project_id, region):
        client = SpeechClient(client_options={"api_endpoint": f"{region}-speech.googleapis.com"})
        request = GetRecognizerRequest(
                    name=f"projects/{project_id}/locations/{region}/recognizers/{recognizer}",
                )
        response = client.get_recognizer(request=request)
        return response



    def batch_recognize(self,recognizer, uri_input_audio, uri_results_folder):
        """
        Recognition without specification of recognizer is also possible (not implemented here).
        Then the recognizer should have the form: recognizer=f"projects/{project_id}/locations/{region}/recognizers/_",
        in this case, a config should be specified in the BatchRecognizeRequest.
        Otherwise a specific recognizer should be provided.
        """
        location = recognizer.name.split("locations/")[1].split("/")[0]
        client = SpeechClient(client_options={"api_endpoint": f"{location}-speech.googleapis.com"})

        output_config = cloud_speech.RecognitionOutputConfig(gcs_output_config=cloud_speech.GcsOutputConfig(
                uri=uri_results_folder)
                )

        files_metadata = [cloud_speech.BatchRecognizeFileMetadata(
                uri=uri_input_audio
            )]

        request = cloud_speech.BatchRecognizeRequest(
            recognizer=recognizer.name,
            # config=config,
            recognition_output_config=output_config,
            files=files_metadata
        )

        # Transcribes the audio into text
        operation = client.batch_recognize(request=request, timeout=1500)
        return operation


    def get_speech_v2_results(self,response, project_id):
        response_json = MessageToDict(response._pb)
        if "error" in list(response_json["results"].values())[0].keys():
            print("Error in transcription process...", response_json)
            return {"results": []}
        res_gs_obj = response_json["results"][list(response_json["results"].keys())[0]]["uri"]
        storage_client = storage.Client(project=project_id)
        bucket = storage_client.get_bucket(res_gs_obj.split("//")[1].split("/")[0])
        blob = bucket.get_blob("/".join(res_gs_obj.split("//")[1].split("/")[1:]))
        res_json = json.loads(blob.download_as_text())
        if len(res_json.keys()) == 0:
            print("Retrieved empty results file...")
            res_json = {"results": []}
        return res_json


    # make_transcript(upload_blob('bucket_audio_euwest3', filename, f'audio/{filename}'),
    #                 project_id,
    #                 "gs://bucket_audio_euwest3/results",
    #                 "chirp2-uk",
    #                 "us-central1")


