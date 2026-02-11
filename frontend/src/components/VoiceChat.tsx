import { useState, useRef, useEffect, useCallback } from 'react'
import { X, Mic, MicOff, Volume2, VolumeX, Phone } from 'lucide-react'
import clsx from 'clsx'

interface VoiceChatProps {
    isOpen: boolean
    onClose: () => void
    onSendMessage: (text: string) => Promise<string>
    userName?: string
}

type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking'

export default function VoiceChat({ isOpen, onClose, onSendMessage, userName }: VoiceChatProps) {
    const [voiceState, setVoiceState] = useState<VoiceState>('idle')
    const [transcript, setTranscript] = useState('')
    const [interimTranscript, setInterimTranscript] = useState('')
    const [responseText, setResponseText] = useState('')
    const [error, setError] = useState('')
    const [conversationLog, setConversationLog] = useState<{ role: 'user' | 'ai'; text: string }[]>([])

    const recognitionRef = useRef<any>(null)
    const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)
    const autoListenTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const silenceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    // Start listening automatically when opened
    useEffect(() => {
        if (isOpen) {
            setConversationLog([])
            setTranscript('')
            setResponseText('')
            setError('')
            // Small delay then start listening
            autoListenTimeoutRef.current = setTimeout(() => {
                startListening()
            }, 500)
        } else {
            stopEverything()
        }

        return () => {
            stopEverything()
        }
    }, [isOpen])

    const stopEverything = () => {
        if (recognitionRef.current) {
            try { recognitionRef.current.stop() } catch {}
            recognitionRef.current = null
        }
        window.speechSynthesis?.cancel()
        if (autoListenTimeoutRef.current) clearTimeout(autoListenTimeoutRef.current)
        if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current)
        setVoiceState('idle')
        setInterimTranscript('')
    }

    const startListening = useCallback(() => {
        setError('')
        setTranscript('')
        setInterimTranscript('')

        const isSecureContext = window.isSecureContext || location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1'
        if (!isSecureContext) {
            setError('Sesli sohbet için HTTPS gereklidir.')
            return
        }

        if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            setError('Tarayıcınız sesli sohbeti desteklemiyor. Chrome veya Edge kullanın.')
            return
        }

        const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition
        const recognition = new SpeechRecognition()
        recognition.lang = 'tr-TR'
        recognition.continuous = true
        recognition.interimResults = true

        let finalText = ''

        recognition.onresult = (event: any) => {
            let interim = ''
            let final = ''

            for (let i = 0; i < event.results.length; i++) {
                if (event.results[i].isFinal) {
                    final += event.results[i][0].transcript
                } else {
                    interim += event.results[i][0].transcript
                }
            }

            if (final) {
                finalText = final
                setTranscript(final)
            }
            setInterimTranscript(interim)

            // Reset silence timer on every result
            if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current)
            silenceTimeoutRef.current = setTimeout(() => {
                // User stopped speaking for 2 seconds — send the message
                if (finalText.trim()) {
                    recognition.stop()
                }
            }, 2000)
        }

        recognition.onerror = (event: any) => {
            if (event.error === 'not-allowed') {
                setError('Mikrofon erişimi reddedildi.')
            } else if (event.error === 'no-speech') {
                // Restart listening if no speech detected
                setVoiceState('idle')
                autoListenTimeoutRef.current = setTimeout(() => startListening(), 500)
                return
            } else if (event.error !== 'aborted') {
                setError(`Ses hatası: ${event.error}`)
            }
            setVoiceState('idle')
        }

        recognition.onend = () => {
            if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current)

            if (finalText.trim()) {
                // We have text, process it
                handleVoiceMessage(finalText.trim())
            } else {
                setVoiceState('idle')
            }
        }

        recognitionRef.current = recognition
        try {
            recognition.start()
            setVoiceState('listening')
        } catch {
            setError('Mikrofon başlatılamadı.')
        }
    }, [])

    const handleVoiceMessage = async (text: string) => {
        setVoiceState('processing')
        setConversationLog(prev => [...prev, { role: 'user', text }])

        try {
            const response = await onSendMessage(text)
            setResponseText(response)
            setConversationLog(prev => [...prev, { role: 'ai', text: response }])

            // Speak the response
            speakResponse(response)
        } catch {
            setError('Yanıt alınamadı. Tekrar deneyin.')
            setVoiceState('idle')
            // Auto restart listening after error
            autoListenTimeoutRef.current = setTimeout(() => startListening(), 2000)
        }
    }

    const speakResponse = (text: string) => {
        setVoiceState('speaking')
        window.speechSynthesis.cancel()

        // Clean text for speech (remove markdown, etc.)
        const cleanText = text
            .replace(/\*\*/g, '')
            .replace(/\*/g, '')
            .replace(/#{1,6}\s/g, '')
            .replace(/```[\s\S]*?```/g, '')
            .replace(/`[^`]*`/g, '')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .replace(/\n{2,}/g, '. ')
            .replace(/\n/g, '. ')
            .trim()

        const utterance = new SpeechSynthesisUtterance(cleanText)
        utterance.lang = 'tr-TR'
        utterance.rate = 1.05
        utterance.pitch = 1.0

        const voices = window.speechSynthesis.getVoices()
        const turkishVoice = voices.find(v => v.lang.startsWith('tr'))
        if (turkishVoice) utterance.voice = turkishVoice

        utterance.onend = () => {
            setVoiceState('idle')
            utteranceRef.current = null
            // Auto-restart listening after response is spoken
            autoListenTimeoutRef.current = setTimeout(() => {
                startListening()
            }, 600)
        }

        utterance.onerror = () => {
            setVoiceState('idle')
            utteranceRef.current = null
            autoListenTimeoutRef.current = setTimeout(() => startListening(), 1000)
        }

        utteranceRef.current = utterance
        window.speechSynthesis.speak(utterance)
    }

    const handleStopSpeaking = () => {
        window.speechSynthesis.cancel()
        setVoiceState('idle')
    }

    const handleToggleListening = () => {
        if (voiceState === 'listening') {
            if (recognitionRef.current) {
                try { recognitionRef.current.stop() } catch {}
            }
            setVoiceState('idle')
        } else if (voiceState === 'idle') {
            startListening()
        } else if (voiceState === 'speaking') {
            handleStopSpeaking()
        }
    }

    const handleClose = () => {
        stopEverything()
        onClose()
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-[100] flex flex-col bg-gradient-to-b from-dark-950 via-dark-900 to-dark-950">
            {/* Header */}
            <div className="flex items-center justify-between px-4 sm:px-6 py-4">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
                        <Volume2 className="w-4 h-4 text-white" />
                    </div>
                    <div>
                        <h3 className="text-white text-sm font-medium">Sesli Sohbet</h3>
                        <p className="text-dark-500 text-xs">Company.AI Asistan</p>
                    </div>
                </div>
                <button
                    onClick={handleClose}
                    className="p-2 rounded-full hover:bg-dark-800 text-dark-400 hover:text-white transition-colors"
                >
                    <X className="w-5 h-5" />
                </button>
            </div>

            {/* Conversation Log */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 space-y-4">
                {conversationLog.length === 0 && voiceState === 'idle' && (
                    <div className="h-full flex items-center justify-center">
                        <p className="text-dark-500 text-sm text-center">
                            Mikrofon butonuna basarak sohbete başlayın
                        </p>
                    </div>
                )}

                {conversationLog.map((msg, i) => (
                    <div key={i} className={clsx(
                        'max-w-[85%] rounded-2xl px-4 py-3',
                        msg.role === 'user'
                            ? 'ml-auto bg-primary-600/20 text-primary-100 border border-primary-500/20'
                            : 'mr-auto bg-dark-800/60 text-dark-200 border border-dark-700/30'
                    )}>
                        <p className="text-xs font-medium mb-1 opacity-60">
                            {msg.role === 'user' ? (userName || 'Siz') : 'AI Asistan'}
                        </p>
                        <p className="text-sm leading-relaxed">{msg.text}</p>
                    </div>
                ))}

                {/* Current state display */}
                {voiceState === 'listening' && (
                    <div className="text-center py-4">
                        <p className="text-primary-400 text-sm animate-pulse">
                            {interimTranscript || transcript || 'Dinliyorum...'}
                        </p>
                    </div>
                )}

                {voiceState === 'processing' && (
                    <div className="text-center py-4">
                        <div className="flex items-center justify-center gap-1.5">
                            <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                        <p className="text-dark-500 text-xs mt-2">Düşünüyorum...</p>
                    </div>
                )}

                {voiceState === 'speaking' && (
                    <div className="text-center py-2">
                        <p className="text-violet-400 text-xs animate-pulse">Konuşuyorum...</p>
                    </div>
                )}
            </div>

            {/* Error */}
            {error && (
                <div className="mx-4 sm:mx-6 mb-4 px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs text-center">
                    {error}
                </div>
            )}

            {/* Bottom Controls */}
            <div className="flex flex-col items-center gap-4 px-4 sm:px-6 pb-8 pt-4">
                {/* Voice State Visualizer */}
                <div className="relative flex items-center justify-center">
                    {/* Pulse rings for listening state */}
                    {voiceState === 'listening' && (
                        <>
                            <div className="absolute w-28 h-28 rounded-full bg-primary-500/10 animate-ping" style={{ animationDuration: '2s' }} />
                            <div className="absolute w-24 h-24 rounded-full bg-primary-500/15 animate-ping" style={{ animationDuration: '1.5s' }} />
                            <div className="absolute w-20 h-20 rounded-full bg-primary-500/20 animate-pulse" />
                        </>
                    )}

                    {/* Pulse rings for speaking state */}
                    {voiceState === 'speaking' && (
                        <>
                            <div className="absolute w-28 h-28 rounded-full bg-violet-500/10 animate-ping" style={{ animationDuration: '2s' }} />
                            <div className="absolute w-24 h-24 rounded-full bg-violet-500/15 animate-ping" style={{ animationDuration: '1.5s' }} />
                            <div className="absolute w-20 h-20 rounded-full bg-violet-500/20 animate-pulse" />
                        </>
                    )}

                    {/* Loading ring for processing */}
                    {voiceState === 'processing' && (
                        <div className="absolute w-20 h-20 rounded-full border-2 border-primary-500/30 border-t-primary-500 animate-spin" />
                    )}

                    {/* Main button */}
                    <button
                        onClick={handleToggleListening}
                        disabled={voiceState === 'processing'}
                        className={clsx(
                            'relative z-10 w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl',
                            voiceState === 'listening' && 'bg-primary-500 text-white scale-110 shadow-primary-500/40',
                            voiceState === 'speaking' && 'bg-violet-600 text-white shadow-violet-500/40',
                            voiceState === 'processing' && 'bg-dark-700 text-dark-400 cursor-wait',
                            voiceState === 'idle' && 'bg-dark-700 hover:bg-dark-600 text-white hover:scale-105'
                        )}
                    >
                        {voiceState === 'listening' && <Mic className="w-7 h-7" />}
                        {voiceState === 'speaking' && <Volume2 className="w-7 h-7" />}
                        {voiceState === 'processing' && <Mic className="w-7 h-7 opacity-50" />}
                        {voiceState === 'idle' && <Mic className="w-7 h-7" />}
                    </button>
                </div>

                {/* State label */}
                <p className={clsx(
                    'text-xs font-medium',
                    voiceState === 'listening' && 'text-primary-400',
                    voiceState === 'speaking' && 'text-violet-400',
                    voiceState === 'processing' && 'text-dark-500',
                    voiceState === 'idle' && 'text-dark-500'
                )}>
                    {voiceState === 'listening' && 'Dinliyorum — Konuşun'}
                    {voiceState === 'speaking' && 'Yanıtlıyorum — Durdurmak için dokunun'}
                    {voiceState === 'processing' && 'İşleniyor...'}
                    {voiceState === 'idle' && 'Mikrofona dokunun'}
                </p>

                {/* End call button */}
                <button
                    onClick={handleClose}
                    className="w-12 h-12 rounded-full bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors shadow-lg shadow-red-500/30"
                    title="Sesli sohbeti kapat"
                >
                    <Phone className="w-5 h-5 rotate-[135deg]" />
                </button>
            </div>
        </div>
    )
}
