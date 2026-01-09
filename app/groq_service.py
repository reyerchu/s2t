"""
Groq API Service for Speech-to-Text
使用 Groq 的免費 API 進行語音辨識
使用 OpenCC 進行簡繁轉換
使用 LLM 進行非中文翻譯
"""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)
import logging
from groq import Groq
from typing import Optional, Dict, Any, List
from opencc import OpenCC
import re

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# 初始化 OpenCC 簡體轉繁體（台灣標準）
cc = OpenCC('s2twp')

def is_chinese(text):
    """檢查文字是否包含中文"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))

class GroqService:
    def __init__(self):
        self.client = None
        self.whisper_model = "whisper-large-v3"
        self.llm_model = "llama-3.3-70b-versatile"
        
        if GROQ_API_KEY:
            self.client = Groq(api_key=GROQ_API_KEY)
            logging.info(f"Groq 服務已初始化 (Whisper: {self.whisper_model})")
        else:
            logging.warning("未設定 GROQ_API_KEY，將使用本地 Whisper 模型")
    
    def is_available(self) -> bool:
        return self.client is not None
    
    def to_traditional(self, text: str) -> str:
        """使用 OpenCC 將簡體中文轉換為繁體中文（台灣標準）"""
        if not text:
            return text
        return cc.convert(text)
    
    async def translate_to_chinese(self, text: str) -> str:
        """使用 LLM 將非中文文字翻譯為繁體中文"""
        if not self.client or not text.strip():
            return text
        
        try:
            logging.info("使用 LLM 翻譯為繁體中文")
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "你是專業翻譯。將以下文字翻譯成台灣繁體中文。只輸出翻譯結果，不要任何解釋。"},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                max_tokens=4096
            )
            translated = response.choices[0].message.content.strip()
            logging.info("翻譯完成")
            return translated
        except Exception as e:
            logging.error(f"翻譯失敗: {str(e)}")
            return text
    
    async def transcribe(self, audio_path: str, language: str = None) -> Dict[str, Any]:
        if not self.client:
            raise ValueError("Groq 服務未初始化")
        
        logging.info(f"使用 Groq Whisper large-v3 進行轉錄: {audio_path}")
        
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
            
            # 根據語言決定處理方式
            if detected_lang in ["zh", "chinese"] or is_chinese(original_text):
                # 中文：使用 OpenCC 轉繁體
                processed_text = self.to_traditional(original_text)
                logging.info("檢測到中文，使用 OpenCC 轉換繁體")
            else:
                # 非中文：翻譯為繁體中文
                processed_text = await self.translate_to_chinese(original_text)
                logging.info(f"檢測到 {detected_lang}，已翻譯為繁體中文")
            
            result = {
                "text": processed_text,
                "language": detected_lang,
                "segments": []
            }
            
            if hasattr(transcription, "segments") and transcription.segments:
                for seg in transcription.segments:
                    seg_text = seg.get("text", "")
                    if detected_lang in ["zh", "chinese"] or is_chinese(seg_text):
                        processed_seg = self.to_traditional(seg_text)
                    else:
                        processed_seg = await self.translate_to_chinese(seg_text)
                    
                    result["segments"].append({
                        "start": seg.get("start", 0),
                        "end": seg.get("end", 0),
                        "text": processed_seg
                    })
            else:
                result["segments"] = [{
                    "start": 0,
                    "end": getattr(transcription, "duration", 0),
                    "text": processed_text
                }]
            
            logging.info(f"Groq 轉錄完成，語言: {detected_lang}, 段落數: {len(result['segments'])}")
            return result
            
        except Exception as e:
            logging.error(f"Groq 轉錄失敗: {str(e)}")
            raise
    
    async def post_process_segments(self, segments: List[Dict], language: str = "zh") -> tuple:
        full_text = " ".join([seg["text"].strip() for seg in segments])
        return segments, full_text


groq_service = GroqService()
