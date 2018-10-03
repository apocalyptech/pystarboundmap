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
import io
import re
import time
import json
import mmap
import starbound
from PIL import Image
from PyQt5 import QtGui

def read_config(config_data):
    """
    Attempts to parse a starbound .config file.  These are very nearly JSON,
    but include comments prefixed by //, which isn't allowed in JSON, so
    the JSON parser fails.  https://pypi.org/project/json5/ might be able
    to parse these, actually, but as its README mentions, it is SUPER slow.
    Way slower than even the gigantic list of comment special cases below.
    """
    out_lines = []
    df = io.StringIO(config_data.decode('utf-8'))
    odf = io.StringIO()
    in_comment = False
    for line in df.readlines():
        # ack, multiline comments in /objects/generic/statuspod/statuspod.object
        # also in /objects/ancient/hologramgalaxy/hologramgalaxy.object, and
        # unfortunately that one necessitates some stripping (though stripping
        # is no more CPU-intensive than hardcoding the few instances)
        if line.lstrip()[:2] == '/*':
            in_comment = True
        else:
            if in_comment:
                if line.lstrip()[:2] == '*/':
                    in_comment = False
            else:
                idx = line.find('//')
                if idx == -1:
                    print(line, file=odf)
                else:
                    print(line[0:idx], file=odf)

            # This list of patterns allows us to load all the data we care about
            # (that I'm aware of anyway) but I've moved to just stripping out
            # anything after // automatically.  That shaves about a second off of
            # our startup time.  Doubtless there are image processing speedups
            # which would probably account for the majority of the loadtime)
            #elif line[:3] != '// ':
            #    found_pattern = False
            #    for pattern in [
            #            ' // ',
            #            # special case for /objects/biome/foundry/lavatanklarge/lavatanklarge.object
            #            '//FIRE',
            #            # special cases for /objects/biome/tentacle/tentaclespawner1/tentaclespawner1.object
            #            '//type',
            #            '//additional',
            #            '//relative',
            #            '//[x,y] size',
            #            '//total',
            #            # special case for /objects/avian/sawblade/sawblade.object
            #            '//mollys',
            #            # special case for /objects/avian/birdgroundlantern/birdgroundlantern.object
            #            '//"interactive"',
            #            # special cases for /objects/outpost/signstore/signdispenser.object
            #            '//"openSounds"',
            #            '//"closeSounds"',
            #            # special case for /objects/glitch/medievalspikes/medievalspikes.object
            #            '//TODO',
            #            # special case for /objects/themed/island/islandhammock/islandhammock.object
            #            '//"sitCoverImage"',
            #            # special case for /objects/protectorate/objects/protectoratewindbanner3/protectoratewindbanner3.object
            #            '//"soundEffect"',
            #            # special cases for /objects/protectorate/objects/protectoratelobbyvending/protectoratelobbyvending.object
            #            '//"onSound"',
            #            '//"offSound"',
            #            # special case for /objects/spawner/spawners/spawner_human.object
            #            '//6000,',
            #            # special cases for /objects/spawner/colonydeed/colonydeed.object
            #            '//whether',
            #            '//delay',
            #            '//cooldown',
            #            '//scan',
            #            '//length',
            #            '//seconds',
            #            # special cases for /objects/spawner/invisiblemonsterspawner.object
            #            '//level',
            #            '//options',
            #            '//only',
            #            # special case for /objects/crafting/upgradeablecraftingobjects/craftingwheel/craftingwheel.object
            #            '//this',
            #            ]:
            #        idx = line.find(pattern)
            #        if idx != -1:
            #            found_pattern = True
            #            break
            #    if found_pattern:
            #        print(line[0:idx], file=odf)
            #    else:
            #        print(line, file=odf)
    odf.seek(0)
    return json.load(odf)

def strip_colors(input_string):
    """
    Strips color information from a string
    """
    return re.sub('\^\w+?;', '', input_string)

