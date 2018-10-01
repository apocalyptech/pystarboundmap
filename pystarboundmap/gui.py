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
import sys
import time
from PyQt5 import QtWidgets, QtGui, QtCore
from .data import StarboundData

# Hardcoded, for now:

# Original game (cheat, abandoned)
#playerfile = '509185ee4570a66b2d514e2e4740199c.player'
#world_name = 'Kuma Expanse IV'

# Current game (Destructicus)
playerfile = '1d6a362efdf17303b77e33c75f73114f.player'
world_name = 'Fribbilus Xax Swarm I'
#world_name = 'Fribbilus Xax Swarm II'
#world_name = 'Fribbilus Xax Swarm IV'

class Constants(object):

    (z_black,
        z_background,
        z_background_mod,
        z_plants,
        z_foreground,
        z_objects,
        z_foreground_mod,
        z_overlay,
        ) = range(8)

class GUITile(QtWidgets.QGraphicsRectItem):
    """
    Hoverable area which the user can click on for info, etc.
    """

    def __init__(self, parent, tile, x, y, region, gui_x, gui_y):
        super().__init__()
        self.parent = parent
        self.tile = tile
        self.x = x
        self.y = y
        self.region = region
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
        materials = self.parent.data.materials
        matmods = self.parent.data.matmods
        world = self.parent.world

        # Materials (background)
        self.material_background = None
        if tile.background_material in materials and tile.foreground_material not in materials:
            self.material_background = QtWidgets.QGraphicsPixmapItem(materials[tile.background_material].bgimage)
            self.material_background.setPos(gui_x, gui_y)
            self.material_background.setZValue(Constants.z_background)
            self.parent.addItem(self.material_background)

        # Matmods (background)
        self.mod_background = None
        if tile.background_mod in matmods and tile.foreground_material not in materials:
            self.mod_background = QtWidgets.QGraphicsPixmapItem(matmods[tile.background_mod].bgimage)
            self.mod_background.setPos(gui_x-4, gui_y-4)
            self.mod_background.setZValue(Constants.z_background_mod)
            self.parent.addItem(self.mod_background)

        # Materials (foreground)
        self.material_foreground = None
        if tile.foreground_material in materials:
            self.material_foreground = QtWidgets.QGraphicsPixmapItem(materials[tile.foreground_material].image)
            self.material_foreground.setPos(gui_x, gui_y)
            self.material_foreground.setZValue(Constants.z_foreground)
            self.parent.addItem(self.material_foreground)

        # Matmods (foreground)
        self.mod_foreground = None
        if tile.foreground_mod in matmods:
            self.mod_foreground = QtWidgets.QGraphicsPixmapItem(matmods[tile.foreground_mod].image)
            self.mod_foreground.setPos(gui_x-4, gui_y-4)
            self.mod_foreground.setZValue(Constants.z_foreground_mod)
            self.parent.addItem(self.mod_foreground)

    def unload(self):
        """
        Unloads ourself from the scene
        """
        if self.material_background:
            self.parent.removeItem(self.material_background)
            self.material_background = None
        if self.mod_background:
            self.parent.removeItem(self.mod_background)
            self.mod_background = None
        if self.material_foreground:
            self.parent.removeItem(self.material_foreground)
            self.material_foreground = None
        if self.mod_foreground:
            self.parent.removeItem(self.mod_foreground)
            self.mod_foreground = None

    def hoverEnterEvent(self, event=None):
        data_table = self.parent.mainwindow.data_table
        materials = self.parent.data.materials
        matmods = self.parent.data.matmods

        data_table.set_region(self.region.rx, self.region.ry)
        data_table.set_tile(self.x, self.y)

        if self.tile.foreground_material in materials:
            data_table.set_material(materials[self.tile.foreground_material].name)
        else:
            if self.tile.foreground_material >= 0:
                data_table.set_material('Unknown ({})'.format(self.tile.foreground_material))
            else:
                data_table.set_material('')

        if self.tile.foreground_mod in matmods:
            data_table.set_matmod(matmods[self.tile.foreground_mod].name)
        else:
            if self.tile.foreground_mod >= 0:
                data_table.set_matmod('Unknown ({})'.format(self.tile.foreground_mod))
            else:
                data_table.set_matmod('')

        if self.tile.background_material in materials:
            data_table.set_back_material(materials[self.tile.background_material].name)
        else:
            if self.tile.background_material >= 0:
                data_table.set_back_material('Unknown ({})'.format(self.tile.background_material))
            else:
                data_table.set_back_material('')

        if self.tile.background_mod in matmods:
            data_table.set_back_matmod(matmods[self.tile.background_mod].name)
        else:
            if self.tile.background_mod >= 0:
                data_table.set_back_matmod('Unknown ({})'.format(self.tile.background_mod))
            else:
                data_table.set_back_matmod('')

        # TODO: Might want to pre-brighten our images and swap 'em out.  Or
        # at least do so for objects, so we could highlight the whole thing.
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 128)))
        self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        #self.setFocus()

    def hoverLeaveEvent(self, event=None):
        self.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 0)))
        self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        #self.clearFocus()

