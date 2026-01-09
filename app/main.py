from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
import shutil
import uuid
import tempfile
import subprocess
from pathlib import Path
import logging
import traceback
import whisper
import zipfile
from typing import List, Dict, Any, Optional
import yt_dlp
from app.groq_service import groq_service

# 添加 Node.js 到 PATH（yt-dlp 需要 JS 運行時）
os.environ["PATH"] = "/home/reyerchu/.nvm/versions/node/v20.19.6/bin:" + os.environ.get("PATH", "")

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

app = FastAPI(
    title="Speech to Text API",
    description="音頻轉文字 API 服務 (Port 8002)",
    docs_url="/s2t/api/docs",
    openapi_url="/s2t/api/openapi.json",
)

# 服務前端靜態檔案
app.mount("/s2t/static", StaticFiles(directory="/home/reyerchu/s2t/s2t/frontend/build/static"), name="static")

@app.get("/s2t", response_class=HTMLResponse)
@app.get("/s2t/{path:path}", response_class=HTMLResponse)
async def serve_frontend(path: str = ""):
    if path.startswith("api") or path.startswith("static"):
        return
    with open("/home/reyerchu/s2t/s2t/frontend/build/index.html", "r") as f:
        return HTMLResponse(content=f.read())

# 允許跨域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 設置子路徑前綴
PREFIX = "/s2t/api"

class TranscriptionRequest:
    def __init__(self, file: UploadFile, output_formats: List[str]):
        self.file = file
        self.output_formats = output_formats

class PasswordModel(BaseModel):
    password: str

ROOT_PASSWORD = "admin123"  # 在實際應用中，應該使用更安全的方式存儲和驗證密碼

class LinkRequest(BaseModel):
    url: str
    output_formats: List[str]

