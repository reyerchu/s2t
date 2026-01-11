"""
Groq API Service for Speech-to-Text
支援多 API Key 輪替，突破速率限制
"""
import os
import subprocess
import tempfile
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)
import logging
from groq import Groq
from typing import Optional, Dict, Any, List
from opencc import OpenCC
import re

# 支援多個 API Key（逗號分隔）
GROQ_API_KEYS_STR = os.environ.get("GROQ_API_KEY", "")
GROQ_API_KEYS = [k.strip() for k in GROQ_API_KEYS_STR.split(",") if k.strip()]

MAX_FILE_SIZE_MB = 24
CHUNK_DURATION_SEC = 600

cc = OpenCC('s2twp')

def is_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text))

def get_audio_duration(audio_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except:
        return 0

def split_audio(audio_path: str, chunk_duration: int = CHUNK_DURATION_SEC) -> List[str]:
    duration = get_audio_duration(audio_path)
    if duration == 0:
        return [audio_path]
    
    chunks = []
    temp_dir = tempfile.mkdtemp()
    num_chunks = int(duration / chunk_duration) + 1
    
    logging.info(f"音訊時長: {duration:.1f}秒，分割成 {num_chunks} 個片段")
    
    for i in range(num_chunks):
        start_time = i * chunk_duration
        chunk_path = os.path.join(temp_dir, f"chunk_{i:03d}.wav")
        
        subprocess.run([
            "ffmpeg", "-y", "-i", audio_path,
            "-ss", str(start_time), "-t", str(chunk_duration),
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            chunk_path
        ], capture_output=True)
        
        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 1000:
            chunks.append(chunk_path)
            logging.info(f"已建立片段 {i+1}/{num_chunks}")
    
    return chunks if chunks else [audio_path]

class GroqService:
    def __init__(self):
        self.clients = []
        self.current_client_idx = 0
        self.whisper_model = "whisper-large-v3"
        self.llm_model = "llama-3.3-70b-versatile"
        
        if GROQ_API_KEYS:
            for i, key in enumerate(GROQ_API_KEYS):
                self.clients.append(Groq(api_key=key))
            logging.info(f"Groq 服務已初始化，共 {len(self.clients)} 個 API Key（每小時上限 {len(self.clients) * 2} 小時音訊）")
        else:
            logging.warning("未設定 GROQ_API_KEY")
    
    @property
    def client(self):
        if not self.clients:
            return None
        return self.clients[self.current_client_idx]
    
    def switch_to_next_client(self):
        """切換到下一個 API Key"""
        if len(self.clients) > 1:
            old_idx = self.current_client_idx
            self.current_client_idx = (self.current_client_idx + 1) % len(self.clients)
            logging.info(f"切換 API Key: {old_idx + 1} -> {self.current_client_idx + 1}")
            return True
        return False
    
    def is_available(self) -> bool:
        return len(self.clients) > 0
    
    def to_traditional(self, text: str) -> str:
        if not text:
            return text
        return cc.convert(text)
    
    async def translate_to_chinese(self, text: str) -> str:
        if not self.client or not text.strip():
            return text
        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "你是專業翻譯。將以下文字翻譯成台灣繁體中文。只輸出翻譯結果。"},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=4096
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"翻譯失敗: {str(e)}")
            return text
    
    async def transcribe_chunk_with_retry(self, audio_path: str, language: str, time_offset: float, max_retries: int = 10) -> Dict[str, Any]:
        """轉錄單個片段，含多 Key 輪替和重試邏輯"""
        last_error = None
        keys_tried = set()
        
        for attempt in range(max_retries):
            try:
                with open(audio_path, "rb") as audio_file:
                    transcription = self.client.audio.transcriptions.create(
                        file=(os.path.basename(audio_path), audio_file.read()),
                        model=self.whisper_model,
                        response_format="verbose_json",
                        language=language,
                        temperature=0.0
                    )
                
                detected_lang = getattr(transcription, "language", "unknown")
                original_text = transcription.text
                
                if detected_lang in ["zh", "chinese"] or is_chinese(original_text):
                    processed_text = self.to_traditional(original_text)
                else:
                    processed_text = await self.translate_to_chinese(original_text)
                
                segments = []
                if hasattr(transcription, "segments") and transcription.segments:
                    for seg in transcription.segments:
                        seg_text = seg.get("text", "")
                        if detected_lang in ["zh", "chinese"] or is_chinese(seg_text):
                            processed_seg = self.to_traditional(seg_text)
                        else:
                            processed_seg = seg_text
                        
                        segments.append({
                            "start": seg.get("start", 0) + time_offset,
                            "end": seg.get("end", 0) + time_offset,
                            "text": processed_seg
                        })
                else:
                    segments = [{
                        "start": time_offset,
                        "end": time_offset + getattr(transcription, "duration", 0),
                        "text": processed_text
                    }]
                
                return {
                    "text": processed_text,
                    "language": detected_lang,
                    "segments": segments,
                    "success": True
                }
                
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                if "429" in error_str or "rate_limit" in error_str.lower():
                    keys_tried.add(self.current_client_idx)
                    
                    # 嘗試切換到其他 Key
                    if self.switch_to_next_client():
                        if self.current_client_idx not in keys_tried:
                            logging.info(f"使用新 API Key 重試...")
                            continue
                    
                    # 所有 Key 都試過了，需要等待
                    wait_time = 65
                    match = re.search(r'try again in (\d+)m([\d.]+)s', error_str)
                    if match:
                        wait_time = int(match.group(1)) * 60 + float(match.group(2)) + 10
                    
                    logging.warning(f"所有 API Key 都達到限制，等待 {wait_time:.0f} 秒")
                    keys_tried.clear()  # 重置，下一輪重新嘗試所有 key
                    await asyncio.sleep(wait_time)
                else:
                    logging.error(f"轉錄錯誤: {error_str}")
                    await asyncio.sleep(10)
        
        logging.error(f"片段轉錄失敗: {last_error}")
        return {"text": "", "language": "unknown", "segments": [], "success": False}
    
    async def transcribe(self, audio_path: str, language: str = None) -> Dict[str, Any]:
        if not self.clients:
            raise ValueError("Groq 服務未初始化")
        
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        logging.info(f"音訊檔案大小: {file_size_mb:.2f} MB")
        
        if file_size_mb > MAX_FILE_SIZE_MB:
            logging.info(f"檔案超過 {MAX_FILE_SIZE_MB} MB，進行分割處理")
            chunks = split_audio(audio_path)
            
            all_text = []
            all_segments = []
            detected_lang = "unknown"
            
            for i, chunk_path in enumerate(chunks):
                time_offset = i * CHUNK_DURATION_SEC
                logging.info(f"處理片段 {i+1}/{len(chunks)} (使用 Key {self.current_client_idx + 1}/{len(self.clients)})")
                
                result = await self.transcribe_chunk_with_retry(chunk_path, language, time_offset)
                
                if result["success"]:
                    all_text.append(result["text"])
                    all_segments.extend(result["segments"])
                    detected_lang = result["language"]
                    logging.info(f"片段 {i+1} 完成")
                else:
                    logging.warning(f"片段 {i+1} 失敗")
                
                try:
                    os.remove(chunk_path)
                except:
                    pass
            
            return {
                "text": " ".join(all_text),
                "language": detected_lang,
                "segments": all_segments
            }
        else:
            result = await self.transcribe_chunk_with_retry(audio_path, language, 0)
            return {
                "text": result["text"],
                "language": result["language"],
                "segments": result["segments"]
            }
    
    async def summarize(self, text: str, max_length: int = 500) -> str:
        """使用 LLM 生成文字摘要"""
        if not self.clients or not text.strip():
            return ""
        
        # 如果文字太短，不需要摘要
        if len(text) < 200:
            return text
        
        try:
            logging.info("使用 LLM 生成摘要...")
            
            # 如果文字太長，截取前面部分
            max_input = 6000  # 約 2000 tokens，避免超過 LLM 限制
            input_text = text[:max_input] if len(text) > max_input else text
            
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": """你是專業的內容摘要專家。請為以下內容生成一個簡潔有力的摘要。

要求：
1. 使用繁體中文
2. 摘要長度約 200-500 字
3. 包含主要重點和關鍵資訊
4. 使用條列式格式便於閱讀
5. 開頭先用一句話概述主題

格式：
## 內容摘要

**主題概述**：[一句話概述]

**重點摘要**：
• [重點1]
• [重點2]
• [重點3]
..."""
                    },
                    {"role": "user", "content": input_text}
                ],
                temperature=0.3,
                max_tokens=1024
            )
            
            summary = response.choices[0].message.content.strip()
            logging.info(f"摘要生成完成，長度：{len(summary)} 字")
            return summary
            
        except Exception as e:
            logging.error(f"生成摘要失敗: {str(e)}")
            return ""
    
    async def post_process_segments(self, segments: List[Dict], language: str = "zh") -> tuple:
        full_text = " ".join([seg["text"].strip() for seg in segments])
        return segments, full_text


groq_service = GroqService()
