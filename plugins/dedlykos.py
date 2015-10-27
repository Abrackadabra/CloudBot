import asyncio
from sqlalchemy import Table, Column, String, UniqueConstraint

from cloudbot import hook
from cloudbot.util import database
from cloudbot.util.persistent_set import PersistentSet

WEREWOLF_CHAN = '##werewolf'
MIRROR_CHAN = '##werewolf-ded'

table = Table(
    'dedlykos_table',
    database.metadata,
    Column('nick', String(200)),
    Column('set', String(200)),
    UniqueConstraint('nick', 'set'))

privileged = PersistentSet('privileged', table)
kicked = PersistentSet('kicked', table)
playing = PersistentSet('playing', table)


@hook.on_start
def load_cache(db):
    """
    :type db: sqlalchemy.orm.Session
    """
    privileged.load(db)
    kicked.load(db)
    playing.load(db)
    playing.clear(db)


@asyncio.coroutine
@hook.periodic(3)
def periodic_checker(bot, db):
    for conn in bot.connections.values():
        yield from check(bot, conn, db)


@asyncio.coroutine
def check(bot, conn, db):
    """
    :type bot: CloudBot
    :type conn: IrcClient
    :type db: sqlalchemy.orm.Session
    """
    registry = conn.memory.get('registry')
    if not registry or not registry.mode(WEREWOLF_CHAN) or not registry.mode(MIRROR_CHAN):
        return

    w = registry.chan(WEREWOLF_CHAN)
    m = registry.chan(MIRROR_CHAN)

    wm = registry.mode(WEREWOLF_CHAN)
    mm = registry.mode(MIRROR_CHAN)

    for j in set(m):
        if not j.account:
            conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Unidentified'))
            return

        if j not in w and 'm' in wm:
            conn.send('KICK {} {} :{}'
                      .format(MIRROR_CHAN, j.nick, 'Not in {}'.format(WEREWOLF_CHAN)))
            return

    for i in w & m:
        wp = registry.get_dude_prefixes(WEREWOLF_CHAN, i)
        mp = registry.get_dude_prefixes(MIRROR_CHAN, i)

        if '+' in wp and '+' not in mp:
            conn.send('MODE {} +v {}'.format(MIRROR_CHAN, i.nick))
            return
        if '+' not in wp and '+' in mp:
            conn.send('MODE {} -v {}'.format(MIRROR_CHAN, i.nick))
            return

    if 'm' in wm:
        if 'i' not in mm:
            conn.send('MODE {} +i'.format(MIRROR_CHAN))

        for i in w:
            wp = registry.get_dude_prefixes(WEREWOLF_CHAN, i)
            for j in m:
                if '+' in wp and i.account == j.account:
                    conn.send('KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Playing ##werewolf'))
                    kicked.add(db, '{} {}'.format(j.nick, i.account))
                    playing.add(db, i.account)
                    return

                if '+' not in wp and i.account == j.account and i.account not in privileged.set():
                    conn.send(
                        'KICK {} {} :{}'.format(MIRROR_CHAN, j.nick, 'Not allowed to spectate'))
                    kicked.add(db, '{} {}'.format(j.nick, j.account))
                    return

            for j in kicked.set():
                nick, account = j.split()
                if i not in m and '+' not in wp and i.nick == nick and i.account == account and \
                                i.account in playing.set():
                    conn.send('INVITE {} {}'.format(i.nick, MIRROR_CHAN))
                    kicked.remove(db, j)
                    playing.remove(db, account)
                    return
    else:
        if 'i' in mm:
            conn.send('MODE {} -i'.format(MIRROR_CHAN))

        for i in w:
            for j in kicked.set():
                nick, account = j.split()
                if i not in m and i.nick == nick and i.account == account:
                    conn.send('INVITE {} {}'.format(i.nick, MIRROR_CHAN))
                    kicked.remove(db, j)
                    return


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def add_spectator(conn, event, bot, nick, reply, db, text):
    nicks = text.split()

    added = []

    for i in nicks:
        if i not in privileged.set():
            privileged.add(db, i)
            added.append(i)

    return '[{}] have been added to spectators.'.format(', '.join(added))


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def remove_spectator(conn, event, bot, nick, reply, db, text):
    nicks = text.split()

    removed = []

    for i in nicks:
        if i in privileged.set():
            privileged.remove(db, i)
            removed.append(i)

    return '[{}] have been removed from spectators.'.format(', '.join(removed))


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def list_spectators(conn, event, bot, nick, reply, db, text):
    return privileged.set()


@asyncio.coroutine
@hook.command(permissions=['botcontrol'])
def a(conn, chan, event, bot, nick, reply, db, loop, text):
    conn.message(chan, '{}'.format(kicked.set()))
    conn.message(chan, '{}'.format(privileged.set()))