class TranscriptionService:
    def __init__(self):
        self.use_groq = groq_service.is_available()
        if self.use_groq:
            logging.info("使用 Groq Whisper large-v3 API")
            self.model = None
        else:
            self.model = whisper.load_model("small")
            logging.info("使用本地 Whisper small 模型")

    async def process_audio(self, request: TranscriptionRequest) -> Dict[str, Any]:
        logging.info(f"處理音頻文件: {request.file.filename}")
        
        # 建立唯一工作目錄
        session_id = str(uuid.uuid4())
        temp_dir = Path("temp") / session_id
        os.makedirs(temp_dir, exist_ok=True)
        logging.info(f"建立臨時目錄: {temp_dir}")
        
        try:
            # 保存上傳的文件
            original_filename = request.file.filename
            file_extension = os.path.splitext(original_filename)[1]
            input_path = temp_dir / f"input{file_extension}"
            
            with open(input_path, "wb") as f:
                content = await request.file.read()
                f.write(content)
            
            logging.info(f"原始文件已保存: {input_path}")
            
            # 預處理音頻 - 壓縮以符合 Groq API 限制
            FFMPEG_PATH = "/home/reyerchu/.local/bin/ffmpeg"
            processed_path = temp_dir / "compressed.mp3"
            
            # 壓縮為低比特率 MP3
            cmd = [
                FFMPEG_PATH, "-y", "-i", str(input_path),
                "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
                str(processed_path)
            ]
            
            logging.info(f"執行 ffmpeg 命令: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                error_message = stderr.decode('utf-8', errors='replace')
                logging.error(f"ffmpeg 處理失敗: {error_message}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Audio preprocessing failed: {error_message}"
                )
            
            logging.info("音頻預處理完成")
            
            # 使用 Whisper 進行轉錄
            logging.info("開始進行轉錄...")
            try:
                if self.use_groq:
                    result = await groq_service.transcribe(str(processed_path))
                    # OpenCC 已在 transcribe 中將文字轉換為繁體中文
                    logging.info("Groq 轉錄完成（OpenCC 繁體轉換）")
                else:
                    result = self.model.transcribe(str(processed_path))
                logging.info("轉錄完成")
            except Exception as e:
                logging.error(f"轉錄失敗: {str(e)}")
                traceback.print_exc()
                raise HTTPException(
                    status_code=500, 
                    detail=f"Transcription failed: {str(e)}"
                )
            
            # 處理輸出
            logging.info(f"生成輸出格式: {request.output_formats}")
            outputs = {}
            base_filename = os.path.splitext(original_filename)[0]
            
            # 生成各種格式
            for fmt in request.output_formats:
                output_path = temp_dir / f"{base_filename}.{fmt}"
                if fmt == "txt":
                    with open(output_path, "w", encoding="utf-8") as f:
                        # 優先使用 LLM 校正後的繁體中文
                        if "corrected_text" in result and result["corrected_text"]:
                            f.write(result["corrected_text"])
                        else:
                            text_lines = [segment["text"].strip() for segment in result["segments"]]
                            f.write("\n".join(text_lines))
                elif fmt == "srt":
                    self._write_srt(result["segments"], output_path)
                elif fmt == "vtt":
                    self._write_vtt(result["segments"], output_path)
                elif fmt == "tsv":
                    self._write_tsv(result["segments"], output_path)
                elif fmt == "json":
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                
                # 讀取輸出文件內容
                with open(output_path, "r", encoding="utf-8") as f:
                    outputs[fmt] = f.read()
                
                logging.info(f"已生成 {fmt} 格式: {output_path}")
            
            # 創建 ZIP 文件
            zip_path = temp_dir / f"{base_filename}.zip"
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for fmt in request.output_formats:
                    file_path = temp_dir / f"{base_filename}.{fmt}"
                    zip_file.write(file_path, arcname=f"{base_filename}.{fmt}")
            
            logging.info(f"已創建 ZIP 文件: {zip_path}")
            
            # 返回結果和 ZIP 文件路徑
            return {
                "data": outputs,
                "zip_path": str(zip_path),
                "session_id": session_id,
                "filename": base_filename
            }
            
        except Exception as e:
            logging.error(f"處理過程中發生錯誤: {str(e)}")
            traceback.print_exc()
            # 清理臨時目錄
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=500, 
                detail=f"Error processing audio: {str(e)}"
            )
    
    def _write_srt(self, segments, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_time = self._format_timestamp(segment["start"], format="srt")
                end_time = self._format_timestamp(segment["end"], format="srt")
                text = segment["text"].strip()
                f.write(f"{i}\n{start_time} --> {end_time}\n{text}\n\n")
    
    def _write_vtt(self, segments, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for i, segment in enumerate(segments):
                start_time = self._format_timestamp(segment["start"], format="vtt")
                end_time = self._format_timestamp(segment["end"], format="vtt")
                text = segment["text"].strip()
                f.write(f"{i+1}\n{start_time} --> {end_time}\n{text}\n\n")
    
    def _write_tsv(self, segments, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("start\tend\ttext\n")
            for segment in segments:
                start_time = segment["start"]
                end_time = segment["end"]
                text = segment["text"].strip()
                f.write(f"{start_time}\t{end_time}\t{text}\n")
    
    def _format_timestamp(self, seconds, format="srt"):
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        milliseconds = int((seconds - int(seconds)) * 1000)
        seconds = int(seconds)
        
        if format == "srt":
            return f"{int(hours):02d}:{int(minutes):02d}:{seconds:02d},{milliseconds:03d}"
        elif format == "vtt":
            return f"{int(hours):02d}:{int(minutes):02d}:{seconds:02d}.{milliseconds:03d}"
        else:
            return seconds

    async def process_link(self, request: LinkRequest) -> Dict[str, Any]:
        logging.info(f"處理連結: {request.url}")
        
        # 建立唯一工作目錄
        session_id = str(uuid.uuid4())
        temp_dir = Path("temp") / session_id
        os.makedirs(temp_dir, exist_ok=True)
        logging.info(f"建立臨時目錄: {temp_dir}")
        
        try:
            # 判斷連結類型
            if "youtube.com" in request.url or "youtu.be" in request.url or "facebook.com" in request.url or "fb.watch" in request.url:
                platform = "Facebook" if "facebook.com" in request.url or "fb.watch" in request.url else "YouTube"
                logging.info(f"下載 {platform} 視頻")
                # 使用更穩健的配置
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',
                    }],
                    'outtmpl': str(temp_dir / 'input.%(ext)s'),
                    'nocheckcertificate': True,
                    'ignoreerrors': False,
                    'js_runtimes': {'node': {}},
                    'quiet': False,
                    'verbose': True,
                }
                
                try:
                    # 直接下載並獲取視頻信息
                    video_title = "facebook_video" if "facebook.com" in request.url or "fb.watch" in request.url else "youtube_video"
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(request.url, download=True)
                        if info and 'title' in info:
                            video_title = info.get('title', 'youtube_video')
                            video_title = "".join(c for c in video_title if c.isalnum() or c in (' ', '-', '_')).strip()
                            logging.info(f"成功下載視頻: {video_title}")
                    
                    # 檢查是否下載成功
                    input_files = list(temp_dir.glob('input.*'))
                    if not input_files:
                        logging.warning("第一次下載失敗，使用備用設置嘗試")
                        
                        # 備用設置
                        backup_opts = ydl_opts.copy()
                        backup_opts['format'] = 'bestaudio/bestvideo'
                        backup_opts['force_generic_extractor'] = True
                        backup_opts['cachedir'] = False
                        backup_opts['extract_flat'] = False
                        backup_opts['skip_download'] = False
                        backup_opts['js_runtimes'] = {'node': {'path': '/home/reyerchu/.nvm/versions/node/v20.19.6/bin/node'}}
                        backup_opts['http_headers'] = {
                            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'DNT': '1',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                        }
                        
                        with yt_dlp.YoutubeDL(backup_opts) as ydl:
                            ydl.download([request.url])
                        
                        # 再次檢查
                        input_files = list(temp_dir.glob('input.*'))
                        if not input_files:
                            raise Exception("無法使用任何方法下載視頻")
                        
                except Exception as e:
                    logging.error(f"YouTube 下載失敗: {str(e)}")
                    logging.error(f"詳細錯誤信息: {traceback.format_exc()}")
                    # 提供友好的錯誤消息給用戶
                    formatted_error = """
                    抱歉，我們無法處理這個 YouTube 鏈接。可能由於以下原因：
                    
                    1. 視頻可能有年齡限制或區域限制
                    2. 視頻可能已被刪除或設為私有
                    3. YouTube 的政策或界面可能已經更改
                    
                    請嘗試：
                    1. 使用不同的視頻
                    2. 下載視頻後手動上傳
                    3. 如果問題持續，請聯繫管理員
                    """
                    
                    # 創建一個模擬轉錄結果，而不是拋出錯誤
                    mock_transcript = f"YouTube 視頻下載失敗。原因: {str(e)[:100]}..."
                    mock_segments = [{"start": 0, "end": 5, "text": mock_transcript}]
                    
                    result = {
                        "text": mock_transcript,
                        "segments": mock_segments,
                        "language": "zh"
                    }
                    
                    # 處理輸出
                    outputs = {}
                    base_filename = "youtube_error"
                    
                    # 生成各種格式
                    for fmt in request.output_formats:
                        output_path = temp_dir / f"{base_filename}.{fmt}"
                        if fmt == "txt":
                            with open(output_path, "w", encoding="utf-8") as f:
                                f.write(formatted_error)
                        elif fmt == "srt":
                            self._write_srt(mock_segments, output_path)
                        elif fmt == "vtt":
                            self._write_vtt(mock_segments, output_path)
                        elif fmt == "tsv":
                            self._write_tsv(mock_segments, output_path)
                        elif fmt == "json":
                            with open(output_path, "w", encoding="utf-8") as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                        
                        # 讀取輸出文件內容
                        with open(output_path, "r", encoding="utf-8") as f:
                            outputs[fmt] = f.read()
                        
                        logging.info(f"已生成 {fmt} 格式: {output_path}")
                    
                    # 創建 ZIP 文件
                    zip_path = temp_dir / f"{base_filename}.zip"
                    with zipfile.ZipFile(zip_path, "w") as zip_file:
                        for fmt in request.output_formats:
                            file_path = temp_dir / f"{base_filename}.{fmt}"
                            zip_file.write(file_path, arcname=f"{base_filename}.{fmt}")
                    
                    logging.info(f"已創建 ZIP 文件: {zip_path}")
                    
                    # 返回錯誤消息但不拋出異常
                    return {
                        "data": outputs,
                        "zip_path": str(zip_path),
                        "session_id": session_id,
                        "filename": base_filename
                    }
            elif "drive.google.com" in request.url:
                logging.info("下載 Google Drive 文件")
                # 使用更穩健的配置
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'wav',
                    }],
                    'outtmpl': str(temp_dir / 'input.%(ext)s'),
                    'nocheckcertificate': True,
                    'ignoreerrors': True,
                    'js_runtimes': {'node': {}},
                    'no_warnings': False,
                    'quiet': False,
                    'extract_flat': False,
                    'skip_download': False,
                    'cookiesfrombrowser': ('chrome',),  # 嘗試使用 Chrome cookies
                    'verbose': True,
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-us,en;q=0.5',
                    }
                }
                
                try:
                    # 嘗試使用可選的文件名
                    file_name = "google_drive_file"  # 預設名稱
                    
                    # 先嘗試獲取文件名
                    try:
                        info_opts = ydl_opts.copy()
                        info_opts['skip_download'] = True
                        with yt_dlp.YoutubeDL(info_opts) as info_ydl:
                            info = info_ydl.extract_info(request.url, download=False)
                            if info and 'title' in info:
                                file_name = info.get('title', 'google_drive_file')
                                # 清理文件名中的非法字符
                                file_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_')).strip()
                                logging.info(f"成功獲取文件名: {file_name}")
                    except Exception as e:
                        logging.warning(f"無法獲取文件名: {str(e)}")
                    
                    # 直接下載
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        # 嘗試禁用 SSL 驗證
                        import ssl
                        ssl._create_default_https_context = ssl._create_unverified_context
                        ydl.download([request.url])
                    
                    # 檢查是否下載成功
                    input_files = list(temp_dir.glob('input.*'))
                    if not input_files:
                        logging.warning("第一次下載失敗，使用備用設置嘗試")
                        
                        # 備用設置
                        backup_opts = ydl_opts.copy()
                        backup_opts['force_generic_extractor'] = True
                        backup_opts['cachedir'] = False
                        
                        with yt_dlp.YoutubeDL(backup_opts) as ydl:
                            ydl.download([request.url])
                        
                        # 再次檢查
                        input_files = list(temp_dir.glob('input.*'))
                        if not input_files:
                            raise Exception("無法使用任何方法下載 Google Drive 文件")
                        
                except Exception as e:
                    logging.error(f"Google Drive 下載失敗: {str(e)}")
                    # 提供友好的錯誤消息給用戶
                    formatted_error = """
                    抱歉，我們無法處理這個 Google Drive 鏈接。可能由於以下原因：
                    
                    1. 文件可能有訪問限制或權限設置
                    2. 文件可能已被刪除或移動
                    3. Google Drive 的政策或界面可能已經更改
                    4. SSL 證書驗證問題
                    
                    請嘗試：
                    1. 確保文件是公開可訪問的
                    2. 下載文件後手動上傳
                    3. 如果問題持續，請聯繫管理員
                    """
                    
                    # 創建一個模擬轉錄結果，而不是拋出錯誤
                    mock_transcript = f"Google Drive 文件下載失敗。原因: {str(e)[:100]}..."
                    mock_segments = [{"start": 0, "end": 5, "text": mock_transcript}]
                    
                    result = {
                        "text": mock_transcript,
                        "segments": mock_segments,
                        "language": "zh"
                    }
                    
                    # 處理輸出
                    outputs = {}
                    base_filename = "google_drive_error"
                    
                    # 生成各種格式
                    for fmt in request.output_formats:
                        output_path = temp_dir / f"{base_filename}.{fmt}"
                        if fmt == "txt":
                            with open(output_path, "w", encoding="utf-8") as f:
                                f.write(formatted_error)
                        elif fmt == "srt":
                            self._write_srt(mock_segments, output_path)
                        elif fmt == "vtt":
                            self._write_vtt(mock_segments, output_path)
                        elif fmt == "tsv":
                            self._write_tsv(mock_segments, output_path)
                        elif fmt == "json":
                            with open(output_path, "w", encoding="utf-8") as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                        
                        # 讀取輸出文件內容
                        with open(output_path, "r", encoding="utf-8") as f:
                            outputs[fmt] = f.read()
                        
                        logging.info(f"已生成 {fmt} 格式: {output_path}")
                    
                    # 創建 ZIP 文件
                    zip_path = temp_dir / f"{base_filename}.zip"
                    with zipfile.ZipFile(zip_path, "w") as zip_file:
                        for fmt in request.output_formats:
                            file_path = temp_dir / f"{base_filename}.{fmt}"
                            zip_file.write(file_path, arcname=f"{base_filename}.{fmt}")
                    
                    logging.info(f"已創建 ZIP 文件: {zip_path}")
                    
                    # 返回錯誤消息但不拋出異常
                    return {
                        "data": outputs,
                        "zip_path": str(zip_path),
                        "session_id": session_id,
                        "filename": base_filename
                    }
            else:
                raise HTTPException(
                    status_code=400,
                    detail="不支持的連結類型。請提供 YouTube 或 Google Drive 連結。"
                )
            
            # 檢查下載的文件是否存在
            input_files = list(temp_dir.glob('input.*'))
            if not input_files:
                raise HTTPException(
                    status_code=500,
                    detail="下載失敗：未找到音頻文件"
                )
            
            # 預處理音頻
            processed_path = temp_dir / "processed.wav"
            input_path = input_files[0]  # 使用找到的第一個文件
            
            # 使用 ffmpeg 轉換為 WAV 格式
            cmd = [
                "ffmpeg", "-i", str(input_path), 
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", 
                str(processed_path)
            ]
            
            logging.info(f"執行 ffmpeg 命令: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                error_message = stderr.decode('utf-8', errors='replace')
                logging.error(f"ffmpeg 處理失敗: {error_message}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"音頻預處理失敗: {error_message}"
                )
            
            logging.info("音頻預處理完成")
            
            # 使用 Whisper 進行轉錄
            logging.info("開始進行轉錄...")
            try:
                if self.use_groq:
                    result = await groq_service.transcribe(str(processed_path))
                    # OpenCC 已在 transcribe 中將文字轉換為繁體中文
                    logging.info("Groq 轉錄完成（OpenCC 繁體轉換）")
                else:
                    result = self.model.transcribe(str(processed_path))
                logging.info("轉錄完成")
            except Exception as e:
                logging.error(f"轉錄失敗: {str(e)}")
                traceback.print_exc()
                raise HTTPException(
                    status_code=500, 
                    detail=f"轉錄失敗: {str(e)}"
                )
            
            # 處理輸出
            logging.info(f"生成輸出格式: {request.output_formats}")
            outputs = {}
            
            # 使用視頻標題或文件名作為基礎文件名
            base_filename = video_title if "youtube.com" in request.url or "youtu.be" in request.url or "facebook.com" in request.url or "fb.watch" in request.url else file_name
            logging.info(f"使用檔案名稱: {base_filename} 作為輸出文件前綴")
            
            # 生成各種格式
            for fmt in request.output_formats:
                output_path = temp_dir / f"{base_filename}.{fmt}"
                if fmt == "txt":
                    with open(output_path, "w", encoding="utf-8") as f:
                        # 優先使用 LLM 校正後的繁體中文
                        if "corrected_text" in result and result["corrected_text"]:
                            f.write(result["corrected_text"])
                        else:
                            text_lines = [segment["text"].strip() for segment in result["segments"]]
                            f.write("\n".join(text_lines))
                elif fmt == "srt":
                    self._write_srt(result["segments"], output_path)
                elif fmt == "vtt":
                    self._write_vtt(result["segments"], output_path)
                elif fmt == "tsv":
                    self._write_tsv(result["segments"], output_path)
                elif fmt == "json":
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                
                # 讀取輸出文件內容
                with open(output_path, "r", encoding="utf-8") as f:
                    outputs[fmt] = f.read()
                
                logging.info(f"已生成 {fmt} 格式: {output_path}")
            
            # 創建 ZIP 文件
            zip_path = temp_dir / f"{base_filename}.zip"
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for fmt in request.output_formats:
                    file_path = temp_dir / f"{base_filename}.{fmt}"
                    zip_file.write(file_path, arcname=f"{base_filename}.{fmt}")
            
            logging.info(f"已創建 ZIP 文件: {zip_path}")
            
            # 返回結果和 ZIP 文件路徑
            return {
                "data": outputs,
                "zip_path": str(zip_path),
                "session_id": session_id,
                "filename": base_filename
            }
            
        except Exception as e:
            logging.error(f"處理過程中發生錯誤: {str(e)}")
            traceback.print_exc()
            # 清理臨時目錄
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=500, 
                detail=f"處理連結時發生錯誤: {str(e)}"
            )

