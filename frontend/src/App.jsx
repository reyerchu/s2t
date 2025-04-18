import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [selectedFormats, setSelectedFormats] = useState({
    txt: true,
    srt: true,
    vtt: false,
    tsv: false,
    json: false
  });
  const [zipUrl, setZipUrl] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setLogs([]);
    setResults(null);
    setZipUrl(null);
  };

  const handleFormatChange = (format) => {
    setSelectedFormats(prev => ({
      ...prev,
      [format]: !prev[format]
    }));
  };

  const addLog = (message) => {
    setLogs(prev => [...prev, `${new Date().toLocaleTimeString()} - ${message}`]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setLogs([]);
    addLog(`開始處理文件: ${file.name}`);
    
    const formData = new FormData();
    formData.append('file', file);
    
    const formats = Object.entries(selectedFormats)
      .filter(([_, selected]) => selected)
      .map(([format]) => format);
    
    formData.append('output_formats', JSON.stringify(formats));
    addLog(`選擇的輸出格式: ${formats.join(', ')}`);

    try {
      addLog('正在上傳文件...');
      const response = await axios.post('http://localhost:8000/transcribe', formData, {
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          addLog(`上傳進度: ${percentCompleted}%`);
        }
      });
      
      addLog('文件處理完成');
      setResults(response.data.data);
      setZipUrl(`http://localhost:8000${response.data.zip_url}`);
      addLog('可以下載轉錄結果了');
    } catch (error) {
      console.error('Error:', error);
      addLog(`錯誤: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 to-gray-800 text-white">
      {/* Header */}
      <header className="bg-gray-900 py-6 shadow-lg">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500">
            影音轉文字服務
          </h1>
          <p className="text-gray-400 mt-2">
            將您的影片或音頻檔案轉換為多種格式的文字內容
          </p>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-gray-800 rounded-xl shadow-xl p-6 border border-gray-700">
            <h2 className="text-2xl font-bold mb-6 text-blue-400">選擇輸出格式</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
              {Object.entries({
                txt: '.txt (純文字)',
                srt: '.srt (字幕)',
                vtt: '.vtt (網頁字幕)',
                tsv: '.tsv (Excel)',
                json: '.json (完整數據)'
              }).map(([format, label]) => (
                <label key={format} className="flex items-center space-x-3 p-3 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedFormats[format]}
                    onChange={() => handleFormatChange(format)}
                    className="form-checkbox h-5 w-5 text-blue-500 rounded"
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            <form onSubmit={handleSubmit}>
              <h2 className="text-2xl font-bold mb-4 text-blue-400">上傳文件</h2>
              <div className="mb-6">
                <div className="border-2 border-dashed border-gray-600 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
                  <input
                    type="file"
                    accept="*/*"
                    onChange={handleFileChange}
                    className="hidden"
                    id="file-upload"
                  />
                  <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <span className="text-gray-300 text-lg font-medium">選擇文件或拖放至此</span>
                    <span className="text-gray-500 text-sm mt-1">支持所有影片和音頻格式</span>
                    {file && (
                      <div className="mt-4 p-3 bg-blue-900/30 rounded-lg">
                        <p className="text-blue-300">已選擇: {file.name}</p>
                        <p className="text-gray-400 text-sm">大小: {(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                      </div>
                    )}
                  </label>
                </div>
              </div>

              <button
                type="submit"
                disabled={!file || loading}
                className={`w-full py-3 px-4 rounded-lg font-bold text-lg transition-colors ${
                  !file || loading 
                    ? 'bg-gray-600 text-gray-400 cursor-not-allowed' 
                    : 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white'
                }`}
              >
                {loading ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    處理中...
                  </span>
                ) : '開始轉換'}
              </button>
            </form>
          </div>

          <div>
            {logs.length > 0 && (
              <div className="bg-gray-800 rounded-xl shadow-xl p-6 border border-gray-700 mb-8">
                <h2 className="text-2xl font-bold mb-4 text-blue-400">處理進度</h2>
                <div className="bg-black text-green-400 p-4 rounded-lg font-mono text-sm h-64 overflow-y-auto">
                  {logs.map((log, index) => (
                    <div key={index} className="mb-1 leading-relaxed">{log}</div>
                  ))}
                </div>
              </div>
            )}

            {zipUrl && (
              <div className="bg-gradient-to-r from-blue-900/50 to-purple-900/50 rounded-xl shadow-xl p-6 border border-blue-700 mb-8">
                <h2 className="text-2xl font-bold mb-4 text-blue-300">轉換完成</h2>
                <p className="text-gray-300 mb-4">您的文件已成功轉換為文字，點擊下方按鈕下載所有格式。</p>
                <a 
                  href={zipUrl} 
                  className="block w-full text-center bg-blue-600 hover:bg-blue-700 text-white py-3 px-4 rounded-lg font-bold transition-colors"
                  download
                >
                  下載 ZIP 文件
                </a>
              </div>
            )}
          </div>
        </div>

        {results && (
          <div className="mt-8 bg-gray-800 rounded-xl shadow-xl p-6 border border-gray-700">
            <h2 className="text-2xl font-bold mb-6 text-blue-400">預覽結果</h2>
            <div className="grid grid-cols-1 gap-6">
              {Object.entries(results).map(([format, content]) => (
                <div key={format} className="border border-gray-700 bg-gray-750 rounded-lg p-4">
                  <h3 className="font-bold mb-3 text-lg flex items-center">
                    <span className="inline-block w-8 h-8 rounded-full bg-blue-500 text-white mr-2 flex items-center justify-center">
                      {format.charAt(0).toUpperCase()}
                    </span>
                    <span className="text-blue-300">{format.toUpperCase()} 格式</span>
                  </h3>
                  <div className="bg-gray-900 p-4 rounded-lg">
                    {format === 'json' ? (
                      <pre className="whitespace-pre-wrap text-gray-300 text-sm">
                        {JSON.stringify(content, null, 2)}
                      </pre>
                    ) : (
                      <pre className="whitespace-pre-wrap text-gray-300">
                        {content}
                      </pre>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 text-center text-gray-500 text-sm">
          <p>© {new Date().getFullYear()} 音頻轉文字服務 - 使用 Whisper 語音辨識模型</p>
        </footer>
      </div>
    </div>
  );
}

export default App; 