class GUIRegion(object):
    """
    Class to hold info about a single region
    """

    def __init__(self, scene, rx, ry, data, world):
        self.scene = scene
        self.rx = rx
        self.ry = ry
        self.data = data
        self.world = world
        self.children = []
        self.tiles = []
        self.loaded = False

    def load(self):
        """
        Loads ourself into memory
        """

        if self.loaded:
            return

        self.children = []
        self.tiles = []

        # Some convenience vars
        materials = self.data.materials
        matmods = self.data.matmods
        objects = self.data.objects
        plants = self.data.plants
        world = self.world
        self.loaded = True

        # Get tiles
        try:
            data_tiles = world.get_tiles(self.rx, self.ry)
        except KeyError:
            print('WARNING: Region ({}, {}) was not found in world'.format(self.rx, self.ry))
            return

        # "real" coordinates
        base_x = self.rx*32
        gui_x = base_x*8
        base_y = self.ry*32
        gui_y = (world.height*8)-(base_y*8)

        # Background for our drawn area (black)
        region_bak = self.scene.addRect(gui_x, gui_y-255, 255, 255,
                QtGui.QPen(QtGui.QColor(0, 0, 0)),
                QtGui.QBrush(QtGui.QColor(0, 0, 0)),
                )
        region_bak.setZValue(Constants.z_black)
        self.children.append(region_bak)

        # Tiles!
        cur_row = 0
        cur_col = 0
        for data_tile in data_tiles:
            self.tiles.append(GUITile(self.scene, data_tile,
                base_x+cur_col, base_y+cur_row,
                self,
                gui_x+cur_col*8, gui_y-(cur_row+1)*8))
            self.scene.addItem(self.tiles[-1])
            cur_col += 1
            if cur_col == 32:
                cur_col = 0
                cur_row += 1

        # Entities!
        entities = []
        try:
            entities = world.get_entities(self.rx, self.ry)
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
                    qpmi.setPos(
                            (obj_x*8) + offset_x,
                            (world.height*8)-(obj_y*8) - offset_y - image.height(),
                            )
                    qpmi.setZValue(Constants.z_objects)
                    self.scene.addItem(qpmi)
                    self.children.append(qpmi)
            elif e.name == 'PlantEntity':
                (obj_x, obj_y) = tuple(e.data['tilePosition'])
                for piece in e.data['pieces']:
                    piece_img = piece['image'].split('?')[0]
                    if piece_img in plants:
                        img = plants[piece_img].image
                        qpmi = QtWidgets.QGraphicsPixmapItem(img)
                        qpmi.setPos(
                                (obj_x*8) + (piece['offset'][0]*8),
                                (world.height*8)-(obj_y*8) - (piece['offset'][1]*8) - img.height(),
                                )
                        qpmi.setZValue(Constants.z_plants)
                        self.scene.addItem(qpmi)
                        self.children.append(qpmi)
                    else:
                        print('not found: {}'.format(piece_img))
            elif (e.name == 'MonsterEntity'
                    or e.name == 'NpcEntity'
                    or e.name == 'StagehandEntity'
                    or e.name == 'ItemDropEntity'):
                # Ignoring for now
                pass
            else:
                print('Unknown entity type: {}'.format(e.name))

    def unload(self):
        """
        Unload from the graphics scene
        """
        for child in self.children:
            self.scene.removeItem(child)
        for tile in self.tiles:
            tile.unload()
            self.scene.removeItem(tile)
        self.tiles = []
        self.children = []
        self.loaded = False

