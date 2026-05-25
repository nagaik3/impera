"""
IMPERATOR Telegram Bot — Canal de comunicação com operações de investimento.

Responde perguntas sobre:
- Status dos bots (EXODUS, Genesis, Contrarian, Sentinel)
- P&L, trades recentes, posições abertas
- Bankroll e performance
- Análises e decisões estratégicas

Stack:
- python-telegram-bot (long polling)
- Google Gemini 2.5 Flash (raciocínio com contexto operacional)
- openai-whisper local (transcrição de áudio)
- Dados reais do EXODUS/Contrarian em ~/investimentos/polymarket-bot/data/
"""
import json
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from google import genai
from google.genai import types

# ================================================================
# CONFIG
# ================================================================

load_dotenv(os.path.expanduser("~/Scripts/.env"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_GEMINI_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ALLOWED_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))

# Paths
DATA_DIR = os.path.expanduser("~/Scripts/data")
HISTORY_FILE = os.path.join(DATA_DIR, "gemini_bot_history.json")
LOG_FILE = os.path.join(DATA_DIR, "gemini_bot.log")
OBSIDIAN_DAILY = os.path.expanduser("~/Obsidian/IMPERA/Daily Notes")

# EXODUS data
EXODUS_DIR = os.path.expanduser("~/investimentos/polymarket-bot")
EXODUS_TRADES = os.path.join(EXODUS_DIR, "data", "trades.json")
CONTRARIAN_TRADES = os.path.join(EXODUS_DIR, "data", "contrarian_trades.json")
CONTRARIAN_STATE = os.path.join(EXODUS_DIR, "data", "contrarian_state.json")

MAX_HISTORY = 40
WHISPER_MODEL_NAME = "base"
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """Você é IMPERATOR — o agente central de operações de investimento do Iago.

Seu papel:
- Reportar status das operações (EXODUS, Contrarian Engine, Genesis, Sentinel)
- Analisar P&L, trades, posições abertas
- Dar insights estratégicos baseados em dados reais
- Ser direto, conciso, usar tabelas quando faz sentido
- Português brasileiro, tom de parceiro/operador

Contexto operacional:
- Plataforma: Polymarket (mercados de previsão crypto Up/Down)
- EXODUS v5.3: engine principal, DOGE + BTC live, demais shadow
- Contrarian Engine v1.0: compra DOWN quando UP >= 85c (R/R 7-8:1)
- Bankroll atual em USDC na Polymarket
- Meta: US$1-2K/mês renda passiva

Quando o usuário perguntar sobre status/dados, você receberá um bloco [DADOS OPERACIONAIS]
com informações em tempo real. Use esses dados para responder com precisão.

Regras:
- Nunca inventar números — use apenas os dados fornecidos
- Se não tem dados suficientes, diga
- Sugira ações quando relevante
- Alerte sobre riscos ou anomalias
"""

# ================================================================
# LOGGING
# ================================================================

