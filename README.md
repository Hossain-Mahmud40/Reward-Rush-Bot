# 🎁 Reward Rush Bot

![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)
![Python](https://img.shields.io/badge/Python-3.8%2B-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

**Reward Rush Bot** is a powerful yet beginner-friendly **Telegram giveaway and reward management bot** built with Python.  
It helps Telegram communities run **giveaways, redeem codes, distribute prizes (accounts or files), and manage users** efficiently.

This project was built as a **learning-focused real-world project**, going beyond simple bot replies to include **permissions, persistence, rate limiting, and admin controls**.

---

## 📌 What This Bot Can Do

Reward Rush Bot is ideal for:
- Telegram giveaway channels
- Promotional communities
- Reward-based systems
- Learning how real Telegram bots work

---

## ✨ Features

### 🎉 Giveaway Management
- Start giveaways with timers
- Add prizes (accounts or files)
- Automatically select winners
- Notify participants and admins

### 🎟 Code Redemption System
- Users can redeem **unique codes** for rewards
- Cooldowns and rate-limiting to prevent abuse
- Supports both **accounts and downloadable files**

### 👥 User & Admin Roles
- Owner-only and admin-only commands
- Add/remove admins
- Ban users permanently
- Banned users are ignored by the system

### 📢 Broadcast & Notifications
- Notify winners automatically
- Admin alerts for important actions
- Progress updates during giveaways

### 📂 File-Based Prizes
- Admins can upload files as rewards
- Files are delivered automatically on redemption

### 🔐 Security & Safety
- Thread-safe data access (locking)
- Markdown escaping to prevent injection
- Channel membership enforcement
- Banned-user validation

### 🤖 Automation Features
- Auto-approve join requests
- Forward user messages to admins for support

### 💾 Data Persistence
All bot data is stored in a single file:
- `data.json`

Includes:
- Users
- Admins
- Accounts
- Giveaways
- Banned users

---

## 🧰 Tech Stack

- **Python 3.8+**
- **pyTelegramBotAPI**
- **python-dotenv**
- **Telegram Bot API**
- **JSON (lightweight database)**

---

## 📁 Project Structure
reward-rush-bot/
│
├── bot.py # Main bot logic
├── data.json # Persistent storage (users, giveaways, bans)
├── .env # Environment variables (BOT_TOKEN)
├── requirements.txt # Python dependencies
└── README.md # Documentation


---

## ✅ Prerequisites

- Python 3.8 or higher  
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)  
- Access to Telegram channels for membership checks  

---

## 🚀 Setup Instructions

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yourusername/reward-rush-bot.git
cd reward-rush-bot
```
2️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```
3️⃣ Configure Environment Variables
Edit the .env with a notepad then change the bot token with yours.
BOT_TOKEN=your_bot_token_here

4️⃣ Configure Owners & Channels
Edit bot.py:

OWNERS = [123456789]

CHANNELS = {
    -100xxxxxxxxxx: "Channel Name"
}
5️⃣ Run the Bot
```bash
python bot.py
```
⚠️ Disclaimer

This bot is built for educational and community use.
Always follow Telegram’s terms of service.

📄 License

MIT License — free to use, modify, and learn from.
