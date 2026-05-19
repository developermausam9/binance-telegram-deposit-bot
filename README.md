# Binance Telegram Deposit Bot 🤖💰

A secure, light-weight, and production-ready Telegram bot built with `python-telegram-bot` (v20+) that checks and displays the single **latest confirmed deposit** from your Binance account inside a dedicated Telegram group. 

Requests are authenticated locally via `HMAC-SHA256` and require **read-only** API keys. No trading or withdrawal functionalities are included, and credentials are never sent to external servers.

---

## Key Features
- 🔄 **Latest-Only Mode**: The `/check` command scans your last 20 deposits and displays *only* the single latest confirmed deposit (`status == 1`) based on the deposit time (`insertTime`).
- 🔒 **Zero-Trust Security**: Never stores keys in code; uses strict environment configuration (`.env`). No withdrawal or trade logic is present.
- 👥 **Group Isolation**: Supports an optional `ALLOWED_GROUP_ID` system. If configured, the bot will silently ignore commands coming from any other user or group.
- 🧵 **Asynchronous Design**: Employs non-blocking event-loop mechanics (`asyncio.to_thread`) for API requests, ensuring absolute reliability.
- 🐳 **Cloud-Ready**: Prepared for immediate deployment to **Render**, **Railway**, or **VPS** with pre-configured `Procfile` and graceful crash handlers.

---

## Project Structure
```text
binance-telegram-deposit-bot/
├── bot.py               # Bot entry point and command router
├── binance_client.py    # Binance API client with HMAC SHA256 signing
├── config.py            # Environment variable loader & validator
├── requirements.txt     # Dependency definition file
├── .env.example         # Template for environment configuration
├── README.md            # Complete documentation
└── Procfile             # Process instruction for cloud hosting
```

---

## 🔒 Security Best Practices

> [!CAUTION]
> **API Key Permissions**: When creating the API Key in your Binance account, ensure that **only** the **"Enable Reading"** permission is ticked.
> - **DO NOT** enable "Enable Spot & Margin Trading".
> - **DO NOT** enable "Enable Withdrawals". The bot does not have withdrawal logic and will fail if the secret key is compromised, but restricting permissions at the API level is the absolute best security measure.

- **Do Not Push Secrets**: Never commit `.env` or share your API Key or API Secret.
- **Group Lock**: Populate `ALLOWED_GROUP_ID` in your production settings so only members in your specific group can trigger checks.

---

## Setup Instructions

### Phase 1: Create your Telegram Bot
1. Open Telegram and search for `@BotFather`.
2. Start a chat and type `/newbot`.
3. Follow the instructions to give your bot a name and a username.
4. Copy the generated **Telegram Bot Token** (e.g., `1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
5. Open your Telegram group, add the bot as a member, and give it standard messaging permissions.

#### How to find your Telegram Group ID:
- **Using a bot**: Add `@RawDataBot` or `@MissRose_bot` to your group and type `/id`. It will output the group ID (e.g. `-100223456789`). Copy this number (including the minus sign). Remove the helper bot after copying the ID.

---

### Phase 2: Create a Binance API Key
1. Log in to your Binance account.
2. Navigate to **API Management** (under your profile menu).
3. Click **Create API** and choose **System generated API key**.
4. Set a label (e.g., `Telegram-Deposit-Bot`).
5. Complete security verification.
6. **Save your API Key and API Secret Key immediately** (the secret will only be shown once!).
7. Verify that under **API restrictions**, **"Enable Reading"** is the only enabled option. All others must be unchecked.

---

### Phase 3: Local Installation & Configuration

#### 1. Clone the repository and navigate inside:
```bash
git clone <your-repository-url>
cd binance-telegram-deposit-bot
```

#### 2. Create and activate a Python virtual environment:
```bash
# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

#### 3. Install the dependencies:
```bash
pip install -r requirements.txt
```

#### 4. Configure environment variables:
Copy the template `.env.example` file to `.env`:
```bash
cp .env.example .env
```
Open `.env` in your text editor and fill in your actual credentials:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
ALLOWED_GROUP_ID=-100223456789
```

#### 5. Run the bot locally:
```bash
python bot.py
```
Test the bot by typing `/check` in your configured Telegram group!

---

## 🚀 Deployment Guide

### Option A: VPS Deployment (Systemd Service)
For reliable running on an **Oracle Cloud Free Tier, DigitalOcean, or AWS VPS** (Ubuntu/Debian):

1. **Install Git & Python** on the VPS:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git -y
   ```
2. **Setup the Project**: Clone the code, configure `.env` as explained in Phase 3.
3. **Create a Systemd Service**: Create a system daemon so the bot restarts automatically if the server reboots:
   ```bash
   sudo nano /etc/systemd/system/telegram-deposit-bot.service
   ```
4. **Paste the following configuration** (adjust `/home/ubuntu/` to your actual path):
   ```ini
   [Unit]
   Description=Binance Telegram Deposit Bot Service
   After=network.target

   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/binance-telegram-deposit-bot
   ExecStart=/home/ubuntu/binance-telegram-deposit-bot/venv/bin/python bot.py
   Restart=always
   RestartSec=5
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```
5. **Start and enable the service**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start telegram-deposit-bot.service
   sudo systemctl enable telegram-deposit-bot.service
   ```
6. **Check logs**:
   ```bash
   sudo journalctl -u telegram-deposit-bot.service -f -n 50
   ```

---

### Option B: Deploying on Render
1. Sign up on [Render](https://render.com/).
2. Create a new service: **New +** -> **Background Worker** (do NOT use a Web Service, as this bot runs as a persistent listener and doesn't expose an HTTP port).
3. Connect your GitHub repository.
4. Set the **Build Command** to:
   ```bash
   pip install -r requirements.txt
   ```
5. Set the **Start Command** to:
   ```bash
   python bot.py
   ```
6. Navigate to **Environment** tab and add the variables:
   - `TELEGRAM_BOT_TOKEN`
   - `BINANCE_API_KEY`
   - `BINANCE_API_SECRET`
   - `ALLOWED_GROUP_ID` (Optional)
7. Deploy!

---

### Option C: Deploying on Railway
1. Sign up on [Railway](https://railway.app/).
2. Click **New Project** -> **Deploy from GitHub repo**.
3. Select your repository.
4. Railway will automatically detect the `Procfile` and provision a worker.
5. Under the **Variables** tab of the service, add the configuration parameters (`TELEGRAM_BOT_TOKEN`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`, and `ALLOWED_GROUP_ID`).
6. Deploy!
