from fastapi import FastAPI
from pydantic import BaseModel
import os
import json

from organizer.scanner import list_files
from organizer.classifier import get_extension, classify
from organizer.actions import ensure_folder, resolve_duplicates, move_file
from organizer.undo import undo_moves
from file_organizer.organizer.undo import log

UNDO_LOG = "undo_log.txt"

app = FastAPI(title="Master File Organizer API")

# Request Modelss

class OrganizeRequest(BaseModel):
    path: str
    config_path: str = "config.json"
    dry_run: bool = False

class UndoRequest(BaseModel):
    pass

# Endpoints

@app.post("/organize")
def organize_files(req: OrganizeRequest):
    """Organize files in a folder via API."""
    if not os.path.exists(req.path):
        return {"error": "Path does not exist"}
    
    # Load config
    with open(req.config_path, "r") as f:
        config = json.load(f)

    lookup = {ext.lower(): cat for cat, exts in config.items() for ext in exts}

    undo_log = open(UNDO_LOG, "w")

    actions = []

    for filename, filepath in list_files(req.path):
        ext = get_extension(filename)
        if not ext:
            continue

        category = classify(ext, lookup)
        category_folder = os.path.join(req.path, category)

        ensure_folder(category_folder, req.dry_run, log)

        dest_path = os.path.join(category_folder, filename)

        if os.path.exists(dest_path):
            dest_path = resolve_duplicates(dest_path)

        if req.dry_run:
            actions.append({"action": "move", "src": filepath, "dest": dest_path})
        else:
            move_file(filepath, dest_path, req.dry_run, undo_log, log)
            actions.append({"moved": f"{filepath} -> {dest_path}"})

    undo_log.close()
    log("API organization run complete")

    return{"status": "success", "actions": actions}

@app.post("/undo")
def undo_last(req: UndoRequest):
    """Undo the last organization run."""
    undo_moves(UNDO_LOG, log)
    return {"status": "undo complete"}
    
@app.get("/config")
def get_config():
    """Return the current config.json."""
    if not os.path.exists("config.json"):
        return {"error": "Config file not found"}
    
    with open("config.json", "r") as f:
        return json.load(f)
    
