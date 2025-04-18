from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.responses import JSONResponse, FileResponse
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
    description="音頻轉文字 API 服務",
    docs_url="/s2t/api/docs",
    openapi_url="/s2t/api/openapi.json",
)

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

class TranscriptionService:
    def __init__(self):
        self.model = whisper.load_model("tiny")
        logging.info("Whisper model loaded")

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
            
            # 預處理音頻（如果需要）
            processed_path = temp_dir / "processed.wav"
            
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
                    detail=f"Audio preprocessing failed: {error_message}"
                )
            
            logging.info("音頻預處理完成")
            
            # 使用 Whisper 進行轉錄
            logging.info("開始進行轉錄...")
            try:
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
                        # 每個段落一行，而不是所有文字連在一起
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
        zip_url = f"/download/{result['session_id']}/{result['filename']}.zip"
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

@app.get(f"{PREFIX}/download/{{session_id}}/{{filename}}")
async def download_file(session_id: str, filename: str):
    file_path = f"temp/{session_id}/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 