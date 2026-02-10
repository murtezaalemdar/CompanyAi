import { Cloud, Droplets, Wind, Thermometer, MapPin, Calendar } from 'lucide-react'

interface ForecastDay {
    day: string
    high: string
    low: string
    condition: string
    icon: string
}

interface WeatherData {
    type: 'weather'
    location: string
    temperature: string
    unit: string
    condition: string
    condition_icon: string
    precipitation: string
    humidity: string
    wind: string
    date: string
    forecast: ForecastDay[]
    source: string
}

// Hava durumu ikonları — condition_icon emoji'ye göre büyük SVG-benzeri ikon
const WEATHER_BG: Record<string, string> = {
    '☀️': 'from-amber-400 to-orange-500',
    '⛅': 'from-blue-400 to-slate-500',
    '☁️': 'from-slate-400 to-slate-600',
    '🌧️': 'from-blue-500 to-slate-700',
    '🌦️': 'from-blue-400 to-slate-600',
    '⛈️': 'from-slate-600 to-slate-800',
    '🌨️': 'from-blue-200 to-slate-400',
    '❄️': 'from-blue-100 to-blue-300',
    '🌫️': 'from-gray-300 to-gray-500',
    '💨': 'from-teal-400 to-slate-500',
    '🌡️': 'from-blue-400 to-indigo-600',
}

function getGradient(icon: string): string {
    return WEATHER_BG[icon] || 'from-blue-400 to-indigo-600'
}

export default function WeatherCard({ data }: { data: WeatherData }) {
    const gradient = getGradient(data.condition_icon)

    return (
        <div className="w-full max-w-lg my-3 rounded-2xl overflow-hidden shadow-xl">
            {/* Üst kısım — Ana hava durumu */}
            <div className={`bg-gradient-to-br ${gradient} p-5 text-white`}>
                <div className="flex items-center gap-1.5 text-white/80 text-sm mb-3">
                    <MapPin className="w-3.5 h-3.5" />
                    <span className="font-medium">{data.location}</span>
                    {data.date && (
                        <>
                            <span className="mx-1">•</span>
                            <Calendar className="w-3.5 h-3.5" />
                            <span>{data.date}</span>
                        </>
                    )}
                </div>

                <div className="flex items-center justify-between">
                    <div className="flex items-end gap-3">
                        <span className="text-7xl font-extralight leading-none">
                            {data.temperature}°
                        </span>
                        <div className="mb-2">
                            <span className="text-4xl">{data.condition_icon}</span>
                            <p className="text-sm text-white/90 mt-1">{data.condition}</p>
                        </div>
                    </div>
                </div>

                {/* Alt bilgiler — nem, yağış, rüzgar */}
                <div className="flex gap-5 mt-4 text-sm text-white/85">
                    {data.humidity && (
                        <div className="flex items-center gap-1.5">
                            <Droplets className="w-4 h-4" />
                            <span>Nem: {data.humidity}</span>
                        </div>
                    )}
                    {data.precipitation && (
                        <div className="flex items-center gap-1.5">
                            <Cloud className="w-4 h-4" />
                            <span>Yağış: {data.precipitation}</span>
                        </div>
                    )}
                    {data.wind && (
                        <div className="flex items-center gap-1.5">
                            <Wind className="w-4 h-4" />
                            <span>Rüzgar: {data.wind}</span>
                        </div>
                    )}
                </div>
            </div>

            {/* Alt kısım — Haftalık tahmin */}
            {data.forecast && data.forecast.length > 0 && (
                <div className="bg-dark-800/90 backdrop-blur-sm px-4 py-3">
                    <div className="flex justify-between overflow-x-auto gap-1">
                        {data.forecast.map((day, i) => (
                            <div
                                key={i}
                                className="flex flex-col items-center min-w-[52px] py-2 px-1 rounded-lg hover:bg-white/5 transition-colors"
                            >
                                <span className="text-xs text-dark-400 font-medium">
                                    {day.day}
                                </span>
                                <span className="text-xl my-1">{day.icon}</span>
                                <div className="text-xs">
                                    <span className="text-white font-medium">{day.high}°</span>
                                    <span className="text-dark-500 ml-0.5">{day.low}°</span>
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="text-right mt-1">
                        <span className="text-[10px] text-dark-600">
                            {data.source}
                        </span>
                    </div>
                </div>
            )}
        </div>
    )
}
