#!/usr/bin/env python3
"""
Telegram Bot — Iago & Claude
Bot pessoal 24/7 para conversar via Telegram.
Backend: Gemini 2.5 Flash | Áudio: Whisper local (offline, grátis)
"""

import os
import sys
import json
import logging
import tempfile
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from google import genai

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ENV_PATH = Path(__file__).parent / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_CLAUDE_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ALLOWED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "5883974795"))

DATA_DIR = Path(__file__).parent / "data"
HISTORY_FILE = DATA_DIR / "claude_bot_history.json"
LOG_FILE = DATA_DIR / "claude_bot.log"

MODEL = "gemini-2.5-flash"
MAX_HISTORY = 40  # pares de mensagens

# Obsidian
OBSIDIAN_VAULT = Path.home() / "Obsidian" / "IMPERA"
OBSIDIAN_DAILY = OBSIDIAN_VAULT / "Daily Notes"

SYSTEM_PROMPT = """Você é o assistente pessoal do Iago de Almeida Ribeiro Rodrigues.

Contexto sobre o Iago:
- Gestor de processos na IMPERA Produtos Naturais (equipe de copywriters e editores de vídeo)
- Pai (filha nasceu 16/03/2026)
- Objetivo de médio prazo: sair do Brasil e morar no exterior (Japão/Canadá/Paraguai)
- Interesses: gestão de processos, performance marketing, operação criativa, tecnologia, investimentos
- Está construindo um SaaS (Creative Brief Generator) nas horas vagas
- Estuda japonês
- Tem uma empresa de editores freelancer (Spaciarios)

Suas diretrizes:
- Responda em português brasileiro
- Seja direto, prático e empático
- Tom de parceiro/amigo — não formal demais
- Quando ele compartilhar ideias, ajude a desenvolver e questione construtivamente
- Ajude com organização pessoal, metas, produtividade, saúde, finanças, carreira
- Se ele mandar áudio transcrito, responda naturalmente (ignore artefatos de transcrição)
- Respostas concisas — não se estenda demais a menos que ele peça
- Lembre do contexto da conversa
"""

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------


def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            return []
    return []


def save_history(history: list):
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2))


def trim_history(history: list) -> list:
    if len(history) > MAX_HISTORY * 2:
        history = history[-(MAX_HISTORY * 2) :]
    return history


# ---------------------------------------------------------------------------
# Obsidian — salva conversas na Daily Note
# ---------------------------------------------------------------------------

BRT = timezone(timedelta(hours=-3))


def obsidian_log(user_msg: str, bot_response: str, voice: bool = False):
    """Append conversa na Daily Note do Obsidian."""
    try:
        now = datetime.now(BRT)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        daily_path = OBSIDIAN_DAILY / f"{date_str}.md"

        # Prefixo para indicar se foi voz ou texto
        prefix = "🎤" if voice else "💬"

        # Bloco da conversa
        entry = (
            f"\n**{time_str}** {prefix} **Iago:**\n"
            f"{user_msg}\n\n"
            f"**{time_str}** 🤖 **Bot:**\n"
            f"{bot_response}\n\n---\n"
        )

        if daily_path.exists():
            content = daily_path.read_text()
            # Se já tem seção Telegram Bot, append nela
            if "## Telegram Bot" in content:
                content = content.rstrip() + "\n" + entry
            else:
                # Cria a seção no final
                content = content.rstrip() + "\n\n## Telegram Bot\n" + entry
            daily_path.write_text(content)
        else:
            # Cria daily note nova com frontmatter
            day_name = now.strftime("%A")
            frontmatter = (
                f"---\ntipo: daily\ndata: {date_str}\n"
                f"dia_semana: {day_name}\ntags: [daily, telegram]\n---\n\n"
                f"# {now.strftime('%d/%m/%Y')} — {day_name}\n\n"
                f"## Telegram Bot\n{entry}"
            )
            daily_path.write_text(frontmatter)

        logger.info(f"Obsidian: salvo em {daily_path.name}")
    except Exception as e:
        logger.error(f"Obsidian error: {e}")


