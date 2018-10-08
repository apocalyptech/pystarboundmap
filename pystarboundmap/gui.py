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
import re
import sys
import time
import struct
import timeago
import datetime
from PyQt5 import QtWidgets, QtGui, QtCore
from .data import StarboundData
from .config import Config

class Constants(object):

    (z_black,
        z_background,
        z_background_mod,
        z_plants,
        z_foreground,
        z_objects,
        z_foreground_mod,
        z_liquids,
        z_overlay,
        ) = range(9)

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
        liquids = self.parent.data.liquids
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

        # Liquids
        self.liquid = None
        if tile.liquid in liquids:
            self.liquid = QtWidgets.QGraphicsRectItem()
            self.liquid.setRect(0, 0, 8, 8)
            self.liquid.setPos(gui_x, gui_y)
            self.liquid.setBrush(QtGui.QBrush(liquids[tile.liquid].overlay))
            self.liquid.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
            self.liquid.setZValue(Constants.z_liquids)
            self.parent.addItem(self.liquid)

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
        if self.liquid:
            self.parent.removeItem(self.liquid)
            self.liquid = None

    def hoverEnterEvent(self, event=None):
        data_table = self.parent.mainwindow.data_table
        materials = self.parent.data.materials
        matmods = self.parent.data.matmods
        liquids = self.parent.data.liquids

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

        if self.tile.liquid in liquids:
            data_table.set_liquid(liquids[self.tile.liquid].name)
        else:
            if self.tile.liquid > 0:
                data_table.set_liquid('Unknown ({})'.format(self.tile.liquid))
            else:
                data_table.set_liquid('')

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
                    or e.name == 'ItemDropEntity'
                    or e.name == 'VehicleEntity'
                    ):
                # TODO: Ignoring for now
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

    def __init__(self, parent, mainwindow):

        super().__init__(parent)
        self.parent = parent
        self.mainwindow = mainwindow
        self.data = None
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

        # If there's a mech beacon in the map, center there (there will often
        # be just black space visible, otherwise) - otherwise center on the
        # spawn point
        if 'mechbeacon' in self.world.uuid_to_region_map:
            coords = self.world.get_uuid_coords('mechbeacon')
            if coords:
                self.center_on(*coords)
            else:
                self.center_on_spawn()
        else:
            self.center_on_spawn()

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

    def centered_tile(self):
        """
        Returns the ingame coordinates of the tile we're currently
        centered on
        """

        coord_x = int(self.hbar.value() + self.hbar.pageStep()/2)
        coord_y = int(self.vbar.value() + self.vbar.pageStep()/2)
        return self.scene_to_ingame(coord_x, coord_y)

    def center_on_spawn(self):
        """
        Centers ourself on the spawn point
        """
        self.center_on(*self.world.metadata['playerStart'])

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

    def clear(self):
        """
        Clears out our scene
        """
        super().clear()
        self.world = None
        self.regions = {}
        self.loaded_regions = set()
        self.given_center = False

    def refresh(self, data):
        """
        Refreshes our scene - currently just used when we change data
        dirs, because it's possible that our graphics may have changed,
        etc.
        """
        for region in self.loaded_regions:
            self.regions[region].unload()
        super().clear()
        self.data = data
        self.loaded_regions = set()
        self.draw_visible_area()

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
        self.setMinimumWidth(200)

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.cur_row = 0

        self.world_name_label = self.add_row('World')
        self.world_type_label = self.add_row('World Type')
        self.world_extra_label = self.add_row('Extra Info')
        self.world_filename_label = self.add_row('Filename', selectable=True)
        self.world_size_label = self.add_row('Size')

        self.region_label = self.add_row('Region', selectable=True)
        self.tile_label = self.add_row('Coords', selectable=True)

        self.mat_label = self.add_row('Fore Mat')
        self.matmod_label = self.add_row('Fore Mod')
        self.back_mat_label = self.add_row('Back Mat')
        self.back_matmod_label = self.add_row('Back Mod')
        self.liquid_label = self.add_row('Liquid')

        # Spacer at the bottom so that the other cells don't expand
        self.layout.addWidget(QtWidgets.QLabel(),
                self.cur_row, 0,
                1, 2)
        self.layout.setRowStretch(self.cur_row, 1)

    def add_row(self, label, selectable=False):
        label = QtWidgets.QLabel('{}:'.format(label))
        label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.layout.addWidget(label,
                self.cur_row, 0,
                QtCore.Qt.AlignRight,
                )
        data_label = QtWidgets.QLabel()
        data_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
        if selectable:
            data_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.layout.addWidget(data_label, self.cur_row, 1)
        self.cur_row += 1
        return data_label

    def set_world_name(self, world_name):
        self.world_name_label.setText(world_name)

    def set_world_type(self, world_type):
        self.world_type_label.setText(world_type)

    def set_world_extra(self, world_extra):
        self.world_extra_label.setText(world_extra)

    def set_world_filename(self, world_filename):
        self.world_filename_label.setText(world_filename)

    def set_world_size(self, width, height):
        self.world_size_label.setText('{}x{}'.format(width, height))

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

    def set_liquid(self, liquid):
        self.liquid_label.setText(liquid)

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

