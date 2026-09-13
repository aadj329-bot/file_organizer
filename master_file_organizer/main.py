import os
import argparse    
import json
from tkinter import Tk, filedialog

from organizer.scanner import list_files
from organizer.classifier import get_extension, classify
from organizer.actions import ensure_folder, resolve_duplicates, move_file
from organizer.undo import undo_moves
from file_organizer.organizer.undo import log

undo_log_path = "undo_log.txt"

def main():
    parser = argparse.ArgumentParser(description="Organize files by extension.")
    parser.add_argument("--path", required=True, help="Folder to organize")
    parser.add_argument("--config", default="config.json", help="Path to category config file")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without moving files")
    parser.add_argument("--undo", action="store_true", help="Undo the last organization run")
    
    args = parser.parse_args()

    if not args.path:
        Tk().withdraw()
        args.path = filedialog.askdirectory(title="Select a folder to organize")
    
    if args.undo:
        undo_moves(undo_log_path, log)
        return
    
    with open(args.config, "r") as f:
        config = json.load(f)

    lookup = {ext.lower(): cat for cat, exts in config.items() for ext in exts}

    undo_log = open(undo_log_path, "w")

    for filename, filepath in list_files(args.path):
        ext = get_extension(filename)
        if not ext:
            continue

        category = classify(ext, lookup)
        category_folder = os.path.join(args.path, category)

        ensure_folder(category_folder, args.dry_run, log)

        dest_path = os.path.join(category_folder, filename)

        if os.path.exists(dest_path):
            dest_path = resolve_duplicates(dest_path)

        move_file(filepath, dest_path, args.dry_run, undo_log, log)
            
    undo_log.close()
    log("Organization run complete")
            
if __name__ == "__main__":
    main()            

