import os
from lutris import settings
from lutris.util import display
from lutris.runners.runner import Runner


class zdoom(Runner):
    # http://zdoom.org/wiki/Command_line_parameters
    description = "ZDoom DOOM Game Engine"
    human_name = "ZDoom"
    platform = "PC"
    game_options = [
        {
            'option': 'main_file',
            'type': 'file',
            'label': 'WAD file',
            'help': ("The game data, commonly called a WAD file.")
        },
        {
            'option': 'file',
            'type': 'string',
            'label': 'PWAD file',
            'help': ("Used to load one or more PWAD files which generally contain "
                     "user-created levels.")
        },
        {
            'option': 'warp',
            'type': 'string',
            'label': 'Warp to map',
            'help': ("Starts the game on the given map.")
        }
    ]
    runner_options = [
        {
            "option": "2",
            "label": "Pixel Doubling",
            "type": "bool",
            'default': False
        },
        {
            "option": "4",
            "label": "Pixel Quadrupling",
            "type": "bool",
            'default': False
        },
        {
            "option": "nostartup",
            "label": "Disable Startup Screens",
            "type": "bool",
            'default': False
        },
        {
            "option": "nosound",
            "label": "Disable Both Music and Sound Effects",
            "type": "bool",
            'default': False,
        },
        {
            "option": "nosfx",
            "label": "Disable Sound Effects",
            "type": "bool",
            'default': False
        },
        {
            "option": "nomusic",
            "label": "Disable Music",
            "type": "bool",
            'default': False
        },
        {
            "option": "skill",
            "label": "Skill",
            "type": "choice",
            "default": '',
            "choices": {
                ("None", ''),
                ("I'm Too Young To Die (0)", '0'),
                ("Hey, Not Too Rough (1)", '1'),
                ("Hurt Me Plenty (2)", '2'),
                ("Ultra-Violence (3)", '3'),
                ("Nightmare! (4)", '4'),
            }
        }
    ]

    def get_executable(self):
        return os.path.join(settings.RUNNER_DIR, 'zdoom')

    @property
    def working_dir(self):
        # Run in the installed game's directory.
        return self.game_path

    def play(self):
        command = [self.get_executable()]

        resolution = self.runner_config.get("resolution")
        if resolution:
            if resolution == 'desktop':
                resolution = display.get_current_resolution()
            width, height = resolution.split('x')
            command.append("-width")
            command.append(width)
            command.append("-height")
            command.append(height)

        # Append any boolean options.
        bool_options = ['nomusic', 'nosfx', 'nosound', '2', '4', 'nostartup']
        for option in bool_options:
            if self.runner_config.get(option):
                command.append("-%s" % option)

        # Append the skill level.
        skill = self.runner_config.get('skill')
        if skill:
            command.append("-skill")
            command.append(skill)

        # Append the warp map.
        warp = self.game_config.get('warp')
        if warp:
            command.append("-warp")
            command.append(warp)

        # Append the wad file to load, if provided.
        wad = self.game_config.get('main_file')
        if wad:
            command.append("-iwad")
            command.append(wad)

        # Append the pwad files to load, if provided.
        pwad = self.game_config.get('file')
        if pwad:
            command.append("-file")
            command.append(pwad)

        return {'command': command}
