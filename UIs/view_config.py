from addons.UIdea.libs import ui as ui_class
import re
import discord
import time

SELECTED_FORMATTING = ('**`>`', '**')
REGULAR_FORMATTING = ('`.`', '')
NO_SELECTOR_FORMATTING = ('', '')
JOIN_STR = '\n'
PATH_SEPERATOR = ' > '
DISPLAY_MODES = ('packages','addons', 'info')
INFO_LIST_PREFIX = '-- '
INFO_LIST_SUFFIX = '\n'

class UI(ui_class.UI):
    def shouldCreate(message):
        return collect_args(message.content) is not None and message.server is not None

    def onCreate(self, message):
        # init
        args = collect_args(message.content)
        self.history = ['packages', '', '']
        self.verbose = args.group(2) is not None
        self.server = message.server.id
        self.selector_index = 0
        # generate text to display
        if args.group(1) is not None:
            # look for package/addon name
            matches_found = 0
            if args.group(1) in self.bot.packages:
                self.history[1] = args.group(1)
                self.display_mode_index = 1
                matches_found = 1
            else:
                if args.group(1) in self.bot.commands:
                    matches_found += 1
                    pkg = self.bot.get_package(args.group(1),self.bot.COMMANDS)
                    if pkg is None:
                        matches_found -= 1
                if args.group(1) in self.bot.reactions:
                    matches_found += 1
                    pkg = self.bot.get_package(args.group(1),self.bot.REACTIONS)
                    if pkg is None:
                        matches_found -= 1
                if args.group(1) in self.bot.plugins:
                    matches_found += 1
                    pkg = self.bot.get_package(args.group(1),self.bot.PLUGINS)
                    if pkg is None:
                        matches_found -= 1
                if matches_found == 1:
                    self.selector_index = -1
                    self.history[1] = pkg
                    self.history[2] = args.group(1)
                    self.display_mode_index = 2
            if matches_found == 1:
                # generate and display text
                self.now_displaying = self.history[self.display_mode_index]
                self.lines = self.get_lines_from(args.group(1), mode=DISPLAY_MODES[self.display_mode_index])
                self.embed.description = self.make_desc()
                self.update()
                return
        # fall back generate and display text
        self.now_displaying = self.history[0]
        self.display_mode_index = 0
        self.lines = self.get_package_lines()
        self.embed.description = self.make_desc()
        self.update()

    def up(self, reaction, user):
        if self.selector_index != -1:
            if self.selector_index > 0:
                self.selector_index -= 1
            else:
                self.selector_index = len(self.lines)-1
        self.embed.description = self.make_desc()
        self.update()

    def down(self, reaction, user):
        if self.selector_index != -1:
            if self.selector_index+1 < len(self.lines):
                self.selector_index += 1
            else:
                self.selector_index = 0
        self.embed.description = self.make_desc()
        self.update()

    def select(self, reaction, user):
        if self.display_mode_index+1 < len(DISPLAY_MODES):
            self.display_mode_index += 1
            self.now_displaying = self.lines[self.selector_index]
            self.history[self.display_mode_index] = self.now_displaying
            self.lines = self.get_lines_from(self.now_displaying, mode=DISPLAY_MODES[self.display_mode_index])
            if self.display_mode_index+1 == len(DISPLAY_MODES):
                # deepest screen has nothing to select
                self.selector_index = -1
            else:
                self.selector_index = 0
            self.embed.description = self.make_desc()
            self.update()

    def back(self, reaction, user):
        if self.display_mode_index > 0:
            self.display_mode_index -= 1
            self.now_displaying = self.history[self.display_mode_index]
            if self.now_displaying == 'packages':
                self.lines = self.get_package_lines()
            else:
                self.lines = self.get_lines_from(self.now_displaying, mode=DISPLAY_MODES[self.display_mode_index])
            self.selector_index = 0
            self.embed.description = self.make_desc()
            self.update()


    def make_desc(self):
        new_desc = ''
        new_desc += '**' + self.make_history_line() + '**\n\n'
        for i in range(len(self.lines)):
            if self.selector_index == -1:
                new_desc += NO_SELECTOR_FORMATTING[0]
                new_desc += self.lines[i]
                new_desc += NO_SELECTOR_FORMATTING[1]
            elif i == self.selector_index:
                new_desc += SELECTED_FORMATTING[0]
                new_desc += self.lines[i]
                new_desc += SELECTED_FORMATTING[1]
            else:
                new_desc += REGULAR_FORMATTING[0]
                new_desc += self.lines[i]
                new_desc += REGULAR_FORMATTING[1]
            new_desc += JOIN_STR
        if self.verbose:
            new_desc += '**__Verbose Info__**\n```'
            new_desc += '\ncursor ' + str(self.selector_index) + ', '+ str(self.display_mode_index)
            new_desc += '\nhistory ' + str(self.history)
            new_desc += '\nupdated @ ' + str(time.time())
            new_desc += '```'
        return new_desc

    def make_history_line(self):
        return PATH_SEPERATOR.join(self.history[:self.display_mode_index+1])

    def get_package_lines(self):
        lines = list()
        for pkg in self.bot.packages:
            lines.append(pkg)
        lines.sort()
        return lines

    def get_lines_from(self, name, mode='addons'):
        lines = list()
        if mode == 'packages':
            return self.get_package_lines()

        if mode == 'addons':
            for addon_type in self.bot.packages[name]:
                lines += self.bot.packages[name][addon_type]
            lines.sort()
            return lines

        if mode == 'info':
            # find addon
            is_command = name in self.bot.commands
            is_reaction = name in self.bot.reactions
            is_plugin = name in self.bot.plugins
            if (is_command + is_reaction + is_plugin) > 1:
                pkg = self.history[1]
                is_command = name in self.bot.packages[pkg][self.bot.COMMANDS]
                is_reaction = name in self.bot.packages[pkg][self.bot.REACTIONS]
                is_plugin = name in self.bot.packages[pkg][self.bot.PLUGINS]

            # make/get lines
            if is_command:
                lines = self.get_command_info().split(JOIN_STR)
                return lines
            if is_reaction:
                lines = self.get_reaction_info().split(JOIN_STR)
                return lines
            if is_plugin:
                lines = self.get_plugin_info().split(JOIN_STR)
                return lines

    def get_command_info(self):
        info = ''
        server_id = self.server
        name = self.history[-1]
        cmd_inst = self.bot.commands[name]
        info += '**__Permitted Users__**\n'
        if server_id in cmd_inst.perms:
            if len(cmd_inst.perms[server_id]) == 0:
                info += '- No one -\n'
            else:
                for user_id in cmd_inst.perms[server_id]:
                    user = self.get_user_from_id(user_id)
                    info += INFO_LIST_PREFIX
                    info += '<@'+user_id+'>'
                    info += INFO_LIST_SUFFIX
        else:
            info += '- Everyone -\n'
        return info

    def get_reaction_info(self):
        info = ''
        server_id = self.server
        name = self.history[-1]
        rxn_inst = self.bot.reactions[name]
        info += '**__Permitted Users__**\n'
        if server_id in rxn_inst.perms:
            if len(rxn_inst.perms[server_id]) == 0:
                info += '- No one -\n'
            else:
                for user_id in rxn_inst.perms[server_id]:
                    user = self.get_user_from_id(user_id)
                    info += INFO_LIST_PREFIX
                    info += '<@'+user_id+'>'
                    info += INFO_LIST_SUFFIX
        else:
            info += '- Everyone -\n'
        info += '**__Emoji__**\n'
        if not isinstance(rxn_inst.emoji, dict):
            info += '- Not Supported -\n'
        elif server_id in rxn_inst.emoji:
            if len(rxn_inst.emoji[server_id])==1:
                info += rxn_inst.emoji[server_id] + '\n'
            else: # assumed emoji id
                emoji = discord.utils.find(lambda e : e.id == rxn_inst.emoji[server_id], self.bot.get_all_emojis())
                info += ':' + emoji.name + ':'
        else:
            info += '- No emoji set -'
        return info

    def get_plugin_info(self):
        info = ''
        server_id = self.server
        name = self.history[-1]
        plug_inst = self.bot.plugins[name]
        info = '- Not Supported (PLUGIN) -'
        return info

    def get_user_from_id(self, user_id):
        return discord.utils.find(lambda u: u.id == user_id, self.bot.get_all_members())

def collect_args(msg_content):
    return re.search(r'\bconfig(?:uration)?(?:\s*for)?(?:\s*((?![\-\s])\S*))?(?:\s*(-v\b))?', msg_content, re.I)
