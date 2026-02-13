import { useState, useCallback } from 'react'
import { Copy, Check, Code2 } from 'lucide-react'

interface MessageContentProps {
    content: string
    role: 'user' | 'assistant'
}

interface ContentPart {
    type: 'text' | 'code'
    content: string
    language?: string
}

/** Mesaj içeriğini code block ve metin parçalarına ayır */
function parseContent(raw: string): ContentPart[] {
    const parts: ContentPart[] = []
    // Satır satır tarayarak ``` açılış/kapanışını bul
    const lines = raw.split('\n')
    let inCodeBlock = false
    let codeLang = ''
    let codeLines: string[] = []
    let textLines: string[] = []

    for (const line of lines) {
        const trimmed = line.trimEnd()

        if (!inCodeBlock) {
            // Kod bloğu açılışı: ```python, ```js, ``` vb.
            const openMatch = trimmed.match(/^```(\w*)$/)
            if (openMatch) {
                // Önceki metin bölümünü kaydet
                if (textLines.length > 0) {
                    const text = textLines.join('\n')
                    if (text.trim()) parts.push({ type: 'text', content: text })
                    textLines = []
                }
                inCodeBlock = true
                codeLang = openMatch[1] || 'code'
                codeLines = []
            } else {
                textLines.push(line)
            }
        } else {
            // Kod bloğu kapanışı
            if (trimmed === '```') {
                parts.push({
                    type: 'code',
                    language: codeLang,
                    content: codeLines.join('\n').replace(/\n$/, ''),
                })
                inCodeBlock = false
                codeLang = ''
                codeLines = []
            } else {
                codeLines.push(line)
            }
        }
    }

    // Kapanmamış kod bloğu varsa — yine de code olarak ekle
    if (inCodeBlock && codeLines.length > 0) {
        parts.push({
            type: 'code',
            language: codeLang,
            content: codeLines.join('\n').replace(/\n$/, ''),
        })
    }

    // Kalan metin
    if (textLines.length > 0) {
        const text = textLines.join('\n')
        if (text.trim()) parts.push({ type: 'text', content: text })
    }

    // Hiç part yoksa tamamını text olarak döndür
    if (parts.length === 0) {
        parts.push({ type: 'text', content: raw })
    }

    return parts
}

/** Basit inline markdown: **bold**, *italic*, `inline code` */
function renderInlineMarkdown(text: string): (string | JSX.Element)[] {
    const elements: (string | JSX.Element)[] = []
    // Split satır satır, markdown heading ve bold/italic/inline code dönüştür
    const lines = text.split('\n')

    lines.forEach((line, lineIdx) => {
        // Heading
        if (/^### (.+)/.test(line)) {
            elements.push(
                <h3 key={`h3-${lineIdx}`} className="text-base font-bold text-white mt-3 mb-1">
                    {line.replace(/^### /, '')}
                </h3>
            )
            return
        }
        if (/^## (.+)/.test(line)) {
            elements.push(
                <h2 key={`h2-${lineIdx}`} className="text-lg font-bold text-white mt-4 mb-1">
                    {line.replace(/^## /, '')}
                </h2>
            )
            return
        }
        if (/^# (.+)/.test(line)) {
            elements.push(
                <h1 key={`h1-${lineIdx}`} className="text-xl font-bold text-white mt-4 mb-2">
                    {line.replace(/^# /, '')}
                </h1>
            )
            return
        }

        // Satır içeriğini inline markdown olarak parse et
        const parts = line.split(/(\*\*.*?\*\*|\*.*?\*|`[^`]+`)/g)
        const lineElements = parts.map((part, partIdx) => {
            if (/^\*\*(.*)\*\*$/.test(part)) {
                return (
                    <strong key={`b-${lineIdx}-${partIdx}`} className="text-white font-semibold">
                        {part.slice(2, -2)}
                    </strong>
                )
            }
            if (/^\*(.*)\*$/.test(part) && !part.startsWith('**')) {
                return <em key={`i-${lineIdx}-${partIdx}`}>{part.slice(1, -1)}</em>
            }
            if (/^`([^`]+)`$/.test(part)) {
                return (
                    <code
                        key={`ic-${lineIdx}-${partIdx}`}
                        className="bg-dark-700/80 text-primary-300 px-1.5 py-0.5 rounded text-[13px] font-mono"
                    >
                        {part.slice(1, -1)}
                    </code>
                )
            }
            return part
        })

        if (lineIdx > 0) elements.push(<br key={`br-${lineIdx}`} />)
        elements.push(...lineElements)
    })

    return elements
}

/** Kod bloğu bileşeni — kopyalama butonu ile */
function CodeBlock({ code, language }: { code: string; language: string }) {
    const [copied, setCopied] = useState(false)

    const handleCopy = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(code)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        } catch {
            // Fallback: eski yöntem
            const textarea = document.createElement('textarea')
            textarea.value = code
            textarea.style.position = 'fixed'
            textarea.style.opacity = '0'
            document.body.appendChild(textarea)
            textarea.select()
            document.execCommand('copy')
            document.body.removeChild(textarea)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }, [code])

    return (
        <div className="relative group my-3 rounded-xl overflow-hidden border border-dark-600/50">
            {/* Üst bar — dil etiketi + kopyala butonu */}
            <div className="flex items-center justify-between px-4 py-2 bg-dark-900/80 border-b border-dark-600/50">
                <div className="flex items-center gap-2 text-xs text-dark-400">
                    <Code2 className="w-3.5 h-3.5" />
                    <span>{language}</span>
                </div>
                <button
                    onClick={handleCopy}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-all duration-200 ${
                        copied
                            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                            : 'bg-dark-700/50 text-dark-300 hover:text-white hover:bg-dark-600/80 border border-dark-600/30'
                    }`}
                    title="Kodu kopyala"
                >
                    {copied ? (
                        <>
                            <Check className="w-3.5 h-3.5" />
                            <span>Kopyalandı!</span>
                        </>
                    ) : (
                        <>
                            <Copy className="w-3.5 h-3.5" />
                            <span>Kopyala</span>
                        </>
                    )}
                </button>
            </div>

            {/* Kod alanı */}
            <pre className="overflow-x-auto p-4 bg-[#0d1117] text-[13px] leading-relaxed">
                <code className="text-dark-200 font-mono whitespace-pre">{code}</code>
            </pre>
        </div>
    )
}

/** Ana bileşen — mesaj içeriğini kod blokları + metin olarak render eder */
export default function MessageContent({ content, role }: MessageContentProps) {
    // User mesajlarını basit göster
    if (role === 'user') {
        return <div className="whitespace-pre-wrap">{content}</div>
    }

    const parts = parseContent(content)

    return (
        <div className="message-content">
            {parts.map((part, idx) => {
                if (part.type === 'code') {
                    return (
                        <CodeBlock
                            key={`code-${idx}`}
                            code={part.content}
                            language={part.language || 'code'}
                        />
                    )
                }
                return (
                    <div key={`text-${idx}`} className="whitespace-pre-wrap">
                        {renderInlineMarkdown(part.content)}
                    </div>
                )
            })}
        </div>
    )
}
