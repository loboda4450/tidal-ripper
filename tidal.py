#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shutil
import typing
from io import BytesIO
from pathlib import Path

import requests

from tidal_api import tidalapi
from mutagen import id3
from mutagen.flac import Picture, FLAC, FLACNoHeaderError

import queue
import threading
import sys
from colorama import init, Fore, Back

init(autoreset=True)

class QueueObject:
    def __init__(self):
        pass

    def download(self):
        pass

    def display(self):
        pass


class QueueTrack(QueueObject):
    def __init__(self, track):
        self.track = track
        print(Fore.RED + f'\nEnqueued track: {self.track.artist.name} - {self.track.name}' + '\n')
        pass

    def download(self):
        track_name = f'{self.track.name}{f" ({self.track.version})" if self.track.version else ""}'
        print(Fore.GREEN + f'\nDownloading track: {self.track.artist.name} - {track_name}' + '\n')
        download_flac(self.track, folder / f'{self.track.artist.name} - {track_name}.flac'.replace("/", "_"))
        print(Fore.CYAN + f'\nTrack: {self.track.artist.name} - {track_name} downloaded!')
        pass

    def display(self):
        print(f'Track {self.track.artist.name} - {track_name}')
        pass


class QueueAlbum(QueueObject):
    def __init__(self, album, folder):
        self.album = album
        self.folder = folder
        print(Fore.RED + f'\nEnqueued album: {self.album.artist.name} - {self.album.name}' + '\n')

    def download(self):
        print(Fore.GREEN + f'Downloading album: {self.album.artist.name} - {self.album.name}')
        tracks = session.get_album_tracks(album_id=album_id)  # type: typing.Iterable[tidalapi.models.Track]
        num = 0
        # TODO: handle multicd albums better (separate dirs and playlists?)
        discs = max(map(lambda x: x.disc_num, tracks))
        folder = self.folder / self.album.artist.name.replace("/", "_") / f'{f"({self.album.release_date.year}) " if self.album.release_date is not None else ""}{self.album.name}'.replace("/", "_")
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f'00. {self.album.name.replace("/", "_")}.m3u', 'w') as playlist_file:
            for track in tracks:
                num += 1
                track_name = f'{track.name}{f" ({track.version})" if track.version else ""}'
                track_name = track_name.replace('"', '')
                print(Fore.GREEN + f'Downloading ({num}/{self.album.num_tracks}): {track_name}' + '\n') # printing each downloaded element kills clarity so badly
                fname = f'{str(track.track_num).zfill(2)}. {track_name.replace("/", "_")}.flac'
                download_flac(track, folder / fname, album=self.album)
                playlist_file.write(fname)
                playlist_file.write("\n")
        print(Fore.CYAN + f'\nAlbum {self.album.artist.name} - {self.album.name} downloaded!' + '\n')
        pass

    def display(self):
        print(Fore.LIGHTMAGENTA_EX + f'Album {self.album.artist.name} - {self.album.name}')
        pass


class QueuePlaylist(QueueObject):
    def __init__(self, playlist, folder):
        self.playlist = playlist
        self.folder = folder
        pass

    def download(self):
        pass

    def display(self):
        print(self.playlist_id)
        pass


def get_track_title(track):
    title = track.name.strip()  # just in case

    # add featuring artists if not already
    if not "(feat." in title and len(track.artists) > 1:
        title += f' (feat. {" & ".join([x.name for x in track.artists[1:]])})'

    # put track version into title
    if len(track.artists) > 1:
        title += f" [{track.version}]" if track.version else ""
    else:
        title += f" ({track.version})" if track.version else ""

    return title


def download_flac(track: tidalapi.models.Track, file_path, album=None):
    if album is None:
        album = track.album
    url = session.get_media_url(track_id=track.id)

    r = requests.get(url, stream=True)
    r.raw.decode_content = True
    data = BytesIO()
    shutil.copyfileobj(r.raw, data)
    data.seek(0)
    audio = FLAC(data)

    # general metatags
    audio['artist'] = track.artist.name
    audio['title'] = f'{track.name}{f" ({track.version})" if track.version else ""}'

    # album related metatags
    audio['albumartist'] = album.artist.name
    audio['album'] = f'{album.name}{f" ({album.version})" if album.version else ""}'
    audio['date'] = str(album.year)

    # track/disc position metatags
    audio['discnumber'] = str(track.volumeNumber)
    audio['disctotal'] = str(album.numberOfVolumes)
    audio['tracknumber'] = str(track.trackNumber)
    audio['tracktotal'] = str(album.numberOfTracks)

    # Tidal sometimes returns null for track copyright
    if track.copyright:
        audio['copyright'] = track.copyright
    elif album.copyright:
        audio['copyright'] = album.copyright

    # identifiers for later use in own music libraries
    if track.isrc:
        audio['isrc'] = track.isrc
    if album.upc:
        audio['upc'] = album.upc

    pic = Picture()
    pic.type = id3.PictureType.COVER_FRONT
    pic.width = 640
    pic.height = 640
    pic.mime = 'image/jpeg'
    r = requests.get(track.album.image, stream=True)
    r.raw.decode_content = True
    pic.data = r.raw.read()

    audio.add_picture(pic)

    data.seek(0)
    audio.save(data)
    with open(file_path, "wb") as f:
        data.seek(0)
        shutil.copyfileobj(data, f)


