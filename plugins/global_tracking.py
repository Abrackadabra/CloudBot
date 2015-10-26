import asyncio
from cloudbot import hook
from cloudbot.bot import CloudBot
from cloudbot.clients.irc import IrcClient


class Dude(object):
    """
    Mutable! Nick and account may change.

    :type nick: str
    :type username: str
    :type host: str
    :type account: str
    """

    def __init__(self, nick, username, host, account):
        self.nick = nick
        self.username = username
        self.host = host
        self.account = account

    def __repr__(self):
        return '{}!{}@{} as {}'.format(self.nick, self.username, self.host, self.account)

    @staticmethod
    def insert_zwsp(s):
        s = str(s)
        return '{}\u200b{}'.format(s[0], s[1:])

    def __str__(self):
        return '{}!{}@{} as {}'.format(
            Dude.insert_zwsp(self.nick),
            Dude.insert_zwsp(self.username),
            Dude.insert_zwsp(self.host),
            Dude.insert_zwsp(self.account))

    def __eq__(self, other):
        return self.nick == other.nick and self.username == other.username and \
               self.host == other.host and self.account == other.account

    def __hash__(self):
        return hash('{}@{}'.format(self.username, self.host))


class Registry(object):
    """
    chan -> Dude -> set of prefixes
    :type chans: dict[str, dict[Dude, set[str]]]

    :type chanmodes: dict[str, set[str]]
    """

    def __init__(self):
        self.chans = {}
        self.chanmodes = {}

    def process_who(self, chan, who):
        self.chans[chan] = {}
        for i, j in who:
            self.chans[chan][i] = j

    def process_join(self, chan, dude):
        if chan not in self.chans:
            return

        self.chans[chan][dude] = set()
        if chan not in self.chanmodes:
            self.chanmodes[chan] = set()

    def process_part(self, chan, dude):
        if chan not in self.chans:
            return

        if dude in self.chans[chan]:
            del self.chans[chan][dude]

    def process_self_part(self, chan):
        if chan in self.chans:
            del self.chans[chan]
            del self.chanmodes[chan]

    def process_quit(self, nick):
        dude = self.get_dude(nick)
        if dude:
            for i in self.chans.values():
                if dude in i:
                    del i[dude]

    def process_nick(self, old_nick, new_nick):
        dude = self.get_dude(old_nick)
        if dude:
            dude.nick = new_nick

    def process_account_change(self, nick, new_account):
        dude = self.get_dude(nick)
        if dude:
            dude.account = new_account

    def process_mode_change(self, chan, mode):
        plus = '+'
        arg_index = 0

        if chan not in self.chans:
            self.chans[chan] = {}
        if chan not in self.chanmodes:
            self.chanmodes[chan] = set()

        for i in mode[0]:
            if i in '+-':
                plus = i
            elif i in 'oqbv':
                arg_index += 1
                arg = mode[arg_index]

                dude = self.get_dude(arg)
                if dude:
                    if dude not in self.chans[chan]:
                        self.chans[chan][dude] = set()

                    prefix = ''
                    if i == 'v':
                        prefix = '+'
                    elif i == 'o':
                        prefix = '@'

                    if prefix:
                        if plus == '+':
                            self.chans[chan][dude].add(prefix)
                        else:
                            self.chans[chan][dude].remove(prefix)

            elif i in 'ciCgtnjm':
                if plus == '+':
                    self.chanmodes[chan].add(i)
                else:
                    self.chanmodes[chan].remove(i)

    def get_dude(self, nick):
        """
        :type nick: str
        :rtype: Dude
        """
        for i in self.chans.values():
            for j in i:
                if j.nick == nick:
                    return j

    def get_dude_prefixes(self, chan, dude):
        """
        :type dude: Dude
        :rtype: set[str]
        """
        if chan in self.chans:
            if dude in self.chans[chan]:
                return self.chans[chan][dude]

    def chan(self, chan):
        """
        :rtype: set[Dude]
        """
        if chan in self.chans:
            return set(self.chans[chan])

    def mode(self, chan):
        """
        :rtype: set[str]
        """
        if chan in self.chanmodes:
            return self.chanmodes[chan]


