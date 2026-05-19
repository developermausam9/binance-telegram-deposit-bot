import os
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


def normalize_blockchain_deposit(d: dict) -> dict:
    """Normalize a standard blockchain deposit object to a unified schema."""
    return {
        "type": "blockchain",
        "amount": d.get("amount", "0"),
        "coin": d.get("coin", "").upper(),
        "network": d.get("network", "N/A"),
        "time": int(d.get("insertTime", 0)),
        "tx_id": d.get("txId", "").strip(),
        "sender": None
    }


def normalize_pay_transaction(p: dict) -> dict:
    """Normalize a Binance Pay transaction object to a unified schema."""
    payer_name = p.get("payerInfo", {}).get("name") if p.get("payerInfo") else None
    note = p.get("note", "").strip()
    sender = note if note else payer_name
    return {
        "type": "pay",
        "amount": p.get("amount", "0"),
        "coin": p.get("currency", "").upper(),
        "network": "Binance Pay",
        "time": int(p.get("transactionTime", 0)),
        "tx_id": p.get("transactionId", "").strip(),
        "sender": sender
    }


def format_latest_deposit(deposit: dict) -> str:
    """Format normalized deposit/pay dictionary into a clean, premium visual design."""
    coin = deposit.get("coin", "").upper()
    raw_amount = deposit.get("amount", "0")
    
    # Format amount to remove trailing zero digits for cleaner visual representation
    try:
        amount = f"{float(raw_amount):.8f}".rstrip('0').rstrip('.')
    except ValueError:
        amount = raw_amount

    network = deposit.get("network", "N/A")
    
    # Format time (in milliseconds since epoch) to: "19 May 2026, 8:30 PM"
    time_ms = deposit.get("time", 0)
    try:
        dt = datetime.datetime.fromtimestamp(time_ms / 1000.0, tz=datetime.timezone.utc)
        formatted_time = dt.strftime("%d %B %Y, %I:%M %p")
    except Exception:
        formatted_time = "N/A"
        
    tx_id = deposit.get("tx_id", "")
    dep_type = deposit.get("type", "blockchain")
    sender = deposit.get("sender")

    if dep_type == "pay":
        reference_str = f"Transaction ID: {tx_id}" if tx_id else "Internal Transfer"
        sender_str = f"\nFrom: {sender}" if sender else ""
        return (
            f"Latest deposit confirmed ✅\n\n"
            f"Type: Binance Pay 💳\n"
            f"Amount: {amount} {coin}\n"
            f"Time: {formatted_time} (UTC){sender_str}\n"
            f"Reference: {reference_str}"
        )
    else:
        reference = tx_id if tx_id else "Internal Transfer"
        return (
            f"Latest deposit confirmed ✅\n\n"
            f"Type: Blockchain Deposit ⛓\n"
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
    """Handle /check command: retrieve blockchain and pay histories, merge, and reply."""
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
        
        # Query 20 recent records from both endpoints in parallel to keep things extremely fast
        blockchain_task = asyncio.to_thread(client.get_deposit_history, limit=20)
        pay_task = asyncio.to_thread(client.get_pay_history, limit=20)
        
        blockchain_raw, pay_raw = await asyncio.gather(
            blockchain_task, 
            pay_task, 
            return_exceptions=True
        )

        # Handle blockchain results (propagate error if both fail, otherwise log and fall back)
        blockchain_deposits = []
        if isinstance(blockchain_raw, Exception):
            logger.error(f"Error fetching blockchain deposits: {blockchain_raw}")
            if isinstance(pay_raw, Exception):
                raise blockchain_raw  # Both failed, propagate the main exception
        else:
            blockchain_deposits = blockchain_raw

        # Handle Pay results
        pay_transactions = []
        if isinstance(pay_raw, Exception):
            logger.error(f"Error fetching Binance Pay transactions: {pay_raw}")
        else:
            pay_transactions = pay_raw

        # Normalize and filter blockchain deposits (status == 1 corresponds to "Success")
        normalized_blockchain = [
            normalize_blockchain_deposit(d)
            for d in blockchain_deposits
            if d.get("status") == 1
        ]

        # Normalize pay transactions
        normalized_pay = [
            normalize_pay_transaction(p)
            for p in pay_transactions
        ]

        # Merge and pick the absolute latest one
        all_deposits = normalized_blockchain + normalized_pay

        if not all_deposits:
            await status_message.edit_text("No deposits arrived yet")
        else:
            latest = max(all_deposits, key=lambda d: d.get("time", 0))
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
    
    # Detect if we are running in a Render Web Service environment
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    port_str = os.getenv("PORT")
    
    if render_url:
        logger.info(f"Render Web Service environment detected. Starting in WEBHOOK mode at {render_url}...")
        port = int(port_str) if port_str else 8080
        # Start webhook listener
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=config.TELEGRAM_BOT_TOKEN,
            webhook_url=f"{render_url}/{config.TELEGRAM_BOT_TOKEN}"
        )
    else:
        logger.info("Local environment detected. Starting in POLLING mode...")
        # Start polling for Telegram events locally
        app.run_polling()



if __name__ == '__main__':
    main()
