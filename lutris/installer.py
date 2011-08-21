#!/usr/bin/python
# -*- coding:Utf-8 -*-
#
#  Copyright (C) 2010 Mathieu Comandon <strider@strycore.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License version 3 as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

""" This is where takes place the whole install process for games

TODO: The gui frontend
"""

import os
import gtk
import yaml
import shutil
import urllib
import urllib2
import subprocess
import lutris.constants
from lutris.constants import LUTRIS_CACHE_PATH, INSTALLER_URL

from lutris.config import LutrisConfig
from lutris.gui.common import DownloadDialog, ErrorDialog, DirectoryDialog
from lutris.util import log

def unzip(filename, dest=None):
    """Unzips a file"""
    command = ["unzip", '-o', filename]
    if dest:
        command = command + ['-d', dest]
    subprocess.call(command)

def unrar(filename):
    """Unrar a file"""

    subprocess.call(["unrar", "x", filename])

def untar(filename, dest=None, method='gzip'):
    """Untar a file"""
    cwd = os.getcwd()
    if dest and os.path.exists(dest):
    	os.chdir(dest)
    if method == 'gzip':
    	compression_flag = 'z'
    elif method == 'bzip2':
        compression_flag = 'j'
    else:
    	compression_flag = ''
    subprocess.call(["tar", "x%sf" % compression_flag, filename])
    os.chdir(cwd)

def run_installer(filename):
    """Run an installer of .sh or .run type"""
    subprocess.call(["chmod", "+x", filename])
    subprocess.call([filename])

def reporthook(piece, received_bytes, total_size):
    """Follows the progress of a download"""

    print "%d %%" % ((piece * received_bytes) * 100 / total_size)


