#!/usr/bin/env python3
# vim: set expandtab tabstop=4 shiftwidth=4:

import os
import appdirs
import configparser

class Config(object):
    """
    Class to hold our config/prefs info
    """

    # Starbound Vars
    starbound_data_dir = None

    # GUI Vars
    app_w = 1050
    app_h = 700

    def __init__(self):

        self.config_dir = appdirs.user_config_dir('pystarboundmap')
        self.config_file = os.path.join(self.config_dir, 'pystarboundmap.conf')

        self.load()

    def load(self):
        """
        Reads our config from the config file, or attempts to autodetect,
        if the config file is not already found.  Will automatically save out
        the config file if it was not present at first.
        """

        if os.path.exists(self.config_dir) and os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config.read(self.config_file)
            self.starbound_data_dir = config['starbound']['data_dir']
            if self.starbound_data_dir == 'None':
                self.starbound_data_dir = None
            self.app_w = int(config['gui']['app_w'])
            self.app_h = int(config['gui']['app_h'])
            return

        # If we got here, we don't have a config file, so we'll have to
        # attempt to autodetect some paths.

        # Finally, save out the file
        self.save()

    def save(self):
        """
        Saves our config to disk
        """

        # Create the config dir if it's not already present
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

        # Now save
        config = configparser.ConfigParser()
        config['starbound'] = {}
        if self.starbound_data_dir:
            config['starbound']['data_dir'] = self.starbound_data_dir
        else:
            config['starbound']['data_dir'] = 'None'
        config['gui'] = {}
        config['gui']['app_w'] = str(self.app_w)
        config['gui']['app_h'] = str(self.app_h)
        with open(self.config_file, 'w') as df:
            config.write(df)