class Material(object):
    """
    Holds info about a material.  Right now we're ignoring all the
    fancy rendering options and pretending that everything is the
    very first (top left) tile, and we're not drawing edges or the
    like.
    """

    def __init__(self, info, path, pakdata, crop_parameters):
        self.info = info
        self.name = info['materialName']
        df = io.BytesIO(pakdata.get(
                '{}/{}'.format(path, info['renderParameters']['texture'])
                ))
        full_image = Image.open(df)
        cropped = full_image.crop(crop_parameters)
        df = io.BytesIO()
        cropped.save(df, format='png')
        #self.image = df.getvalue()
        self.image = QtGui.QPixmap()
        if not self.image.loadFromData(df.getvalue()):
            raise Exception('Could not load material {}'.format(self.name))

        self.bgimage = QtGui.QPixmap()
        self.bgimage.loadFromData(df.getvalue())
        painter = QtGui.QPainter(self.bgimage)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 192)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        painter.drawRect(0, 0, 8, 8)

class Matmod(object):
    """
    Holds info about a matmod.  Right now we're ignoring all the
    fancy rendering options and rendering the whole shebang, though
    we're only using the very first (top left) tile.
    """

    def __init__(self, info, pakdata):
        self.info = info
        self.name = info['modName']
        df = io.BytesIO(pakdata.get(
                '/tiles/mods/{}'.format(info['renderParameters']['texture'])
                ))
        full_image = Image.open(df)
        cropped = full_image.crop((0, 8, 16, 24))
        df = io.BytesIO()
        cropped.save(df, format='png')
        #self.image = df.getvalue()
        self.image = QtGui.QPixmap()
        if not self.image.loadFromData(df.getvalue()):
            raise Exception('Could not load material {}'.format(self.name))

        self.bgimage = QtGui.QPixmap()
        self.bgimage.loadFromData(df.getvalue())
        painter = QtGui.QPainter(self.bgimage)
        painter.setCompositionMode(painter.CompositionMode_DestinationIn)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 192)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        painter.drawRect(0, 0, 16, 16)

class Plant(object):
    """
    Class to hold plant info.  This is more basic than all our other
    objects because map plant entities seem to only ever reference the
    PNG directly.
    """

    def __init__(self, pathname, pakdata):
        self.image = QtGui.QPixmap()
        self.image.loadFromData(pakdata.get(pathname))

class SBObjectOrientation(object):
    """
    Info about a specific orientation.  Note that we're ignoring
    color variations - just grabbing the top right image for now.
    """

    def __init__(self, info, frames, path, pakdata):
        self.info = info
        self.offset = (0, 0)
        self.anchor = (0, 0)
        self.image = None

        # Grab offset, if we can
        if 'imagePosition' in info:
            self.offset = tuple(info['imagePosition'])

        # Figure out what property holds the image filename
        if 'dualImage' in info:
            file_string = info['dualImage']
        elif 'image' in info:
            file_string = info['image']
        elif 'imageLayers' in info:
            # TODO: not actually sure what the Right thing to do here is.
            # Just taking the first one in the list.
            file_string = info['imageLayers'][0]['image']
        elif 'leftImage' in info:
            # TODO: Not sure here either - there'll also be a rightImage.
            # I assume that the direction is specified somehow by the map
            # data.  Just taking the left version for now
            file_string = info['leftImage']
        else:
            raise Exception('Not sure what to do with {}'.format(path))

        # Grab the actual image filename and frame info file
        image_file = file_string.split(':')[0]
        info_frames = self.get_frame(path, image_file, frames, pakdata)
        if image_file[0] == '/':
            full_image_file = image_file
        else:
            full_image_file = '{}/{}'.format(path, image_file)

        # Now read in the image and crop
        df = io.BytesIO(pakdata.get(full_image_file))
        full_image = Image.open(df)
        if info_frames:
            (width, height) = tuple(info_frames['frameGrid']['size'])
        else:
            (width, height) = full_image.size
        cropped = full_image.crop((0, 0, width, height))
        df = io.BytesIO()
        cropped.save(df, format='png')
        self.image = QtGui.QPixmap()
        self.image.loadFromData(df.getvalue())

    def get_frame(self, path, image_file, frames, pakdata):
        """
        Given a path and image filename, read in frames if possible
        """
        base_filename = image_file.rsplit('.', 1)[0]
        if base_filename not in frames:
            full_filename = '{}/{}.frames'.format(path, base_filename)
            try:
                frames[base_filename] = read_config(pakdata.get(full_filename))
            except KeyError:
                if 'default' not in frames:
                    full_filename = '{}/default.frames'.format(path)
                    try:
                        frames['default'] = read_config(pakdata.get(full_filename))
                    except KeyError:
                        frames['default'] = None
                frames[base_filename] = frames['default']
        return frames[base_filename]

