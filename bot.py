import asyncio
import logging
import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from binance_client import BinanceClient, BinanceAPIError
import config

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def format_latest_deposit(deposit: dict) -> str:
    """Format deposit dictionary into a clean, premium visual design."""
    coin = deposit.get("coin", "").upper()
    raw_amount = deposit.get("amount", "0")
    
    # Format amount to remove trailing zero digits for cleaner visual representation
    try:
        amount = f"{float(raw_amount):.8f}".rstrip('0').rstrip('.')
    except ValueError:
        amount = raw_amount

    network = deposit.get("network", "N/A")
    
    # Format insertTime (in milliseconds since epoch) to: "19 May 2026, 8:30 PM"
    insert_time_ms = deposit.get("insertTime", 0)
    try:
        dt = datetime.datetime.fromtimestamp(insert_time_ms / 1000.0, tz=datetime.timezone.utc)
        formatted_time = dt.strftime("%d %B %Y, %I:%M %p")
    except Exception:
        formatted_time = "N/A"
        
    tx_id = deposit.get("txId", "").strip()
    reference = tx_id if tx_id else "Internal Transfer"

    return (
        f"Latest deposit confirmed ✅\n\n"
        f"Amount: {amount} {coin}\n"
        f"Network: {network}\n"
        f"Time: {formatted_time} (UTC)\n"
        f"Reference: {reference}"
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command by sending a greeting message to authorized groups."""
    chat = update.effective_chat
    if not chat:
        return

    # Restrict to configured group ID if present
    if config.ALLOWED_GROUP_ID and chat.id != config.ALLOWED_GROUP_ID:
        return

    welcome_text = (
        "🤖 *Binance Deposit Monitor Bot* is active!\n\n"
        "I will help check the status of your deposits. "
        "Simply send `/check` in this group to fetch the latest confirmed Binance deposit.\n\n"
        "🔒 *Security Information*:\n"
        "• The associated Binance API Key has read-only permission.\n"
        "• Withdrawal and trading permissions are disabled."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /check command: retrieve history, filter confirmed, pick latest, and reply."""
    chat = update.effective_chat
    if not chat:
        return

    # Check optional ALLOWED_GROUP_ID restriction
    if config.ALLOWED_GROUP_ID and chat.id != config.ALLOWED_GROUP_ID:
        logger.warning(f"Ignored /check command executed in unauthorized Chat ID: {chat.id}")
        return

    # Reply with a temporary processing indicator
    status_message = await update.message.reply_text("🔄 Checking Binance deposits...")

    try:
        # Offload the blocking requests network call to a worker thread using asyncio.to_thread
        client = BinanceClient()
        
        # Query 20 recent deposits to ensure we find the latest confirmed one
        deposits = await asyncio.to_thread(client.get_deposit_history, limit=20)
        
        # Filter for confirmed deposits only (status == 1 corresponds to "Success")
        confirmed = [d for d in deposits if d.get("status") == 1]
        
        if not confirmed:
            await status_message.edit_text("No deposits arrived yet")
        else:
            # Pick the single latest confirmed deposit based on insertTime
            latest = max(confirmed, key=lambda d: d.get("insertTime", 0))
            reply_text = format_latest_deposit(latest)
            await status_message.edit_text(reply_text)
            
    except BinanceAPIError as e:
        logger.error(f"Binance API error in /check command: {e}")
        # Build user-friendly explanation of error details
        error_explanation = e.binance_msg if e.binance_msg else "Connection timed out or returned invalid status."
        await status_message.edit_text(
            f"⚠️ *Binance API Error*\n"
            f"Failed to fetch deposit history.\n\n"
            f"*Details:* {error_explanation}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Unexpected exception in /check command: {e}", exc_info=True)
        await status_message.edit_text(
            "⚠️ *System Error*\n"
            "An unexpected error occurred while processing the deposit check. Please check the logs.",
            parse_mode="Markdown"
        )


def main():
    logger.info("Initializing bot setup...")
    
    # Initialize the python-telegram-bot application with token
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("check", check_command))
    
    # Start polling for Telegram events
    logger.info("Bot is polling. Press Ctrl+C to terminate.")
    app.run_polling()


if __name__ == '__main__':
    main()
