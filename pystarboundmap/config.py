#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:
#
# Python Starbound Mapper (pystarboundmap)
# Copyright (C) 2018 CJ Kucera 
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the development team nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CJ KUCERA BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import os
import json
import base64
import appdirs
import platform
import configparser
from collections import namedtuple

# OS-specific imports
cur_os = None
(OS_WINDOWS,
    OS_MAC,
    OS_LINUX) = range(3)
system = platform.system()
if system == 'Windows':
    cur_os = OS_WINDOWS
    import winreg
elif system == 'Darwin':
    cur_os = OS_DARWIN
elif system == 'Linux':
    cur_os = OS_LINUX
else:
    print('Warning: Platform not detected, cannot attempt game autodetection')

class WorldNameCache(object):
    """
    Simple object to cache world name information from our world files, so that
    we don't have to keep parsing the world file every time the open-by-name
    dialog is open.
    """

    cache_ver = 2
    WorldName = namedtuple('WorldName', [
        'sort_name',
        'world_name',
        'extra_desc',
        ])

    def __init__(self, filename):
        self.filename = filename
        self.mapping = {}
        self.changed = False

        if os.path.exists(filename):
            with open(filename, 'r') as df:
                parsed_file = json.load(df)
                if ('version' in parsed_file
                        and parsed_file['version'] == self.cache_ver
                        and 'mapping' in parsed_file):
                    self.mapping = parsed_file['mapping']

    def register_planet(self, path, world_name, world_type, biome_types, sort_name):
        """
        Registers the name of a planet at `path`, with world name `world_name`,
        `world_type` and `biome_types`.  `sort_name` is the key the GUI will use
        to sort, when sorting alphabetically.
        """
        if biome_types:
            self.mapping[path] = (sort_name, world_name, '{}: {}'.format(world_type, biome_types))
        else:
            self.mapping[path] = (sort_name, world_name, world_type)
        self.changed = True

    def register_other(self, path, world_name, extra_desc, sort_name):
        """
        Registers the name of a non-planet world at `path`, with world name
        `world_name` and `extra_desc`.  `sort_name` is the key the GUI will use
        to sort, when sorting alphabetically.
        """
        self.mapping[path] = (sort_name, world_name, extra_desc)
        self.changed = True

    def save(self):
        """
        Saves ourself to disk
        """
        with open(self.filename, 'w') as df:
            json.dump({
                    'version': self.cache_ver,
                    'mapping': self.mapping,
                    }, df)
            self.changed = False

    def __getitem__(self, path):
        """
        Allows us to act like a dict
        """
        return WorldNameCache.WorldName(*self.mapping[path])

    def __contains__(self, path):
        """
        A bit more allowing us to act like a dict
        """
        return path in self.mapping

