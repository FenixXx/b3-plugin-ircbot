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

from ircbot.colors import colormap
from ircbot.colors import RESET

def convert_colors(message):
    """
    Convert Q3 color codes with IRC ones.
    :param message: The string on whifh to operate.
    """
    for i in range(0, 10):
        # loop form 0 to 9 and replace all the codes
        message = message.replace('^%d' % i, colormap[i])
    return '%s%s%s' % (RESET, message, RESET)