os.makedirs(DATA_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("imperator_tg")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ================================================================
# GEMINI CLIENT
# ================================================================

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ================================================================
# WHISPER (lazy load)
# ================================================================

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        logger.info(f"Loading Whisper model '{WHISPER_MODEL_NAME}'...")
        _whisper_model = whisper.load_model(WHISPER_MODEL_NAME)
        logger.info("Whisper model loaded.")
    return _whisper_model


def transcribe_audio(file_path: str) -> str:
    wmodel = get_whisper_model()
    result = wmodel.transcribe(file_path, language="pt")
    return result.get("text", "").strip()


# ================================================================
# OPERATIONAL DATA GATHERING
# ================================================================


def get_operational_context() -> str:
    """Gather real-time operational data for Gemini context."""
    sections = []

    # 1. Bot processes status
    try:
        ps = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=5)
        lines = ps.stdout.split("\n")
        bots = {}
        for line in lines:
            if "engine.py" in line and "grep" not in line:
                bots["EXODUS Engine"] = "RUNNING"
            if "genesis_engine" in line and "grep" not in line:
                bots["Genesis Engine"] = "RUNNING"
            if "genesis_aggressive" in line and "grep" not in line:
                bots["Genesis Aggressive"] = "RUNNING"
            if "sentinel_scanner" in line and "grep" not in line:
                bots["Sentinel"] = "RUNNING"
            if "contrarian_engine" in line and "grep" not in line:
                bots["Contrarian Engine"] = "RUNNING"

        status_lines = [f"  {k}: {v}" for k, v in bots.items()]
        sections.append("BOTS:\n" + "\n".join(status_lines) if status_lines else "BOTS: nenhum rodando")
    except Exception as e:
        sections.append(f"BOTS: erro ao verificar ({e})")

    # 2. EXODUS trades & P&L
    try:
        with open(EXODUS_TRADES, "r") as f:
            trades = json.load(f)

        now = time.time()
        exits = [t for t in trades if "EXIT" in t.get("action", "")]
        wins = [t for t in exits if t.get("pnl", 0) > 0]
        losses = [t for t in exits if t.get("pnl", 0) < 0]
        total_pnl = sum(t.get("pnl", 0) for t in exits)

        # Last 7 days
        week = [t for t in exits if t.get("timestamp", 0) > now - 7 * 86400]
        week_pnl = sum(t.get("pnl", 0) for t in week)

        # Today
        today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        today = [t for t in exits if t.get("timestamp", 0) > today_start]
        today_pnl = sum(t.get("pnl", 0) for t in today)

        # Last 5 trades
        recent = sorted(exits, key=lambda x: x.get("timestamp", 0))[-5:]
        recent_lines = []
        for t in recent:
            dt = datetime.fromtimestamp(t["timestamp"]).strftime("%m/%d %H:%M")
            pnl = t.get("pnl", 0)
            q = t.get("market_question", "?")[:35]
            recent_lines.append(f"  {dt} | ${pnl:+.2f} | {q}")

        wr = len(wins) / len(exits) * 100 if exits else 0
        sections.append(
            f"EXODUS P&L:\n"
            f"  Total: {len(exits)} trades | WR: {wr:.1f}% | P&L total: ${total_pnl:.2f}\n"
            f"  7 dias: {len(week)} trades | P&L: ${week_pnl:.2f}\n"
            f"  Hoje: {len(today)} trades | P&L: ${today_pnl:.2f}\n"
            f"  Últimos trades:\n" + "\n".join(recent_lines)
        )
    except Exception as e:
        sections.append(f"EXODUS: erro ao ler trades ({e})")

    # 3. Contrarian Engine
    try:
        with open(CONTRARIAN_STATE, "r") as f:
            state = json.load(f)
        positions = state.get("positions", [])

        with open(CONTRARIAN_TRADES, "r") as f:
            ct = json.load(f)
        entries = [t for t in ct if t.get("action") == "CONTRARIAN_ENTRY"]
        exits_c = [t for t in ct if "EXIT" in t.get("action", "")]
        c_pnl = sum(t.get("pnl", 0) for t in exits_c)

        pos_lines = []
        for p in positions:
            pos_lines.append(
                f"  {p.get('asset','?')} DOWN @ {p.get('entry_price',0)*100:.1f}c "
                f"(UP={p.get('up_price_at_entry',0)*100:.0f}c) | "
                f"R/R {p.get('rr_ratio',0):.1f}:1 | cost=${p.get('cost',0):.2f}"
            )

        sections.append(
            f"CONTRARIAN ENGINE:\n"
            f"  Entries: {len(entries)} | Exits: {len(exits_c)} | P&L: ${c_pnl:.2f}\n"
            f"  Posições abertas: {len(positions)}\n"
            + ("\n".join(pos_lines) if pos_lines else "  (nenhuma)")
        )
    except FileNotFoundError:
        sections.append("CONTRARIAN ENGINE: sem dados ainda")
    except Exception as e:
        sections.append(f"CONTRARIAN ENGINE: erro ({e})")

    # 4. Bankroll (from PortfolioSync logs)
    try:
        log_path = os.path.join(EXODUS_DIR, "logs", "bot.log")
        result = subprocess.run(
            ["grep", "PortfolioSync OK", log_path],
            capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n")
        if lines and lines[-1]:
            last = lines[-1]
            # Extract dollar amount
            import re
            match = re.search(r'\$([0-9.]+)', last)
            if match:
                sections.append(f"BANKROLL: ${match.group(1)} USDC")
    except Exception:
        pass

    # 5. Engine log (last activity)
    try:
        log_path = os.path.join(EXODUS_DIR, "logs", "bot.log")
        result = subprocess.run(
            ["tail", "-5", log_path],
            capture_output=True, text=True, timeout=5)
        sections.append(f"ENGINE LOG (últimas linhas):\n{result.stdout.strip()}")
    except Exception:
        pass

    return "\n\n".join(sections)


# ================================================================
# HISTORY
# ================================================================


def load_history() -> list:
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(history: list):
    trimmed = history[-MAX_HISTORY:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def history_to_gemini_contents(history: list) -> list:
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
    return contents


# ================================================================
# OBSIDIAN
# ================================================================


def append_to_daily_note(speaker: str, content: str):
    today = datetime.now().strftime("%Y-%m-%d")
    note_path = os.path.join(OBSIDIAN_DAILY, f"{today}.md")
    now_str = datetime.now().strftime("%H:%M")

    section_header = "## IMPERATOR Telegram"
    entry = f"- **{now_str}** [{speaker}]: {content}\n"

    if os.path.exists(note_path):
        with open(note_path, "r") as f:
            existing = f.read()
    else:
        existing = f"# {today}\n\n"

    if section_header not in existing:
        existing = existing.rstrip() + f"\n\n{section_header}\n\n"

    existing = existing.rstrip() + "\n" + entry

    os.makedirs(os.path.dirname(note_path), exist_ok=True)
    with open(note_path, "w") as f:
        f.write(existing)


# ================================================================
# GEMINI CALL
# ================================================================


def ask_gemini(user_message: str, history: list) -> str:
    """Send message to Gemini with operational context."""
    # Gather real-time data
    ops_context = get_operational_context()

    # Prepend operational data to user message
    enriched_message = (
        f"[DADOS OPERACIONAIS em {datetime.now().strftime('%Y-%m-%d %H:%M')}]\n"
        f"{ops_context}\n\n"
        f"[MENSAGEM DO IAGO]\n{user_message}"
    )

    contents = history_to_gemini_contents(history)
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=enriched_message)]))

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"Erro ao consultar Gemini: {e}"


