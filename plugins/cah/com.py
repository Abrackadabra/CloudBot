class Communicator(object):
  def __init__(self, conn, chan):
    self.reply = lambda nick, msg: conn.message(chan, '({}) {}'.format(nick, msg))
    self.announce = lambda msg: conn.message(chan, msg)
    self.notice = lambda nick, msg: conn.notice(nick, msg)
