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

# Hardcoded stuff for now
base_game = '/usr/local/games/Steam/SteamApps/common/Starbound'
base_storage = os.path.join(base_game, 'storage')
base_player = os.path.join(base_storage, 'player')
base_universe = os.path.join(base_storage, 'universe')
base_pak = os.path.join(base_game, 'assets', 'packed.pak')

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

    def __init__(self, playerdict):
        self.playerdict = playerdict

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

    def get_worlds(self, world_name=None):
        """
        If `world_name` is `None`, return a list of all planets known
        to the user, as a list of tuples of the form:
            (world_name, filename)

        If a `name` is specified, return just that
        planet, or `None`.
        
        Note that both modes will have to actually load in world files
        to get the names.
        """

        planets = []

        for (coords, systemdict) in self.get_systems():
            base_system_name = '{}_{}_{}'.format(*coords)

            # Nothing actually useful to us in here, it seems...
            #with open(
            #        os.path.join(base_universe, '{}.system'.format(base_system_name)),
            #        'rb') as systemdf:
            #    system = starbound.read_sbvj01(systemdf)
            #    print(system)

            # in systemdict, there's three keys:
            #   mappedObjects: Space stations and the like, it seems
            #   bookmarks: Bookmarks, presumably
            #   mappedPlanets: Planets (doesn't seem to include moons?)
            for planet in systemdict['mappedPlanets']:
                world_filename = os.path.join(
                        base_universe,
                        '{}_{}.world'.format(base_system_name, planet['planet']))
                #print('Opening {}'.format(world_filename))
                with open(world_filename, 'rb') as worlddf:
                    worldmm = mmap.mmap(worlddf.fileno(), 0, access=mmap.ACCESS_READ)
                    world = starbound.World(worldmm)
                    world.read_metadata()

                    # Keys in world.metadata:
                    #   centralStructure
                    #   spawningEnabled
                    #   adjustPlayerStart
                    #   protectedDungeonIds
                    #   playerStart
                    #   dungeonIdBreathable
                    #   respawnInWorld
                    #   worldTemplate
                    #   worldProperties
                    #   dungeonIdGravity
                    #print(world.metadata)
                    cp = world.metadata['worldTemplate']['celestialParameters']
                    name = strip_colors(cp['name'])
                    #print('Loaded world: {}'.format(name))
                    if world_name:
                        if name.lower() == world_name.lower():
                            #print('Found world {}, type {}, size {}x{} - Subtypes:'.format(
                            #    world_name,
                            #    cp['parameters']['worldType'],
                            #    world.width,
                            #    world.height,
                            #    ))
                            #for subtype in cp['parameters']['terrestrialType']:
                            #    print(' * {}'.format(subtype))
                            return world
                    else:
                        planets.append((name, world_filename))

                    # TODO: I'm using mmap here without *really* having investigated
                    # how to manage them properly.  Once the UI can load planets
                    # interactively, will have to make sure that these get closed
                    # out properly so that world data doesn't stay resident in RAM.
                    worldmm.close()

        # Return, depending on mode
        if world_name:
            return None
        else:
            return planets

class StarboundData(object):
    """
    Master class to hold the starbound data that we're interested in.
    """

    def __init__(self, pakfile=base_pak):

        # Read in the data file
        with open(pakfile, 'rb') as pakdf:

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
            for (obj_path, obj_name) in obj_list:
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
            for matmod_name in paktree.get_all_matching_ext('/tiles/mods', '.matmod'):
                # All matmods, at least in the base game, are classicmaterialtemplate
                matmodpath = '/tiles/mods/{}'.format(matmod_name)
                matmod = json.loads(pakdata.get(matmodpath))
                self.matmods[matmod['modId']] = Matmod(matmod, pakdata)

            # Load in object data
            start = time.time()
            self.objects = {}
            obj_list = paktree.get_all_recurs_matching_ext('/objects', '.object')
            for (obj_path, obj_name) in obj_list:
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
            for (img_path, img_name) in img_list:
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

    def get_player(self, player_file):
        """
        Returns player data, given the specified player file
        """
        player = None
        with open(os.path.join(base_player, player_file), 'rb') as playerdf:
            player = Player(starbound.read_sbvj01(playerdf))
        return player
