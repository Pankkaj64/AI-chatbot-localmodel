# Multimodal AI Chatbot

A ChatGPT-style web app with a FastAPI backend and a React frontend. Users can chat with OpenAI GPT-4o or GPT-4o mini, attach an image for the model to analyse, or ask DALL-E 3 to generate one. Conversations are saved per session in SQLite. Every reply shows its token usage and estimated cost, and both prompts and replies pass through the OpenAI Moderation API before anything is shown.

## Features

- **Text chat** with a choice of `gpt-4o-mini` (the default) or `gpt-4o` from a dropdown. The browser remembers the chosen model.
- **Image understanding**: attach an image and it is sent to the model as base64 along with the message.
- **Image generation**: tick "Generate Image" to create a 1024x1024 image with DALL-E 3 from the prompt.
- **Session-based history**: messages are stored in SQLite by `session_id`, and the last 10 messages of a session go back to the model as context.
- **Chat sidebar** with a list of recent chats, search by title, loading of a previous session and deletion of a session. Deleting the chat that is open starts a new chat.
- **Token and cost tracking**: each reply shows its prompt, reply and total token counts, its estimated USD cost (based on a per-model price table) and the model used. A running total is shown for the current session.
- **Safety filtering**: the OpenAI Moderation API checks the user's message (a flagged message is rejected with HTTP 400) and the model's reply (a flagged reply is replaced with a refusal).
- **Bias mitigation** through a system prompt that asks for neutral, objective answers and gives the current date and time. After moderation, a separate `gpt-4o-mini` check classifies the reply as biased or clean, and a reply marked as biased is shown with a short warning note in front of it.
- **Markdown rendering** of replies, including GitHub-flavoured Markdown and syntax-highlighted code blocks.
- The current chat and session are saved in `localStorage`, so a page refresh does not lose them.

## Tech Stack

| Layer    | Technology |
|----------|------------|
| Backend  | Python, FastAPI, Uvicorn, OpenAI Python SDK, Pillow, python-dotenv, SQLite (`sqlite3`) |
| AI       | OpenAI Chat Completions (`gpt-4o`, `gpt-4o-mini`), DALL-E 3, Moderation API |
| Frontend | React 19 (Create React App / `react-scripts`), `react-markdown`, `remark-gfm`, `react-syntax-highlighter` |

## How it works

```
React UI (localhost:3000)
   |  multipart/form-data: message, model, session_id, image?, generate_img
   v
FastAPI  POST /chat (localhost:8000)
   1. Moderation check on the user message
   2. Load the last 10 messages for this session from SQLite
   3. Chat Completion (system prompt + history + text/image)
   4. Work out the token cost from MODEL_PRICING
   5. Moderation check on the reply, then a bias check (a biased reply gets a warning note)
   6. Optional DALL-E 3 image generation
   7. Save the user and assistant messages to chat.db
   v
JSON { reply, image_url, session_id, usage }
```

## Project Structure

```
AI-Chatbot/
├── backend/
│   ├── main.py                 # FastAPI app: chat, sessions, history, moderation, bias check, pricing, SQLite
│   ├── requirements.txt        # Backend dependencies
│   └── .env.example            # Template for backend/.env
└── frontend/
    ├── package.json            # CRA scripts and dependencies
    ├── public/                 # index.html, icons, manifest
    └── src/
        ├── App.js              # Root component, renders ChatApp
        ├── App.css             # Dark chat UI styles
        └── components/
            ├── ChatApp.jsx     # Main chat view: input, attachments, image toggle, messages, cost
            ├── ChatHistory.jsx # Sidebar: recent sessions, search, delete
            └── ModelSelector.jsx # GPT-4o / GPT-4o mini dropdown
```

## Getting Started

### Prerequisites

- Python 3.10 or newer (the code uses the `X | None` type syntax)
- Node.js and npm
- An OpenAI API key

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then set OPENAI_API_KEY in .env
```

Start the API:

```bash
uvicorn main:app --reload
```

The API runs at `http://localhost:8000`. On startup it creates `chat.db` and the `messages` table if they do not exist yet.

### Frontend

```bash
cd frontend
npm install
npm start
```

The app opens at `http://localhost:3000` and calls the backend at `http://localhost:8000`.

## Usage

1. Start the backend and the frontend, then open `http://localhost:3000`.
2. Choose a model, type a message and press Enter (Shift+Enter adds a new line).
3. Click **Attach** to send an image with your message, or tick **Generate Image** to get a DALL-E 3 image for your prompt.
4. Open the sidebar (☰) to start a new chat, search past chats, reopen one or delete it.

### API Endpoints

| Method   | Endpoint                 | Description |
|----------|--------------------------|-------------|
| `POST`   | `/chat`                  | Form fields: `message` (required), `model` (default `gpt-4o-mini`), `session_id`, `image` (file), `generate_img` (bool). Returns `reply`, `image_url`, `session_id` and `usage` (token counts and estimated cost). |
| `GET`    | `/sessions`              | Lists sessions, newest first. Each has a title made from the first 30 characters of its first message. |
| `GET`    | `/history/{session_id}`  | Returns every message in a session, with images, cost and usage. |
| `DELETE` | `/sessions/{session_id}` | Deletes all messages in a session. |

## Notes

- This is a local development project. CORS allows all origins, and the frontend calls `http://localhost:8000` directly.
- Costs are estimates from the hard-coded `MODEL_PRICING` table in `backend/main.py` (USD per 1M tokens), not from OpenAI billing. The moderation and bias-check calls are not included in the estimate.