class Config(object):
    """
    Class to hold our config/prefs info.  Looking back, I'm really not sure
    why I didn't just use Qt's settings framework, like I did for FT/BLCMM Explorer.
    Ah, well, this is done now.
    """

    # Starbound Vars
    starbound_data_dir = None
    starbound_steam_appid = 211820

    # GUI Vars
    app_w = 1050
    app_h = 700
    splitter = None

    def __init__(self):

        self.config_dir = appdirs.user_config_dir('pystarboundmap', 'Apocalyptech')
        self.config_file = os.path.join(self.config_dir, 'pystarboundmap.conf')
        self.worldname_cache = WorldNameCache(os.path.join(self.config_dir, 'worldname_cache.json'))

        self.load()

    def load(self):
        """
        Reads our config from the config file, or attempts to autodetect,
        if the config file is not already found.  Will automatically save out
        the config file if it was not present at first.
        """

        global cur_os, OS_WINDOWS, OS_MAC, OS_LINUX

        save_after = False

        # Load the config file if we have it
        if os.path.exists(self.config_dir) and os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config.read(self.config_file)
            if 'starbound' in config:
                if 'data_dir' in config['starbound']:
                    self.starbound_data_dir = config['starbound']['data_dir']
                    if self.starbound_data_dir == 'None':
                        self.starbound_data_dir = None
            if 'gui' in config:
                if 'app_w' in config['gui']:
                    self.app_w = int(config['gui']['app_w'])
                if 'app_h' in config['gui']:
                    self.app_h = int(config['gui']['app_h'])
                if 'splitter' in config['gui']:
                    self.splitter = base64.b64decode(config['gui']['splitter'])
        else:
            save_after = True

        # Check to see if we have a Starbound data dir
        if not self.starbound_data_dir:

            # Attempt to detect
            if cur_os == OS_WINDOWS:
                self.starbound_data_dir = self.detect_datadir_win()
            elif (cur_os == OS_MAC
                    or cur_os == OS_LINUX):
                self.starbound_data_dir = self.detect_datadir_maclinux()

            # Check to see if we found it
            if self.starbound_data_dir:
                save_after = True

        # Finally, save out the file
        if save_after:
            self.save()

    def save(self):
        """
        Saves our config to disk
        """

        # Create the config dir if it's not already present
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

        # Now save
        config = configparser.ConfigParser()
        config['starbound'] = {}
        if self.starbound_data_dir:
            config['starbound']['data_dir'] = self.starbound_data_dir
        else:
            config['starbound']['data_dir'] = 'None'
        config['gui'] = {}
        config['gui']['app_w'] = str(self.app_w)
        config['gui']['app_h'] = str(self.app_h)
        config['gui']['splitter'] = base64.b64encode(self.splitter).decode('utf-8')
        with open(self.config_file, 'w') as df:
            config.write(df)

    def detect_datadir_win(self):
        """
        Attempt to find Starbound data dir on Win
        """

        # TODO: This is all literally completely untested.

        # This initial list is a complete guess on my part
        possible_values = [
                r'C:\Program Files\Starbound',
                r'C:\Program Files (x86)\Starbound',
                ]

        # Check Steam first.  These keys come from an app that detects
        # steam installs for Borderlands 2, but I assume Steam probably
        # creates these for all apps?
        try:
            for key_root in ['Software', 'Software\WOW6432Node']:
                reg = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                        r'{}\Microsoft\Windows\CurrentVersion\Uninstall\Steam App {}'.format(
                            key_root, self.starbound_steam_appid))
                (value, regtype) = winreg.QueryValueEx(reg, 'InstallLocation')
                winreg.CloseKey(reg)
                if value and value != '':
                    possible_values.append(value)
                    break
        except WindowsError as e:
            print('Unable to query registry for Starbound install loc: {}'.format(e))
        except Exception as e:
            print('Error querying registry for Starbound install loc: {}'.format(e))

        # Is there a way to check for GOG installs like that?

        # Loop through the possibilities we've generated so far
        return self.check_possible_dirs(possible_values)

    def detect_datadir_maclinux(self):
        """
        Attempt to find Starbound data dir on Win/Linux.  This is more or
        less identical 'cause we're just looking for a Steam install,
        basically.
        """

        # Only actually checking for Steam
        return self.get_steam_starbound_install_dir()

    def get_steam_starbound_install_dir(self):
        """
        Attempt to find a Steam Starbound install dir
        """

        library_folders = self.get_steam_library_folders_maclinux()
        possible_dirs = []
        for folder in library_folders:
            manifest = os.path.join(folder,
                    'appmanifest_{}.acf'.format(
                        self.starbound_steam_appid))
            if os.path.exists(manifest):
                possible_dirs.append(os.path.join(folder, 'common', 'Starbound'))
        return self.check_possible_dirs(possible_dirs)

    def get_steam_base_path_maclinux(self):
        """
        Returns our base Steam installation path, based on a few of the
        likely locations.  
        """

        global cur_os, OS_MAC, OS_LINUX

        if cur_os == OS_MAC:
            return os.path.expanduser('~/Library/Application Support/Steam')

        else:
            path = os.path.expanduser('~/.steam/steam')
            if os.path.exists(path):
                return path

            path = os.path.expanduser('~/.local/share/Steam')
            if os.path.exists(path):
                return path

        return None

    def get_steam_library_folders_maclinux(self):
        """
        Given an `steam_dir`, try to find all Steam library folders.
        """

        folders = []

        # Get the base steam dir if we can.
        steam_dir = self.get_steam_base_path_maclinux()
        if not steam_dir:
            return folders

        # Our base install is almost certainly a library folder itself
        for steamapps in ['steamapps', 'SteamApps']:
            base_library = os.path.join(steam_dir, steamapps)
            if os.path.exists(base_library):
                folders.append(base_library)
                break

        # Check for libraryfolders.vdf (w/ two possible cases in the dir)
        vdf = None
        for steamapps in ['steamapps', 'SteamApps']:
            vdf = os.path.join(steam_dir, steamapps, 'libraryfolders.vdf')
            if os.path.exists(vdf):
                break
            else:
                vdf = None

        # "Parse" the VDF file, if we have it.  This is pretty potato.
        if vdf:
            with open(vdf) as df:
                for line in df.readlines():
                    parts = line.split()
                    if len(parts) == 2:
                        parts = [p.strip('"') for p in parts]
                        try:
                            library_idx = int(parts[0])
                            for steamapps in ['steamapps', 'SteamApps']:
                                library_dir = os.path.join(parts[1], steamapps)
                                if os.path.exists(library_dir):
                                    folders.append(library_dir)
                                    break
                        except ValueError as e:
                            pass

        # ... aaand we're done.
        return folders

    def check_possible_dirs(self, possible_values):
        """
        Given a list of `possible_values`, see if they're valid Starbound install
        locations (or at least that they have packed.pak and a 'storage' dir)
        """
        for dirname in possible_values:
            if (os.path.exists(dirname)
                    and os.path.exists(os.path.join(dirname, 'assets', 'packed.pak'))
                    and os.path.exists(os.path.join(dirname, 'storage'))):
                return dirname
        return None
