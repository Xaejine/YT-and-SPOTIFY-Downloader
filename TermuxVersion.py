import os
import re
import sys
import json
import time
import glob
import configparser
import subprocess
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


CONFIG_FILE = "spotify_converter.cfg"
DEFAULT_CONFIG = {
    "Spotify": {"client_id": "", "client_secret": ""},
    "Settings": {"output_path": str(Path.home() / "downloads")},
}


def log(message, level="info"):
    icons = {
        "info": "[*]",
        "success": "[+]",
        "error": "[x]",
        "warning": "[!]",
    }
    print(f"{icons.get(level, '[*]')} {message}")


def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        config.read_dict(DEFAULT_CONFIG)
        with open(CONFIG_FILE, "w") as f:
            config.write(f)
    else:
        config.read(CONFIG_FILE)
        for section in DEFAULT_CONFIG:
            if section not in config:
                config[section] = {}
            for key, val in DEFAULT_CONFIG[section].items():
                if key not in config[section]:
                    config[section][key] = val
    return config


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        config.write(f)


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)


def initialize_spotify_client(config):
    try:
        cid = config["Spotify"]["client_id"]
        secret = config["Spotify"]["client_secret"]
        if not cid or not secret:
            log("Spotify API credentials not set. Configure them first.", "error")
            return None
        auth = SpotifyClientCredentials(client_id=cid, client_secret=secret)
        return spotipy.Spotify(auth_manager=auth)
    except Exception as e:
        log(f"Spotify client error: {e}", "error")
        return None


def download_youtube(query, output_path, is_video=False):
    output_template = os.path.join(output_path, "%(title)s.%(ext)s")
    command = [
        "yt-dlp", "--newline", "--progress-template", "json", "--no-playlist",
        "-o", output_template
    ]

    if is_video:
        command += ["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best", "--merge-output-format", "mp4"]
        command.append(query)
    else:
        command += [
            "-x", "--audio-format", "mp3", "--audio-quality", "192K",
            "--embed-thumbnail", "--add-metadata", "--embed-metadata",
            "--prefer-ffmpeg",
        ]
        command.append(f"ytsearch1:{query} official audio")

    log(f"Running: {' '.join(command)}", "info")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line.strip())
    return process.wait() == 0


def convert_spotify_playlist(spotify, url, output_dir):
    playlist_id = re.search(r"(?:playlist/|playlist:)([a-zA-Z0-9]+)", url)
    if not playlist_id:
        log("Invalid Spotify playlist URL", "error")
        return

    try:
        playlist = spotify.playlist(playlist_id.group(1))
        name = sanitize_filename(playlist["name"])
        full_path = os.path.join(output_dir, name)
        os.makedirs(full_path, exist_ok=True)

        log(f"Playlist: {name}")
        tracks = playlist["tracks"]["items"]
        while playlist["tracks"]["next"]:
            playlist["tracks"] = spotify.next(playlist["tracks"])
            tracks += playlist["tracks"]["items"]

        for i, item in enumerate(tracks, 1):
            track = item["track"]
            title = track["name"]
            artist = ", ".join([a["name"] for a in track["artists"]])
            query = f"{artist} - {title}"

            filename = os.path.join(full_path, sanitize_filename(f"{query}.mp3"))
            if os.path.exists(filename):
                log(f"[{i}] Skipping (already exists): {query}")
                continue

            log(f"[{i}] Downloading: {query}")
            success = download_youtube(query, full_path)
            if not success:
                log(f"Failed: {query}", "warning")
    except Exception as e:
        log(f"Error converting playlist: {e}", "error")


def download_single():
    url = input("Enter YouTube URL: ").strip()
    if not url.startswith("http"):
        log("Invalid URL", "error")
        return

    vtype = input("Download as (m)usic or (v)ideo? [m/v]: ").lower().strip()
    is_video = vtype == "v"
    config = load_config()
    output_path = config["Settings"]["output_path"]
    os.makedirs(output_path, exist_ok=True)

    download_youtube(url, output_path, is_video)


def menu():
    config = load_config()
    while True:
        print("\n====== Spotify ↔ YouTube Converter ======")
        print("1. Convert Spotify Playlist")
        print("2. Download Single YouTube Video or Music")
        print("3. Configure Spotify API")
        print("4. Set Output Directory")
        print("5. Exit")
        choice = input("Choose an option (1-5): ").strip()

        if choice == "1":
            spotify = initialize_spotify_client(config)
            if not spotify:
                continue
            url = input("Enter Spotify Playlist URL: ").strip()
            output_path = config["Settings"]["output_path"]
            convert_spotify_playlist(spotify, url, output_path)

        elif choice == "2":
            download_single()

        elif choice == "3":
            cid = input("Enter Spotify Client ID: ").strip()
            secret = input("Enter Spotify Client Secret: ").strip()
            config["Spotify"]["client_id"] = cid
            config["Spotify"]["client_secret"] = secret
            save_config(config)
            log("Spotify credentials saved.", "success")

        elif choice == "4":
            path = input("Enter output directory path: ").strip()
            if not os.path.exists(path):
                try:
                    os.makedirs(path)
                except:
                    log("Invalid directory or permission denied.", "error")
                    continue
            config["Settings"]["output_path"] = path
            save_config(config)
            log(f"Output path set to {path}", "success")

        elif choice == "5":
            print("Goodbye!")
            break
        else:
            log("Invalid choice. Try again.", "warning")


if __name__ == "__main__":
    try:
        subprocess.run(["yt-dlp", "--version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[x] yt-dlp is not installed. Run:")
        print("    pkg install yt-dlp -y")
        sys.exit(1)

    try:
        import spotipy
    except ImportError:
        print("[x] spotipy is not installed. Run:")
        print("    pip install spotipy")
        sys.exit(1)

    menu()
