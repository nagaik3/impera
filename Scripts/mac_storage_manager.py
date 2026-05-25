#!/usr/bin/env python3
"""
mac_storage_manager.py — Gestão de armazenamento macOS (Apple Silicon / Sequoia)
Autor: Iago Almeida
Replicação das funcionalidades do CleanMyMac via shell puro.

Uso:
  python3 mac_storage_manager.py --report
  python3 mac_storage_manager.py --phase 1
  python3 mac_storage_manager.py --phase 1 --execute
  python3 mac_storage_manager.py --phase 1 --execute --confirm-extras
  python3 mac_storage_manager.py --phase 2 --execute
  python3 mac_storage_manager.py --phase 3 --execute
  python3 mac_storage_manager.py --all --execute
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────
# ANSI colors (no third-party deps)
# ─────────────────────────────────────────────
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

HOME = Path.home()
LOG_FILE = HOME / "Scripts" / "logs" / "mac_storage_manager.log"

# ─────────────────────────────────────────────
# SAFETY: paths that must NEVER be touched
# ─────────────────────────────────────────────
PROTECTED_PATHS = [
    HOME / "Scripts",
    HOME / "Obsidian",
    HOME / "Library" / "Application Support" / "Claude" / "vm_bundles",
    HOME / "Library" / "Application Support" / "Google" / "Chrome",
    HOME / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions",
    HOME / ".colima",
    HOME / "Library" / "Group Containers" / "group.net.whatsapp.WhatsApp.shared" / "Message",
]

SERVIDOR_AL = Path("/Volumes/Servidor AL")
SAMSUNG_USB  = Path("/Volumes/Samsung USB")


def is_protected(path: Path) -> bool:
    """Return True if path is inside any protected directory."""
    p = Path(path).resolve()
    for protected in PROTECTED_PATHS:
        try:
            p.relative_to(protected.resolve())
            return True
        except ValueError:
            continue
    return False


def cprint(color: str, msg: str) -> None:
    print(f"{color}{msg}{RESET}")


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    print(line)


def human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f}PB"


def dir_size(path: Path) -> int:
    """Return total size in bytes of a directory tree, 0 if not found."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                try:
                    total += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return total


def safe_remove(path: Path, dry_run: bool = True) -> int:
    """Remove a path (file or directory). Returns bytes freed (0 on dry-run)."""
    if is_protected(path):
        cprint(RED, f"  [BLOQUEADO] {path} está numa zona protegida — abortando")
        return 0
    size = dir_size(path) if path.is_dir() else (path.stat().st_size if path.exists() else 0)
    if dry_run:
        cprint(YELLOW, f"  [DRY-RUN] removeria {path} ({human_size(size)})")
        return 0
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()
        cprint(GREEN, f"  [OK] removido {path} ({human_size(size)})")
        log(f"REMOVED {path} ({human_size(size)})")
        return size
    except Exception as e:
        cprint(RED, f"  [ERRO] {path}: {e}")
        log(f"ERROR removing {path}: {e}")
        return 0


def safe_copy(src: Path, dst: Path, dry_run: bool = True) -> int:
    """Copy src to dst, skipping if dst already exists. Returns bytes copied."""
    size = dir_size(src) if src.is_dir() else (src.stat().st_size if src.exists() else 0)
    if not src.exists():
        cprint(RED, f"  [SKIP] origem não existe: {src}")
        return 0
    if dst.exists():
        cprint(CYAN, f"  [SKIP] já existe no destino: {dst.name}")
        return 0
    if dry_run:
        cprint(YELLOW, f"  [DRY-RUN] copiaria {src.name} → {dst.parent} ({human_size(size)})")
        return 0
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        cprint(GREEN, f"  [OK] copiado {src.name} → {dst.parent} ({human_size(size)})")
        log(f"COPIED {src} → {dst} ({human_size(size)})")
        return size
    except Exception as e:
        cprint(RED, f"  [ERRO] {src.name}: {e}")
        log(f"ERROR copying {src} → {dst}: {e}")
        return 0


