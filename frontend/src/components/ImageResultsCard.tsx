import { useState } from 'react'
import { X, ExternalLink, Search, ChevronLeft, ChevronRight, Download, FolderDown, Check } from 'lucide-react'
import JSZip from 'jszip'

interface ImageItem {
    src: string
    thumbnail: string
    title: string
    source: string
    link: string
}

interface ImageResultsData {
    type: 'images'
    query: string
    images: ImageItem[]
    source: string
}

export default function ImageResultsCard({ data }: { data: ImageResultsData }) {
    const [lightbox, setLightbox] = useState<number | null>(null)
    const [imgErrors, setImgErrors] = useState<Set<number>>(new Set())
    const [downloading, setDownloading] = useState<number | null>(null)
    const [zipProgress, setZipProgress] = useState<'idle' | 'downloading' | 'zipping' | 'done'>('idle')
    const [zipCount, setZipCount] = useState({ done: 0, total: 0 })

    const downloadAllAsZip = async () => {
        const valid = data.images.filter((_, i) => !imgErrors.has(i))
        if (valid.length === 0) return

        setZipProgress('downloading')
        setZipCount({ done: 0, total: valid.length })

        const zip = new JSZip()
        const folder = zip.folder(data.query.replace(/[^a-zA-Z0-9\u00C0-\u024F\s_-]/g, '').replace(/\s+/g, '_') || 'gorseller')!
        let completed = 0

        await Promise.allSettled(
            valid.map(async (img, i) => {
                try {
                    const url = img.src || img.thumbnail
                    const res = await fetch(url)
                    const blob = await res.blob()
                    const safeName = (img.title || `gorsel_${i + 1}`)
                        .replace(/[^a-zA-Z0-9\u00C0-\u024F\s_-]/g, '')
                        .replace(/\s+/g, '_')
                        .substring(0, 50)
                    const ext = blob.type?.includes('png') ? '.png' : blob.type?.includes('webp') ? '.webp' : '.jpg'
                    folder.file(`${String(i + 1).padStart(2, '0')}_${safeName}${ext}`, blob)
                } catch {
                    // CORS — atla
                } finally {
                    completed++
                    setZipCount({ done: completed, total: valid.length })
                }
            })
        )

        setZipProgress('zipping')
        const content = await zip.generateAsync({ type: 'blob' })
        const a = document.createElement('a')
        a.href = URL.createObjectURL(content)
        a.download = `${data.query.replace(/[^a-zA-Z0-9\u00C0-\u024F\s_-]/g, '').replace(/\s+/g, '_') || 'gorseller'}.zip`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(a.href)

        setZipProgress('done')
        setTimeout(() => setZipProgress('idle'), 3000)
    }

    const downloadImage = async (img: ImageItem, index: number, e?: React.MouseEvent) => {
        if (e) e.stopPropagation()
        setDownloading(index)
        try {
            const url = img.src || img.thumbnail
            const response = await fetch(url)
            const blob = await response.blob()
            const safeName = (img.title || `gorsel_${index + 1}`)
                .replace(/[^a-zA-Z0-9\u00C0-\u024F\s_-]/g, '')
                .replace(/\s+/g, '_')
                .substring(0, 60)
            const ext = blob.type?.includes('png') ? '.png' : blob.type?.includes('webp') ? '.webp' : '.jpg'
            const a = document.createElement('a')
            a.href = URL.createObjectURL(blob)
            a.download = `${safeName}${ext}`
            document.body.appendChild(a)
            a.click()
            document.body.removeChild(a)
            URL.revokeObjectURL(a.href)
        } catch {
            // CORS engeli — yeni sekmede aç
            window.open(img.src || img.thumbnail, '_blank')
        } finally {
            setTimeout(() => setDownloading(null), 1000)
        }
    }

    const handleImgError = (index: number) => {
        setImgErrors((prev) => new Set(prev).add(index))
    }

    const visibleImages = data.images.filter((_, i) => !imgErrors.has(i))

    const openLightbox = (globalIndex: number) => {
        setLightbox(globalIndex)
    }

    const navigateLightbox = (dir: number) => {
        if (lightbox === null) return
        const validIndices = data.images.map((_, i) => i).filter((i) => !imgErrors.has(i))
        const currentPos = validIndices.indexOf(lightbox)
        const newPos = (currentPos + dir + validIndices.length) % validIndices.length
        setLightbox(validIndices[newPos])
    }

    if (visibleImages.length === 0) return null

    return (
        <>
            <div className="w-full max-w-2xl my-3">
                {/* Başlık */}
                <div className="flex items-center gap-2 mb-2 text-sm text-dark-400">
                    <Search className="w-3.5 h-3.5" />
                    <span>Görseller — <span className="text-dark-300">{data.query}</span></span>
                    <div className="ml-auto flex items-center gap-2">
                        <button
                            onClick={downloadAllAsZip}
                            disabled={zipProgress !== 'idle'}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all
                                bg-dark-700/60 hover:bg-dark-600 text-dark-300 hover:text-white border border-dark-600/50 hover:border-dark-500
                                disabled:opacity-60 disabled:cursor-wait"
                            title="Tüm görselleri ZIP olarak indir"
                        >
                            {zipProgress === 'idle' && (
                                <><FolderDown className="w-3.5 h-3.5" /> Tümünü İndir ({visibleImages.length})  </>
                            )}
                            {zipProgress === 'downloading' && (
                                <><div className="w-3.5 h-3.5 border-2 border-dark-400 border-t-blue-400 rounded-full animate-spin" /> {zipCount.done}/{zipCount.total} indiriliyor</>
                            )}
                            {zipProgress === 'zipping' && (
                                <><div className="w-3.5 h-3.5 border-2 border-dark-400 border-t-emerald-400 rounded-full animate-spin" /> ZIP hazırlanıyor…</>
                            )}
                            {zipProgress === 'done' && (
                                <><Check className="w-3.5 h-3.5 text-emerald-400" /> <span className="text-emerald-400">İndirildi</span></>
                            )}
                        </button>
                        <span className="text-dark-600 text-xs">{data.source}</span>
                    </div>
                </div>

                {/* Görsel Grid */}
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-1.5 rounded-xl overflow-hidden">
                    {data.images.map((img, i) => {
                        if (imgErrors.has(i)) return null
                        return (
                            <div
                                key={i}
                                className="relative group cursor-pointer aspect-square bg-dark-800 overflow-hidden rounded-lg"
                                onClick={() => openLightbox(i)}
                            >
                                <img
                                    src={img.thumbnail || img.src}
                                    alt={img.title}
                                    loading="lazy"
                                    className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-110"
                                    onError={() => handleImgError(i)}
                                />
                                {/* Hover overlay */}
                                <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                                    {/* İndir butonu */}
                                    <button
                                        className="absolute top-1.5 right-1.5 p-1.5 rounded-full bg-black/60 hover:bg-black/80 text-white/80 hover:text-white transition-colors z-10"
                                        onClick={(e) => downloadImage(img, i, e)}
                                        title="Görseli indir"
                                    >
                                        {downloading === i ? (
                                            <div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                                        ) : (
                                            <Download className="w-3.5 h-3.5" />
                                        )}
                                    </button>
                                    <div className="absolute bottom-0 left-0 right-0 p-2">
                                        <p className="text-white text-[10px] leading-tight line-clamp-2 font-medium">
                                            {img.title}
                                        </p>
                                        {img.source && (
                                            <p className="text-white/60 text-[9px] mt-0.5 truncate">
                                                {img.source}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )
                    })}
                </div>
            </div>

            {/* Lightbox Modal */}
            {lightbox !== null && data.images[lightbox] && (
                <div
                    className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
                    onClick={() => setLightbox(null)}
                >
                    {/* Üst butonlar */}
                    <div className="absolute top-4 right-4 flex items-center gap-2 z-10">
                        {/* İndir */}
                        <button
                            className="text-white/70 hover:text-white p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                            onClick={(e) => {
                                e.stopPropagation()
                                if (lightbox !== null && data.images[lightbox]) {
                                    downloadImage(data.images[lightbox], lightbox)
                                }
                            }}
                            title="Görseli indir"
                        >
                            {downloading === lightbox ? (
                                <div className="w-5 h-5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                            ) : (
                                <Download className="w-5 h-5" />
                            )}
                        </button>
                        {/* Kapat */}
                        <button
                            className="text-white/70 hover:text-white p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
                            onClick={() => setLightbox(null)}
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Sol ok */}
                    <button
                        className="absolute left-4 text-white/70 hover:text-white p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors z-10"
                        onClick={(e) => {
                            e.stopPropagation()
                            navigateLightbox(-1)
                        }}
                    >
                        <ChevronLeft className="w-6 h-6" />
                    </button>

                    {/* Görsel */}
                    <div
                        className="max-w-[85vw] max-h-[85vh] flex flex-col items-center"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <img
                            src={data.images[lightbox].src || data.images[lightbox].thumbnail}
                            alt={data.images[lightbox].title}
                            className="max-w-full max-h-[75vh] object-contain rounded-lg shadow-2xl"
                        />
                        <div className="mt-3 text-center px-4">
                            <p className="text-white text-sm font-medium">
                                {data.images[lightbox].title}
                            </p>
                            {data.images[lightbox].link && (
                                <a
                                    href={data.images[lightbox].link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs mt-1 transition-colors"
                                >
                                    <ExternalLink className="w-3 h-3" />
                                    {data.images[lightbox].source || 'Kaynağa git'}
                                </a>
                            )}
                        </div>
                    </div>

                    {/* Sağ ok */}
                    <button
                        className="absolute right-4 text-white/70 hover:text-white p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors z-10"
                        onClick={(e) => {
                            e.stopPropagation()
                            navigateLightbox(1)
                        }}
                    >
                        <ChevronRight className="w-6 h-6" />
                    </button>
                </div>
            )}
        </>
    )
}
