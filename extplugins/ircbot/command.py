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


from copy import copy

LEVEL_USER = 0
LEVEL_VOICED = 1
LEVEL_OPERATOR = 2

class IRCCommand(object):
    """
    Represent a registered command which can be executed by an IRCClient.
    """
    ircbot = None           # IRC BOT object instance
    connection = None       # server connection instance
    func = None             # the function to execute when the command is intercepted
    name = ''               # the name of the command
    help = ''               # command help text
    minlevel = 0            # the minimum required level to execute the command

    prefix = '!'            # prefix for normal command execution
    prefixLoud = '@'        # prefix for loud command execution

    loud = False

    def __init__(self, ircbot, name, minlevel, func):
        """
        Create a new IRCCommand instance.
        :param ircbot: IRC BOT object instance.
        :param name: The command name.
        :param minlevel: The minimum level to be able to use the command.
        :param func: The function to execute when the command is received.
        """
        self.ircbot = ircbot
        self.connection = ircbot.connection
        self.prefix = ircbot.cmdPrefix
        self.prefixLoud = ircbot.cmdPrefixLoud
        self.name = name
        self.minlevel = minlevel
        self.func = func
        self.help = func.__doc__.strip().replace('\r', '').replace('\n', '')

    def canUse(self, client):
        """
        Check whether the given client can use this command.
        :param client: The client who executed the command.
        :return: True if the given client can use the command, False otherwise.
        """
        if self.minlevel == LEVEL_USER:
            # everyone can use the command
            return True

        if self.minlevel == LEVEL_VOICED:
            # only voiced clients and operators can use it
            if client.is_voiced() or client.is_oper():
                return True

        if self.minlevel == LEVEL_OPERATOR:
            # only operators can use it
            if client.is_oper():
                return True

        return False

    def execute(self, client, data, loud=False):
        """
        Execute a command.
        """
        cmd = copy(self)
        cmd.loud = loud
        self.func(client=client, data=data, cmd=cmd)

    def sayLoudOrPM(self, client, message):
        """
        Send a message to a client or to the channel he is in.
        """
        if not self.loud:
            # send the message privately
            client.message(message)
        else:
            # send a public notice in the channel
            client.channel.message(message)

    def __repr__(self):
        """
        String object representation.
        :return: A string representing this object.
        """
        return '%s<%s> : minlevel<%d> : func<%s>' % (self.__class__.__name__, self.name, self.minlevel, self.func.__name__)