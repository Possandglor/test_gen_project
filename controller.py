import base64

from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File, Form
from flask import Flask, request, jsonify, send_from_directory
from typing import Dict, List, Any, Optional
import tempfile
import os
from flask import Flask, render_template, request, redirect, url_for, session
from concurrent.futures import ThreadPoolExecutor, as_completed

from service.pws import PowerStone
from service.work_audio import WorkAudio
from service.work_gemini_audio import GeminiTranscription
from service.work_storage import Storage
from service.work_text import WorkText
from service.gemini import Gemini
import time
import json
import docx2txt
from flask_cors import CORS
from service.logger import Logger

app = Flask(__name__, static_url_path='/videosummary/static')
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB

logger = Logger()


@app.route('/videosummary/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


pws = PowerStone()

UPLOAD_FOLDER = 'test'
storage = Storage()
work_text = WorkText()
bucket_name = pws.config.bucket_name
project_id = pws.config.project_id
gemini = Gemini(project_id=project_id)


models_regions = {
    "long-uk": "eu",
    "short": "eu",
    "chirp-uk": "europe-west4",
    "chirp2-uk": "us-central1"
}
recognizer_name = "chirp2-uk"
recognizer_location = "us-central1"
work_audio = WorkAudio()

app.secret_key = 'your_secret_key'


texts = {}



# Параметры для многопоточности
MAX_WORKERS = os.cpu_count() // 2


def process_and_upload_file(filename: str, bucket_name: str) -> str:
    """Обрабатывает аудиофайл и загружает его в Google Cloud Storage."""
    # try:
    #     audio_file = work_audio.convert_to_audio(os.path.join(UPLOAD_FOLDER, filename))
    # except Exception as e:
    #     print(e)
    #     audio_file = os.path.join(UPLOAD_FOLDER, filename)

    # mono_audio = work_audio.convert_to_mono(audio_file)
    # mono_audio = work_audio.extract_audio_to_mono(filename)
    dest_name = '/'.join(filename.split('/')[-2:])
    url = storage.upload_to_blob(bucket_name, filename, f"audio/{dest_name}")

    # Удаляем файлы после обработки
    for file_path in [filename]:
        try:
            os.remove(file_path)
        except Exception as e:
            print(e)

    return url


def transcribe_file_new(filename: str, model: str, project_id: str, bucket_name: str,
                        models_regions: Dict[str, str]) -> str:
    """Выполняет транскрипцию аудиофайла."""
    url = process_and_upload_file(filename=filename, bucket_name=bucket_name)
    if "gemini-1.5" in model:
        geminiTranscript = GeminiTranscription(model, project_id=project_id)
        try:
            return geminiTranscript.getResults(url)
        except Exception as e:
            print(e)
            current_model = "chirp2-uk"
            return work_text.make_transcript(url, project_id, f"gs://{bucket_name}/results", current_model,
                                             models_regions[current_model])
    else:
        return work_text.make_transcript(url, project_id, f"gs://{bucket_name}/results", model, models_regions[model])


def transcribe_large_audio(filename: str, model: str, project_id: str, bucket_name: str,
                           models_regions: Dict[str, str]) -> str:
    """
    Splits a large audio file, processes and transcribes each chunk.
    """
    # Extract audio to mono first
    mono_audio_path = work_audio.extract_audio_to_mono(os.path.join(UPLOAD_FOLDER, filename))

    # Split the audio into smaller chunks
    chunk_files = work_audio.split_audio_to_chunks(mono_audio_path)

    transcripts = []
    # Dictionary to hold chunk index and its transcript
    ordered_transcripts = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(transcribe_file_new, chunk, model, project_id, bucket_name, models_regions): chunk
            for chunk in chunk_files
        }
        for future in as_completed(futures):
            chunk_file = futures[future]
            chunk_index = int(
                os.path.basename(chunk_file).split('_')[1].split('.')[0])  # Extract index from 'chunk_001.mp3'
            ordered_transcripts[chunk_index] = future.result()
            transcripts.append(future.result())

    sorted_transcripts = [ordered_transcripts[index] for index in sorted(ordered_transcripts.keys())]
    complete_transcript = ""
    current_index = 0
    for i in sorted_transcripts:
        complete_transcript += f"""
[{current_index * 3:02}:00] 
{i}"""
        current_index += 1
    # complete_transcript = " ".join(sorted_transcripts)

    # Merge transcripts from all chunks
    # complete_transcript = " ".join(transcripts)
    try:
        os.remove(UPLOAD_FOLDER + "/" + filename)
    except Exception as e:
        print(e)
    try:
        os.remove(mono_audio_path)
    except Exception as e:
        print(e)
    try:
        os.rmdir(f"{mono_audio_path.split('.')[0]}_chunks")
    except Exception as e:
        print(e)

    return complete_transcript


