import React, { useState } from 'react';
import { Upload, X, Image as ImageIcon } from 'lucide-react';

interface ImageUploadProps {
  maxFiles?: number;
  maxSizeMB?: number;
  acceptedTypes?: string[];
  onImagesChange: (files: File[]) => void;
  existingImages?: string[];
  onRemoveExisting?: (url: string) => void;
}

export const ImageUpload: React.FC<ImageUploadProps> = ({
  maxFiles = 5,
  maxSizeMB = 5,
  acceptedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'],
  onImagesChange,
  existingImages = [],
  onRemoveExisting
}) => {
  const [previews, setPreviews] = useState<string[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string>('');

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files || []);
    setError('');

    // Validate number of files
    if (files.length + selectedFiles.length + existingImages.length > maxFiles) {
      setError(`Maximum ${maxFiles} images allowed`);
      return;
    }

    // Validate file types and sizes
    const validFiles: File[] = [];
    const newPreviews: string[] = [];

    for (const fileItem of selectedFiles) {
      const file = fileItem as File;
      if (!acceptedTypes.includes(file.type)) {
        setError(`Invalid file type: ${file.name}. Only ${acceptedTypes.join(', ')} are allowed.`);
        continue;
      }

      if (file.size > maxSizeMB * 1024 * 1024) {
        setError(`${file.name} is too large. Maximum size is ${maxSizeMB}MB.`);
        continue;
      }

      validFiles.push(file);
      
      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        newPreviews.push(reader.result as string);
        if (newPreviews.length === validFiles.length) {
          setPreviews([...previews, ...newPreviews]);
        }
      };
      reader.readAsDataURL(file as Blob);
    }

    const updatedFiles = [...files, ...validFiles];
    setFiles(updatedFiles);
    onImagesChange(updatedFiles);
  };

  const handleRemoveNew = (index: number) => {
    const newFiles = files.filter((_, i) => i !== index);
    const newPreviews = previews.filter((_, i) => i !== index);
    setFiles(newFiles);
    setPreviews(newPreviews);
    onImagesChange(newFiles);
    setError('');
  };

  const totalImages = existingImages.length + files.length;

  return (
    <div className="space-y-4">
      {/* Upload Area */}
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 hover:border-blue-500 transition-colors">
        <input
          type="file"
          id="image-upload"
          multiple
          accept={acceptedTypes.join(',')}
          onChange={handleFileSelect}
          className="hidden"
          disabled={totalImages >= maxFiles}
        />
        <label
          htmlFor="image-upload"
          className={`flex flex-col items-center justify-center cursor-pointer ${
            totalImages >= maxFiles ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          <Upload className="w-12 h-12 text-gray-400 mb-2" />
          <p className="text-sm font-medium text-gray-700">
            {totalImages >= maxFiles ? 'Maximum images reached' : 'Click to upload images'}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {acceptedTypes.map(t => t.split('/')[1].toUpperCase()).join(', ')} up to {maxSizeMB}MB
          </p>
          <p className="text-xs text-gray-500">
            ({totalImages}/{maxFiles} images)
          </p>
        </label>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Existing Images */}
      {existingImages.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">Current Images</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {existingImages.map((url, index) => (
              <div key={`existing-${index}`} className="relative group">
                <img
                  src={url}
                  alt={`Existing ${index + 1}`}
                  className="w-full h-32 object-cover rounded-lg border border-gray-200"
                />
                {onRemoveExisting && (
                  <button
                    type="button"
                    onClick={() => onRemoveExisting(url)}
                    className="absolute top-2 right-2 bg-red-600 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-700"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
                <div className="absolute bottom-2 left-2 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded">
                  Existing
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* New Image Previews */}
      {previews.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">New Images</h4>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {previews.map((preview, index) => (
              <div key={`new-${index}`} className="relative group">
                <img
                  src={preview}
                  alt={`Preview ${index + 1}`}
                  className="w-full h-32 object-cover rounded-lg border border-gray-200"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveNew(index)}
                  className="absolute top-2 right-2 bg-red-600 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-700"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="absolute bottom-2 left-2 bg-green-600 text-white text-xs px-2 py-1 rounded">
                  New
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {existingImages.length === 0 && previews.length === 0 && (
        <div className="text-center py-8">
          <ImageIcon className="w-16 h-16 text-gray-300 mx-auto mb-2" />
          <p className="text-sm text-gray-500">No images uploaded yet</p>
        </div>
      )}
    </div>
  );
};