class OpenByDialog(QtWidgets.QDialog):
    """
    Base dialog for both of our open-by-name dialogs
    """

    def __init__(self, parent, main_label):
        super().__init__(parent)
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setMinimumSize(400, 350)
        self.setWindowTitle('Load Starbound World')

        self.sort_mtime_idx = 0
        self.sort_alpha_idx = 1

        # Layout info
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # Title
        title_label = QtWidgets.QLabel(main_label, self)
        title_label.setStyleSheet('font-weight: bold; font-size: 12pt;')
        layout.addWidget(title_label, 0, QtCore.Qt.AlignCenter)

        # Box to hold sorting buttons
        w = QtWidgets.QWidget()
        hbox = QtWidgets.QHBoxLayout()
        w.setLayout(hbox)
        self.button_mtime = QtWidgets.QPushButton('Sort: new -> old', self)
        self.button_mtime.setCheckable(True)
        self.button_mtime.setChecked(True)
        hbox.addWidget(self.button_mtime)
        self.button_alpha = QtWidgets.QPushButton('Sort: A -> Z', self)
        self.button_alpha.setCheckable(True)
        self.button_alpha.setChecked(False)
        hbox.addWidget(self.button_alpha)
        self.sort_group = QtWidgets.QButtonGroup(self)
        self.sort_group.addButton(self.button_mtime)
        self.sort_group.addButton(self.button_alpha)
        self.sort_group.buttonClicked.connect(self.populate_buttons)
        layout.addWidget(w)

        # Scrolled Area
        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)

        # Scroll Contents
        contents = QtWidgets.QWidget(self)
        self.grid = QtWidgets.QGridLayout()
        contents.setLayout(self.grid)

        # Populate contents
        self.buttons = self.generate_buttons()
        self.populate_buttons()

        # Spacer at the end of the grid (this won't ever get removed, even
        # during re-sorts)
        self.grid.addWidget(QtWidgets.QLabel(''), len(self.buttons), 0)
        self.grid.setRowStretch(len(self.buttons), 1)

        # Add our contents to the scroll widget
        layout.addWidget(self.scroll, 1)
        self.scroll.setWidget(contents)

        # Buttons
        buttonbox = QtWidgets.QDialogButtonBox(self)
        buttonbox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttonbox.rejected.connect(self.reject)
        layout.addWidget(buttonbox, 0, QtCore.Qt.AlignRight)

    def human_date(self, date):
        """
        Given a date, return a human-readable string.  Currently using the
        `timeago` library to provide "<N> hours ago" type strings, rather than
        a big ol' block of timestamp.
        """
        return timeago.format(date)

    def generate_buttons(self):
        """
        This is where the buttons get generated.  Should return the index
        of the last row added so that we can then add an extra row to
        stretch.
        """
        raise Exception('Implement me!')

    def populate_buttons(self):
        """
        Put our buttons in place given the currently-selected sorting
        method.
        """

        # Figure out which index we'll sort on
        if self.sort_group.checkedButton() == self.button_mtime:
            to_sort = self.sort_mtime_idx
            reverse = True
        else:
            to_sort = self.sort_alpha_idx
            reverse = False

        # Now add things.  This'll automatically shuffle stuff around without
        # us having to worry about removing things first.
        for row, (_, _, button) in enumerate(
                sorted(self.buttons, reverse=reverse, key=lambda i: i[to_sort])
                ):
            self.grid.addWidget(button, row, 0)