@app.post("/videosummary/summarizeByUrl")
def summarizeByUrl(
        prompt: str = Form(...),
        is_return_text: bool = Form(...),
        file: UploadFile = File(...)) -> Dict[str, Any]:
    prompt = request.form.get('prompt')
    model = request.form.get('model')
    filenames = request.form.get("filenames").split(",")
    urls = []
    transcripts = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(transcribe_large_audio, filename, model, project_id, bucket_name, models_regions) for
                   filename in filenames]
        for future in as_completed(futures):
            transcripts.append(future.result())

    # Постобработка результатов транскрипции с использованием Gemini
    prompt += ": '{text}'"
    summarized_data = gemini.summarize_request(prompt, ' '.join(transcripts))

    response = {
        "summarized_data": summarized_data
    }

    if is_return_text:
        response["transcript"] = """
""".join(transcripts)

    # Удаление загруженных файлов из GCS
    for url in urls:
        mono_audio_name = url.split("/")[-1]
        try:
            storage.delete_from_blob(bucket_name, f"audio/{mono_audio_name}")
        except Exception as e:
            print(e)

    return response


@app.post("/videosummary/summarizeByUrl_backup")
def summarizeByUrl_backup(
        prompt: str = Form(...),
        is_return_text: bool = Form(...),
        file: UploadFile = File(...)) -> Dict[str, Any]:
    prompt = request.form.get('prompt') if request != None else prompt
    model = request.form.get('model')
    is_return_text = (request.form.get('is_return_text') == "True" or request.form.get(
        'is_return_text') == "on") if request != None else is_return_text
    # api_key = get_api_key()
    filenames = request.form.get("filenames").split(",")
    transcripts = []
    urls = []
    for filename in filenames:
        try:
            audio_file = work_audio.convert_to_audio(os.getcwd() + "/" + UPLOAD_FOLDER + "/" + filename)
        except Exception as e:
            print(e)
            audio_file = os.getcwd() + "/" + UPLOAD_FOLDER + "/" + filename
        mono_audio = work_audio.convert_to_mono(audio_file)
        url = storage.upload_to_blob(bucket_name, mono_audio, "audio/" + mono_audio.split("/")[-1])
        # url = request.form.get('url')
        urls.append(url)
        try:
            os.remove(UPLOAD_FOLDER + "/" + filename)
        except Exception as e:
            print(e)

        try:
            os.remove(audio_file)
        except Exception as e:
            print(e)

        try:
            os.remove(mono_audio)
        except Exception as e:
            print(e)

    if "gemini-1.5" in model:
        geminiTranscript = GeminiTranscription(model, project_id=project_id)
        for url in urls:
            try:

                result = geminiTranscript.getResults(url, prompt)
                transcripts.append(result)
            except:
                current_model = "chirp2-uk"
                transcript = work_text.make_transcript(url, project_id, f"gs://{bucket_name}/results", current_model,
                                                       models_regions[current_model])
                transcripts.append(transcript)
            time.sleep(5)
    else:
        for url in urls:
            transcript = work_text.make_transcript(url, project_id, f"gs://{bucket_name}/results", model,
                                                   models_regions[model])
            transcripts.append(transcript)
            time.sleep(5)

    prompt = prompt + ": '{text}'"
    summirized_data = gemini.summarize_request(prompt, ' '.join(transcripts))

    response = {
        "summirized_data": summirized_data
    }
    if is_return_text:
        response["transcript"] = " ".join(transcripts)
    try:

        storage.delete_from_blob(bucket_name, f"audio/{mono_audio.split('/')[-1]}")
    except Exception as e:
        print(e)
        a = 5
    return response