class SBObject(object):
    """
    Class to hold info about a starbound "object".  We're ignoring a lot
    of information about the object, and like our other graphics, just
    taking the top-left image in the graphics files.
    """

    def __init__(self, info, filename, path, pakdata):
        self.info = info
        self.orientations = []
        self.frames = {}
        for o in info['orientations']:
            self.orientations.append(
                    SBObjectOrientation(o, self.frames, path, pakdata)
                    )

    def get_image(self, orientation):
        """
        Returns a tuple for displaying the image of this object, at the
        given orientation.  The first element will be the image data
        (as a PNG), the second two will be the x and y offsets at which
        it should be rendered.
        """
        if orientation < len(self.orientations):
            orient = self.orientations[orientation]
        else:
            orient = self.orientations[0]
        return (orient.image, orient.offset[0], orient.offset[1])

class Liquid(object):
    """
    Class to hold info about a liquid.  Not much in here, honestly
    """

    def __init__(self, info):
        self.info = info
        self.name = info['name']
        self.overlay = QtGui.QColor(*info['color'])

class PakTree(object):
    """
    Tree-based dict so we can "browse" pak contents by directory.
    Makes no distinction between directories and files.
    """

    def __init__(self):
        self.top = {}

    def add_path(self, pathname):
        """
        Adds a path to our tree
        """
        parts = pathname.lower().split('/')[1:]
        cur = self.top
        for part in parts:
            if part not in cur:
                cur[part] = {}
            cur = cur[part]

    def get_all_in_path(self, path):
        """
        Gets all "files" within the given path.
        """
        parts = path.lower().split('/')[1:]
        cur = self.top
        for part in parts:
            if part not in cur:
                return []
            cur = cur[part]
        return sorted(cur.keys())

    def get_all_matching_ext(self, path, ext):
        """
        Gets all "files" within the given path which match the given
        extension.  Note that "extension" is being used here a bit
        generously - be sure to pass in a leading dot if you want it
        to *actually* be an extension.
        """
        to_ret = []
        for item in self.get_all_in_path(path):
            if item.endswith(ext):
                to_ret.append(item)
        return to_ret

    def get_all_recurs_matching_ext(self, path, ext):
        """
        Searches recursively through the tree, starting at `path`, to
        find all files matching the given extension.  Returns a list
        of tuples - the first element is the *full* path the file is
        found in, and the second is the name of the file
        """
        cur = self.top
        for part in path.lower().split('/')[1:]:
            if part not in cur:
                return []
            cur = cur[part]
        return self._search_in(path.lower(), cur, ext)

    def _search_in(self, cur_path, node, ext):
        """
        Inner recursive function for `get_all_recurs_matching_ext`
        """
        to_ret = []
        for name, children in node.items():
            if name.endswith(ext):
                to_ret.append((cur_path, name))
            elif len(children) > 0:
                to_ret.extend(self._search_in(
                    '{}/{}'.format(cur_path, name),
                    children,
                    ext,
                    ))
        return to_ret

