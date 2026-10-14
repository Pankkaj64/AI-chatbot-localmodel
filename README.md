# Multimodal AI Chatbot (local models)

A ChatGPT-style web app with a FastAPI backend and a React frontend that runs entirely on **local models served by [Ollama](https://ollama.com)**, so no API key or paid service is needed. Users can chat with a choice of local models and attach an image for a vision model to analyse. Conversations are saved per session in **Postgres**. Prompts and replies are checked for safety and bias by the local model before anything is shown.

## Features

- **Text chat** with a choice of local models from a dropdown: `gemma3` (the default), `qwen2.5:3b`, `qwen2.5vl:3b` and `qwen3-vl:2b`. The browser remembers the chosen model.
- **Image understanding**: attach an image and it is sent to the model as base64 along with the message. This needs a vision model (`gemma3`, `qwen2.5vl:3b` or `qwen3-vl:2b`). `qwen2.5:3b` is text-only.
- **Session-based history**: messages are stored in Postgres by `session_id`, and the last 10 messages of a session go back to the model as context.
- **Chat sidebar** with a list of recent chats, search by title, loading of a previous session and deletion of a session. Deleting the chat that is open starts a new chat.
- **Token tracking**: each reply shows its prompt, reply and total token counts and the model used. Local models are free, so the cost is always $0.
- **Safety filtering**: the local model classifies the user's message as safe or unsafe (an unsafe message gets a safety-violation reply) and then checks the model's reply (an unsafe reply is replaced with a refusal).
- **Bias mitigation** through a system prompt that asks for neutral, objective answers and gives the current date and time. After the safety check, a separate local-model check classifies the reply as biased or clean, and a reply marked as biased is shown with a short warning note in front of it.
- **User accounts**: signup and login endpoints with bcrypt-hashed passwords and JWT access/refresh tokens. Chats are not yet tied to a user.
- **Markdown rendering** of replies, including GitHub-flavoured Markdown and syntax-highlighted code blocks.
- The current chat and session are saved in `localStorage`, so a page refresh does not lose them.

## Tech Stack

| Layer    | Technology |
|----------|------------|
| Backend  | Python, FastAPI, Uvicorn, OpenAI Python SDK (`AsyncOpenAI`, pointed at Ollama), Pillow, pydantic-settings |
| Database | Postgres, SQLModel / SQLAlchemy (async), asyncpg |
| Auth     | PyJWT, passlib + bcrypt |
| AI       | Ollama's OpenAI-compatible API (`/v1/chat/completions`) with local models |
| Frontend | React 19 (Create React App / `react-scripts`), `react-markdown`, `remark-gfm`, `react-syntax-highlighter` |

## How it works

```
React UI (localhost:3000)
   |  multipart/form-data: message, model, session_id, image?
   v
FastAPI  POST /chat/chat (localhost:8000)
   1. Safety check on the user message (local model)
   2. Load the last 10 messages for this session from Postgres
   3. Chat completion on Ollama (system prompt + history + text/image)
   4. Safety check on the reply, then a bias check (a biased reply gets a warning note)
   5. Save the user and assistant messages to Postgres
   v
JSON { reply, image_url, session_id, usage }
```

Every request makes up to four model calls (input safety, reply, reply safety, bias check). The safety and bias checks always use `LLM_MODEL`, so choosing a different model in the dropdown makes Ollama switch models and is slower.

## Project Structure

```
AI-Chatbot/
├── backend/
│   ├── main.py                 # FastAPI app: CORS, creates tables on startup, mounts the routers
│   ├── config.py               # Settings read from .env (pydantic-settings)
│   ├── requirements.txt        # Backend dependencies
│   ├── .env.example            # Template for backend/.env
│   ├── db/
│   │   └── database.py         # Async Postgres engine and per-request session
│   ├── app/                    # Chat
│   │   ├── routes.py           # /chat, /sessions, /history, delete session
│   │   ├── service.py          # ChatService: database queries
│   │   ├── llm.py              # Ollama calls: reply, safety check, bias check
│   │   ├── models.py           # Message table
│   │   └── schemas.py          # API response shapes
│   └── auth/                   # Signup and login
│       ├── routes.py           # /signup, /login
│       ├── service.py          # UserService
│       ├── utils.py            # Password hashing, JWT
│       ├── models.py           # User table
│       └── schemas.py          # Request/response shapes
└── frontend/
    ├── package.json            # CRA scripts and dependencies
    ├── public/                 # index.html, icons, manifest
    └── src/
        ├── App.js              # Root component, renders ChatApp
        ├── App.css             # Dark chat UI styles
        └── components/
            ├── ChatApp.jsx     # Main chat view: input, attachments, messages, token usage
            ├── ChatHistory.jsx # Sidebar: recent sessions, search, delete
            └── ModelSelector.jsx # Local model dropdown
```

## Getting Started

### Prerequisites

- Python 3.10 or newer (the code uses the `X | None` type syntax)
- Node.js and npm
- [Ollama](https://ollama.com), with the models pulled:
  ```bash
  ollama pull gemma3
  ollama pull qwen2.5:3b
  ollama pull qwen2.5vl:3b
  ollama pull qwen3-vl:2b
  ```
  Only `gemma3` is required; pull the others if you want them in the dropdown.
- Postgres (for example `brew install postgresql@18`), with a database for the app:
  ```bash
  createdb ai
  ```

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in DATABASE_URL and JWT_SECRET
```

`.env` settings:

| Variable              | Description |
|-----------------------|-------------|
| `LLM_BASE_URL`        | Ollama's OpenAI-compatible endpoint (default `http://localhost:11434/v1`) |
| `LLM_MODEL`           | Default model, also used for the safety and bias checks (default `gemma3`) |
| `DATABASE_URL`        | e.g. `postgresql+asyncpg://<user>:<password>@localhost:5432/ai` |
| `JWT_SECRET`          | A long random string (at least 32 characters) |
| `JWT_ALGORITHM`       | Default `HS256` |
| `ACCESS_TOKEN_EXPIRY` | Access token lifetime in seconds (default `3600`) |

Make sure Ollama is running (the menu-bar app, or `ollama serve`), then start the API from the activated venv:

```bash
uvicorn main:app --reload
```

The API runs at `http://localhost:8000`. On startup it creates the `messages` and `user` tables if they do not exist yet.

### Frontend

```bash
cd frontend
npm install
npm start
```

The app opens at `http://localhost:3000` and calls the backend at `http://localhost:8000`.

## Usage

1. Start Ollama, Postgres, the backend and the frontend, then open `http://localhost:3000`.
2. Choose a model, type a message and press Enter (Shift+Enter adds a new line).
3. Click **Attach** to send an image with your message (use a vision model).
4. Open the sidebar (☰) to start a new chat, search past chats, reopen one or delete it.

### API Endpoints

| Method   | Endpoint                      | Description |
|----------|-------------------------------|-------------|
| `POST`   | `/chat/chat`                  | Form fields: `message` (required), `model` (default `LLM_MODEL`), `session_id`, `image` (file). Returns `reply`, `image_url`, `session_id` and `usage` (token counts). `generate_img=true` returns 400, since local models can't generate images. |
| `GET`    | `/chat/sessions`              | Lists sessions, newest first. Each has a title made from the first 30 characters of its first message. |
| `GET`    | `/chat/history/{session_id}`  | Returns every message in a session, with images and usage. |
| `DELETE` | `/chat/sessions/{session_id}` | Deletes all messages in a session. |
| `POST`   | `/auth/signup`                | JSON: `first_name`, `last_name`, `username`, `email`, `password`. Creates a user. |
| `POST`   | `/auth/login`                 | JSON: `email`, `password`. Returns an access token and a refresh token. |

## Notes

- This is a local development project. CORS allows all origins, and the frontend calls `http://localhost:8000` directly.
- Small local models (2–4B parameters) give weaker answers than hosted models, and their safety and bias classifications are less reliable than a dedicated moderation API.
- Tables are created with `SQLModel.metadata.create_all` on startup; there are no migrations yet.
