import os
import sys
import re
import json
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import yt_dlp

# -------------------------------------------------
# -------------------------------------------------

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_ffmpeg_path():
    """
    Επιστρεφει το path του ffmpeg.exe.
    Ψαχνει δίπλα στο exe, μετα στο system PATH.
    """
    base_path = get_base_path()
    local_ffmpeg  = os.path.join(base_path, "ffmpeg.exe")
    local_ffprobe = os.path.join(base_path, "ffprobe.exe")

    if os.path.exists(local_ffmpeg) and os.path.exists(local_ffprobe):
        return local_ffmpeg

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return None


def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|+&%$#@!]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.strip('. ')
    return name or "download"


def load_settings():
    settings_file = os.path.join(get_base_path(), "settings.json")
    if os.path.exists(settings_file):
        with open(settings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"download_folder": os.path.join(get_base_path(), "Downloads")}


def save_settings(settings):
    settings_file = os.path.join(get_base_path(), "settings.json")
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f)


def convert_to_mp3(ffmpeg_exe, input_file, output_file):
    """
    Καλει ffmpeg χειροκινητα — ελεγχουμε ακριβως τι περναει,
    χωρις να εμπλεκεται το yt-dlp postprocessor.
    """
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", input_file,
        "-vn",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        output_file
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    return result.returncode == 0


def download_mp3(video_url, outdir, status_callback=None):
    ffmpeg_exe = get_ffmpeg_path()

    if not ffmpeg_exe:
        messagebox.showerror(
            "Σφαλμα",
            f"Δεν βρεθηκε ffmpeg!\n\n"
            f"Βαλε ffmpeg.exe + ffprobe.exe στον φακελο:\n{get_base_path()}"
        )
        if status_callback:
            status_callback("ffmpeg δεν βρεθηκε.", error=True)
        return

    # --- ΒΗΜΑ 1: Ανακτηση video ID και τιτλου ---
    if status_callback:
        status_callback("Ανακτηση πληροφοριων...", error=False)

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_id  = info.get("id", "download")
            raw_title = info.get("title", video_id)
    except Exception as e:
        if status_callback:
            status_callback("Αποτυχια ανακτησης.", error=True)
        messagebox.showerror("Σφαλμα", f"Αποτυχια ανακτησης:\n{str(e)}")
        return

    safe_title = sanitize_filename(raw_title)

    # --- ΒΗΜΑ 2: Κατεβασμα ηχου μονο, χωρίς postprocessor ---
    if status_callback:
        status_callback(f"Κατεβασμα: {safe_title}", error=False)

    base_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(outdir, f"{video_id}.%(ext)s"),
        "noplaylist": True,
        "postprocessors": [],   # κανενα postprocessor — ffmpeg το καλουμε εμεις
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
    }

    strategies = [
        ("ios",         {"extractor_args": {"youtube": {"player_client": ["ios"]}}}),
        ("android",     {"extractor_args": {"youtube": {"player_client": ["android"]}}}),
        ("ios+edge",    {"extractor_args": {"youtube": {"player_client": ["ios"]}}, "cookiesfrombrowser": ("edge",)}),
        ("ios+chrome",  {"extractor_args": {"youtube": {"player_client": ["ios"]}}, "cookiesfrombrowser": ("chrome",)}),
        ("ios+firefox", {"extractor_args": {"youtube": {"player_client": ["ios"]}}, "cookiesfrombrowser": ("firefox",)}),
    ]

    downloaded_file = None
    errors = []

    for label, extra in strategies:
        if status_callback:
            status_callback(f"Κατεβασμα ({label})...", error=False)
        try:
            with yt_dlp.YoutubeDL({**base_opts, **extra}) as ydl:
                ydl.download([video_url])

            # Βρισκουμε το αρχειο που κατεβηκε (π.χ. dQw4w9WgXcQ.webm)
            for f in os.listdir(outdir):
                if f.startswith(video_id) and not f.endswith(".mp3") and not f.endswith(".part"):
                    downloaded_file = os.path.join(outdir, f)
                    break
            if downloaded_file:
                break
        except Exception as e:
            errors.append(f"[{label}]: {e}")

    if not downloaded_file or not os.path.exists(downloaded_file):
        if status_callback:
            status_callback("Αποτυχια ληψης.", error=True)
        detail = "\n\n".join(errors[-2:])
        messagebox.showerror("Σφαλμα", f"Αποτυχια ληψης:\n\n{detail}")
        return

    # --- ΒΗΜΑ 3: Μετατροπη σε MP3 με απευθειας κληση ffmpeg ---
    if status_callback:
        status_callback("Μετατροπη σε MP3...", error=False)

    mp3_path = os.path.join(outdir, f"{safe_title}.mp3")
    if os.path.exists(mp3_path):
        mp3_path = os.path.join(outdir, f"{safe_title} [{video_id}].mp3")

    success = convert_to_mp3(ffmpeg_exe, downloaded_file, mp3_path)

    try:
        os.remove(downloaded_file)
    except Exception:
        pass

    if not success:
        if status_callback:
            status_callback("Αποτυχια μετατροπης.", error=True)
        messagebox.showerror("Σφαλμα", "Η μετατροπη σε MP3 απετυχε.")
        return

    if status_callback:
        status_callback("Ολοκληρωθηκε!", error=False)
    messagebox.showinfo(
        "Ολοκληρωθηκε",
        f"Επιτυχης ληψη!\n\n"
        f"Αρχειο: {os.path.basename(mp3_path)}\n"
        f"Φακελος: {outdir}"
    )