class Player(object):
    """
    Wrapper class for the player save dict, to provide a helper function
    or two.
    """

    def __init__(self, playerdict, base_universe):
        self.playerdict = playerdict
        self.base_universe = base_universe
        self.name = playerdict.data['identity']['name']

    def get_systems(self):
        """
        Returns a list of tuples of the form:
            ((x, y, z), systemdict)
        Describing all systems known to this player.
        (I'm using x, y, z because I imagine that those are maybe
        supposed to be coordinates, but in reality I suspect they're
        effectively random.)
        """

        # Will have to check that the universeMap dicts always has just one key
        # (a uuid or something)
        for k, v in self.playerdict.data['universeMap'].items():
            # universeMap keys:
            #   systems
            #   teleportBookmarks

            systemlist = v['systems']
            return systemlist

    def get_worlds(self, data):
        """
        Given a StarboundData object `data`, returns a list of all worlds
        known to the user, as a list of tuples of the form:
            (sortable_name, world_name, filename)
        
        Note that this has to actually load in world files to get the names
        on the first runthrough, but we *do* now cache the name information,
        so subsequent listings should be much faster.
        """

        worlds = []
        (world_dict, extra_uuid) = data.get_worlds()

        # Get our world name cache
        cache = data.config.get_worldname_cache()

        # Add in our own spaceship, if we've got it
        ship_path = os.path.join(data.base_player, '{}.shipworld'.format(self.playerdict.data['uuid']))
        if os.path.exists(ship_path):
            if ship_path not in cache:
                cache.register_other(ship_path, 'Starship', 'Your Starship', 'aaaaa')
            worlds.append((
                cache[ship_path].sort_name,
                cache[ship_path].world_name,
                cache[ship_path].extra_desc,
                ship_path))

        # Loop through all systems we've explored
        for (coords, systemdict) in self.get_systems():
            base_system_name = '{}_{}_{}'.format(*coords)

            if base_system_name in world_dict:
                detected_system_name = None
                for planet in systemdict['mappedPlanets']:
                    if planet['planet'] in world_dict[base_system_name]:
                        for filename in world_dict[base_system_name][planet['planet']]:
                            if filename not in cache:
                                (world, worlddf) = StarboundData.open_world(filename)
                                cp = world.metadata['worldTemplate']['celestialParameters']
                                raw_name = cp['name']
                                cache.register_planet(filename,
                                        world_name=strip_colors(raw_name),
                                        world_type=cp['parameters']['description'],
                                        biome_types=', '.join(cp['parameters']['terrestrialType']),
                                        sort_name=StarboundData.world_name_to_sortable(raw_name))
                                worlddf.close()

                            # This is the only way I can find to try and associate a system
                            # to its name (only really useful in the uuid checks below).  Alas!
                            if not detected_system_name:
                                detected_system_name = re.sub(r'(.*?) \d.*', r'\1', cache[filename].sort_name)

                            worlds.append((
                                cache[filename].sort_name,
                                cache[filename].world_name,
                                cache[filename].extra_desc,
                                filename,
                                ))

                # Now loop through any extra worlds we found via UUID
                if not detected_system_name:
                    detected_system_name = '(Unknown System)'
                for uuid in systemdict['mappedObjects'].keys():
                    if uuid in extra_uuid:
                        (filename, description) = extra_uuid[uuid]
                        if filename not in cache:
                            cache.register_other(filename,
                                    world_name='{} - {}'.format(detected_system_name, description),
                                    extra_desc='Non-Planet System Object',
                                    sort_name='{} 99 - {}'.format(detected_system_name, description).lower(),
                                    )
                        worlds.append((
                            cache[filename].sort_name,
                            cache[filename].world_name,
                            cache[filename].extra_desc,
                            filename,
                            ))

        # Save our cache, if anything's changed
        if cache.changed:
            cache.save()

        # Return our list
        return worlds