# 創建轉錄服務實例
transcription_service = TranscriptionService()

@app.post(f"{PREFIX}/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    output_formats: str = Form(None)
):
    try:
        # 解析輸出格式
        formats = ["txt", "srt", "vtt", "tsv", "json"]
        if output_formats:
            formats = json.loads(output_formats)
        
        # 檢查檔案類型
        if not file.filename:
            logging.warning("未提供檔案名稱")
            raise HTTPException(status_code=400, detail="No file name provided")
        
        logging.info(f"接收到轉錄請求: {file.filename}, 格式: {formats}")
        
        # 處理音頻
        request = TranscriptionRequest(file=file, output_formats=formats)
        result = await transcription_service.process_audio(request)
        
        # 返回結果
        zip_url = f"{PREFIX}/download/{result['session_id']}/{result['filename']}.zip"
        return JSONResponse({
            "data": result["data"],
            "zip_url": zip_url
        })
    
    except Exception as e:
        logging.error(f"處理請求時發生錯誤: {str(e)}")
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

# Add a new endpoint that matches the frontend's request path
@app.post("/transcribe")
async def transcribe_root(
    file: UploadFile = File(...),
    output_formats: str = Form(None)
):
    # Forward the request to the main transcribe endpoint
    return await transcribe(file, output_formats)

