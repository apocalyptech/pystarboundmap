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

import io
import os
import re
import time
import mmap
import json
import starbound
from PIL import Image
from PyQt5 import QtWidgets, QtGui, QtCore

# Hardcoded stuff for now
base_game = '/usr/local/games/Steam/SteamApps/common/Starbound'
base_storage = os.path.join(base_game, 'storage')
base_player = os.path.join(base_storage, 'player')
base_universe = os.path.join(base_storage, 'universe')
base_pak = os.path.join(base_game, 'assets', 'packed.pak')

# Original game (cheat, abandoned)
#playerfile = os.path.join(base_player, '509185ee4570a66b2d514e2e4740199c.player')

# Current game (Destructicus)
playerfile = os.path.join(base_player, '1d6a362efdf17303b77e33c75f73114f.player')
#world_name = 'Fribbilus Xax Swarm II'
world_name = 'Fribbilus Xax Swarm IV'

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

class MapScene(QtWidgets.QGraphicsScene):
    """
    Our main scene which renders the map.
    """

    def __init__(self, parent, mainwindow):

        super().__init__(parent)
        self.mainwindow = mainwindow
        self.load_map()

    def load_map(self):

        # Just draw the starting region, as a start
        #x, y = self.mainwindow.world.metadata['playerStart']
        #rx, ry = int(x // 32), int(y // 32)
        #print('Player start at ({}, {}), region ({}, {})'.format(
        #    x, y,
        #    rx, ry,
        #    ))
        #self.draw_region(rx, ry)

        # Draw the whole map.  Here we go!
        for (rx, ry) in self.mainwindow.world.get_all_regions_with_tiles():
            self.draw_region(rx, ry)

        # We'll have to see if this is actually necessary or not.
        # I suspect not, really.
        #self.setSceneRect(QtCore.QRectF(start_x, start_y, 256, 256))

    def draw_region(self, rx, ry):
        """
        Draws the specified region (if we can)
        """
        # Some convenience vars
        pakdata = self.mainwindow.pakdata
        materials = self.mainwindow.materials
        matmods = self.mainwindow.matmods
        objects = self.mainwindow.objects
        world = self.mainwindow.world

        # Get tiles
        try:
            tiles = world.get_tiles(rx, ry)
        except KeyError:
            print('WARNING: Region ({}, {}) was not found in world'.format(rx, ry))
            return

        # "real" coordinates
        start_x = rx*256
        start_y = world.height-ry*256

        # Background for our drawn area (black)
        self.addRect(start_x, start_y, 255, 255,
                QtGui.QPen(QtGui.QColor(0, 0, 0)),
                QtGui.QBrush(QtGui.QColor(0, 0, 0)),
                )

        # Materials (background)
        cur_row = 31
        cur_col = 0
        for tile in tiles:
            if tile.background_material in materials and tile.foreground_material not in materials:
                qpmi = QtWidgets.QGraphicsPixmapItem(materials[tile.background_material].bgimage)
                qpmi.setPos(start_x+cur_col*8, start_y+cur_row*8)
                self.addItem(qpmi)
            cur_col += 1
            if cur_col == 32:
                cur_col = 0
                cur_row -= 1

        # Matmods (background)
        cur_row = 31
        cur_col = 0
        for tile in tiles:
            if tile.background_mod in matmods and tile.foreground_material not in materials:
                qpmi = QtWidgets.QGraphicsPixmapItem(matmods[tile.background_mod].bgimage)
                qpmi.setPos(start_x+cur_col*8-4, start_y+cur_row*8-4)
                self.addItem(qpmi)
            cur_col += 1
            if cur_col == 32:
                cur_col = 0
                cur_row -= 1

        # Materials (foreground)
        cur_row = 31
        cur_col = 0
        for tile in tiles:
            if tile.foreground_material in materials:
                qpmi = QtWidgets.QGraphicsPixmapItem(materials[tile.foreground_material].image)
                qpmi.setPos(start_x+cur_col*8, start_y+cur_row*8)
                self.addItem(qpmi)
            cur_col += 1
            if cur_col == 32:
                cur_col = 0
                cur_row -= 1

        # Entities!
        entities = []
        try:
            entities = world.get_entities(rx, ry)
        except KeyError:
            pass

        for e in entities:
            if e.name == 'PlantEntity':
                # Ignoring for now
                pass
            elif e.name == 'ObjectEntity':
                # Woo
                obj_name = e.data['name']
                obj_orientation = e.data['orientationIndex']
                (obj_x, obj_y) = tuple(e.data['tilePosition'])
                if obj_name in objects:
                    obj = objects[obj_name]
                    (image, offset_x, offset_y) = obj.get_image(obj_orientation)
                    qpmi = QtWidgets.QGraphicsPixmapItem(image)
                    #print('--')
                    #print('Drawing w/ coords {}, {}'.format(obj_x, obj_y))
                    #print('Adjusting for rx, ry {}, {}: {}, {}'.format(32*rx, 32*ry, obj_x-(32*rx), obj_y-(32*ry)))
                    #print('Offset: {}, {}'.format(offset_x, offset_y))
                    qpmi.setPos(start_x+(obj_x-(32*rx))*8+offset_x, start_y+(32-(obj_y-(32*ry))-2)*8+offset_y)
                    self.addItem(qpmi)
            else:
                print('Unknown entity type: {}'.format(e.name))

        #keycounts = {}
        #for idx, e in enumerate(entities):
        #    print('Entity {}'.format(idx))
        #    for k in e.data.keys():
        #        print(' * {}'.format(k))
        #        if k not in keycounts:
        #            keycounts[k] = 1
        #        else:
        #            keycounts[k] += 1
        #for k, v in keycounts.items():
        #    print('{}: {}'.format(k, v))

        # Matmods (foreground)
        cur_row = 31
        cur_col = 0
        for tile in tiles:
            if tile.foreground_mod in matmods:
                qpmi = QtWidgets.QGraphicsPixmapItem(matmods[tile.foreground_mod].image)
                qpmi.setPos(start_x+cur_col*8-4, start_y+cur_row*8-4)
                self.addItem(qpmi)
            cur_col += 1
            if cur_col == 32:
                cur_col = 0
                cur_row -= 1

