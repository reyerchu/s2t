import React, { useState, useRef } from 'react';
import axios from 'axios';

// Configure axios base URL and timeout
axios.defaults.baseURL = '/s2t/api';
axios.defaults.timeout = 1800000; // 5 minutes timeout

function App() {
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState('');
  const [inputMode, setInputMode] = useState('file'); // 'file' or 'url'
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

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isDragging) setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles && droppedFiles.length > 0) {
      setFile(droppedFiles[0]);
      setLogs([]);
      setResults(null);
      setZipUrl(null);
      
      // 更新文件輸入框的值（供參考）
      if (fileInputRef.current) {
        // 因为安全原因，无法直接设置 input 的 files 属性，但这不影响我们处理拖放的文件
        // fileInputRef.current.files = droppedFiles;
      }
    }
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

  const handleUrlChange = (e) => {
    setUrl(e.target.value);
    setLogs([]);
    setResults(null);
    setZipUrl(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (inputMode === 'file' && !file) return;
    if (inputMode === 'url' && !url) return;

    setLoading(true);
    setLogs([]);
    setZipUrl(null);  // Clear the zipUrl when starting a new transcription
    
    const formats = Object.entries(selectedFormats)
      .filter(([_, selected]) => selected)
      .map(([format]) => format);
    
    addLog(`選擇的輸出格式: ${formats.join(', ')}`);

    try {
      if (inputMode === 'file') {
        addLog(`開始處理文件: ${file.name}`);
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
      setPassword(''); // Reset password when opening dialog
      setShowPasswordDialog(true);
    } catch (error) {
      console.error('Error fetching temp size:', error);
      addLog(`獲取暫存資料夾大小失敗: ${error.message}`);
      setTempFolderSize(null);
      setShowPasswordDialog(true);
    }
  };

  const handlePasswordSubmit = async () => {
    // If password is empty, treat as cancel
    if (!password.trim()) {
      setShowPasswordDialog(false);
      setPassword('');
      return;
    }

    // Process the password attempt
    if (password === 'admin123') {
      try {
        setCleaningStatus('cleaning');
        addLog('正在清空暫存檔案...');
        await axios.post('/clean-temp', { password });
        setCleaningStatus('success');
        setZipUrl(null);  // Clear the zipUrl when cleaning temporary files
        addLog('暫存檔案已清空');
      } catch (error) {
        setCleaningStatus('error');
        addLog(`清空暫存檔案失敗: ${error.message}`);
      }
    } else {
      setCleaningStatus('error');
      addLog('密碼錯誤');
    }
    
    // Always close the dialog and reset password after attempt
    setShowPasswordDialog(false);
    setPassword('');
  };

  const handlePasswordKeyDown = (e) => {
    if (e.key === 'Enter') {
      handlePasswordSubmit();
    } else if (e.key === 'Escape') {
      setShowPasswordDialog(false);
      setPassword('');
    }
  };

  return (
    <div className="min-h-screen bg-white text-gray-800">
      {/* Header */}
      <header className="bg-gradient-to-r from-amber-600 to-yellow-500 py-6 shadow-md">
        <div className="container mx-auto px-4">
          <h1 className="text-4xl font-bold text-white">
            影音轉文字服務
          </h1>
          <p className="text-amber-100 mt-2">
            將您的影片或音頻檔案轉換為多種格式的文字內容
          </p>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        {/* Admin Actions */}
        <div className="mb-8">
          <button
            onClick={handleCleanFiles}
            className="bg-red-600 hover:bg-red-700 text-white py-2 px-4 rounded-lg font-medium transition-colors float-right"
          >
            清空暫存檔案
          </button>
          <div className="clear-both"></div>
        </div>

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <h2 className="text-2xl font-bold mb-6 text-amber-700">選擇輸出格式</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-8">
              {Object.entries({
                txt: '.txt (純文字)',
                srt: '.srt (字幕)',
                vtt: '.vtt (網頁字幕)',
                tsv: '.tsv (Excel)',
                json: '.json (完整數據)'
              }).map(([format, label]) => (
                <label key={format} className="flex items-center space-x-3 p-3 rounded-lg bg-amber-50 hover:bg-amber-100 transition-colors cursor-pointer border border-amber-200">
                  <input
                    type="checkbox"
                    checked={selectedFormats[format]}
                    onChange={() => handleFormatChange(format)}
                    className="form-checkbox h-5 w-5 text-amber-600 rounded"
                  />
                  <span className="text-gray-700">{label}</span>
                </label>
              ))}
            </div>

            <form onSubmit={handleSubmit}>
              <div className="mb-6">
                <div className="flex space-x-4 mb-4">
                  <button
                    type="button"
                    onClick={() => setInputMode('file')}
                    className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                      inputMode === 'file'
                        ? 'bg-amber-600 text-white'
                        : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                    }`}
                  >
                    上傳檔案
                  </button>
                  <button
                    type="button"
                    onClick={() => setInputMode('url')}
                    className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                      inputMode === 'url'
                        ? 'bg-amber-600 text-white'
                        : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                    }`}
                  >
                    輸入網址
                  </button>
                </div>

                {inputMode === 'file' ? (
                  <div 
                    className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                      isDragging 
                        ? 'border-amber-600 bg-amber-100' 
                        : 'border-amber-300 hover:border-amber-500 bg-amber-50'
                    }`}
                    onDragEnter={handleDragEnter}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                  >
                    <input
                      type="file"
                      accept="*/*"
                      onChange={handleFileChange}
                      className="hidden"
                      id="file-upload"
                      ref={fileInputRef}
                    />
                    <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-amber-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      <span className="text-gray-700 text-lg font-medium">
                        {isDragging ? '放開以上傳文件' : '選擇文件或拖放至此'}
                      </span>
                      <span className="text-gray-500 text-sm mt-1">支持所有影片和音頻格式</span>
                      {file && (
                        <div className="mt-4 p-3 bg-amber-100 rounded-lg">
                          <p className="text-amber-700">已選擇: {file.name}</p>
                        </div>
                      )}
                    </label>
                  </div>
                ) : (
                  <div className="border-2 border-dashed rounded-lg p-8 text-center transition-colors border-amber-300 bg-amber-50">
                    <div className="flex flex-col items-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 text-amber-500 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                      </svg>
                      <input
                        type="text"
                        value={url}
                        onChange={handleUrlChange}
                        placeholder="請輸入 YouTube、Facebook 或 Google Drive 連結"
                        className="w-full px-4 py-2 border border-amber-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                      />
                      <div className="mt-2 text-sm text-gray-500">
                        支援的連結格式：
                        <ul className="list-disc list-inside mt-1 text-left">
                          <li>YouTube 影片連結 (例如: https://www.youtube.com/watch?v=...)</li>
                          <li>YouTube 短連結 (例如: https://youtu.be/...)</li>
                          <li>Facebook 影片/Reel 連結 (例如: facebook.com/reel/... 或 facebook.com/share/...)</li>
                          <li>Google Drive 音頻/視頻檔案連結</li>
                        </ul>
                      </div>
                      {url && (
                        <div className="mt-4 p-3 bg-amber-100 rounded-lg">
                          <p className="text-amber-700">已輸入: {url}</p>
                          {url.includes('youtube.com') || url.includes('youtu.be') ? (
                            <p className="text-sm text-amber-600 mt-1">✓ YouTube 連結已識別</p>
                          ) : url.includes('facebook.com') || url.includes('fb.watch') ? (
                            <p className="text-sm text-amber-600 mt-1">✓ Facebook 連結已識別</p>
                          ) : url.includes('drive.google.com') ? (
                            <p className="text-sm text-amber-600 mt-1">✓ Google Drive 連結已識別</p>
                          ) : (
                            <p className="text-sm text-red-600 mt-1">⚠ 請輸入有效的連結</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              <button
                type="submit"
                disabled={loading || (inputMode === 'file' ? !file : !url)}
                className={`w-full py-3 px-4 rounded-lg font-medium text-white transition-colors ${
                  loading || (inputMode === 'file' ? !file : !url)
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-amber-600 hover:bg-amber-700'
                }`}
              >
                {loading ? '處理中...' : '開始轉錄'}
              </button>
            </form>
          </div>

          <div>
            {logs.length > 0 && (
              <div className="bg-white rounded-xl shadow-md p-6 border border-gray-200 mb-8">
                <h2 className="text-2xl font-bold mb-4 text-amber-700">處理進度</h2>
                <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm h-64 overflow-y-auto">
                  {logs.map((log, index) => (
                    <div key={index} className="mb-1 leading-relaxed">{log}</div>
                  ))}
                </div>
              </div>
            )}

            {zipUrl && (
              <div className="bg-amber-50 rounded-xl shadow-md p-6 border border-amber-200 mb-8">
                <h2 className="text-2xl font-bold mb-4 text-amber-700">轉換完成</h2>
                <p className="text-gray-700 mb-4">您的文件已成功轉換為文字，點擊下方按鈕下載所有格式。</p>
                <div className="mt-4">
                  <a
                    href={zipUrl}
                    download
                    className="block w-full text-center bg-amber-600 hover:bg-amber-700 text-white py-3 px-4 rounded-lg font-bold transition-colors"
                  >
                    下載 ZIP 文件：{zipUrl.split('/').pop()}
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>

        {results && (
          <div className="mt-8 bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <h2 className="text-2xl font-bold mb-6 text-amber-700">預覽結果</h2>
            <div className="grid grid-cols-1 gap-6">
              {/* 摘要優先顯示 */}
              {results.summary && (
                <div className="border-2 border-green-300 bg-green-50 rounded-lg p-4">
                  <h3 className="font-bold mb-3 text-lg flex items-center">
                    <span className="inline-block w-8 h-8 rounded-full bg-green-600 text-white mr-2 flex items-center justify-center">
                      📝
                    </span>
                    <span className="text-green-700">AI 內容摘要</span>
                  </h3>
                  <div className="bg-white p-4 rounded-lg border border-gray-200 prose prose-sm max-w-none">
                    <pre className="whitespace-pre-wrap text-gray-700">
                      {results.summary}
                    </pre>
                  </div>
                </div>
              )}
              {/* 其他格式 */}
              {Object.entries(results).filter(([format]) => format !== 'summary').map(([format, content]) => (
                <div key={format} className="border border-amber-200 bg-amber-50 rounded-lg p-4">
                  <h3 className="font-bold mb-3 text-lg flex items-center">
                    <span className="inline-block w-8 h-8 rounded-full bg-amber-600 text-white mr-2 flex items-center justify-center">
                      {format.charAt(0).toUpperCase()}
                    </span>
                    <span className="text-amber-700">{format.toUpperCase()} 格式</span>
                  </h3>
                  <div className="bg-white p-4 rounded-lg border border-gray-200">
                    {format === 'json' ? (
                      <pre className="whitespace-pre-wrap text-gray-700 text-sm">
                        {JSON.stringify(content, null, 2)}
                      </pre>
                    ) : (
                      <pre className="whitespace-pre-wrap text-gray-700">
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

      {/* Password Dialog */}
      {showPasswordDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-96">
            <h3 className="text-xl font-bold mb-4 text-amber-700">需要密碼</h3>
            <p className="text-gray-600 mb-4">
              請輸入管理員密碼以清空暫存檔案
              {tempFolderSize && ` (${tempFolderSize.size_mb} MBytes，${tempFolderSize.file_count} 個檔案)`}
            </p>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={handlePasswordKeyDown}
              className="w-full p-2 border border-gray-300 rounded mb-4"
              placeholder="請輸入密碼"
              autoFocus
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => {
                  setShowPasswordDialog(false);
                  setPassword('');
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
              >
                取消
              </button>
              <button
                onClick={handlePasswordSubmit}
                className="px-4 py-2 bg-amber-600 text-white rounded hover:bg-amber-700"
              >
                確認
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Processing Status */}
      {cleaningStatus && (
        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-2 text-amber-700">處理進度</h3>
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center mb-2">
              <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mr-2"></div>
              <span className="text-gray-700">處理中...</span>
            </div>
            <div className="text-sm text-gray-600">
              {cleaningStatus === 'cleaning' && '正在清空暫存檔案...'}
              {cleaningStatus === 'success' && '暫存檔案已清空'}
              {cleaningStatus === 'error' && '清空暫存檔案失敗'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App; 