@asyncio.coroutine
@hook.irc_raw('004')
def on_connect(bot, conn, event, loop):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """

    conn.memory['registry'] = Registry()

    conn.memory['tracking_who_lock'] = asyncio.Lock(loop=loop)
    conn.memory['tracking_whois_lock'] = asyncio.Lock(loop=loop)
    conn.memory['tracking_mode_lock'] = asyncio.Lock(loop=loop)


@asyncio.coroutine
def get_who(bot, conn, chan):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type chan: str
    """
    who_spec = '%chnufa'

    with (yield from conn.memory['tracking_who_lock']):
        conn.memory['tracking_who_queue'] = asyncio.Queue()
        conn.memory['tracking_who_chan'] = chan

        dudes = []

        conn.send("WHO {} {}".format(chan, who_spec))
        while True:
            item = yield from conn.memory['tracking_who_queue'].get()
            if not item:
                break

            dude, prefixes = item

            if dude.nick == conn.nick:
                continue

            dudes.append((dude, prefixes))

    return dudes


@asyncio.coroutine
@hook.irc_raw("354")
def who_item(bot, conn, event):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """

    chan, username, host, nick, prefix, account = event.irc_paramlist[1:]

    if (
                    not conn.memory.get('tracking_who_lock') or
                    not conn.memory['tracking_who_lock'].locked() or
                    chan != conn.memory['tracking_who_chan']):
        bot.logger.warning('Unexpected who item {}'.format(event.irc_paramlist))
        return

    prefixes = set()
    if '+' in prefix:
        prefixes.add('+')
    if '@' in prefix:
        prefixes.add('@')

    if account == '0':
        account = None

    dude = conn.memory['registry'].get_dude(nick)
    if not dude:
        dude = Dude(nick, username, host, account)

    yield from conn.memory['tracking_who_queue'].put((dude, prefixes))


@asyncio.coroutine
@hook.irc_raw("315")
def who_end(bot, conn, event):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    chan = event.irc_paramlist[1]

    if (
                    not conn.memory.get('tracking_who_lock') or
                    not conn.memory['tracking_who_lock'].locked() or
                    chan != conn.memory['tracking_who_chan']):
        bot.logger.warning('Unexpected who end {}'.format(event.irc_paramlist))
        return

    yield from conn.memory['tracking_who_queue'].put(None)


@asyncio.coroutine
def get_whois(bot, conn, nick):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type nick: str
    """

    with (yield from conn.memory['tracking_whois_lock']):
        conn.memory['tracking_whois_queue'] = asyncio.Queue()
        conn.memory['tracking_whois_nick'] = nick

        conn.send("WHOIS {}".format(nick))

        a = []
        for i in range(4):
            x = yield from conn.memory['tracking_whois_queue'].get()
            if not x:
                break
            a.append(x)

    if len(a) != 3 and len(a) != 4:
        return

    nick, username, host = a[:3]

    account = a[3] if len(a) == 4 else None

    dude = conn.memory['registry'].get_dude(nick)
    if not dude:
        dude = Dude(nick, username, host, account)

    return dude


@asyncio.coroutine
@hook.irc_raw("311")
def whois_item(bot, conn, event):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    nick, username, host = event.irc_paramlist[1:4]

    if (
                    not conn.memory.get('tracking_whois_lock') or
                    not conn.memory['tracking_whois_lock'].locked() or
                    nick != conn.memory['tracking_whois_nick']):
        bot.logger.warning('Unexpected whois item {}'.format(event.irc_paramlist))
        return

    yield from conn.memory['tracking_whois_queue'].put(nick)
    yield from conn.memory['tracking_whois_queue'].put(username)
    yield from conn.memory['tracking_whois_queue'].put(host)


@asyncio.coroutine
@hook.irc_raw("330")
def whois_acc(bot, conn, event):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    nick, account = event.irc_paramlist[1:3]

    if (
                    not conn.memory.get('tracking_whois_lock') or
                    not conn.memory['tracking_whois_lock'].locked() or
                    nick != conn.memory['tracking_whois_nick']):
        bot.logger.warning('Unexpected whois acc {}'.format(event.irc_paramlist))
        return

    yield from conn.memory['tracking_whois_queue'].put(account)


