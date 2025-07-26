import customtkinter as ctk
import threading
import subprocess
import os
import shutil
import glob
import json
import time
import re
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import datetime
from typing import Optional, Dict, Any, List
from tkinter import filedialog, PhotoImage, messagebox
from pathlib import Path
import configparser
import sys


CONFIG_FILE = "spotify_converter.cfg"
DEFAULT_CONFIG = {
    "Spotify": {"client_id": "", "client_secret": ""},
    "Settings": {
        "output_path": os.path.expanduser("~/Downloads"),
        "theme": "dark",
        "color_theme": "blue",
        "download_type": "music",
    },
}


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class SpotifyToYouTubeConverter(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings_window = None

        self.config = self.load_config()

        self.spotify_client_id = self.config["Spotify"]["client_id"]
        self.spotify_client_secret = self.config["Spotify"]["client_secret"]
        self.spotify = None

        self.setup_ui()

        if self.spotify_client_id and self.spotify_client_secret:
            self.initialize_spotify_client()

        self.download_thread: Optional[threading.Thread] = None
        self.current_process: Optional[subprocess.Popen] = None
        self.active_downloads: Dict[str, Any] = {}
        self.stop_requested = False

    def load_config(self) -> configparser.ConfigParser:

        config = configparser.ConfigParser()

        if not os.path.exists(CONFIG_FILE):
            config.read_dict(DEFAULT_CONFIG)
            try:
                with open(CONFIG_FILE, "w") as configfile:
                    config.write(configfile)
            except Exception as e:
                print(f"Error creating config file: {e}")
        else:
            try:
                config.read(CONFIG_FILE)
            except Exception as e:
                print(f"Error reading config file: {e}")

                config.read_dict(DEFAULT_CONFIG)

        for section, options in DEFAULT_CONFIG.items():
            if section not in config:
                config[section] = {}
            for key, value in options.items():
                if key not in config[section]:
                    config[section][key] = value

        return config

    def save_config(self):

        try:
            with open(CONFIG_FILE, "w") as configfile:
                self.config.write(configfile)
            print("Config saved successfully")
            return True
        except Exception as e:
            print(f"Error saving config file: {e}")
            return False

    def setup_ui(self):

        self.title("Spotify And YT Downloader")
        self.geometry("900x700")
        self.resizable(True, True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=(20, 0), sticky="nsew")

        self.tab_single = self.tabview.add("Youtube Download")
        self.tab_playlist = self.tabview.add("Spotify Download")

        self.setup_single_download_tab()

        self.setup_spotify_playlist_tab()

        self.progress_box = ctk.CTkTextbox(self, wrap="word")
        self.progress_box.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="nsew")

        self.progress_box.insert("end", "Spotify to YouTube Music Converter     \n")

        self.progress_box.insert(
            "end", f"Initialized at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        if not self.spotify_client_id or not self.spotify_client_secret:
            self.progress_box.insert(
                "end", "⚠️ Warning: Spotify API credentials not configured\n"
            )

        self.progress_box.insert("end", "\n")
        self.progress_box.configure(state="disabled")

        self.progress_box.tag_config("log_info", foreground="white")
        self.progress_box.tag_config("log_success", foreground="#2ecc71")
        self.progress_box.tag_config("log_warning", foreground="#f39c12")
        self.progress_box.tag_config("log_error", foreground="#e74c3c")
        self.progress_box.tag_config("log_debug", foreground="#3498db")
        self.progress_box.tag_config("log_important", foreground="#f1c40f")

        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_bar.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.stop_button = ctk.CTkButton(
            self.button_frame,
            text="⏹ Stop",
            fg_color="#e74c3c",
            hover_color="#c0392b",
            command=self.stop_download,
            state="disabled",
        )
        self.stop_button.pack(side="left", expand=True, padx=(0, 10))

        self.clear_logs_btn = ctk.CTkButton(
            self.button_frame, text="🧹 Clear Logs", command=self.clear_logs
        )
        self.clear_logs_btn.pack(side="left", expand=True, padx=(0, 10))

        self.settings_btn = ctk.CTkButton(
            self.button_frame, text="⚙️ Settings", command=self.open_settings
        )
        self.settings_btn.pack(side="left", expand=True)

    def setup_single_download_tab(self):

        self.download_type = ctk.StringVar(
            value=self.config["Settings"].get("download_type", "music")
        )
        self.output_path = ctk.StringVar(value=self.config["Settings"]["output_path"])

        self.url_frame = ctk.CTkFrame(self.tab_single)
        self.url_frame.pack(pady=(10, 5), padx=10, fill="x")

        self.url_entry = ctk.CTkEntry(
            self.url_frame, placeholder_text="Enter YouTube URL", height=35
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.clear_url_btn = ctk.CTkButton(
            self.url_frame,
            text="🗑️",
            width=40,
            command=lambda: self.url_entry.delete(0, "end"),
        )
        self.clear_url_btn.pack(side="right")

        self.options_frame = ctk.CTkFrame(self.tab_single)
        self.options_frame.pack(pady=5, padx=10, fill="x")

        ctk.CTkLabel(self.options_frame, text="Download Type:").pack(
            side="left", padx=(0, 10)
        )
        ctk.CTkRadioButton(
            self.options_frame,
            text="🎵 Music (MP3)",
            variable=self.download_type,
            value="music",
            command=self.save_download_type,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(
            self.options_frame,
            text="🎬 Video (MP4)",
            variable=self.download_type,
            value="video",
            command=self.save_download_type,
        ).pack(side="left", padx=(0, 20))

        ctk.CTkLabel(self.options_frame, text="Save to:").pack(
            side="left", padx=(20, 10)
        )
        self.path_entry = ctk.CTkEntry(
            self.options_frame, textvariable=self.output_path, height=35
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.browse_btn = ctk.CTkButton(
            self.options_frame, text="📁", width=40, command=self.browse_output_path
        )
        self.browse_btn.pack(side="right")

        self.download_button = ctk.CTkButton(
            self.tab_single,
            text="⬇️ Download",
            command=self.start_single_download,
            fg_color="#2ecc71",
            hover_color="#27ae60",
        )
        self.download_button.pack(pady=10)

    def setup_spotify_playlist_tab(self):

        self.playlist_frame = ctk.CTkFrame(self.tab_playlist)
        self.playlist_frame.pack(pady=(10, 5), padx=10, fill="x")

        self.playlist_entry = ctk.CTkEntry(
            self.playlist_frame,
            placeholder_text="Enter Spotify Playlist URL",
            height=35,
        )
        self.playlist_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.clear_playlist_btn = ctk.CTkButton(
            self.playlist_frame,
            text="🗑️",
            width=40,
            command=lambda: self.playlist_entry.delete(0, "end"),
        )
        self.clear_playlist_btn.pack(side="right")

        self.playlist_options_frame = ctk.CTkFrame(self.tab_playlist)
        self.playlist_options_frame.pack(pady=5, padx=10, fill="x")

        ctk.CTkLabel(self.playlist_options_frame, text="Save to:").pack(
            side="left", padx=(0, 10)
        )
        self.playlist_path_entry = ctk.CTkEntry(
            self.playlist_options_frame, textvariable=self.output_path, height=35
        )
        self.playlist_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.playlist_browse_btn = ctk.CTkButton(
            self.playlist_options_frame,
            text="📁",
            width=40,
            command=self.browse_output_path,
        )
        self.playlist_browse_btn.pack(side="right")

        self.playlist_info_frame = ctk.CTkFrame(self.tab_playlist)
        self.playlist_info_frame.pack(pady=5, padx=10, fill="x")

        self.playlist_name_label = ctk.CTkLabel(
            self.playlist_info_frame,
            text="📋 Playlist: Not loaded",
            font=ctk.CTkFont(weight="bold"),
        )
        self.playlist_name_label.pack(side="left", padx=5)

        self.track_count_label = ctk.CTkLabel(
            self.playlist_info_frame,
            text="🎵 Tracks: 0",
            font=ctk.CTkFont(weight="bold"),
        )
        self.track_count_label.pack(side="left", padx=5)

        self.owner_label = ctk.CTkLabel(
            self.playlist_info_frame, text="👤 Owner: ", font=ctk.CTkFont(weight="bold")
        )
        self.owner_label.pack(side="left", padx=5)

        self.convert_button = ctk.CTkButton(
            self.tab_playlist,
            text="♫ Convert Playlist",
            command=self.start_playlist_conversion,
            fg_color="#9b59b6",
            hover_color="#8e44ad",
        )
        self.convert_button.pack(pady=10)

    def browse_output_path(self):

        path = filedialog.askdirectory(initialdir=self.output_path.get())
        if path:
            self.output_path.set(path)
            self.config["Settings"]["output_path"] = path
            self.save_config()

    def save_download_type(self):

        self.config["Settings"]["download_type"] = self.download_type.get()
        self.save_config()

    def log(self, message: str, level: str = "info"):

        timestamp = datetime.now().strftime("%H:%M:%S")
        level_icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "debug": "🐛",
        }

        icon = level_icons.get(level, "ℹ️")
        tag = f"log_{level}"

        self.progress_box.configure(state="normal")
        self.progress_box.insert("end", f"[{timestamp}] {icon} {message}\n", tag)
        self.progress_box.see("end")
        self.progress_box.configure(state="disabled")

        if level in ("success", "error", "warning"):
            self.status_bar.configure(text=message)

    def clear_logs(self):

        self.progress_box.configure(state="normal")
        self.progress_box.delete("1.0", "end")
        self.progress_box.insert("end", "Spotify to YouTube Music Converter     \n")
        self.progress_box.insert(
            "end", f"Logs cleared at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        self.progress_box.configure(state="disabled")
        self.status_bar.configure(text="Logs cleared")

    def open_settings(self):

        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = ctk.CTkToplevel(self)
        self.settings_window.title("Settings")
        self.settings_window.geometry("500x400")
        self.settings_window.resizable(False, False)
        self.settings_window.attributes("-topmost", True)
        self.settings_window.protocol("WM_DELETE_WINDOW", self.on_settings_close)
        self.center_window(self.settings_window)

        spotify_frame = ctk.CTkFrame(self.settings_window)
        spotify_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(
            spotify_frame,
            text="🔑 Spotify API Settings",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(spotify_frame, text="Client ID:").pack(anchor="w")
        self.client_id_entry = ctk.CTkEntry(spotify_frame)
        self.client_id_entry.pack(fill="x", pady=(0, 10))
        self.client_id_entry.insert(0, self.spotify_client_id)

        ctk.CTkLabel(spotify_frame, text="Client Secret:").pack(anchor="w")
        self.client_secret_entry = ctk.CTkEntry(spotify_frame, show="*")
        self.client_secret_entry.pack(fill="x", pady=(0, 10))
        self.client_secret_entry.insert(0, self.spotify_client_secret)

        appearance_frame = ctk.CTkFrame(self.settings_window)
        appearance_frame.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(
            appearance_frame,
            text="🎨 Appearance",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(0, 10))

        ctk.CTkLabel(appearance_frame, text="Theme:").pack(anchor="w")
        self.theme_var = ctk.StringVar(value=self.config["Settings"]["theme"])
        theme_menu = ctk.CTkOptionMenu(
            appearance_frame,
            values=["dark", "light", "system"],
            variable=self.theme_var,
        )
        theme_menu.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(appearance_frame, text="Color Theme:").pack(anchor="w")
        self.color_theme_var = ctk.StringVar(
            value=self.config["Settings"]["color_theme"]
        )
        color_theme_menu = ctk.CTkOptionMenu(
            appearance_frame,
            values=["blue", "green", "dark-blue"],
            variable=self.color_theme_var,
        )
        color_theme_menu.pack(fill="x", pady=(0, 10))

        save_btn = ctk.CTkButton(
            self.settings_window,
            text="💾 Save Settings",
            command=self.save_settings,
            fg_color="#2ecc71",
            hover_color="#27ae60",
        )
        save_btn.pack(pady=10)

    def center_window(self, window):

        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def on_settings_close(self):

        self.settings_window.destroy()
        self.settings_window = None

    def save_settings(self):

        client_id = self.client_id_entry.get().strip()
        client_secret = self.client_secret_entry.get().strip()
        theme = self.theme_var.get()
        color_theme = self.color_theme_var.get()

        if not client_id or not client_secret:
            messagebox.showerror(
                "Error", "Both Client ID and Client Secret are required!"
            )
            return

        self.config["Spotify"]["client_id"] = client_id
        self.config["Spotify"]["client_secret"] = client_secret
        self.config["Settings"]["theme"] = theme
        self.config["Settings"]["color_theme"] = color_theme

        if self.save_config():

            self.spotify_client_id = client_id
            self.spotify_client_secret = client_secret

            ctk.set_appearance_mode(theme)
            ctk.set_default_color_theme(color_theme)

            self.initialize_spotify_client()

            self.log("Settings saved and applied successfully", "success")
            messagebox.showinfo("Success", "Settings saved successfully!")
        else:
            messagebox.showerror("Error", "Failed to save settings!")

    def initialize_spotify_client(self):

        try:
            if not self.spotify_client_id or not self.spotify_client_secret:
                self.log("Spotify credentials not configured", "warning")
                return

            auth_manager = SpotifyClientCredentials(
                client_id=self.spotify_client_id,
                client_secret=self.spotify_client_secret,
            )
            self.spotify = spotipy.Spotify(auth_manager=auth_manager)
            self.log("Spotify client initialized successfully", "success")
        except Exception as e:
            self.log(f"Failed to initialize Spotify client: {str(e)}", "error")
            self.spotify = None

    def start_single_download(self):

        url = self.url_entry.get().strip()
        if not url:
            self.log("Please enter a valid URL.", "error")
            return

        if self.download_thread and self.download_thread.is_alive():
            self.log("A download is already in progress.", "warning")
            return

        self.download_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        self.download_thread = threading.Thread(
            target=self.download_single, args=(url,), daemon=True
        )
        self.download_thread.start()

    def start_playlist_conversion(self):

        playlist_url = self.playlist_entry.get().strip()
        if not playlist_url:
            self.log("Please enter a valid Spotify playlist URL.", "error")
            return

        if not self.spotify:
            self.log(
                "Spotify client not initialized. Please check your API credentials in Settings.",
                "error",
            )
            return

        if self.download_thread and self.download_thread.is_alive():
            self.log("A download is already in progress.", "warning")
            return

        self.convert_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        self.download_thread = threading.Thread(
            target=self.convert_spotify_playlist, args=(playlist_url,), daemon=True
        )
        self.download_thread.start()

    def download_single(self, url: str):

        try:
            download_type = self.download_type.get()
            output_path = self.output_path.get()

            if not os.path.exists(output_path):
                os.makedirs(output_path)
                self.log(f"Created output directory: {output_path}", "info")

            output_template = os.path.join(output_path, "%(title)s.%(ext)s")

            command = [
                "yt-dlp",
                "--newline",
                "--progress-template",
                "json",
                "--no-playlist",
                "-o",
                output_template,
            ]

            if download_type == "music":
                command.extend(
                    [
                        "-x",
                        "--audio-format",
                        "mp3",
                        "--audio-quality",
                        "192K",
                        "--embed-thumbnail",
                        "--add-metadata",
                        "--embed-metadata",
                        "--metadata-from-title",
                        "%(artist)s - %(title)s",
                        "--prefer-ffmpeg",
                    ]
                )
            else:
                command.extend(
                    [
                        "-f",
                        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                        "--merge-output-format",
                        "mp4",
                    ]
                )

            command.append(url)

            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
            )

            for line in self.current_process.stdout:
                self.parse_progress(line.strip())

            return_code = self.current_process.wait()

            if return_code == 0:
                self.log("Download completed successfully", "success")
                if download_type == "music":
                    self.post_process_mp3s(output_path)
            else:
                self.log(f"Download failed with return code {return_code}", "error")

        except Exception as e:
            self.log(f"Error during download: {str(e)}", "error")
        finally:
            self.current_process = None
            self.after(0, lambda: self.download_button.configure(state="normal"))
            self.after(0, lambda: self.convert_button.configure(state="normal"))
            self.after(0, lambda: self.stop_button.configure(state="disabled"))

    def extract_spotify_playlist_id(self, url: str) -> Optional[str]:

        patterns = [
            r"open\.spotify\.com/playlist/([a-zA-Z0-9]+)",
            r"spotify:playlist:([a-zA-Z0-9]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def convert_spotify_playlist(self, playlist_url: str):

        try:
            self.stop_requested = False

            playlist_id = self.extract_spotify_playlist_id(playlist_url)
            if not playlist_id:
                self.log("Invalid Spotify playlist URL", "error")
                return

            try:

                playlist = self.spotify.playlist(playlist_id)
            except spotipy.SpotifyException as e:
                if e.http_status == 404:
                    self.log(
                        "Playlist not found. It may be private or deleted.", "error"
                    )
                elif e.http_status == 403:
                    self.log(
                        "Access denied. Check your Spotify API credentials.", "error"
                    )
                else:
                    self.log(f"Spotify API error: {str(e)}", "error")
                return
            except Exception as e:
                self.log(f"Error accessing playlist: {str(e)}", "error")
                return

            playlist = self.spotify.playlist(playlist_id)
            playlist_name = playlist.get("name", "Unknown Playlist")
            owner = playlist.get("owner", {}).get("display_name", "Unknown")
            total_tracks = playlist.get("tracks", {}).get("total", 0)

            self.after(
                0,
                lambda: self.playlist_name_label.configure(
                    text=f"📋 Playlist: {playlist_name}"
                ),
            )
            self.after(0, lambda: self.owner_label.configure(text=f"👤 Owner: {owner}"))
            self.after(
                0,
                lambda: self.track_count_label.configure(
                    text=f"🎵 Tracks: {total_tracks}"
                ),
            )

            self.log(f"Converting playlist: {playlist_name}", "info")
            self.log(f"Owner: {owner}", "info")
            self.log(f"Total tracks: {total_tracks}", "info")

            output_path = os.path.join(
                self.output_path.get(), self.sanitize_filename(playlist_name)
            )
            if not os.path.exists(output_path):
                os.makedirs(output_path)
                self.log(f"Created playlist directory: {output_path}", "info")

            results = self.spotify.playlist_tracks(playlist_id)
            tracks = results.get("items", [])

            while results.get("next"):
                results = self.spotify.next(results)
                tracks.extend(results.get("items", []))

            success_count = 0

            for i, item in enumerate(tracks, 1):
                if self.stop_requested:
                    self.log(
                        f"\nDownload stopped by user after {success_count} tracks",
                        "warning",
                    )
                    break

                track = item.get("track", {})
                if not track:
                    continue

                track_name = track.get("name", "Unknown Track")
                artists = ", ".join(
                    [artist["name"] for artist in track.get("artists", [])]
                )

                self.log(
                    f"\nDownloading track {i}/{len(tracks)}: {artists} - {track_name}",
                    "info",
                )

                expected_filename = f"{artists} - {track_name}.mp3"
                expected_path = os.path.join(
                    output_path, self.sanitize_filename(expected_filename)
                )
                if os.path.exists(expected_path):
                    self.log(
                        f"Track already exists, skipping: {expected_filename}", "info"
                    )
                    success_count += 1
                    continue

                if self.download_from_search(f"{artists} {track_name}", output_path):
                    success_count += 1

            if success_count == len(tracks):
                self.log(
                    f"\n🎉 Playlist conversion complete: {success_count} tracks downloaded",
                    "success",
                )
            else:
                self.log(
                    f"\n⚠️ Partial conversion: {success_count} of {len(tracks)} tracks downloaded",
                    "warning",
                )

        except Exception as e:
            self.log(f"Error during playlist conversion: {str(e)}", "error")
        finally:
            self.stop_requested = False
            self.current_process = None
            self.after(0, lambda: self.convert_button.configure(state="normal"))
            self.after(0, lambda: self.stop_button.configure(state="disabled"))

    def download_from_search(self, search_query: str, output_path: str) -> bool:

        try:
            output_template = os.path.join(output_path, "%(title)s.%(ext)s")

            command = [
                "yt-dlp",
                "--newline",
                "--progress-template",
                "json",
                "--no-playlist",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "192K",
                "--embed-thumbnail",
                "--add-metadata",
                "--embed-metadata",
                "--parse-metadata",
                "title:%(artist)s - %(title)s",
                "--prefer-ffmpeg",
                "-o",
                output_template,
                f"ytsearch1:{search_query} official audio",
            ]

            self.log(f"Searching for: {search_query}", "debug")
            self.log(f"Executing command: {' '.join(command)}", "debug")

            self.current_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
            )

            for line in self.current_process.stdout:
                self.parse_progress(line.strip())

            return_code = self.current_process.wait()

            if return_code == 0:
                self.log("Track downloaded successfully", "success")
                return True
            else:
                self.log(
                    f"Track download failed with return code {return_code}", "error"
                )
                return False

        except Exception as e:
            self.log(f"Error during track download: {str(e)}", "error")
            return False

    def sanitize_filename(self, filename: str) -> str:

        return re.sub(r'[\\/*?:"<>|]', "_", filename)

    def stop_download(self):

        self.stop_requested = True
        if self.current_process:
            self.log("Stopping download process...", "warning")
            try:
                self.current_process.terminate()
                time.sleep(1)
                if self.current_process.poll() is None:
                    self.current_process.kill()
                self.log("Download stopped by user", "warning")
            except Exception as e:
                self.log(f"Error stopping process: {str(e)}", "error")
            finally:
                self.current_process = None
                self.after(0, lambda: self.download_button.configure(state="normal"))
                self.after(0, lambda: self.convert_button.configure(state="normal"))
                self.after(0, lambda: self.stop_button.configure(state="disabled"))

    def parse_progress(self, line: str):

        try:
            if not line:
                return

            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    self.handle_progress_data(data)
                    return
                except json.JSONDecodeError:
                    pass

            if "ERROR" in line:
                self.log(line, "error")
            elif "WARNING" in line:
                self.log(line, "warning")
            elif "Downloading" in line or "Merging" in line:
                self.log(line, "info")
            else:
                self.log(line, "debug")

        except Exception as e:
            self.log(f"Error parsing progress: {str(e)}", "error")

    def handle_progress_data(self, data: Dict[str, Any]):

        if "status" in data:
            status = data["status"]

            if status == "downloading":
                progress = data.get("progress", {})
                percent = progress.get("percent", 0)
                speed = progress.get("speed", "N/A")
                eta = progress.get("eta", "N/A")

                self.log(
                    f"Downloading: {percent:.1f}% complete | "
                    f"Speed: {self.format_speed(speed)} | "
                    f"ETA: {self.format_eta(eta)}",
                    "info",
                )

            elif status == "finished":
                self.log("Post-processing complete", "success")

            elif status == "error":
                self.log(f"Error: {data.get('message', 'Unknown error')}", "error")

    def format_speed(self, speed: Any) -> str:

        if speed == "N/A":
            return speed

        try:
            speed = float(speed)
            if speed < 1024:
                return f"{speed:.1f} B/s"
            elif speed < 1024 * 1024:
                return f"{speed / 1024:.1f} KB/s"
            else:
                return f"{speed / (1024 * 1024):.1f} MB/s"
        except:
            return str(speed)

    def format_eta(self, eta: Any) -> str:

        if eta == "N/A":
            return eta

        try:
            eta = int(eta)
            if eta < 60:
                return f"{eta}s"
            elif eta < 3600:
                return f"{eta // 60}m {eta % 60}s"
            else:
                return f"{eta // 3600}h {(eta % 3600) // 60}m"
        except:
            return str(eta)

    def post_process_mp3s(self, output_path: str):

        try:
            mp3_files = glob.glob(os.path.join(output_path, "*.mp3"))

            if not mp3_files:
                self.log("No MP3 files found for post-processing", "warning")
                return

            self.log(f"Found {len(mp3_files)} MP3 file(s) for post-processing", "info")
            self.log("MP3 post-processing complete", "success")

        except Exception as e:
            self.log(f"Error during MP3 post-processing: {str(e)}", "error")


if __name__ == "__main__":

    try:
        subprocess.run(["yt-dlp", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        messagebox.showerror(
            "Error",
            "yt-dlp is not installed or not in PATH. Please install it first.",
        )
        sys.exit(1)

    app = SpotifyToYouTubeConverter()
    app.mainloop()
