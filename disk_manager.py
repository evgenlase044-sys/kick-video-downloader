import os
import shutil
from typing import Dict, Any, Optional

def format_bytes(bytes_val: int) -> str:
    """Format bytes into readable string (B, KB, MB, GB, TB)."""
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

    def check_space(
        self,
        required_bytes: int,
        path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if target disk has enough free space for the video.
        Requires exactly the video size without any extra buffers.
        """
        disk_info = self.get_disk_info(path)
        free_bytes = disk_info["free_bytes"]
        
        is_enough = free_bytes >= required_bytes
        shortage_bytes = max(0, required_bytes - free_bytes)
        remaining_after = max(0, free_bytes - required_bytes)

        if not is_enough:
            status = "INSUFFICIENT_SPACE"
            message = (
                f"ОШИБКА: Недостаточно свободного места на диске {disk_info['drive']}! "
                f"Требуется для видео: {format_bytes(required_bytes)}, "
                f"свободно на диске: {format_bytes(free_bytes)}. "
                f"Необходимо удалить файлы и освободить как минимум {format_bytes(shortage_bytes)} перед скачиванием!"
            )
        else:
            status = "ENOUGH_SPACE"
            message = (
                f"Места достаточно. Свободно: {format_bytes(free_bytes)}, "
                f"требуется для видео: {format_bytes(required_bytes)}. "
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
    
    # Test with 5 GB (typical 1080p stream)
    test_5gb = 5 * 1024 * 1024 * 1024
    res = dm.check_space(test_5gb)
    print("\nCheck for 5 GB download:")
    print("Is enough:", res["is_enough"])
    print("Message:", res["message"])
    
    # Test with simulated 500 GB (force shortage check)
    test_huge = 500 * 1024 * 1024 * 1024
    res_huge = dm.check_space(test_huge)
    print("\nCheck for 500 GB (simulated shortage):")
    print("Is enough:", res_huge["is_enough"])
    print("Message:", res_huge["message"])
