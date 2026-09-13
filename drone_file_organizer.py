import hashlib
import os          
import shutil      
import argparse    
import json
from datetime import datetime
from tkinter import Tk, filedialog
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import subprocess


# -----------------------------
# Metadata Extraction Functions
# -----------------------------

def get_metadata(path):
    """ Extracts robust metadata from photos, videos, and DJI drone files.
    Returns a dictionary with:
        - timestamp
        -gps (lat, lon, alt)
        - camera info
        - video metadata
        - drone flight data (SRT)
        - file stats (size, mtime)
    """

    metadata = {
        "timestamp": None,
        "gps": {"lat": None, "lon": None, "alt": None},
        "camera": {
            "model": None,
            "make": None,
            "lens": None,
            "iso": None,
            "aperture": None,
            "shutter_speed": None,
            "focal_length": None
        },
        "video":{
            "creation_time": None,
            "duration": None,
            "codec": None,
            "bitrate": None,
            "resolution": None
        },
        "drone":{
            "flight_timestamp": None,
            "gps_altitude": None,
            "gps_lat": None,
            "gps_lon": None,
            "flight_duration": None,
            "max_altitude": None,
            "max_distance": None
        },
        "file":{
            "size_bytes": os.path.getsize(path),
            "modified": datetime.fromtimestamp(os.path.getmtime(path)),
            "hash_md5": None,
            "extension": os.path.splitext(path)[1].lower()
        }
    }

    # -----------------------------
    # Helpers
    # -----------------------------
    def hash_file():
        try:
            with open(path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None
        
    def parse_exif():
        try:
            img = Image.open(path)
            exif = img.getexif()
            if not exif:
                return
        
            exif_data = {TAGS.get(k, k): v for k, v in exif.items()}

            # Timestamp
            for key in ("DateTimeOriginal", "CreateDate", "ModifyDate"):
                ts_str = exif_data.get(key)
                if ts_str:
                    try:
                        metadata["timestamp"] = datetime.strptime(ts_str, "%Y:%m:%d %H:%M:%S")
                        break
                    except Exception:
                        pass  # Continue to next key if parsing fails

            # Camera Info
            metadata["camera"]["model"] = exif_data.get("Model")
            metadata["camera"]["make"] = exif_data.get("Make")
            metadata["camera"]["lens"] = exif_data.get("LensModel")
            metadata["camera"]["iso"] = exif_data.get("ISOSpeedRatings")
            metadata["camera"]["aperture"] = exif_data.get("FNumber")
            metadata["camera"]["shutter_speed"] = exif_data.get("ExposureTime")
            metadata["camera"]["focal_length"] = exif_data.get("FocalLength")

            # GPS
            gps_raw = exif_data.get("GPSInfo")
            if gps_raw:
                gps = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}

                def convert(coord):
                    try:
                        d, m, s = coord
                        return float(d) + float(m)/60 + float(s)/3600
                    except Exception:
                        return None
                    
                lat = gps.get("GPSLatitude")
                lon = gps.get("GPSLongitude")
                lat_ref = gps.get("GPSLatitudeRef")
                lon_ref = gps.get("GPSLongitudeRef")
                alt = gps.get("GPSAltitude")

                if lat and lon:
                    metadata["gps"]["lat"] = convert(lat)
                    metadata["gps"]["lon"] = convert(lon)
                    if lat_ref == "S":
                        metadata["gps"]["lat"] *= -1
                    if lon_ref == "W":
                        metadata["gps"]["lon"] *= -1

                if alt:
                    metadata["gps"]["alt"] = float(alt)
        except Exception:
            pass  # Not an image or no EXIF data
    
    def parse_video():
        if not path.lower().endswith(('.mp4', '.mov', '.m4v')):
            return
        
        try:
            cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
                   "-show_format", "-show_streams", path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            meta = json.loads(result.stdout)

            # Format-level metadata
            format_meta = meta.get("format", {})
            metadata["video"]["creation_time"] = format_meta.get("tags", {}).get("creation_time")
            metadata["video"]["duration"] = float(format_meta.get("duration", 0))
            metadata["video"]["bitrate"] = int(format_meta.get("bit_rate", 0))

            # Stream-level metadata (video stream)
            for stream in meta.get("streams", []):
                if stream.get("codec_type") == "video":
                    metadata["video"]["codec"] = stream.get("codec_name")
                    metadata["video"]["resolution"] = f"{stream.get('width')}x{stream.get('height')}"
                    break
        except Exception:
            pass  # ffprobe failed or not available

    def parse_srt():
        if path.lower().endswith('.srt'):
            try:
                with open(path, "r", encoding="utf8", errors="ignore") as f:
                    for line in f: 
                        if "-->" in line:
                            ts = line.split("-->")[0].strip()
                            h, m, s = ts.split(":")
                            s = s.replace(",", ".")  # Convert to float seconds
                            base = datetime.fromtimestamp(os.path.getmtime(path))
                            metadata["drone"]["flight_timestamp"] = base.replace(hour=int(h), minute=int(m), second=int(float(s)))

                    # GPS lines (DJI embeds them)
                        if "GPS" in line:
                            parts = line.split(",")
                            for p in parts:
                                if "Lat" in p:
                                    metadata["drone"]["gps_lat"] = float(p.split(":")[1])
                                if "Lon" in p:
                                    metadata["drone"]["gps_lon"] = float(p.split(":")[1])
                                if "Alt" in p:
                                    metadata["drone"]["gps_altitude"] = float(p.split(":")[1])
            except Exception:
                pass  # Not a DJI SRT or parsing failed

    # ----------------------------
    # Run Helpers
    # ----------------------------
    metadata["file"]["hash_md5"] = hash_file()
    parse_exif()
    parse_video()
    parse_srt()

    return metadata