class OpenByPlanetName(OpenByDialog):
    """
    Dialog to open a world by planet name, rather than by filename
    """

    class PlanetNameButton(QtWidgets.QPushButton):
        """
        Ridiculous little class, but it lets us know which button was clicked, easily.
        """

        def __init__(self, parent, world_name, filename, mtime, extra_text):
            super().__init__(parent)
            self.parent = parent
            self.world_name = world_name
            self.filename = filename
            if extra_text and extra_text != '':
                self.setText("{}\n{}\n{}".format(world_name, extra_text, parent.human_date(mtime)))
            else:
                self.setText(world_name)
            self.clicked.connect(self.planet_clicked)

        def planet_clicked(self):
            self.parent.planet_clicked(self.filename)

    def __init__(self, parent, player):

        self.player = player
        self.parent_dialog = parent
        self.chosen_filename = None
        super().__init__(parent, 'Open Starbound World for {}'.format(player.name))

    def generate_buttons(self):
        """
        This is where the buttons get generated
        """
        buttons = []
        for (mtime, sort_name, world_name, extra_text, filename) in self.player.get_worlds(self.parent_dialog.mainwindow.data):
            button = OpenByPlanetName.PlanetNameButton(self, world_name, filename, mtime, extra_text)
            buttons.append((mtime, sort_name, button))
        return buttons

    def planet_clicked(self, filename):
        """
        A planet was chosen
        """
        self.parent().planet_clicked(filename)
        self.accept()

class OpenByPlayerName(OpenByDialog):
    """
    Dialog to open a world by player name, rather than by filename
    """

    class PlayerNameButton(QtWidgets.QPushButton):
        """
        Ridiculous little class, but it lets us know which button was clicked, easily.
        """

        def __init__(self, parent, player, mtime):
            super().__init__(parent)
            self.parent = parent
            self.player = player
            # TODO: meh, as usual, getting HTML/rich text inside a Qt widget is hard.
            # Would like to Bold the name here, but I don't think it's worth it.
            self.setText("{}\n{}".format(player.name, parent.human_date(mtime)))
            self.clicked.connect(self.player_clicked)

        def player_clicked(self):
            self.parent.player_clicked(self.player)

    def __init__(self, parent):

        self.mainwindow = parent
        self.chosen_player = None
        self.chosen_filename = None
        super().__init__(parent, 'Open Starbound World')

    def generate_buttons(self):
        """
        This is where the buttons get generated
        """
        buttons = []
        for mtime, player in self.mainwindow.data.get_all_players():
            button = OpenByPlayerName.PlayerNameButton(self, player, mtime)
            buttons.append((mtime, player.name.lower(), button))
        return buttons

    def player_clicked(self, player):
        """
        A player was chosen; get its planets.
        """
        self.chosen_player = player
        self.setEnabled(False)
        for (_, _, button) in self.buttons:
            button.setEnabled(False)
        dialog = OpenByPlanetName(self, player)
        dialog.exec()
        self.setEnabled(True)
        for (_, _, button) in self.buttons:
            button.setEnabled(True)

    def planet_clicked(self, filename):
        """
        A planet was chosen
        """
        self.chosen_filename = filename
        self.accept()

