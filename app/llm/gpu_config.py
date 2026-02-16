"""
CompanyAI — GPU Otomatik Algılama ve Konfigürasyon
=====================================================
Ekran kartı (GPU) donanım değişikliklerini otomatik algılar
ve Ollama LLM parametrelerini buna göre ayarlar.

DESTEKLENEN SENARYOLAR:
  ┌──────────────────────────────────────────────────────────────────┐
  │ Senaryo              │ Algılama     │ Otomatik Ayar              │
  ├──────────────────────┼──────────────┼────────────────────────────┤
  │ GPU yok (CPU)        │ ✅ nvidia-smi│ timeout=900s, num_gpu=0    │
  │ Tek GPU (sığar)      │ ✅ nvidia-smi│ timeout=120s, num_gpu=99   │
  │ Tek GPU (sığmaz)     │ ✅ nvidia-smi│ kısmi offload, num_gpu=N   │
  │ Multi-GPU (sığar)    │ ✅ nvidia-smi│ timeout=60s, num_gpu=99    │
  │ Multi-GPU (sığmaz)   │ ✅ nvidia-smi│ kısmi offload, num_gpu=N   │
  │ GPU değiştirildi     │ ✅ Startup   │ Tüm parametreler yeniden   │
  │ GPU eklendi          │ ✅ Startup   │ Ollama env + params güncelle│
  │ GPU çıkarıldı        │ ✅ Startup   │ CPU moduna düşer           │
  └──────────────────────┴──────────────┴────────────────────────────┘

  Ollama /etc/default/ollama CUDA_VISIBLE_DEVICES değeri
  otomatik güncellenir; Ollama gerekirse yeniden başlatılır.

KULLANIM:
  # Startup'ta otomatik çalışır (main.py lifespan)
  from app.llm.gpu_config import gpu_config
  await gpu_config.probe()    # GPU algıla + parametreleri ayarla
  opts = gpu_config.options   # Ollama API options dict'i
"""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger()

# Ollama environment dosya yolu (systemd service tarafından okunur)
OLLAMA_ENV_PATH = Path("/etc/default/ollama")


@dataclass
class GPUInfo:
    """Tek bir GPU kartının bilgileri."""
    index: int
    name: str
    vram_total_mb: int
    vram_free_mb: int
    vram_used_mb: int
    utilization_percent: int = 0
    temperature_c: int = 0
    compute_capability: str = ""

    @property
    def vram_total_gb(self) -> float:
        return round(self.vram_total_mb / 1024, 1)

    @property
    def vram_free_gb(self) -> float:
        return round(self.vram_free_mb / 1024, 1)


