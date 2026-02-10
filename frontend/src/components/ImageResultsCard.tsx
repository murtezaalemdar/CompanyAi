import { useState } from 'react'
import { X, ExternalLink, Search, ChevronLeft, ChevronRight } from 'lucide-react'

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
                    <span className="text-dark-600 ml-auto text-xs">{data.source}</span>
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
                    {/* Kapat */}
                    <button
                        className="absolute top-4 right-4 text-white/70 hover:text-white p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors z-10"
                        onClick={() => setLightbox(null)}
                    >
                        <X className="w-5 h-5" />
                    </button>

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
