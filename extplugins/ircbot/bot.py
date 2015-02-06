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

import b3
import b3.cron
import irc
import irc.bot
import irc.buffer
import irc.client
import irc.connection
import irc.modes
import re
import sys
import socket
import traceback

from b3.clients import Client
from b3.clients import Group
from b3.functions import time2minutes
from b3.functions import minutesStr
from b3.functions import getCmd
from copy import copy
from textwrap import TextWrapper
from time import sleep
from time import time

from irc.client import Event
from irc.client import InvalidCharacters
from irc.client import MessageTooLong
from irc.client import ServerNotConnectedError
from irc.client import NickMask
from irc.client import _rfc_1459_command_regexp
from irc.client import is_channel
from irc.events import numeric
from irc.ctcp import dequote

from ircbot import __version__ as p_version
from ircbot import __author__ as p_author
from ircbot.colors import *
from ircbot.channel import IRCChannel
from ircbot.command import IRCCommand
from ircbot.command import LEVEL_USER
from ircbot.command import LEVEL_OPERATOR

P_ALL = 'all'

class IRCBot(irc.bot.SingleServerIRCBot):

    plugin = None
    adminPlugin = None
    settings = None
    wrapper = None
    cmdPrefix = '!'
    cmdPrefixLoud = '@'

    commands = {}
    crontab = None

    ####################################################################################################################
    ##                                                                                                                ##
    ##   BOT INITIALIZATION                                                                                           ##
    ##                                                                                                                ##
    ####################################################################################################################

    def __init__(self, plugin):
        """
        Object constructor.
        :param plugin: IRC BOT plugin object instance.
        """
        self.plugin = plugin
        self.settings = plugin.settings
        self.adminPlugin = plugin.adminPlugin
        self.cmdPrefix = plugin.adminPlugin.cmdPrefix
        self.cmdPrefixLoud = plugin.adminPlugin.cmdPrefixLoud

        # patch the library
        patch_lib(self)

        # initialize the textwrapper: will be used to split client/channel messages which will result in
        # messages set to the IRC network bigger than 512 bytes (which will raise MessageTooLong exception)
        self.wrapper = TextWrapper(width=400, drop_whitespace=True, break_long_words=True, break_on_hyphens=False)

        self.debug('connecting to network %s:%s...' % (self.settings['address'], self.settings['port']))
        super(IRCBot, self).__init__(server_list=[(self.settings['address'], self.settings['port'])],
                                     nickname=self.settings['nickname'],
                                     realname=self.settings['nickname'])

        if self.settings['maxrate'] > 0:
            # limit commands frequency as specified in the config file
            self.connection.set_rate_limit(self.settings['maxrate'])

        # register IRC commands
        if 'commands-irc' in self.plugin.config.sections():
            for cmd in self.plugin.config.options('commands-irc'):
                minlevel = self.plugin.config.getint('commands-irc', cmd)
                func = getCmd(self, cmd)
                if func:
                    self.register_command(name=cmd, minlevel=minlevel, func=func)

        # initialize crontabs
        self.install_crontab()

    ####################################################################################################################
    ##                                                                                                                ##
    ##   OVERRIDDEN METHODS                                                                                           ##
    ##                                                                                                                ##
    ####################################################################################################################

    def _dispatcher(self, connection, event):
        """
        Dispatch events to on_<event.type> method, if available.
        """
        # if there is a handler defined for this type of event, execute it
        if hasattr(self, 'on_%s' % event.type):
            try:
                self.verbose('handling event: Event<%s>' % event.type)
                method = getattr(self, 'on_%s' % event.type)
                method(connection, event)
            except Exception, msg:
                self.error('could not handle event Event<%s>: %s: %s %s', event.type,
                           msg.__class__.__name__, msg, traceback.extract_tb(sys.exc_info()[2]))

    ####################################################################################################################
    ##                                                                                                                ##
    ##   OVERRIDDEN IRCBOT EVENT HANDLERS                                                                             ##
    ##                                                                                                                ##
    ####################################################################################################################

    def _on_join(self, connection, event):
        """
        Triggered when a user joins a channel.
        :param connection: The current server connection object instance.
        :param event: The event to be handled.
        """
        channel = event.target
        nick = event.source.nick
        # if it's the bot itself joining the channel
        if nick == connection.get_nickname():
            # create a new channel in the channels dictionary
            self.channels[event.target] = IRCChannel(ircbot=self, name=channel)
            self.channels[event.target].showbans = self.settings['showbans']
            self.channels[event.target].showgame = self.settings['showgame']
            self.channels[event.target].showkicks = self.settings['showkicks']

        # add the user to the channel user list
        self.channels[channel].add_user(nick=nick)

    def _on_kick(self, connection, event):
        """
        Triggered when a user is kicked from a channel.
        :param connection: The current server connection object instance.
        :param event: The event to be handled.
        """
        nick = event.arguments[0]
        channel = event.target
        # if it's the bot itself being kicked from a channel
        if nick == connection.get_nickname():
            # delete che channel entry and let the bot rejoin:
            # a new channel entry will be created due to _on_join being called
            del self.channels[channel]
            self.debug('rejoining %s channel upon event kick being received...' % self.settings['channel'])
            self.connection.join(self.settings['channel'])
        else:
            self.channels[channel].remove_user(nick)

    def _on_namreply(self, connection, event):
        """
        Triggered after the BOT joins a channel.
        Will receive the list of connected users.
        :param connection: The current server connection object instance.
        :param event: The event to be handled.
        e.arguments[0] == "@" for secret channels,
                          "*" for private channels,
                          "=" for others (public channels)
        e.arguments[1] == channel
        e.arguments[2] == nick list
        """
        # get our tokens
        ch_type, channel, nick_list = event.arguments

        if channel == '*':
            # User is not in any visible channel
            # http://tools.ietf.org/html/rfc2812#section-3.2.5
            return

        for nick in nick_list.split():
            nick_modes = []
            if nick[0] in self.connection.features.prefix:
                nick_modes.append(self.connection.features.prefix[nick[0]])
                nick = nick[1:]

            # add the user to the channel
            self.channels[channel].add_user(nick)
            for mode in nick_modes:
                # set the user modes for this channel
                self.channels[channel].set_usermode('+%s' % mode, nick)

    def _on_mode(self, connection, event):
        """
        Triggered when channel/user modes change.
        :param connection: The current server connection object instance
        :param event: The event to be handled
        """
        modes = irc.modes.parse_channel_modes(' '.join(event.arguments))
        channel = event.target
        if channel in self.channels:
            if len(event.arguments) == 2:
                # if this is a user mode
                nick = event.arguments[1]
                if self.channels[channel].has_user(nick):
                    for m in modes:
                        mode = '%s%s' % (m[0], m[1])
                        self.channels[channel].set_usermode(mode, nick)
            else:
                # if this is a channel mode
                for m in modes:
                    mode = '%s%s' % (m[0], m[1])
                    self.channels[channel].set_mode(mode)

    ####################################################################################################################
    ##                                                                                                                ##
    ##   IRCBOT EVENT HANDLERS                                                                                        ##
    ##                                                                                                                ##
    ####################################################################################################################

    def on_ping(self, connection, event):
        """
        Triggered when the BOT receive a PING from the server.
        :param connection: The current server connection object instance.
        :param event: The event to be handled.
        """
        # we must send a proper pong reply otherwise the
        # irc network may think we timed out and drop us
        self.connection.pong(event.target)

    def on_nicknameinuse(self, connection, event):
        """
        Triggered when the BOT nickname is already in use.
        :param connection: The current server connection object instance.
        :param event: The event to be handled.
        """
        nick1 = connection.get_nickname()
        nick2 = nick1 + '_'
        self.warning('nickname already in use (%s): renaming to %s...' % (nick1, nick2))
        self.connection.nick(nick2)

    def on_welcome(self, connection, event):
        """
        Triggered when the server welcome the BOT.
        :param connection: The current server connection object instance.
        :param event: The event to be handled.
        """
        self.debug('received welcome from server %s:%s' % (self.settings['address'], self.settings['port']))

        # send the auto perform commands
        for command in self.settings['perform']:
            self.debug('sending auto perform command: %s' % command)
            self.connection.send_raw(command)
            sleep(2) # sleep so the server can process the command

        # join the preconfingured channel
        self.debug('joining channel: %s...' % self.settings['channel'])
        self.connection.join(self.settings['channel'])

    def on_pubmsg(self, connection, event):
        """
        Triggered when the BOT detect a new message being written in a channel he's in.
        :param connection: The current server connection object instance.
        :param event: The event to be handled.
        """
        channel = self.channels[event.target]       # IRCChannel object instance
        nickmask = NickMask(event.source)           # NickMask object instance
        if not channel.has_user(nickmask.nick):
            # patch which prevent AttributeError to be raised when it's not possible to find
            # the user who send a pub message in a channel in the user dict. Look that the most of the
            # times the user would need to join again the channel to issue commands if he's voiced
            # or an operator of the channel since this will not update user flags
            self.warning('could not retrieve client %s on channel %s' % (nickmask.nick, channel.name))
            self.debug('creating new entry for client %s in channel %s' % (nickmask.nick, channel.name))
            channel.add_user(nick=nickmask.nick)

        client = channel.get_user(nickmask.nick)    # IRCClient object instance
        message = event.arguments[0].strip()        # The said message

        if len(message) > 2 and message[:1] in (self.cmdPrefix, self.cmdPrefixLoud):
            prefix, command, data = self.parse_command(message)
            loud = prefix == self.cmdPrefixLoud
            self.on_command(client=client, command=command, data=data, loud=loud)
        else:
            if channel.livechat:
                botname = self.connection.get_nickname()
                if client.nick not in ('Q', 'S', 'D', botname) and not 'warbot' in client.nick:
                    self.verbose('broadcasting chat message on game server: %s: %s' % (client.nick, message))
                    self.plugin.console.say('^7[^1IRC^7] %s: ^3%s' % (client.nick, message))

    ####################################################################################################################
    ##                                                                                                                ##
    ##   CRON EXECUTION                                                                                               ##
    ##                                                                                                                ##
    ####################################################################################################################

    def install_crontab(self):
        """
        Cleanup and create the crontabs.
        """
        self.debug('installing crontab...')
        self.plugin.console.cron - self.crontab
        self.crontab = b3.cron.PluginCronTab(self.plugin, self.cron, 0, '*/%s' % self.settings['interval'])
        self.plugin.console.cron + self.crontab

    def cron(self):
        """
        Scheduled execution.
        """
        self.debug('executing cron...')
        # check that the socket has been actually created: it may happen that the first
        # connection will be delayed and thus this will raise a ServerNotConnectedError
        if self.connection.socket and not self.connection.is_connected():
            self.debug('connection with the server lost: reconnecting...')
            self.connection.reconnect()

    ####################################################################################################################
    ##                                                                                                                ##
    ##   OTHER METHODS                                                                                                ##
    ##                                                                                                                ##
    ####################################################################################################################

    def lookup_client(self, data, client=None):
        """
        Return a list of clients matching the given input.
        :param data: The search handle.
        :return: A list of matches for the given input string.
        """
        # avoid to use getByMagic() here so we can perform a name search also
        # on the storage layer in order to be able to search ppl using partial name
        if re.match(r'^[0-9]+$', data):
            # seems to be a client slot id
            bclient = self.plugin.console.clients.getByCID(data)
            match = [bclient] if bclient else []
        elif re.match(r'^@([0-9]+)$', data):
            # seems to be a client database id
            match = self.plugin.console.clients.getByDB(data)
        else:
            # search by name
            match = self.plugin.console.clients.lookupByName(data)

        if not match:
            # we got no result
            if client:
                # if we got a client in input report the no match
                client.message('no client found matching %s%s' % (RED, data))
            match = None
        elif len(match) > 1:
            # we got multiple results
            if client:
                # if we got a client in input
                # report the multiple matches
                collection = []
                for bclient in match:
                    collection.append('[%s@%s%s] %s' % (ORANGE, bclient.id, RESET, bclient.name))
                client.message('multiple clients matching %s%s%s: %s' % (RED, data, RESET, ', '.join(collection)))
            match = None
        else:
            # we got one result
            match = match[0]

        return match

    def register_command(self, name, minlevel, func):
        """
        Register a command.
        :param name: The command name.
        :param minlevel: The minimum level to be able to execute the command.
        :param func: The command handler.
        """
        # check that the command has not been already registered
        name = name.lower()
        if name in self.commands:
            self.warning('command %s is already registered' % name)
            return

        # check that the supplied handle is actually a callable
        func = getattr(self, func.__name__, None)
        if not callable(func):
            self.error('could not register command %s: invalid handler specified' % name)
            return

        # clamp minlevel so it doesn't mess things up when checking execution
        minlevel = LEVEL_USER if minlevel < LEVEL_USER else minlevel
        minlevel = LEVEL_OPERATOR if minlevel > LEVEL_OPERATOR else minlevel

        # register the command
        self.commands[name] = IRCCommand(ircbot=self, name=name, minlevel=minlevel, func=func)
        self.debug('registered command %r' % self.commands[name])

    @staticmethod
    def parse_command(data):
        """
        Parse the given string extracting command tokens.
        :param data: The string to be tokenized.
        """
        pfx = data[:1]
        cmd = data[1:].split(' ', 1)
        if len(cmd) < 2:
            return pfx, cmd[0], ''
        return pfx, cmd[0], cmd[1]

    @staticmethod
    def get_reason(reason):
        """
        Append a suffix to the given reason which identifies penalties issued from IRC
        :param reason: The reason for the penalty
        :return: A formatted reason with a suffix appended
        """
        if not reason:
            return 'banned by an IRC admin'
        return reason + ' (by an IRC admin)'

    def ban(self, bclient, client, reason=None, keyword=None, duration=None):
        """
        Ban a client from the server.
        :param bclient: The B3 client to ban
        :param client: The IRCClient executing the ban
        :param reason: The reason for this ban
        :param keyword: The keyword used for the ban reason
        :param duration: The duration of the ban
        """
        # protect superadmins from being banned
        bgroup = Group(keyword='superadmin')
        bgroup = self.plugin.console.storage.getGroup(bgroup)
        if bclient.inGroup(bgroup):
            client.message("%s%s%s is a %s%s%s and can't be banned" % (ORANGE, bclient.name, RESET, ORANGE, bgroup.name, RESET))
            return

        # make him a guest again
        bclient.groupBits = 0
        bclient.save()

        # get the correct ban method and use it
        ban = bclient.ban if not duration else bclient.tempban
        ban(reason=self.get_reason(reason), keyword=keyword, duration=duration)

        banmessage = '%s%s%s was banned by %s%s%s' % (ORANGE, bclient.name, RESET, ORANGE, client.nick, RESET)
        if duration:
            # add the duration in a readable format if specified
            banmessage += ' for %s%s%s' % (RED, minutesStr(time2minutes(duration)), RESET)
        if reason:
            # add the ban reason: convert game server color codes for proper printing
            banmessage += ' [reason: %s%s%s]' % (RED, convert_colors(reason), RESET)

        # since the ban produced an event without admin client object, there
        # will be no notice displayed in the IRC channel, so print the message publicly
        client.channel.message(banmessage)

    ####################################################################################################################
    ##                                                                                                                ##
    ##   COMMAND EXECUTION                                                                                            ##
    ##                                                                                                                ##
    ####################################################################################################################

    def on_command(self, client, command, data, loud=False):
        """
        Executed when a command is received.
        :param client: The client who executed the command.
        :param command: The command to be executed.
        :param data: Extra data to be passed to the command.
        :param loud: Boolean value which regulate the command output visibility.
        """
        try:

            # since multiple B3 can be connected to the same channel we have to identify
            # on which B3 the command we parsed needs to be forwarded. To do so we expect
            # to see the BOT name as first argument of the command.
            # 08/12/2014: added 'listen_global' configuration variable which let bots to interact
            # with commands forwarded using the 'all' placeholder as bot name (all the bots will intercept the command)
            split = data.split(' ', 1)
            botname = self.connection.get_nickname().lower()
            placeholder = split[0].lower()
            if self.settings['listen_global']:
                if placeholder != botname and placeholder != P_ALL:
                    return
            else:
                if placeholder != botname:
                    return

            data = ''
            if len(split) > 1:
                data = split[1]

            command = command.lower()
            if not command in self.commands:
                # actually inform the client that the command is not a valid one
                client.message('invalid command: %s%s%s%s' % (ORANGE, self.cmdPrefix, RED, command))
                return

            # get the command object
            cmd = self.commands[command]

            # check for sufficient level
            if not cmd.canUse(client):
                client.message('no sufficient access to command %s%s%s%s' % (ORANGE, cmd.prefix, RED, cmd.name))
                return

            # execute the command
            cmd.execute(client=client, data=data, loud=loud)

        except Exception:
            # send a visual notice to the client
            client.message('could not execute command')
            raise

    ####################################################################################################################
    ##                                                                                                                ##
    ##   IRC COMMANDS                                                                                                 ##
    ##                                                                                                                ##
    ####################################################################################################################

    def cmd_alias(self, client, data, cmd=None):
        """
        <client> - display all the aliases of a client
        """
        if not data:
            client.message('missing data, try %s!%shelp alias' % (ORANGE, RESET))
            return

        bclient = self.lookup_client(data, client)
        if not bclient:
            return

        collection = []
        for a in bclient.aliases:
            collection.append('%s (%sx%s%s)' % (a.alias, GREEN, a.numUsed, RESET))

        # print the aliases
        cmd.sayLoudOrPM(client, '%s%s%s aliases: %s' % (ORANGE, bclient.name, RESET, ', '.join(collection)))

    def cmd_b3(self, client, data, cmd=None):
        """
        - display the B3 version
        """
        cmd.sayLoudOrPM(client, '%s - uptime: [%s%s%s]' % (convert_colors(b3.version),
                                                           minutesStr(self.plugin.console.upTime() / 60.0),
                                                           GREEN, RESET))

    def cmd_ban(self, client, data, cmd=None):
        """
        <client> [reason] - ban a client from the server
        """
        m = self.adminPlugin.parseUserCmd(data)
        if not m:
            client.message('invalid data, try %s!%shelp ban' % (ORANGE, RESET))
            return

        cid, keyword = m
        bclient = self.lookup_client(cid, client)
        if not bclient:
            return

        reason = self.adminPlugin.getReason(keyword)
        duration = self.adminPlugin.config.getDuration('settings', 'ban_duration')
        self.ban(bclient=bclient, client=client, reason=reason, keyword=keyword, duration=duration)

    def cmd_cvar(self, client, data, cmd=None):
        """
        <name> [<value>] - get/set a cvar value
        """
        if not data:
            client.message('missing data, try %s!%shelp cvar' % (ORANGE, RESET))
            return

        try:

            data = data.split(' ', 1)
            if len(data) == 1:
                cvar = self.plugin.console.getCvar(data[0])
                if not cvar:
                    client.message('invalid cvar name supplied')
                    return

                # print the cvar value in the chat
                cmd.sayLoudOrPM(client, 'CVAR [%s%s%s] : [%s%s%s]' % (ORANGE, cvar.name, RESET, ORANGE,
                                                                      convert_colors(cvar.value), RESET))
            else:
                # set the cvar and dissplay the value
                self.plugin.console.setCvar(data[0], data[1])
                cmd.sayLoudOrPM(client, 'CVAR [%s%s%s] : [%s%s%s]' % (ORANGE, data[0], RESET, ORANGE,
                                                                      convert_colors(data[1]), RESET))

        except AttributeError:
            # since not all the games support cvars we need
            # to handle the case where the parser has no getCvar
            # or setCvar method implemented
            cmd.sayLoudOrPM('%s%s%s parser does not support cvar get/set' % (RED, self.plugin.console.game.gameName, RESET))

    def cmd_exec(self, client, data, cmd=None):
        """
        <command> [<params>] - execute a b3 command (this command may have security
        implications since an IRC operator will be recognized by B3 as a superadmin)
        """
        if not data:
            client.message('missing data, try %s!%shelp cvar' % (ORANGE, RESET))
            return

        # append the prefix to the given data so we can use parse_command
        if data[:1] not in (self.adminPlugin.cmdPrefix, self.adminPlugin.cmdPrefixLoud, self.adminPlugin.cmdPrefixBig):
            data = '%s%s' % (self.adminPlugin.cmdPrefix, data)

        prefix, command, args = self.parse_command(data.lower())
        if command not in self.adminPlugin._commands:
            client.message('invalid b3 command supplied: %s%s%s%s' % (ORANGE, self.adminPlugin.cmdPrefix, RESET, command))
            return

        ## MOCK SOME METHODS AND ATTRIBUTES
        original_say = self.plugin.console.say
        original_saybig = self.plugin.console.saybig
        original_message = self.plugin.console.message

        def new_say(text):
            cmd.sayLoudOrPM(client, convert_colors(text))
            original_say(text)

        def new_saybig(text):
            cmd.sayLoudOrPM(client, convert_colors(text))
            original_saybig(text)

        def new_message(target, text):
            client.message(convert_colors(text))

        self.plugin.console.say = new_say
        self.plugin.console.saybig = new_saybig
        self.plugin.console.message = new_message
        new_cmd = copy(cmd)
        new_cmd.sayLoudOrPM_original = new_cmd.sayLoudOrPM
        new_cmd.sayLoudOrPM = lambda x, y: new_cmd.sayLoudOrPM_original(x, self.plugin.console.stripColors(y))

        setattr(client, 'name', client.nick)
        setattr(client, 'exactName', client.nick)
        setattr(client, 'maxLevel', 100)
        setattr(client, 'groupBits', 128)

        try:
            b3_command = self.adminPlugin._commands[command]
            b3_command.func(data=args, client=client, cmd=new_cmd)
            b3_command.time = self.plugin.console.time()
        except Exception, e:
            client.message('could not execute b3 command: %s%s%s%s' % (ORANGE, self.adminPlugin.cmdPrefix, RESET, command))
            self.debug('could not execute B3 command : %s%s : %r' % (self.adminPlugin.cmdPrefix, command, e))
        finally:
            ## UNDO MOCKING
            self.plugin.console.say = original_say
            self.plugin.console.saybig = original_saybig
            self.plugin.console.message = original_message
            delattr(client, 'name')
            delattr(client, 'exactName')
            delattr(client, 'maxLevel')
            delattr(client, 'groupBits')

    def cmd_help(self, client, data, cmd=None):
        """
        [<command>] - display the help text
        """
        if not data:
            commands = []
            for command in self.commands:
                if self.commands[command].canUse(client):
                    commands.append('%s%s' % (self.commands[command].prefix, command))

            if not commands:
                cmd.sayLoudOrPM(client, 'you have no available command')
                return

            commands.sort()
            cmd.sayLoudOrPM(client, 'command list: %s' % (', '.join(commands)))
        else:
            command = data.lower()
            if command not in self.commands:
                cmd.sayLoudOrPM(client, 'command not found: %s%s%s%s' % (ORANGE, cmd.prefix, RED, cmd.name))
                return

            # if the guy has no access
            if not self.commands[command].canUse(client):
                cmd.sayLoudOrPM(client, 'you have no sufficient access to %s%s%s%s' % (ORANGE, cmd.prefix, RED, cmd.name))
                return

            # send the help text
            cmd.sayLoudOrPM(client, '%s%s %s' % (self.commands[command].prefix,
                                                 self.commands[command].name,
                                                 self.commands[command].help))

    def cmd_kick(self, client, data, cmd=None):
        """
        <client> [<reason>] - kick a client from the server
        """
        m = self.adminPlugin.parseUserCmd(data)
        if not m:
            client.message('invalid data, try %s!%shelp kick' % (ORANGE, RESET))
            return

        cid, keyword = m
        bclient = self.lookup_client(cid, client)
        if not bclient:
            return

        if not bclient.cid:
            client.message('%s%s%s is not connected' % (ORANGE, bclient.name, RESET))
            return

        # protect superadmins from being kicked
        bgroup = Group(keyword='superadmin')
        bgroup = self.plugin.console.storage.getGroup(bgroup)
        if bclient.inGroup(bgroup):
            client.message("%s%s%s is a %s%s%s and can't be kicked" % (ORANGE, bclient.name, RESET, ORANGE, bgroup.name, RESET))
            return

        # get the reason and kick the client
        reason = self.adminPlugin.getReason(keyword)
        bclient.kick(reason=self.get_reason(reason), keyword=keyword)

        # compute the feedback message
        message = '%s%s%s was kicked by %s%s%s' % (ORANGE, bclient.name, RESET, ORANGE, client.nick, RESET)
        if reason:
            # add the ban reason: convert game server color codes for proper printing
            message += ' [reason: %s%s%s]' % (RED, convert_colors(reason), RESET)

        # print globally
        client.channel.message(message)

    def cmd_list(self, client, data, cmd=None):
        """
        - display the list of online clients
        """
        bclients = self.plugin.console.clients.getList()
        if not bclients:
            cmd.sayLoudOrPM(client, 'no clients online')
            return

        collection = []
        for bclient in bclients:
            collection.append('[%s%s%s] %s' % (ORANGE, bclient.cid, RESET, bclient.name))

        # send the list of online clients
        cmd.sayLoudOrPM(client, 'online clients: %s' % ', '.join(collection))

    def cmd_listbans(self, client, data, cmd=None):
        """
        <client> - list all the active bans of a client
        """
        if not data:
            client.message('missing data, try %s!%shelp listbans' % (ORANGE, RESET))
            return

        bclient = self.lookup_client(data, client)
        if not bclient:
            return

        # get all the bans and tempbans of this client
        penalties = self.plugin.console.storage.getClientPenalties(bclient, type='Ban') + \
                    self.plugin.console.storage.getClientPenalties(bclient, type='TempBan')

        if not penalties:
            cmd.sayLoudOrPM(client, '%s%s%s has no active bans' % (ORANGE, bclient.name, RESET))
            return

        for p in penalties:
            banstring = 'ban: %s@%s%s' % (ORANGE, p.id, RESET)
            if p.adminId:
                admin = self.plugin.console.storage.getClient(Client(id=p.adminId))
                banstring += ' - issued by: %s%s%s' % (ORANGE, admin.name, RESET)
            if p.reason:
                banstring += ' - reason: %s%s%s' % (ORANGE, self.plugin.console.stripColors(p.reason), RESET)
            if p.timeExpire != -1:
                banstring += ' - expire: %s%s%s' % (RED, minutesStr(((p.timeExpire - time()) / 60)), RESET)
            else:
                banstring += ' - expire: %snever%s' % (RED, RESET)

            cmd.sayLoudOrPM(client, banstring)

    def cmd_livechat(self, client, data, cmd=None):
        """
        [<on|off>] - enable or disable the live chat
        """
        if not data:
            status = GREEN + 'ON' if client.channel.livechat else RED + 'OFF'
            cmd.sayLoudOrPM(client, 'livechat: %s' % status)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('invalid data, try %s!%shelp livechat' % (ORANGE, RESET))
            return

        if data == 'on':
            client.channel.livechat = True
            cmd.sayLoudOrPM(client, 'livechat: %sON' % GREEN)
        else:
            client.channel.livechat = False
            cmd.sayLoudOrPM(client, 'livechat: %sOFF' % RED)

    def cmd_lookup(self, client, data, cmd=None):
        """
        <client> - retrieve information on a client
        """
        if not data:
            client.message('missing data, try %s!%shelp lookup' % (ORANGE, RESET))
            return

        bclient = self.lookup_client(data, client)
        if not bclient:
            return

        pbid = bclient.pbid if bclient.pbid else 'n/a'
        seen = self.plugin.console.stripColors(self.plugin.console.formatTime(bclient.timeEdit))
        group = self.plugin.console.storage.getGroup(Group(level=bclient.maxLevel))

        cmd.sayLoudOrPM(client, 'name: %s%s%s - id: %s@%s%s - pbid: %s%s%s - level: %s%s%s - seen: %s%s' % (GREEN,
                        bclient.name, RESET, GREEN, bclient.id, RESET, GREEN, pbid, RESET, GREEN, group.keyword,
                        RESET, GREEN, seen))

        cmd.sayLoudOrPM(client, 'ip: %s%s%s - guid: %s%s%s - connections: %s%s%s - warnings: %s%s%s - bans: %s%s' % (
                        GREEN, bclient.ip, RESET, GREEN, bclient.guid, RESET, GREEN, bclient.connections, RESET, GREEN,
                        bclient.numWarnings, RESET, GREEN, bclient.numBans))

    def cmd_permban(self, client, data, cmd=None):
        """
        <client> [reason] - permanently ban a client from the server
        """
        m = self.adminPlugin.parseUserCmd(data)
        if not m:
            client.message('invalid data, try %s!%shelp ban' % (ORANGE, RESET))
            return

        cid, keyword = m
        bclient = self.lookup_client(cid, client)
        if not bclient:
            return

        reason = self.adminPlugin.getReason(keyword)
        self.ban(bclient=bclient, client=client, reason=reason, keyword=keyword)

    def cmd_plugins(self, client, data, cmd=None):
        """
        - display the list of plugins loaded
        """
        collection = []

        # get all the available plugins
        plugins = self.plugin.console._plugins.keys()
        plugins.sort()

        for name in plugins:
            # for every plugin retrieve the status
            plugin = self.plugin.console._plugins[name]
            status = GREEN + 'ON' if plugin.isEnabled() else RED + 'OFF'
            collection.append('%s: %s%s' % (name, status, RESET))

        # print the list of plugins
        cmd.sayLoudOrPM(client, 'plugins: %s' % ', '.join(collection))

    def cmd_reconnect(self, client, data, cmd=None):
        """
        - reconnect the BOT to the IRC network
        """
        self.disconnect("rebooting...")
        self.debug('disconnected from IRC network %s' % self.settings['address'])

        # remove everything we stored
        # it will remove the entry from the dict
        # by deleting the reference thus the garbage
        # collector will delete it soon enough
        for key in self.channels:
            del self.channels[key]

        self.plugin.console.cron - self.crontab     # remove the current crontab
        sleep(2)                                    # sleep a bit so the network has time to free our nickname

        # reconnect to the same network
        self.debug('connecting to IRC network %s:%s' % (self.settings['address'], self.settings['port']))
        self.connection.reconnect()
        self.install_crontab()                      # reinstall the crontab

        if self.settings['maxrate'] > 0:
            # limit commands frequency as specified in the config file
            self.connection.set_rate_limit(self.settings['maxrate'])

    def cmd_showbans(self, client, data, cmd=None):
        """
        [<on|off>] - enable/disable the ban notifications
        """
        if not data:
            status = GREEN + 'ON' if client.channel.showbans else RED + 'OFF'
            cmd.sayLoudOrPM(client, 'showbans: %s' % status)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('invalid data, try %s!%shelp showbans' % (ORANGE, RESET))
            return

        if data == 'on':
            client.channel.showbans = True
            cmd.sayLoudOrPM(client, 'showbans: %sON' % GREEN)
        else:
            client.channel.showbans = False
            cmd.sayLoudOrPM(client, 'showbans: %sOFF' % RED)

    def cmd_showkicks(self, client, data, cmd=None):
        """
        [<on|off>] - enable/disable the kick notifications
        """
        if not data:
            status = GREEN + 'ON' if client.channel.showkicks else RED + 'OFF'
            cmd.sayLoudOrPM(client, 'showkicks: %s' % status)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('invalid data, try %s!%shelp showkicks' % (ORANGE, RESET))
            return

        if data == 'on':
            client.channel.showkicks = True
            cmd.sayLoudOrPM(client, 'showkicks: %sON' % GREEN)
        else:
            client.channel.showkicks = False
            cmd.sayLoudOrPM(client, 'showkicks: %sOFF' % RED)

    def cmd_showgame(self, client, data, cmd=None):
        """
        [<on|off>] - enable/disable new game notifications
        """
        if not data:
            status = GREEN + 'ON' if client.channel.showgame else RED + 'OFF'
            cmd.sayLoudOrPM(client, 'showgame: %s' % status)
            return

        data = data.lower()
        if data not in ('on', 'off'):
            client.message('invalid data, try %s!%shelp showgame' % (ORANGE, RESET))
            return

        if data == 'on':
            client.channel.showgame = True
            cmd.sayLoudOrPM(client, 'showgame: %sON' % GREEN)
        else:
            client.channel.showgame = False
            cmd.sayLoudOrPM(client, 'showgame: %sOFF' % RED)

    def cmd_status(self, client, data, cmd=None):
        """
        - display server status information
        """
        num = len(self.plugin.console.clients.getList())
        maxnum = self.plugin.console.getCvar('sv_maxclients').getInt()
        mapname = self.plugin.console.game.mapName
        nextmap = self.plugin.console.getNextMap()

        # print status information
        cmd.sayLoudOrPM(client, 'mapname: %s%s%s - players: %s%s%s/%s - nextmap: %s%s' % (GREEN,
                                 mapname, RESET, GREEN, num, RESET, maxnum, GREEN, nextmap))

    def cmd_tempban(self, client, data, cmd=None):
        """
        <client> <duration> [reason] - tempban a client from the server
        """
        m = self.adminPlugin.parseUserCmd(data)
        if not m:
            client.message('invalid data, try %s!%shelp tempban' % (ORANGE, RESET))
            return

        # lookup the client
        bclient = self.lookup_client(m[0], client)
        if not bclient:
            return

        # validate input data
        m = re.match('^([0-9]+[dwhsm]*)(?:\s(.+))?$', m[1], re.IGNORECASE)
        if not m:
            client.message('invalid data, try %s!%shelp tempban' % (ORANGE, RESET))
            return

        duration, keyword = m.groups()
        duration = time2minutes(duration)
        reason = self.adminPlugin.getReason(keyword)

        self.ban(bclient=bclient, client=client, reason=reason, keyword=keyword, duration=duration)

    def cmd_unban(self, client, data, cmd=None):
        """
        <client> [<reason>] - unban a client from the server
        """
        m = self.adminPlugin.parseUserCmd(data)
        if not m:
            client.message('invalid data, try %s!%shelp unban' % (ORANGE, RESET))
            return

        cid, keyword = m
        bclient = self.lookup_client(cid, client)
        if not bclient:
            return

        reason = self.adminPlugin.getReason(keyword)
        bclient.unban(reason=self.get_reason(reason))

        message = '%s%s%s was un-banned by %s%s%s' % (ORANGE, bclient.name, RESET, ORANGE, client.nick, RESET)
        if reason:
            # add the ban reason: convert game server color codes for proper printing
            message += ' [reason: %s%s%s]' % (RED, convert_colors(reason), RESET)

        # print globally
        client.channel.message(message)

    def cmd_version(self, client, data, cmd=None):
        """
        - display the plugin version
        """
        cmd.sayLoudOrPM(client, 'IRC BOT plugin for BigBrotherBot(%sB3%s) by %s%s%s - version %s%s%s' % (
                        GREEN, RESET, ORANGE, p_author, RESET, ORANGE, p_version, RESET))

    ####################################################################################################################
    ##                                                                                                                ##
    ##   CUSTOM LOGGING METHODS                                                                                       ##
    ##                                                                                                                ##
    ####################################################################################################################

    def critical(self, msg, *args, **kwargs):
        """
        Log a CRITICAL message.
        """
        self.plugin.critical(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        """
        Log a DEBUG message.
        """
        self.plugin.debug(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """
        Log a ERROR message.
        """
        self.plugin.error(msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        """
        Log a FATAL message.
        """
        self.plugin.fatal(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """
        Log a INFO message.
        """
        self.plugin.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """
        Log a WARNING message.
        """
        self.plugin.warning(msg, *args, **kwargs)

    def verbose(self, msg, *args, **kwargs):
        """
        Log a VERBOSE message.
        """
        self.plugin.verbose(msg, *args, **kwargs)

########################################################################################################################
##                                                                                                                    ##
##   PATCH SOME LIBRARY METHODS                                                                                       ##
##                                                                                                                    ##
########################################################################################################################

def send_raw(self, data):
    """
    Send raw string to the server.
    The string will be padded with appropriate CR LF.
    :param data: The string to be sent.
    """
    # the string should not contain any carriage
    # return other than the one added here.
    if '\r' in data or '\n' in data:
        raise InvalidCharacters('carriage returns and line feeds are not allowed: %s' % data)

    # encode data properly
    data = data.encode('utf-8') + b'\r\n'

    # according to the RFC http://tools.ietf.org/html/rfc2812#page-6,
    # clients should not transmit more than 512 bytes.
    if len(data) > 512:
        raise MessageTooLong('message too long: exceed 512 byte RFC limit: http://tools.ietf.org/html/rfc2812#page-6')

    if self.socket is None:
        raise ServerNotConnectedError('socket is not connected')

    # get the correct sender method
    sender = getattr(self.socket, 'write', self.socket.send)

    try:
        # send the data
        sender(data)
    except socket.error:
        # something went wrong, so just disconnect
        self.disconnect('connection lost')

def _process_line(self, line):
    """
    Process a single line read from the socket.
    :param line: The line to be processed.
    """
    source = None
    command = None
    arguments = None

    # if developer mode is enabled this gets logged
    if hasattr(self, 'dev') and callable(self.dev):
        self.dev(line)

    m = _rfc_1459_command_regexp.match(line)
    if m.group("prefix"):
        prefix = m.group("prefix")
        if not self.real_server_name:
            self.real_server_name = prefix
        source = NickMask(prefix)

    if m.group("command"):
        command = m.group("command").lower()

    if m.group("argument"):
        a = m.group("argument").split(" :", 1)
        arguments = a[0].split()
        if len(a) == 2:
            arguments.append(a[1])

    # translate numerics into more readable strings
    command = numeric.get(command, command)

    if command == "nick":
        if source.nick == self.real_nickname:
            self.real_nickname = arguments[0]
    elif command == "welcome":
        # record the nickname in case the client
        # changed nick in a nicknameinuse callback
        self.real_nickname = arguments[0]
    elif command == "featurelist":
        self.features.load(arguments)

    if command in ["privmsg", "notice"]:

        target, message = arguments[0], arguments[1]
        messages = dequote(message)

        if command == "privmsg":
            if is_channel(target):
                command = "pubmsg"
        else:
            command = "privnotice"
            if is_channel(target):
                command = "pubnotice"

        for m in messages:
            if isinstance(m, tuple):
                command = "ctcpreply"
                if command in ["privmsg", "pubmsg"]:
                    command = "ctcp"
                m = list(m)
                event = Event(command, source, target, m)
                self._handle_event(event)
                if command == "ctcp" and m[0] == "ACTION":
                    event = Event("action", source, target, m[1:])
                    self._handle_event(event)
            else:
                event = Event(command, source, target, [m])
                self._handle_event(event)
    else:

        target = None
        if command == "quit":
            arguments = [arguments[0]]
        elif command == "ping":
            target = arguments[0]
        else:
            target = arguments[0]
            arguments = arguments[1:]

        if command == "mode":
            if not is_channel(target):
                command = "umode"

        event = Event(command, source, target, arguments)
        self._handle_event(event)


def patch_lib(bot):
    """
    Patch the library applying changes to methods and attributes.
    :param bot: The IRCBot instance.
    """
    # patch the buffer_class of ServerConnection so it doesn't raise UnicodeError when an input string can't
    # be decoded: LenientDecodingLineBuffer will use UTF8 but fallbacks on LATIN1 if the decode fails: for more
    # information on this matter visit https://bitbucket.org/jaraco/irc/issue/40/unicodedecodeerror
    bot.debug('patching buffer_class: DecodingLineBuffer<%s> : LenientDecodingLineBuffer<%s>' % (id(irc.client.ServerConnection.buffer_class.__class__), id(irc.buffer.LenientDecodingLineBuffer)))
    irc.client.ServerConnection.buffer_class = irc.buffer.LenientDecodingLineBuffer

    # patch the send_raw method sow e can add more info when it raises exceptions
    bot.debug('patching method: irc.client.ServerConnection.send_raw<%s> : send_raw<%s>' % (id(irc.client.ServerConnection.send_raw), id(send_raw)))
    irc.client.ServerConnection.send_raw = send_raw

    # patch the _process_line method so it doesn't generate 'all_raw_messages' events: speed up the bot
    bot.debug('patching method: irc.client.ServerConnection._process_line<%s> : _process_line<%s>' % (id(irc.client.ServerConnection._process_line), id(_process_line)))
    irc.client.ServerConnection._process_line = _process_line

    if bot.settings['dev']:

        def dev(self, msg, *args, **kwargs):
            """
            Log a DEV message.
            """
            bot.debug('[DEV] %s' % msg, *args, **kwargs)

        bot.debug('creating method: irc.client.ServerConnection.dev<%s>' % id(dev))
        irc.client.ServerConnection.dev = dev