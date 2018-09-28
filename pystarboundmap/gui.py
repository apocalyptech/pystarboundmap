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
import time
import mmap
import json
import starbound
from PyQt5 import QtWidgets, QtGui, QtCore
from .data import read_config, strip_colors, Material, Matmod, SBObject, PakTree

# Hardcoded stuff for now
base_game = '/usr/local/games/Steam/SteamApps/common/Starbound'
base_storage = os.path.join(base_game, 'storage')
base_player = os.path.join(base_storage, 'player')
base_universe = os.path.join(base_storage, 'universe')
base_pak = os.path.join(base_game, 'assets', 'packed.pak')

# Original game (cheat, abandoned)
#playerfile = os.path.join(base_player, '509185ee4570a66b2d514e2e4740199c.player')
#world_name = 'Kuma Expanse IV'

# Current game (Destructicus)
playerfile = os.path.join(base_player, '1d6a362efdf17303b77e33c75f73114f.player')
#world_name = 'Fribbilus Xax Swarm II'
world_name = 'Fribbilus Xax Swarm IV'

class Constants(object):

    (z_black,
        z_background,
        z_background_mod,
        z_foreground,
        z_objects,
        z_foreground_mod,
        z_overlay,
        ) = range(7)

class GUITile(QtWidgets.QGraphicsRectItem):
    """
    Hoverable area which the user can click on for info, etc.
    """

    def __init__(self, parent, tile, x, y, rx, ry, gui_x, gui_y):
        super().__init__()
        self.parent = parent
        self.tile = tile
        self.x = x
        self.y = y
        self.rx = rx
        self.ry = ry
        self.gui_x = gui_x
        self.gui_y = gui_y
        self.setAcceptHoverEvents(True)
        #self.setFlags(self.ItemIsFocusable)
        self.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 0)))
        self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        self.setRect(0, 0, 8, 8)
        self.setPos(gui_x, gui_y)
        self.setZValue(Constants.z_overlay)

        # Convenience vars
        materials = self.parent.mainwindow.materials
        matmods = self.parent.mainwindow.matmods
        world = self.parent.mainwindow.world

        # Materials (background)
        if tile.background_material in materials and tile.foreground_material not in materials:
            self.material_background = QtWidgets.QGraphicsPixmapItem(materials[tile.background_material].bgimage)
            self.material_background.setPos(gui_x, gui_y)
            self.material_background.setZValue(Constants.z_background)
            self.parent.addItem(self.material_background)

        # Matmods (background)
        if tile.background_mod in matmods and tile.foreground_material not in materials:
            self.mod_background = QtWidgets.QGraphicsPixmapItem(matmods[tile.background_mod].bgimage)
            self.mod_background.setPos(gui_x-4, gui_y-4)
            self.mod_background.setZValue(Constants.z_background_mod)
            self.parent.addItem(self.mod_background)

        # Materials (foreground)
        if tile.foreground_material in materials:
            self.material_foreground = QtWidgets.QGraphicsPixmapItem(materials[tile.foreground_material].image)
            self.material_foreground.setPos(gui_x, gui_y)
            self.material_foreground.setZValue(Constants.z_foreground)
            self.parent.addItem(self.material_foreground)

        # Matmods (foreground)
        if tile.foreground_mod in matmods:
            self.mod_foreground = QtWidgets.QGraphicsPixmapItem(matmods[tile.foreground_mod].image)
            self.mod_foreground.setPos(gui_x-4, gui_y-4)
            self.mod_foreground.setZValue(Constants.z_foreground_mod)
            self.parent.addItem(self.mod_foreground)

    def hoverEnterEvent(self, event=None):
        # TODO: Changing brush/pen to get visual highlighting makes the
        # hover events slooooow.  The highlighting lags *significantly*
        # behind the mouse.  Perhaps swapping graphics on our child
        # tiles would work instead?  (pre-brightened, like we do for
        # the background images currently, perhaps?)  Anyway, for now
        # I'm just coping without visual notification.
        print('Tile ({}, {}), Region ({}, {})'.format(self.x, self.y, self.rx, self.ry))
        #self.setBrush(QtGui.QBrush(QtGui.QColor(255, 128, 128, 128)))
        #self.setPen(QtGui.QPen(QtGui.QColor(255, 128, 128, 128)))
        #self.setFocus()

    def hoverLeaveEvent(self, event=None):
        pass
        #self.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 0)))
        #self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        #self.clearFocus()

class MapScene(QtWidgets.QGraphicsScene):
    """
    Our main scene which renders the map.
    """

    def __init__(self, parent, mainwindow):

        super().__init__(parent)
        self.parent = parent
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
        base_x = rx*32
        gui_x = base_x*8
        base_y = ry*32
        gui_y = (world.height*8)-(base_y*8)

        # Background for our drawn area (black)
        region_bak = self.addRect(gui_x, gui_y, 255, 255,
                QtGui.QPen(QtGui.QColor(0, 0, 0)),
                QtGui.QBrush(QtGui.QColor(0, 0, 0)),
                )
        region_bak.setZValue(Constants.z_black)

        # Tiles!
        cur_row = 31
        cur_col = 0
        for tile in tiles:
            self.addItem(GUITile(self, tile,
                base_x+cur_col, base_y+31-cur_row,
                rx, ry,
                gui_x+cur_col*8, gui_y+cur_row*8))
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
            if e.name == 'ObjectEntity':
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
                    qpmi.setPos(gui_x+(obj_x-(32*rx))*8+offset_x, gui_y+(32-(obj_y-(32*ry))-2)*8+offset_y)
                    qpmi.setZValue(Constants.z_objects)
                    self.addItem(qpmi)
            elif (e.name == 'PlantEntity'
                    or e.name == 'MonsterEntity'
                    or e.name == 'NpcEntity'
                    or e.name == 'StagehandEntity'
                    or e.name == 'ItemDropEntity'):
                # Ignoring for now
                pass
            else:
                print('Unknown entity type: {}'.format(e.name))

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
                                print('Loaded world: {}'.format(strip_colors(cp['name'])))
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
