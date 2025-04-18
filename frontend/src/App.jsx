import React, { useState, useEffect } from 'react';
import axios from 'axios';

function App() {
  const [file, setFile] = useState(null);
  const [fileList, setFileList] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedFormats, setSelectedFormats] = useState({
    txt: true,
    srt: true,
    vtt: true,
    tsv: true,
    json: true
  });
  const [zipUrl, setZipUrl] = useState(null);

  // 獲取文件列表
  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const response = await axios.get('http://localhost:8000/files');
        setFileList(response.data.files);
      } catch (error) {
        console.error('Error fetching files:', error);
      }
    };
    
    fetchFiles();
  }, []);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleFormatChange = (format) => {
    setSelectedFormats(prev => ({
      ...prev,
      [format]: !prev[format]
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);
    
    // 將選中的格式轉換為數組
    const formats = Object.entries(selectedFormats)
      .filter(([_, selected]) => selected)
      .map(([format]) => format);
    
    formData.append('output_formats', JSON.stringify(formats));

    try {
      const response = await axios.post('http://localhost:8000/transcribe', formData);
      setResults(response.data.data);
      setZipUrl(`http://localhost:8000${response.data.zip_url}`);
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-3xl font-bold mb-4">音頻轉文字服務</h1>
      
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2">選擇輸出格式</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={selectedFormats.txt}
              onChange={() => handleFormatChange('txt')}
              className="form-checkbox h-5 w-5 text-blue-600"
            />
            <span>.txt (純文字)</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={selectedFormats.srt}
              onChange={() => handleFormatChange('srt')}
              className="form-checkbox h-5 w-5 text-blue-600"
            />
            <span>.srt (字幕)</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={selectedFormats.vtt}
              onChange={() => handleFormatChange('vtt')}
              className="form-checkbox h-5 w-5 text-blue-600"
            />
            <span>.vtt (網頁字幕)</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={selectedFormats.tsv}
              onChange={() => handleFormatChange('tsv')}
              className="form-checkbox h-5 w-5 text-blue-600"
            />
            <span>.tsv (Excel)</span>
          </label>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={selectedFormats.json}
              onChange={() => handleFormatChange('json')}
              className="form-checkbox h-5 w-5 text-blue-600"
            />
            <span>.json (完整數據)</span>
          </label>
        </div>
      </div>
      
      <form onSubmit={handleSubmit} className="mb-4">
        <div className="mb-4">
          <h2 className="text-xl font-bold mb-2">上傳新文件</h2>
          <input
            type="file"
            accept="audio/*,video/*"
            onChange={handleFileChange}
            className="mb-2"
          />
        </div>
        
        <div className="mb-4">
          <h2 className="text-xl font-bold mb-2">或選擇已有文件</h2>
          <select 
            className="w-full p-2 border rounded"
            onChange={(e) => {
              if (e.target.value) {
                // 創建一個假的 File 對象
                const fakeFile = new File([], e.target.value);
                setFile(fakeFile);
              } else {
                setFile(null);
              }
            }}
          >
            <option value="">-- 選擇文件 --</option>
            {fileList.map((fileName) => (
              <option key={fileName} value={fileName}>
                {fileName}
              </option>
            ))}
          </select>
        </div>
        
        <button
          type="submit"
          disabled={!file || loading}
          className="bg-blue-500 text-white px-4 py-2 rounded"
        >
          {loading ? '處理中...' : '開始轉換'}
        </button>
      </form>

      {zipUrl && (
        <div className="mb-4 p-4 bg-green-100 rounded">
          <h2 className="text-xl font-bold mb-2">轉換完成</h2>
          <a 
            href={zipUrl} 
            className="bg-green-500 text-white px-4 py-2 rounded inline-block"
            download
          >
            下載 ZIP 文件
          </a>
        </div>
      )}

      {results && (
        <div className="results">
          <h2 className="text-xl font-bold mb-2">預覽結果</h2>
          
          <div className="grid grid-cols-1 gap-4">
            {Object.entries(results).map(([format, content]) => (
              <div key={format} className="border p-4 rounded">
                <h3 className="font-bold mb-2">{format.toUpperCase()} 格式</h3>
                {format === 'json' ? (
                  <pre className="whitespace-pre-wrap">
                    {JSON.stringify(content, null, 2)}
                  </pre>
                ) : (
                  <pre className="whitespace-pre-wrap">{content}</pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default App; 