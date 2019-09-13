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
import re
from colorama import init, Fore, Back
import os


class QueueObject:
    def __init__(self):
        pass

    def download(self):
        pass

    def display(self):
        pass


class QueueTrack(QueueObject):
    def __init__(self, track, folder):
        self.track = track
        self.folder = folder

    def download(self):
        try:
            for directory in os.listdir(self.folder):
                if directory == self.track.artist.name.replace("/", "_"):
                    folder = directory
                    break
                else:
                    folder = self.folder / '1. No album'
            track_name = f'{self.track.name}{f" ({self.track.version})" if self.track.version else ""}'
            track_name = delete_forbidden_signs(track_name)
            print(Fore.GREEN + f'\nDownloading track: {self.track.artist.name} - {track_name} to {folder}\n')
            download_flac(self.track, folder / f'{self.track.artist.name} - {track_name}.flac'.replace("/", "_"))
            print(Fore.CYAN + f'\nTrack: {self.track.artist.name} - {track_name} downloaded!')
        except FLACNoHeaderError:
            print(Fore.BLACK + Back.RED + "This track is not available in lossless quality, abandoning")
        except ConnectionError:
            print(Fore.BLACK + Back.RED + "Failed to connect, abandoning")
        except PermissionError:
            print(Fore.BLACK + Back.RED + "Check if defined folder is not being used by other app, abandoning")
        except requests.exceptions.HTTPError as e:
            if str(e).split(' ')[0] == '401':
                print(Fore.BLACK + Back.RED + "This track is not available in your country, abandoning")

    def display(self):
        track_name = f'{self.track.name}{f" ({self.track.version})" if self.track.version else ""}'
        print(Fore.LIGHTMAGENTA_EX + f'Track "{track_name}" created by {self.track.artist.name}')


class QueueAlbum(QueueObject):
    def __init__(self, album, folder):
        self.album = album
        self.folder = folder

    def download(self):
        try:
            print(Fore.GREEN + f'Downloading album: {self.album.artist.name} - {self.album.name}\n')
            tracks = session.get_album_tracks(album_id=self.album.id)  # type: typing.Iterable[tidalapi.models.Track]
            num = 0
            discs = max(map(lambda x: x.disc_num, tracks))
            name = f'{f"({self.album.release_date.year}) " if self.album.release_date is not None else ""}{self.album.name}'.replace("/", "_")
            name = delete_forbidden_signs(name)
            album = self.folder / self.album.artist.name.replace("/", "_") / name
            album.mkdir(parents=True, exist_ok=True)
            if discs > 1:
                for d in range(discs):
                    fdisc = self.folder / self.album.artist.name.replace("/", "_") / name / f'Disc {d+1}'
                    fdisc.mkdir(parents=True, exist_ok=True)

            with open(album / f'00. {delete_forbidden_signs(self.album.name)}.m3u', 'w') as playlist_file:
                for track in tracks:
                    try:
                        num += 1
                        track_name = f'{track.name}{f" ({track.version})" if track.version else ""}'
                        track_name = delete_forbidden_signs(track_name)
                        print(
                            Fore.GREEN + f'Downloading ({num}/{self.album.num_tracks}): {track_name}')  # printing
                        # each downloaded element kills clarity so badly//not if coloured
                        fname = f'{str(track.track_num).zfill(2)}. {track_name.replace("/", "_")}.flac'
                        if discs > 1:
                            download_flac(track, album / f'Disc {str(track.volumeNumber)}' / fname, album=self.album)
                        else:
                            download_flac(track, album / fname, album=self.album)

                        playlist_file.write(fname)
                        playlist_file.write("\n")
                    except requests.exceptions.HTTPError as e:
                        if str(e).split(' ')[0] == '401':
                            print(Fore.BLACK + Back.RED + "This track is not available in your country")

            print(Fore.CYAN + f'\nAlbum {self.album.artist.name} - {self.album.name} downloaded!' + '\n')
        except FLACNoHeaderError:
            print(Fore.BLACK + Back.RED + "This album is not available in lossless quality, abandoning")
        except ConnectionError:
            print(Fore.BLACK + Back.RED + "Failed to connect, abandoning")
        except PermissionError:
            print(Fore.BLACK + Back.RED + "Check if defined folder is not being used by other app, abandoning")
        except requests.exceptions.HTTPError as e:
            if str(e).split(' ')[0] == '401':
                print(Fore.BLACK + Back.RED + "This album is not available in your country, abandoning")

    def display(self):
        print(Fore.LIGHTMAGENTA_EX + f'Album "{self.album.name}" created by {self.album.artist.name}')
        pass


