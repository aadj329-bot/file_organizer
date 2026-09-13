import os
import shutil

def ensure_folder(path, dry_run, log):
    if not os.path.exists(path):
        if dry_run:
            print(f"[DRY RUN] Would create folder: {path}")
        else:
            os.makedirs(path)
            log(f"Created folder: {path}")

def resolve_duplicates(dest_path):
    base, extension = os.path.splitext(dest_path)
    counter = 1

    while True:
        new_path = f"{base}_{counter}{extension}"
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def move_file(src, dest, dry_run, undo_log, log):
    if dry_run:
        print(f"[DRY RUN] Would move {src} -> {dest}")
        return
    shutil.move(src,dest)
    undo_log.write(f"{src} -> {dest}\n")
    log(f"Moved {src} -> {dest}")
    print(f"Moved {src} -> {dest}")