class MapScene(QtWidgets.QGraphicsScene):
    """
    Our main scene which renders the map.
    """

    def __init__(self, parent, mainwindow, data):

        super().__init__(parent)
        self.parent = parent
        self.mainwindow = mainwindow
        self.data = data
        self.world = None
        self.regions = {}
        self.loaded_regions = set()
        self.hbar = self.parent.horizontalScrollBar()
        self.hbar.sliderReleased.connect(self.draw_visible_area)
        self.vbar = self.parent.verticalScrollBar()
        self.vbar.sliderReleased.connect(self.draw_visible_area)

        self.dragging = False
        self.moved = False

        # This is used so that our first couple of GUI-setup steps doesn't
        # trigger a map-loading event (until we're actually ready for it)
        self.given_center = False

    def mousePressEvent(self, event):
        """
        Handle a mouse press event (just dragging for now)
        """
        # TODO: I'll probably want to be able to click on a tile to get more
        # info, etc, so this'll have to be smarter
        self.dragging = True
        self.moved = False
        self.parent.setCursor(QtCore.Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        """
        Handle a mouse release event
        """
        self.dragging = False
        self.parent.unsetCursor()
        if self.moved:
            self.draw_visible_area()
            self.moved = False

    def mouseMoveEvent(self, event):
        """
        Mouse Movement
        """
        if self.dragging:
            last = event.lastScreenPos()
            pos = event.screenPos()
            delta_x = last.x() - pos.x()
            delta_y = last.y() - pos.y()
            if delta_x != 0:
                self.dragged = True
                sb = self.parent.horizontalScrollBar()
                new_x = sb.value() + delta_x
                if new_x >= sb.minimum() and new_x <= sb.maximum():
                    sb.setValue(new_x)
                self.moved = True
            if delta_y != 0:
                self.dragged = True
                sb = self.parent.verticalScrollBar()
                new_y = sb.value() + delta_y
                if new_y >= sb.minimum() and new_y <= sb.maximum():
                    sb.setValue(new_y)
                self.moved = True
        else:
            super().mouseMoveEvent(event)

    def load_map(self, world):

        # Store the world reference
        self.world = world
        self.regions = {}

        # Get a list of all regions so we know the count and can draw a
        # QProgressDialog usefully
        min_region_x = 99999999
        min_region_y = 99999999
        max_region_x = 0
        max_region_y = 0
        for region in world.get_all_regions_with_tiles():
            self.regions[region] = GUIRegion(self, region[0], region[1], self.data, self.world)
            min_region_x = min(region[0], min_region_x)
            min_region_y = min(region[1], min_region_y)
            max_region_x = max(region[0], max_region_x)
            max_region_y = max(region[1], max_region_y)

        # Figure out our bounding areas
        start_x = min_region_x*256
        start_y = (world.height*8) - ((max_region_y+1)*256)
        end_x = (max_region_x+1)*256
        end_y = (world.height*8) - (min_region_y*256)
        self.setSceneRect(start_x, start_y, end_x - start_x, end_y - start_y)

        # Get all pending app events out of the way
        self.mainwindow.app.processEvents()

        # For now, center on the starting region
        self.center_on(*self.world.metadata['playerStart'])

    def ingame_to_scene(self, x, y):
        """
        Converts the in-game coordinates (x, y) to scene coordinates,
        centered on the middle of the tile
        """
        new_x = (x*8)+4
        # TODO: this y coord may be slightly off
        new_y = (self.world.height*8) - (y*8) - 4
        return (new_x, new_y)

    def scene_to_ingame(self, x, y):
        """
        Converts scene coordinates (x, y) to in-game coordinates.
        """
        new_x = x//8
        # TODO: this y coord may be slightly off
        new_y = ((self.world.height*8) - y)//8
        return (new_x, new_y)

    def center_on(self, x, y):
        """
        Centers ourself around the in-game coordinates (x, y)
        """

        # Mark that we can start actually drawing now
        self.given_center = True

        # Center the view
        (ctr_x, ctr_y) = self.ingame_to_scene(x, y)
        self.parent.centerOn(ctr_x, ctr_y)

        # Draw what needs drawing
        self.draw_visible_area()

    def draw_visible_area(self):
        """
        Draws the visible area of the scrollbar, and a bit of padding to
        help scrolling hopefully keep up a bit.  Will also purge regions
        which are sufficiently out-of-view.
        """

        if not self.given_center:
            return

        # Figure out what regions we should be showing
        horiz_width = self.hbar.pageStep()
        gui_start_x = self.hbar.value()
        vert_width = self.vbar.pageStep()
        gui_start_y = self.vbar.value()
        (game_min_x, game_max_y) = self.scene_to_ingame(gui_start_x, gui_start_y)
        (game_max_x, game_min_y) = self.scene_to_ingame(
                gui_start_x + horiz_width,
                gui_start_y + vert_width,
                )
        min_rx = game_min_x//32 - 1
        max_rx = game_max_x//32 + 1
        min_ry = game_min_y//32 - 1
        max_ry = game_max_y//32 + 1

        # First find out how many regions we're going to have to load (so that
        # we can initialize a progressbar)
        valid_regions = set()
        regions_to_load = []
        for rx in range(min_rx, max_rx+1):
            for ry in range(min_ry, max_ry+1):
                region = (rx, ry)
                valid_regions.add(region)
                if region in self.regions:
                    if not self.regions[region].loaded:
                        regions_to_load.append(region)

        # Initialize progressbar
        region_loading = self.mainwindow.region_loading
        region_loading.start(len(regions_to_load))

        # Now actually do the loading
        for idx, region in enumerate(regions_to_load):
            #print('Loading region {}'.format(region))
            self.regions[region].load()
            self.loaded_regions.add(region)
            region_loading.update(idx)

        # Unload regions which are too far out
        for region in list(self.loaded_regions):
            if region not in valid_regions:
                #print('Unloading region {}'.format(region))
                self.regions[region].unload()
                self.loaded_regions.remove(region)

        # Finish our progress bar
        region_loading.finish()

class MapArea(QtWidgets.QGraphicsView):
    """
    Main area rendering the map
    """

    def __init__(self, parent, data):

        super().__init__(parent)
        self.mainwindow = parent
        self.scene = MapScene(self, parent, data)
        self.setScene(self.scene)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(200, 200, 200)))
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scene.draw_visible_area()

    def wheelEvent(self, event):
        super().wheelEvent(event)
        self.scene.draw_visible_area()

