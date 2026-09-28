import argparse
import os
import re
import subprocess
import sys
from typing import Optional

# Force UTF-8 encoding in Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from kick_extractor import KickExtractor
from size_calculator import SizeCalculator, HLSUnsupportedError
from disk_manager import DiskManager, format_bytes, DOWNLOAD_PEAK_FACTOR
from downloader import KickDownloader, sanitize_filename

# Optional rich library support
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

DEFAULT_URL = "https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572"


def parse_timecode(value: Optional[str]) -> Optional[float]:
    """'90', '1:30', '01:02:03.5' -> seconds."""
    if value is None or str(value).strip() == "":
        return None
    s = str(value).strip()
    if not re.fullmatch(r"\d+(:\d{1,2}){0,2}(\.\d+)?", s):
        raise argparse.ArgumentTypeError(f"неверный таймкод: {value!r} (пример: 1:02:03)")
    parts = [float(p) for p in s.split(":")]
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def print_header():
    if HAS_RICH:
        console.print(Panel("[bold green]KICK VIDEO DOWNLOADER & ARCHIVER[/bold green]\n"
                            "[dim]Загрузка VOD/стримов Kick.com с контролем места на диске[/dim]", border_style="green"))
    else:
        print("=" * 67)
        print("                KICK VIDEO DOWNLOADER & ARCHIVER")
        print("     Загрузка VOD/стримов Kick.com с контролем места на диске")
        print("=" * 67)


def build_args(argv=None):
    ap = argparse.ArgumentParser(description="Kick VOD downloader")
    ap.add_argument("url", nargs="?", help="ссылка на VOD Kick")
    ap.add_argument("-q", "--quality", type=int, help="номер качества из таблицы (без вопроса)")
    ap.add_argument("--start", type=parse_timecode, help="начало фрагмента (1:02:03)")
    ap.add_argument("--end", type=parse_timecode, help="конец фрагмента (1:05:00)")
    ap.add_argument("-y", "--yes", action="store_true", help="не задавать вопросов")
    a = ap.parse_args(argv)
    if (a.start is None) != (a.end is None):
        ap.error("--start и --end указываются вместе")
    if a.start is not None and a.end <= a.start:
        ap.error("--end должен быть позже --start")
    return a


def trim_exact(src: str, offset: float, duration: float) -> str:
    """Frame-accurate trim of the downloaded segment range (re-encode only
    the requested window; -c copy would snap to keyframes)."""
    out = os.path.splitext(src)[0] + "_cut.mp4"
    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-ss", f"{offset:.3f}", "-i", src,
           "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "0:a:0?",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg не смог обрезать фрагмент: {r.stderr[-400:]}")
    os.replace(out, src)
    return src