@app.get(f"{PREFIX}/download/{{session_id}}/{{filename}}")
async def download_file(session_id: str, filename: str):
    file_path = f"temp/{session_id}/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

# Add a new endpoint that matches the frontend's download request path
@app.get("/download/{session_id}/{filename}")
async def download_file_root(session_id: str, filename: str):
    # Forward the request to the main download_file endpoint
    return await download_file(session_id, filename)

@app.post(f"{PREFIX}/clean-temp")
async def clean_temp_files(password_data: PasswordModel):
    logging.info("接收到清理暫存檔案請求")
    try:
        # 驗證密碼（記錄接收的密碼以便調試）
        received_password = password_data.password.strip()
        logging.info(f"接收到的密碼: '{received_password}'")
        
        # 更寬鬆的密碼檢查（允許前後空格並不區分大小寫）
        if received_password.lower() == ROOT_PASSWORD.lower():
            # 清空 temp 目錄
            temp_dir = Path("temp")
            if os.path.exists(temp_dir):
                # 刪除所有子目錄和文件
                for item in os.listdir(temp_dir):
                    item_path = temp_dir / item
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        os.remove(item_path)
                
                logging.info("成功清空暫存檔案")
                return JSONResponse({"success": True, "message": "成功清空暫存檔案"})
            else:
                logging.info("暫存目錄不存在，已創建")
                os.makedirs(temp_dir, exist_ok=True)
                return JSONResponse({"success": True, "message": "暫存目錄不存在，已創建"})
        else:
            logging.warning(f"密碼驗證失敗，預期密碼: '{ROOT_PASSWORD}'")
            return JSONResponse({"success": False, "message": "密碼不正確 (提示: admin123)"})
        
    except Exception as e:
        logging.error(f"清理暫存檔案時發生錯誤: {str(e)}")
        traceback.print_exc()
        return JSONResponse({"success": False, "message": f"發生錯誤: {str(e)}"})

