'use client';

import React, { useState, useCallback } from 'react';
import { ScreenplayImportResult } from '@/types/screenplay';

interface ScreenplayUploadProps {
  onUploadComplete: (result: ScreenplayImportResult) => void;
  onError: (error: string) => void;
}

export default function ScreenplayUpload({ onUploadComplete, onError }: ScreenplayUploadProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  }, []);

  const handleFile = (file: File) => {
    // Check file type
    const validTypes = [
      'text/plain',
      'text/markdown',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];
    
    const validExtensions = ['.txt', '.md', '.fountain', '.screenplay', '.script', '.pdf', '.docx'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    
    if (!validTypes.includes(file.type) && !validExtensions.includes(fileExtension)) {
      onError('Please upload a valid screenplay file (.txt, .md, .fountain, .pdf, .docx)');
      return;
    }

    // Check file size (50MB limit)
    if (file.size > 50 * 1024 * 1024) {
      onError('File size must be less than 50MB');
      return;
    }

    setFile(file);
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('format', 'screenplay');

      const response = await fetch('/api/v1/books/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Upload failed');
      }

      const result: ScreenplayImportResult = await response.json();
      onUploadComplete(result);
      setFile(null);
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const getFileIcon = () => {
    if (!file) return null;
    
    const extension = file.name.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'fountain':
        return '🎬';
      case 'txt':
      case 'md':
        return '📄';
      case 'pdf':
        return '📕';
      case 'docx':
        return '📘';
      default:
        return '📝';
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Upload Screenplay</h2>
        <p className="text-gray-600">
          Upload your screenplay in Fountain format, plain text, or PDF. 
          We'll automatically parse scenes, dialogue, and characters.
        </p>
      </div>

      {/* Upload Area */}
      <div
        className={`relative border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          type="file"
          id="screenplay-upload"
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          onChange={handleChange}
          accept=".txt,.md,.fountain,.screenplay,.script,.pdf,.docx"
        />
        
        <div className="space-y-4">
          <div className="text-4xl">
            {file ? getFileIcon() : '📤'}
          </div>
          
          {file ? (
            <div>
              <p className="font-medium">{file.name}</p>
              <p className="text-sm text-gray-500">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
          ) : (
            <div>
              <p className="font-medium">Drop your screenplay file here</p>
              <p className="text-sm text-gray-500">
                or click to browse
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Supported Formats */}
      <div className="mt-6 p-4 bg-gray-50 rounded-lg">
        <h3 className="font-medium mb-2">Supported Formats:</h3>
        <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
          <div>• Fountain (.fountain)</div>
          <div>• Plain Text (.txt)</div>
          <div>• Markdown (.md)</div>
          <div>• PDF Screenplays (.pdf)</div>
          <div>• Word Documents (.docx)</div>
          <div>• Custom Formats (.screenplay, .script)</div>
        </div>
      </div>

      {/* Upload Button */}
      {file && (
        <div className="mt-6 flex justify-center space-x-4">
          <button
            onClick={() => setFile(null)}
            className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleUpload}
            disabled={isUploading}
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            {isUploading ? 'Uploading...' : 'Upload Screenplay'}
          </button>
        </div>
      )}

      {/* Upload Progress */}
      {isUploading && (
        <div className="mt-6">
          <div className="flex items-center justify-center space-x-2">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
            <span className="text-sm text-gray-600">Processing screenplay...</span>
          </div>
          <p className="text-xs text-gray-500 text-center mt-2">
            This may take a moment for large files
          </p>
        </div>
      )}
    </div>
  );
}
