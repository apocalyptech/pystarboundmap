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
import json
import mmap
import struct
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
            if line.rstrip()[-2:] != '*/':
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

class Material(object):
    """
    Holds info about a material.  Right now we're ignoring all the
    fancy rendering options and pretending that everything is the
    very first (top left) tile, and we're not drawing edges or the
    like.
    """

    def __init__(self, info, path, full_path, pakdata, crop_parameters):
        self.info = info
        self.name = info['materialName']
        self.path = path
        self.full_path = full_path
        self.pakdata = pakdata
        self.crop_parameters = crop_parameters

        self._image = None
        self._bgimage = None
        self._midimage = None

    @property
    def image(self):
        """
        Loads the image dynamically on-demand.
        """
        if not self._image:
            df = io.BytesIO(self.pakdata.get(
                    '{}/{}'.format(self.path, self.info['renderParameters']['texture'])
                    ))
            full_image = Image.open(df)
            cropped = full_image.crop(self.crop_parameters)
            df = io.BytesIO()
            cropped.save(df, format='png')
            self._image = QtGui.QPixmap()
            if not self.image.loadFromData(df.getvalue()):
                self._image = None
                # TODO: handle these properly
                raise Exception('Could not load material {}'.format(self.name))
        return self._image

    @property
    def bgimage(self):
        """
        Loads the background version dynamically on-demand.
        """
        if not self._bgimage:
            self._bgimage = StarboundData.highlight_pixmap(
                    self.image.copy(), 0, 0, 0, 192,
                    )
        return self._bgimage

    @property
    def midimage(self):
        """
        Loads the midrange version dynamically on-demand.
        """
        if not self._midimage:
            self._midimage = StarboundData.highlight_pixmap(
                    self.image.copy(), 0, 0, 0, 96,
                    )
        return self._midimage

class Matmod(object):
    """
    Holds info about a matmod.  Right now we're ignoring all the
    fancy rendering options and rendering the whole shebang, though
    we're only using the very first (top left) tile.
    """

    def __init__(self, info, full_path, pakdata):
        self.info = info
        self.name = info['modName']
        self.full_path = full_path
        self.pakdata = pakdata

        self._image = None
        self._bgimage = None
        self._midimage = None

    @property
    def image(self):
        """
        Loads the image dynamically on-demand.
        """
        if not self._image:
            df = io.BytesIO(self.pakdata.get(
                    '/tiles/mods/{}'.format(self.info['renderParameters']['texture'])
                    ))
            full_image = Image.open(df)
            cropped = full_image.crop((0, 8, 16, 24))
            df = io.BytesIO()
            cropped.save(df, format='png')
            self._image = QtGui.QPixmap()
            if not self._image.loadFromData(df.getvalue()):
                self._image = None
                # TODO: Handle this
                raise Exception('Could not load material {}'.format(self.name))
        return self._image

    @property
    def bgimage(self):
        """
        Loads the background version dynamically on-demand.
        """

        if not self._bgimage:
            self._bgimage = StarboundData.highlight_pixmap(
                    self.image.copy(), 0, 0, 0, 90,
                    )
        return self._bgimage

    @property
    def midimage(self):
        """
        Loads the midrange version dynamically on-demand.
        """
        if not self._midimage:
            self._midimage = StarboundData.highlight_pixmap(
                    self.image.copy(), 0, 0, 0, 45,
                    )
        return self._midimage

class Plant(object):
    """
    Class to hold plant info.  This is more basic than all our other
    objects because map plant entities seem to only ever reference the
    PNG directly.
    """

    def __init__(self, pathname, pakdata):
        self.pathname = pathname
        self.pakdata = pakdata
        self._image = None
        self._hi_image = None

    @property
    def image(self):
        """
        Loads the image dynamically on-demand.
        """
        if not self._image:
            self._image = QtGui.QPixmap()
            self._image.loadFromData(self.pakdata.get(self.pathname))
        return self._image

    @property
    def hi_image(self):
        """
        Loads the highlighted version dynamically on-demand.
        """
        if not self._hi_image:
            self._hi_image = StarboundData.highlight_pixmap(
                    self.image.copy(), 255, 255, 255, 100,
                    )
        return self._hi_image

