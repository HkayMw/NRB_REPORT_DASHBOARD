"""Build the narrated how-to video from page screenshots + TTS narration."""
import os
import subprocess
import wave

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames")
AUDIO = os.path.join(HERE, "audio")
SEGS = os.path.join(HERE, "segs")
os.makedirs(SEGS, exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H = 1280, 720

BG = (14, 17, 23)
ACCENT = (255, 75, 75)
TEXT = (240, 242, 246)
MUTED = (160, 168, 180)

FONT_BOLD = r"C:\Windows\Fonts\segoeuib.ttf"
FONT_REG = r"C:\Windows\Fonts\segoeui.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def make_card(path, title, lines, kicker=""):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 8, H], fill=ACCENT)
    y = 150
    if kicker:
        d.text((100, y), kicker.upper(), font=font(FONT_BOLD, 26), fill=ACCENT)
        y += 60
    for part in title.split("\n"):
        d.text((100, y), part, font=font(FONT_BOLD, 58), fill=TEXT)
        y += 78
    y += 30
    for line in lines:
        d.text((100, y), line, font=font(FONT_REG, 32), fill=MUTED)
        y += 52
    img.save(path)


def banner(src, dst, step, label):
    img = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, H - 64, W, H], fill=(10, 12, 16, 235))
    d.rectangle([0, H - 64, 8, H], fill=ACCENT + (255,))
    d.text((28, H - 52), step, font=font(FONT_BOLD, 28), fill=ACCENT)
    d.text((190, H - 52), label, font=font(FONT_REG, 28), fill=TEXT)
    img.save(dst)


SCENES = [
    ("card_title", None, None, None,
     "Welcome to the Mzuzu N R B Report Dashboard. This short video shows how to "
     "use the system during the trial phase. First, the important part: daily "
     "reporting does not change. Keep submitting the daily Google form exactly as "
     "before. The dashboard picks up every submission automatically."),
    ("dashboard", "STEP 1", "Live Dashboard — totals, trends and breakdowns", None,
     "This is the Live Dashboard, which anyone can open at any time. It shows "
     "totals for any date range: I Ds captured, I Ds distributed, and birth and "
     "death certificate applications. Use the date range filter on the left, and "
     "press refresh data now to pull the very latest submissions. The tabs switch "
     "between trends over time, section activity, and a field by field breakdown."),
    ("compliance", "STEP 2", "Compliance — who reported, what was covered", None,
     "The Compliance page answers who reported what. Each row is a day and each "
     "column is a section. Green means a report came in. Red means nothing was "
     "submitted that day. The People tab shows each person's submissions, and the "
     "scheduled versus reported tab compares the work schedule against what "
     "actually came in."),
    ("quality", "STEP 3", "Data Quality — duplicates and problems", None,
     "The Data Quality page flags problems automatically: duplicate submissions, "
     "which are removed by keeping the latest copy, rows with names that don't "
     "match the staff list, future dates, and possible double counting. Have a "
     "look at this page now and then during the trial, and report anything odd."),
    ("monthly", "STEP 4", "Monthly Report — one-click Excel export", None,
     "The Monthly Report page replaces the old month end routine. Pick a month, "
     "check the preview, then log in and click download excel report. Weeks are "
     "worked out automatically, Monday to Sunday, using only the days of that "
     "month. The file comes out values only, fully formatted, and already named "
     "correctly. No week dates to edit, nothing to copy, paste, or delete."),
    ("scheduling", "STEP 5", "Scheduling — fair weekly team allocation", None,
     "On the Scheduling page, administrators build the weekly work schedule. Mark "
     "anyone who is away, then click generate fair allocation. The system rotates "
     "people through the teams fairly, using the history of past weeks, so nobody "
     "is stuck in the same section. Adjust any team manually if needed, save the "
     "week, and copy the ready made WhatsApp message at the bottom. Teams "
     "themselves are managed on the manage teams tab, where you can create, edit, "
     "or remove sections and pin fixed members."),
    ("admin", "STEP 6", "Admin — data source, roster, users, backup", None,
     "The Admin page controls everything else. The data source link to the "
     "responses sheet. The staff roster, which must match the names on the form. "
     "The report layout, which decides what appears on the monthly report. User "
     "accounts and roles. And backups. During the trial, please download a "
     "database backup after making changes, because the free hosting resets its "
     "storage when the app is redeployed."),
    ("card_end", None, None, None,
     "That's everything. Daily form as usual, dashboard for live numbers, one "
     "click for the monthly report, and fair schedules in seconds. This is a "
     "trial: please send questions, mistakes, or ideas to Harry so the system can "
     "be improved before full rollout. Thank you."),
]

make_card(os.path.join(FRAMES, "card_title.png"),
          "Mzuzu NRB Report Dashboard",
          ["How to operate the system", "",
           "Daily Google Form  →  Live Dashboard  →  Monthly Report",
           "", "Trial phase — July 2026"],
          kicker="Staff walkthrough")
make_card(os.path.join(FRAMES, "card_end.png"),
          "Quick recap",
          ["1.  Submit the daily Google Form as usual",
           "2.  Dashboard & Compliance — live, any time",
           "3.  Monthly Report — pick month, download",
           "4.  Scheduling — generate, adjust, save, share",
           "5.  Admin — roster, layout, users, backup",
           "", "Trial phase: send feedback to Harry"],
          kicker="Trial phase")

# Banner-stamped frames
for name, step, label, _, _ in SCENES:
    src = os.path.join(FRAMES, f"{name}.png")
    dst = os.path.join(FRAMES, f"_{name}.png")
    if step:
        banner(src, dst, step, label)
    else:
        Image.open(src).convert("RGB").resize((W, H)).save(dst)

# TTS narration via Windows SAPI (System.Speech)
for i, (name, *_rest, text) in enumerate(SCENES):
    wav = os.path.join(AUDIO, f"{name}.wav")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$v = $s.GetInstalledVoices() | ForEach-Object {$_.VoiceInfo.Name}; "
        "if ($v -contains 'Microsoft Zira Desktop') { $s.SelectVoice('Microsoft Zira Desktop') }; "
        "$s.Rate = -1; "
        f"$s.SetOutputToWaveFile('{wav}'); "
        f"$s.Speak([string]$env:NARR_TEXT); $s.Dispose()"
    )
    env = dict(os.environ, NARR_TEXT=text)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True, env=env)

def wav_dur(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()

# Segments: still frame + narration (+0.9s tail)
seg_files = []
for name, *_ in SCENES:
    img = os.path.join(FRAMES, f"_{name}.png")
    wav = os.path.join(AUDIO, f"{name}.wav")
    dur = wav_dur(wav) + 0.9
    seg = os.path.join(SEGS, f"{name}.mp4")
    subprocess.run([
        FFMPEG, "-y", "-loop", "1", "-i", img, "-i", wav,
        "-t", f"{dur:.2f}", "-r", "30",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-af", "apad", "-shortest",
        seg,
    ], check=True, capture_output=True)
    seg_files.append(seg)
    print(f"segment {name}: {dur:.1f}s")

concat_txt = os.path.join(SEGS, "list.txt")
with open(concat_txt, "w") as f:
    for s in seg_files:
        f.write(f"file '{s}'\n")

out = os.path.join(HERE, "how_to_operate_trial.mp4")
subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
                "-c", "copy", out], check=True, capture_output=True)
total = sum(wav_dur(os.path.join(AUDIO, f"{n}.wav")) + 0.9 for n, *_ in SCENES)
print(f"DONE -> {out}  (~{total/60:.1f} min)")