# -----------------------------
# Timestamp
# -----------------------------

def get_timestamp(meta):
    """
    Returns the best available timestamp from the metadata dictionary.
    Priority:
        1. EXIF Timestamp (photo)
        2. Video creation time(MP4/MOV)
        3. Drone flight timestamp
        4. File modified time (fallback)
    """
    # 1. EXIF timestamp
    if meta.get("timestamp"):
        return meta["timestamp"]

    # 2. Video creation time
    vid_ts = meta.get("video", {}).get("creation_time")
    if vid_ts:
        try:
            # ffprobe uses ISO 8601 timestamp
            return datetime.fromisoformat(vid_ts.replace("Z", "+00:00"))
        except Exception:
            pass 

    # 3. Drone Flight timestamp (SRT)
    drone_ts = meta.get("drone", {}).get("flight_timestamp")
    if drone_ts:
        return drone_ts
    
    # 4. Fallback: filesystem modified time
    return meta["file"]["modified"]

def move_file(path, root_output, dry_run=False):
    meta = get_metadata(path)
    ts = get_timestamp(meta)
 
    # Determine file type
    # build folder structure
    # build dest path

    ext = meta["file"]["extension"]

    PHOTO_RAW_EXT = {".dng", ".nef", ".cr2", ".arw"}
    PHOTO_JPG_EXT = {".jpg", ".jpeg"}
    PHOTO_EDITED_EXT = {".png", ".tif", ".tiff", ".psd"}
    VIDEO_EXT = {".mp4", ".mov", ".m4v"}
    LOG_EXT = {".srt"}

    if ext in PHOTO_RAW_EXT:
        subfolder = ["Photos", "RAW"]
    elif ext in PHOTO_JPG_EXT:
        subfolder = ["Photos", "JPG"]
    elif ext in PHOTO_EDITED_EXT:
        subfolder = ["Photos", "Edited"]
    elif ext in VIDEO_EXT:
        subfolder = ["Videos"]
    elif ext in LOG_EXT:
        subfolder = ["Logs"]
    else:
        subfolder = ["Misc"]

    # Build folder structure
    year = ts.strftime("%Y")
    month = ts.strftime("%Y-%m")
    day = ts.strftime("%Y-%m-%d")

    # Flight folder
    if meta["drone"]["flight_timestamp"]:
        ft = meta["drone"]["flight_timestamp"]
        flight_folder = f"{ft.strftime('%Y-%m-%d_%H-%M-%S')}_Flight"
    else:
        flight_folder = f"{day}_Flight01"
    
    # Build destination path
    dest = os.path.join(root_output, year, month, flight_folder, *subfolder)
    os.makedirs(dest, exist_ok=True)

    # Move file
    final_path = os.path.join(dest, os.path.basename(path))

    # Duplicate check
    if os.path.exists(final_path):
        existing_meta = get_metadata(final_path)
        
        # If hashes match -> exact duplicate -> skip
        if existing_meta["file"]["hash_md5"] == meta["file"]["hash_md5"]:
            print(f"Duplicate detected (same file) -> SKIPPED: {path}")
            return
        
        # If hashes differ -> rename
        base, extn = os.path.splitext(os.path.basename(path))
        counter = 1 
        new_final = os.path.join(dest, f"{base}_{counter}{extn}")

        while os.path.exists(new_final):
            counter += 1
            new_final = os.path.join(dest, f"{base}_{counter}{extn}")

        final_path = new_final

    # Dry_run mode
    if dry_run:
        print(f"[DRY RUN] Would move {path} to {final_path}")
        return
    
    # Actual move
    shutil.move(path, final_path)
    undo_log.write(f"{path} -> {final_path}\n")
    print(f"Moved {path} -> {final_path}")



