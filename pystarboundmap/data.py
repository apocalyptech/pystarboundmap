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
import re
import json
from PIL import Image
from PyQt5 import QtWidgets, QtGui, QtCore

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
