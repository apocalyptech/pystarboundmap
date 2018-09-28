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
        materials = self.parent.data.materials
        matmods = self.parent.data.matmods
        world = self.parent.world

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
        #print('Tile ({}, {}), Region ({}, {})'.format(self.x, self.y, self.rx, self.ry))
        self.parent.mainwindow.data_table.set_region(self.rx, self.ry)
        self.parent.mainwindow.data_table.set_tile(self.x, self.y)
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

    def __init__(self, parent, mainwindow, data):

        super().__init__(parent)
        self.parent = parent
        self.mainwindow = mainwindow
        self.data = data
        self.world = None

    def load_map(self, world):

        # Store the world reference
        self.world = world

        # Get a list of all regions so we know the count and can draw a
        # QProgressDialog usefully
        regions = world.get_all_regions_with_tiles()
        print('{} regions to load'.format(len(regions)))

        # Get all pending app events out of the way
        self.mainwindow.app.processEvents()

        # Hide the main qgraphicsview while we're loading
        self.parent.hide()

        # Set up the QProgressDialog
        qpg = QtWidgets.QProgressDialog(self.mainwindow)
        qpg.setWindowTitle('Loading World')
        qpg.setLabelText('Loading World')
        qpg.setRange(0, len(regions))
        qpg.setValue(0)
        qpg.setWindowModality(QtCore.Qt.WindowModal)
        qpg.setMinimumSize(300, 100)
        qpg.show()

        # Draw the whole map.  Here we go!
        start = time.time()
        for idx, (rx, ry) in enumerate(regions):
            self.draw_region(rx, ry)
            # mod value has been tweaked a bit to find something that doesn't
            # affect load performance much but still updates reasonably quickly.
            # Obviously that depends on box performance a bit; this value seems
            # all right on my CPU, at least.
            if (idx % 50) == 0:
                qpg.setValue(idx)
                self.mainwindow.app.processEvents()
                if qpg.wasCanceled():
                    # TODO: handle this better
                    sys.exit(1)
        end = time.time()
        print('Loaded map in {:.1f} secs'.format(end-start))

        # Close the progress dialog
        qpg.close()

        # For now, center on the starting region
        # (this doesn't seem *totally* right, though perhaps the player
        # technically starts in the air a bit?)
        (start_x, start_y) = self.world.metadata['playerStart']
        self.parent.centerOn(start_x*8, (self.world.height*8)-(start_y*8))

        # Show the main qgraphicsview once we're done
        self.parent.show()

    def draw_region(self, rx, ry):
        """
        Draws the specified region (if we can)
        """
        # Some convenience vars
        materials = self.data.materials
        matmods = self.data.matmods
        objects = self.data.objects
        world = self.world

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

    def __init__(self, parent, data):

        super().__init__(parent)
        self.mainwindow = parent
        self.scene = MapScene(self, parent, data)
        self.setScene(self.scene)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(200, 200, 200)))
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

class DataTable(QtWidgets.QWidget):
    """
    Widget to show information about the currently-hovered tile
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedWidth(150)

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.cur_row = 0

        self.region_label = self.add_row('Region')
        self.tile_label = self.add_row('Tile')

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

        # table to store data display
        self.data_table = DataTable(self)
        hbox.addWidget(self.data_table, 0, QtCore.Qt.AlignLeft)

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