def run_cmd(cmd: list, dry_run: bool = True, description: str = "") -> bool:
    """Run a shell command. Returns True on success."""
    if dry_run:
        cprint(YELLOW, f"  [DRY-RUN] executaria: {' '.join(cmd)}")
        return True
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            cprint(GREEN, f"  [OK] {description or ' '.join(cmd)}")
            log(f"CMD OK: {' '.join(cmd)}")
            return True
        else:
            cprint(RED, f"  [ERRO] {description}: {result.stderr.strip()}")
            log(f"CMD FAIL: {' '.join(cmd)} | {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        cprint(RED, f"  [TIMEOUT] {' '.join(cmd)}")
        return False
    except Exception as e:
        cprint(RED, f"  [ERRO] {e}")
        return False


# ─────────────────────────────────────────────
# PHASE 1 — CLEANUP
# ─────────────────────────────────────────────

SAFE_CLEANUP_TARGETS = [
    (HOME / "Library" / "Caches" / "Google" / "Chrome",
     "Chrome caches (~/Library/Caches/Google/Chrome)"),
    (HOME / "Library" / "Application Support" / "Notion" / "Partitions" / "notion" / "Service Worker" / "CacheStorage",
     "Notion Service Worker CacheStorage (4.4GB)"),
    (HOME / "Library" / "Application Support" / "Notion" / "Partitions" / "notion" / "Cache",
     "Notion Partition Cache"),
    (HOME / "Library" / "Caches" / "Comet",
     "Comet cache"),
    (HOME / "Library" / "Caches" / "colima",
     "Colima cache (not VM disks)"),
    (HOME / "Library" / "Caches" / "@granolaelectron-updater",
     "Granola updater cache"),
    (HOME / "Library" / "Caches" / "pip",
     "pip cache"),
    (HOME / "Library" / "Logs" / "CreativeCloud",
     "Adobe CreativeCloud logs"),
    (HOME / "Movies" / "CacheClip",
     "CacheClip (video capture cache)"),
    (HOME / "Library" / "Caches" / "Spotify",
     "Spotify cache"),
    (HOME / "Library" / "Caches" / "ms-playwright",
     "Playwright cache (confirmado inativo)"),
    (HOME / "tmp-npm-cache",
     "Manual npm cache dir (~/tmp-npm-cache)"),
    (HOME / ".npm",
     "npm global cache (~/.npm)"),
    (HOME / ".cache" / "gstreamer-1.0",
     "GStreamer cache"),
    (HOME / ".cache" / "pre-commit",
     "pre-commit cache"),
    (HOME / "Library" / "Application Support" / "Claude" / "DawnGraphiteCache",
     "Claude GPU/Graphite cache"),
    (HOME / "Library" / "Application Support" / "Claude" / "DawnWebGPUCache",
     "Claude WebGPU cache"),
    (HOME / "Library" / "Application Support" / "Claude" / "GPUCache",
     "Claude GPU cache"),
]


def phase1_cleanup(dry_run: bool = True) -> None:
    """Phase 1: clean all safe cache/log/temp targets."""
    cprint(BOLD + BLUE, "\n══════════════════════════════════════════")
    cprint(BOLD + BLUE, " FASE 1 — LIMPEZA DE CACHES E TEMPORÁRIOS")
    cprint(BOLD + BLUE, "══════════════════════════════════════════")
    if dry_run:
        cprint(YELLOW, " MODO DRY-RUN — nenhuma alteração será feita\n")
    else:
        cprint(RED, " MODO EXECUÇÃO — arquivos serão DELETADOS permanentemente\n")

    total_freed = 0
    total_would_free = 0

    cprint(BOLD, "\n[1/2] Targets seguros (automáticos):")
    for path, description in SAFE_CLEANUP_TARGETS:
        if not path.exists():
            cprint(CYAN, f"  [SKIP] não existe: {path.name}")
            continue
        size = dir_size(path) if path.is_dir() else path.stat().st_size
        total_would_free += size
        freed = safe_remove(path, dry_run=dry_run)
        total_freed += freed

    cprint(BOLD, "\n[2/2] Homebrew cleanup:")
    brew_path = shutil.which("brew")
    if brew_path:
        brew_cache = HOME / "Library" / "Caches" / "Homebrew"
        size = dir_size(brew_cache)
        total_would_free += size
        if dry_run:
            cprint(YELLOW, f"  [DRY-RUN] executaria: brew cleanup --prune=all ({human_size(size)})")
        else:
            freed = 0
            if run_cmd([brew_path, "cleanup", "--prune=all"], dry_run=False, description="brew cleanup"):
                new_size = dir_size(brew_cache)
                freed = max(0, size - new_size)
            total_freed += freed
    else:
        cprint(CYAN, "  [SKIP] brew não encontrado no PATH")

    cprint(BOLD + GREEN, f"\n── RESUMO FASE 1 ──")
    if dry_run:
        cprint(GREEN, f"  Espaço que seria liberado: {human_size(total_would_free)}")
        cprint(YELLOW, "  Execute com --execute para aplicar as mudanças.")
    else:
        cprint(GREEN, f"  Espaço liberado: {human_size(total_freed)}")
    log(f"PHASE1 {'DRY-RUN' if dry_run else 'EXECUTE'} | freed={human_size(total_freed)} | would_free={human_size(total_would_free)}")


# ─────────────────────────────────────────────
# PHASE 2 — MIGRATION TO SERVIDOR AL
# ─────────────────────────────────────────────

MIGRATION_MAP = [
    (HOME / "Downloads" / "[MM][OF01][LD02][MLD05][OTMZ][PRECO][KIT03].mp4",
     SERVIDOR_AL / "AMS" / "VSL - GELATINA SLIM" / "[MM][OF01][LD02][MLD05][OTMZ][PRECO][KIT03].mp4",
     True),
    (HOME / "Downloads" / "[NE][OF03][LD01][OTMZ][PREÇO][KIT03].mp4",
     SERVIDOR_AL / "AMS" / "VSL - GELATINA FIT" / "[NE][OF03][LD01][OTMZ][PREÇO][KIT03].mp4",
     True),
    (HOME / "Downloads" / "[NE][OF03][LD02][OTMZ][PREÇO][KIT03].mp4",
     SERVIDOR_AL / "AMS" / "VSL - GELATINA FIT" / "[NE][OF03][LD02][OTMZ][PREÇO][KIT03].mp4",
     True),
    (HOME / "Downloads" / "ssstwitter.com_1778781524816.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "GUARDAR" / "ssstwitter.com_1778781524816.mp4",
     True),
    (HOME / "Movies" / "frieren-eternity.3840x2160.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "WALLPAPERS 4K" / "frieren-eternity.3840x2160.mp4",
     True),
    (HOME / "Movies" / "gojo-hollow-purple.3840x2160.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "WALLPAPERS 4K" / "gojo-hollow-purple.3840x2160.mp4",
     True),
    (HOME / "Movies" / "gojo-purple-hollow-technique.3840x2160.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "WALLPAPERS 4K" / "gojo-purple-hollow-technique.3840x2160.mp4",
     True),
    (HOME / "Movies" / "gojo-satoru-hollow-grace.3840x2160.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "WALLPAPERS 4K" / "gojo-satoru-hollow-grace.3840x2160.mp4",
     True),
    (HOME / "Movies" / "madara-uchiha-naruto.3840x2160.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "WALLPAPERS 4K" / "madara-uchiha-naruto.3840x2160.mp4",
     True),
    (HOME / "Movies" / "ryomen-sukuna-sorcerer.3840x2160.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "WALLPAPERS 4K" / "ryomen-sukuna-sorcerer.3840x2160.mp4",
     True),
    (HOME / "Movies" / "tomioka-giyu-frozen-silence.3840x2160.mp4",
     SERVIDOR_AL / "DOWNLOADS MAC" / "WALLPAPERS 4K" / "tomioka-giyu-frozen-silence.3840x2160.mp4",
     True),
]


def verify_volume(volume: Path, name: str) -> bool:
    """Return True if volume is mounted and writable."""
    if not volume.exists():
        cprint(RED, f"  [ERRO] Volume '{name}' não está montado em {volume}")
        cprint(YELLOW, f"  Conecte o HD externo e tente novamente.")
        return False
    test_file = volume / ".mac_storage_manager_test"
    try:
        test_file.touch()
        test_file.unlink()
        return True
    except OSError as e:
        cprint(RED, f"  [ERRO] Volume '{name}' não está acessível para escrita: {e}")
        return False


def phase2_migrate(dry_run: bool = True) -> None:
    """Phase 2: copy large files to Servidor AL, then delete from SSD."""
    cprint(BOLD + BLUE, "\n══════════════════════════════════════════")
    cprint(BOLD + BLUE, " FASE 2 — MIGRAÇÃO PARA SERVIDOR AL")
    cprint(BOLD + BLUE, "══════════════════════════════════════════")
    if dry_run:
        cprint(YELLOW, " MODO DRY-RUN — nenhuma cópia ou deleção será feita\n")
    else:
        cprint(RED, " MODO EXECUÇÃO — arquivos serão copiados e depois DELETADOS do SSD\n")

    if not verify_volume(SERVIDOR_AL, "Servidor AL"):
        cprint(RED, "Abortando Fase 2 — volume não disponível.")
        return

    total_copied = 0
    total_would_copy = 0
    deleted_from_ssd = 0
    errors = 0

    for src, dst, delete_after in MIGRATION_MAP:
        if not src.exists():
            cprint(CYAN, f"  [SKIP] não existe: {src.name}")
            continue

        size = src.stat().st_size if src.is_file() else dir_size(src)
        total_would_copy += size

        copied = safe_copy(src, dst, dry_run=dry_run)

        if not dry_run and copied > 0:
            total_copied += copied
            if dst.exists():
                dst_size = dst.stat().st_size if dst.is_file() else dir_size(dst)
                if dst_size >= size * 0.99:
                    if delete_after:
                        freed = safe_remove(src, dry_run=False)
                        deleted_from_ssd += freed
                else:
                    cprint(RED, f"  [AVISO] tamanho no destino ({human_size(dst_size)}) diferente da origem ({human_size(size)}) — NÃO deletando origem")
                    errors += 1
            else:
                cprint(RED, f"  [AVISO] destino não encontrado após cópia — NÃO deletando origem")
                errors += 1

    cprint(BOLD + GREEN, f"\n── RESUMO FASE 2 ──")
    if dry_run:
        cprint(GREEN, f"  Espaço que seria liberado do SSD: {human_size(total_would_copy)}")
        cprint(YELLOW, "  Execute com --execute para aplicar as migrações.")
    else:
        cprint(GREEN, f"  Arquivos copiados: {human_size(total_copied)}")
        cprint(GREEN, f"  Espaço liberado do SSD: {human_size(deleted_from_ssd)}")
        if errors:
            cprint(RED, f"  Erros de verificação: {errors} (origens preservadas)")
    log(f"PHASE2 {'DRY-RUN' if dry_run else 'EXECUTE'} | copied={human_size(total_copied)} | ssd_freed={human_size(deleted_from_ssd)} | errors={errors}")


# ─────────────────────────────────────────────
# PHASE 3 — CRONTAB AUTOMATION
# ─────────────────────────────────────────────

CRON_MARKER = "# mac_storage_manager weekly cleanup"
CRON_LINE = (
    "0 3 * * 0 "
    f"/usr/bin/python3 {HOME}/Scripts/mac_storage_manager.py "
    "--phase 1 --execute "
    f">> {HOME}/Scripts/logs/mac_storage_manager.log 2>&1"
)


def phase3_automate(dry_run: bool = True) -> None:
    """Phase 3: install weekly crontab entry for automatic cleanup."""
    cprint(BOLD + BLUE, "\n══════════════════════════════════════════")
    cprint(BOLD + BLUE, " FASE 3 — AUTOMAÇÃO SEMANAL (CRONTAB)")
    cprint(BOLD + BLUE, "══════════════════════════════════════════")

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = result.stdout if result.returncode == 0 else ""

    if CRON_MARKER in current:
        cprint(GREEN, "  [OK] Crontab já configurado (entrada existente):")
        for line in current.splitlines():
            if CRON_MARKER in line or "mac_storage_manager" in line:
                cprint(CYAN, f"    {line}")
        return

    new_entry = f"\n{CRON_MARKER}\n{CRON_LINE}\n"

    if dry_run:
        cprint(YELLOW, "  [DRY-RUN] adicionaria ao crontab:")
        cprint(CYAN, f"    {CRON_LINE}")
        cprint(YELLOW, "  Horário: domingo às 03:00 (Fase 1 apenas — sem migração)")
        return

    new_crontab = current.rstrip() + new_entry
    proc = subprocess.run(
        ["crontab", "-"],
        input=new_crontab,
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        cprint(GREEN, "  [OK] Crontab instalado com sucesso:")
        cprint(CYAN, f"    {CRON_LINE}")
        log(f"PHASE3 CRONTAB INSTALLED: {CRON_LINE}")
    else:
        cprint(RED, f"  [ERRO] Falha ao instalar crontab: {proc.stderr.strip()}")
        log(f"PHASE3 CRONTAB ERROR: {proc.stderr.strip()}")


# ─────────────────────────────────────────────
# REPORT — disk usage snapshot
# ─────────────────────────────────────────────

REPORT_TARGETS = [
    (HOME / "Library" / "Caches" / "Google" / "Chrome",          "Chrome Caches"),
    (HOME / "Library" / "Application Support" / "Notion",         "Notion AppSupport"),
    (HOME / "Library" / "Caches" / "ms-playwright",               "Playwright cache"),
    (HOME / "Library" / "Caches" / "Comet",                       "Comet cache"),
    (HOME / "Library" / "Caches" / "Spotify",                     "Spotify cache"),
    (HOME / "Library" / "Caches" / "colima",                      "Colima cache"),
    (HOME / "Library" / "Caches" / "@granolaelectron-updater",    "Granola cache"),
    (HOME / "Library" / "Caches" / "pip",                         "pip cache"),
    (HOME / "Library" / "Caches" / "Homebrew",                    "Homebrew cache"),
    (HOME / ".npm",                                                "npm cache"),
    (HOME / "tmp-npm-cache",                                       "tmp-npm-cache"),
    (HOME / "Library" / "Logs" / "CreativeCloud",                 "CreativeCloud logs"),
    (HOME / "Movies" / "CacheClip",                               "CacheClip"),
    (HOME / ".cache" / "whisper",                                  "Whisper models (PRESERVADO)"),
    (HOME / "Library" / "Application Support" / "Claude" / "vm_bundles", "Claude VM bundles (NÃO TOCAR)"),
    (HOME / "Downloads",                                           "Downloads"),
    (HOME / "Library" / "Application Support" / "Google" / "Chrome", "Chrome AppSupport (NÃO TOCAR)"),
    (HOME / "Library" / "Group Containers" / "group.net.whatsapp.WhatsApp.shared", "WhatsApp data (NÃO TOCAR)"),
]


def print_report() -> None:
    """Print current disk usage for all tracked paths."""
    cprint(BOLD + BLUE, "\n══════════════════════════════════════════")
    cprint(BOLD + BLUE, " RELATÓRIO DE USO DE DISCO")
    cprint(BOLD + BLUE, "══════════════════════════════════════════\n")

    stat = shutil.disk_usage("/")
    cprint(BOLD, f"SSD interno:  {human_size(stat.used)} usado / {human_size(stat.total)} total ({human_size(stat.free)} livre)")

    for vol, label in [(SERVIDOR_AL, "Servidor AL"), (SAMSUNG_USB, "Samsung USB")]:
        if vol.exists():
            s = shutil.disk_usage(str(vol))
            cprint(BOLD, f"{label}:  {human_size(s.used)} usado / {human_size(s.total)} total ({human_size(s.free)} livre)")

    cprint(BOLD, "\nTop consumidores rastreados:\n")
    rows = []
    for path, label in REPORT_TARGETS:
        if path.exists():
            size = dir_size(path)
            rows.append((size, label, path))

    rows.sort(reverse=True)
    for size, label, path in rows:
        bar_len = min(40, int(size / (1024**3) * 10))
        bar = "█" * bar_len
        color = RED if size > 1_000_000_000 else (YELLOW if size > 200_000_000 else GREEN)
        print(f"  {color}{human_size(size):>8}{RESET}  {label:<45}  {color}{bar}{RESET}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mac Storage Manager — limpeza, migração e automação de disco",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 mac_storage_manager.py --report
  python3 mac_storage_manager.py --phase 1
  python3 mac_storage_manager.py --phase 1 --execute
  python3 mac_storage_manager.py --phase 2 --execute
  python3 mac_storage_manager.py --phase 3 --execute
  python3 mac_storage_manager.py --all --execute
        """
    )
    parser.add_argument(
        "--phase", type=int, choices=[1, 2, 3],
        help="Executar uma fase específica (1=limpeza, 2=migração, 3=automação)"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Executar todas as fases em sequência"
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Aplicar mudanças reais (padrão: dry-run)"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Exibir relatório de uso de disco e sair"
    )

    args = parser.parse_args()

    dry_run = not args.execute

    if not any([args.phase, args.all, args.report]):
        parser.print_help()
        sys.exit(0)

    if args.report:
        print_report()
        return

    cprint(BOLD + CYAN, f"\n{'='*50}")
    cprint(BOLD + CYAN, f"  MAC STORAGE MANAGER  —  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    cprint(BOLD + CYAN, f"  Modo: {'EXECUÇÃO REAL' if args.execute else 'DRY-RUN (simulação)'}")
    cprint(BOLD + CYAN, f"{'='*50}")

    log(f"=== STARTED {'DRY-RUN' if dry_run else 'EXECUTE'} phase={args.phase or 'ALL'} ===")

    if args.all or args.phase == 1:
        phase1_cleanup(dry_run=dry_run)

    if args.all or args.phase == 2:
        phase2_migrate(dry_run=dry_run)

    if args.all or args.phase == 3:
        phase3_automate(dry_run=dry_run)

    cprint(BOLD + GREEN, f"\n{'='*50}")
    cprint(BOLD + GREEN, f"  Concluído. Log: {LOG_FILE}")
    cprint(BOLD + GREEN, f"{'='*50}\n")
    log("=== FINISHED ===")


if __name__ == "__main__":
    main()