class DataTable(QtWidgets.QWidget):
    """
    Widget to show information about the currently-hovered tile
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedWidth(200)

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.cur_row = 0

        self.region_label = self.add_row('Region')
        self.tile_label = self.add_row('Coords')

        self.mat_label = self.add_row('Fore Mat')
        self.matmod_label = self.add_row('Fore Mod')
        self.back_mat_label = self.add_row('Back Mat')
        self.back_matmod_label = self.add_row('Back Mod')

        # Spacer at the bottom so that the other cells don't expand
        self.layout.addWidget(QtWidgets.QLabel(),
                self.cur_row, 0,
                1, 2)
        self.layout.setRowStretch(self.cur_row, 1)

    def add_row(self, label):
        label = QtWidgets.QLabel('{}:'.format(label))
        label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.layout.addWidget(label,
                self.cur_row, 0,
                QtCore.Qt.AlignRight,
                )
        data_label = QtWidgets.QLabel()
        data_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        self.layout.addWidget(data_label, self.cur_row, 1)
        self.cur_row += 1
        return data_label

    def set_region(self, rx, ry):
        self.region_label.setText('({}, {})'.format(rx, ry))

    def set_tile(self, x, y):
        self.tile_label.setText('({}, {})'.format(x, y))

    def set_material(self, material):
        self.mat_label.setText(material)

    def set_matmod(self, mod):
        self.matmod_label.setText(mod)

    def set_back_material(self, material):
        self.back_mat_label.setText(material)

    def set_back_matmod(self, mod):
        self.back_matmod_label.setText(mod)

class RegionLoadingNotifier(QtWidgets.QWidget):
    """
    Widgets to show a progress bar (and some text) while loading regions
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.text_label = QtWidgets.QLabel('', self)
        self.layout.addWidget(self.text_label, 0, 0)
        self.text_label.hide()

        self.bar = QtWidgets.QProgressBar(self)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.layout.addWidget(self.bar, 1, 0)
        self.num_regions = 1
        self.bar.hide()

    def start(self, num_regions):
        """
        Starts us off
        """

        self.num_regions = num_regions
        if num_regions > 0:
            self.bar.setRange(0, num_regions)
            self.bar.setValue(0)
            self.text_label.setText('Loading Regions: 0/{}'.format(num_regions))
            self.text_label.show()
            self.bar.show()

    def update(self, value):
        """
        Updates with a new value
        """
        self.bar.setValue(value)
        self.text_label.setText('Loading Regions: {}/{}'.format(value, self.num_regions))

    def finish(self):
        """
        Finish!
        """
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.text_label.setText('')
        self.num_regions = 1
        self.text_label.hide()
        self.bar.hide()