class Installer(gtk.Dialog):
    """ Lutris installer """

    def __init__(self, game, installer=False):
        # Internal game config
        self.lutris_config = None

        # Name of the game
        self.game_name = game

        # Stores a list of actions that will be sent back to the user
        # in order to complete the installation
        self.installer_user_actions = []

        # Actions that the installer has to run
        # in order to complete the install.
        self.installer_actions = []

        # List of errors that occurred while installing the game
        self.installer_errors = []

        # Content of yaml file
        self.install_data = {}

        # Essential game information to create Lutris launcher
        self.game_info = {}

        # Dictionary of the files needed to install the game
        self.gamefiles = {}

        if installer is False:
            self.installer_dest_path = os.path.join(LUTRIS_CACHE_PATH,
                                                    self.game_name + ".yml")
        else:
            self.installer_dest_path = installer
        success = self.pre_install()
        if not success:
            log.logger.error("Unable to install game")
            log.logger.error(self.installer_errors)
            if 'INSTALLER_UNREACHABLE' in self.installer_errors:
                ErrorDialog("Can't find an installer for \"%s\""
                                % self.game_name)
        else:
            log.logger.info("Ready! Launching installer.")

        gtk.Dialog.__init__(self)
        self.set_default_size(600,480)
        self.set_resizable(False)
        self.connect('destroy', lambda q: gtk.main_quit())

        banner = gtk.Image()
        banner.set_from_file('/home/strider/quake-banner.jpg')
        self.vbox.pack_start(banner, False, False)

        description = gtk.Label()
        description.set_markup('Quake is a classic FPS released by iD Software in 1996')
        description.set_padding(20, 20)
        self.vbox.pack_start(description, True, True)

        separator = gtk.HSeparator()
        self.vbox.pack_start(separator, True, True)

        button = gtk.Button('Install')
        button.connect('clicked', self.install)

        alignment = gtk.Alignment()
        alignment.set(0.95,0.1,0.15,0)
        alignment.set_padding(10,10,0,0)
        alignment.add(button)
        
        self.vbox.pack_start(alignment, False, False)
        self.show_all()

    def download_installer(self):
        """ Save the downloaded installer to disk. """

        full_url = INSTALLER_URL + self.game_name + '.yml'
        request = urllib2.Request(url=full_url)
        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError:
            log.logger.debug("Server is unreachable")
            self.installer_errors.append("INSTALLER_UNREACHABLE")
            success = False
        else:
            urllib.urlretrieve(full_url, self.installer_dest_path)
            success = True
        return success

    def set_games_dir(self, path):
        """ Set the base path where the game will be installed """
        self.games_dir = path

    def pre_install(self):
        """Reads the installer and checks everything is OK
        before beginning the install process
        """

        # Download installer if not already there.
        if not os.path.exists(self.installer_dest_path):
            success = self.download_installer()
            if not success:
                return False
        else:
            log.logger.debug('Using local copy of the installer')
        # Parse installer file
        success = self.parseconfig()
        self.games_dir = self.lutris_config.get_path()
        if not self.games_dir:
            self.installer_user_actions.append("ask_games_dir")
            log.logger.debug('Install dir missing')
            return False

        self.game_dir = os.path.join(self.games_dir, self.game_name)
        if not os.path.exists(self.game_dir):
            os.mkdir(self.game_dir)

        return success

    def install(self, widget=None, data=None):
        """ Runs the actions to complete the install. """
        self.download_game_files()
        os.chdir(self.game_dir)

        for action in self.installer_actions:
            action_name = action.keys()[0]
            action_data = action[action_name]
            mappings = {'check_md5': self.check_md5,
                        'extract' : self._extract,
                        'move' : self._move,
                        'delete': self.delete,
                        'request_media': self._request_media,
                        'run': self._run,
                        'locate': self._locate }
            if action_name not in mappings.keys():
                print "Action " + action_name + " not supported !"
                return False
            mappings[action_name](action_data)
        self.write_config()

    def parseconfig(self):
        """ Reads the installer file. """

        self.install_data = yaml.load(file(self.installer_dest_path, 'r').read())

        #Checking protocol
        protocol_version = self.install_data['protocol']
        if protocol_version != lutris.constants.protocol_version:
            print("Wrong protocol version (Expected %d, got %d)" %
                  (lutris.constants.protocol_version, protocol_version))
            return False

        mandatory_fields = ['version', 'runner', 'name']
        optional_fields = ['exe', 'iso', 'rom']
        for field in mandatory_fields:
            self.game_info[field] = self.install_data[field]
        for field in optional_fields:
            if field in self.install_data:
                self.game_info[field] = self.install_data[field]
        self.game_files = self.install_data['files']

        self.game_name = self.install_data['name']
        self.game_slug = os.path.basename(self.installer_dest_path)[:-4]

        self.installer_actions = self.install_data['installer']
        self.lutris_config = LutrisConfig(runner=self.game_info['runner'])
        return True

    def download_game_files(self):
        for gamefile in self.game_files:
            file_id = gamefile.keys()[0]
            # Game files can be either a string, containing the location of the
            # file to fetch or a dict with the possible options :
            # - url : location of file (mandatory)
            # - filename : force destination filename
            # - nocopy : don't copy the file in the cache (doesn't work for internet links)
            copyfile = True
            if isinstance(gamefile[file_id], dict):
                url = gamefile[file_id]['url']
                if 'filename' in gamefile[file_id]:
                    filename = gamefile[file_id]['filename']
                else:
                    filename = None

                if 'nocopy' in gamefile[file_id]:
                    copyfile = False
            else:
                url = gamefile[file_id]
                filename = None
            dest_path = self._download(url, filename, copyfile)
            self.gamefiles[file_id] = dest_path
        return True

    def write_config(self):
        """ Writes the game configration as a Lutris launcher. """
        config_filename = os.path.join(lutris.constants.GAME_CONFIG_PATH,
                                       self.game_slug + ".yml")

        config_data = {'game': {},
                       'realname': self.game_info['name'],
                       'runner': self.game_info['runner']}
        launchers = ['exe', 'iso', 'rom']

        for launcher in launchers:
            if(launcher in self.game_info):
                config_data['game'][launcher] = os.path.join(self.game_dir,
                                                             self.game_info[launcher])

        yaml_config = yaml.dump(config_data, default_flow_style=False)
        file(config_filename, "w").write(yaml_config)

    def check_md5(self, data):
        """ Calculates the checksum of a file and validates it. """

        print 'checking md5 for file ' + self.gamefiles[data['file']]
        print 'expecting ' + data['value']
        print "NOT IMPLEMENTED"
        return True

    def _download(self, url, filename=None, copyfile=True):
        """ Downloads a file.
        Not necessarily downloading a file but fetching it from anywhere.
        url: location of the file to fetch
        destfile: force filename of destfile

        return the path of local file
        """

        log.logger.debug('Downloading ' + url)
        dest_dir = os.path.join(lutris.constants.TMP_PATH, self.game_slug)
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        if not filename:
            filename = os.path.basename(url)
        dest_file = os.path.join(dest_dir, filename)
        if os.path.exists(dest_file):
            return dest_file
        if url.startswith("file://"):
            location = url[7:]
            if copyfile is True:
                shutil.copy(location, dest_dir)
        elif url.startswith("$ASK_DIR"):
            #Ask the user where is located the file
            basename = url[9:]
            d = DirectoryDialog("Select location of file %s " % basename)
            file_path = d.folder
            if copyfile is True:
                location = os.path.join(file_path, basename)
                shutil.copy(location, dest_dir)
        else:
            DownloadDialog(url, dest_file)
        return dest_file

    def delete(self, data):
        """ Deletes a file """
        print "will delete " + self.gamefiles[data['file']]
        print "let's not delete anything right now, m'kay ?"

    def _get_path(self, data):
        """Return a filesystem path based on data"""

        if data == 'parent':
            path = os.path.join(self.game_dir, '..')
        else:
        	path = self.game_dir
        return path

    def _extract(self, data):
        """ Extracts a file, guessing the compression method """

        print 'extracting ' + data['file']
        filename = self.gamefiles[data['file']]
        extension = filename[filename.rfind(".") + 1:]

        if extension == "zip":
            unzip(filename, self.game_dir)
        if filename.endswith('.tgz') or filename.endswith('.tar.gz'):
        	untar(filename, self._get_path('parent'))
        if filename.endswith('.tar.bz2'):
        	untar(filename, None, 'bzip2')

    def _move(self, data):
        """ Moves a file. """
        src = data['src']
        if src in self.gamefiles.keys():
            src = self.gamefiles[src]
        destination_alias = data['dst']
        if data['dst'] == 'gamedir':
            dst = self.game_dir
        else:
            dst = data['dst'].replace('homedir', os.path.expanduser('~'))
            if not os.path.exists(dst):
                dst = '/tmp'

        print "Moving %s to %s" % (src, dst)

        if not os.path.exists(src):
            print "I cannot move what does not exist"
            return False
        try:
            shutil.move(src, dst)
        except shutil.Error:
            print "Could not move the file, destination already exists ?"
            return False
        return True

    def _request_media(self, data):
        if 'default' in data:
            path = data['default']
        if os.path.exists(os.path.join(path, data['contains'])):
            return True
        else:
            return False
    def _run(self, data):
        exec_path = os.path.join(lutris.constants.TMP_PATH, self.game_slug,
                                 self.gamefiles[data['file']])
        if not os.path.exists(exec_path):
            print "unable to find %s" % exec_path
            exit()
        else:
            os.popen('chmod +x %s' % exec_path)
            subprocess.call([exec_path])

    def _locate(self):
        return None


