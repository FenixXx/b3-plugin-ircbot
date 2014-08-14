#
# IRC BOT Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2014 Daniele Pantaleone <fenix@bigbrotherbot.net>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# CHANGELOG
#
# 17/07/2014 - 1.0 - Fenix    - initial release
# 05/08/2014 - 1.1 - Pr3acher - fixed duration for tempban
# 14/08/2014 - 1.2 - Fenix    - do not display game information if the server is empty
#                             - added command !listbans: display the active bans of a given client
#                             - inform clients when a received command is not registered

__author__ = 'Fenix'
__version__ = '1.2'

import b3
import b3.plugin
import b3.events

from b3.functions import getCmd
from b3.functions import minutesStr
from ConfigParser import NoOptionError
from ConfigParser import NoSectionError
from ircbot.bot import IRCBot
from ircbot.colors import *
from threading import Thread
from xml.dom import minidom

class IrcbotPlugin(b3.plugin.Plugin):
    """
    IRC bot plugin implementation.
    """
    adminPlugin = None  # Admin Plugin object instance
    pthread = None      # separate thread executing the IRC BOT main loop
    ircbot = None       # IRC BOT object instance

    serverinfo = {
        'ip': '',
        'port': '',
    }

    settings = {
        'nickname': '',
        'interval': 1,
        'showbans': True,
        'showkicks': True,
        'showgame': True,
        'address': '',
        'port': 6667,
        'maxrate': 1,
        'channel': '',
        'perform': [],
    }

    ####################################################################################################################
    ##                                                                                                                ##
    ##  PLUGIN INIT                                                                                                   ##
    ##                                                                                                                ##
    ####################################################################################################################

    def __init__(self, console, config=None):
        """
        Build the plugin object.
        :param console: The parser instance.
        :param config: The plugin configuration object instance.
        """
        b3.plugin.Plugin.__init__(self, console, config)
        self.adminPlugin = self.console.getPlugin('admin')
        if not self.adminPlugin:
            self.critical('could not start without admin plugin')
            raise SystemExit(220)

    def onLoadConfig(self):
        """
        Load plugin configuration.
        """
        try:
            self.settings['nickname'] = self.config.get('settings', 'nickname')
            self.debug('loaded settings/nickname: %s' % self.settings['nickname'])
        except NoOptionError:
            self.error('could not find settings/nickname in config file: plugin will be disabled')

        try:
            self.settings['interval'] = self.config.getint('settings', 'interval')
            self.debug('loaded settings/interval: %s' % self.settings['interval'])
        except NoOptionError:
            self.error('could not find settings/interval in config file, using default: %s' % self.settings['interval'])
        except ValueError, e:
            self.warning('could not load settings/interval config value: %s' % e)
            self.debug('using default value for settings/interval: %s' % self.settings['interval'])

        try:
            self.settings['showbans'] = self.config.getboolean('settings', 'showbans')
            self.debug('loaded settings/showbans: %s' % self.settings['showbans'])
        except NoOptionError:
            self.error('could not find settings/showbans in config file, using default: %s' % self.settings['showbans'])
        except ValueError, e:
            self.warning('could not load settings/showbans config value: %s' % e)
            self.debug('using default value for settings/showbans: %s' % self.settings['showbans'])

        try:
            self.settings['showkicks'] = self.config.getboolean('settings', 'showkicks')
            self.debug('loaded settings/showkicks: %s' % self.settings['showkicks'])
        except NoOptionError:
            self.error('could not find settings/showkicks in config file, using default: %s' % self.settings['showkicks'])
        except ValueError, e:
            self.warning('could not load settings/showkicks config value: %s' % e)
            self.debug('using default value for settings/showkicks: %s' % self.settings['showkicks'])

        try:
            self.settings['showgame'] = self.config.getboolean('settings', 'showgame')
            self.debug('loaded settings/showgame: %s' % self.settings['showgame'])
        except NoOptionError:
            self.error('could not find settings/showgame in config file, using default: %s' % self.settings['showgame'])
        except ValueError, e:
            self.warning('could not load settings/showgame config value: %s' % e)
            self.debug('using default value for settings/showgame: %s' % self.settings['showgame'])

        try:
            self.settings['address'] = self.config.get('connection', 'address')
            self.debug('loaded connection/address: %s' % self.settings['address'])
        except NoOptionError:
            self.error('could not find connection/address in config file: plugin will be disabled')

        try:
            self.settings['port'] = self.config.getint('connection', 'port')
            self.debug('loaded connection/port: %s' % self.settings['port'])
        except NoOptionError:
            self.error('could not find connection/port in config file, using default: %s' % self.settings['port'])
        except ValueError, e:
            self.warning('could not load connection/port config value: %s' % e)
            self.debug('using default value for connection/port: %s' % self.settings['port'])

        try:
            self.settings['maxrate'] = self.config.getint('connection', 'maxrate')
            self.debug('loaded connection/maxrate: %s' % self.settings['maxrate'])
        except NoOptionError:
            self.error('could not find connection/maxrate in config file, using default: %s' % self.settings['maxrate'])
        except ValueError, e:
            self.warning('could not load connection/maxrate config value: %s' % e)
            self.debug('using default value for connection/maxrate: %s' % self.settings['maxrate'])

        try:
            self.settings['channel'] = self.config.get('connection', 'channel')
            self.debug('loaded connection/channel: %s' % self.settings['channel'])
        except NoOptionError:
            self.error('could not find connection/channel in config file: plugin will be disabled')
        except ValueError, e:
            self.error('could not load connection/channel config value: plugin will be disabled: %s' % e)

        try:
            # automatic commands to be performed on connection
            document = minidom.parse(self.config.fileName)
            commands = document.getElementsByTagName('command')
            for node in commands:
                command = None
                for v in node.childNodes:
                    if v.nodeType == v.TEXT_NODE:
                        command = v.data
                        break

                if not command:
                    self.warning('could not parse auto perform command: empty node found')
                    continue

                self.debug('adding command to auto perform: %s' % command)
                self.settings['perform'].append(command)
        except NoSectionError:
            pass

        # if the configuration is not valid, disable the plugin since it won't work anyway
        if not self.settings['nickname'] or not self.settings['address'] or not self.settings['channel']:
            self.warning('plugin configuration incomplete: disabling the plugin')
            self.disable()

    def onStartup(self):
        """
        Initialize plugin settings.
        """
        # register our commands
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                sp = cmd.split('-')
                alias = None
                if len(sp) == 2:
                    cmd, alias = sp

                func = getCmd(self, cmd)
                if func:
                    self.adminPlugin.registerCommand(self, cmd, level, func, alias)

        # get server information
        self.serverinfo['ip'] = self.console.config.get('server', 'public_ip')
        self.serverinfo['port'] = self.console.config.get('server', 'port')

        # register process stop event hooks
        self.registerEventHook(self.console.getEventID('EVT_STOP'), self.onShutdown)
        self.registerEventHook(self.console.getEventID('EVT_EXIT'), self.onShutdown)

        # register necessary events
        self.registerEvent(self.console.getEventID('EVT_CLIENT_SAY'), self.onSay)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_BAN'), self.onBan)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_BAN_TEMP'), self.onBan)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_KICK'), self.onKick)
        self.registerEvent(self.console.getEventID('EVT_GAME_MAP_CHANGE'), self.onMapChange)

        # startup the bot
        self.ircbot = IRCBot(plugin=self)

        # start the bot main loop in a separate thread
        self.pthread = Thread(target=self.ircbot.start)
        self.pthread.setDaemon(True)
        self.pthread.start()

        # notice plugin started
        self.debug('plugin started')

    ####################################################################################################################
    ##                                                                                                                ##
    ##  EVENTS                                                                                                        ##
    ##                                                                                                                ##
    ####################################################################################################################

    def onShutdown(self, event):
        """
        Perform operations when B3 goes offline.
        :param event: An EVT_STOP or EVT_EXIT event.
        """
        self.debug('shutting down irc connection...')
        self.ircbot.disconnect('B3 is going offline')

    def onSay(self, event):
        """
        Perform operations when EVT_CLIENT_SAY is received.
        :param event: An EVT_CLIENT_SAY event.
        """
        client = event.client
        message = event.data.strip()
        if message:
            for name, channel in self.ircbot.channels.iteritems():
                if channel.livechat:
                    # if live chat is enabled on this channel, broadcast the message
                    channel.message('[%sCHAT%s] %s%s%s: %s' % (RED, RESET, ORANGE, client.name, RESET, message))

    def onBan(self, event):
        """
        Perform operations when EVT_CLIENT_BAN or EVT_CLIENT_BAN_TEMP is received.
        :param event: An EVT_CLIENT_BAN or and EVT_CLIENT_BAN_TEMP event.
        """
        admin = event.data['admin']
        if admin is None:
            # do not display B3 autokick/bans otherwise it can
            # mess up the IRC chat (suppose to send notices from a
            # server with TK plugin enabled) and the bot could
            # be G-Lined.
            return

        client = event.client
        reason = event.data['reason']

        message = '[%sBAN%s] %s%s%s banned %s%s%s' % (RED, RESET, ORANGE, admin.name, RESET, ORANGE, client.name, RESET)

        if reason:
            # if there is a reason attached to the ban, append it to the notice
            message += ' [reason : %s%s%s]' % (RED, self.console.stripColors(reason), RESET)

        duration = 'permanent'
        if 'duration' in event.data:
            # if there is a duration convert it
            duration = minutesStr(event.data['duration'])

        # append the duration to the ban notice
        message += ' [duration : %s%s%s]' % (RED, duration, RESET)

        for name, channel in self.ircbot.channels.iteritems():
            if channel.showbans:
                # if showbans is enabled, broadcast the notice
                channel.message(message)

    def onKick(self, event):
        """
        Perform operations when EVT_CLIENT_KICK is received.
        :param event: An EVT_CLIENT_KICK event.
        """
        admin = event.data['admin']
        if admin is None:
            # do not display B3 autokick/bans otherwise it can
            # mess up the IRC chat (suppose to send notices from a
            # server with TK plugin enabled) and the bot could
            # be G-Lined.
            return

        client = event.client
        reason = event.data['reason']

        message = '[%sKICK%s] %s%s%s kicked %s%s%s' % (RED, RESET, ORANGE, admin.name, RESET, ORANGE, client.name, RESET)

        if reason:
            # if there is a reason attached to the ban, append it to the notice
            message += ' [reason : %s%s%s]' % (RED, self.console.stripColors(reason), RESET)

        for name, channel in self.ircbot.channels.iteritems():
            if channel.showkicks:
                # if showkicks is enabled, broadcast the notice
                channel.message(message)

    def onMapChange(self, event):
        """
        Perform operations on EVT_GAME_MAP_CHANGE
        :param event: An EVT_GAME_MAP_CHANGE event.
        """
        if not len(self.console.clients.getList()):
            # do not display information if the server is empty: no one
            # will join an empty server anyway so don't bother
            return

        num = len(self.console.clients.getList())
        maxnum = self.console.getCvar('sv_maxclients').getInt()
        address = self.serverinfo['ip'] + ':' + self.serverinfo['port']
        mapname = event.data['new']

        for name, channel in self.ircbot.channels.iteritems():
            if channel.showgame:
                channel.message('[%sGAME%s] mapname: %s%s%s - players: %s%s%s/%s - join: %s/connect %s' % (BLUE,
                                RESET, GREEN, mapname, RESET, GREEN, num, RESET, maxnum, BLUE, address))

    ####################################################################################################################
    ##                                                                                                                ##
    ##  COMMANDS                                                                                                      ##
    ##                                                                                                                ##
    ####################################################################################################################

    def cmd_livechat(self, data, client, cmd=None):
        """
        [<on|off>] - enable or disable the live chat globally
        """
        if not data:
            # display the current status
            message = '^7livechat:'
            for name, channel in self.ircbot.channels.iteritems():
                message += ' ^7' + channel.name + '^3:'
                message += '^2ON' if channel.livechat else '^1OFF'
            cmd.sayLoudOrPM(client, message)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('^7invalid data, try ^3!^7help livechat')
            return

        if data == 'on':
            for name, channel in self.ircbot.channels.iteritems():
                if not channel.livechat:
                    channel.livechat = True
                    channel.message('livechat: %sON' % GREEN)
            cmd.sayLoudOrPM(client, '^7livechat: ^2ON')
        else:
            for name, channel in self.ircbot.channels.iteritems():
                if channel.livechat:
                    channel.livechat = False
                    channel.message('livechat: %sOFF' % RED)
            cmd.sayLoudOrPM(client, '^7livechat: ^1OFF')

    def cmd_showbans(self, data, client, cmd=None):
        """
        [<on|off>] - enable/disable the ban notifications globally
        """
        if not data:
            # display the current status
            message = '^7showbans:'
            for name, channel in self.ircbot.channels.iteritems():
                message += ' ^7' + channel.name + '^3:'
                message += '^2ON' if channel.showbans else '^1OFF'
            cmd.sayLoudOrPM(client, message)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('^7invalid data, try ^3!^7help showbans')
            return

        if data == 'on':
            for name, channel in self.ircbot.channels.iteritems():
                if not channel.showbans:
                    channel.showbans = True
                    channel.message('showbans: %sON' % GREEN)
            cmd.sayLoudOrPM(client, '^7showbans: ^2ON')
        else:
            for name, channel in self.ircbot.channels.iteritems():
                if channel.showbans:
                    channel.showbans = False
                    channel.message('showbans: %sOFF' % RED)
            cmd.sayLoudOrPM(client, '^7showbans: ^1OFF')

    def cmd_showkicks(self, data, client, cmd=None):
        """
        [<on|off>] - enable/disable the ban notifications globally
        """
        if not data:
            # display the current status
            message = '^7showkicks:'
            for name, channel in self.ircbot.channels.iteritems():
                message += ' ^7' + channel.name + '^3:'
                message += '^2ON' if channel.showkicks else '^1OFF'
            cmd.sayLoudOrPM(client, message)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('^7invalid data, try ^3!^7help showkicks')
            return

        if data == 'on':
            for name, channel in self.ircbot.channels.iteritems():
                if not channel.showkicks:
                    channel.showkicks = True
                    channel.message('showkicks: %sON' % GREEN)
            cmd.sayLoudOrPM(client, '^7showkicks: ^2ON')
        else:
            for name, channel in self.ircbot.channels.iteritems():
                if channel.showkicks:
                    channel.showkicks = False
                    channel.message('showkicks: %sOFF' % RED)
            cmd.sayLoudOrPM(client, '^7showkicks: ^1OFF')

    def cmd_showgame(self, data, client, cmd=None):
        """
        [<on|off>] - enable/disable the game notifications globally
        """
        if not data:
            # display the current status
            message = '^7showgame:'
            for name, channel in self.ircbot.channels.iteritems():
                message += ' ^7' + channel.name + '^3:'
                message += '^2ON' if channel.showgame else '^1OFF'
            cmd.sayLoudOrPM(client, message)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('^7invalid data, try ^3!^7help showgame')
            return

        if data == 'on':
            for name, channel in self.ircbot.channels.iteritems():
                if not channel.showgame:
                    channel.showgame = True
                    channel.message('showgame: %sON' % GREEN)
            cmd.sayLoudOrPM(client, '^7showgame: ^2ON')
        else:
            for name, channel in self.ircbot.channels.iteritems():
                if channel.showgame:
                    channel.showgame = False
                    channel.message('showgame: %sOFF' % RED)
            cmd.sayLoudOrPM(client, '^7showgame: ^1OFF')
