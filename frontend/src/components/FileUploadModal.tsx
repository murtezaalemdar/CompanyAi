import { useState, useRef, useCallback, useEffect } from 'react'
import {
    X,
    Upload,
    Camera,
    Image as ImageIcon,
    FileText,
    File,
    Trash2,
    Check,
    AlertCircle,
    Loader2,
    Video,
    StopCircle,
    RotateCcw,
    ZoomIn,
    Download
} from 'lucide-react'
import clsx from 'clsx'

interface UploadedFile {
    id: string
    file: File
    preview?: string
    type: 'image' | 'document' | 'other'
    status: 'uploading' | 'success' | 'error'
    progress: number
    errorMessage?: string
}

interface FileUploadModalProps {
    isOpen: boolean
    onClose: () => void
    onFilesSelected: (files: File[]) => void
    maxFiles?: number
    maxSizePerFile?: number // MB cinsinden
    acceptedTypes?: string[]
}

const DEFAULT_ACCEPTED_TYPES = [
    // Images
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'image/svg+xml',
    'image/bmp',
    // Documents
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain',
    'text/csv',
    'application/json',
    // Archives
    'application/zip',
    'application/x-rar-compressed',
]

export default function FileUploadModal({
    isOpen,
    onClose,
    onFilesSelected,
    maxFiles = 10,
    maxSizePerFile = 50, // 50 MB default
    acceptedTypes = DEFAULT_ACCEPTED_TYPES,
}: FileUploadModalProps) {
    const [activeTab, setActiveTab] = useState<'upload' | 'camera'>('upload')
    const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
    const [isDragging, setIsDragging] = useState(false)
    const [previewFile, setPreviewFile] = useState<UploadedFile | null>(null)

    // Camera states
    const [isCameraActive, setIsCameraActive] = useState(false)
    const [cameraStream, setCameraStream] = useState<MediaStream | null>(null)
    const [capturedImage, setCapturedImage] = useState<string | null>(null)
    const [cameraError, setCameraError] = useState<string | null>(null)
    const [facingMode, setFacingMode] = useState<'user' | 'environment'>('environment')

    const fileInputRef = useRef<HTMLInputElement>(null)
    const videoRef = useRef<HTMLVideoElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)

    // Cleanup camera on unmount or close
    useEffect(() => {
        return () => {
            if (cameraStream) {
                cameraStream.getTracks().forEach(track => track.stop())
            }
        }
    }, [cameraStream])

    // Reset states when modal closes
    useEffect(() => {
        if (!isOpen) {
            stopCamera()
            setCapturedImage(null)
            setCameraError(null)
        }
    }, [isOpen])

    const getFileType = (file: File): 'image' | 'document' | 'other' => {
        if (file.type.startsWith('image/')) return 'image'
        if (
            file.type.includes('pdf') ||
            file.type.includes('word') ||
            file.type.includes('excel') ||
            file.type.includes('powerpoint') ||
            file.type.includes('text') ||
            file.type.includes('csv') ||
            file.type.includes('json')
        ) return 'document'
        return 'other'
    }

    const getFileIcon = (type: 'image' | 'document' | 'other') => {
        switch (type) {
            case 'image':
                return <ImageIcon className="w-8 h-8" />
            case 'document':
                return <FileText className="w-8 h-8" />
            default:
                return <File className="w-8 h-8" />
        }
    }

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes'
        const k = 1024
        const sizes = ['Bytes', 'KB', 'MB', 'GB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    }

    const validateFile = (file: File): { valid: boolean; error?: string } => {
        // Check size
        if (file.size > maxSizePerFile * 1024 * 1024) {
            return { valid: false, error: `Dosya çok büyük (max: ${maxSizePerFile}MB)` }
        }
        // Check type
        if (acceptedTypes.length > 0 && !acceptedTypes.includes(file.type)) {
            return { valid: false, error: 'Desteklenmeyen dosya formatı' }
        }
        return { valid: true }
    }

    const processFiles = useCallback((files: FileList | File[]) => {
        const fileArray = Array.from(files)
        const remainingSlots = maxFiles - uploadedFiles.length

        if (fileArray.length > remainingSlots) {
            alert(`En fazla ${maxFiles} dosya yükleyebilirsiniz. Kalan slot: ${remainingSlots}`)
            return
        }

        const newFiles: UploadedFile[] = fileArray.map((file) => {
            const validation = validateFile(file)
            const type = getFileType(file)

            const uploadedFile: UploadedFile = {
                id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                file,
                type,
                status: validation.valid ? 'success' : 'error',
                progress: validation.valid ? 100 : 0,
                errorMessage: validation.error,
            }

            // Generate preview for images
            if (type === 'image' && validation.valid) {
                const reader = new FileReader()
                reader.onload = (e) => {
                    setUploadedFiles((prev) =>
                        prev.map((f) =>
                            f.id === uploadedFile.id
                                ? { ...f, preview: e.target?.result as string }
                                : f
                        )
                    )
                }
                reader.readAsDataURL(file)
            }

            return uploadedFile
        })

        setUploadedFiles((prev) => [...prev, ...newFiles])
    }, [uploadedFiles.length, maxFiles, maxSizePerFile, acceptedTypes])

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
        processFiles(e.dataTransfer.files)
    }, [processFiles])

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(true)
    }, [])

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault()
        setIsDragging(false)
    }, [])

    const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            processFiles(e.target.files)
        }
    }

    const removeFile = (id: string) => {
        setUploadedFiles((prev) => prev.filter((f) => f.id !== id))
    }

    const clearAllFiles = () => {
        setUploadedFiles([])
    }

    // Camera functions
    const startCamera = async () => {
        try {
            setCameraError(null)
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode,
                    width: { ideal: 1920 },
                    height: { ideal: 1080 },
                },
                audio: false,
            })

            if (videoRef.current) {
                videoRef.current.srcObject = stream
            }
            setCameraStream(stream)
            setIsCameraActive(true)
        } catch (error) {
            console.error('Camera error:', error)
            setCameraError('Kameraya erişim sağlanamadı. Lütfen izinleri kontrol edin.')
        }
    }

    const stopCamera = () => {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop())
            setCameraStream(null)
        }
        setIsCameraActive(false)
    }

    const switchCamera = () => {
        stopCamera()
        setFacingMode(prev => prev === 'user' ? 'environment' : 'user')
        setTimeout(startCamera, 100)
    }

    const capturePhoto = () => {
        if (videoRef.current && canvasRef.current) {
            const video = videoRef.current
            const canvas = canvasRef.current

            canvas.width = video.videoWidth
            canvas.height = video.videoHeight

            const ctx = canvas.getContext('2d')
            if (ctx) {
                ctx.drawImage(video, 0, 0)
                const imageData = canvas.toDataURL('image/jpeg', 0.9)
                setCapturedImage(imageData)
                stopCamera()
            }
        }
    }

    const retakePhoto = () => {
        setCapturedImage(null)
        startCamera()
    }

    const useCapturedPhoto = () => {
        if (capturedImage) {
            // Convert base64 to File
            fetch(capturedImage)
                .then(res => res.blob())
                .then(blob => {
                    // Create file from blob with proper typing
                    const fileName = `camera_${Date.now()}.jpg`
                    const file = new window.File([blob], fileName, { type: 'image/jpeg' })
                    processFiles([file])
                    setCapturedImage(null)
                    setActiveTab('upload')
                })
        }
    }

    const handleConfirm = () => {
        const validFiles = uploadedFiles
            .filter((f) => f.status === 'success')
            .map((f) => f.file)

        if (validFiles.length > 0) {
            onFilesSelected(validFiles)
        }
        onClose()
    }

    if (!isOpen) return null

    const successfulFiles = uploadedFiles.filter((f) => f.status === 'success')

    return (
        <>
            {/* Main Modal */}
            <div className="fixed inset-0 z-50 flex items-center justify-center">
                {/* Backdrop */}
                <div
                    className="absolute inset-0 bg-black/70 backdrop-blur-sm"
                    onClick={onClose}
                />

                {/* Modal Content */}
                <div className="relative bg-dark-900 rounded-2xl border border-dark-700 w-full max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl">
                    {/* Header */}
                    <div className="flex items-center justify-between p-6 border-b border-dark-700">
                        <div className="flex items-center gap-4">
                            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center">
                                <Upload className="w-6 h-6 text-white" />
                            </div>
                            <div>
                                <h2 className="text-xl font-semibold text-white">Dosya Yükle</h2>
                                <p className="text-sm text-dark-400">
                                    Resim, doküman veya diğer dosyaları ekleyin
                                </p>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-dark-800 rounded-lg transition-colors"
                        >
                            <X className="w-6 h-6 text-dark-400" />
                        </button>
                    </div>

                    {/* Tabs */}
                    <div className="flex border-b border-dark-700">
                        <button
                            onClick={() => {
                                setActiveTab('upload')
                                stopCamera()
                            }}
                            className={clsx(
                                'flex-1 px-6 py-4 flex items-center justify-center gap-2 font-medium transition-all',
                                activeTab === 'upload'
                                    ? 'text-primary-400 border-b-2 border-primary-400 bg-primary-500/5'
                                    : 'text-dark-400 hover:text-white hover:bg-dark-800/50'
                            )}
                        >
                            <Upload className="w-5 h-5" />
                            Dosya Yükle
                        </button>
                        <button
                            onClick={() => {
                                setActiveTab('camera')
                                if (!isCameraActive && !capturedImage) {
                                    startCamera()
                                }
                            }}
                            className={clsx(
                                'flex-1 px-6 py-4 flex items-center justify-center gap-2 font-medium transition-all',
                                activeTab === 'camera'
                                    ? 'text-primary-400 border-b-2 border-primary-400 bg-primary-500/5'
                                    : 'text-dark-400 hover:text-white hover:bg-dark-800/50'
                            )}
                        >
                            <Camera className="w-5 h-5" />
                            Kamera
                        </button>
                    </div>

                    {/* Content */}
                    <div className="p-6 max-h-[60vh] overflow-y-auto">
                        {activeTab === 'upload' ? (
                            <div className="space-y-6">
                                {/* Drop Zone */}
                                <div
                                    onDrop={handleDrop}
                                    onDragOver={handleDragOver}
                                    onDragLeave={handleDragLeave}
                                    onClick={() => fileInputRef.current?.click()}
                                    className={clsx(
                                        'border-2 border-dashed rounded-2xl p-8 transition-all cursor-pointer',
                                        isDragging
                                            ? 'border-primary-400 bg-primary-500/10'
                                            : 'border-dark-600 hover:border-dark-500 hover:bg-dark-800/30'
                                    )}
                                >
                                    <div className="flex flex-col items-center gap-4 text-center">
                                        <div className={clsx(
                                            'w-16 h-16 rounded-2xl flex items-center justify-center transition-colors',
                                            isDragging ? 'bg-primary-500/20 text-primary-400' : 'bg-dark-800 text-dark-400'
                                        )}>
                                            <Upload className="w-8 h-8" />
                                        </div>
                                        <div>
                                            <p className="text-lg font-medium text-white">
                                                {isDragging ? 'Dosyaları bırakın' : 'Dosyaları sürükleyip bırakın'}
                                            </p>
                                            <p className="text-sm text-dark-400 mt-1">
                                                veya <span className="text-primary-400">dosya seç</span>
                                            </p>
                                        </div>
                                        <div className="flex flex-wrap justify-center gap-2 text-xs text-dark-500">
                                            <span className="px-2 py-1 bg-dark-800 rounded">PNG, JPG, WEBP</span>
                                            <span className="px-2 py-1 bg-dark-800 rounded">PDF, DOCX, XLSX</span>
                                            <span className="px-2 py-1 bg-dark-800 rounded">TXT, CSV, JSON</span>
                                        </div>
                                        <p className="text-xs text-dark-500">
                                            Maksimum {maxSizePerFile}MB, {maxFiles} dosyaya kadar
                                        </p>
                                    </div>
                                </div>

                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    multiple
                                    accept={acceptedTypes.join(',')}
                                    onChange={handleFileInputChange}
                                    className="hidden"
                                />

                                {/* Uploaded Files List */}
                                {uploadedFiles.length > 0 && (
                                    <div className="space-y-4">
                                        <div className="flex items-center justify-between">
                                            <h3 className="text-sm font-medium text-white">
                                                Yüklenen Dosyalar ({successfulFiles.length}/{uploadedFiles.length})
                                            </h3>
                                            <button
                                                onClick={clearAllFiles}
                                                className="text-xs text-red-400 hover:text-red-300 transition-colors"
                                            >
                                                Tümünü Temizle
                                            </button>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            {uploadedFiles.map((file) => (
                                                <div
                                                    key={file.id}
                                                    className={clsx(
                                                        'flex items-center gap-3 p-3 rounded-xl border transition-all',
                                                        file.status === 'error'
                                                            ? 'bg-red-500/10 border-red-500/30'
                                                            : 'bg-dark-800/50 border-dark-700 hover:border-dark-600'
                                                    )}
                                                >
                                                    {/* Preview / Icon */}
                                                    <div
                                                        className={clsx(
                                                            'w-14 h-14 rounded-lg flex items-center justify-center shrink-0 cursor-pointer overflow-hidden',
                                                            file.status === 'error' ? 'bg-red-500/20 text-red-400' : 'bg-dark-700 text-dark-400'
                                                        )}
                                                        onClick={() => file.preview && setPreviewFile(file)}
                                                    >
                                                        {file.preview ? (
                                                            <img
                                                                src={file.preview}
                                                                alt={file.file.name}
                                                                className="w-full h-full object-cover"
                                                            />
                                                        ) : (
                                                            getFileIcon(file.type)
                                                        )}
                                                    </div>

                                                    {/* File Info */}
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium text-white truncate">
                                                            {file.file.name}
                                                        </p>
                                                        <p className="text-xs text-dark-400">
                                                            {formatFileSize(file.file.size)}
                                                        </p>
                                                        {file.status === 'error' && (
                                                            <p className="text-xs text-red-400 flex items-center gap-1 mt-1">
                                                                <AlertCircle className="w-3 h-3" />
                                                                {file.errorMessage}
                                                            </p>
                                                        )}
                                                    </div>

                                                    {/* Status / Actions */}
                                                    <div className="flex items-center gap-2">
                                                        {file.status === 'uploading' && (
                                                            <Loader2 className="w-5 h-5 text-primary-400 animate-spin" />
                                                        )}
                                                        {file.status === 'success' && (
                                                            <Check className="w-5 h-5 text-green-400" />
                                                        )}
                                                        <button
                                                            onClick={() => removeFile(file.id)}
                                                            className="p-1.5 hover:bg-dark-700 rounded-lg transition-colors text-dark-400 hover:text-red-400"
                                                        >
                                                            <Trash2 className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            /* Camera Tab */
                            <div className="space-y-6">
                                {cameraError ? (
                                    <div className="flex flex-col items-center justify-center py-12 text-center">
                                        <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mb-4">
                                            <AlertCircle className="w-8 h-8 text-red-400" />
                                        </div>
                                        <p className="text-red-400 mb-4">{cameraError}</p>
                                        <button
                                            onClick={startCamera}
                                            className="btn-primary"
                                        >
                                            Tekrar Dene
                                        </button>
                                    </div>
                                ) : capturedImage ? (
                                    /* Captured Image Preview */
                                    <div className="space-y-4">
                                        <div className="relative aspect-video bg-black rounded-xl overflow-hidden">
                                            <img
                                                src={capturedImage}
                                                alt="Captured"
                                                className="w-full h-full object-contain"
                                            />
                                        </div>
                                        <div className="flex justify-center gap-4">
                                            <button
                                                onClick={retakePhoto}
                                                className="btn-secondary flex items-center gap-2"
                                            >
                                                <RotateCcw className="w-5 h-5" />
                                                Tekrar Çek
                                            </button>
                                            <button
                                                onClick={useCapturedPhoto}
                                                className="btn-primary flex items-center gap-2"
                                            >
                                                <Check className="w-5 h-5" />
                                                Bu Fotoğrafı Kullan
                                            </button>
                                        </div>
                                    </div>
                                ) : (
                                    /* Camera View */
                                    <div className="space-y-4">
                                        <div className="relative aspect-video bg-black rounded-xl overflow-hidden">
                                            <video
                                                ref={videoRef}
                                                autoPlay
                                                playsInline
                                                muted
                                                className="w-full h-full object-cover"
                                            />
                                            {!isCameraActive && (
                                                <div className="absolute inset-0 flex items-center justify-center bg-dark-900">
                                                    <Loader2 className="w-8 h-8 text-primary-400 animate-spin" />
                                                </div>
                                            )}

                                            {/* Camera Controls Overlay */}
                                            {isCameraActive && (
                                                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-4">
                                                    <button
                                                        onClick={switchCamera}
                                                        className="p-3 bg-dark-900/80 hover:bg-dark-800 rounded-full transition-colors"
                                                        title="Kamera Değiştir"
                                                    >
                                                        <RotateCcw className="w-5 h-5 text-white" />
                                                    </button>
                                                    <button
                                                        onClick={capturePhoto}
                                                        className="w-16 h-16 bg-white rounded-full flex items-center justify-center hover:scale-105 transition-transform shadow-lg"
                                                        title="Fotoğraf Çek"
                                                    >
                                                        <div className="w-12 h-12 bg-primary-500 rounded-full" />
                                                    </button>
                                                    <button
                                                        onClick={stopCamera}
                                                        className="p-3 bg-dark-900/80 hover:bg-red-500/80 rounded-full transition-colors"
                                                        title="Kamerayı Kapat"
                                                    >
                                                        <StopCircle className="w-5 h-5 text-white" />
                                                    </button>
                                                </div>
                                            )}
                                        </div>

                                        {/* Hidden canvas for capture */}
                                        <canvas ref={canvasRef} className="hidden" />

                                        {!isCameraActive && !cameraError && (
                                            <div className="flex justify-center">
                                                <button
                                                    onClick={startCamera}
                                                    className="btn-primary flex items-center gap-2"
                                                >
                                                    <Camera className="w-5 h-5" />
                                                    Kamerayı Başlat
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between p-6 border-t border-dark-700 bg-dark-800/50">
                        <p className="text-sm text-dark-400">
                            {successfulFiles.length} dosya seçildi
                        </p>
                        <div className="flex gap-3">
                            <button onClick={onClose} className="btn-secondary">
                                İptal
                            </button>
                            <button
                                onClick={handleConfirm}
                                disabled={successfulFiles.length === 0}
                                className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Ekle ({successfulFiles.length})
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Image Preview Modal */}
            {previewFile && previewFile.preview && (
                <div className="fixed inset-0 z-[60] flex items-center justify-center">
                    <div
                        className="absolute inset-0 bg-black/90"
                        onClick={() => setPreviewFile(null)}
                    />
                    <div className="relative max-w-[90vw] max-h-[90vh]">
                        <img
                            src={previewFile.preview}
                            alt={previewFile.file.name}
                            className="max-w-full max-h-[90vh] object-contain rounded-lg"
                        />
                        <button
                            onClick={() => setPreviewFile(null)}
                            className="absolute top-4 right-4 p-2 bg-dark-900/80 hover:bg-dark-800 rounded-full transition-colors"
                        >
                            <X className="w-6 h-6 text-white" />
                        </button>
                        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 bg-dark-900/80 px-4 py-2 rounded-full">
                            <p className="text-sm text-white">{previewFile.file.name}</p>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
