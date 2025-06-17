import os
import subprocess
import datetime

counter_file = "counter.txt"

def reset_counter_if_new_week():
    today = datetime.datetime.now().isocalendar()[1]
    if os.path.exists(counter_file):
        with open(counter_file) as f:
            saved_week, count = map(int, f.read().split(","))
        if saved_week != today:
            with open(counter_file, "w") as f:
                f.write(f"{today},0")
    else:
        with open(counter_file, "w") as f:
            f.write(f"{today},0")

def get_current_count():
    reset_counter_if_new_week()
    with open(counter_file) as f:
        _, count = f.read().split(",")
        return int(count)

def can_download_more():
    return get_current_count() < 500

def increase_count(n=1):
    week = datetime.datetime.now().isocalendar()[1]
    count = get_current_count()
    with open(counter_file, "w") as f:
        f.write(f"{week},{count+n}")

def download_spotify(link, single=True):
    folder = "downloads"
    os.makedirs(folder, exist_ok=True)
    os.chdir(folder)

    cmd = ["spotdl", "download", link]
    subprocess.call(cmd)

    songs = [f for f in os.listdir() if f.endswith(".mp3")]
    paths = [os.path.join(os.getcwd(), song) for song in songs]

    os.chdir("..")
    return paths