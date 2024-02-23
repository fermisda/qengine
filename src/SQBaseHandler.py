from webpie import WPHandler
import json, string, re

Letters = set(string.ascii_letters)
Digits = set(string.digits)
Alphanumeric = Letters | Digits
NameChars = Alphanumeric | set("_.")
NumericChars = set("-.+e") | Digits



def add_data_origin(method):
    def decorated_method(self, req, *params, **args):
        response = method(self, req, *params, **args)
        env = req.environ
        host = env.get("SERVER_NAME")
        port = env.get("SERVER_PORT")
        if host and port:
            response.headers["X-Data-Origin"] = host + ":" + port
        return response
    return decorated_method

class MyJSONEncoder(json.JSONEncoder):

    def default(self, o):
        from datetime import datetime, date, time, timedelta

        if isinstance(o, (datetime, date, time)):
            return str(o)
        elif isinstance(o, timedelta):
            return o.total_seconds()



class SQBaseHandler(WPHandler):

    def getDB(self, qdict = {}, dbname = None):
        return self.App.getDB(qdict, dbname)

    def defaultDB(self):
        return self.App.defaultDB()

    def getDBParams(self, dbname = None):
        return self.App.getDBParams(dbn = dbname)

    def check_for_injection(self, s):
        if "'" in s:
            raise ValueError("Possible SQL injection attempt")

    def validate_name(self, s):
        for c in s:
            if c not in NameChars:
                raise ValueError("Invalid name or namespace")
        words = s.split('.')
        namespace, name = None, s
        if len(words) not in (1,2):
            raise ValueError("Invalid namespace.name")
        if len(words) == 2:
            namespace, name = words
        if namespace and \
                (namespace.startswith("pg_") or namespace == "information_schema"):
            raise ValueError("Invalid namespace")
        return True

    def validate_value(self, s):
        if "'" in s or '\n' in s:    raise ValueError("Invalid value")
        return True

    def validate_number(self, s):
        for c in s:
            if not c in NumericChars: raise ValueError("Invalid number")
        return True

    def formatCSV(self, columns, data, quote_strings):
        def quote(x):
            do_quote = quote_strings
            if isinstance(x, (dict, list)):
                x = json.dumps(x)
                do_quote = True
            if isinstance(x, str):
                if do_quote or (',' in x or '"' in x or '\n' in x):
                    x = x.replace('"', '""')
                    x = '"' + x + '"'
            else:
                x = str(x)
            return x
        colnames = ','.join([quote(cn) for cn in columns])
        #print colnames
        yield '%s\n' % (colnames, )
        for tup in data:
            #output.append('%s\n' % (','.join(['%s' % (x,) for x in tup]),))
            yield ('%s\n' % (','.join([quote(x) for x in tup]),))

    def formatJSON(self, columns, data):
        first_item = True
        encoder = MyJSONEncoder()
        for row in data:
            prefix = "[" if first_item else ","

            data_dict = {cn:v for cn, v in zip(columns, row)}
            yield prefix + encoder.encode(data_dict)
            first_item = False
        if first_item:
            # empty list
            yield "[]"
        else:
            yield "]"

    def mergeLines(self, iter, maxlen=10000):
        buf = []
        total = 0
        for l in iter:
            n = len(l)
            if n + total > maxlen:
                yield bytes(''.join(buf), "utf-8")
                buf = []
                total = 0
            buf.append(l)
            total += n
        if buf:
            yield bytes(''.join(buf), "utf-8")
