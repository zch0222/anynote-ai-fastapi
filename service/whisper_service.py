import json
import os
import torch
import uuid
from core.config import WHISPER_MODEL
import whisper
from model.dto import WhisperRunDTO
from model.vo import WhisperRunVO, WhisperSubmitVO
from utils.file_util import download_file
from constants.whisper_constants import WHISPER_MEDIA_DIR, WHISPER_MEDIA_AUDIO_DIR, WHISPER_SRT_DIR, WHISPER_MINIO_SRT_DIR, WHISPER_TXT_DIR, WHISPER_MINIO_TXT_DIR
import datetime
from core.minio_server import MinioServer
from core.aio_redis_server import AIORedisServer
from constants.redis_channel_constants import WHISPER_STATUS_CHANNEL
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor

import asyncio
import time

class WhisperService:

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.minio_server = MinioServer()
        os.makedirs(WHISPER_SRT_DIR, exist_ok=True)
        os.makedirs(WHISPER_TXT_DIR, exist_ok=True)
        self.executor = ProcessPoolExecutor()
        # self.model = whisper.model(WHISPER_MODEL)

    def __del__(self):
        print("CLOSE executor----------------------")
        self.executor.shutdown(wait=True)


    # 将解码结果保存为 SRT 文件
    def save_srt(self, result, srt_file):
        def format_timestamp(seconds):
            ms = int((seconds - int(seconds)) * 1000)
            td = datetime.timedelta(seconds=int(seconds))
            return f"{str(td):0>8},{ms:03d}"

        with open(srt_file, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(result['segments'], start=1):
                start = format_timestamp(segment['start'])
                end = format_timestamp(segment['end'])
                text = segment['text'].strip()
                f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

    def save_txt(self, result, txt_file: str):
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(result["text"])

    async def run_whisper(self, whisper_run_dto: WhisperRunDTO, channel: str):
        print(self.device)
        model = whisper.load_model(WHISPER_MODEL).to(self.device)
        audio_file = download_file(whisper_run_dto.url, WHISPER_MEDIA_DIR)
        # audio_path = f"{WHISPER_MEDIA_AUDIO_DIR}/{audio_file.hash_value}.mp3"
        # extract_sound(audio_file.file_path, audio_path)
        # audio = whisper.load_audio(audio_file.file_path)
        # audio = whisper.pad_or_trim(audio)
        # mel = whisper.log_mel_spectrogram(audio).to(model.device).to(self.device)
        # _, probs = model.detect_language(mel)
        # print(f"Detected language: {max(probs, key=probs.get)}")
        # options = whisper.DecodingOptions(language=whisper_run_dto.language)
        # result = whisper.decode(model, mel, options)
        await AIORedisServer().publish(channel, {
            "status": "running"
        })
        result = model.transcribe(audio_file.file_path, language=whisper_run_dto.language)
        srt_file = f"{WHISPER_SRT_DIR}/{audio_file.hash_value}.srt"
        txt_file = f"{WHISPER_TXT_DIR}/{audio_file.hash_value}.txt"
        self.save_srt(result, srt_file)
        self.save_txt(result, txt_file)
        srt_url = self.minio_server.upload(srt_file, f"{WHISPER_MINIO_SRT_DIR}/{audio_file.hash_value}.srt")
        txt_url = self.minio_server.upload(txt_file, f"{WHISPER_MINIO_TXT_DIR}/{audio_file.hash_value}.txt")
        # print(json.dumps(result, indent=2))
        await AIORedisServer().publish(channel, {
            "status": "finished",
            "data": WhisperRunVO(text=result["text"],
                                    srt=srt_url,
                                    txt=txt_url).to_dict()
        })

    def on_whisper_status_message(self, message):
        yield 'id: {}\nevent: message\ndata: {}\n\n'.format(int(time.time()), message)

    async def heartbeat(self, channel: str):
        while True:
            print("HEARTBEAT-----------------------------------------------")
            await AIORedisServer().publish(channel, {
                "status": "running"
            })
            await asyncio.sleep(10)

    def submit_whisper_task(self, whisper_run_dto: WhisperRunDTO):
        task_id = uuid.uuid4().__str__()
        channel = f"{WHISPER_STATUS_CHANNEL}:{task_id}"
        run_whisper_task = asyncio.create_task(self.run_whisper(whisper_run_dto, channel))
        return WhisperSubmitVO(task_id=task_id)


    async def whisper(self, whisper_run_dto: WhisperRunDTO):
        task_id = uuid.uuid4().__str__()
        loop = asyncio.get_running_loop()
        channel = f"{WHISPER_STATUS_CHANNEL}:{task_id}"
        run_whisper_task = asyncio.create_task(self.run_whisper(whisper_run_dto, channel))
        heartbeat_task = asyncio.create_task(self.heartbeat(channel))
        yield 'id: {}\nevent: message\ndata: {}\n\n'.format(int(time.time()), {
            "status": "running"
        })
        try:
            async for message in AIORedisServer().subscribe(channel):
                if message["status"] == "finished":
                    heartbeat_task.cancel()
                yield 'id: {}\nevent: message\ndata: {}\n\n'.format(int(time.time()), json.dumps(message))
        except asyncio.CancelledError:
            run_whisper_task.cancel()
            heartbeat_task.cancel()
            print("Client disconnected. All tasks are cancelled.")
        finally:
            # 确保所有任务都被取消或完成
            if not run_whisper_task.done():
                run_whisper_task.cancel()
            if not heartbeat_task.done():
                heartbeat_task.cancel()

        await asyncio.gather(run_whisper_task, heartbeat_task, return_exceptions=True)
        print("Tasks are cleaned up after client disconnected or task completed.")

    async def get_whisper_task_status(self, task_id):
        channel = f"{WHISPER_STATUS_CHANNEL}:{task_id}"
        heartbeat_task = asyncio.create_task(self.heartbeat(channel))
        try:
            async for message in AIORedisServer().subscribe(channel):
                if message["status"] == "finished":
                    heartbeat_task.cancel()
                yield 'id: {}\nevent: message\ndata: {}\n\n'.format(int(time.time()), json.dumps(message))
        except asyncio.CancelledError:
            heartbeat_task.cancel()
            print("Client disconnected. All tasks are cancelled.")
        finally:
            # 确保所有任务都被取消或完成
            if not heartbeat_task.done():
                heartbeat_task.cancel()

        await asyncio.gather(heartbeat_task, return_exceptions=True)
        print("Tasks are cleaned up after client disconnected or task completed.")