def main(argv=None):
    args = build_args(argv)
    print_header()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_dir = os.path.join(base_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    extractor = KickExtractor(base_dir)
    disk_manager = DiskManager(downloads_dir)

    # 1. URL input
    url = (args.url or "").strip()
    if not url.startswith("http"):
        if args.yes:
            print("[!] Укажите ссылку на видео")
            sys.exit(2)
        print("Введите ссылку на видео Kick (Enter для примера):")
        inp = input(f"[{DEFAULT_URL}]: ").strip()
        url = inp if inp else DEFAULT_URL

    print(f"\n[+] Получение информации о видео: {url} ...")
    try:
        info = extractor.extract(url)
    except Exception as e:
        print(f"\n[!] ОШИБКА: {e}")
        sys.exit(1)

    # cookies/UA from the extractor: segments behind Cloudflare 403 without them
    headers = None
    try:
        headers = extractor.get_size_headers()
    except Exception:
        headers = None
    calculator = SizeCalculator(headers=headers)

    print(f"\nНазвание:   {info['title']}")
    print(f"Стример:    {info['streamer']}")
    print(f"Хронометраж: {info['duration_str']}")
    print(f"Потоков:    {len(info['qualities'])}")

    # 2. Size estimate for each quality
    print("\n[+] Оценка размера видео для всех вариантов качества (HEAD-выборка сегментов)...")
    qualities_data = []
    span = (args.end - args.start) if args.start is not None else None
    for idx, q in enumerate(info["qualities"], 1):
        size_res = calculator.calculate_stream_size(q["playlist_url"], q["bandwidth"], info["duration"])
        est = size_res["estimated_bytes"]
        if span and size_res["duration_seconds"] > 0:
            est = int(est * min(1.0, (span + 20) / size_res["duration_seconds"]))
        space_res = disk_manager.check_space(est, peak_factor=DOWNLOAD_PEAK_FACTOR)
        qualities_data.append({"index": idx, "quality": q, "size": size_res, "bytes": est, "space": space_res})

    disk_info = disk_manager.get_disk_info()
    print(f"\nЦелевой диск: {disk_info['drive']} (Свободно: {disk_info['free_formatted']} из {disk_info['total_formatted']})\n")
    max_br = max(item["size"]["bitrate_kbps"] for item in qualities_data) if qualities_data else 0

    if HAS_RICH:
        table = Table(title="Доступные качества стрима", border_style="dim")
        for col, kw in (("№", {"justify": "center", "style": "bold cyan"}), ("Качество", {"style": "bold green"}),
                        ("Разрешение", {"justify": "center"}), ("FPS", {"justify": "center"}),
                        ("Битрейт", {"justify": "right", "style": "cyan"}),
                        ("≈ Размер", {"justify": "right", "style": "bold yellow"}), ("Статус памяти", {})):
            table.add_column(col, **kw)
        for item in qualities_data:
            q, s, sp = item["quality"], item["size"], item["space"]
            is_src = (s["bitrate_kbps"] == max_br and len(qualities_data) > 1 and item != qualities_data[0])
            lbl = f"{q['label']} [bold magenta](Source)[/bold magenta]" if is_src else q["label"]
            status_str = (f"[green]✓ Хватает ({sp['free_formatted']} свободно)[/green]" if sp["is_enough"]
                          else f"[bold red]⚠ НЕ ХВАТАЕТ! Дефицит: {sp['shortage_formatted']}[/bold red]")
            table.add_row(str(item["index"]), lbl, q["resolution"], f"{q['fps']} fps",
                          s.get("bitrate_formatted", f"{q['bandwidth'] // 1000}k"),
                          format_bytes(item["bytes"]), status_str)
        console.print(table)
    else:
        print(f"{'№':<3} {'Качество':<18} {'Разрешение':<12} {'FPS':<7} {'Битрейт':<12} {'≈ Размер':<14} {'Статус памяти'}")
        print("-" * 88)
        for item in qualities_data:
            q, s, sp = item["quality"], item["size"], item["space"]
            is_src = (s["bitrate_kbps"] == max_br and len(qualities_data) > 1 and item != qualities_data[0])
            lbl = f"{q['label']} (Source)" if is_src else q["label"]
            status_str = f"[OK] Хватает ({sp['free_formatted']})" if sp["is_enough"] else f"[!] НЕ ХВАТАЕТ! Дефицит: {sp['shortage_formatted']}"
            print(f"{item['index']:<3} {lbl:<18} {q['resolution']:<12} {q['fps']:<7} {s.get('bitrate_formatted', ''):<12} {format_bytes(item['bytes']):<14} {status_str}")

    if not qualities_data:
        print("[!] Нет доступных потоков")
        sys.exit(1)

    # 4. Quality
    if args.quality:
        if not 1 <= args.quality <= len(qualities_data):
            print(f"[!] Качество должно быть от 1 до {len(qualities_data)}")
            sys.exit(2)
        choice = args.quality
    elif args.yes:
        choice = 1
    else:
        choice = 1
        while True:
            try:
                val = input(f"\nВыберите номер качества (1-{len(qualities_data)}) [1]: ").strip()
                if not val:
                    break
                choice = int(val)
                if 1 <= choice <= len(qualities_data):
                    break
                print(f"Пожалуйста, введите число от 1 до {len(qualities_data)}.")
            except ValueError:
                print("Некорректный ввод. Введите число.")

    selected = qualities_data[choice - 1]
    req_bytes = selected["bytes"]
    q_label = selected["quality"]["label"]
    print(f"\nВыбрано: {q_label} (≈{format_bytes(req_bytes)})")

    # 5. Segment list (whole VOD or the requested slice)
    print("\n[+] Загрузка плейлиста сегментов...")
    trim = None
    try:
        if args.start is not None:
            detailed, _ = calculator.fetch_playlist_segments_detailed(selected["quality"]["playlist_url"])
            segments, range_dur, total, range_start = SizeCalculator.slice_range(detailed, args.start, args.end)
            trim = (args.start - range_start, min(args.end, total) - args.start)
            print(f"[+] Фрагмент {args.start:.1f}–{min(args.end, total):.1f} с: {len(segments)} сегментов")
        else:
            segments, _ = calculator.fetch_playlist_segments(selected["quality"]["playlist_url"])
            print(f"[+] Всего сегментов: {len(segments)}")
    except (HLSUnsupportedError, ValueError) as e:
        print(f"[!] {e}")
        sys.exit(1)

    # 6. STRICT DISK SPACE ENFORCEMENT LOOP (peak: segments + MP4, +5%)
    while True:
        check = disk_manager.check_space(req_bytes, peak_factor=DOWNLOAD_PEAK_FACTOR)
        if check["is_enough"]:
            print(f"[✓] Проверка памяти пройдена! Свободно: {check['free_formatted']}, "
                  f"нужно на пике: {check['required_safety_formatted']}.")
            break
        print("\n" + "=" * 76)
        print(f" [!] ВНИМАНИЕ: НЕ ХВАТАЕТ МЕСТА НА ДИСКЕ {check['drive']}!")
        print(f"     Видео: {check['required_formatted']}; на пике (сегменты + MP4, запас 5%): {check['required_safety_formatted']}")
        print(f"     Свободно сейчас:    {check['free_formatted']}")
        print(f"     Дефицит места:      {check['shortage_formatted']}")
        print("=" * 76)
        if args.yes:
            sys.exit(1)
        user_input = input("\nОсвободите место и нажмите [Enter] для повторной проверки (или 'q' для выхода): ").strip().lower()
        if user_input in ("q", "quit", "exit"):
            print("Отменено пользователем.")
            sys.exit(0)

    # 7. Download and merge
    suffix = f"_{int(args.start)}-{int(args.end)}s" if args.start is not None else ""
    output_filename = f"{q_label}_{sanitize_filename(info['streamer'])}_{sanitize_filename(info['title'])}{suffix}.mp4"
    downloader = KickDownloader(output_dir=downloads_dir, max_workers=14, headers=headers)
    print(f"[+] Сохранение в: {os.path.join(downloads_dir, output_filename)}")
    print("[+] Начинается загрузка (прерванная загрузка продолжится с места обрыва)...\n")

    last_pct = -1

    def progress_callback(data):
        nonlocal last_pct
        pct = data["percent"]
        if int(pct) != last_pct:
            last_pct = int(pct)
            if data["status"] == "downloading":
                bar_len = 30
                filled = int(bar_len * (pct / 100))
                bar = "█" * filled + "░" * (bar_len - filled)
                sys.stdout.write(
                    f"\r[{bar}] {pct:5.1f}% | {data['downloaded_formatted']} / {data['total_formatted']} "
                    f"| {data['speed_formatted']} | ETA: {data['eta_formatted']} | "
                    f"Сегменты: {data['completed_segments']}/{data['total_segments']}   ")
                sys.stdout.flush()
            elif data["status"] == "merging":
                print("\n\n[+] Все сегменты скачаны! Сборка цельного MP4 через FFmpeg...")

    try:
        final_mp4 = downloader.download_stream(segment_urls=segments, output_filename=output_filename,
                                               estimated_total_bytes=req_bytes, progress_callback=progress_callback)
        if trim:
            print(f"[+] Точная обрезка фрагмента ({trim[1]:.1f} с)...")
            trim_exact(final_mp4, trim[0], trim[1])
        print("\n[✓] УСПЕШНО ЗАВЕРШЕНО!")
        print(f"[✓] Видео сохранено: {final_mp4}")
        print(f"[✓] Размер файла: {format_bytes(os.path.getsize(final_mp4))}")
    except KeyboardInterrupt:
        print("\n\n[!] Загрузка прервана. Повторный запуск продолжит с места обрыва.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[!] ОШИБКА: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
