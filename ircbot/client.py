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

from .colors import RESET
from .colors import convert_colors

class IRCClient(object):
    """
    Represent a client connected to the IRC channel.
    This class provides some of the attributes and methods of b3.clients.Client
    in order to create a communication bridge between B3 and IRC clients.
    """
    ircbot = None       # bot instance
    plugin = None       # ircbot plugin instance
    connection = None   # server connection instance
    channel = None      # the channel the client is in
    nick = None         # the client nickname

    ####################################################################################################################
    #                                                                                                                  #
    #   OBJECT INIT                                                                                                    #
    #                                                                                                                  #
    ####################################################################################################################

    def __init__(self, ircbot, channel, nick):
        """
        Create a new IRCClient instance.
        :param ircbot: The IRC BOT object instance.
        :param channel: The channel the client is in.
        :param nick: The client nickname.
        """
        self.ircbot = ircbot
        self.plugin = ircbot.plugin
        self.connection = ircbot.connection
        self.channel = channel
        self.nick = nick

    ####################################################################################################################
    #                                                                                                                  #
    #   OTHER METHODS                                                                                                  #
    #                                                                                                                  #
    ####################################################################################################################

    def is_oper(self):
        """
        Check whether this client has operator status in the channel he's in.
        :return: True if the client has operator status, False otherwise.
        """
        return self.channel.is_oper(self)

    def is_voiced(self):
        """
        Check whether this client has voice status in the channel he's in.
        :return: True if the client has voice status, False otherwise.
        """
        return self.channel.is_voiced(self)

    def is_halfop(self):
        """
        Check whether this client has half operator status in the channel he's in.
        :return: True if the client has half operator status, False otherwise.
        """
        return self.channel.is_halfop(self)

    def message(self, message):
        """
        Send a private message to a client.
        :param message: The message to be forwarded.
        """
        message = '%s%s' % (RESET, message)
        for msg in self.ircbot.wrapper.wrap(message):
            self.connection.notice(self.nick, convert_colors(msg))

    ####################################################################################################################
    #                                                                                                                  #
    #   OBJECT REPRESENTATION                                                                                          #
    #                                                                                                                  #
    ####################################################################################################################

    def __repr__(self):
        """
        String object representation.
        :return: A string representing this object.
        """
        return '%s<%s>' % (self.__class__.__name__, self.nick)