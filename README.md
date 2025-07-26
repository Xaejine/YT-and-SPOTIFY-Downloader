# Spotify & YouTube Downloader

A dual-interface application for downloading music/videos from YouTube and converting Spotify playlists to audio files. Includes both a modern GUI (PC) and a terminal-based interface (Termux).


---

FEATURES
- Download YouTube videos as MP4 or extract audio as MP3
- Convert entire Spotify playlists to MP3 with metadata
- Automatic embedding of metadata and album art
- Sleek desktop GUI and lightweight CLI for Termux
- Progress tracking and download resuming
- Customizable output directories

---

REQUIREMENTS

PC (GUI Version)
- Python 3.7+
- Install dependencies:
  pip install customtkinter spotipy
- yt-dlp installed and available in PATH:
  https://github.com/yt-dlp/yt-dlp

Termux (CLI Version)
- Python 3.7+
- Install via Termux:
  pkg install python
  pip install spotipy
  pkg install yt-dlp

---

INSTALLATION

git clone https://github.com/Xaejine/YT-and-SPOTIFY-Downloader.git
cd spotify-youtube-downloader

PC Version:
python GuiForPc.py

Termux Version:
python TermuxVersion.py

---

FIRST-TIME SETUP

Get Spotify API Credentials:
1. Go to: https://developer.spotify.com/dashboard/
2. Create a new app
3. Copy your Client ID and Client Secret
4. Run the app and enter credentials when prompted

---

HOW TO USE

PC (GUI) Version

YouTube Tab:
- Paste YouTube URL
- Select Music (MP3) or Video (MP4)
- Choose output folder
- Click "Download"

Spotify Tab:
- Paste Spotify playlist URL
- Playlist info loads automatically
- Click "Convert Playlist"

Termux (Menu) Version

1. Convert Spotify Playlist
2. Download Single YouTube Video/Music
3. Configure Spotify API
4. Set Output Directory
5. Exit

---

CONFIGURATION

All settings are saved in spotify_converter.cfg:

[Spotify]
client_id = your_client_id
client_secret = your_client_secret

[Settings]
output_path = /path/to/downloads
theme = dark  # PC version only

---

TROUBLESHOOTING

API Errors:
- Make sure Spotify credentials are valid

Download Fails:
- Check internet connection
- Update yt-dlp: yt-dlp -U

Metadata Issues:
- Install ffmpeg
  - PC: https://ffmpeg.org/
  - Termux: pkg install ffmpeg

---

FAQ

Q: Can I download private Spotify playlists?
A: No, only public playlists are supported.

Q: Why are some tracks missing?
A: The app searches YouTube for matches — obscure songs may not appear.

Q: How to change download quality?
A: Edit the source code (look for audio-quality or bestvideo flags)
