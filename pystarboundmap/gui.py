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
        z_objects,
        z_foreground,
        z_foreground_mod,
        z_liquids,
        z_overlay,
        ) = range(9)

class HTMLStyle(QtWidgets.QProxyStyle):
    """
    A QProxyStyle which can be used to render HTML/Rich text inside
    QComboBoxes, QCheckBoxes and QRadioButtons.  Note that for QComboBox,
    this does NOT alter rendering of the items when you're choosing from
    the list.  For that you'll need to set an item delegate.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_doc = QtGui.QTextDocument()

    def drawItemText(self, painter, rect, alignment, pal, enabled, text, text_role):
        """
        This is what draws the text - we use an internal QTextDocument
        to do the formatting.  The general form of this function follows the
        C++ version at https://github.com/qt/qtbase/blob/5.9/src/widgets/styles/qstyle.cpp

        Note that we completely ignore the `alignment` and `enabled` variable.
        This is always left-aligned, and does not currently support disabled
        widgets.
        """
        if not text or text == '':
            return

        # Save our current pen if we need to
        saved_pen = None
        if text_role != QtGui.QPalette.NoRole:
            saved_pen = painter.pen()
            painter.setPen(QtGui.QPen(pal.brush(text_role), saved_pen.widthF()))

        # Render the text.  There's a bit of voodoo here with the rectangles
        # and painter translation; there was various bits of finagling necessary
        # to get this to seem to work with both combo boxes and checkboxes.
        # There's probably better ways to be doing this.
        margin = 3
        painter.save()
        painter.translate(rect.left()-margin, 0)
        self.text_doc.setHtml(text)
        self.text_doc.setTextWidth(rect.width())
        self.text_doc.drawContents(painter,
                QtCore.QRectF(rect.adjusted(-rect.left(), 0, -margin, 0)))
        painter.restore()

        # Restore our previous pen if we need to
        if text_role != QtGui.QPalette.NoRole:
            painter.setPen(saved_pen)

    def sizeFromContents(self, contents_type, option, size, widget=None):
        """
        For ComboBoxes, this gets called to determine the size of the list of
        options for the comboboxes.  This is too wide for our HTMLComboBox, so
        we pull in the width from there instead.
        """
        width = size.width()
        height = size.height()
        if contents_type == self.CT_ComboBox and widget and type(widget) == HTMLComboBox:
            size = widget.sizeHint()
            width = size.width() + widget.width_adjust_contents
        return super().sizeFromContents(contents_type,
                option,
                QtCore.QSize(width, height),
                widget)

class HTMLWidgetHelper(object):
    """
    Class to enable HTML/Rich text on a "simple" Qt widget such as QCheckBox
    or QRadioButton.  The most important bit is setting the widget style to
    HTMLStyle.  The rest is all just making sure that the widget is sized
    properly; without it, the widget will be too wide.  If you don't care
    about that, you can easily just use .setStyle(HTMLStyle()) on a regular
    widget without bothering with subclassing.

    There's doubtless some corner cases we're missing here, but it works
    for my purposes.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(HTMLStyle())
        self.stored_size = None

    def setText(self, text):
        """
        Sets text, and clears out our sizeHint so that it can update.
        """
        self.stored_size = None
        super().setText(text)

    def sizeHint(self):
        """
        Use a QTextDocument to compute our rendered text size
        """
        if not self.stored_size:
            doc = QtGui.QTextDocument()
            doc.setHtml(self.text())
            size = doc.size()
            # Details from this derived from QCheckBox/QRadioButton sizeHint sourcecode:
            # https://github.com/qt/qtbase/blob/5.9/src/widgets/widgets/qcheckbox.cpp
            # https://github.com/qt/qtbase/blob/5.9/src/widgets/widgets/qradiobutton.cpp
            opt = QtWidgets.QStyleOptionButton()
            self.initStyleOption(opt)
            self.stored_size = QtCore.QSize(
                    size.width() + opt.iconSize.width() + 4,
                    max(size.height(), opt.iconSize.height()))
        return self.stored_size

    def minimumSizeHint(self):
        """
        Just use the same logic as `sizeHint`
        """
        return self.sizeHint()

class HTMLQPushButton(HTMLWidgetHelper, QtWidgets.QPushButton):
    """
    An HTML-enabled QPushButton.  All the actual work is done in HTMLWidgetHelper.
    We're abusing (well, using) Python's multiple inheritance since the same code
    works well for more than one widget type.
    """