class GUI(QtWidgets.QMainWindow):
    """
    Main application window
    """

    def __init__(self, app):
        super().__init__()

        self.app = app

        # Load data.  This more technically belongs in the Application
        # class but whatever.
        self.data = StarboundData()

        # Initialization stuff
        self.world = None
        self.initUI()

        # Show ourselves
        self.show()

        # For now, hardcoded loading of a specific map
        self.load_map()

    def initUI(self):

        # File Menu
        menubar = self.menuBar()
        filemenu = menubar.addMenu('&File')
        filemenu.addAction('&Quit', self.action_quit, 'Ctrl+Q')

        # HBox to store our main widgets
        w = QtWidgets.QWidget()
        hbox = QtWidgets.QHBoxLayout()
        w.setLayout(hbox)

        # Lefthand side vbox
        lh = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout()
        lh.setLayout(vbox)
        hbox.addWidget(lh, 0, QtCore.Qt.AlignLeft)

        # table to store data display
        self.data_table = DataTable(self)
        vbox.addWidget(self.data_table, 0, QtCore.Qt.AlignLeft)

        # Spacer on the lefthand panel
        spacer = QtWidgets.QWidget()
        vbox.addWidget(spacer, 1)

        # Region-loading display
        self.region_loading = RegionLoadingNotifier(self)
        vbox.addWidget(self.region_loading, 0)

        # Main Widget
        self.maparea = MapArea(self, self.data)
        self.scene = self.maparea.scene
        hbox.addWidget(self.maparea, 1)

        # Central Widget
        self.setCentralWidget(w)

        # Main window
        self.setMinimumSize(1050, 700)
        self.resize(1050, 700)
        self.setWindowTitle('Starbound Mapper')

    def action_quit(self):
        """
        Handle our "Quit" action.
        """
        self.close()

    def load_map(self):
        """
        Hardcoded for now
        """

        player = self.data.get_player(playerfile)
        if player:
            self.world = player.get_worlds(world_name)

        if self.world:
            self.scene.load_map(self.world)
        else:
            # TODO: Once we have interactive stuff, handle this better.
            raise Exception('World not found')

class Application(QtWidgets.QApplication):
    """
    Main application
    """

    def __init__(self):
        super().__init__([])
        self.app = GUI(self)

