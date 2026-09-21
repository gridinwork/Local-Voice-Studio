"""GPU / VRAM introspection helpers used by GUI status panel and benchmarks."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GpuStatus:
    available: bool
    name: str = ""
    cuda_version: str = ""
    vram_total_mb: float = 0.0
    vram_used_mb: float = 0.0
    vram_free_mb: float = 0.0
    error: str = ""


def get_gpu_status() -> GpuStatus:
    try:
        import torch
    except ImportError as e:
        return GpuStatus(available=False, error=f"PyTorch не установлен: {e}")

    if not torch.cuda.is_available():
        return GpuStatus(available=False, error="CUDA недоступна. Проверьте драйвер NVIDIA и установку PyTorch с поддержкой CUDA.")

    idx = torch.cuda.current_device()
    name = torch.cuda.get_device_name(idx)
    free_b, total_b = torch.cuda.mem_get_info(idx)
    used_b = total_b - free_b
    return GpuStatus(
        available=True,
        name=name,
        cuda_version=torch.version.cuda or "unknown",
        vram_total_mb=total_b / (1024 * 1024),
        vram_used_mb=used_b / (1024 * 1024),
        vram_free_mb=free_b / (1024 * 1024),
    )


def get_process_vram_mb() -> float:
    """VRAM currently allocated by this process via torch (not system-wide)."""
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated() / (1024 * 1024)
    except ImportError:
        pass
    return 0.0


def get_process_vram_peak_mb() -> float:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / (1024 * 1024)
    except ImportError:
        pass
    return 0.0


def reset_peak_stats() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        pass


def empty_cache() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
