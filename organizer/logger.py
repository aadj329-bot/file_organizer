from datetime import datetime

def log(message, log_path="organizer_log.txt"):
    timestamp = datetime.now().strftime("%Y-%m-d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
        