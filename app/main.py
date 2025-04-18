from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import whisper
import ffmpeg
import os
import json
import zipfile
import glob
from typing import List
import uuid
import logging
import traceback

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TranscriptionService:
    def __init__(self):
        logger.info("Loading Whisper model...")
        self.model = whisper.load_model("medium")  # 可選擇不同大小的模型
        logger.info("Whisper model loaded successfully")
    
    async def process_audio(self, file: UploadFile, output_formats: List[str]):
        # 創建唯一的輸出目錄
        output_dir = f"temp/{uuid.uuid4()}"
        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Created output directory: {output_dir}")
        
        # 保存上傳的音頻文件，使用原始文件名
        original_filename = file.filename
        temp_path = f"{output_dir}/{original_filename}"
        logger.info(f"Saving uploaded file to: {temp_path}")
        
        try:
            # 記錄文件信息
            logger.info(f"File details - Name: {original_filename}, Content-Type: {file.content_type}")
            
            # 讀取文件內容
            content = await file.read()
            content_size = len(content)
            logger.info(f"Read file content, size: {content_size} bytes")
            
            if content_size == 0:
                logger.error("Uploaded file is empty (0 bytes)")
                raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes)")
            
            # 保存文件
            with open(temp_path, "wb") as buffer:
                buffer.write(content)
            
            # 驗證保存的文件
            saved_size = os.path.getsize(temp_path)
            logger.info(f"Saved file size: {saved_size} bytes")
            
            if saved_size == 0:
                logger.error("Saved file is empty (0 bytes)")
                raise HTTPException(status_code=500, detail="Failed to save file: File is empty")
            
            if saved_size != content_size:
                logger.error(f"File size mismatch: Original={content_size}, Saved={saved_size}")
                raise HTTPException(status_code=500, detail="File size mismatch during save")
            
            # 使用 ffmpeg 進行音頻預處理
            processed_path = f"{output_dir}/audio.wav"
            logger.info(f"Processing audio with ffmpeg: {temp_path} -> {processed_path}")
            
            try:
                # 使用更明確的參數，並添加格式檢測
                stream = ffmpeg.input(temp_path)
                # 提取音頻並設置參數
                stream = ffmpeg.output(stream, processed_path, 
                                    acodec='pcm_s16le',  # 使用 16-bit PCM 編碼
                                    ac=1,                # 單聲道
                                    ar='16k',            # 16kHz 採樣率
                                    loglevel='error',    # 只顯示錯誤信息
                                    **{'vn': None})      # 忽略視頻流
                
                # 添加詳細的錯誤捕獲
                try:
                    stdout, stderr = ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
                    if stderr:
                        logger.warning(f"FFmpeg stderr output: {stderr.decode()}")
                except ffmpeg.Error as e:
                    error_message = e.stderr.decode() if e.stderr else str(e)
                    logger.error(f"FFmpeg error: {error_message}")
                    raise HTTPException(status_code=500, detail=f"Audio processing failed: {error_message}")
                
                logger.info("Audio extraction completed successfully")
                
                # 檢查處理後的文件是否存在且大小不為0
                if not os.path.exists(processed_path):
                    logger.error("Processed file does not exist")
                    raise HTTPException(status_code=500, detail="Audio processing failed: Output file does not exist")
                
                processed_size = os.path.getsize(processed_path)
                logger.info(f"Processed file size: {processed_size} bytes")
                
                if processed_size == 0:
                    logger.error("Processed file is empty (0 bytes)")
                    raise HTTPException(status_code=500, detail="Audio processing failed: Output file is empty")
                
            except Exception as e:
                logger.error(f"Error processing audio: {str(e)}")
                logger.error(traceback.format_exc())
                raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")
            
            # 使用 Whisper 進行轉錄
            logger.info("Starting transcription with Whisper")
            try:
                # 設置 Whisper 參數
                result = self.model.transcribe(
                    processed_path,
                    language="zh",
                    task="transcribe",
                    fp16=False,  # 強制使用 FP32
                    verbose=True  # 顯示詳細信息
                )
                logger.info("Transcription completed successfully")
                logger.info(f"Transcription result: {result['text'][:100]}...")  # 記錄轉錄結果的前100個字符
            except Exception as e:
                logger.error(f"Transcription error: {str(e)}")
                logger.error(traceback.format_exc())
                raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
            
            # 生成選擇的格式的輸出
            logger.info(f"Generating outputs for formats: {output_formats}")
            outputs = self._generate_outputs(result, output_dir, output_formats)
            
            # 創建 ZIP 文件
            zip_path = f"{output_dir}/transcripts.zip"
            logger.info(f"Creating ZIP file: {zip_path}")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for format in output_formats:
                    file_path = f"{output_dir}/transcript.{format}"
                    if os.path.exists(file_path):
                        zipf.write(file_path, f"transcript.{format}")
            
            # 清理臨時文件，但保留 ZIP
            logger.info("Cleaning up temporary files")
            for file in glob.glob(f"{output_dir}/*"):
                if not file.endswith('.zip'):
                    os.remove(file)
            
            return {
                "zip_path": zip_path,
                "outputs": outputs
            }
            
        except Exception as e:
            logger.error(f"Error in process_audio: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
    
    def _generate_outputs(self, result, output_dir, output_formats):
        outputs = {}
        
        # 純文字 (.txt)
        if "txt" in output_formats:
            txt_path = f"{output_dir}/transcript.txt"
            logger.info(f"Generating TXT file: {txt_path}")
            
            # 改為每個片段一行
            text_lines = [segment["text"].strip() for segment in result["segments"]]
            text = "\n".join(text_lines)
            
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            outputs["txt"] = text
        
        # SRT 格式
        if "srt" in output_formats:
            srt_path = f"{output_dir}/transcript.srt"
            logger.info(f"Generating SRT file: {srt_path}")
            srt_content = self._generate_srt(result["segments"])
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            outputs["srt"] = srt_content
        
        # VTT 格式
        if "vtt" in output_formats:
            vtt_path = f"{output_dir}/transcript.vtt"
            logger.info(f"Generating VTT file: {vtt_path}")
            vtt_content = self._generate_vtt(result["segments"])
            with open(vtt_path, "w", encoding="utf-8") as f:
                f.write(vtt_content)
            outputs["vtt"] = vtt_content
        
        # TSV 格式
        if "tsv" in output_formats:
            tsv_path = f"{output_dir}/transcript.tsv"
            logger.info(f"Generating TSV file: {tsv_path}")
            tsv_content = self._generate_tsv(result["segments"])
            with open(tsv_path, "w", encoding="utf-8") as f:
                f.write(tsv_content)
            outputs["tsv"] = tsv_content
        
        # JSON 格式
        if "json" in output_formats:
            json_path = f"{output_dir}/transcript.json"
            logger.info(f"Generating JSON file: {json_path}")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            outputs["json"] = result
        
        return outputs

    def _generate_srt(self, segments):
        srt_lines = []
        for i, segment in enumerate(segments, start=1):
            start = self._format_timestamp(segment["start"])
            end = self._format_timestamp(segment["end"])
            srt_lines.extend([
                str(i),
                f"{start} --> {end}",
                segment["text"].strip(),
                ""
            ])
        return "\n".join(srt_lines)

    def _generate_vtt(self, segments):
        vtt_lines = ["WEBVTT\n"]
        for i, segment in enumerate(segments):
            start = self._format_timestamp(segment["start"])
            end = self._format_timestamp(segment["end"])
            vtt_lines.extend([
                f"{start} --> {end}",
                segment["text"].strip(),
                ""
            ])
        return "\n".join(vtt_lines)

    def _generate_tsv(self, segments):
        tsv_lines = ["start\tend\ttext"]
        for segment in segments:
            start = self._format_timestamp(segment["start"])
            end = self._format_timestamp(segment["end"])
            text = segment["text"].strip().replace("\t", " ")
            tsv_lines.append(f"{start}\t{end}\t{text}")
        return "\n".join(tsv_lines)

    def _format_timestamp(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

service = TranscriptionService()

@app.get("/files")
async def list_files():
    """列出 temp 目錄中的所有文件"""
    files = []
    for file in os.listdir("temp"):
        if os.path.isfile(os.path.join("temp", file)) and not file.endswith('.zip'):
            files.append(file)
    return {"files": files}

@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    output_formats: str = Form("[]")
):
    try:
        # 解析輸出格式列表
        formats = json.loads(output_formats)
        if not formats:
            formats = ["txt", "srt", "vtt", "tsv", "json"]  # 默認全部輸出
        
        logger.info(f"Received file: {file.filename}, formats: {formats}")
        result = await service.process_audio(file, formats)
        return {
            "status": "success",
            "data": result["outputs"],
            "zip_url": f"/download/{os.path.basename(os.path.dirname(result['zip_path']))}/transcripts.zip"
        }
    except Exception as e:
        logger.error(f"Error in transcribe_audio: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/download/{dir_id}/transcripts.zip")
async def download_zip(dir_id: str):
    """下載 ZIP 文件"""
    zip_path = f"temp/{dir_id}/transcripts.zip"
    if os.path.exists(zip_path):
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename="transcripts.zip"
        )
    return {"status": "error", "message": "File not found"}

@app.get("/files/{filename}")
async def get_file(filename: str):
    """獲取指定文件的內容"""
    file_path = f"temp/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=filename
    ) 