@asyncio.coroutine
@hook.irc_raw("318")
def whois_end(bot, conn, event):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    nick = event.irc_paramlist[1]

    if (
                    not conn.memory.get('tracking_whois_lock') or
                    not conn.memory['tracking_whois_lock'].locked() or
                    nick != conn.memory['tracking_whois_nick']):
        bot.logger.warning('Unexpected whois end {}'.format(event.irc_paramlist))
        return

    yield from conn.memory['tracking_whois_queue'].put(None)


@asyncio.coroutine
def get_mode(bot, conn, chan):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type chan: str
    """
    with (yield from conn.memory['tracking_mode_lock']):
        conn.memory['tracking_mode_future'] = asyncio.Future()
        conn.memory['tracking_mode_chan'] = chan

        conn.send("MODE {}".format(chan))

        mode = yield from conn.memory['tracking_mode_future']
        return mode


@asyncio.coroutine
@hook.irc_raw("324")
def mode_item(bot, conn, chan, event):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type chan: str
    :type event: Event
    """
    chan = event.irc_paramlist[1]

    if (
                    not conn.memory.get('tracking_mode_lock') or
                    not conn.memory['tracking_mode_lock'].locked() or
                    chan != conn.memory['tracking_mode_chan']):
        bot.logger.warning('Unexpected mode item {}'.format(event.irc_paramlist))
        return

    conn.memory['tracking_mode_future'].set_result(event.irc_paramlist[2])


@asyncio.coroutine
@hook.irc_raw("PART")
def tracking_on_part(bot, conn, event, chan, nick):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    registry = conn.memory.get('registry')
    if registry and nick and chan:
        if nick == conn.nick:
            registry.process_self_part(chan)
        else:
            dude = registry.get_dude(nick)

            registry.process_part(chan, dude)


@asyncio.coroutine
@hook.irc_raw("KICK")
def tracking_on_kick(bot, conn, event, chan):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    nick = event.irc_paramlist[1]
    registry = conn.memory.get('registry')
    if registry and nick and chan:
        if nick == conn.nick:
            registry.process_self_part(chan)
        else:
            dude = registry.get_dude(nick)

            registry.process_part(chan, dude)


@asyncio.coroutine
@hook.irc_raw("JOIN")
def tracking_on_join(bot, event, chan, nick, conn, db):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    registry = conn.memory.get('registry')
    if not registry:
        return

    # in case of 'JOIN :<chan>'
    if not chan:
        chan = event.irc_paramlist[0][1:]

    if nick == conn.nick:
        who = yield from get_who(bot, conn, chan)
        registry.process_who(chan, who)

        mode = yield from get_mode(bot, conn, chan)
        registry.process_mode_change(chan, [mode])
    else:
        dude = yield from get_whois(bot, conn, nick)
        registry.process_join(chan, dude)


@asyncio.coroutine
@hook.irc_raw("QUIT")
def tracking_on_quit(bot, conn, event, nick):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    registry = conn.memory.get('registry')
    if registry and nick and nick != conn.nick:
        registry.process_quit(nick)


@asyncio.coroutine
@hook.irc_raw("NICK")
def tracking_on_nick(bot, conn, event, nick):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    old_nick = nick
    new_nick = event.irc_paramlist[0][1:]
    registry = conn.memory.get('registry')
    if registry:
        registry.process_nick(old_nick, new_nick)


@asyncio.coroutine
@hook.irc_raw("MODE")
def tracking_on_mode(bot, conn, event, chan):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    if not chan.startswith('#'):
        return
    registry = conn.memory.get('registry')
    if registry:
        registry.process_mode_change(chan, event.irc_paramlist[1:])


@asyncio.coroutine
@hook.irc_raw("ACCOUNT")
def tracking_on_account(bot, conn, event, nick):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type event: Event
    """
    new_account = event.irc_paramlist[0]
    if new_account == '*':
        new_account = None
    registry = conn.memory.get('registry')
    if registry:
        registry.process_account_change(nick, new_account)


@asyncio.coroutine
@hook.command(autohelp=False)
def show_registry(bot, conn, text, chan):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    """
    r = conn.memory.get('registry')
    s = ', '.join(str(i) for i in r.chan(text))
    for i in range(len(s) // 300 + 1):
        conn.message(chan, 'People: {}'.format(s[i * 300: i * 300 + 300]))
    conn.message(chan, 'Modes: {}'.format(r.mode(text)))
