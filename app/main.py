from fastapi import FastAPI, UploadFile, File, Form
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
        self.model = whisper.load_model("medium")  # 可選擇不同大小的模型
    
    async def process_audio(self, file: UploadFile, output_formats: List[str]):
        # 創建唯一的輸出目錄
        output_dir = f"temp/{uuid.uuid4()}"
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存上傳的音頻文件
        temp_path = f"{output_dir}/{file.filename}"
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # 使用 ffmpeg 進行音頻預處理
        audio = ffmpeg.input(temp_path)
        audio = ffmpeg.output(audio, f"{output_dir}/processed.wav")
        ffmpeg.run(audio)
        
        # 使用 Whisper 進行轉錄
        result = self.model.transcribe(
            f"{output_dir}/processed.wav",
            language="zh",
            task="transcribe"
        )
        
        # 生成選擇的格式的輸出
        outputs = self._generate_outputs(result, output_dir, output_formats)
        
        # 創建 ZIP 文件
        zip_path = f"{output_dir}/transcripts.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for format in output_formats:
                file_path = f"{output_dir}/transcript.{format}"
                if os.path.exists(file_path):
                    zipf.write(file_path, f"transcript.{format}")
        
        # 清理臨時文件，但保留 ZIP
        for file in glob.glob(f"{output_dir}/*"):
            if not file.endswith('.zip'):
                os.remove(file)
        
        return {
            "zip_path": zip_path,
            "outputs": outputs
        }
    
    def _generate_outputs(self, result, output_dir, output_formats):
        outputs = {}
        
        # 純文字 (.txt)
        if "txt" in output_formats:
            with open(f"{output_dir}/transcript.txt", "w", encoding="utf-8") as f:
                f.write(result["text"])
            outputs["txt"] = result["text"]
        
        # SRT 格式
        if "srt" in output_formats:
            srt_content = self._generate_srt(result["segments"])
            with open(f"{output_dir}/transcript.srt", "w", encoding="utf-8") as f:
                f.write(srt_content)
            outputs["srt"] = srt_content
        
        # VTT 格式
        if "vtt" in output_formats:
            vtt_content = self._generate_vtt(result["segments"])
            with open(f"{output_dir}/transcript.vtt", "w", encoding="utf-8") as f:
                f.write(vtt_content)
            outputs["vtt"] = vtt_content
        
        # TSV 格式
        if "tsv" in output_formats:
            tsv_content = self._generate_tsv(result["segments"])
            with open(f"{output_dir}/transcript.tsv", "w", encoding="utf-8") as f:
                f.write(tsv_content)
            outputs["tsv"] = tsv_content
        
        # JSON 格式
        if "json" in output_formats:
            with open(f"{output_dir}/transcript.json", "w", encoding="utf-8") as f:
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
        
        result = await service.process_audio(file, formats)
        return {
            "status": "success",
            "data": result["outputs"],
            "zip_url": f"/download/{os.path.basename(os.path.dirname(result['zip_path']))}/transcripts.zip"
        }
    except Exception as e:
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