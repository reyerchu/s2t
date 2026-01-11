import React, { useState, useRef } from 'react';
import axios from 'axios';

axios.defaults.baseURL = '/s2t/api';
axios.defaults.timeout = 1800000;

function App() {
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState('');
  const [inputMode, setInputMode] = useState('file');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFormats, setSelectedFormats] = useState({
    txt: true,
    srt: true,
    vtt: false,
    tsv: false,
    json: false
  });
  const [zipUrl, setZipUrl] = useState(null);
  const fileInputRef = useRef(null);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [password, setPassword] = useState('');
  const [cleaningStatus, setCleaningStatus] = useState(null);
  const [tempFolderSize, setTempFolderSize] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setLogs([]);
      setResults(null);
      setZipUrl(null);
    }
  };

  const handleDragEnter = (e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); };
  const handleDragOver = (e) => { e.preventDefault(); e.stopPropagation(); if (!isDragging) setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); e.stopPropagation(); setIsDragging(false); };
  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false);
    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles && droppedFiles.length > 0) {
      setFile(droppedFiles[0]);
      setLogs([]); setResults(null); setZipUrl(null);
    }
  };

  const handleFormatChange = (format) => {
    setSelectedFormats(prev => ({ ...prev, [format]: !prev[format] }));
  };

  const addLog = (message) => {
    setLogs(prev => [...prev, `${new Date().toLocaleTimeString()} - ${message}`]);
  };

  const handleUrlChange = (e) => {
    setUrl(e.target.value);
    setLogs([]); setResults(null); setZipUrl(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (inputMode === 'file' && !file) return;
    if (inputMode === 'url' && !url) return;

    setLoading(true);
    setResults(null);
    setZipUrl(null);
    setLogs([]);

    try {
      const formats = Object.entries(selectedFormats)
        .filter(([_, checked]) => checked)
        .map(([format]) => format);

      if (formats.length === 0) {
        addLog('請至少選擇一種輸出格式');
        setLoading(false);
        return;
      }

      if (inputMode === 'file') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('output_formats', JSON.stringify(formats));
        
        addLog('正在上傳文件...');
        const response = await axios.post('transcribe', formData, {
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            addLog(`上傳進度: ${percentCompleted}%`);
          }
        });
        
        addLog('文件處理完成');
        setResults(response.data.data);
        setZipUrl(response.data.zip_url);
      } else {
        addLog(`開始處理連結: ${url}`);
        const response = await axios.post('transcribe-link', {
          url: url,
          output_formats: formats
        });
        
        addLog('連結處理完成');
        setResults(response.data.data);
        setZipUrl(response.data.zip_url);
      }
      
      addLog('可以下載轉錄結果了');
    } catch (error) {
      console.error('Error:', error);
      addLog(`錯誤: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCleanFiles = async () => {
    try {
      const response = await axios.get('temp-size');
      setTempFolderSize(response.data);
      setShowPasswordDialog(true);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  const confirmCleanFiles = async () => {
    try {
      setCleaningStatus('cleaning');
      const response = await axios.post('clean-temp', { password });
      if (response.data.success) {
        setCleaningStatus('success');
        setTimeout(() => {
          setShowPasswordDialog(false);
          setCleaningStatus(null);
          setPassword('');
        }, 1500);
      } else {
        setCleaningStatus('error');
        setTimeout(() => setCleaningStatus(null), 2000);
      }
    } catch (error) {
      setCleaningStatus('error');
      setTimeout(() => setCleaningStatus(null), 2000);
    }
  };

  const cancelCleanFiles = () => {
    setShowPasswordDialog(false);
    setCleaningStatus(null);
    setPassword('');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-amber-600 to-yellow-500 py-4 shadow-md">
        <div className="container mx-auto px-4">
          <h1 className="text-3xl font-bold text-white">影音轉文字服務</h1>
          <p className="text-amber-100 text-sm">將您的影片或音頻檔案轉換為多種格式的文字內容</p>
        </div>
      </header>

      <div className="container mx-auto px-4 py-6">
        {/* Row 1: 上傳檔案/輸入網址 | 處理進度(含清空按鈕) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          {/* 左: 上傳檔案/輸入網址 */}
          <div className="bg-white rounded-lg shadow p-4 border">
            <div className="flex space-x-2 mb-3">
              <button type="button" onClick={() => setInputMode('file')}
                className={`flex-1 py-2 px-3 rounded text-sm font-medium ${inputMode === 'file' ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-700'}`}>
                上傳檔案
              </button>
              <button type="button" onClick={() => setInputMode('url')}
                className={`flex-1 py-2 px-3 rounded text-sm font-medium ${inputMode === 'url' ? 'bg-amber-600 text-white' : 'bg-amber-100 text-amber-700'}`}>
                輸入網址
              </button>
            </div>
            {inputMode === 'file' ? (
              <div className={`border-2 border-dashed rounded p-4 text-center ${isDragging ? 'border-amber-600 bg-amber-50' : 'border-gray-300'}`}
                onDragEnter={handleDragEnter} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
                <input type="file" accept="*/*" onChange={handleFileChange} className="hidden" id="file-upload" ref={fileInputRef} />
                <label htmlFor="file-upload" className="cursor-pointer text-sm text-gray-600">
                  {file ? <span className="text-amber-700 font-medium">{file.name}</span> : '選擇或拖放檔案'}
                </label>
              </div>
            ) : (
              <input type="text" value={url} onChange={handleUrlChange}
                placeholder="YouTube / Facebook / Google Drive 連結"
                className="w-full px-3 py-2 border rounded text-sm focus:ring-2 focus:ring-amber-500" />
            )}
          </div>

          {/* 右: 處理進度 (含清空暫存按鈕在右上角) */}
          <div className="bg-white rounded-lg shadow p-4 border">
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-bold text-amber-700 text-sm">處理進度</h3>
              <button onClick={handleCleanFiles}
                className="bg-red-500 hover:bg-red-600 text-white py-1 px-3 rounded text-xs font-medium">
                清空暫存檔案
              </button>
            </div>
            <div className="bg-gray-900 text-green-400 p-2 rounded font-mono text-xs h-24 overflow-y-auto">
              {logs.length > 0 ? logs.map((log, i) => <div key={i}>{log}</div>) : <span className="text-gray-500">等待開始...</span>}
            </div>
          </div>
        </div>

        {/* Row 2: 選擇輸出格式 | 轉換完成/下載 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
          {/* 左: 選擇輸出格式 */}
          <div className="bg-white rounded-lg shadow p-4 border">
            <h3 className="font-bold text-amber-700 mb-2 text-sm">選擇輸出格式</h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries({ txt: 'TXT', srt: 'SRT', vtt: 'VTT', tsv: 'TSV', json: 'JSON' }).map(([fmt, label]) => (
                <label key={fmt} className="flex items-center space-x-1 px-3 py-1 rounded bg-amber-50 border border-amber-200 cursor-pointer text-sm">
                  <input type="checkbox" checked={selectedFormats[fmt]} onChange={() => handleFormatChange(fmt)} className="text-amber-600" />
                  <span>{label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* 右: 轉換完成/下載 */}
          <div className="bg-white rounded-lg shadow p-4 border flex items-center justify-center">
            {zipUrl ? (
              <a href={zipUrl} download className="block w-full text-center bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded text-sm font-bold">
                📥 下載 ZIP
              </a>
            ) : (
              <div className="text-gray-400 text-sm text-center">轉換完成後可下載</div>
            )}
          </div>
        </div>

        {/* Row 3: 開始轉錄 */}
        <div className="mb-6">
          <button type="button" onClick={handleSubmit}
            disabled={loading || (inputMode === 'file' ? !file : !url)}
            className={`w-full py-3 rounded-lg font-bold text-white text-lg ${loading || (inputMode === 'file' ? !file : !url) ? 'bg-gray-400' : 'bg-amber-600 hover:bg-amber-700'}`}>
            {loading ? '處理中...' : '🎙️ 開始轉錄'}
          </button>
        </div>

        {/* 預覽結果 */}
                {results && (
          <div className="bg-white rounded-lg shadow p-4 border">
            <h2 className="text-xl font-bold text-amber-700 mb-4">預覽結果</h2>
            
            {/* AI 內容摘要 - 獨立一行 */}
            {results.summary && (
              <div className="border-2 border-green-300 bg-green-50 rounded-lg p-4 mb-4">
                <h3 className="font-bold text-green-700 mb-2 flex items-center">📝 AI 內容摘要</h3>
                <pre className="whitespace-pre-wrap text-gray-700 text-sm bg-white p-3 rounded border max-h-64 overflow-y-auto">{results.summary}</pre>
              </div>
            )}
            
            {/* TXT 和 SRT 並排 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {results.txt && (
                <div className="border border-amber-200 bg-amber-50 rounded-lg p-4">
                  <h3 className="font-bold text-amber-700 mb-2">📄 TXT 格式</h3>
                  <pre className="whitespace-pre-wrap text-gray-700 text-sm bg-white p-3 rounded border max-h-64 overflow-y-auto">{results.txt}</pre>
                </div>
              )}
              {results.srt && (
                <div className="border border-amber-200 bg-amber-50 rounded-lg p-4">
                  <h3 className="font-bold text-amber-700 mb-2">📄 SRT 格式</h3>
                  <pre className="whitespace-pre-wrap text-gray-700 text-sm bg-white p-3 rounded border max-h-64 overflow-y-auto">{results.srt}</pre>
                </div>
              )}
            </div>
            
            {/* 其他格式 */}
            {Object.entries(results).filter(([fmt]) => !["summary", "txt", "srt"].includes(fmt)).length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
                {Object.entries(results).filter(([fmt]) => !["summary", "txt", "srt"].includes(fmt)).map(([fmt, content]) => (
                  <div key={fmt} className="border border-amber-200 bg-amber-50 rounded-lg p-4">
                    <h3 className="font-bold text-amber-700 mb-2">{fmt.toUpperCase()} 格式</h3>
                    <pre className="whitespace-pre-wrap text-gray-700 text-sm bg-white p-3 rounded border max-h-64 overflow-y-auto">
                      {fmt === "json" ? JSON.stringify(content, null, 2) : content}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}<footer className="mt-8 text-center text-gray-400 text-xs">
          © {new Date().getFullYear()} 影音轉文字服務 - Powered by Groq Whisper
        </footer>
      </div>

      {/* Password Dialog */}
      {showPasswordDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-80">
            <h3 className="text-lg font-bold mb-4 text-amber-700">清空暫存檔案</h3>
            {tempFolderSize && (
              <p className="text-sm text-gray-600 mb-3">
                目前大小: {tempFolderSize.size_mb?.toFixed(2) || 0} MB ({tempFolderSize.file_count || 0} 個檔案)
              </p>
            )}
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="請輸入密碼" className="w-full px-3 py-2 border rounded mb-4" />
            <div className="flex space-x-2">
              <button onClick={cancelCleanFiles} className="flex-1 py-2 bg-gray-300 rounded">取消</button>
              <button onClick={confirmCleanFiles} className="flex-1 py-2 bg-red-500 text-white rounded">
                {cleaningStatus === 'cleaning' ? '清理中...' : '確認清空'}
              </button>
            </div>
            {cleaningStatus === 'success' && <p className="text-green-600 text-sm mt-2 text-center">✓ 清理成功</p>}
            {cleaningStatus === 'error' && <p className="text-red-600 text-sm mt-2 text-center">✗ 密碼錯誤</p>}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