@app.post("/videosummary/summarizeDocByUrl")
def summarizeDocByUrl(
        prompt: str = Form(...),
        is_return_text: bool = Form(...),
        file: UploadFile = File(...)) -> Dict[str, Any]:
    prompt = request.form.get('prompt') if request != None else prompt
    prompt = f"Ти - експерт з розбирання текстових даних та роз'яснень, що у цих файлах відбувається. З огляду на це, дай відповідь на питання: {prompt} " + "{text}"
    model = request.form.get('model')
    is_return_text = (request.form.get('is_return_text') == "True" or request.form.get(
        'is_return_text') == "on") if request != None else is_return_text
    # api_key = get_api_key()
    filenames = request.form.get("filenames").split(",")

    transcripts = []
    urls = []
    for filename in filenames:

        file_path = os.getcwd() + "/" + UPLOAD_FOLDER + "/" + filename
        # Example usage:
        # text = read_docx(file_path)

        # Example usage:
        text = docx2txt.process(file_path)
        transcripts.append(text)
        # print(text)

        # url = upload_to_blob(bucket_name,file_path,"files/"+file_path.split("/")[-1])
        # url = request.form.get('url')
        # urls.append(url)
        try:
            os.remove(UPLOAD_FOLDER + "/" + filename)
        except Exception as e:
            print(e)

    # geminiTranscript = GeminiTranscription(model)
    # result = geminiTranscript.getResultsDoc(urls,prompt)
    result = gemini.summarize_request(prompt, ' '.join(transcripts))
    response = {
        "summirized_data": result
    }

    return response


def split_text(text, max_length=5000):
    # Розділення тексту на частини по 5000 символів
    chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)]
    return chunks


@app.post("/videosummary/gettext")
def getText():
    id = int(request.form.get('id'))
    part = int(request.form.get('part'))

    return texts[id][part]


@app.route('/videosummary/')
def home():
    return redirect(url_for('main'))

@app.route('/videosummary/main', methods=['GET', 'POST'])
def main():
    return render_template('index.html')

@app.route('/videosummary/get_user_data')
def get_user_data():
    if 'logged_in' in session:
        return jsonify({"login": session["login"], "result_check": session["result_check"]})
    else:
        return jsonify({"error": "User not logged in"}), 401


@app.route('/videosummary/upload-chunk', methods=['POST'])
def upload_chunk():
    file_chunk = request.files['fileChunk']
    chunk_index = request.form['chunkIndex']
    file_name = request.form['fileName']

    chunk_filename = f"{UPLOAD_FOLDER}/{file_name}.part{chunk_index}"

    with open(chunk_filename, 'wb') as chunk_file:
        chunk_file.write(file_chunk.read())

    return jsonify({"message": "Chunk uploaded successfully"}), 200


@app.route('/videosummary/complete-upload', methods=['POST'])
async def complete_upload():
    data = request.get_json()
    file_name = data['fileName']
    total_chunks = data['totalChunks']

    with open(f"{UPLOAD_FOLDER}/{file_name}", 'wb') as final_file:
        for i in range(total_chunks):
            chunk_filename = f"{UPLOAD_FOLDER}/{file_name}.part{i}"
            with open(chunk_filename, 'rb') as chunk_file:
                final_file.write(chunk_file.read())
            os.remove(chunk_filename)

    return jsonify({"message": "Upload complete"}), 200


@app.post("/videosummary/summarizeaudio")
async def summarize_audio_less_32mb():
    is_return_text = bool(request.form.get('is_return_text', 'True').lower() in ['true', '1', 'yes', 'on'])
    is_return_summarize = bool(request.form.get('is_return_summarize', 'False').lower() in ['true', '1', 'yes', 'on'])

    file = request.files['file']
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
        contents = file.read()
        temp_file.write(contents)
        temp_file_path = temp_file.name

    mono_audio = work_audio.convert_to_mono(temp_file_path)
    url = storage.upload_to_blob(bucket_name, mono_audio, "audio/" + mono_audio.split("/")[-1])
    # url = request.form.get('url')

    try:
        os.remove(temp_file_path)
    except Exception as e:
        print(e)

    try:
        os.remove(mono_audio)
    except Exception as e:
        print(e)
    response = {}
    transcript = work_text.make_transcript(url, project_id, f"gs://{bucket_name}/results", recognizer_name,
                                           recognizer_location)

    if is_return_text:
        response['transcript'] = transcript
    if is_return_summarize:
        prompt = request.form['prompt']
        prompt = prompt + ': "{text}"'
        summirized_data = gemini.summarize_request(prompt, transcript)

        response["summirized_data"] = summirized_data

    try:

        storage.delete_from_blob(bucket_name, f"audio/{mono_audio.split('/')[-1]}")
    except Exception as e:
        print(e)
        a = 5
    return response