class StarboundData(object):
    """
    Master class to hold the starbound data that we're interested in.
    """

    base_game = None
    base_storage = None
    base_player = None
    base_universe = None
    base_pak = None

    world_name_sortable_conversions = [
            ('^green;I^white;', '01'),
            ('^green;II^white;', '02'),
            ('^green;III^white;', '03'),
            ('^green;IV^white;', '04'),
            ('^green;V^white;', '05'),
            ('^green;VI^white;', '06'),
            ('^green;VII^white;', '07'),
            ('^green;VIII^white;', '08'),
            ('^green;IX^white;', '09'),
            ('^green;X^white;', '10'),
            ('^green;XI^white;', '11'),
            ('^green;XII^white;', '12'),
            ]

    def __init__(self, config, progress_callback=None):
        """
        `config` should be a Config object (which will have the base game
        installation directory info).  `progress_callback` can be used to
        update a progress bar, for some visual feedback while we load
        things.
        """

        self.config = config
        self.base_game = config.starbound_data_dir
        self.base_storage = os.path.join(self.base_game, 'storage')
        self.base_player = os.path.join(self.base_storage, 'player')
        self.base_universe = os.path.join(self.base_storage, 'universe')
        self.base_pak = os.path.join(self.base_game, 'assets', 'packed.pak')
        progress_update_interval = 50

        # Read in the data file
        with open(self.base_pak, 'rb') as pakdf:

            paktree = PakTree()
            pakdata = starbound.SBAsset6(pakdf)

            # py-starbound doesn't let you "browse" inside the pakfile's
            # internal "directory", so we're doing it by hand here
            pakdata.read_index()
            for path in pakdata.index.keys():
                paktree.add_path(path)

            # Cropping parameters for our various material templates.
            # TODO: obviously if we want to render things *correctly*
            # we'd have to actually parse/understand these.  Instead
            # we're just grabbing the top-left image, basically.
            crop_params = {
                    '/tiles/classicmaterialtemplate.config': (4, 12, 12, 20),
                    '/tiles/platformtemplate.config': (8, 0, 16, 8),
                    '/tiles/girdertemplate.config': (1, 1, 9, 9),
                    '/tiles/screwtemplate.config': (2, 14, 10, 22),
                    '/tiles/columntemplate.config': (2, 14, 10, 22),
                    '/tiles/rowtemplate.config': (2, 14, 10, 22),

                    # Out of all of these, this will be the one that's Most
                    # Wrong.  I think this is space station stuff
                    '/tiles/slopedmaterialtemplate.config': (24, 0, 32, 8),

                    # These two are quite wrong, of course, since they're supposed
                    # to "join up" properly.  For pipes I chose the straight
                    # horizontal image, though note that this'll fail for tentacle
                    # pipes!
                    '/tiles/pipetemplate.config': (68, 36, 76, 44),
                    '/tiles/railtemplate.config': (3, 5, 11, 13),
                }

            # Load in our materials
            self.materials = {}
            obj_list = paktree.get_all_recurs_matching_ext('/tiles', '.material')
            for idx, (obj_path, obj_name) in enumerate(obj_list):
                if progress_callback and idx % progress_update_interval == 0:
                    progress_callback()
                matpath = '{}/{}'.format(obj_path, obj_name)
                material = json.loads(pakdata.get(matpath))
                if 'renderTemplate' in material:
                    if material['renderTemplate'] in crop_params:
                        self.materials[material['materialId']] = Material(
                                material,
                                obj_path,
                                pakdata,
                                crop_params[material['renderTemplate']],
                                )
                    else:
                        print('Unhandled material render template: {}'.format(material['renderTemplate']))
                else:
                    print('No render template found for {}'.format(matpath))

            # Load in our material mods.
            self.matmods = {}
            for idx, matmod_name in enumerate(paktree.get_all_matching_ext('/tiles/mods', '.matmod')):
                if progress_callback and idx % progress_update_interval == 0:
                    progress_callback()
                # All matmods, at least in the base game, are classicmaterialtemplate
                matmodpath = '/tiles/mods/{}'.format(matmod_name)
                matmod = json.loads(pakdata.get(matmodpath))
                self.matmods[matmod['modId']] = Matmod(matmod, pakdata)

            # Load in object data
            start = time.time()
            self.objects = {}
            obj_list = paktree.get_all_recurs_matching_ext('/objects', '.object')
            for idx, (obj_path, obj_name) in enumerate(obj_list):
                if progress_callback and idx % progress_update_interval == 0:
                    progress_callback()
                obj_full_path = '{}/{}'.format(obj_path, obj_name)
                obj_json = read_config(pakdata.get(obj_full_path))
                self.objects[obj_json['objectName']] = SBObject(obj_json, obj_name, obj_path, pakdata)
            end = time.time()
            print('Loaded objects in {:.1f} sec'.format(end-start))

            # Load in plant data
            # The Entities seem to actually only references these by PNG path, so
            # I guess that's what we'll do too.
            start = time.time()
            self.plants = {}
            img_list = paktree.get_all_recurs_matching_ext('/plants', '.png')
            for idx, (img_path, img_name) in enumerate(img_list):
                if progress_callback and idx % progress_update_interval == 0:
                    progress_callback()
                img_full_path = '{}/{}'.format(img_path, img_name)
                self.plants[img_full_path] = Plant(img_full_path, pakdata)
            end = time.time()
            print('Loaded plants in {:.1f} sec'.format(end-start))

            #for idx, (weight, system_name) in enumerate(celestial_names['systemNames']):
            #    if system_name == 'Fribbilus Xax':
            #        print('Fribbilus Xax found at {}'.format(idx))
            #        # 493
            #        break
            #for idx, (weight, suffix_name) in enumerate(celestial_names['systemSuffixNames']):
            #    if suffix_name == 'Swarm':
            #        print('Swarm found at {}'.format(idx))
            #        # 29
            #        break

            # Load in liquid data
            self.liquids = {}
            liquid_list = paktree.get_all_recurs_matching_ext('/liquids', '.liquid')
            for idx, (liquid_path, liquid_name) in enumerate(liquid_list):
                if progress_callback and idx % progress_update_interval == 0:
                    progress_callback()
                liquid_full_path = '{}/{}'.format(liquid_path, liquid_name)
                liquid = read_config(pakdata.get(liquid_full_path))
                self.liquids[liquid['liquidId']] = Liquid(liquid)

    def get_all_players(self):
        """
        Returns a list of tuples describing all players.  Tuples will be of the form
            (timestamp, Player object)
        and will be sorted so that the most recently-modified players are first.
        """
        entries = []
        with os.scandir(self.base_player) as it:
            for entry in it:
                if entry.name.endswith('.player'):
                    player = self.get_player(entry.path)
                    entries.append((entry.stat().st_mtime, player))
        # TODO: sorting by mtime, because that's how Starbound does it.  Should
        # we at least provide the option for alphabetical?
        return sorted(entries, reverse=True)

    def get_player(self, player_file):
        """
        Returns player data, given the specified player file
        """
        player = None
        with open(os.path.join(self.base_player, player_file), 'rb') as playerdf:
            player = Player(starbound.read_sbvj01(playerdf), self.base_universe)
        return player

    def get_worlds(self):
        """
        Get available worlds from the `universe` dir.  Useful when trying to find out
        what worlds are available for a given user, since there's otherwise not really
        a directory of those, apart from what planets have been "visited" (but that
        doesn't actually have anything to do with what planets have been landed on,
        and thus which worlds have maps).

        Returns a tuple - the first element will be a nested dict with the top-level
        keys being the string "coordinates" of the system, as three underscore-
        separated numbers, and the next-level keys being the number of the planet.
        The value for that key will be a list of filenames.

        The second element of the tuple will be a dict whose keys are UUIDs.  The
        values will be a tuple whose first element is the filenames, and the second
        element is the descriptive text found in the filename.  (These will be random
        encounters (if they've been saved) or space stations or the like, and don't
        really have any useful text to show the user other than what's in the filename.)
        """
        worlds = {}
        extra_uuids = {}
        for filename in os.listdir(self.base_universe):
            match = re.match(r'([-0-9]+_[-0-9]+_[-0-9]+)_(\d+)(_(\d+))?.world', filename)
            if match:
                system = match.group(1)
                planet_num = int(match.group(2))
                if match.group(4) is None:
                    moon_num = None
                else:
                    moon_num = int(match.group(4))
                if system not in worlds:
                    worlds[system] = {}
                if planet_num not in worlds[system]:
                    worlds[system][planet_num] = []
                worlds[system][planet_num].append(os.path.join(self.base_universe, filename))
            else:
                match = re.match(r'(.*)-([0-9a-f]{32})-(\d+).(temp)?world', filename)
                if match:
                    description = match.group(1)
                    uuid = match.group(2)
                    num = int(match.group(3))
                    is_temp = match.group(4)
                    extra_uuids[uuid] = (os.path.join(self.base_universe, filename), description)
        return (worlds, extra_uuids)

    @staticmethod
    def world_name_to_sortable(name):
        """
        Given a raw world name (with color highlights and everything), convert
        it to a string that will sort properly using regular ol' alphanumerics.
        This is basically just converting the roman numerals into numbers.
        """
        for (old, new) in StarboundData.world_name_sortable_conversions:
            if old in name:
                return name.replace(old, new).lower()
        return name.lower()

    @staticmethod
    def open_world(filename):
        """
        Given a `filename`, returns a tuple where the first element is
        a World object, and the second is a filehandle which should be
        closed once the app is through with it (this will actually be
        an mmap object).
        """

        with open(filename, 'rb') as worlddf:
            worldmm = mmap.mmap(worlddf.fileno(), 0, access=mmap.ACCESS_READ)
            world = starbound.World(worldmm)
            world.read_metadata()
            return (world, worldmm)
