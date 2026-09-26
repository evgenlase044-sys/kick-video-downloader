import os
import sys
import shutil
from kick_extractor import KickExtractor
from size_calculator import SizeCalculator
from disk_manager import DiskManager, format_bytes
from downloader import KickDownloader

# Ensure UTF-8 output
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def test_full_pipeline():
    print("==========================================================")
    print("   1. ТЕСТ ИЗВЛЕЧЕНИЯ ДАННЫХ С KICK.COM")
    print("==========================================================")
    test_url = "https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572"
    extractor = KickExtractor()
    info = extractor.extract(test_url)

    print(f"✓ Заголовок: {info['title']}")
    print(f"✓ Стример:   {info['streamer']}")
    print(f"✓ Длительность: {info['duration_str']} ({info['duration']} сек)")
    print(f"✓ Master M3U8: {info['master_m3u8'][:60]}...")
    print(f"✓ Найдено качеств: {len(info['qualities'])}")
    assert len(info["qualities"]) >= 3, "Должно быть минимум 3 качества"

    print("\n==========================================================")
    print("   2. ТЕСТ ТОЧНОГО РАСЧЕТА РАЗМЕРА И СЕМПЛИРОВАНИЯ (HEAD)")
    print("==========================================================")
    calculator = SizeCalculator()
    for q in info["qualities"]:
        res = calculator.calculate_stream_size(q["playlist_url"], q["bandwidth"], info["duration"], sample_count=5)
        print(f" - [{q['label']}] {q['resolution']} @ {q['fps']}fps: {res['formatted_size']} ({res['segments_count']} сегментов)")
        assert res["estimated_bytes"] > 0, f"Размер для {q['label']} должен быть больше 0"

    print("\n==========================================================")
    print("   3. ТЕСТ КОНТРОЛЯ МЕСТА НА ДИСКЕ И СТРОГОЙ БЛОКИРОВКИ")
    print("==========================================================")
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
    dm = DiskManager(test_dir)
    disk_info = dm.get_disk_info()
    print(f"Целевой диск: {disk_info['drive']}")
    print(f"Свободно: {disk_info['free_formatted']} из {disk_info['total_formatted']}")

    # 3.1 Normal size test
    normal_size = 2 * 1024 * 1024 * 1024  # 2 GB
    normal_res = dm.check_space(normal_size)
    print(f"\nПроверка нормального размера (2 GB):")
    print(f"  Хватает места: {normal_res['is_enough']}")
    print(f"  Статус: {normal_res['status']}")
    assert normal_res["is_enough"] is True

    # 3.2 Shortage test (simulate requiring more than free space)
    huge_size = disk_info["free_bytes"] + 10 * 1024 * 1024 * 1024  # free + 10 GB
    huge_res = dm.check_space(huge_size)
    print(f"\nПроверка сценария дефицита места (требуется {format_bytes(huge_size)}):")
    print(f"  Хватает места: {huge_res['is_enough']}")
    print(f"  Статус: {huge_res['status']}")
    print(f"  Дефицит: {huge_res['shortage_formatted']}")
    print(f"  Сообщение: {huge_res['message']}")
    assert huge_res["is_enough"] is False
    assert huge_res["shortage_bytes"] > 0

    print("\n==========================================================")
    print("   4. ТЕСТ СКАЧИВАНИЯ 3 ТЕСТОВЫХ СЕГМЕНТОВ И СБОРКИ В MP4")
    print("==========================================================")
    # Pick lowest quality (160p) and download first 3 segments to verify FFmpeg muxing
    lowest_q = info["qualities"][-1]
    all_segments, _ = calculator.fetch_playlist_segments(lowest_q["playlist_url"])
    test_segments = all_segments[:3]
    print(f"Тестовое качество: {lowest_q['label']}")
    print(f"Всего сегментов в видео: {len(all_segments)}, тестируем первые {len(test_segments)}")

    downloader = KickDownloader(output_dir=test_dir, max_workers=3)
    test_mp4_name = "_test_verification.mp4"
    
    events = []
    def on_prog(p):
        events.append(p["status"])

    final_file = downloader.download_stream(
        segment_urls=test_segments,
        output_filename=test_mp4_name,
        estimated_total_bytes=1024 * 1024,
        progress_callback=on_prog,
        force_skip_space_check=True
    )

    print(f"✓ Выходной файл создан: {final_file}")
    assert os.path.exists(final_file), "MP4 файл должен существовать"
    size = os.path.getsize(final_file)
    print(f"✓ Размер тестового видео: {format_bytes(size)}")
    assert size > 0, "Файл не должен быть пустым"
    assert "downloading" in events
    assert "merging" in events
    assert "completed" in events

    # Clean up test mp4
    try:
        os.remove(final_file)
        print("✓ Тестовый временный файл успешно удален")
    except Exception:
        pass

    print("\n==========================================================")
    print("   ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    print("==========================================================")

if __name__ == "__main__":
    test_full_pipeline()