# -------------------------------------------------
#  GUI
# -------------------------------------------------

class YTDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube to MP3 Downloader")
        self.root.geometry("520x310")
        self.root.resizable(False, False)

        self.settings = load_settings()
        os.makedirs(self.settings["download_folder"], exist_ok=True)

        self._build_ui()
        self._check_ffmpeg_on_startup()

    def _build_ui(self):
        pad = {"padx": 20, "pady": 5}

        tk.Label(
            self.root,
            text="YouTube to MP3 Downloader",
            font=("Arial", 13, "bold"),
            fg="#c0392b"
        ).pack(pady=(15, 5))

        tk.Label(self.root, text="YouTube URL:").pack(**pad)
        self.url_entry = tk.Entry(self.root, width=55, font=("Arial", 10))
        self.url_entry.pack(padx=20, pady=2)

        self.download_btn = tk.Button(
            self.root,
            text="Κατεβασμα MP3",
            command=self.start_download,
            bg="#c0392b",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=20,
            pady=6,
            relief="flat",
            cursor="hand2"
        )
        self.download_btn.pack(pady=12)

        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            fg="#555555",
            font=("Arial", 9),
            wraplength=480
        )
        self.status_label.pack()

        tk.Frame(self.root, height=1, bg="#dddddd").pack(fill="x", padx=20, pady=10)

        tk.Label(self.root, text="Φακελος ληψεων:", font=("Arial", 9, "bold")).pack(anchor="w", padx=20)
        self.folder_label = tk.Label(
            self.root,
            text=self.settings["download_folder"],
            fg="#333333",
            wraplength=460,
            justify="left",
            font=("Arial", 9)
        )
        self.folder_label.pack(anchor="w", padx=20, pady=2)

        tk.Button(
            self.root,
            text="Αλλαγη φακελου...",
            command=self.change_folder,
            font=("Arial", 9),
            cursor="hand2"
        ).pack(pady=5)

    def _check_ffmpeg_on_startup(self):
        if not get_ffmpeg_path():
            messagebox.showwarning(
                "ffmpeg δεν βρεθηκε",
                f"Βαλε ffmpeg.exe + ffprobe.exe στον φακελο:\n{get_base_path()}\n\n"
                f"Ληψη: https://www.gyan.dev/ffmpeg/builds/"
            )
            self.set_status("ffmpeg δεν βρεθηκε!", error=True)

    def set_status(self, text, error=False):
        self.status_var.set(text)
        self.status_label.config(fg="#c0392b" if error else "#27ae60")
        self.root.update_idletasks()

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Προσοχη", "Παρακαλω εισαγετε URL.")
            return

        self.download_btn.config(state="disabled", text="Γινεται ληψη...")
        self.set_status("Παρακαλω περιμενετε...", error=False)

        def run():
            download_mp3(url, self.settings["download_folder"], self.set_status)
            self.download_btn.config(state="normal", text="Κατεβασμα MP3")
            self.url_entry.delete(0, tk.END)

        threading.Thread(target=run, daemon=True).start()

    def change_folder(self):
        new_folder = filedialog.askdirectory(title="Επιλεξτε φακελο")
        if new_folder:
            self.settings["download_folder"] = new_folder
            save_settings(self.settings)
            self.folder_label.config(text=new_folder)
            messagebox.showinfo("OK", "Ο φακελος ληψεων αλλαξε.")


# -------------------------------------------------
# -------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = YTDownloaderApp(root)
    root.mainloop()
