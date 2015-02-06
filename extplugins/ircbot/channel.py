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

from irc.bot import Channel

from ircbot.colors import RESET
from ircbot.client import IRCClient
from ircbot.colors import convert_colors

class IRCChannel(Channel):
    """
    A class for keeping information about an IRC channel.
    Inherits from irc.bot.Channel providing some more functionalities.
    """
    ircbot = None       # bot instance
    plugin = None       # ircbot plugin instance
    connection = None   # server connection instance
    name = None         # channel name

    modedict = {}       # will hold dict references according the channel modes

    livechat = False    # live chat streaming
    showbans = True     # display admin bans whenever the event is raised
    showkicks = True    # display admin kicks whenever the event is raised
    showgame = True     # will display information when a new game is starting on the server

    def __init__(self, ircbot, name):
        """
        Create a new IRCChannel instance.
        :param ircbot: The IRC BOT object instance.
        :param name: The channel name.
        """
        Channel.__init__(self)

        self.ircbot = ircbot
        self.plugin = ircbot.plugin
        self.connection = ircbot.connection
        self.name = name

        # this will overwrite the modes attribute set
        # in the Channel constructor: was a dict but we
        # don't need to associate keys to values
        self.modes = []

        self.modedict = {
            'o': self.operdict,
            'v': self.voiceddict,
            'q': self.ownerdict,
            'h': self.halfopdict
        }

    ####################################################################################################################
    ##                                                                                                                ##
    ##  USER RELATED METHODS                                                                                          ##
    ##                                                                                                                ##
    ####################################################################################################################

    def users(self):
        """
        Returns an unsorted list of the channel's users.
        :return: A list of IRCClient objects.
        """
        return self.userdict.items()

    def opers(self):
        """
        Returns an unsorted list of the channel's operators.
        :return: A list of IRCClient objects.
        """
        return self.operdict.items()

    def voiced(self):
        """
        Returns an unsorted list of the persons that have voice mode set in the channel.
        :return: A list of IRCClient objects.
        """
        return self.voiceddict.items()

    def owners(self):
        """
        Returns an unsorted list of the channel's owners.
        :return: A list of IRCClient objects.
        """
        return self.ownerdict.items()

    def halfops(self):
        """
        Returns an unsorted list of the channel's half-operators.
        :return: A list of IRCClient objects.
        """
        return self.halfopdict.items()

    def has_user(self, client):
        """
        Check whether the channel has a user.
        :return: True if the user is in the channel, False otherwise.
        """
        nick = client  # assuming a string
        if isinstance(client, IRCClient):
            nick = client.nick
        return nick in self.userdict

    def is_oper(self, client):
        """
        Check whether a user has operator status in the channel.
        :return: True if the user has operator status in the channel, False otherwise.
        """
        nick = client  # assuming a string
        if isinstance(client, IRCClient):
            nick = client.nick
        return nick in self.operdict

    def is_voiced(self, client):
        """
        Check whether a user has voice mode set in the channel.
        :return: True if the user has voice status set in the channel, False otherwise.
        """
        nick = client  # assuming a string
        if isinstance(client, IRCClient):
            nick = client.nick
        return nick in self.voiceddict

    def is_owner(self, client):
        """
        Check whether a user has owner status in the channel.
        :return: True if the user has owner status set in the channel, False otherwise.
        """
        nick = client  # assuming a string
        if isinstance(client, IRCClient):
            nick = client.nick
        return nick in self.ownerdict

    def is_halfop(self, client):
        """
        Check whether a user has half-operator status in the channel.
        :return: True if the user has half-operator status set in the channel, False otherwise.
        """
        nick = client  # assuming a string
        if isinstance(client, IRCClient):
            nick = client.nick
        return nick in self.halfopdict

    def add_user(self, nick):
        """
        Add a new user to the channel.
        :param nick: The client nickname.
        """
        # if this user is already in this channel
        if self.has_user(nick):
            return

        # create a new IRCClient instance and store it in the user dict
        client = IRCClient(ircbot=self.ircbot, channel=self, nick=nick)
        self.ircbot.debug('adding client %s on channel %s: %r' % (nick, self.name, client))
        self.userdict[nick] = client

    def get_user(self, client):
        """
        Return an IRCClient object matching the given parameter.
        :param client: The client nickname or the IRCClient object itself.
        :return: The IRCClient object of the client or None.
        """
        nick = client  # assuming a string
        if isinstance(client, IRCClient):
            nick = client.nick

        # get it from the users dict
        if nick in self.userdict:
            return self.userdict[client]

        return None

    def remove_user(self, client):
        """
        Remove a user from a channel.
        :param client: The client to remove.
        """
        nick = client  # assuming a string
        if isinstance(client, IRCClient):
            nick = client.nick

        self.ircbot.debug('removing client %s from channel %s: %r' % (nick, self.name, client))
        for d in self.userdict, self.operdict, self.voiceddict:
            if nick in d:
                del d[nick]

    def change_nick(self, before, after):
        """
        Update the nickname of a client.
        :param before: The old nickname.
        :param after: The new nickname.
        """
        # update in the channel users dict
        self.ircbot.debug('updating nick for client %s on channel %s: %s' % (before, self.name, after))
        self.userdict[after] = self.userdict.pop(before)
        self.userdict[after].nick = after

        # update in the operators dict
        if before in self.operdict:
            self.operdict[after] = self.operdict.pop(before)
            self.operdict[after].nick = after

        # update in the voiced dict
        if before in self.voiceddict:
            self.voiceddict[after] = self.voiceddict.pop(before)
            self.voiceddict[after].nick = after

    def set_userdetails(self, nick, client):
        """
        Update user information.
        :param nick: The user nickname.
        :param client: The IRCClient instance.
        """
        # if not the correct class instance
        if not isinstance(client, IRCClient):
            raise AttributeError('client parameter must be instance of IRCClient')

        self.ircbot.debug('updating client %s data on channel %s: %r' % (nick, self.name, client))
        self.userdict[nick] = client

        # update in operators dict
        if nick in self.operdict:
            self.operdict[nick] = client

        # update in voiced dict
        if nick in self.voiceddict:
            self.voiceddict[nick] = client

    def set_usermode(self, mode, client):
        """
        Set a user mode.
        :param mode: The client mode
        :param client: The client whose mode needs to be updated
        """
        if mode[0] not in ('-', '+') or not mode[1] in self.modedict:
            raise AttributeError('unsupported client mode given: %s' % mode)

        # if not an IRCClient instance, get the corresponding one
        if not isinstance(client, IRCClient):
            client = self.userdict[client]

        self.ircbot.debug('setting mode %s on channel %s for client %s' % (mode, self.name, client.nick))
        d = self.modedict[mode[1]]
        if mode[0] == '+' and not client.nick in d:
            d[client.nick] = client
        elif mode[0] == '-' and client.nick in d:
            del d[client.nick]

    ####################################################################################################################
    ##                                                                                                                ##
    ##   CHANNEL MODE METHODS                                                                                         ##
    ##                                                                                                                ##
    ####################################################################################################################

    def set_mode(self, mode, *args, **kwargs):
        """
        Set mode on the channel.
        :param mode: The channel mode
        """
        if mode[0] not in ('-', '+'):
            raise AttributeError('unsupported channel mode given: %s' % mode)

        self.ircbot.debug('setting mode %s on channel %s' % (mode, self.name))
        if mode[0] == '+' and mode[1] not in self.modes:
            self.modes.append(mode[1])
        elif mode[0] == '-' and mode[1] in self.modes:
            del self.modes[mode[1]]

    def clear_mode(self, mode, *args, **kwargs):
        """
        We do not use this: check set_mode() and set_clientmode().
        """
        pass

    def has_mode(self, mode):
        """
        Check whether the channel has the given mode set.
        :param mode: The mode to be matched
        :return: True if the channel has the given mode set, False otherwise
        """
        return mode in self.modes

    def is_moderated(self):
        """
        Check whethet the channel is moderated.
        :return: True is the channel is moderated, False otherwise
        """
        return self.has_mode('m')

    def is_secret(self):
        """
        Check whether the channel is secret.
        :return: True if the channel is secret, False otherwise
        """
        return self.has_mode('s')

    def is_protected(self):
        """
        Check whether the channel is protected.
        :return: True if the channel is protected, False otherwise
        """
        return self.has_mode('p')

    def has_topic_lock(self):
        """
        Check whether the channel has topic locked.
        :return: True if the channel has topic locked, False otherwise
        """
        return self.has_mode('t')

    def is_invite_only(self):
        """
        Check if the channel can be joined only on invite.
        :return: True if the channel has invite only set, False otherwise
        """
        return self.has_mode('i')

    def has_allow_external_messages(self):
        """
        Check whether the channel allows external messages.
        :return: True if the channel allows external messages, False otherwise
        """
        return self.has_mode('n')

    def has_limit(self):
        """
        Check whether the channel has user limit set.
        :return: True if the channel has user limit set, False otherwise
        """
        return self.has_mode('l')

    def has_key(self):
        """
        Check whether the channel is key protected.
        :return:
        """
        return self.has_mode('k')

    def limit(self):
        """
        We do not use this one
        """
        pass

    ####################################################################################################################
    ##                                                                                                                ##
    ##  USER RELATED METHODS                                                                                          ##
    ##                                                                                                                ##
    ####################################################################################################################

    def message(self, message):
        """
        Send a message publicly in a channel.
        :param message: The message to be sent.
        """
        message = '%s%s' % (RESET, message)
        for msg in self.ircbot.wrapper.wrap(message):
            self.connection.privmsg(self.name, convert_colors(msg))