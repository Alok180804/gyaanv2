# gyaanv2

A clean Streamlit RAG app for Google Drive knowledge bases. Paste a Google Drive folder or file link, sync supported files, and ask grounded questions with citations. If the answer is not present in indexed documents, the assistant returns exactly `No data found.`

## Features
- Google Drive folders and individual files as sources
- Google Docs, Sheets, Slides, PDFs, plain text, CSV, Markdown, DOCX, XLSX, and PPTX ingestion where available
- Recursive chunking with page/sheet/slide-aware metadata
- Sentence Transformers embeddings
- Local Qdrant vector database
- SQLite metadata database
- Configurable LLM providers: OpenAI, Claude, Gemini, Ollama, or extractive fallback
- Streamlit pages: Settings, Documents, Chat
- Docker Compose support

## Setup
1. Copy environment values:
```bash
cp .env.example .env
```
2. Create a Google OAuth desktop client and save it as `credentials.json` in this directory, or set `GOOGLE_CREDENTIALS_FILE`.
3. Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
4. Run the app:
```bash
streamlit run app.py
```
The first Google sync opens an OAuth flow and writes `token.json` locally.

## Docker
```bash
docker compose up --build
```
Mount `credentials.json` into the container or bind the project directory as configured in `docker-compose.yml`.

## Usage
1. Open **Settings**.
2. Paste a Google Drive folder/document link and click **Add source**.
3. Click **Sync all active sources** or sync a single source.
4. Open **Documents** to inspect indexed files and chunk counts.
5. Open **Chat**, ask a question, and inspect retrieved sources/chunks.

## Configuration
See `.env.example`. `LLM_PROVIDER=ollama` sends final answers to a locally running Ollama server by default. Set `LLM_MODEL` to the local model name you downloaded (for example `llama3.1`), or use `openai`, `claude`, `gemini`, or `extractive` for other answer modes. Final answers include citations and the model used when data is found.
