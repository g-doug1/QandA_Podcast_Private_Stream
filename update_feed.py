import os
import subprocess
from mutagen.mp3 import MP3
from datetime import datetime
from email.utils import format_datetime

FEED_PATH = "feed.xml"
AUDIO_DIR = "audio/"
BASE_URL = "https://github.com/g-doug1/QandA_Podcast_Private_Stream/audio/"

def check_and_reencode(filepath):
    """Ensure MP3 is mono, 44100 Hz, 64kbps (CBR), no metadata."""
    print(f"📂 Checking: {filepath}")

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels,bit_rate",
         "-of", "default=noprint_wrappers=1", filepath],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"⚠️ ffprobe failed on {filepath}")
        return

    props = {}
    for line in result.stdout.strip().split('\n'):
        if '=' in line:
            key, value = line.split('=')
            props[key] = int(value.strip())

    sr = props.get("sample_rate", 0)
    br = props.get("bit_rate", 0)
    ch = props.get("channels", 0)

    print(f"   ↳ Sample rate: {sr} Hz")
    print(f"   ↳ Bitrate: {br} bps ({br // 1000} kbps)")
    print(f"   ↳ Channels: {ch}")

    sr_ok = (sr == 44100)
    br_ok = (63000 <= br <= 65000)  # Allow tolerance around 64k
    ch_ok = (ch == 1)

    if sr_ok and br_ok and ch_ok:
        print("✅ Format OK — no re-encoding.\n")
        return

    print("🔧 Re-encoding required...")
    temp_file = filepath + ".tmp.mp3"
    result = subprocess.run([
        "ffmpeg", "-y", "-i", filepath,
        "-map", "0:a", "-acodec", "libmp3lame",
        "-b:a", "64k", "-ar", "44100", "-ac", "1",
        "-map_metadata", "-", "-id3v2_version", "3",
        temp_file
    ])

    if result.returncode == 0:
        # Optional: remove leftover ID3 tags with id3v2 if available
        try:
            subprocess.run(["id3v2", "--delete-all", temp_file], check=False)
        except FileNotFoundError:
            pass  # skip silently if id3v2 not installed

        os.replace(temp_file, filepath)
        print(f"✅ Re-encoded and cleaned: {filepath}\n")
    else:
        print(f"❌ ffmpeg failed to re-encode: {filepath}\n")

def get_metadata(filepath):
    audio = MP3(filepath)
    title = os.path.splitext(os.path.basename(filepath))[0]  # use filename as title
    duration = int(audio.info.length)
    minutes, seconds = divmod(duration, 60)
    hours, minutes = divmod(minutes, 60)
    duration_str = f"{hours}:{minutes:02}:{seconds:02}"
    size_bytes = os.path.getsize(filepath)
    pubdate = format_datetime(datetime.utcfromtimestamp(os.path.getmtime(filepath)))
    return title, duration_str, size_bytes, pubdate

def generate_item_xml(filename, title, duration, size, pubdate):
    url = BASE_URL + filename
    return f"""    <item>
      <title>{title}</title>
      <description>{title}</description>
      <enclosure url="{url}" length="{size}" type="audio/mpeg"/>
      <guid>{filename}</guid>
      <pubDate>{pubdate}</pubDate>
      <itunes:duration>{duration}</itunes:duration>
    </item>
"""

def generate_feed():
    items = []
    for file in sorted(os.listdir(AUDIO_DIR)):
        if file.endswith(".mp3"):
            fullpath = os.path.join(AUDIO_DIR, file)
            check_and_reencode(fullpath)
            title, duration, size, pubdate = get_metadata(fullpath)
            items.append(generate_item_xml(file, title, duration, size, pubdate))

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Your Podcast Title</title>
    <link>{BASE_URL}</link>
    <language>en-us</language>
    <itunes:author>Your Name</itunes:author>
    <description>Your description here.</description>
    <itunes:explicit>no</itunes:explicit>
{''.join(items)}
  </channel>
</rss>"""
    with open(FEED_PATH, "w", encoding="utf-8") as f:
        f.write(feed)
    print(f"✅ feed.xml updated with {len(items)} episode(s).")

if __name__ == "__main__":
    generate_feed()