@dataclass
class GPUConfig:
    """
    GPU Otomatik Konfigürasyon Yöneticisi.
    
    Startup'ta `probe()` çağrıldığında:
    1. nvidia-smi ile tüm GPU'ları algılar
    2. VRAM toplamına göre optimal num_gpu, num_ctx, batch belirler
    3. Timeout'u GPU/CPU durumuna göre ayarlar
    4. Her istek `options` property'sinden güncel parametreleri alır
    """
    gpus: list = field(default_factory=list)
    _probed: bool = False

    # ── Hesaplanan Parametreler ──
    num_gpu: int = 0           # Ollama'ya gönderilecek GPU layer sayısı (0=CPU, 99=tümü)
    num_ctx: int = 8192        # Context window
    num_batch: int = 512       # Batch size
    num_thread: int = 8        # CPU thread (GPU varken düşürülebilir)
    timeout: float = 900.0     # HTTP timeout (saniye)
    total_vram_gb: float = 0.0 # Toplam VRAM

    async def probe(self) -> "GPUConfig":
        """
        GPU donanımını algıla ve parametreleri otomatik ayarla.
        Startup'ta bir kez çağrılır. Sonucu cache'ler.
        """
        self.gpus = []
        self.total_vram_gb = 0.0

        # ── 1. nvidia-smi ile algıla ──
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 7:
                        gpu = GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            vram_total_mb=int(parts[2]),
                            vram_used_mb=int(parts[3]),
                            vram_free_mb=int(parts[4]),
                            utilization_percent=int(parts[5]),
                            temperature_c=int(parts[6]),
                        )
                        self.gpus.append(gpu)
                        self.total_vram_gb += gpu.vram_total_gb
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, Exception) as e:
            logger.info("gpu_probe_nvidia_smi_failed", error=str(e))

        # ── 2. Ollama /api/ps ile cross-check ──
        if not self.gpus:
            try:
                import httpx
                from app.config import settings
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/ps")
                    if resp.status_code == 200:
                        data = resp.json()
                        for m in data.get("models", []):
                            vram_bytes = m.get("size_vram", 0)
                            if vram_bytes > 0:
                                proc = m.get("details", {}).get("processor", "")
                                if "GPU" in proc.upper():
                                    self.total_vram_gb = round(vram_bytes / (1024**3), 1)
                                    logger.info("gpu_detected_via_ollama",
                                                vram_gb=self.total_vram_gb, processor=proc)
            except Exception:
                pass

        # ── 3. Parametreleri hesapla ──
        self._configure()
        self._probed = True

        # ── 4. Ollama GPU erişimini senkronize et ──
        ollama_restarted = self._sync_ollama_env()

        # ── 5. Loglama ──
        if self.gpus:
            for g in self.gpus:
                logger.info(
                    "gpu_detected",
                    index=g.index,
                    name=g.name,
                    vram_total_gb=g.vram_total_gb,
                    vram_free_gb=g.vram_free_gb,
                    temperature=g.temperature_c,
                )
            logger.info(
                "gpu_config_applied",
                gpu_count=len(self.gpus),
                total_vram_gb=self.total_vram_gb,
                num_gpu=self.num_gpu,
                num_ctx=self.num_ctx,
                num_batch=self.num_batch,
                timeout=self.timeout,
            )
        else:
            logger.info(
                "gpu_not_found",
                mode="CPU-only",
                num_thread=self.num_thread,
                timeout=self.timeout,
            )

        return self

    def _estimate_model_size_gb(self) -> float:
        """Model adından tahmini model boyutunu (GB) hesapla."""
        from app.config import settings
        model_name = getattr(settings, "LLM_MODEL", "").lower()

        # Model adından parametre sayısını çıkar (ör: "72b", "70b", "32b", "14b")
        match = re.search(r'(\d+)b', model_name)
        if not match:
            return 0.0

        params_b = int(match.group(1))

        # Quantization seviyesine göre tahmini boyut (GB)
        # Q3_K_M ≈ params * 0.5, Q4_K_M ≈ params * 0.6, Q5 ≈ params * 0.7, F16 ≈ params * 2
        if "q3" in model_name or "q2" in model_name:
            return params_b * 0.5
        elif "q4" in model_name:
            return params_b * 0.6
        elif "q5" in model_name or "q6" in model_name:
            return params_b * 0.7
        elif "q8" in model_name:
            return params_b * 1.0
        else:
            # Varsayılan Q4_K_M
            return params_b * 0.6

    def _configure(self):
        """GPU durumuna göre optimal parametreleri hesapla."""
        from app.config import settings

        gpu_count = len(self.gpus)
        physical_cores = os.cpu_count() // 2 if os.cpu_count() else 8

        if gpu_count == 0 and self.total_vram_gb == 0:
            # ── CPU-Only Modu ──
            self.num_gpu = 0
            self.num_ctx = 8192
            self.num_batch = 512
            self.num_thread = physical_cores
            self.timeout = 900.0  # CPU inference yavaş → 15 dk

        elif gpu_count == 1 or (gpu_count == 0 and self.total_vram_gb > 0):
            # ── Tek GPU Modu ──
            vram = self.total_vram_gb if self.total_vram_gb > 0 else (
                self.gpus[0].vram_total_gb if self.gpus else 0
            )

            # ── Model boyutu vs VRAM kontrolü ──
            # Model tamamen GPU'ya sığmıyorsa → kısmi offload (partial offload)
            # GPU bellek çakışmasını (embedding model + LLM) önlemek için
            # VRAM'in %75'i model için kullanılabilir (geri kalan KV cache + embedding)
            estimated_size = self._estimate_model_size_gb()
            usable_vram = vram * 0.75  # %25 KV cache, embedding, overhead için

            if estimated_size > 0 and estimated_size > usable_vram:
                # Model tamamen sığmıyor → Kısmi GPU Offload
                # Modelin parametre sayısından tahmini katman sayısı hesapla
                _match = re.search(r'(\d+)b', getattr(settings, "LLM_MODEL", "").lower())
                _params_b = int(_match.group(1)) if _match else 0
                # Transformer mimarileri: ~1.1x parametre sayısı kadar katman
                _estimated_layers = max(32, int(_params_b * 1.1))

                if usable_vram >= 4:
                    # En az 4GB VRAM varsa kısmi offload yap
                    _layer_ratio = min(0.95, usable_vram / estimated_size)
                    _partial_layers = max(1, int(_estimated_layers * _layer_ratio))

                    logger.info(
                        "gpu_partial_offload",
                        model_size_gb=estimated_size,
                        vram_gb=vram,
                        usable_vram_gb=usable_vram,
                        total_layers_est=_estimated_layers,
                        offload_layers=_partial_layers,
                        offload_ratio=f"{_layer_ratio:.1%}",
                    )
                    self.num_gpu = _partial_layers
                    self.num_ctx = 4096
                    self.num_batch = 256
                    self.num_thread = max(4, physical_cores // 2)
                    self.timeout = 900.0  # 15 dk timeout
                else:
                    # VRAM çok az (<4GB) → CPU-only
                    logger.info(
                        "gpu_insufficient_for_model",
                        model_size_gb=estimated_size,
                        vram_gb=vram,
                        decision="CPU-only (VRAM < 4GB)",
                    )
                    self.num_gpu = 0
                    self.num_ctx = 8192
                    self.num_batch = 512
                    self.num_thread = physical_cores
                    self.timeout = 900.0
                return

            self.num_gpu = 99  # Tüm katmanları GPU'ya yükle
            self.num_thread = max(4, physical_cores // 2)  # GPU varken CPU thread azalt

            if vram >= 24:
                # 24GB+ (RTX 4090, A5000, vb.)
                self.num_ctx = 16384
                self.num_batch = 1024
                self.timeout = 900.0
            elif vram >= 12:
                # 12-24GB (RTX 3060 12GB, RTX 4070, vb.)
                self.num_ctx = 8192
                self.num_batch = 512
                self.timeout = 900.0
            elif vram >= 8:
                # 8-12GB (RTX 3060 8GB, RTX 4060, vb.)
                self.num_ctx = 4096
                self.num_batch = 256
                self.timeout = 900.0
            else:
                # <8GB (GTX 1660, RTX 3050, vb.)
                self.num_ctx = 2048
                self.num_batch = 128
                self.timeout = 900.0

        else:
            # ── Multi-GPU Modu (2+ GPU) ──
            self.num_thread = max(4, physical_cores // 4)  # GPU ağırlıklı

            # ── Model boyutu vs toplam VRAM kontrolü ──
            estimated_size = self._estimate_model_size_gb()
            # Multi-GPU overhead: sadece CUDA context (~500MB/GPU) + küçük allocator overhead
            # 2×24GB = 48GB → %8 overhead = 44.2GB kullanılabilir (72B Q4 ≈ 43.2GB → sığar)
            usable_vram = self.total_vram_gb * 0.92  # %8 overhead (CUDA context per GPU)

            if estimated_size > 0 and estimated_size > usable_vram:
                # Model toplam VRAM'e sığmıyor → multi-GPU kısmi offload
                _match = re.search(r'(\d+)b', getattr(settings, "LLM_MODEL", "").lower())
                _params_b = int(_match.group(1)) if _match else 0
                _estimated_layers = max(32, int(_params_b * 1.1))

                if usable_vram >= 8:
                    _layer_ratio = min(0.95, usable_vram / estimated_size)
                    _partial_layers = max(1, int(_estimated_layers * _layer_ratio))

                    logger.info(
                        "gpu_multi_partial_offload",
                        model_size_gb=estimated_size,
                        total_vram_gb=self.total_vram_gb,
                        usable_vram_gb=usable_vram,
                        gpu_count=gpu_count,
                        total_layers_est=_estimated_layers,
                        offload_layers=_partial_layers,
                        offload_ratio=f"{_layer_ratio:.1%}",
                    )
                    self.num_gpu = _partial_layers
                    self.num_ctx = 8192
                    self.num_batch = 512
                    self.timeout = 900.0
                else:
                    # Toplam VRAM < 8GB → CPU-only
                    logger.info(
                        "multi_gpu_insufficient",
                        model_size_gb=estimated_size,
                        total_vram_gb=self.total_vram_gb,
                        decision="CPU-only",
                    )
                    self.num_gpu = 0
                    self.num_ctx = 8192
                    self.num_batch = 512
                    self.num_thread = physical_cores
                    self.timeout = 900.0
                return

            self.num_gpu = 99  # Ollama otomatik dağıtır

            # v5.9.1: Model boyutu VRAM'in %85+'ını kaplıyorsa context'i düşük tut
            # 72B Q4 ≈ 47GB, 2×24GB = 48GB → KV cache'e yer kalmıyor → 8K yeterli
            _model_fills_vram = (estimated_size > 0 and estimated_size >= usable_vram * 0.85)

            if self.total_vram_gb >= 48:
                # 48GB+ toplam (örn: 2×24GB veya 3×16GB)
                if _model_fills_vram:
                    # Model VRAM'i çok dolduruyor → KV cache'e az yer → 8K context
                    # Bu ayar TPS'i de artırır (16K→8K: 2.9→7.7 TPS)
                    self.num_ctx = 8192
                    self.num_batch = 512
                else:
                    self.num_ctx = 16384
                    self.num_batch = 1024
                self.timeout = 900.0
            elif self.total_vram_gb >= 24:
                # 24-48GB toplam
                if _model_fills_vram:
                    self.num_ctx = 8192
                    self.num_batch = 512
                else:
                    self.num_ctx = 16384
                    self.num_batch = 1024
                self.timeout = 900.0
            else:
                # <24GB toplam
                self.num_ctx = 8192
                self.num_batch = 512
                self.timeout = 900.0

    @property
    def options(self) -> dict:
        """Ollama API'ye gönderilecek options dict'i.
        
        ÖNEMLİ: num_gpu=99 gönderilmez — Ollama'nın kendi otomatik GPU
        katman hesaplamasını kullanmasına izin verilir.  Aksi hâlde Ollama
        modeli 99 katmanla GPU'ya yüklemeye çalışır ve VRAM yetersizse
        'unable to allocate CUDA buffer' hatası verir.
        Sadece açık kısmi offload (1-98) veya CPU-only (0) durumunda gönderilir.
        """
        opts = {
            "num_thread": self.num_thread,
            "num_ctx": self.num_ctx,
            "num_batch": self.num_batch,
        }
        # num_gpu=99 → Ollama'ya bırak (göndermiyoruz).
        # Kısmi offload (1 ≤ N < 99) → açık katman sayısını gönder.
        # CPU-only (0) ve GPU mevcut → 0 gönder.
        if 0 < self.num_gpu < 99:
            opts["num_gpu"] = self.num_gpu
        elif self.num_gpu == 0 and self._probed and len(self.gpus) > 0:
            # GPU algılandı ama model için yetersiz → açıkça CPU modunu zorla
            opts["num_gpu"] = 0
        # num_gpu == 99 → Ollama otomatik belirler, options'a eklenmez.
        return opts

    @property
    def is_gpu_available(self) -> bool:
        return len(self.gpus) > 0 or self.total_vram_gb > 0

    @property
    def gpu_count(self) -> int:
        return len(self.gpus)

    @property
    def mode(self) -> str:
        """Çalışma modu string'i."""
        n = len(self.gpus)
        if n == 0 and self.total_vram_gb == 0:
            return "CPU-only"
        elif n >= 1 and 0 < self.num_gpu < 99:
            gpu_name = self.gpus[0].name if self.gpus else "GPU"
            return f"Partial GPU Offload ({gpu_name}, {self.num_gpu} layers)"
        elif n == 1:
            return f"Single GPU ({self.gpus[0].name})"
        elif n > 1:
            return f"Multi-GPU ({n}× GPU, {self.total_vram_gb:.0f}GB VRAM)"
        else:
            return f"GPU (Ollama-detected, {self.total_vram_gb:.0f}GB VRAM)"

    # ── Ollama Environment Senkronizasyonu ──

    def _sync_ollama_env(self) -> bool:
        """
        /etc/default/ollama dosyasındaki CUDA_VISIBLE_DEVICES değerini
        algılanan GPU'lara göre otomatik günceller.

        Dönen: bool — Ollama yeniden başlatıldıysa True.
        """
        if not OLLAMA_ENV_PATH.exists():
            # İlk kurulum veya Windows → atlat
            return False

        try:
            current_env = OLLAMA_ENV_PATH.read_text()
        except PermissionError:
            logger.warning("ollama_env_read_permission_denied", path=str(OLLAMA_ENV_PATH))
            return False

        # ── Beklenen CUDA_VISIBLE_DEVICES değerini hesapla ──
        gpu_count = len(self.gpus)
        if gpu_count == 0:
            desired_cuda = '""'  # GPU yok → Ollama da kullanmasın
        else:
            # Tüm GPU index'lerini virgülle birleştir: "0", "0,1", "0,1,2"
            desired_cuda = ",".join(str(g.index) for g in self.gpus)

        # Mevcut CUDA_VISIBLE_DEVICES değerini bul
        cuda_match = re.search(r'^CUDA_VISIBLE_DEVICES=(.*)$', current_env, re.MULTILINE)
        current_cuda = cuda_match.group(1).strip().strip('"') if cuda_match else None

        # ── Değişiklik gerekiyor mu? ──
        needs_update = current_cuda != desired_cuda

        if not needs_update:
            logger.info("ollama_env_already_synced", cuda_visible_devices=desired_cuda)
            return False

        logger.info(
            "ollama_env_updating",
            old_cuda=current_cuda,
            new_cuda=desired_cuda,
            gpu_count=gpu_count,
        )

        # ── Yeni env dosyası oluştur ──
        new_env = self._build_ollama_env(desired_cuda)

        try:
            OLLAMA_ENV_PATH.write_text(new_env)
            logger.info("ollama_env_written", path=str(OLLAMA_ENV_PATH))
        except PermissionError:
            logger.error("ollama_env_write_permission_denied", path=str(OLLAMA_ENV_PATH))
            return False

        # ── Ollama'yı yeniden başlat ──
        return self._restart_ollama()

    def _build_ollama_env(self, cuda_devices: str) -> str:
        """Algılanan GPU'lara göre optimal /etc/default/ollama içeriği oluştur."""
        gpu_count = len(self.gpus)
        gpu_names = ", ".join(g.name for g in self.gpus) if self.gpus else "None"
        total_vram = f"{self.total_vram_gb:.0f}GB" if self.total_vram_gb else "0GB"

        return f"""# CompanyAI — Ollama Environment Config (Auto-Generated)
# GPU Algılama: {gpu_count} GPU, {total_vram} toplam VRAM
# GPU'lar: {gpu_names}
# Bu dosya gpu_config.py tarafından otomatik güncellenir.

# Flash Attention — bellek kullanımını azaltır, hızlandırır
OLLAMA_FLASH_ATTENTION=1

# KV Cache quantize — VRAM tasarrufu sağlar
OLLAMA_KV_CACHE_TYPE=q8_0

# Paralel istek ve model limitleri
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1

# GPU Erişimi — otomatik ayarlandı ({gpu_count} GPU algılandı)
CUDA_VISIBLE_DEVICES={cuda_devices}

# Model sürekli bellekte kalsın
OLLAMA_KEEP_ALIVE=-1

# Host
OLLAMA_HOST=0.0.0.0:11434
"""

    def _restart_ollama(self) -> bool:
        """Ollama systemd servisini yeniden başlat."""
        try:
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=10)
            result = subprocess.run(
                ["systemctl", "restart", "ollama"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("ollama_restarted_for_gpu_sync")
                # Ollama'nın tam başlaması için kısa bekle
                import time
                time.sleep(3)
                return True
            else:
                logger.error("ollama_restart_failed", stderr=result.stderr[:200])
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning("ollama_restart_skipped", reason=str(e))
            return False

    def summary(self) -> dict:
        """Admin API ve loglar için özet."""
        return {
            "mode": self.mode,
            "gpu_count": len(self.gpus),
            "total_vram_gb": self.total_vram_gb,
            "gpus": [
                {
                    "index": g.index,
                    "name": g.name,
                    "vram_total_gb": g.vram_total_gb,
                    "vram_free_gb": g.vram_free_gb,
                    "utilization_percent": g.utilization_percent,
                    "temperature_c": g.temperature_c,
                }
                for g in self.gpus
            ],
            "applied_config": {
                "num_gpu": self.num_gpu,
                "num_ctx": self.num_ctx,
                "num_batch": self.num_batch,
                "num_thread": self.num_thread,
                "timeout_seconds": self.timeout,
            },
            "probed": self._probed,
        }


# ── Singleton Instance ──
gpu_config = GPUConfig()
