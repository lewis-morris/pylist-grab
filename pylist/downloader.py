import os
import re
import time
from dataclasses import dataclass
from typing import List, Optional

import requests
from moviepy import AudioFileClip
from mutagen.id3 import TIT2, TPE1, COMM, APIC, TDRC, TCON, TALB
from mutagen.mp3 import MP3
from yt_dlp import YoutubeDL

from pylist.utils import run_silently


@dataclass
class SimplePlaylist:
    """Minimal playlist representation used by the downloader."""

    title: str
    video_urls: List[str]

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.video_urls)


REMOVE_WORDS = [
    "|",
    "Official Video",
    "Lyric Video",
    "Official Music Video",
    "Official Lyric Video",
    "Official Audio",
    "Visualizer",
    "Audio",
    "Video",
    "(Video)",
    "Cover",
    "MV",
    "Extended Version",
    "Instrumental",
    "Radio Edit",
    "Clip Officiel",
    "Official",
    "HD",
    "[HQ]",
    "HQ",
    "4K",
    "VEVO",
    "Explicit",
    "Music Video",
    "(Clean)",
    "Demo",
    "Teaser",
    "Performance Video",
]


def set_metadata(
    save_path: str,
    filename: str,
    author: str,
    title: str,
    album: str,
    artwork: str,
    keywords: List[str],
    comment: str,
    date: str,
    genre: Optional[str] = None,
) -> None:
    """Populate ID3 metadata for the downloaded MP3 file."""

    audio = MP3(save_path)

    try:
        audio.add_tags()
    except Exception:
        pass

    if title:
        audio["TIT2"] = TIT2(encoding=3, text=title)
        audio.save()
        audio = MP3(save_path)

    if author:
        audio["TPE1"] = TPE1(encoding=3, text=author)
        audio.save()
        audio = MP3(save_path)

    if album:
        audio["TALB"] = TALB(encoding=3, text=album)
        audio.save()
        audio = MP3(save_path)

    if comment:
        audio["COMM"] = COMM(encoding=3, lang="eng", desc="desc", text=comment)
        audio.save()
        audio = MP3(save_path)

    if date:
        audio["TDRC"] = TDRC(encoding=3, text=str(date))
        audio.save()
        audio = MP3(save_path)

    featured_artist = grab_ft(title)
    if featured_artist:
        featured_artist_tag = TPE1(encoding=3, text=featured_artist)
        if "TPE2" in audio:
            audio["TPE2"].text[0] = featured_artist
            audio.save()
        else:
            audio["TPE2"] = featured_artist_tag
            audio.save()
        audio = MP3(save_path)

    if artwork:
        try:
            artwork_data = requests.get(artwork, timeout=5).content
            audio.tags.add(
                APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=artwork_data)
            )
            audio.save()
        except Exception:
            pass

    if genre:
        audio["TCON"] = TCON(encoding=3, text=genre)
        audio.save()


def clean_remix(title: str, author: str) -> str:
    if author in title:
        title = title.replace(author, "")
    if "()" in title:
        title = title.replace("()", "")
    for typ in ["bootleg", "remix", "edit", "mix", "rework", "re-edit"]:
        if f"({typ})" in title.lower():
            title = title.lower().replace(f"({typ})", typ)
    return title


def clean_title(title: str, featured: str) -> str:
    for word in REMOVE_WORDS:
        title = (
            title.replace(word, "")
            .replace(word.lower(), "")
            .replace(word.upper(), "")
            .replace(word.title(), "")
        )

    title = (
        title.replace(featured, "")
        .replace("(ft. )", "")
        .replace("ft. ", "")
        .replace("ft ", "")
    )

    return (
        title.replace("  ", " ")
        .replace("()", "")
        .replace("[]", "")
        .replace("( )", "")
        .replace("[ ]", "")
        .replace("  ", " ")
        .replace("( ", "(")
        .replace(" )", ")")
        .replace("/", " - ")
        .strip()
    )


def grab_ft(title: str) -> Optional[str]:
    if "ft" in title.lower():
        location = title.lower().find("ft")
        return title[location:].strip()
    return None


def validate_playlist(playlist_url: str) -> SimplePlaylist:
    """Validate a playlist URL and return a :class:`SimplePlaylist`."""

    ydl_opts = {"quiet": True, "extract_flat": True}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    entries = info.get("entries") or []
    if not entries:
        raise Exception("Playlist is empty")

    video_urls = []
    for entry in entries:
        url = entry.get("url") or entry.get("webpage_url")
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={entry.get('id')}"
        video_urls.append(url)

    return SimplePlaylist(title=info.get("title", "Playlist"), video_urls=video_urls)


def download_stream_from_url(song_url: str) -> dict:
    """Download the best audio from the given video URL."""

    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "outtmpl": "temp_audio.%(ext)s",
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(song_url, download=True)
        info["filepath"] = ydl.prepare_filename(info)
    return info