@app.get(f"{PREFIX}/temp-size")
async def get_temp_size():
    """獲取 temp 目錄的大小信息"""
    logging.info("請求獲取暫存目錄大小")
    try:
        temp_dir = Path("temp")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
            return JSONResponse({"size_bytes": 0, "size_mb": 0, "file_count": 0})
        
        # 計算目錄大小和文件數量
        total_size = 0
        file_count = 0
        
        for dirpath, dirnames, filenames in os.walk(temp_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
                    file_count += 1
        
        # 轉換為 MB
        size_mb = round(total_size / (1024 * 1024), 2)
        
        logging.info(f"暫存目錄大小: {size_mb} MB, 文件數量: {file_count}")
        return JSONResponse({
            "size_bytes": total_size,
            "size_mb": size_mb,
            "file_count": file_count
        })
        
    except Exception as e:
        logging.error(f"獲取暫存目錄大小時發生錯誤: {str(e)}")
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

# Add new endpoints that match the frontend's request paths
@app.get("/temp-size")
async def get_temp_size_root():
    # Forward the request to the main get_temp_size endpoint
    return await get_temp_size()

@app.post("/clean-temp")
async def clean_temp_files_root(password_data: PasswordModel):
    # Forward the request to the main clean_temp_files endpoint
    return await clean_temp_files(password_data)

@app.post(f"{PREFIX}/transcribe-link")
async def transcribe_link(request: LinkRequest):
    try:
        logging.info(f"接收到轉錄連結請求: {request.url}, 格式: {request.output_formats}")
        
        # 處理音頻
        result = await transcription_service.process_link(request)
        
        # 返回結果
        zip_url = f"{PREFIX}/download/{result['session_id']}/{result['filename']}.zip"
        return JSONResponse({
            "data": result["data"],
            "zip_url": zip_url
        })
    except Exception as e:
        logging.error(f"處理連結時發生錯誤: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True) 