def download_thread(q):
    while True:
        if q.qsize() > 0:
            tmp = q.get()
            tmp.download()


if __name__ == "__main__":
    import argparse

    q = queue.Queue()  # infinite queue
    d_thread = threading.Thread(target=download_thread, args=(q,))
    d_thread.start()  # starting a download thread (works continuously)
    print("Download thread has started\n")

    p = argparse.ArgumentParser()
    p.add_argument('login', help="TIDAL login/email")
    p.add_argument('password', help="TIDAL password")
    p.add_argument('output_dir', help="output directory (download target)")
    p.add_argument('--api_token', help="TIDAL API token", default='BI218mwp9ERZ3PFI')
    args = p.parse_args()

    config = tidalapi.Config(tidalapi.Quality.lossless)
    config.api_token = args.api_token
    session = tidalapi.Session(config)
    session.login(args.login, args.password)

    print(Back.BLUE + Fore.LIGHTGREEN_EX + "Tidal FLAC ripper\n")

    while True:
        folder = Path(args.output_dir)
        folder.mkdir(parents=True, exist_ok=True)

        print("0) Search for track\n1) Download track\n2) Download album\n3) Download playlist\n4) Display queue\n5) Exit\n")
        mode = input("Select mode:")

        # TODO: download queue
        # TODO: search for album
        # TODO: search for artist
        # TODO: search for playlist
        try:
            if mode == "0":
                search_query = input("Enter search query: ")
                search = session.search(field='track', value=search_query)
                for track in search.tracks:
                    # TODO: selector to download
                    print(f"{track.id}: {track.artist.name} - {track.name}")

            elif mode == "1":
                link = input("Enter link or track id: ")
                track_id = link.split('/')[-1]
                q.put(QueueTrack(session.get_track(track_id, withAlbum=True)))  # adding a track to download queue

            elif mode == "2":
                link = input("Enter album id: ")
                album_id = link.split('/')[-1]
                q.put(QueueAlbum(session.get_album(album_id=album_id), folder))  # adding a track to download queue

            elif mode == "3":
                playlist_id = input("Enter playlist id: ")
                playlist = session.get_playlist(playlist_id=playlist_id)
                tracks = session.get_playlist_tracks(playlist_id=playlist_id)
                print(f'Downloading playlist: {playlist.name}')
                num = 0
                folder = folder / playlist.name.replace("/", "_")
                folder.mkdir(parents=True, exist_ok=True)
                with open(folder / f'{playlist.name.replace("/", "_")}.m3u', "w") as playlist_file:
                    for track in tracks:
                        num += 1
                        track_name = f'{track.name}{f" ({track.version})" if track.version else ""}'
                        print(f'Downloading ({num}/{playlist.num_tracks}): {track_name}')
                        fname = f'{track.artist.name} - {track_name}.flac'.replace("/", "_")
                        download_flac(track, folder / fname)
                        playlist_file.write(fname)
                        playlist_file.write("\n")
                print("Playlist downloaded!")

            elif mode == "4":
                if not q.empty():
                    print('\n' + Fore.LIGHTMAGENTA_EX + str(q.qsize()) + " element(s) in queue\n")
                    for member in list(q.queue):
                        member.display()
                    print('\n')
                else:
                    print(Fore.LIGHTMAGENTA_EX + "Queue is empty\n")


            elif mode == "5":
                if not q.empty():
                    sys.exit("Queue is not empty, ripper will shut down immediately after the download process")
                else:
                    sys.exit("Thanks for using tidal ripper. Don't close this window if your last download hasn't finished. See you around!")

            else:
                print("Incorrect mode!")

        except FLACNoHeaderError:
            print("This track is not available in lossless quality, abandoning")
        except Exception as e:
            print(f"Error occurred: {e}")