def extract_featured_artist(song_info: str) -> Optional[str]:
    patterns = [
        r"ft\.\s*(?:\()?(.*?)(?:\))?\s*-",
        r"-\s*(?:.*?)ft\.\s*(?:\()?(.*?)(?:\))?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, song_info)
        if match:
            return match.group(1).strip()
    return None


def pull_genre(title: str) -> Optional[str]:
    options = [
        "Deep House",
        "Electro House",
        "Future House",
        "Progressive House",
        "Tech House",
        "Tropical House",
        "Techno",
        "Detroit Techno",
        "Minimal Techno",
        "Dub Techno",
        "Industrial Techno",
        "Drum and Bass",
        "Liquid Drum and Bass",
        "Jump-Up",
        "Neurofunk",
        "Jungle",
        "Dubstep",
        "Brostep",
        "Chillstep",
        "Trance",
        "Progressive Trance",
        "Psytrance (Psychedelic Trance)",
        "Vocal Trance",
        "Uplifting Trance",
        "Electro",
        "Electroclash",
        "Electropop",
        "EDM",
        "Big Room",
        "Dance-Pop",
        "Ambient",
        "Ambient House",
        "Dark Ambient",
        "Drone Music",
        "Breakbeat",
        "Nu Skool Breaks",
        "Big Beat",
        "Breakcore",
        "Hardcore",
        "Happy Hardcore",
        "Gabber",
        "UK Hardcore",
        "Industrial",
        "EBM",
        "Aggrotech",
        "IDM",
        "Glitch",
        "Drill 'n' Bass",
        "Trip-Hop",
        "Downtempo",
        "Glitch Hop",
        "Moombahton",
        "Future Bass",
        "Grime",
        "Trap",
        "Hybrid Trap",
        "Synthwave",
        "Vaporwave",
        "Outrun",
        "Chillwave",
        "House",
        "DnB",
        "Drum & Bass",
        "Drum & base",
    ]
    for op in options:
        if op.lower() in title.lower():
            return op
    return None


def attempt_get_title_author(info: dict) -> tuple[str, str]:
    try:
        author, title = info["title"].split("-", 1)
    except ValueError:
        parts = info["title"].split("-")
        author = parts[0]
        title = " ".join(parts[1:])
    return author.strip(), title.strip()


def pull_meta_data(info: dict) -> dict:
    featured = extract_featured_artist(info.get("title", "")) or extract_featured_artist(
        info.get("uploader", "")
    )
    if featured is None:
        featured = ""

    if "-" in info.get("title", ""):
        author, title = attempt_get_title_author(info)
    else:
        author = info.get("uploader", "")
        title = info.get("title", "")

    title = clean_title(title, featured)
    author = clean_title(author, featured)
    title = clean_remix(title, author)

    if featured:
        author = f"{author}, {featured}"

    if "-" not in title:
        filename = f"{title} - {author}"
    else:
        filename = title.replace("/", " ").replace("\\", " ")

    artwork = info.get("thumbnail")
    keywords = info.get("tags", [])
    comment = info.get("description", "")
    upload_date = info.get("upload_date")
    date = None
    if upload_date:
        date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

    return {
        "filename": filename,
        "author": author,
        "title": title,
        "artwork": artwork,
        "keywords": keywords,
        "comment": comment,
        "date": date,
    }


def read_write_audio(meta_data: dict, dump_directory: str, source_path: str) -> str:
    """Convert downloaded audio to MP3 and save it to the dump directory."""

    audio = AudioFileClip(source_path)
    save_filename = f"{meta_data['filename']}.mp3"
    final_save_filename = os.path.join(dump_directory, save_filename)
    audio.write_audiofile(final_save_filename)
    audio.close()
    os.remove(source_path)
    return final_save_filename


def download_playlist(
    playlist: SimplePlaylist,
    dump_directory: str = "./",
    genre: Optional[str] = None,
    do_yield: bool = True,
    verbosity: int = 1,
    download_indicator_function: Optional[callable] = None,
    silence: bool = True,
) -> Optional[dict]:
    """Download a playlist and yield metadata for each song."""

    def log(message: str, indicator: Optional[callable] = None, no_indicator: int = 0) -> None:
        if verbosity > 1:
            print(message)
        if indicator:
            indicator(no_indicator)

    if dump_directory and not os.path.exists(dump_directory):
        raise Exception("Dump directory does not exist")

    for url in playlist.video_urls:
        for attempt in range(5):
            try:
                start_time = time.time()

                log("Attempting to grab: " + url, download_indicator_function, 1)
                info = run_silently(download_stream_from_url, silence, url)
                if info:
                    meta_data = pull_meta_data(info)
                    log("Metadata received: " + str(meta_data))

                    log("Attempting to download")
                    filename = run_silently(
                        read_write_audio, silence, meta_data, dump_directory, info["filepath"]
                    )

                    log("Download complete", download_indicator_function, 2)

                    run_silently(
                        set_metadata,
                        silence,
                        save_path=filename,
                        genre=genre,
                        **{**meta_data, **{"album": playlist.title}},
                    )
                    log("MP3 Metadata saved")

                    end_time = time.time()
                    time_taken = end_time - start_time

                    if do_yield:
                        yield meta_data, time_taken
                    log("Download complete", download_indicator_function, 3)
                    break
                else:
                    if verbosity > 0:
                        log("Could not download: " + url)
            except Exception as e:  # pragma: no cover - network dependent
                if verbosity > 0:
                    log(f"Could not download: {url} because of {e}")
                if attempt == 4 and do_yield:
                    yield None, None

