Python Starbound Mapper
-----------------------

Yet another Starbound mapper!  This is in very early stages, and
apologies if it never gets much beyond this point but it pops up
in your Google results anyway.

Uses:
 - Python 3
 - python-pillow
 - PyQt5
 - py-starbound (by blixt)

**Extremely** rough at the moment, and not suitable for public use
yet.  Will update this with usage info and the like if it ever gets to a nicer
stage.  Uses blixt's lovely
[py-starbound](https://github.com/blixt/py-starbound) to get at the data
(currently it requires some functions which are not yet actually committed to
that project though).

TODO
----

 - Choose maps (totally hardcoded to my own savegames at the moment)
 - Add NPCs/Enemies/Monsters?
   - (What's a StagehandEntity, I wonder?)
 - Highlight tiles for info
   - Click for full info
 - Go to spawn points, flags
 - Zoom
   - Slider
   - `+`/`-` via keyboard
 - Open file menu
 - Progress bar while loading resources
 - Search for item types (ores, quest-related things?)
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
     - Need a progress bar for loading
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
