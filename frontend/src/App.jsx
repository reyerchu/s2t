import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
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
      const response = await axios.post('/s2t/api/transcribe', formData, {
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          addLog(`上傳進度: ${percentCompleted}%`);
        }
      });
      
      addLog('文件處理完成');
      setResults(response.data.data);
      setZipUrl(`/s2t/api${response.data.zip_url}`);
      addLog('可以下載轉錄結果了');
    } catch (error) {
      console.error('Error:', error);
      addLog(`錯誤: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 修改為獲取暫存資料夾大小
  const handleCleanFiles = async () => {
    try {
      const response = await axios.get('/s2t/api/temp-size');
      setTempFolderSize(response.data);
      setShowPasswordDialog(true);
    } catch (error) {
      console.error('Error fetching temp size:', error);
      addLog(`獲取暫存資料夾大小失敗: ${error.message}`);
      // 如果獲取大小失敗，仍然顯示對話框但不顯示大小
      setTempFolderSize(null);
      setShowPasswordDialog(true);
    }
  };

  const handlePasswordSubmit = async () => {
    setCleaningStatus('處理中...');
    try {
      const response = await axios.post('/s2t/api/clean-temp', { password });
      if (response.data.success) {
        setCleaningStatus('成功清空暫存檔案');
        addLog('已清空所有暫存檔案');
      } else {
        setCleaningStatus('密碼錯誤或清空失敗');
        addLog('清空暫存檔案失敗: 密碼錯誤');
      }
    } catch (error) {
      console.error('Error:', error);
      setCleaningStatus('發生錯誤');
      addLog(`清空暫存檔案錯誤: ${error.message}`);
    } finally {
      setTimeout(() => {
        setCleaningStatus(null);
        setShowPasswordDialog(false);
        setPassword('');
      }, 3000);
    }
  };

  const handleCancelPasswordDialog = () => {
    setShowPasswordDialog(false);
    setPassword('');
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
              <h2 className="text-2xl font-bold mb-4 text-amber-700">上傳文件</h2>
              <div className="mb-6">
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
                        <p className="text-gray-600 text-sm">大小: {(file.size / (1024 * 1024)).toFixed(2)} MB</p>
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
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                    : 'bg-amber-600 hover:bg-amber-700 text-white'
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
                <a 
                  href={zipUrl} 
                  className="block w-full text-center bg-amber-600 hover:bg-amber-700 text-white py-3 px-4 rounded-lg font-bold transition-colors"
                  download
                >
                  下載 ZIP 文件
                </a>
              </div>
            )}
          </div>
        </div>

        {results && (
          <div className="mt-8 bg-white rounded-xl shadow-md p-6 border border-gray-200">
            <h2 className="text-2xl font-bold mb-6 text-amber-700">預覽結果</h2>
            <div className="grid grid-cols-1 gap-6">
              {Object.entries(results).map(([format, content]) => (
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
          <div className="bg-white rounded-xl shadow-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-bold mb-4 text-amber-700">需要密碼</h3>
            <p className="text-gray-700 mb-4">
              請輸入密碼以清空暫存檔案
              {tempFolderSize && ` (${tempFolderSize.size_mb} MBytes，${tempFolderSize.file_count} 個檔案)`}
            </p>
            
            <form onSubmit={(e) => {
              e.preventDefault();
              handlePasswordSubmit();
            }}>
              <div className="mb-4">
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="請輸入密碼"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                  autoFocus
                />
              </div>

              {cleaningStatus && (
                <div className={`mb-4 p-3 rounded-lg ${
                  cleaningStatus.includes('成功') 
                    ? 'bg-green-100 text-green-700' 
                    : 'bg-red-100 text-red-700'
                }`}>
                  {cleaningStatus}
                </div>
              )}

              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={handleCancelPasswordDialog}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg transition-colors"
                >
                  確認
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default App; 