class GUITile(QtWidgets.QGraphicsRectItem):
    """
    Hoverable area which the user can click on for info, etc.
    """

    (BRUSH_NONE,
        BRUSH_NORMAL,
        BRUSH_PLANT,
        BRUSH_OBJECT,
        BRUSH_HOVER) = range(5)

    def __init__(self, parent, tile, x, y, region, gui_x, gui_y, layer_toggles):
        super().__init__()
        self.hovered = False
        self.highlight_objects = layer_toggles.object_anchors_toggle.isChecked()
        self.highlight_plants = layer_toggles.plant_anchors_toggle.isChecked()
        self.plants = []
        self.objects = []
        self.parent = parent
        self.tile = tile
        self.x = x
        self.y = y
        self.region = region
        self.gui_x = gui_x
        self.gui_y = gui_y
        self.setAcceptHoverEvents(True)
        self.last_brush = GUITile.BRUSH_NONE
        self.set_default_brush()
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
        if tile.background_material in materials:
            if layer_toggles.back_mid_toggle.isChecked():
                image = materials[tile.background_material].midimage
            else:
                image = materials[tile.background_material].bgimage
            self.material_background = QtWidgets.QGraphicsPixmapItem(image)
            self.material_background.setPos(gui_x, gui_y)
            self.material_background.setZValue(Constants.z_background)
            if not layer_toggles.back_toggle.isChecked():
                self.material_background.setVisible(False)
            self.parent.addItem(self.material_background)

        # Matmods (background)
        self.mod_background = None
        if tile.background_mod in matmods:
            if layer_toggles.back_mid_toggle.isChecked():
                image = matmods[tile.background_mod].midimage
            else:
                image = matmods[tile.background_mod].bgimage
            self.mod_background = QtWidgets.QGraphicsPixmapItem(image)
            self.mod_background.setPos(gui_x-4, gui_y-4)
            self.mod_background.setZValue(Constants.z_background_mod)
            if not layer_toggles.back_mod_toggle.isChecked():
                self.mod_background.setVisible(False)
            self.parent.addItem(self.mod_background)

        # Materials (foreground)
        self.material_foreground = None
        if tile.foreground_material in materials:
            self.material_foreground = QtWidgets.QGraphicsPixmapItem(materials[tile.foreground_material].image)
            self.material_foreground.setPos(gui_x, gui_y)
            self.material_foreground.setZValue(Constants.z_foreground)
            if not layer_toggles.fore_toggle.isChecked():
                self.material_foreground.setVisible(False)
            self.parent.addItem(self.material_foreground)

        # Matmods (foreground)
        self.mod_foreground = None
        if tile.foreground_mod in matmods:
            self.mod_foreground = QtWidgets.QGraphicsPixmapItem(matmods[tile.foreground_mod].image)
            self.mod_foreground.setPos(gui_x-4, gui_y-4)
            self.mod_foreground.setZValue(Constants.z_foreground_mod)
            if not layer_toggles.fore_mod_toggle.isChecked():
                self.mod_foreground.setVisible(False)
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
            if not layer_toggles.liquids_toggle.isChecked():
                self.liquid.setVisible(False)
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

    def add_plant(self, desc, obj_list):
        """
        Adds an attached plant by its description name, and its associated Plant
        objects
        """
        self.plants.append((desc, obj_list))
        if len(self.plants) == 1:
            self.set_default_brush()

    def add_object(self, obj_data, obj_name, obj_orientation, qpmi, entity):
        """
        Adds an attached object, with its object data, name, orientation,
        and QGraphicsPixmapItem
        """
        self.objects.append((obj_data, obj_name, obj_orientation, qpmi, entity))
        if len(self.objects) == 1:
            self.set_default_brush()

    def hoverEnterEvent(self, event=None):
        data_table = self.parent.mainwindow.data_table
        materials = self.parent.data.materials
        matmods = self.parent.data.matmods
        liquids = self.parent.data.liquids
        self.parent.cur_hover = self
        self.hovered = True

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

        # Gather a list of entities to report on
        entities = []

        # Objects!
        for (obj_data, obj_name, obj_orientation, qpmi, _) in self.objects:
            entities.append(obj_name)
            qpmi.setPixmap(obj_data.get_hi_image(obj_orientation))

        # Plants!
        for (desc, part_list) in self.plants:
            entities.append(desc)
            for (plant_obj, qpmi) in part_list:
                qpmi.setPixmap(plant_obj.hi_image)

        # Update the datatable with our entity info
        data_table.set_entities(entities)

        # TODO: Might want to pre-brighten our images and swap 'em out.  Or
        # at least do so for objects, so we could highlight the whole thing.
        self.last_brush = GUITile.BRUSH_HOVER
        self.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 128)))
        self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))

    def hoverLeaveEvent(self, event=None):
        self.hovered = False
        self.set_default_brush()

        # Restore object images
        for (obj_data, obj_name, obj_orientation, qpmi, _) in self.objects:
            qpmi.setPixmap(obj_data.get_image(obj_orientation)[0])

        # Restore plant images
        for (desc, part_list) in self.plants:
            for (plant_obj, qpmi) in part_list:
                qpmi.setPixmap(plant_obj.image)

    def toggle_foreground(self, checked):
        if self.material_foreground:
            self.material_foreground.setVisible(checked)

    def toggle_fore_mod(self, checked):
        if self.mod_foreground:
            self.mod_foreground.setVisible(checked)

    def toggle_background(self, checked):
        if self.material_background:
            self.material_background.setVisible(checked)

    def toggle_back_mod(self, checked):
        if self.mod_background:
            self.mod_background.setVisible(checked)

    def toggle_back_mid(self, checked):
        """
        Toggles whether we're using mid-brightness background images
        """
        if self.material_background:
            if checked:
                image = self.parent.data.materials[self.tile.background_material].midimage
            else:
                image = self.parent.data.materials[self.tile.background_material].bgimage
            self.material_background.setPixmap(image)
        if self.mod_background:
            if checked:
                image = self.parent.data.matmods[self.tile.background_mod].midimage
            else:
                image = self.parent.data.matmods[self.tile.background_mod].bgimage
            self.mod_background.setPixmap(image)

    def set_default_brush(self):
        """
        Sets our default (non-hovered) brush/pen state.  Changing this is
        expensive, which is why we're keeping track of the brush state with
        `last_brush` rather than blindly updating.
        """
        if not self.hovered:
            if self.highlight_objects and len(self.objects) > 0:
                if self.last_brush != GUITile.BRUSH_OBJECT:
                    self.setBrush(QtGui.QBrush(QtGui.QColor(150, 150, 255, 200)))
                    self.setPen(QtGui.QPen(QtGui.QColor(190, 190, 255, 255)))
                    self.last_brush = GUITile.BRUSH_OBJECT
            elif self.highlight_plants and len(self.plants) > 0:
                if self.last_brush != GUITile.BRUSH_PLANT:
                    self.setBrush(QtGui.QBrush(QtGui.QColor(150, 255, 150, 200)))
                    self.setPen(QtGui.QPen(QtGui.QColor(190, 255, 190, 255)))
                    self.last_brush = GUITile.BRUSH_PLANT
            else:
                if self.last_brush != GUITile.BRUSH_NORMAL:
                    self.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 0)))
                    self.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
                    self.last_brush = GUITile.BRUSH_NORMAL

    def toggle_liquids(self, checked):
        if self.liquid:
            self.liquid.setVisible(checked)

    def toggle_object_anchors(self, checked):
        self.highlight_objects = checked
        self.set_default_brush()

    def toggle_plant_anchors(self, checked):
        self.highlight_plants = checked
        self.set_default_brush()