class SBObjectOrientation(object):
    """
    Info about a specific orientation.  Note that we're ignoring
    color variations - just grabbing the top right image for now.
    """

    def __init__(self, info, frames, path, pakdata):
        self.info = info
        self.offset = (0, 0)
        self.anchor = (0, 0)
        self.pakdata = pakdata
        self._image = None
        self._hi_image = None

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
        self.info_frames = self.get_frame(path, image_file, frames, pakdata)
        if image_file[0] == '/':
            self.full_image_file = image_file
        else:
            self.full_image_file = '{}/{}'.format(path, image_file)

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

    @property
    def image(self):
        """
        Loads the image dynamically on-demand.
        """
        if not self._image:
            df = io.BytesIO(self.pakdata.get(self.full_image_file))
            full_image = Image.open(df)
            if self.info_frames:
                (width, height) = tuple(self.info_frames['frameGrid']['size'])
            else:
                (width, height) = full_image.size
            cropped = full_image.crop((0, 0, width, height))
            df = io.BytesIO()
            cropped.save(df, format='png')
            self._image = QtGui.QPixmap()
            self._image.loadFromData(df.getvalue())
        return self._image

    @property
    def hi_image(self):
        """
        Loads the highlighted version dynamically on-demand.
        """
        if not self._hi_image:
            self._hi_image = StarboundData.highlight_pixmap(
                    self.image.copy(), 255, 255, 255, 100,
                    )
        return self._hi_image

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
        self.full_path = '{}/{}'.format(path, filename)
        for o in info['orientations']:
            self.orientations.append(
                    SBObjectOrientation(o, self.frames, path, pakdata)
                    )

    def get_image_path(self, orientation):
        """
        Returns the path to the graphic used
        """
        if orientation < len(self.orientations):
            orient = self.orientations[orientation]
        else:
            orient = self.orientations[0]
        return orient.full_image_file

    def get_image(self, orientation):
        """
        Returns a tuple for displaying the image of this object, at the
        given orientation.  The first element will be the image data
        (as a QPixmap), the second two will be the x and y offsets at which
        it should be rendered.
        """
        if orientation < len(self.orientations):
            orient = self.orientations[orientation]
        else:
            orient = self.orientations[0]
        return (orient.image, orient.offset[0], orient.offset[1])

    def get_hi_image(self, orientation):
        """
        Returns the highlighted image data for the specified orientation
        (as a QPixmap).  This doesn't provide offset info because it's only
        used while hovering, and the position data is already set at that
        point
        """
        if orientation < len(self.orientations):
            orient = self.orientations[orientation]
        else:
            orient = self.orientations[0]
        return orient.hi_image

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
        find all files matching the given extension.  `ext` can either
        be a single extension, or a set of extensions.  Returns a list
        of tuples - the first element is the *full* path the file is
        found in, and the second is the name of the file
        """
        cur = self.top
        for part in path.lower().split('/')[1:]:
            if part not in cur:
                return []
            cur = cur[part]
        if type(ext) != set:
            ext = set([ext])
        return self._search_in(path.lower(), cur, ext)

    def _search_in(self, cur_path, node, exts):
        """
        Inner recursive function for `get_all_recurs_matching_ext`
        """
        to_ret = []
        for name, children in node.items():
            parts = name.rsplit('.', 1)
            if len(parts) == 2 and parts[1] in exts:
                to_ret.append((cur_path, name))
            elif len(children) > 0:
                to_ret.extend(self._search_in(
                    '{}/{}'.format(cur_path, name),
                    children,
                    exts,
                    ))
        return to_ret

class Bookmark(object):
    """
    Class to hold info about a bookmark
    """

    def __init__(self, bookmark):
        """
        `bookmark` should be the dict acquired by looping through the
        player's "teleportBookmarks"
        """
        self.name = bookmark['bookmarkName']
        target = bookmark['target']
        list_data = target[0]
        self.uuid = target[1]
        self.filename = StarboundData.world_string_to_filename(list_data)

    def __lt__(self, other):
        """
        Makes this object sortable (by bookmark name)
        """
        return self.name.lower() < other.name.lower()

class Player(object):
    """
    Wrapper class for the player save dict, to provide a helper function
    or two.
    """

    def __init__(self, playerdict, base_universe):
        self.playerdict = playerdict
        self.base_universe = base_universe
        self.name = playerdict.data['identity']['name']
        self.uuid = playerdict.data['uuid']

        # Figure out our current location
        self.cur_world_filename = None
        self.cur_world_loc = None
        context_path = os.path.join(base_universe, '{}.clientcontext'.format(self.uuid))
        if os.path.exists(context_path):
            with open(context_path, 'rb') as df:
                context = starbound.read_sbvj01(df)
                if 'reviveWarp' in context.data:
                    self.cur_world_filename = StarboundData.world_string_to_filename(
                            context.data['reviveWarp']['world'])
                    if self.cur_world_filename:
                        self.cur_world_loc = tuple(context.data['reviveWarp']['target'])

        # Load in bookmarks
        self.bookmarks = {}

        # TODO: Check that the universeMap dicts always has just one key
        # (a uuid or something)
        for k, v in self.playerdict.data['universeMap'].items():
            for bookmark_data in v['teleportBookmarks']:
                bookmark = Bookmark(bookmark_data)
                if bookmark.filename:
                    if bookmark.filename not in self.bookmarks:
                        self.bookmarks[bookmark.filename] = []
                    self.bookmarks[bookmark.filename].append(bookmark)

    def get_systems(self):
        """
        Returns a list of tuples of the form:
            ((x, y, z), systemdict)
        Describing all systems known to this player.
        (I'm using x, y, z because I imagine that those are maybe
        supposed to be coordinates, but in reality I suspect they're
        effectively random.)
        """

        # TODO: Check that the universeMap dicts always has just one key
        # (a uuid or something)
        for k, v in self.playerdict.data['universeMap'].items():
            # universeMap keys:
            #   systems
            #   teleportBookmarks

            systemlist = v['systems']
            return systemlist

    def get_worlds(self, data, progress_callback=None):
        """
        Given a StarboundData object `data`, returns a list of all worlds
        known to the user, as a list of tuples of the form:
            (mtime, config.WorldNameCache.WorldName tuple, filename)
        
        Note that this has to actually load in world files to get the names
        on the first runthrough, but we *do* now cache the name information,
        so subsequent listings should be much faster.

        `progress_callback` can be used to specify a function to call to update
        the value of a progress bar as we go through (note that we do NOT
        currently support a "real" 0 -> 100% progress bar, since the logic here
        is a bit weird and branches off depending on what we find, as we go.
        Tearing it apart to be able to provide a total-number-of-files-to-load-
        from-disk count before actually processing is more work than I care to
        deal with at the moment).
        """

        worlds = []
        (world_dict, extra_uuid) = data.get_worlds()

        # Get our world name cache
        cache = data.config.worldname_cache

        # Add in our own spaceship, if we've got it
        ship_path = os.path.join(data.base_player, '{}.shipworld'.format(self.playerdict.data['uuid']))
        if os.path.exists(ship_path):
            ship_mtime = os.path.getmtime(ship_path)
            if ship_path not in cache or cache[ship_path].mtime != ship_mtime:
                (world, worlddf) = StarboundData.open_world(ship_path)
                cache.register_other(
                        ship_path,
                        'Starship',
                        'Your Starship',
                        'aaaaa',
                        world,
                        ship_mtime,
                        )
                worlddf.close()
                if progress_callback:
                    progress_callback()
            worlds.append((
                ship_mtime,
                cache[ship_path],
                ship_path,
                ))

        # Loop through all systems we've explored
        for (coords, systemdict) in self.get_systems():
            base_system_name = '{}_{}_{}'.format(*coords)

            if base_system_name in world_dict:
                detected_system_name = None
                for planet in systemdict['mappedPlanets']:
                    if planet['planet'] in world_dict[base_system_name]:
                        for filename in world_dict[base_system_name][planet['planet']]:
                            world_mtime = os.path.getmtime(filename)
                            if filename not in cache or cache[filename].mtime != world_mtime:
                                (world, worlddf) = StarboundData.open_world(filename)
                                cache.register_planet(filename,
                                        world_name=StarboundData.strip_colors(world.info.name),
                                        world_type=world.info.description,
                                        biome_types=', '.join(world.info.world_biomes),
                                        sort_name=StarboundData.world_name_to_sortable(world.info.name),
                                        world_obj=world,
                                        mtime=world_mtime,
                                        )
                                worlddf.close()
                                if progress_callback:
                                    progress_callback()

                            # This is the only way I can find to try and associate a system
                            # to its name (only really useful in the uuid checks below).  Alas!
                            if not detected_system_name:
                                detected_system_name = re.sub(
                                        r'^(.*?) (I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)( .*)?$',
                                        r'\1',
                                        cache[filename].world_name)

                            worlds.append((
                                world_mtime,
                                cache[filename],
                                filename,
                                ))

                # Now loop through any extra worlds we found via UUID
                if not detected_system_name:
                    detected_system_name = '(Unknown System)'
                for uuid in systemdict['mappedObjects'].keys():
                    if uuid in extra_uuid:
                        (filename, description) = extra_uuid[uuid]
                        other_mtime = os.path.getmtime(filename)
                        if filename not in cache or cache[filename].mtime != other_mtime:
                            if description.startswith('unique-'):
                                description = description[7:]
                            (world, worlddf) = StarboundData.open_world(filename)
                            cache.register_other(filename,
                                    world_name='{} - {}'.format(detected_system_name, description),
                                    extra_desc='Non-Planet System Object',
                                    sort_name='{} 99 - {}'.format(detected_system_name, description).lower(),
                                    world_obj=world,
                                    mtime=other_mtime,
                                    )
                            worlddf.close()
                            if progress_callback:
                                progress_callback()
                        worlds.append((
                            other_mtime,
                            cache[filename],
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

    class World(starbound.World):
        """
        Simple little wrapper class because I want to keep track of the filename
        inside the World object, which py-starbound isn't going to care about.
        """

        def __init__(self, stream, filename):
            super().__init__(stream)
            self.filename = filename
            self.base_filename = os.path.basename(filename)

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

    def __init__(self, config):
        """
        `config` should be a Config object (which will have the base game
        installation directory info).
        """

        self.config = config
        self.base_game = config.starbound_data_dir
        self.base_storage = os.path.join(self.base_game, 'storage')
        self.base_player = os.path.join(self.base_storage, 'player')
        self.base_universe = os.path.join(self.base_storage, 'universe')
        self.base_pak = os.path.join(self.base_game, 'assets', 'packed.pak')

        # Read in the data file
        pakdf = open(self.base_pak, 'rb')
        self.pakdf = pakdf
        if pakdf:

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
                    # to "join up" properly.  For pipes I chose a tile which is
                    # the straight horizontal image for most, though note that it's
                    # a vertical image for tentacle pipes.
                    '/tiles/pipetemplate.config': (68, 36, 76, 44),
                    '/tiles/railtemplate.config': (3, 5, 11, 13),
                }

            # Load in our materials
            self.materials = {}
            obj_list = paktree.get_all_recurs_matching_ext('/tiles', 'material')
            for idx, (obj_path, obj_name) in enumerate(obj_list):
                matpath = '{}/{}'.format(obj_path, obj_name)
                material = json.loads(pakdata.get(matpath))
                if 'renderTemplate' in material:
                    if material['renderTemplate'] in crop_params:
                        self.materials[material['materialId']] = Material(
                                material,
                                obj_path,
                                matpath,
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
                # All matmods, at least in the base game, are classicmaterialtemplate
                matmodpath = '/tiles/mods/{}'.format(matmod_name)
                matmod = json.loads(pakdata.get(matmodpath))
                self.matmods[matmod['modId']] = Matmod(matmod, matmodpath, pakdata)

            # Load in object data (this also populates some item names, for container reporting)
            self.items = {}
            self.objects = {}
            obj_list = paktree.get_all_recurs_matching_ext('/objects', 'object')
            for idx, (obj_path, obj_name) in enumerate(obj_list):
                obj_full_path = '{}/{}'.format(obj_path, obj_name)
                obj_json = read_config(pakdata.get(obj_full_path))
                self.objects[obj_json['objectName']] = SBObject(obj_json, obj_name, obj_path, pakdata)
                self.items[obj_json['objectName']] = StarboundData.strip_colors(obj_json['shortdescription'])

            # Load in plant data
            # The Entities seem to actually only references these by PNG path, so
            # I guess that's what we'll do too.
            self.plants = {}
            img_list = paktree.get_all_recurs_matching_ext('/plants', 'png')
            for idx, (img_path, img_name) in enumerate(img_list):
                img_full_path = '{}/{}'.format(img_path, img_name)
                self.plants[img_full_path] = Plant(img_full_path, pakdata)

            # Load in liquid data
            self.liquids = {}
            liquid_list = paktree.get_all_recurs_matching_ext('/liquids', 'liquid')
            for idx, (liquid_path, liquid_name) in enumerate(liquid_list):
                liquid_full_path = '{}/{}'.format(liquid_path, liquid_name)
                liquid = read_config(pakdata.get(liquid_full_path))
                self.liquids[liquid['liquidId']] = Liquid(liquid)

            # Load in extra item name mapping (just for reporting container contents)
            # (have verified that none of these "overwrite" the mappings set up by
            # the object processing)
            item_list = paktree.get_all_recurs_matching_ext('/items', set([
                # There may be some things in here which shouldn't be, but whatever.
                # Might make more sense to *exclude* extensions instead?  That
                # list would be a bit shorter: animation, combofinisher,
                # config, frames, lua, png, weaponability, weaponcolors
                'activeitem', 'augment', 'back', 'beamaxe', 'chest',
                'consumable', 'currency', 'flashlight', 'harvestingtool',
                'head', 'inspectiontool', 'instrument', 'item', 'legs',
                'liqitem', 'matitem', 'miningtool', 'painttool',
                'thrownitem', 'tillingtool', 'unlock', 'wiretool',
                ]))
            for item_path, item_name in item_list:
                item_full_path = '{}/{}'.format(item_path, item_name)
                item = read_config(pakdata.get(item_full_path))
                self.items[item['itemName']] = StarboundData.strip_colors(item['shortdescription'])

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

    def close(self):
        """
        Closes our open filehandle
        """
        if self.pakdf:
            self.pakdf.close()

    @staticmethod
    def world_name_to_sortable(name):
        """
        Given a raw world name (with color highlights and everything), convert
        it to a string that will sort properly using regular ol' alphanumerics.
        This is basically just converting the roman numerals into numbers.
        """
        for (old, new) in StarboundData.world_name_sortable_conversions:
            if old in name:
                return StarboundData.strip_colors(name.replace(old, new).lower())
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
            world = StarboundData.World(worldmm, filename)
            return (world, worldmm)

    @staticmethod
    def strip_colors(input_string):
        """
        Strips color information from a string
        """
        return re.sub('\^\w+?;', '', input_string)

    @staticmethod
    def world_string_to_filename(world_desc):
        """
        Converts a world description string (colon-delimited, starting with
        CelestialWorld, ClientShipWorld, or InstanceWorld) into a filename.
        Note that this does *not* return the data directory as well -- if
        you intend to open a file with this (as opposed to just checking
        filenames), be sure to check for `shipworld` in the file name, to
        know to load from the `player` dir instead of `universe`.
        """
        parts = world_desc.split(':')
        world_type = parts[0]
        if world_type == 'CelestialWorld':
            if len(parts) < 5:
                raise Exception('Not sure what to do with world string: {}'.format(world_desc))
            coords = (parts[1], parts[2], parts[3])
            planet = parts[4]
            if len(parts) == 6:
                moon = parts[5]
                return '{}_{}_{}_{}_{}.world'.format(
                        *coords,
                        planet,
                        moon,
                        )
            else:
                return '{}_{}_{}_{}.world'.format(
                        *coords,
                        planet,
                        )
        elif world_type == 'ClientShipWorld':
            # Hardly seems worth it to bookmark your own ship, but it *is*
            # possible, so we'll support it.
            return '{}.shipworld'.format(parts[1])
        elif world_type == 'InstanceWorld':
            if len(parts) < 4:
                raise Exception('Not sure what to do with world_string: {}'.format(world_desc))
            inner_desc = parts[1]
            target_uuid = parts[2]
            suffix = parts[3]
            if target_uuid != '-' and suffix != '-':
                # Bookmarks to The Outpost (and perhaps others?) have blank info here,
                # and we couldn't load them anyway, so just skip 'em
                # TODO: is it always "unique" as a prefix?
                return 'unique-{}-{}-{}.world'.format(
                        inner_desc,
                        target_uuid,
                        suffix,
                        )
        else:
            print('Unknown world type: {}'.format(world_type))
        return None

    @staticmethod
    def highlight_pixmap(pixmap, r, g, b, a):
        """
        Given a QPixmap `pixmap`, highlight it with the given color.
        For convenience, returns `pixmap`, though of course the reference
        will not have changed.
        """
        painter = QtGui.QPainter(pixmap)
        painter.setCompositionMode(painter.CompositionMode_SourceAtop)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b, a)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 0)))
        painter.drawRect(0, 0, pixmap.width(), pixmap.height())
        return pixmap