class SettingsDialog(QtWidgets.QDialog):
    """
    Settings dialog.  A bit barren, but what are you gonna do?
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.maingui = parent
        self.config = parent.config

        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Settings')
        self.setMinimumSize(700, 150)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # Title
        label = QtWidgets.QLabel('<b>Settings</b>')
        layout.addWidget(label, 0, QtCore.Qt.AlignCenter)

        # Settings Grid
        # If we ever get more than a single setting, it'll probably pay
        # to abstract this a bit
        settings = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout()
        grid.setColumnStretch(1, 1)
        settings.setLayout(grid)
        layout.addWidget(settings, 0)

        # Starbound Data Dir
        grid.addWidget(QtWidgets.QLabel('<b>Starbound Data Dir:</b> '), 0, 0, QtCore.Qt.AlignRight)
        self.cur_data_dir = QtWidgets.QLabel('')
        self.cur_data_dir.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.cur_data_dir.setFrameShape(QtWidgets.QFrame.Panel)
        self.cur_data_dir.setBackgroundRole(QtGui.QPalette.AlternateBase)
        self.cur_data_dir.setAutoFillBackground(True)
        self.set_data_dir_display()
        grid.addWidget(self.cur_data_dir, 0, 1)
        starbound_data_dir_button = QtWidgets.QPushButton('Choose', self)
        starbound_data_dir_button.clicked.connect(self.choose_starbound_data_dir)
        grid.addWidget(starbound_data_dir_button, 0, 2)

        # Spacer
        layout.addWidget(QtWidgets.QLabel(''), 1)

        # Buttons
        buttonbox = QtWidgets.QDialogButtonBox(self)
        buttonbox.addButton(QtWidgets.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.close)
        layout.addWidget(buttonbox, 0, QtCore.Qt.AlignRight)

    def set_data_dir_display(self):
        """
        Convenience function to report the currently-selected dir
        """
        if self.config.starbound_data_dir:
            self.cur_data_dir.setText('<tt>{}</tt>'.format(self.config.starbound_data_dir))
        else:
            self.cur_data_dir.setText('<i>(no value)</i>')

    def choose_starbound_data_dir(self):
        """
        Launch a dialog to choose the Starbound install dir
        """
        chosen_dir = QtWidgets.QFileDialog.getExistingDirectory(self,
                'Choose Starbound Install Directory',
                os.path.join(os.path.realpath(__file__), '..')
                )
        if chosen_dir:
            # Test to make sure that the directory contains what we expect
            checks = [
                    os.path.join('assets', 'packed.pak'),
                    os.path.join('storage', 'player'),
                    os.path.join('storage', 'universe'),
                    ]
            for check in checks:
                full_path = os.path.join(chosen_dir, check)
                if not os.path.exists(full_path):
                    msg = QtWidgets.QMessageBox(self)
                    msg.setWindowTitle('Invalid Starbound Directory')
                    msg.setText('<b>Error:</b> the chosen directory does not appear to '
                            + '<br/>be a valid Starbound install directory')
                    msg.setIcon(QtWidgets.QMessageBox.Critical)
                    button = msg.addButton(QtWidgets.QMessageBox.Ok)
                    msg.setDefaultButton(button)
                    msg.exec()
                    return

            # If we got here, our dir should be valid.
            self.config.starbound_data_dir = chosen_dir
            self.set_data_dir_display()

    def close(self):
        """
        Process closing the window.  Note that if the user closes the dialog
        w/ Esc (as opposed to Enter or the OK button), this won't actually
        be called - `reject()` would be needed for that.
        """
        self.maingui.save_config()
        super().close()

class GoToDialog(QtWidgets.QDialog):
    """
    Dialog to prompt the user for coordinates to warp to.  I'm tempted to
    have this support switching between regions and full coords, but in the
    end that's probably too much work for not enough gain.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.maingui = parent
        self.config = parent.config

        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Go To Coordinates')
        self.setMinimumSize(200, 150)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # Title
        label = QtWidgets.QLabel('<b>Go To Coordinates</b>')
        layout.addWidget(label, 0, QtCore.Qt.AlignCenter)

        # Contents
        grid = QtWidgets.QGridLayout()
        self.world = self.maingui.world

        # Get our current center point
        (cur_x, cur_y) = self.maingui.scene.centered_tile()

        # X
        self.label_x = QtWidgets.QLabel('X:')
        grid.addWidget(self.label_x, 0, 0, QtCore.Qt.AlignRight)
        self.spin_x = QtWidgets.QSpinBox(self)
        self.spin_x.setMinimum(0)
        self.spin_x.setMaximum(self.world.metadata['worldTemplate']['size'][0])
        self.spin_x.setValue(cur_x)
        grid.addWidget(self.spin_x, 0, 1)

        # Y
        self.label_y = QtWidgets.QLabel('Y:')
        grid.addWidget(self.label_y, 1, 0, QtCore.Qt.AlignRight)
        self.spin_y = QtWidgets.QSpinBox(self)
        self.spin_y.setMinimum(0)
        self.spin_y.setMaximum(self.world.metadata['worldTemplate']['size'][1])
        self.spin_y.setValue(cur_y)
        grid.addWidget(self.spin_y, 1, 1)

        # Widget to hold the contents
        w = QtWidgets.QWidget()
        w.setLayout(grid)
        w.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        layout.addWidget(w, 0, QtCore.Qt.AlignCenter)

        # Spacer
        layout.addWidget(QtWidgets.QLabel(''), 1)

        # Buttons
        buttonbox = QtWidgets.QDialogButtonBox(self)
        buttonbox.addButton(QtWidgets.QDialogButtonBox.Ok)
        buttonbox.addButton(QtWidgets.QDialogButtonBox.Cancel)
        buttonbox.accepted.connect(self.warp)
        buttonbox.rejected.connect(self.close)
        layout.addWidget(buttonbox, 0, QtCore.Qt.AlignRight)

    def warp(self):
        """
        User hit OK, let's do this.
        """
        self.maingui.scene.center_on(self.spin_x.value(), self.spin_y.value())
        self.close()