class GUIRegion(object):
    """
    Class to hold info about a single region
    """

    def __init__(self, scene, rx, ry, data, world):
        self.scene = scene
        self.layer_toggles = scene.mainwindow.layer_toggles
        self.rx = rx
        self.ry = ry
        self.data = data
        self.world = world
        self.region_back = None
        self.objects = []
        self.plants = []
        self.tiles = []
        self.loaded = False

    def load(self):
        """
        Loads ourself into memory
        """

        if self.loaded:
            return

        self.region_back = None
        self.objects = []
        self.plants = []
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
        self.region_back = self.scene.addRect(gui_x, gui_y-255, 255, 255,
                QtGui.QPen(QtGui.QColor(0, 0, 0)),
                QtGui.QBrush(QtGui.QColor(0, 0, 0)),
                )
        self.region_back.setZValue(Constants.z_black)

        # Tiles!
        cur_row = 0
        cur_col = 0
        for data_tile in data_tiles:
            self.tiles.append(GUITile(self.scene, data_tile,
                base_x+cur_col, base_y+cur_row,
                self,
                gui_x+cur_col*8, gui_y-(cur_row+1)*8,
                self.layer_toggles))
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
                    if not self.layer_toggles.objects_toggle.isChecked():
                        qpmi.setVisible(False)
                    self.scene.addItem(qpmi)
                    self.objects.append(qpmi)
                    rel_x = obj_x - base_x
                    rel_y = obj_y - base_y
                    tile_idx = rel_y*32 + rel_x
                    self.tiles[tile_idx].add_object(obj, obj_name, obj_orientation, qpmi, e.data)
            elif e.name == 'PlantEntity':
                desc = e.data['descriptions']['description']
                images = []
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
                        if not self.layer_toggles.plants_toggle.isChecked():
                            qpmi.setVisible(False)
                        images.append((plants[piece_img], qpmi))
                        self.scene.addItem(qpmi)
                        self.plants.append(qpmi)
                    else:
                        print('not found: {}'.format(piece_img))
                rel_x = obj_x - base_x
                rel_y = obj_y - base_y
                tile_idx = rel_y*32 + rel_x
                self.tiles[tile_idx].add_plant(desc, images)
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
        for obj in self.objects:
            self.scene.removeItem(obj)
        for plant in self.plants:
            self.scene.removeItem(plant)
        for tile in self.tiles:
            tile.unload()
            self.scene.removeItem(tile)
        if self.region_back:
            self.scene.removeItem(self.region_back)
        self.tiles = []
        self.objects = []
        self.plants = []
        self.region_back = None
        self.loaded = False

    def toggle_foreground(self, checked):
        """
        Toggle the foreground
        """
        for tile in self.tiles:
            tile.toggle_foreground(checked)

    def toggle_fore_mod(self, checked):
        """
        Toggle the foreground mod
        """
        for tile in self.tiles:
            tile.toggle_fore_mod(checked)

    def toggle_background(self, checked):
        """
        Toggle the background
        """
        for tile in self.tiles:
            tile.toggle_background(checked)

    def toggle_back_mod(self, checked):
        """
        Toggle the background mod
        """
        for tile in self.tiles:
            tile.toggle_back_mod(checked)

    def toggle_back_mid(self, checked):
        """
        Toggle midrange background highlighting
        """
        for tile in self.tiles:
            tile.toggle_back_mid(checked)

    def toggle_liquids(self, checked):
        """
        Toggle liquids
        """
        for tile in self.tiles:
            tile.toggle_liquids(checked)

    def toggle_objects(self, checked):
        """
        Toggle objects
        """
        for obj in self.objects:
            obj.setVisible(checked)

    def toggle_object_anchors(self, checked):
        """
        Toggle object anchors
        """
        for tile in self.tiles:
            tile.toggle_object_anchors(checked)

    def toggle_plants(self, checked):
        """
        Toggle plants
        """
        for plant in self.plants:
            plant.setVisible(checked)

    def toggle_plant_anchors(self, checked):
        """
        Toggle plant anchors
        """
        for tile in self.tiles:
            tile.toggle_plant_anchors(checked)