# ---------------------------------------------------------------------------
# Gemini API
# ---------------------------------------------------------------------------

gemini_client = genai.Client(api_key=GEMINI_API_KEY)


def history_to_gemini_contents(history: list) -> list:
    """Converte histórico interno para formato Gemini contents."""
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    return contents


def ask_llm(user_message: str, history: list) -> str:
    """Envia mensagem para Gemini e retorna a resposta."""
    history.append({"role": "user", "content": user_message})
    history = trim_history(history)

    try:
        contents = history_to_gemini_contents(history)
        response = gemini_client.models.generate_content(
            model=MODEL,
            contents=contents,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "max_output_tokens": 4096,
            },
        )
        assistant_msg = response.text
        history.append({"role": "assistant", "content": assistant_msg})
        save_history(history)
        return assistant_msg
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        history.pop()
        return f"Erro ao consultar Gemini: {e}"


# ---------------------------------------------------------------------------
# Whisper local (offline, grátis)
# ---------------------------------------------------------------------------

whisper_model = None


def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        import whisper

        logger.info("Carregando modelo Whisper (base)...")
        whisper_model = whisper.load_model("base")
        logger.info("Whisper pronto.")
    return whisper_model


def transcribe_audio(file_path: str) -> str:
    """Transcreve áudio usando Whisper local."""
    try:
        model = get_whisper_model()
        result = model.transcribe(file_path, language="pt")
        return result["text"].strip()
    except Exception as e:
        logger.error(f"Whisper error: {e}")
        return f"[Erro na transcrição: {e}]"


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------


def is_authorized(update: Update) -> bool:
    return update.effective_chat.id == ALLOWED_CHAT_ID


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await update.message.reply_text(
        "Fala, Iago! Tô online 24/7. Manda texto ou áudio que eu respondo. 🤙"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    save_history([])
    await update.message.reply_text("Histórico limpo. Conversa zerada!")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    history = load_history()
    brt = timezone(timedelta(hours=-3))
    now = datetime.now(brt).strftime("%d/%m/%Y %H:%M")
    msg = (
        f"📊 Status do Bot\n"
        f"Online: ✅\n"
        f"Hora: {now}\n"
        f"Mensagens no histórico: {len(history)}\n"
        f"Modelo: {MODEL}\n"
        f"Whisper: local (offline)"
    )
    await update.message.reply_text(msg)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    user_msg = update.message.text
    logger.info(f"Texto recebido: {user_msg[:80]}...")

    await update.message.chat.send_action("typing")

    history = load_history()
    response = ask_llm(user_msg, history)

    # Salva no Obsidian
    obsidian_log(user_msg, response, voice=False)

    if len(response) <= 4096:
        await update.message.reply_text(response)
    else:
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i : i + 4096])


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    await update.message.chat.send_action("typing")
    logger.info("Áudio recebido, transcrevendo...")

    voice = update.message.voice or update.message.audio
    if not voice:
        await update.message.reply_text("Não consegui processar esse áudio.")
        return

    file = await voice.get_file()

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

    try:
        transcription = transcribe_audio(tmp_path)
        logger.info(f"Transcrição: {transcription[:80]}...")

        if transcription.startswith("["):
            await update.message.reply_text(transcription)
            return

        # Envia pro LLM com contexto de áudio
        user_msg = f"[áudio transcrito]: {transcription}"
        history = load_history()
        response = ask_llm(user_msg, history)

        # Salva no Obsidian (mensagem original transcrita)
        obsidian_log(transcription, response, voice=True)

        reply = f"🎤 _{transcription}_\n\n{response}"
        if len(reply) <= 4096:
            await update.message.reply_text(reply)
        else:
            await update.message.reply_text(f"🎤 _{transcription}_")
            for i in range(0, len(response), 4096):
                await update.message.reply_text(response[i : i + 4096])
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_CLAUDE_TOKEN não configurado!")
        sys.exit(1)
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY não configurado!")
        sys.exit(1)

    logger.info(f"Iniciando bot Telegram (modelo: {MODEL})...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    logger.info("Bot online! Aguardando mensagens...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