class QueuePlaylist(QueueObject):
    def __init__(self, playlist, folder):
        self.playlist = playlist
        self.folder = folder

    def download(self):
        try:
            print(Fore.GREEN + f'Downloading playlist: {self.playlist.name}\n')
            tracks = session.get_playlist_tracks(playlist_id=self.playlist.id)
            num = 0
            playlist_name = delete_forbidden_signs(self.playlist.name)
            folder = self.folder / playlist_name
            folder.mkdir(parents=True, exist_ok=True)
            with open(folder / f'{self.playlist.name.replace("/", "_")}.m3u', "w") as playlist_file:
                for track in tracks:
                    num += 1
                    track_name = f'{track.name}{f" ({track.version})" if track.version else ""}'
                    track_name = delete_forbidden_signs(track_name)
                    print(Fore.GREEN + f'Downloading ({num}/{self.playlist.num_tracks}): {track_name}')
                    fname = f'{track.artist.name} - {track_name}.flac'.replace("/", "_")
                    download_flac(track, folder / fname)
                    playlist_file.write(fname)
                    playlist_file.write("\n")

            print(Fore.CYAN + f'\nPlaylist {self.playlist.name} downloaded!' + '\n')
        except FLACNoHeaderError:
            print(Fore.BLACK + Back.RED + "This playlist is not available in lossless quality, abandoning")
        except ConnectionError:
            print(Fore.BLACK + Back.RED + "Failed to connect, abandoning")
        except PermissionError:
            print(Fore.BLACK + Back.RED + "Check if defined folder is not being used by other app, abandoning")
        except requests.exceptions.HTTPError as e:
            if e == '401':
                print(Fore.BLACK + Back.RED + "This playlist is not available in your country, abandoning")

    def display(self):
        print(Fore.LIGHTMAGENTA_EX + f'Playlist "{self.playlist.name}" created by {self.playlist.creator}')


def menu(mode):
    try:
        if mode == "l":
            search_query = input("Enter search query: ")
            search = session.search(field='track', value=search_query)
            for track in search.tracks:
                # TODO: selector to download
                print(f"{track.id}: {track.artist.name} - {track.name}")

        elif mode == "s":
            if not q.empty():
                print('\n' + Fore.LIGHTMAGENTA_EX + str(q.qsize()) + " element(s) in queue\n")
                for member in list(q.queue):
                    member.display()
                print('\n')
            else:
                print(Fore.LIGHTMAGENTA_EX + "Queue is empty\n")

        elif mode == "e":
            if not q.empty():
                print('Queue is not empty, ripper will shut down immediately after the download process')
                menu("s")
                sys.exit(0)
            else:
                print("Thanks for using tidal ripper. Don't close this window if your last download hasn't "
                      "finished. See you around!")
                sys.exit(0)
        else:
            print("Incorrect mode!")

    except Exception as e:
        print(f"Error occurred: {e}")


def download_menu(folder):
        try:
            link = input("Paste link to file:\n")
            category = link.split("/")[-2]
            file_id = link.split("/")[-1]

            if category == "track":
                track = session.get_track(track_id=file_id, withAlbum=True)
                q.put(QueueTrack(track, folder))  # adding a track to download queue
                print(Fore.RED + f'\nEnqueued track: {track.artist.name} - {track.name}\n')

            elif category == "album":
                album = session.get_album(album_id=file_id)
                q.put(QueueAlbum(album, folder))  # adding a track to download queue
                print(Fore.RED + f'\nEnqueued album: {album.artist.name} - {album.name}\n')

            elif category == "playlist":
                playlist = session.get_playlist(playlist_id=file_id)
                q.put(QueuePlaylist(playlist, folder))
                print(Fore.RED + f'\nEnqueued playlist: {playlist.name} \n')
        except Exception as e:
            print(f"Error occurred: {e}")


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
    if hasattr(track, 'copyright') and track.copyright:
        audio['copyright'] = track.copyright
    elif hasattr(album, 'copyright') and album.copyright:
        audio['copyright'] = album.copyright

    # identifiers for later use in own music libraries
    if hasattr(track, 'isrc') and track.isrc:
        audio['isrc'] = track.isrc
    if hasattr(album, 'upc') and album.upc:
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


def delete_forbidden_signs(name):
    forbidden = '<>:|"/\\?*'
    replacement = '_'
    for c in forbidden:
        name = name.replace(c, replacement)

    return name


def download_thread(q):
    while True:
        tmp = q.get()
        tmp.download()


def internet_access():
    try:
        requests.get("http://listen.tidal.com", timeout=3)
        print(Fore.LIGHTGREEN_EX + Back.BLACK + "Internet connection checked!\n")

    except requests.ConnectionError:
        print(Fore.LIGHTRED_EX + Back.BLACK + "You have no internet connection, exiting\n")
        sys.exit()


if __name__ == "__main__":
    # TODO: search for album
    # TODO: search for artist
    # TODO: search for playlist
    import argparse

    init(autoreset=True)
    internet_access()
    p = argparse.ArgumentParser()
    p.add_argument('login', help="TIDAL login/email")
    p.add_argument('password', help="TIDAL password")
    p.add_argument('output_dir', help="output directory (download target)")
    p.add_argument('--api_token', help="TIDAL API token", default='kgsOOmYk3zShYrNP')
    args = p.parse_args()

    config = tidalapi.Config(tidalapi.Quality.lossless)
    config.api_token = args.api_token
    session = tidalapi.Session(config)
    session.login(args.login, args.password)

    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)

    print(Back.BLUE + Fore.LIGHTGREEN_EX + "Tidal FLAC ripper\n")

    q = queue.Queue()  # infinite queue
    d_thread = threading.Thread(target=download_thread, args=(q,))
    d_thread.start()  # starting a download thread

    while True:
        print(
            "\n[L]ook for track"
            "\n[D]ownload"
            "\n[S]how queue"
            "\n[E]xit\n")
        mode = input("Select mode:\n")
        mode = mode.lower()
        while mode != "l" and mode != "d" and mode != "s" and mode != "e":
            mode = input("Select mode:\n")
            mode = mode.lower()

        if mode == "d":
            download_menu(folder)
        else:
            menu(mode)