# ================================================================
# HANDLERS
# ================================================================


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    await update.message.reply_text(
        "IMPERATOR online. Pergunte sobre status, P&L, trades, ou qualquer coisa das operações."
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    save_history([])
    await update.message.reply_text("Histórico limpo.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return
    ops = get_operational_context()
    # Truncate if too long for Telegram
    if len(ops) > 4000:
        ops = ops[:4000] + "\n..."
    await update.message.reply_text(f"📊 IMPERATOR STATUS\n\n{ops}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    user_msg = update.message.text
    if not user_msg:
        return

    logger.info(f"Iago: {user_msg[:80]}")

    history = load_history()
    response = ask_gemini(user_msg, history)

    # Save clean message to history (without ops data)
    history.append({"role": "user", "content": user_msg, "ts": time.time()})
    history.append({"role": "assistant", "content": response, "ts": time.time()})
    save_history(history)

    # Obsidian
    append_to_daily_note("Iago", user_msg)
    append_to_daily_note("IMPERATOR", response)

    # Telegram has 4096 char limit
    if len(response) > 4000:
        for i in range(0, len(response), 4000):
            await update.message.reply_text(response[i:i+4000])
    else:
        await update.message.reply_text(response)

    logger.info(f"Reply sent ({len(response)} chars)")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID:
        return

    logger.info("Voice message received")

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name

    await file.download_to_drive(tmp_path)

    try:
        transcription = transcribe_audio(tmp_path)
        logger.info(f"Transcription: {transcription[:80]}")

        if not transcription:
            await update.message.reply_text("Não consegui transcrever o áudio.")
            return

        history = load_history()
        response = ask_gemini(transcription, history)

        history.append({"role": "user", "content": f"[áudio] {transcription}", "ts": time.time()})
        history.append({"role": "assistant", "content": response, "ts": time.time()})
        save_history(history)

        append_to_daily_note("Iago (áudio)", transcription)
        append_to_daily_note("IMPERATOR", response)

        reply = f"🎤 {transcription}\n\n{response}"
        if len(reply) > 4000:
            await update.message.reply_text(f"🎤 {transcription}")
            await update.message.reply_text(response[:4000])
        else:
            await update.message.reply_text(reply)

    finally:
        os.unlink(tmp_path)


# ================================================================
# MAIN
# ================================================================


def main():
    logger.info("Starting IMPERATOR Telegram Bot...")

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_GEMINI_TOKEN not set")
        return
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set")
        return
    if not ALLOWED_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not set")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    logger.info(f"IMPERATOR Bot ready. Chat ID: {ALLOWED_CHAT_ID}")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
