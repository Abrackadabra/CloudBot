from sqlalchemy import Table, Column, String, Integer

partial_table = lambda meta: Table(
  'cah',
  meta,
  Column('nick', String, primary_key=True),
  Column('pingif', Integer)
)


class DbAdapter(object):
  def __init__(self, db, table):
    self._db = db
    self._table = table
    self.cache = {}

    self.load_cache()

  def load_cache(self):
    q = self._db.execute(self._table.select())
    self.cache = {row['nick']: row['pingif'] for row in q}

  def write(self, nick, pingif):
    if nick in self.cache:
      self._db.execute(self._table.update().where(self._table.c.nick == nick).values(
        pingif=pingif
      ))
    else:
      self._db.execute(self._table.insert().values(
        nick=nick,
        pingif=pingif
      ))
    self._db.commit()

    self.cache[nick] = pingif
