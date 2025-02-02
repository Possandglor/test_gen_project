from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import os
from service.singleton import SingletonMeta
import av
import subprocess
class WorkAudio(metaclass=SingletonMeta):
    """
    Клас обробки відео та аудіо. Основна ціль: з медіа файлу зробити wav з однією доріжкою аудіо.
    """
    def convert_to_audio(self, filename):
        """
        Перетворення відео на аудіо
        :param filename:
        :return:
        """
        video = VideoFileClip(filename)

        # Извлекаем аудио из видео
        audio = video.audio
        del video
        new_filename = f"{filename.split('.')[0]}_output.mp3"
        audio.write_audiofile(new_filename)
        video.close()
        del video
        
        return new_filename
    
    def convert_to_mono(self, filename):
        """
        Об'єднання доріжок до однієї через лібу pydub
        :param filename:
        :return:
        """
        stereo_audio = AudioSegment.from_file(f"{filename}")

        mono_audio = stereo_audio.set_channels(1)

        mono_filename = f"{filename.split('.')[0]}_mono_audio.mp3"
        mono_audio.export(mono_filename, format="mp3")
        del stereo_audio
        return mono_filename

    def extract_audio_to_mono(self,input_video_path):
        """
         Об'єднання доріжок до однієї через системний ffmpeg (цей швидше працює)
        :param input_video_path:
        :return:
        """
        output_audio_path = f"{input_video_path.split('.')[0]}_mono_audio.mp3"
        command = [
            "ffmpeg",
            "-y",
            "-i", input_video_path,      # Входной видеофайл
            "-ac", "1",                  # Преобразовать в моно (1 канал)
            output_audio_path            # Путь для сохранения аудио
        ]
        subprocess.run(command, check=True)
        return output_audio_path
    

    def split_audio_to_chunks(self,input_audio_path, chunk_duration=300):
        """
        Розділення аудіо на частини для паралельної обробки.
        """
        # Output directory
        output_dir = f"{input_audio_path.split('.')[0]}_chunks"
        os.makedirs(output_dir, exist_ok=True)

        # Command to split audio into chunks
        command = [
            "ffmpeg",
            "-i", input_audio_path,                  # Input audio file
            "-f", "segment",                         # Segment format
            "-segment_time", str(chunk_duration),    # Duration of each chunk in seconds
            "-c", "copy",                            # Copy the codec (no re-encoding)
            f"{output_dir}/chunk_%03d.mp3"           # Output format (chunk_001.mp3, chunk_002.mp3, ...)
        ]
        # disable subprocess output
        command.append("-loglevel")
        command.append("quiet")

        subprocess.run(command, check=True)

        # Get the list of chunk files
        chunk_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir)]
        
        return chunk_files