@app.post("/videosummary/summary_test")
async def test_summary() -> Dict[str, Any]:
    """
    Суммаризація діалогів після заливки іх через апі заливки
    Шаблонні відповіді на різні запити
    :param files:
    :param prompt:
    :param model:
    :param is_return_transcription:
    :return:
    """
    logger.info(request.data)

    request_data = request.json
    files_data = request_data.get("files", [])
    model = request_data.get("model")
    is_return_transcription = request_data.get("is_return_transcription", False)
    prompt = request_data.get("prompt")

    summary_results = []

    # Используем ThreadPoolExecutor для обработки транскрипции в нескольких потоках
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for file_group in files_data:
            logger.log(file_group)
            # Собираем все аудиофайлы и callback'и для транскрипции
            file_names = [file_group.get("audio")] + [file_group.get(cb) for cb in ["callBack1", "callBack2"] if
                                                      file_group.get(cb)]
            # Запускаем транскрипцию для всех файлов в группе
            futures.append(
                executor.submit(transcribe_files_group, file_names, model)
            )

        for idx, future in enumerate(as_completed(futures)):
            transcripts = future.result()  # Результат транскрипции для группы файлов

            # Объединяем транскрипции и создаем полный текст для суммаризации
            full_transcript = " ".join(transcripts)
            summary = gemini.summarize_request(prompt + ": {text}", full_transcript)

            # Формируем результат для каждого блока
            summary_results.append({
                "ID": files_data[idx]["audio"].split(".")[0],  # Используем имя файла без расширения как ID
                "Summary": summary,
                "Transcription": full_transcript if is_return_transcription else None
            })

    response = {
        "summarys": summary_results,
        "Message": "ok"
    }

    return response


@app.post("/videosummary/summary_csv")
async def csv_summary() -> Dict[str, Any]:
    """
    Summarization csv file with gemini
    input params - file, prompt, model
    :return:
    """
    logger.info(request.data)
    file = request.files["file"]
    prompt = request.form.get("prompt") + " {text}"
    model = request.form.get("model")

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
        contents = file.read()
        temp_file.write(contents)
        temp_file_path = temp_file.name

    # read text from input file to  string
    with open(temp_file_path, "r") as f:
        client_text = f.read()
        logger.log(client_text)

    os.remove(temp_file_path)

    summary = gemini.summarize_request(prompt, client_text, model)

    # Формируем результат
    response = {
        "summary": summary,
        "Message": "ok"
    }

    return response


@app.post("/videosummary/summary_docx")
async def docx_summary() -> Dict[str, Any]:
    """
    Summarization docx file with gemini
    input params - file, prompt, model
    :return:
    """
    logger.info(request.data)
    file = request.files["file"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
        contents = file.read()
        temp_file.write(contents)
        temp_file_path = temp_file.name

    prompt = request.form.get("prompt") + " {text}"
    model = request.form.get("model")

    # read text from input file to  string
    # with open(os.path.join(os.getcwd(), UPLOAD_FOLDER, file), "r") as f:
    client_text = docx2txt.process(temp_file_path)

    os.remove(temp_file_path)

    summary = gemini.summarize_request(prompt, client_text, model)

    # Формируем результат
    response = {
        "summary": summary,
        "Message": "ok"
    }

    return response


def transcribe_files_group(filenames: List[str], model: str) -> List[str]:
    transcripts = []
    for filename in filenames:
        # Выполняем транскрипцию для каждого файла
        transcript = transcribe_large_audio(filename, model, project_id, bucket_name, models_regions)
        logger.info(filename)
        logger.info(transcript)
        transcripts.append(transcript)

    return transcripts


@app.get("/videosummary/getfiles")
def get_files():
    files = os.listdir(UPLOAD_FOLDER)
    return jsonify(files)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
