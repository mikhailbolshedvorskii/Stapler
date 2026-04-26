 # 🏥 Stapler — AI Medical Assistant

Stapler is an intelligent assistant that transforms the chaos of medical paperwork into a structured knowledge base. It digitizes lab results, identifies patterns, and helps users monitor their health without needing a medical dictionary.

> **The philosophy is simple: you shouldn't manage your data — your data should work for you**


# 🚀 How It Works (Execution Flow)

**1 Upload:** User sends a photo or PDF of a medical test to the Telegram bot.


**2 Digitization:** The Gemini AI module performing native multimodal OCR extracts biomarkers, dates, and laboratory names directly from the image.


**3 Structuring:** Data is saved to a cloud database (Firestore) in the following format:

- `Document ID` / `Date` / `Laboratory`

- `Biomarkers` (Name, Value, Reference Range)

- `AI Summary` (Brief insight in plain language)


**4 Analytics:** The system compares the current result with historical data in the database and identifies trends.

# 💬 Interface Features

### Current Prototype (Telegram)

- The bot serves as a personal medical archive, available 24/7.

- Instant Response: Decoding of complex analyses within 15-20 seconds.

- `/history` Command: Quick access to the last 5 medical checkups.

- Security: Each user's profile is strictly tied to their Telegram ID.

### Development Roadmap:

- Shared Access: Ability to share records with a trusted doctor or family member.

- Voice Search: Search using natural language ("Show me my sugar levels from last year").

- Web Dashboard: A comprehensive portal with health trend graphs and analytics.


# 🧠 Vision

The long-term goal of Stapler is to evolve into a private ecosystem that:

- Automatically collects data from emails and messaging apps.

- Predicts critical deviations before they become serious health issues.

- Ensures medical data transparency: the simplicity of a folder, the accuracy of a table, and the power of AI.


# 📂 Project Structure (Core) (это надо доработать)

``` stapler_project/
├── main.py             # Entry point and bot lifecycle
├── handlers.py         # Command and message processing logic
├── ai_parser.py        # System brain: Gemini AI (Native OCR + Logic)
├── database.py         # Cloud storage (Firebase Firestore)
└── .env                # Secret access keys 
```


# Telescope Next Steps

- Intelligent Trends: Visualization of biomarker changes over time.

- Multilingual Support: Full localization for EN/RU/Global markets.

- Proactive Alerts: Notifications for scheduled follow-up checkups.

## 📜 Metadata

Status: Working Prototype (MVP)

Infrastructure: Google Cloud / Firebase

Author: M. M. Bolshedvorskii

Disclaimer: This tool is an AI assistant, not a medical professional. Always consult with a doctor.