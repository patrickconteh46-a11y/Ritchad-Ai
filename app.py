import os, sqlite3, uuid, json
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
DB = Path(__file__).with_name("ritchad.db")
UPLOADS = Path(__file__).with_name("uploads")
UPLOADS.mkdir(exist_ok=True)
app = FastAPI(title="RITCHAD AI API", version="0.1.0")
origin = os.getenv("APP_ORIGIN", "http://localhost:5173")
app.add_middleware(CORSMiddleware, allow_origins=[origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, content TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY, description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY, filename TEXT NOT NULL, stored_name TEXT NOT NULL, created_at TEXT NOT NULL);
        """)
init()

def now(): return datetime.now(timezone.utc).isoformat()

class ChatIn(BaseModel):
    message: str
class MemoryIn(BaseModel):
    content: str
class TaskIn(BaseModel):
    title: str
class ActionIn(BaseModel):
    description: str

@app.get("/health")
def health(): return {"status":"ok","name":"RITCHAD AI"}

@app.get("/memories")
def memories():
    with db() as c: return [dict(r) for r in c.execute("SELECT * FROM memories ORDER BY created_at DESC")]
@app.post("/memories")
def add_memory(x: MemoryIn):
    if not x.content.strip(): raise HTTPException(400, "Memory cannot be empty")
    ident=str(uuid.uuid4())
    with db() as c: c.execute("INSERT INTO memories VALUES(?,?,?)",(ident,x.content.strip(),now()))
    return {"id":ident,"content":x.content.strip()}

@app.get("/tasks")
def tasks():
    with db() as c: return [dict(r) for r in c.execute("SELECT * FROM tasks ORDER BY created_at DESC")]
@app.post("/tasks")
def add_task(x: TaskIn):
    if not x.title.strip(): raise HTTPException(400,"Task title required")
    ident=str(uuid.uuid4())
    with db() as c: c.execute("INSERT INTO tasks(id,title,done,created_at) VALUES(?,?,0,?)",(ident,x.title.strip(),now()))
    return {"id":ident,"title":x.title.strip(),"done":0}
@app.patch("/tasks/{task_id}")
def toggle_task(task_id: str):
    with db() as c:
        row=c.execute("SELECT done FROM tasks WHERE id=?",(task_id,)).fetchone()
        if not row: raise HTTPException(404,"Task not found")
        done=0 if row["done"] else 1
        c.execute("UPDATE tasks SET done=? WHERE id=?",(done,task_id))
    return {"id":task_id,"done":done}

@app.post("/actions")
def propose_action(x: ActionIn):
    ident=str(uuid.uuid4())
    with db() as c: c.execute("INSERT INTO actions VALUES(?,?,?,?)",(ident,x.description.strip(),"pending",now()))
    return {"id":ident,"description":x.description.strip(),"status":"pending","message":"Approval required; no device action has been executed."}
@app.get("/actions")
def actions():
    with db() as c: return [dict(r) for r in c.execute("SELECT * FROM actions ORDER BY created_at DESC")]
@app.post("/actions/{action_id}/approve")
def approve_action(action_id: str):
    with db() as c:
        row=c.execute("SELECT id FROM actions WHERE id=?",(action_id,)).fetchone()
        if not row: raise HTTPException(404,"Action not found")
        c.execute("UPDATE actions SET status='approved_not_executed' WHERE id=?",(action_id,))
    return {"id":action_id,"status":"approved_not_executed","message":"Approved in demo only. No external device command was sent."}

@app.post("/files")
async def upload_file(file: UploadFile = File(...)):
    # MVP guardrails: bounded size and safe generated storage name; production needs malware scanning/auth.
    data=await file.read(5*1024*1024+1)
    if len(data)>5*1024*1024: raise HTTPException(413,"Maximum file size is 5 MB")
    ident=str(uuid.uuid4()); suffix=Path(file.filename or "").suffix[:12]
    stored=ident+suffix
    (UPLOADS/stored).write_bytes(data)
    with db() as c: c.execute("INSERT INTO uploads VALUES(?,?,?,?)",(ident,file.filename or "upload",stored,now()))
    return {"id":ident,"filename":file.filename or "upload","size":len(data)}
@app.get("/files")
def list_files():
    with db() as c: return [dict(r) for r in c.execute("SELECT id,filename,created_at FROM uploads ORDER BY created_at DESC")]

@app.get("/web-search")
def web_search(q: str):
    if not q.strip(): raise HTTPException(400,"Query required")
    return {"query":q,"configured":False,"results":[],"note":"Connect a trusted search provider adapter and API key to enable live web search."}

@app.post("/chat")
def chat(x: ChatIn):
    key=os.getenv("OPENAI_API_KEY")
    if not key or key=="replace_me":
        return {"reply":"RITCHAD is running, but its AI brain is not configured yet. Add OPENAI_API_KEY to backend/.env and restart the backend.","configured":False}
    from openai import OpenAI
    with db() as c:
        mem=[r["content"] for r in c.execute("SELECT content FROM memories ORDER BY created_at DESC LIMIT 12")]
        task=[r["title"] for r in c.execute("SELECT title FROM tasks WHERE done=0 LIMIT 12")]
    context="\n".join(["User-approved memories: "+("; ".join(mem) if mem else "none"),"Open tasks: "+("; ".join(task) if task else "none")])
    try:
        client=OpenAI(api_key=key)
        result=client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL","gpt-4o-mini"),
            messages=[{"role":"system","content":"You are RITCHAD, a helpful personal assistant. Be clear and practical. Never claim to execute device actions, browse live web, or modify files unless an enabled tool actually did so. Ask for explicit confirmation before consequential external actions. Context:\n"+context},
                      {"role":"user","content":x.message}],
            max_tokens=600)
        return {"reply":result.choices[0].message.content or "", "configured":True}
    except Exception as e:
        raise HTTPException(502,"AI provider request failed; check server configuration.")
