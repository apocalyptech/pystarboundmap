Python Starbound Mapper
-----------------------

Yet another Starbound mapper!  This is in pretty early stages, but is at
least pretty functional as a bare-bones map viewer.

Uses:
 - Python 3
 - python-pillow
 - PyQt5
 - [py-starbound](https://github.com/blixt/py-starbound) (by blixt)

**NOTE:** There is still a hardcoded path at the top of `data.py` which defines
where to find the Starbound install dir, so be sure to change it yourself:

```py
# Hardcoded stuff for now
base_game = '/usr/local/games/Steam/SteamApps/common/Starbound'
```

Screenshot
----------

This is pretty much it, at the moment.  You can open new maps by filename,
or by choosing a character's name followed by a planet name (note that that
one doesn't yet let you open moons, space stations, etc).  Click-and-drag
will move the map around, in addition to your usual scrolling methods.

[![pystarboundmap screenshot](screenshot.png)](screenshot.png)

TODO
----

 - Add NPCs/Enemies/Monsters/Vehicles?
   - (What's a StagehandEntity, I wonder?)
 - Add liquids
 - Highlight tiles for info
   - Click for full info
 - Go to spawn points, flags
 - Zoom
   - Slider
   - `+`/`-` via keyboard
 - Initial open dialog doesn't center on parent window?
 - Open-by-Name dialog doesn't include space stations or moons or
   anomalies
 - Progress bar while loading resources
 - Search for item types (ores, quest-related things?)
 - Platforms seem to draw a black area underneath 'em
 - Visualization of explored areas (as defined by light sources)
 - Remember window geometry between runs
 - Autodetect game location
   - Have some methods for Steam detection via other projects, but
     is there any registry entries or something for non-Steam installs?
     Does Starbound even have non-Steam builds?
   - Manually choose install dir, regardless
 - Support for mods
 - Performance improvements
   - Resource loading:
     - This only takes about 5-6 sec on my machine, so it's not bad,
       but I suspect I could get rid of some spurious PNG conversions
   - Map loading/rendering:
     - This is pretty slow, and I'll have to profile it to figure out
       where the slowness actually is.  It's more of an annoyance at
       the moment, though, since we're now only rendering the visible
       areas of the map, rather than loading the entire thing at the
       app startup
     - Render more than just a single extra region on each side?
     - Would like to move map loading into a separate thread so it can
       happen more in the background, rather than freezing the GUI
       while it loads.  (Using the mouse scrollwheel especially is
       quite jerky because of this.)
     - Keep a "history" of loaded Regions and only expire them after
       they haven't been used in N redraws?  That way, scrolling back
       to a previously-visited area would be less likely to have to re-load.
 - Toggles for various element types?
 - Fancier rendering?  (base map materials have "edges" which we completely
   ignore at the moment.  I suspect I'll never actually implement this
   since it'd probably increas our render time for a bunch, and it's not
   really important for anything you'd want to actually use this for)
 - Properly handle on/off items (light sources), open/closed doors, etc
 - Properly handle coloration of objects/tiles?
 - Randomize tiles w/ multiple options (dirt, etc, seems to be randomly
   assigned from four or five options.  The randomization is fixed-seed
   inside Starbound itself, and I highly doubt I'd be able to get it the
   same, but maps would probably still look nicer with them randomized)
 - Parse render templates properly
 - "Attach" objects/plants to Tile objects so they can be reported in
   the mouseover notifications

LICENSE
-------

pystarboundmap is licensed under the
[New/Modified (3-Clause) BSD License](https://opensource.org/licenses/BSD-3-Clause).
A copy is also found in [COPYING.txt](COPYING.txt).
