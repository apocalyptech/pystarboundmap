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
   - Map loading/rendering (this is slooow):
     - Only load/render what's actually on the screen (and maybe a few
       screenfuls in each direction, so that ideally there's not a lot
       of pop-in while scrolling?)
     - Load more of the map in the background, maybe, in addition to
       the above?
   - Window defocus/refocus:
     - This could just be a problem on X11 - presumably it's display-
       dependant.  Anyway, losing focus and then regaining focus causes
       a very noticeable pause while, presumably, the whole graphics
       surface gets reloaded into an X11 buffer.  Maybe some of my
       proposed fixes for the map render/load could help here?  Will
       have to experiment.
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
 - How big do worlds get, anyway?  A 6000x3000 world that I loaded is
   a bit slow but not too bad (though this is before adding in being
   able to highlight/click on tiles)
 - Parse render templates properly

LICENSE
-------

pystarboundmap is licensed under the
[New/Modified (3-Clause) BSD License](https://opensource.org/licenses/BSD-3-Clause).
A copy is also found in [COPYING.txt](COPYING.txt).
