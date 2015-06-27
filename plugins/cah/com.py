class Communicator(object):
  def __init__(self, conn, chan):
    self.conn = conn
    self.chan = chan

  def announce(self, msg):
    msg = msg.replace('`', '\x02')

    while len(msg) > 0:
      self.conn.message(self.chan, msg[:400])
      msg = msg[400:]

  def reply(self, nick, msg):
    self.announce('({}) {}'.format(nick, msg))

  def notice(self, nick, msg):
    msg = msg.replace('`', '\x02')

    while len(msg) > 0:
      self.conn.notice(nick, msg[:400])
      msg = msg[400:]
