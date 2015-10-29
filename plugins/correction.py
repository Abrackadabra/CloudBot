import multiprocessing
import re
import sre_constants

from cloudbot import hook

from cloudbot.util.formatting import ireplace

correction_re = re.compile(r"^[sS]/(.*/.*(?:/[igx]{,4})?)\S*$")


def check(q, nick, find, replace, msg):
    try:
        if re.findall(find, msg, re.IGNORECASE):
            if "\x01ACTION" in msg:
                msg = msg.replace("\x01ACTION", "").replace("\x01", "")
                replace_bold = "\x02" + replace + "\x02"
                mod_msg = re.sub(find, replace_bold, msg, flags=re.IGNORECASE)
                q.put("Correction, * {} {}".format(nick, mod_msg))
            else:
                replace_bold = "\x02" + replace + "\x02"
                mod_msg = re.sub(find, replace_bold, msg, flags=re.IGNORECASE)
                q.put("Correction, <{}> {}".format(nick, mod_msg))
    except sre_constants.error:
        # bad regex
        pass


@hook.regex(correction_re)
def correction(match, conn, chan, message):
    """
    :type match: re.__Match
    :type conn: cloudbot.client.Client
    :type chan: str
    """
    groups = [b.replace("\/", "/") for b in re.split(r"(?<!\\)/", match.groups()[0])]
    find = groups[0]
    replace = groups[1]

    for item in conn.history[chan].__reversed__():
        nick, timestamp, msg = item
        if correction_re.match(msg):
            # don't correct corrections, it gets really confusing
            continue

        try:
            q = multiprocessing.Queue()
            p = multiprocessing.Process(target=check, args=[q, nick, find, replace, msg])
            p.start()
            p.join(timeout=1)
            if p.is_alive():
                message('ಠ_ಠ')
                p.terminate()
                return
            else:
                if not q.empty():
                    msg = q.get()
                    message(msg)
                    return
        except sre_constants.error:
            # bad regex
            pass