class InfoDialog(QtWidgets.QDialog):
    """
    Generic class for an info-display dialog
    """

    def __init__(self, parent, min_w, min_h, cur_w, cur_h, title):
        super().__init__(parent)

        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setMinimumSize(min_w, min_h)
        self.resize(cur_w, cur_h)
        self.setWindowTitle(title)

        # Layout info
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # Title
        title_label = QtWidgets.QLabel(title, self)
        title_label.setStyleSheet('font-weight: bold; font-size: 12pt;')
        layout.addWidget(title_label, 0, QtCore.Qt.AlignCenter)

        # Scrolled Area
        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)

        # Scroll Contents
        contents = QtWidgets.QWidget(self)
        self.grid = QtWidgets.QGridLayout()
        contents.setLayout(self.grid)
        self.cur_row = 0

        # Populate contents
        self.populate_contents()

        # Spacer at the end of the grid
        self.grid.addWidget(QtWidgets.QLabel(''), self.cur_row, 0)
        self.grid.setRowStretch(self.cur_row, 1)

        # Make the second column stretch, not the first
        self.grid.setColumnStretch(1, 1)

        # Add our contents to the scroll widget
        layout.addWidget(self.scroll, 1)
        self.scroll.setWidget(contents)

        # Buttons
        buttonbox = QtWidgets.QDialogButtonBox(self)
        buttonbox.addButton(QtWidgets.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.close)
        layout.addWidget(buttonbox, 0, QtCore.Qt.AlignRight)

    def populate_contents(self):
        """
        Contents of the info dialog
        """
        raise Exception('Implement me!')

    def add_heading_row(self, heading):
        """
        Adds a heading row
        """
        # A bit of space if we're not the very first row
        if self.cur_row != 0:
            self.grid.addWidget(QtWidgets.QLabel(''), self.cur_row, 0, 1, 2)
            self.cur_row += 1

        # Now the actual header
        label = QtWidgets.QLabel('<b>{}</b>'.format(heading))
        self.grid.addWidget(label, self.cur_row, 0, 1, 2, QtCore.Qt.AlignCenter)
        self.cur_row += 1
        return label

    def add_label(self, label_text):
        """
        Adds a label
        """
        label = QtWidgets.QLabel('<b>{}</b>:'.format(label_text))
        self.grid.addWidget(label, self.cur_row, 0, QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
        return label

    def add_text_data(self, text):
        """
        Adds the specified text as data
        """
        data = QtWidgets.QLabel(text)
        data.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.grid.addWidget(data, self.cur_row, 1, QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        return data

    def add_text_row(self, label, text):
        """
        Adds a text row
        """
        label_widget = self.add_label(label)
        data_widget = self.add_text_data(text)
        self.cur_row += 1
        return data_widget

    def add_lookup_text_row(self, label, value, lookup, extra='', nothing=-1):
        """
        Adds a row whose label is looked up from a dict
        """
        if value in lookup:
            text = '<tt>{}</tt>{} (ID {})'.format(lookup[value].name, extra, value)
        else:
            if value > nothing:
                text = 'Unknown{} (ID {})'.format(extra, value)
            else:
                text = '-'
        self.add_text_row(label, text)

    def add_list_data_row(self, label, data):
        """
        Adds a row with list data
        """
        label_widget = self.add_label(label)
        data_widget = self.add_list_data(data)
        self.cur_row += 1
        return data_widget

    def add_list_data(self, data):
        """
        Adds a list of data
        """

        # TODO: I'd like to use, say, a QListWidget or something, but controlling the widget
        # height on those was annoying, and I wanted the items to be easily copy+pasteable.
        # In the end I'm just going with a multiline QLabel inside a QScrollArea

        if len(data) == 0:
            return None

        scroll = QtWidgets.QScrollArea(self)
        scroll.setFrameShadow(QtWidgets.QFrame.Sunken)
        scroll.setFrameShape(QtWidgets.QFrame.Panel)
        w = QtWidgets.QLabel('<tt>{}</tt>'.format('<br/>'.join(data)), self)
        w.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        scroll.setWidget(w)
        self.grid.addWidget(scroll, self.cur_row, 1)
        return w

class TileInfoDialog(InfoDialog):
    """
    Popup dialog for detailed tile info
    """

    def __init__(self, parent, guitile, config):
        self.config = config
        self.guitile = guitile
        super().__init__(parent,
                Config.tileinfo_w, Config.tileinfo_h,
                config.tileinfo_w, config.tileinfo_h,
                'Tile Information for ({:d}, {:d})'.format(guitile.x, guitile.y),
                )

    def populate_contents(self):
        """
        Populate the contents of the dialog
        """

        guitile = self.guitile
        tile = guitile.tile
        scene = guitile.parent
        world = scene.world
        data = scene.data
        data_table = scene.mainwindow.data_table

        # Actually populate the grid.  TODO: Taking some of this info directly
        # from the DataTable, which is a bit unseemly.  Should push that
        # stuff into a proper data class.

        self.add_text_row('Region', '({:d}, {:d})'.format(guitile.region.rx, guitile.region.ry))
        self.add_text_row('Coordinates', '({:d}, {:d})'.format(guitile.x, guitile.y))
        self.add_lookup_text_row('Foreground Material', tile.foreground_material, data.materials)
        self.add_lookup_text_row('Foreground Material Mod', tile.foreground_mod, data.matmods)
        self.add_lookup_text_row('Background Material', tile.background_material, data.materials)
        self.add_lookup_text_row('Background Material Mod', tile.background_mod, data.matmods)

        # Liquids
        if tile.liquid_level > 0:
            extra_liquid = ' at {:d}%'.format(round(tile.liquid_level*100))
        else:
            extra_liquid = ''
        self.add_lookup_text_row('Liquid', tile.liquid, data.liquids,
                extra=extra_liquid, nothing=0)

        # Plants
        if len(guitile.plants) > 1:
            show_index = ' {}'.format(idx+1)
        else:
            show_index = ''
        for idx, (plant_desc, parts) in enumerate(guitile.plants):
            partlist = set()
            for (part, _) in parts:
                partlist.add(part.pathname)
            if len(parts) == 1:
                plural = ''
            else:
                plural = 's'
            self.add_text_row(
                    'Plant{}'.format(show_index),
                    '{} ({} part{})'.format(plant_desc, len(parts), plural),
                    )
            if len(partlist) > 0:
                self.add_list_data(sorted(partlist))
                self.cur_row += 1

        # Objects
        if len(guitile.objects) > 1:
            show_index = ' {}'.format(idx+1)
        else:
            show_index = ''
        for idx, (obj_data, obj_name, obj_orientation, _, entity) in enumerate(guitile.objects):
            object_label = 'Object{}'.format(show_index)
            self.add_text_row(
                    object_label,
                    '<tt>{}</tt> ({})'.format(obj_name, StarboundData.strip_colors(obj_data.info['shortdescription'])),
                    )
            self.add_text_data('<tt>{}</tt>'.format(obj_data.full_path))
            self.cur_row += 1
            orient = obj_data.get_image_path(obj_orientation)
            if orient:
                self.add_text_data('<tt>{}</tt>'.format(orient))
                self.cur_row += 1
            if 'items' in entity:
                itemlist = []
                for item in entity['items']:
                    if item and 'content' in item:
                        content = item['content']
                        if 'parameters' in content and 'shortdescription' in content['parameters']:
                            if content['name'] in data.items:
                                suffix = ' ({}: {})'.format(data.items[content['name']], content['parameters']['shortdescription'])
                            else:
                                suffix = ' ({})'.format(content['parameters']['shortdescription'])
                        elif content['name'] in data.items:
                            suffix = ' ({})'.format(data.items[content['name']])
                        else:
                            suffix = ''
                        itemlist.append((
                            content['name'],
                            content['count'],
                            '{}x {}{}'.format(content['count'], content['name'], suffix),
                            ))
                if len(itemlist) > 0:
                    self.add_list_data_row(
                            '{} Contents'.format(object_label),
                            [i[2] for i in sorted(itemlist)],
                            )

    def close(self):
        """
        Handles a close event - used mostly just to save our geometry
        """

        self.config.tileinfo_w = self.width()
        self.config.tileinfo_h = self.height()
        super().close()

class WorldInfoDialog(InfoDialog):
    """
    Popup dialog for detailed world info
    """

    def __init__(self, parent, world, config):
        self.world = world
        self.config = config
        self.data_table = parent.data_table
        super().__init__(parent,
                Config.worldinfo_w, Config.worldinfo_h,
                config.worldinfo_w, config.worldinfo_h,
                'World Information for {}'.format(self.data_table.world_name_label.text()),
                )

    def populate_contents(self):
        """
        Populate the contents of the dialog
        """

        data_table = self.data_table
        world = self.world

        self.add_text_row('World Name', data_table.world_name_label.text())
        self.add_text_row('World Type', data_table.world_type_label.text())
        if data_table.world_extra_label.text() != '':
            self.add_text_row('Extra Info', data_table.world_extra_label.text())
        self.add_text_row('Filename', world.base_filename)
        self.add_text_row('Size', '{}x{}'.format(*world.metadata['worldTemplate']['size']))

        if len(world.dungeons) > 0:
            dungeons = self.add_text_row('Dungeons', '<br/>'.join(sorted(world.dungeons)))
        else:
            self.add_text_row('Dungeons', '-')

        if len(world.biomes) > 0:
            biomes = self.add_text_row('Biomes', '<br/>'.join(sorted(world.biomes)))
        else:
            self.add_text_row('Biomes', '-')

    def close(self):
        """
        Handles a close event - used mostly just to save our geometry
        """

        self.config.worldinfo_w = self.width()
        self.config.worldinfo_h = self.height()
        super().close()

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
        self.cur_hover = None

        # This is used so that our first couple of GUI-setup steps doesn't
        # trigger a map-loading event (until we're actually ready for it)
        self.given_center = False

    def mousePressEvent(self, event):
        """
        Handle a mouse press event (just dragging for now)
        """
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
        else:
            if self.cur_hover:
                dialog = TileInfoDialog(self.parent, self.cur_hover, self.mainwindow.config)
                dialog.exec()

                # Re-focus the main window
                self.mainwindow.activateWindow()

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
        self.cur_hover = None

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
        # Okay, seems we don't actually need this here, for what we're using
        # it for, at least.  May want to rename or refactor these a bit so
        # that these two functions are analagous, 'cause they technically do
        # slightly different things now.
        #(scene_x, scene_y) = self.mainwindow.get_zoom_transform().map(new_x, new_y)
        #return (scene_x, scene_y)
        return (new_x, new_y)

    def scene_to_ingame(self, x, y):
        """
        Converts scene coordinates (x, y) to in-game coordinates.
        """
        (scene_x, scene_y) = self.mainwindow.get_inverted_zoom_transform().map(x, y)
        new_x = scene_x//8
        # TODO: this y coord may be slightly off
        new_y = ((self.world.height*8) - scene_y)//8
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
        vert_height = self.vbar.pageStep()
        gui_start_y = self.vbar.value()
        (game_min_x, game_max_y) = self.scene_to_ingame(gui_start_x, gui_start_y)
        (game_max_x, game_min_y) = self.scene_to_ingame(
                gui_start_x + horiz_width,
                gui_start_y + vert_height,
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
        regions_to_unload = []
        for region in list(self.loaded_regions):
            if region not in valid_regions:
                regions_to_unload.append(region)

        region_loading.start(len(regions_to_unload), label='Unloading Regions')
        for idx, region in enumerate(regions_to_unload):
            #print('Unloading region {}'.format(region))
            self.regions[region].unload()
            self.loaded_regions.remove(region)
            region_loading.update(idx)

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

    def toggle_foreground(self, checked):
        """
        Toggle the foreground
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_foreground(checked)

    def toggle_fore_mod(self, checked):
        """
        Toggle the foreground
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_fore_mod(checked)

    def toggle_background(self, checked):
        """
        Toggle the background
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_background(checked)

    def toggle_back_mod(self, checked):
        """
        Toggle the background
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_back_mod(checked)

    def toggle_back_mid(self, checked):
        """
        Toggle midrange background highlighting
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_back_mid(checked)

    def toggle_liquids(self, checked):
        """
        Toggle liquids
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_liquids(checked)

    def toggle_objects(self, checked):
        """
        Toggle objects
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_objects(checked)

    def toggle_object_anchors(self, checked):
        """
        Toggle object anchors
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_object_anchors(checked)

    def toggle_plants(self, checked):
        """
        Toggle plants
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_plants(checked)

    def toggle_plant_anchors(self, checked):
        """
        Toggle plant anchors
        """
        for region in self.loaded_regions:
            self.regions[region].toggle_plant_anchors(checked)

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
        self.world_filename_label = self.add_row('Filename')
        self.world_size_label = self.add_row('Size')

        self.region_label = self.add_row('Region')
        self.tile_label = self.add_row('Coords')

        self.mat_label = self.add_row('Fore Mat')
        self.matmod_label = self.add_row('Fore Mod')
        self.back_mat_label = self.add_row('Back Mat')
        self.back_matmod_label = self.add_row('Back Mod')
        self.liquid_label = self.add_row('Liquid')
        self.entities_label = self.add_row('Entities')

    def add_row(self, label):
        label = QtWidgets.QLabel('{}:'.format(label))
        label.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        self.layout.addWidget(label,
                self.cur_row, 0,
                QtCore.Qt.AlignRight | QtCore.Qt.AlignTop,
                )
        data_label = QtWidgets.QLabel()
        data_label.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Minimum)
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

    def set_entities(self, entity_list):
        self.entities_label.setText('<br/>'.join(entity_list))

class LayerToggles(QtWidgets.QWidget):
    """
    Widget to display a bunch of toggles for which layers to draw
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.maingui = parent

        self.grid = QtWidgets.QGridLayout()
        self.setLayout(self.grid)

        label = QtWidgets.QLabel('<b>Show Layers:</b>')
        self.grid.addWidget(label, 0, 0)
        self.cur_row = 1

        self.fore_toggle = self.add_row('Foreground Material',
                self.toggle_foreground,
                )
        self.fore_mod_toggle = self.add_row('Foreground Mods',
                self.maingui.scene.toggle_fore_mod,
                indent=True,
                )
        self.back_toggle = self.add_row('Background Material',
                self.toggle_background,
                )
        self.back_mod_toggle = self.add_row('Background Mods',
                self.maingui.scene.toggle_back_mod,
                indent=True,
                )
        self.back_mid_toggle = self.add_row('Use Brighter BG Images',
                self.maingui.scene.toggle_back_mid,
                indent=True,
                default=False,
                )
        self.liquids_toggle = self.add_row('Liquids',
                self.maingui.scene.toggle_liquids,
                )
        self.objects_toggle = self.add_row('Objects',
                self.toggle_objects,
                )
        self.object_anchors_toggle = self.add_row('Highlight Anchors',
                self.maingui.scene.toggle_object_anchors,
                indent=True,
                default=False,
                )
        self.plants_toggle = self.add_row('Plants',
                self.toggle_plants,
                )
        self.plant_anchors_toggle = self.add_row('Highlight Anchors',
                self.maingui.scene.toggle_plant_anchors,
                indent=True,
                default=False,
                )

    def add_row(self, label_text, callback, indent=False, default=True):
        """
        Adds a row to toggle.
        """

        checkbox = QtWidgets.QCheckBox(label_text, self)
        checkbox.setChecked(default)
        checkbox.toggled.connect(callback)
        if indent:
            w = QtWidgets.QWidget()
            hbox = QtWidgets.QHBoxLayout()
            spacer = QtWidgets.QWidget()
            spacer.setFixedWidth(20)
            hbox.addWidget(spacer)
            hbox.addWidget(checkbox, 1, QtCore.Qt.AlignLeft)
            hbox.setContentsMargins(0, 0, 0, 0)
            w.setLayout(hbox)
            self.grid.addWidget(w, self.cur_row, 0)
        else:
            self.grid.addWidget(checkbox, self.cur_row, 0)
        self.cur_row += 1
        return checkbox

    def toggle_foreground(self, checked):
        """
        Toggles the foreground material
        """
        self.maingui.scene.toggle_foreground(checked)
        self.fore_mod_toggle.setEnabled(checked)
        if checked:
            self.fore_mod_toggle.setChecked(self.current_fore_mod_val)
        else:
            self.current_fore_mod_val = self.fore_mod_toggle.isChecked()
            self.fore_mod_toggle.setChecked(False)

    def toggle_background(self, checked):
        """
        Toggles the background material
        """
        self.maingui.scene.toggle_background(checked)
        self.back_mod_toggle.setEnabled(checked)
        if checked:
            self.back_mod_toggle.setChecked(self.current_back_mod_val)
        else:
            self.current_back_mod_val = self.back_mod_toggle.isChecked()
            self.back_mod_toggle.setChecked(False)

    def toggle_objects(self, checked):
        """
        Toggles objects
        """
        self.maingui.scene.toggle_objects(checked)
        self.object_anchors_toggle.setEnabled(checked)
        if checked:
            self.object_anchors_toggle.setChecked(self.current_object_anchors_val)
        else:
            self.current_object_anchors_val = self.object_anchors_toggle.isChecked()
            self.object_anchors_toggle.setChecked(False)

    def toggle_plants(self, checked):
        """
        Toggles plants
        """
        self.maingui.scene.toggle_plants(checked)
        self.plant_anchors_toggle.setEnabled(checked)
        if checked:
            self.plant_anchors_toggle.setChecked(self.current_plant_anchors_val)
        else:
            self.current_plant_anchors_val = self.plant_anchors_toggle.isChecked()
            self.plant_anchors_toggle.setChecked(False)

class RegionLoadingNotifier(QtWidgets.QWidget):
    """
    Widgets to show a progress bar (and some text) while loading regions
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)

        self.label = 'Loading Regions'
        self.text_label = QtWidgets.QLabel('', self)
        self.layout.addWidget(self.text_label, 0, 0)
        self.text_label.hide()

        self.bar = QtWidgets.QProgressBar(self)
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.layout.addWidget(self.bar, 1, 0)
        self.num_regions = 1
        self.bar.hide()

    def start(self, num_regions, label='Loading Regions'):
        """
        Starts us off
        """

        self.num_regions = num_regions
        self.label = label
        if num_regions > 0:
            self.bar.setRange(0, num_regions)
            self.bar.setValue(0)
            self.text_label.setText('{}: 0/{}'.format(self.label, num_regions))
            self.text_label.show()
            self.bar.show()

    def update(self, value):
        """
        Updates with a new value
        """
        self.bar.setValue(value)
        self.text_label.setText('{}: {}/{}'.format(self.label, value, self.num_regions))

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

    def __init__(self, parent, main_label, height=350, extra_widget=None):
        super().__init__(parent)
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setMinimumSize(400, height)
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

        # Extra widget, if we've been given one
        if extra_widget:
            layout.addWidget(extra_widget, 0, QtCore.Qt.AlignCenter)

        # Scrolled Area
        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(True)

        # Scroll Contents
        self.contents = QtWidgets.QWidget(self)
        self.grid = QtWidgets.QGridLayout()
        self.contents.setLayout(self.grid)

        # Populate contents
        self.buttons = self.generate_buttons()
        self.populate_buttons()

        # Spacer at the end of the grid (this won't ever get removed, even
        # during re-sorts)
        self.grid.addWidget(QtWidgets.QLabel(''), len(self.buttons), 0)
        self.grid.setRowStretch(len(self.buttons), 1)

        # Add our contents to the scroll widget
        layout.addWidget(self.scroll, 1)
        self.scroll.setWidget(self.contents)

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

    class PlanetNameButton(HTMLQPushButton):
        """
        Ridiculous little class, but it lets us know which button was clicked, easily.
        """

        # Since space is at a premium, here's some biomes to not bother showing.
        # We're additionally omitting anything that starts with 'underground',
        # though that's done with a `.startswith()` call.
        biome_blacklist = set([
                'asteroids',
                'atmosphere',
                'barrenasteroids',
                'magmarockcorelayer',
                'moon',
                'mooncorelayer',
                'moonunderground',
                'void',
                ])

        def __init__(self, parent, filename, mtime, cache):
            super().__init__(parent)
            self.parent = parent
            self.filename = filename
            self.mtime = mtime
            self.cache = cache
            self.set_world_text()
            self.clicked.connect(self.planet_clicked)

        def chunks(self, l, n):
            """
            Splits a list `l` into `n`-sided chunks, though the
            very *first* one will have one less.

            Adapated from https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
            """
            yield l[:n-1]
            for i in range(n-1, len(l), n):
                yield l[i:i+n]

        def set_world_text(self, show_details=False):
            """
            Sets the world text that should be visible
            """

            # Whether we have "extra" text to display
            if self.cache.extra_desc and self.cache.extra_desc != '':
                extra_display = '<br/>{}'.format(self.cache.extra_desc)
            else:
                extra_display = ''

            # Whether or not we're bookmarked
            if os.path.basename(self.filename) in self.parent.player.bookmarks:
                bookmark_extra = ' <i>(bookmarked)</i>'
            else:
                bookmark_extra = ''

            # These details can be toggled on/off by the user, since they're a bit
            # noisy.
            if show_details:

                # Biomes
                biomes_to_show = []
                for biome in self.cache.biomes:
                    if biome not in self.biome_blacklist and not biome.startswith('underground'):
                        biomes_to_show.append(biome)
                if len(biomes_to_show) > 0:
                    biome_text = ',<br/>'.join(
                            [', '.join(l) for l in self.chunks(sorted(biomes_to_show), 5)]
                            )
                else:
                    biome_text = '-'

                # Dungeons
                if len(self.cache.dungeons) > 0:
                    dungeon_text = ',<br/>'.join(
                            [', '.join(l) for l in self.chunks(sorted(self.cache.dungeons), 4)]
                            )
                else:
                    dungeon_text = '-'

                detail_text = '<br/>Biomes: {}<br/>Dungeons: {}'.format(biome_text, dungeon_text)

            else:

                detail_text = ''

            # Now actually set the text
            self.setText('<div align="center"><b>{}</b>{}{}{}<br/><i>{}</i></div>'.format(
                self.cache.world_name,
                bookmark_extra,
                extra_display,
                detail_text,
                self.parent.human_date(self.mtime),
                ))

        def planet_clicked(self):
            """
            Process a click action
            """
            self.parent.planet_clicked(self.filename)

    def __init__(self, parent, player):

        self.player = player
        self.parent_dialog = parent
        self.mainwindow = parent.mainwindow
        self.chosen_filename = None
        self.get_world_progress = None
        details_checkbox = QtWidgets.QCheckBox('Show biome/dungeon details')
        details_checkbox.setContentsMargins(0, 0, 0, 0)
        super().__init__(parent,
                'Open Starbound World for {}'.format(player.name),
                height=500,
                extra_widget=details_checkbox,
                )
        details_checkbox.clicked.connect(self.toggle_details)
        self.button_padding = None

    def generate_buttons(self):
        """
        This is where the buttons get generated
        """
        # Put up a progress dialog
        self.get_world_progress = QtWidgets.QProgressDialog(self.mainwindow)
        self.get_world_progress.setWindowTitle('Caching World Information for {}'.format(self.player.name))
        label = QtWidgets.QLabel('<b>Caching World Information for {}</b>'.format(self.player.name))
        label.setAlignment(QtCore.Qt.AlignCenter)
        self.get_world_progress.setLabel(label)
        self.get_world_progress.setRange(0, 0)
        self.get_world_progress.setModal(True)
        self.get_world_progress.setMinimumSize(300, 100)
        self.get_world_progress.show()
        # TODO: This is lame - handle cancel events properly instead.
        self.get_world_progress.setCancelButton(None)
        self.mainwindow.app.processEvents()

        # Actually do the loading
        buttons = []
        for (mtime, cache_entry, filename) in self.player.get_worlds(self.parent_dialog.mainwindow.data,
                progress_callback=self.update_get_world_progress):
            button = OpenByPlanetName.PlanetNameButton(self, filename, mtime, cache_entry)
            buttons.append((mtime, cache_entry.sort_name, button))

        # Clean up and exit
        self.get_world_progress.close()
        self.get_world_progress = None
        return buttons

    def update_get_world_progress(self):
        """
        Updates the progress bar we use while loading user world info.
        """
        if self.get_world_progress:
            self.get_world_progress.setValue(0)
            self.mainwindow.app.processEvents()

    def planet_clicked(self, filename):
        """
        A planet was chosen
        """
        self.parent().planet_clicked(filename)
        self.accept()

    def toggle_details(self, checked):
        """
        Toggle details on our buttons
        """
        if self.button_padding is None:
            cur_button_width = 0
            for (_, _, button) in self.buttons:
                cur_button_width = max(cur_button_width, button.sizeHint().width())
            if cur_button_width != 0:
                self.button_padding = self.width() - cur_button_width
        button_width = 0
        for (_, _, button) in self.buttons:
            button.set_world_text(checked)
            button_width = max(button_width, button.sizeHint().width())
        if checked:
            width = self.width()
            if button_width != 0:
                if self.button_padding is not None:
                    button_width += self.button_padding
                if width < button_width:
                    self.resize(button_width, self.height())

class OpenByPlayerName(OpenByDialog):
    """
    Dialog to open a world by player name, rather than by filename
    """

    class PlayerNameButton(HTMLQPushButton):
        """
        Ridiculous little class, but it lets us know which button was clicked, easily.
        """

        def __init__(self, parent, player, mtime):
            super().__init__(parent)
            self.parent = parent
            self.player = player
            self.setText('<div align="center"><b>{}</b><br/><i>{}</i></div>'.format(
                player.name,
                parent.human_date(mtime),
                ))
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
        self.filename_arg = filename

        # Initialization stuff
        self.world = None
        self.worlddf = None
        self.data = None
        self.loaded_filename = None
        self.navigation_actions = []
        self.zoom_levels = []
        # 0.5 scaling just doesn't perform well enough right now
        #for scale in [0.5, 1, 2, 3, 4]:
        for scale in [1, 2, 3, 4]:
            t = QtGui.QTransform()
            if scale != 1:
                t.scale(scale, scale)
            (inverted, _) = t.inverted()
            self.zoom_levels.append((scale, t, inverted))
        self.cur_zoom = 0
        self.initUI()

        # Show ourselves
        self.show()

        # Launch our initial dialogs.  If we don't have at least a *little*
        # bit of delay on this, the dialog won't be *properly* modal, and
        # won't necessarily center on the main window.  `msec` values as
        # low as 3 seem to work just fine on my system
        QtCore.QTimer.singleShot(5, self.initial_dialogs)

    def initial_dialogs(self):
        """
        Show our initial dialogs (or, if provided with a filename argument,
        load that file)
        """

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
            if self.filename_arg:
                self.load_map(self.filename_arg)
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

        # View Menu
        viewmenu = menubar.addMenu('&View')
        self.worldinfo_menu = viewmenu.addAction('&World Info', self.action_world_info, 'Ctrl+I')
        viewmenu.addSeparator()
        viewmenu.addAction('Zoom &In', self.action_zoom_in, '+')
        viewmenu.addAction('Zoom &Out', self.action_zoom_out, '-')

        # Nagivate Menu
        self.navmenu = menubar.addMenu('&Navigate')
        self.goto_menu = self.navmenu.addAction('&Go To...', self.action_goto, 'Ctrl+G')
        self.navmenu.addSeparator()
        self.to_spawn_menu = self.navmenu.addAction('Go to Spawn Point', self.action_to_spawn)

        # Enforce menu state
        self.enforce_menu_state()

        # Main Widget (setting this up before everything else so that the
        # scene object exists for callbacks)
        self.maparea = MapArea(self)
        self.scene = self.maparea.scene

        # Lefthand side vbox
        lh = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout()
        lh.setLayout(vbox)

        # table to store data display
        self.data_table = DataTable(self)
        vbox.addWidget(self.data_table, 0, QtCore.Qt.AlignLeft)

        # Spacer inbetween DataTable and zoom
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        vbox.addWidget(line)

        # Zoom Widget
        w = QtWidgets.QWidget()
        zoom_grid = QtWidgets.QGridLayout()
        zoom_grid.addWidget(QtWidgets.QLabel('<b>Zoom:</b>'), 0, 0, 2, 1)
        self.zoom_widget = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.zoom_widget.setMinimum(0)
        self.zoom_widget.setMaximum(len(self.zoom_levels)-1)
        self.zoom_widget.setValue(self.cur_zoom)
        # This actually looks a bit better without the ticks, since the
        # labels don't exactly line up
        #self.zoom_widget.setTickPosition(QtWidgets.QSlider.TicksBelow)
        #self.zoom_widget.setTickInterval(1)
        self.zoom_widget.setTracking(False)
        self.zoom_widget.valueChanged.connect(self.action_set_zoom)
        zoom_grid.addWidget(self.zoom_widget, 0, 1, 1, len(self.zoom_levels))
        for idx, (level, _, _) in enumerate(self.zoom_levels):
            label = QtWidgets.QLabel('{}x'.format(level), self)
            if idx == 0:
                align = QtCore.Qt.AlignLeft
            elif idx == len(self.zoom_levels) - 1:
                align = QtCore.Qt.AlignRight
            else:
                align = QtCore.Qt.AlignCenter
            zoom_grid.addWidget(label, 1, idx+1, align | QtCore.Qt.AlignTop)
        w.setLayout(zoom_grid)
        vbox.addWidget(w)

        # Spacer inbetween zoom and layer toggles
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        vbox.addWidget(line)

        # Layer Toggles
        self.layer_toggles = LayerToggles(self)
        vbox.addWidget(self.layer_toggles, 0, QtCore.Qt.AlignLeft)

        # Spacer on the lefthand panel
        spacer = QtWidgets.QWidget()
        vbox.addWidget(spacer, 1)

        # Region-loading display
        self.region_loading = RegionLoadingNotifier(self)
        vbox.addWidget(self.region_loading, 0)

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
        self.setMinimumSize(Config.app_w, Config.app_h)
        self.resize(self.config.app_w, self.config.app_h)
        self.set_title()

    def action_world_info(self):
        """
        Shows a dialog with basic world information on it
        """
        dialog = WorldInfoDialog(self, self.world, self.config)
        dialog.exec()

        # Re-focus the main window
        self.activateWindow()

    def action_set_zoom(self, value):
        """
        Sets our zoom value explicitly
        """
        if value >= 0 and value < len(self.zoom_levels) and value != self.cur_zoom:
            self.cur_zoom = value
            self.apply_zoom()

    def action_zoom_out(self):
        """
        Zooms out by a step (if possible)
        """
        if self.cur_zoom > 0:
            self.cur_zoom -= 1
            self.zoom_widget.setValue(self.cur_zoom)
            self.apply_zoom()

    def action_zoom_in(self):
        """
        Zooms in by a step (if possible)
        """
        if self.cur_zoom < len(self.zoom_levels) - 1:
            self.cur_zoom += 1
            self.zoom_widget.setValue(self.cur_zoom)
            self.apply_zoom()

    def apply_zoom(self):
        """
        Applies our current zoom level
        """
        self.maparea.setTransform(self.zoom_levels[self.cur_zoom][1])
        self.scene.draw_visible_area()

    def get_zoom_transform(self):
        """
        Returns our current zoom transformation
        """
        return self.zoom_levels[self.cur_zoom][1]

    def get_inverted_zoom_transform(self):
        """
        Returns our current inverted zoom transformation
        """
        return self.zoom_levels[self.cur_zoom][2]

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
                self.worldinfo_menu.setEnabled(True)
                self.goto_menu.setEnabled(True)
                self.to_spawn_menu.setEnabled(True)
                self.to_spawn_menu.setText('Go to Spawn Point ({:d}, {:d})'.format(
                    *map(int, self.world.metadata['playerStart'])))
            else:
                self.worldinfo_menu.setEnabled(False)
                self.goto_menu.setEnabled(False)
                self.to_spawn_menu.setEnabled(False)
                self.to_spawn_menu.setText('Go to Spawn Point')
        else:
            self.openfile_menu.setEnabled(False)
            self.openname_menu.setEnabled(False)
            self.worldinfo_menu.setEnabled(False)
            self.goto_menu.setEnabled(False)
            self.to_spawn_menu.setEnabled(False)
            self.to_spawn_menu.setText('Go to Spawn Point')

    def load_data(self):
        """
        Loads our data
        """
        if self.config.starbound_data_dir:

            # If we have a current dataset, close it out
            if self.data:
                self.data.close()

            # Actually load the data
            self.data = StarboundData(self.config)
            self.scene.data = self.data

        else:
            self.data = None

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

