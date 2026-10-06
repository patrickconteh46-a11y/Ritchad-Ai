# RITCHAD AI v2

A mobile-first personal AI assistant UI inspired by the approved RITCHAD AI concept: dark cinematic styling, neon cyan glow, glass panels, and the glowing R orb.

## Included
- Modern RITCHAD AI home dashboard
- Voice input using browser SpeechRecognition when supported
- Spoken responses using browser speech synthesis
- Persistent memory API integration
- Tasks API integration
- File upload/list API integration
- Image editor with local preview, brightness, saturation, mono/cool/warm filters
- Prepared buttons for advanced AI image editing
- Responsive PWA layout for Android

## Run frontend
```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` to your deployed FastAPI backend when needed.

## Run backend
```bash
cd backend
python -m venv .venv
# activate the environment
pip install -r requirements.txt
uvicorn app:app --reload
```

The advanced image-editing buttons are UI placeholders until an image-generation/editing provider is connected. Device controls should remain permission-based.
