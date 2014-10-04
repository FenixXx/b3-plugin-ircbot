IRC BOT Plugin for BigBrotherBot [![BigBrotherBot](http://i.imgur.com/7sljo4G.png)][B3]
================================

Description
-----------

A [BigBrotherBot][B3] plugin which introduces interaction between an IRC channel and your game server. The plugin
implements both IRC and in-game commands and it react on both B3 and IRC events.

Download
--------

Latest version available [here](https://github.com/FenixXx/b3-plugin-ircbot/archive/master.zip).

Requirements
------------

In order for this plugin to work you need to have B3 *v1.10dev* installed (or greater). This plugin make use of some additions
added to this B3 version since the 13th July 2014: to make sure you have the correct B3 version, download the last development
snapshot from [here](https://github.com/BigBrotherBot/big-brother-bot/archive/release-1.10.zip). I will not introduce backward
compatibility with B3 *1.9.x* version since it would require too many changes in the plugin code.

Installation
------------

* install python [irc](https://bitbucket.org/jaraco/irc/overview) library by following instructions
* copy the `ircbot` folder into `b3/extplugins`
* copy the `plugin_ircbot.xml` file in `b3/extplugins/conf`
* add to the `plugins` section of your `b3.xml` config file:

  ```xml
  <plugin name="ircbot" config="@b3/extplugins/conf/plugin_ircbot.xml" />
  ```

IRC commands
------------

Since there is the possibility of connecting multiple BOTs to the same IRC channel, every command launched from IRC must
specify as first parameter the BOT name. Every IRC BOT will try to match such parameter with the BOT name itself to see
if a command typed in the chat is directed to him or not: when this match fails the BOT will simply ignore the command.

* **!alias &lt;botname&gt; &lt;client&gt;** `display all the aliases of a client`
* **!ban &lt;botname&gt; &lt;client&gt; [&lt;reason&gt;]** `ban a client`
* **!b3 &lt;botname&gt;** `display the B3 version`
* **!cvar &lt;botname&gt; &lt;name&gt; [&lt;value&gt;]** `set/get a cvar value`
* **!help &lt;botname&gt; [&lt;command&gt;]** `display the help text`
* **!kick &lt;botname&gt; &lt;client&gt; [&lt;reason&gt;]** `kick a client`
* **!list &lt;botname&gt;** `display the list of online clients`
* **!listbans &lt;client&gt;** `list all the active bans of a given client`
* **!livechat &lt;botname&gt; [&lt;on|off&gt;]** `enable/disable the livechat`
* **!lookup &lt;botname&gt; &lt;client&gt;** `retrieve information on a client`
* **!permban &lt;botname&gt; &lt;client&gt; [&lt;reason&gt;]** `permban a client`
* **!plugins &lt;botname&gt;** `display a list of plugins loaded`
* **!reconnect &lt;botname&gt;** `reconnect to the IRC network`
* **!showbans &lt;botname&gt; [&lt;on|off&gt;]** `enable/disable the ban notifications`
* **!showkicks &lt;botname&gt; [&lt;on|off&gt;]** `enable/disable the kick notifications`
* **!showgame &lt;botname&gt; [&lt;on|off&gt;]** `enable/disable new game notifications`
* **!status &lt;botname&gt;** `display server status information`
* **!tempban &lt;botname&gt; &lt;client&gt; &lt;duration&gt; [&lt;reason&gt;]** `tempban a client`
* **!unban &lt;botname&gt; &lt;client&gt; [&lt;reason&gt;]** `un-ban a client`
* **!version &lt;botname&gt;** `display the plugin version`

B3 commands
-----------

* **!livechat [&lt;on|off&gt;]** `enable/disable the livechat`
* **!showbans [&lt;on|off&gt;]** `enable/disable the ban notifications`
* **!showkicks [&lt;on|off&gt;]** `enable/disable the kick notifications`
* **!showgame [&lt;on|off&gt;]** `enable/disable new game notifications`

B3 events
---------

The plugin make use of the folowing events to display notices in the IRC channel:

* `EVT_CLIENT_BAN` and `EVT_CLIENT_BAN_TEMP` : send a notice upon admin bans
* `EVT_CLIENT_KICK` : send a notice upon admin kicks
* `EVT_GAME_MAP_CHANGE` : send a notice when a new game start

Support
-------

If you have found a bug or have a suggestion for this plugin, please report it on the [B3 forums][Support].

[B3]: http://www.bigbrotherbot.net/ "BigBrotherBot (B3)"
[Support]: http://forum.bigbrotherbot.net/plugins-by-fenix/ircbot-plugin/ "Support topic on the B3 forums"