class MapArea(QtWidgets.QGraphicsView):
    """
    Main area rendering the map
    """

    def __init__(self, parent):

        super().__init__(parent)
        self.mainwindow = parent
        self.scene = MapScene(self, parent)
        self.setScene(self.scene)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(200, 200, 200)))
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

class GUI(QtWidgets.QMainWindow):
    """
    Main application window
    """

    def __init__(self, pakdata, materials, matmods, objects, world):
        super().__init__()
        self.pakdata = pakdata
        self.materials = materials
        self.matmods = matmods
        self.objects = objects
        self.world = world
        self.initUI()

    def initUI(self):

        # File Menu
        menubar = self.menuBar()
        filemenu = menubar.addMenu('&File')
        filemenu.addAction('&Quit', self.action_quit, 'Ctrl+Q')

        # Main Widget
        self.maparea = MapArea(self)
        self.scene = self.maparea.scene
        self.setCentralWidget(self.maparea)

        # Main window
        self.setMinimumSize(900, 700)
        self.resize(900, 700)
        self.setWindowTitle('Starbound Mapper')

        # Show
        self.show()

    def action_quit(self):
        """
        Handle our "Quit" action.
        """
        self.close()

class Material(object):
    """
    Holds info about a material.  Right now we're ignoring all the
    fancy rendering options and pretending that everything is the
    very first (top left) tile, and we're not drawing edges or the
    like.

    NOTE: In addition to the above, this only supports classicmaterialtemplate
    """

    def __init__(self, info, pakdata):
        self.info = info
        self.name = info['materialName']
        df = io.BytesIO(pakdata.get(
                '/tiles/materials/{}'.format(info['renderParameters']['texture'])
                ))
        full_image = Image.open(df)
        cropped = full_image.crop((4, 12, 12, 20))
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

class Application(QtWidgets.QApplication):
    """
    Main application
    """

    def __init__(self):
        super().__init__([])

        # Read in the data file
        with open(base_pak, 'rb') as pakdf:

            paktree = PakTree()
            pakdata = starbound.SBAsset6(pakdf)

            # py-starbound doesn't let you "browse" inside the pakfile's
            # internal "directory", so we're doing it by hand here
            pakdata.read_index()
            for path in pakdata.index.keys():
                paktree.add_path(path)

            # Load in our materials
            materials = {}
            for matname in paktree.get_all_matching_ext('/tiles/materials', '.material'):
                matpath = '/tiles/materials/{}'.format(matname)
                material = json.loads(pakdata.get(matpath))
                # Ignoring other kinds of tiles for now
                if 'classicmaterialtemplate.config' in material['renderTemplate']:
                    materials[material['materialId']] = Material(material, pakdata)

            # Load in our material mods.
            matmods = {}
            for matmod_name in paktree.get_all_matching_ext('/tiles/mods', '.matmod'):
                # All matmods, at least in the base game, are classicmaterialtemplate
                matmodpath = '/tiles/mods/{}'.format(matmod_name)
                matmod = json.loads(pakdata.get(matmodpath))
                matmods[matmod['modId']] = Matmod(matmod, pakdata)

            # Load in object data
            start = time.time()
            objects = {}
            obj_list = paktree.get_all_recurs_matching_ext('/objects', '.object')
            for (obj_path, obj_name) in obj_list:
                obj_full_path = '{}/{}'.format(obj_path, obj_name)
                obj_json = read_config(pakdata.get(obj_full_path))
                objects[obj_json['objectName']] = SBObject(obj_json, obj_name, obj_path, pakdata)
            end = time.time()
            print('Loaded objects in {} sec'.format(end-start))

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

            with open(playerfile, 'rb') as playerdf:
                player = starbound.read_sbvj01(playerdf)
                print('Showing data for {}'.format(player.data['identity']['name']))
                # keys in player.data:
                #   movementController
                #   uuid
                #   modeType
                #   description
                #   statusController
                #   deployment
                #   inventory
                #   techs
                #   techController
                #   quests
                #   universeMap
                #   codexes
                #   aiState
                #   companions
                #   blueprints
                #   identity
                #   team
                #   log
                #   shipUpgrades

                # Will have to check that the universeMap dicts always has just one key
                # (a uuid or something)
                for k, v in player.data['universeMap'].items():
                    # universeMap keys:
                    #   systems
                    #   teleportBookmarks

                    systemlist = v['systems']
                    for (coords, systemdict) in systemlist:
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
                            print('Opening {}'.format(world_filename))
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
                                if strip_colors(cp['name']) == world_name:
                                    print('Found world {}, type {}, size {}x{} - Subtypes:'.format(
                                        world_name,
                                        cp['parameters']['worldType'],
                                        world.width,
                                        world.height,
                                        ))
                                    for subtype in cp['parameters']['terrestrialType']:
                                        print(' * {}'.format(subtype))

                                    self.app = GUI(pakdata, materials, matmods, objects, world)
                                    return

        # If we got here, we didn't find what we wanted
        raise Exception('World not found')
