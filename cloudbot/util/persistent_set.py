class PersistentSet(object):
    def __init__(self, set_name, table):
        self._set_name = set_name
        self._table = table
        self._set = set()

    def load(self, db):
        for row in db.execute(self._table.select().where(self._table.c.set == self._set_name)):
            nick = row['nick']
            self._set.add(nick)

    def add(self, db, x):
        if x in self._set:
            print('{} is already in {}'.format(x, self._set))
            return

        self._set.add(x)
        db.execute(self._table.insert().values(nick=x, set=self._set_name))
        db.commit()

    def update(self, db, x):
        for i in x:
            if i not in self._set:
                self._set.add(i)
                db.execute(self._table.insert().values(nick=i, set=self._set_name))
        db.commit()

    def remove(self, db, x):
        if x not in self._set:
            print('{} not in {}'.format(x, self._set))
            return

        self._set.remove(x)
        db.execute(self._table.delete().where(self._table.c.nick == x)
                   .where(self._table.c.set == self._set_name))
        db.commit()

    def clear(self, db):
        self._set.clear()
        db.execute(self._table.delete().where(self._table.c.set == self._set_name))
        db.commit()

    def set(self):
        return set(self._set)
