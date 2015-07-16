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

NORMAL = "\x0F"
BOLD = "\x02"
ITALIC = "\x1d"
UNDERLINE = "\x1f"
RESET = "\x0F\x02"

BLACK = "\x0301"
BLUE = "\x0302"
GREEN = "\x0303"
RED = "\x0304"
BROWN = "\x0305"
PURPLE = "\x0306"
ORANGE = "\x0307"
YELLOW = "\x0308"
LIME = "\x0309"
TEAL = "\x0310"
CYAN = "\x0311"
ROYAL = "\x0312"
MAGENTA = "\x0313"
DARK_GRAY = "\x0314"
LIGHT_GRAY = "\x0315"
WHITE = "\x0316"

# map Q3 color codes to IRC ones:
# used to perform string replacement.
# this actually follow the color codes
# specified in urban terror 4.2 so it may
# work differently in other games
colormap = {
    0: BLACK,
    1: RED,
    2: GREEN,
    3: YELLOW,
    4: BLUE,
    5: CYAN,
    6: MAGENTA,
    7: WHITE,
    8: ORANGE,
    9: DARK_GRAY,
}


def convert_colors(message):
    """
    Convert Q3 color codes with IRC ones.
    :param message: The string on which to operate.
    """
    for i in range(0, 10):
        # loop form 0 to 9 and replace all the codes
        message = message.replace('^%d' % i, colormap[i])
    return '%s%s%s' % (RESET, message, RESET)
