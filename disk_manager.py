import os
import shutil
from typing import Dict, Any, Optional

# Safety margin promised in the README: free space must cover the peak need
# plus 5% (filesystem overhead, ffmpeg temp, moov rewrite for +faststart).
SAFETY_RATIO = 0.05
# While an HLS VOD is merged, the .ts segments AND the final MP4 exist at the
# same time -> the peak need is ~2x the stream size.
DOWNLOAD_PEAK_FACTOR = 2.0


def format_bytes(bytes_val: int) -> str:
    """Format bytes into readable string (B, KB, MB, GB, TB)."""
    bytes_val = int(bytes_val or 0)
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.2f} MB"
    elif bytes_val < 1024 * 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024 * 1024):.2f} TB"


class DiskManager:
    def __init__(self, target_dir: Optional[str] = None):
        self.target_dir = target_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        os.makedirs(self.target_dir, exist_ok=True)

    def get_drive(self, path: Optional[str] = None) -> str:
        """Get drive or mount point for a directory."""
        check_path = os.path.abspath(path or self.target_dir)
        drive, _ = os.path.splitdrive(check_path)
        if drive:
            return drive + "\\"
        return check_path

    def get_disk_info(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Query total, used, and free space on the target disk."""
        check_path = os.path.abspath(path or self.target_dir)
        if not os.path.exists(check_path):
            os.makedirs(check_path, exist_ok=True)

        usage = shutil.disk_usage(check_path)
        drive = self.get_drive(check_path)

        used_pct = round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0.0
        free_pct = round((usage.free / usage.total) * 100, 1) if usage.total > 0 else 0.0

        return {
            "path": check_path,
            "drive": drive,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total_formatted": format_bytes(usage.total),
            "used_formatted": format_bytes(usage.used),
            "free_formatted": format_bytes(usage.free),
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "used_pct": used_pct,
            "free_pct": free_pct
        }

    @staticmethod
    def required_with_margin(required_bytes: int, peak_factor: float = 1.0,
                             safety_ratio: float = SAFETY_RATIO, already_present_bytes: int = 0) -> int:
        """Bytes that must be free: peak need (e.g. segments + MP4) + safety
        margin, minus what is already on disk from a resumed download."""
        req = max(0, int(required_bytes or 0))
        peak = int(req * max(1.0, float(peak_factor or 1.0)))
        need = int(peak * (1.0 + max(0.0, float(safety_ratio or 0.0))))
        return max(0, need - max(0, int(already_present_bytes or 0)))

    def check_space(
        self,
        required_bytes: int,
        path: Optional[str] = None,
        peak_factor: float = 1.0,
        safety_ratio: float = SAFETY_RATIO,
        already_present_bytes: int = 0,
    ) -> Dict[str, Any]:
        """
        Check if the target disk has enough free space.

        required_bytes  - size of the video itself;
        peak_factor     - how many copies exist at the peak (HLS merge = 2.0);
        safety_ratio    - extra margin (README: 5%);
        already_present_bytes - bytes of segments already downloaded (resume).
        """
        disk_info = self.get_disk_info(path)
        free_bytes = disk_info["free_bytes"]
        required_bytes = max(0, int(required_bytes or 0))
        need = self.required_with_margin(required_bytes, peak_factor, safety_ratio, already_present_bytes)

        is_enough = free_bytes >= need
        shortage_bytes = max(0, need - free_bytes)
        remaining_after = max(0, free_bytes - required_bytes)

        if not is_enough:
            status = "INSUFFICIENT_SPACE"
            message = (
                f"ОШИБКА: Недостаточно свободного места на диске {disk_info['drive']}! "
                f"Видео: {format_bytes(required_bytes)}, нужно свободно на пике "
                f"(с учётом сборки и запаса {int(safety_ratio * 100)}%): {format_bytes(need)}, "
                f"свободно: {format_bytes(free_bytes)}. "
                f"Освободите как минимум {format_bytes(shortage_bytes)} перед скачиванием!"
            )
        else:
            status = "ENOUGH_SPACE"
            message = (
                f"Места достаточно. Свободно: {format_bytes(free_bytes)}, "
                f"нужно на пике: {format_bytes(need)} (видео {format_bytes(required_bytes)}). "
                f"После скачивания останется свободно: {format_bytes(remaining_after)}."
            )

        return {
            "is_enough": is_enough,
            "status": status,
            "message": message,
            "drive": disk_info["drive"],
            "path": disk_info["path"],
            "required_bytes": required_bytes,
            "required_formatted": format_bytes(required_bytes),
            # peak need incl. safety margin (cli.py shows it as "с запасом")
            "required_safety_bytes": need,
            "required_safety_formatted": format_bytes(need),
            "peak_factor": peak_factor,
            "safety_ratio": safety_ratio,
            "free_bytes": free_bytes,
            "free_formatted": disk_info["free_formatted"],
            "total_bytes": disk_info["total_bytes"],
            "total_formatted": disk_info["total_formatted"],
            "used_bytes": disk_info["used_bytes"],
            "used_formatted": disk_info["used_formatted"],
            "shortage_bytes": shortage_bytes,
            "shortage_formatted": format_bytes(shortage_bytes),
            "remaining_after_bytes": remaining_after,
            "remaining_after_formatted": format_bytes(remaining_after),
            "used_pct": disk_info["used_pct"],
            "free_pct": disk_info["free_pct"]
        }


if __name__ == "__main__":
    dm = DiskManager()
    info = dm.get_disk_info()
    print("Disk Info for:", info["drive"])
    print(f"Total: {info['total_formatted']} | Used: {info['used_formatted']} ({info['used_pct']}%) | Free: {info['free_formatted']} ({info['free_pct']}%)")
    res = dm.check_space(5 * 1024 ** 3, peak_factor=DOWNLOAD_PEAK_FACTOR)
    print("\nCheck for 5 GB download (peak x2 + 5%):", res["is_enough"], "-", res["message"])
