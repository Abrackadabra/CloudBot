class Communicator(object):
  BOLD_MARKER = '∆'

  def __init__(self, conn, chan):
    self.conn = conn
    self.chan = chan

  def announce(self, msg):
    msg = msg.replace(self.BOLD_MARKER, '\x02')

    for i in self.split_msg(msg):
      self.conn.message(self.chan, i)

  def reply(self, nick, msg):
    self.announce('({}) {}'.format(nick, msg))

  def notice(self, nick, msg):
    msg = msg.replace(self.BOLD_MARKER, '\x02')

    for i in self.split_msg(msg):
      self.conn.notice(nick, i)

  MAX_SPLIT_LENGTH = 400
  SPLIT_LEEWAY = 100
  SPLIT_STRINGS = [', ', '] ', ' ']

  def split_msg(self, s):
    while s:
      piece, new_s = self.cut_msg(s)
      yield piece
      s = new_s

  def cut_msg(self, s):
    if len(s) < self.MAX_SPLIT_LENGTH:
      return s, None

    for split_string in self.SPLIT_STRINGS:
      x = s[self.MAX_SPLIT_LENGTH - self.SPLIT_LEEWAY: self.MAX_SPLIT_LENGTH]
      i = x.rfind(split_string)
      if i != -1:
        j = i + len(split_string) + self.MAX_SPLIT_LENGTH - self.SPLIT_LEEWAY
        return s[:j], s[j:]

    return s[:self.MAX_SPLIT_LENGTH], s[self.MAX_SPLIT_LENGTH:]
