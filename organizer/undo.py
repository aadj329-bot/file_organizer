import os
import shutil

def undo_moves(log_path, log):
    if not os.path.exists(log_path):
        print("No undo log found. Nothing to undo.") 
        return

    print("Undoing previous file move...")
    log("Starting UNDO operation")

    with open(log_path, "r") as f:
        lines = f.readlines()

    for line in reversed(lines):
        src, dest = line.strip().split(" -> ")
        if os.path.exists(dest):
            print(f"Moving back: {dest} -> {src}")
            shutil.move(dest, src)
            log(f"UNDO: {dest} -> {src}")

    print("Undo complete.")
    log("UNDO operation complete")