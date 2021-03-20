from webpie import WPHandler
import json

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



class SQBaseHandler(WPHandler):

    def getDB(self, qdict = {}, dbname = None):
        return self.App.getDB(qdict, dbname)

    def defaultDB(self):
        return self.App.defaultDB()

    def getDBParams(self, dbname = None):
        return self.App.getDBParams(dbn = dbname)

    def check_for_injunction(self, s):
        if s.find(';') >= 0 or s.find("'") >= 0:
            raise ValueError("Possible SQL injunction attempt: \"%s\"" % (s,))

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