# -----------------------------
# ARGUMENT PARSER SETUP
# -----------------------------

parser = argparse.ArgumentParser(description="Organize files by extension.")
parser.add_argument("--path", required=True, help="Folder to organize")
parser.add_argument("--config", default="config.json", help="Path to category config file")
parser.add_argument("--dry-run", action="store_true", help="Show potential actions without moving files")
parser.add_argument("--undo", action="store_true", help="Undo the last organization run")

args = parser.parse_args()

if args.path:
    folder = args.path
else:
    folder = input("Enter folder: ")
    
if not os.path.isdir(folder):
    print("Folder does not exist.")
    exit()
    
if not args.path:
    Tk().withdraw()  # Hide the empty Tk window
    args.path = filedialog.askdirectory(title="Select a folder to organize")
# -----------------------------
# Log files
# -----------------------------
undo_log_path = "undo_log.txt"
human_log_path = "organizer_log.txt"

def log(message):
    """Write a timestamped message to the human-readable log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(human_log_path, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    

# -----------------------------
# Undo Option (Oopsie)
# -----------------------------
if args.undo:
    if not os.path.exists(undo_log_path):
        print("No undo log found. Nothing to undo.")
        exit()
        
    print("Undoing previous file moves...")
    
    with open(undo_log_path, "r") as f:
        lines = f.readlines()
        
    # Reverse order: last moved file gets undone first
    for line in reversed(lines):
        src, dest = line.strip().split(" -> ", 1)
        
        if os.path.exists(dest):
            print(f"Moving back: {dest} -> {src}")
            shutil.move(dest, src)
            
    print("Undo complete.")
    exit()



# -----------------------------
# Undo Log Setup
# -----------------------------
undo_log_path = "undo_log.txt"
undo_log = open(undo_log_path, "w")

# -----------------------------
# MAIN LOGIC
# -----------------------------
main_folder = args.path
dry_run = args.dry_run

# Build file list for progress bar
all_files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
total_files = len(all_files)
processed = 0

for item in all_files:
    item_path = os.path.join(main_folder, item)

    # Process file
    move_file(item_path, main_folder, dry_run)

    # Update progress                                   
    processed += 1
    percent = (processed / total_files) * 100
    bar_length = 40 
    filled = int(bar_length * processed / total_files)
    bar = "█" * filled + "-" * (bar_length - filled)

    print(f"/rProgress: |{bar}| {percent: 5.1f}% 9{processed}/{total_files})", end="")

print("/nOrganization complete.")
       
undo_log.close()