class GUI(QtWidgets.QMainWindow):
    """
    Main application window
    """

    def __init__(self, app, config, filename):
        super().__init__()

        self.app = app
        self.config = config

        # Initialization stuff
        self.world = None
        self.worlddf = None
        self.data = None
        self.loaded_filename = None
        self.load_data_dialog = None
        self.navigation_actions = []
        self.initUI()

        # Show ourselves
        self.show()

        # If we have Starbound data, load it.
        if self.config.starbound_data_dir:
            self.load_data()
        else:
            self.enforce_menu_state()
            msg = QtWidgets.QMessageBox(self)
            msg.setWindowTitle('Starbound Install Dir Not Found')
            msg.setText('<html>Starbound install directory was not found. '
                    + 'Please choose the<br>directory manually in the following '
                    + 'dialog (also accessible<br>via the <tt>Edit -> Settings</tt> '
                    + 'menu.')
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            button = msg.addButton(QtWidgets.QMessageBox.Ok)
            msg.setDefaultButton(button)
            msg.exec()
            self.action_settings()

        # If we've been passed a filename, load it.  Otherwise, open the
        # loading dialog
        if self.data:
            if filename:
                self.load_map(filename)
            else:
                self.action_open_name()

    def initUI(self):

        # File Menu
        menubar = self.menuBar()
        filemenu = menubar.addMenu('&File')
        self.openname_menu = filemenu.addAction('&Open by Name', self.action_open_name, 'Ctrl+O')
        self.openfile_menu = filemenu.addAction('Open &File', self.action_open_file, 'Ctrl+Shift+O')
        filemenu.addSeparator()
        filemenu.addAction('&Quit', self.action_quit, 'Ctrl+Q')

        # Edit Menu
        editmenu = menubar.addMenu('&Edit')
        editmenu.addAction('&Settings', self.action_settings, 'Ctrl+S')

        # Nagivate Menu
        self.navmenu = menubar.addMenu('&Navigate')
        self.goto_menu = self.navmenu.addAction('&Go To...', self.action_goto, 'Ctrl+G')
        self.navmenu.addSeparator()
        self.to_spawn_menu = self.navmenu.addAction('Go to Spawn Point', self.action_to_spawn)

        # Enforce menu state
        self.enforce_menu_state()

        # Lefthand side vbox
        lh = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout()
        lh.setLayout(vbox)

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
        self.maparea = MapArea(self)
        self.scene = self.maparea.scene

        # Splitter to store our main widgets
        self.splitter = QtWidgets.QSplitter()
        self.splitter.addWidget(lh)
        self.splitter.addWidget(self.maparea)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        # Restore splitter settings, if we have any
        if self.config.splitter:
            self.splitter.restoreState(self.config.splitter)

        # Central Widget
        self.setCentralWidget(self.splitter)

        # Main window
        self.setMinimumSize(1050, 700)
        self.resize(self.config.app_w, self.config.app_h)
        self.set_title()

    def set_title(self):
        """
        Sets our window title, including our open filename if we happen
        to have a file open
        """
        if self.loaded_filename:
            self.setWindowTitle('Starbound Mapper | {}'.format(self.loaded_filename))
        else:
            self.setWindowTitle('Starbound Mapper')

    def save_config(self):
        """
        Saves our config.  This is wrapped so that whenever we save app
        config, we also save the window geometry.
        """
        self.config.app_w = self.width()
        self.config.app_h = self.height()
        self.config.splitter = self.splitter.saveState()
        self.config.save()

    def action_quit(self):
        """
        Handle our "Quit" action.
        """
        self.save_config()
        self.close()

    def action_open_file(self):
        """
        Opens by filename
        """

        # TODO: handle errors, etc.

        (filename, filefilter) = QtWidgets.QFileDialog.getOpenFileName(self,
                'Open Starbound World...',
                self.data.base_universe,
                'World Files (*.world *.tempworld *.shipworld);;All Files (*.*)')

        if filename and filename != '':
            self.load_map(filename)

        # Re-focus the main window
        self.activateWindow()

    def action_open_name(self):
        """
        Opens by character/system name
        """

        dialog = OpenByPlayerName(self)
        dialog.exec()
        if dialog.chosen_filename:
            self.load_map(dialog.chosen_filename, dialog.chosen_player)

        # Re-focus the main window
        self.activateWindow()

    def action_settings(self):
        """
        Open our settings dialog
        """

        cur_datadir = self.config.starbound_data_dir
        settings = SettingsDialog(self)
        settings.exec()
        new_datadir = self.config.starbound_data_dir
        if new_datadir:
            if cur_datadir != new_datadir:
                self.load_data()
                self.scene.refresh(self.data)
        else:
            self.close_world()

        # Make sure our menus are enabled/disabled as appropriate
        self.enforce_menu_state()

        # Re-focus the main window
        self.activateWindow()

    def action_goto(self):
        """
        Will open a dialog prompting the user for coordinates
        """
        dialog = GoToDialog(self)
        dialog.exec()

        # Re-focus the main window
        self.activateWindow()

    def action_to_spawn(self):
        """
        Center the map on the spawn point
        """
        self.scene.center_on_spawn()

    def action_to_coords(self, x, y):
        """
        Center the map on the specified point
        """
        self.scene.center_on(x, y)

    def enforce_menu_state(self):
        """
        Toggles various menu items to be enabled/disabled depending on the
        state of the app
        """
        if self.config.starbound_data_dir:
            self.openfile_menu.setEnabled(True)
            self.openname_menu.setEnabled(True)
            if self.world:
                self.goto_menu.setEnabled(True)
                self.to_spawn_menu.setEnabled(True)
                self.to_spawn_menu.setText('Go to Spawn Point ({:d}, {:d})'.format(
                    *map(int, self.world.metadata['playerStart'])))
            else:
                self.goto_menu.setEnabled(False)
                self.to_spawn_menu.setEnabled(False)
                self.to_spawn_menu.setText('Go to Spawn Point')
        else:
            self.openfile_menu.setEnabled(False)
            self.openname_menu.setEnabled(False)
            self.goto_menu.setEnabled(False)
            self.to_spawn_menu.setEnabled(False)
            self.to_spawn_menu.setText('Go to Spawn Point')

    def load_data(self):
        """
        Loads our data
        """
        if self.config.starbound_data_dir:
            # Set up a progress dialog so the user knows something is happening
            self.load_data_dialog = QtWidgets.QProgressDialog(self)
            self.load_data_dialog.setWindowTitle('Loading Graphics Resources...')
            label = QtWidgets.QLabel('<b>Loading Graphics Resources...</b>')
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.load_data_dialog.setLabel(label)
            self.load_data_dialog.setRange(0, 0)
            self.load_data_dialog.setModal(True)
            self.load_data_dialog.setMinimumSize(300, 100)
            self.load_data_dialog.show()
            self.app.processEvents()

            # Actually load the data
            self.data = StarboundData(
                    self.config,
                    progress_callback=self.load_data_progress_callback,
                    )
            self.scene.data = self.data

            # Close our progress dialog
            self.load_data_dialog.close()
            self.load_data_dialog = None

            # Re-focus the main window
            self.activateWindow()
        else:
            self.data = None

    def load_data_progress_callback(self):
        """
        Used by StarboundData to update our progress bar
        """
        if self.load_data_dialog:
            self.load_data_dialog.setValue(0)
            self.app.processEvents()

    def close_world(self):
        """
        Closes the open world, if we have one
        """
        if self.world:
            self.world = None
            self.scene.clear()
        if self.worlddf:
            self.worlddf.close()
            self.worlddf = None
        for action in self.navigation_actions:
            self.navmenu.removeAction(action)
        self.navigation_actions = []

    def add_navigation_item(self, uuid, text):
        """
        Adds an item to our navigation menut, based on the given `uuid` (or just
        ID, in some cases), and with the label `text`.  Returns the action, if
        created, or None.
        """
        coords = self.world.get_uuid_coords(uuid)
        if coords:
            self.navigation_actions.append(
                    self.navmenu.addAction(
                        '{} ({}, {})'.format(text, coords[0], coords[1]),
                        lambda: self.action_to_coords(coords[0], coords[1]),
                        ))
            return self.navigation_actions[-1]
        return None

    def load_map(self, filename, player=None):
        """
        Loads the map from `filename`, optionally having been loaded via
        player `player`.  (This is to support loading player bookmarks
        into our Navigation menu, since those are stored in the player
        files.)
        """

        # Close out any old map we have
        self.close_world()

        # Now load the new one
        # TODO: check for exceptions, etc.
        (self.world, self.worlddf) = StarboundData.open_world(filename)

        if self.world:
            base_filename = os.path.basename(filename)
            self.loaded_filename = filename
            self.set_title()
            self.data_table.set_world_filename(base_filename)
            self.data_table.set_world_size(
                    self.world.metadata['worldTemplate']['size'][0],
                    self.world.metadata['worldTemplate']['size'][1],
                    )
            # We're duplicating some work from Player.get_worlds() here, but
            # consolidating everything would be tricky, and in the end I
            # figured it wouldn't be worth it.
            match = re.match(r'(.*)-([0-9a-f]{32})-(\d+).(temp)?world', base_filename)
            if match:
                self.data_table.set_world_name(match.group(1))
                self.data_table.set_world_type('Non-Planet System Object')
                self.data_table.set_world_extra('')
            elif filename.endswith('.shipworld'):
                self.data_table.set_world_name('Starship')
                self.data_table.set_world_type('Your Starship')
                self.data_table.set_world_extra('')
            elif ('worldTemplate' in self.world.metadata
                    and 'celestialParameters' in self.world.metadata['worldTemplate']):
                cp = self.world.metadata['worldTemplate']['celestialParameters']
                self.data_table.set_world_name(StarboundData.strip_colors(cp['name']))
                self.data_table.set_world_type(cp['parameters']['description'])
                if 'terrestrialType' in cp['parameters']:
                    self.data_table.set_world_extra(', '.join(cp['parameters']['terrestrialType']))
                else:
                    self.data_table.set_world_extra('')
            else:
                self.data_table.set_world_name(base_filename)
                self.data_table.set_world_type('Unknown')
                self.data_table.set_world_extra('')
            self.scene.load_map(self.world)

            # Jump to a Mech Beacon, if we have it
            if 'mechbeacon' in self.world.uuid_to_region_map:
                self.add_navigation_item('mechbeacon', 'Go to Mech Beacon')

            # Update our player-dependent navigation menu actions
            if player:

                # Current Player Location
                if player.cur_world_filename and player.cur_world_filename == base_filename:
                    self.navigation_actions.append(
                            self.navmenu.addAction(
                                'Go to Player Location ({:d}, {:d})'.format(*map(int, player.cur_world_loc)),
                                lambda: self.action_to_coords(*player.cur_world_loc),
                                ))

                # Player Bookmarks
                if base_filename in player.bookmarks:
                    marks = player.bookmarks[base_filename]
                    for mark in sorted(marks):
                        self.add_navigation_item(mark.uuid, 'Go to Bookmark: {}'.format(mark.name))
        else:
            # TODO: Handle this better, too.
            raise Exception('World not found')

        # Update menu state, potentially
        self.enforce_menu_state()

class Application(QtWidgets.QApplication):
    """
    Main application
    """

    def __init__(self, filename=None):
        super().__init__([])

        self.app = GUI(self, Config(), filename)

