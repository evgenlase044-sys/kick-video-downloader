import os
import sys
import time
from typing import Optional

# Force UTF-8 encoding in Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from kick_extractor import KickExtractor
from size_calculator import SizeCalculator
from disk_manager import DiskManager, format_bytes
from downloader import KickDownloader, sanitize_filename

# Optional rich library support
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

def print_header():
    header_text = """
===================================================================
                KICK VIDEO DOWNLOADER & ARCHIVER
     Загрузка VOD/стримов Kick.com с контролем места на диске
===================================================================
"""
    if HAS_RICH:
        console.print(Panel("[bold green]KICK VIDEO DOWNLOADER & ARCHIVER[/bold green]\n[dim]Загрузка VOD/стримов Kick.com в любом качестве с контролем места на диске[/dim]", border_style="green"))
    else:
        print(header_text)

def main():
    print_header()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_dir = os.path.join(base_dir, "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    extractor = KickExtractor(base_dir)
    calculator = SizeCalculator()
    disk_manager = DiskManager(downloads_dir)

    # 1. URL input
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        url = sys.argv[1].strip()
    else:
        default_url = "https://kick.com/jesusavgn/videos/01a0c558-1fd0-7b89-bc86-e5e39b939572"
        print(f"Введите ссылку на видео Kick (Enter для примера):")
        inp = input(f"[{default_url}]: ").strip()
        url = inp if inp else default_url

    print(f"\n[+] Получение информации о видео: {url} ...")
    try:
        info = extractor.extract(url)
    except Exception as e:
        print(f"\n[!] ОШИБКА: {e}")
        sys.exit(1)

    print(f"\nНазвание:   {info['title']}")
    print(f"Стример:    {info['streamer']}")
    print(f"Хронометраж: {info['duration_str']}")
    print(f"Потоков:    {len(info['qualities'])}")

    # 2. Size calculation for each quality
    print("\n[+] Расчет точного размера видео для всех вариантов качества...")
    qualities_data = []

    for idx, q in enumerate(info["qualities"], 1):
        size_res = calculator.calculate_stream_size(q["playlist_url"], q["bandwidth"], info["duration"])
        space_res = disk_manager.check_space(size_res["estimated_bytes"])
        qualities_data.append({
            "index": idx,
            "quality": q,
            "size": size_res,
            "space": space_res
        })

    # 3. Print table of available qualities
    disk_info = disk_manager.get_disk_info()
    print(f"\nЦелевой диск: {disk_info['drive']} (Свободно: {disk_info['free_formatted']} из {disk_info['total_formatted']})\n")

    # Mark source stream
    max_br = max(item["size"]["bitrate_kbps"] for item in qualities_data) if qualities_data else 0

    if HAS_RICH:
        table = Table(title="Доступные качества стрима", border_style="dim")
        table.add_column("№", justify="center", style="bold cyan")
        table.add_column("Качество", style="bold green")
        table.add_column("Разрешение", justify="center")
        table.add_column("FPS", justify="center")
        table.add_column("Битрейт", justify="right", style="cyan")
        table.add_column("Рассчитанный размер", justify="right", style="bold yellow")
        table.add_column("Статус памяти", justify="left")

        for item in qualities_data:
            q = item["quality"]
            s = item["size"]
            sp = item["space"]
            is_src = (s["bitrate_kbps"] == max_br and len(qualities_data) > 1 and item != qualities_data[0])
            lbl = f"{q['label']} [bold magenta](Source)[/bold magenta]" if is_src else q["label"]
            status_str = f"[green]✓ Места хватает ({sp['free_formatted']} свободно)[/green]" if sp["is_enough"] else f"[bold red]⚠ НЕ ХВАТАЕТ! Дефицит: {sp['shortage_formatted']}[/bold red]"
            table.add_row(
                str(item["index"]),
                lbl,
                q["resolution"],
                f"{q['fps']} fps",
                s.get("bitrate_formatted", f"{q['bandwidth']//1000}k"),
                s["formatted_size"],
                status_str
            )
        console.print(table)
    else:
        print(f"{'№':<3} {'Качество':<18} {'Разрешение':<12} {'FPS':<7} {'Битрейт':<12} {'Размер':<14} {'Статус памяти'}")
        print("-" * 88)
        for item in qualities_data:
            q = item["quality"]
            s = item["size"]
            sp = item["space"]
            is_src = (s["bitrate_kbps"] == max_br and len(qualities_data) > 1 and item != qualities_data[0])
            lbl = f"{q['label']} (Source)" if is_src else q["label"]
            status_str = f"[OK] Хватает ({sp['free_formatted']})" if sp["is_enough"] else f"[!] НЕ ХВАТАЕТ! Дефицит: {sp['shortage_formatted']}"
            print(f"{item['index']:<3} {lbl:<18} {q['resolution']:<12} {q['fps']:<7} {s.get('bitrate_formatted', ''):<12} {s['formatted_size']:<14} {status_str}")

    # 4. User selects quality
    choice = 1
    while True:
        try:
            val = input(f"\nВыберите номер качества (1-{len(qualities_data)}) [1]: ").strip()
            if not val:
                choice = 1
                break
            choice = int(val)
            if 1 <= choice <= len(qualities_data):
                break
            print(f"Пожалуйста, введите число от 1 до {len(qualities_data)}.")
        except ValueError:
            print("Некорректный ввод. Введите число.")

    selected = qualities_data[choice - 1]
    req_bytes = selected["size"]["estimated_bytes"]
    q_label = selected["quality"]["label"]

    print(f"\nВыбрано: {q_label} ({selected['size']['formatted_size']})")

    # 5. STRICT DISK SPACE ENFORCEMENT LOOP
    while True:
        check = disk_manager.check_space(req_bytes)
        if check["is_enough"]:
            print(f"[✓] Проверка памяти пройдена! Свободно: {check['free_formatted']}, требуется: {check['required_formatted']}.")
            print(f"    После скачивания останется: {check['remaining_after_formatted']}.")
            break

        # Insufficient space: STRICT REQUIREMENT TO DELETE FILES
        required_with_buffer = int(check['required_bytes'] * 1.05)
        required_buffer_formatted = format_bytes(required_with_buffer)
        print("\n" + "=" * 76)
        print(f" [!] ВНИМАНИЕ: НЕ ХВАТАЕТ МЕСТА НА ДИСКЕ {check['drive']}!")
        print(f"     Требуется для видео: {check['required_formatted']} (с запасом 5%: {required_buffer_formatted})")
        print(f"     Свободно сейчас:    {check['free_formatted']}")
        print(f"     Дефицит места:      {check['shortage_formatted']}")
        print(f"\n     ДЛЯ ПРОДОЛЖЕНИЯ СКАЧИВАНИЯ НЕОБХОДИМО УДАЛИТЬ ФАЙЛЫ")
        print(f"     И ОСВОБОДИТЬ КАК МИНИМУМ {check['shortage_formatted']}!")
        print("=" * 76)

        user_input = input("\nОсвободите место на диске и нажмите [Enter] для повторной проверки (или 'q' для выхода): ").strip().lower()
        if user_input in ("q", "quit", "exit"):
            print("Отменено пользователем.")
            sys.exit(0)

    # 6. Fetch segments list
    print(f"\n[+] Загрузка плейлиста сегментов...")
    segments, _ = calculator.fetch_playlist_segments(selected["quality"]["playlist_url"])
    print(f"[+] Всего сегментов: {len(segments)}")

    # 7. Download and Merge
    output_filename = f"{selected['quality']['label']}_{sanitize_filename(info['streamer'])}_{sanitize_filename(info['title'])}.mp4"
    downloader = KickDownloader(output_dir=downloads_dir, max_workers=14)

    print(f"[+] Сохранение в: {os.path.join(downloads_dir, output_filename)}")
    print("[+] Начинается загрузка...\n")

    last_pct = -1

    def progress_callback(data):
        nonlocal last_pct
        pct = data["percent"]
        if int(pct) != last_pct:
            last_pct = int(pct)
            status = data["status"]
            if status == "downloading":
                bar_len = 30
                filled = int(bar_len * (pct / 100))
                bar = "█" * filled + "░" * (bar_len - filled)
                sys.stdout.write(
                    f"\r[{bar}] {pct:5.1f}% | {data['downloaded_formatted']} / {data['total_formatted']} "
                    f"| {data['speed_formatted']} | ETA: {data['eta_formatted']} | "
                    f"Сегменты: {data['completed_segments']}/{data['total_segments']}   "
                )
                sys.stdout.flush()
            elif status == "merging":
                print(f"\n\n[+] Все сегменты скачаны! Сборка цельного MP4 через FFmpeg...")

    try:
        final_mp4 = downloader.download_stream(
            segment_urls=segments,
            output_filename=output_filename,
            estimated_total_bytes=req_bytes,
            progress_callback=progress_callback
        )
        print(f"\n[✓] УСПЕШНО ЗАВЕРШЕНО!")
        print(f"[✓] Видео сохранено: {final_mp4}")
        print(f"[✓] Размер файла: {format_bytes(os.path.getsize(final_mp4))}")
    except KeyboardInterrupt:
        print("\n\n[!] Загрузка прервана пользователем.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[!] ОШИБКА: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()