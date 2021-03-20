from SQBaseHandler import SQBaseHandler, add_data_origin
from InfoHandler import InfoHandler
from urllib.parse import unquote
import time, sys, json

from webpie import WPHandler, Response, webmethod

PY2 = sys.version_info < (3,)
PY3 = sys.version_info >= (3,)


class SimpleQueryHandler(SQBaseHandler):

    def __init__(self, *params):
        SQBaseHandler.__init__(self, *params)
        self.I = InfoHandler(*params)

            
    def cursorIterator(self, c):
        tup = c.fetchone()
        while tup:
            yield tup
            tup = c.fetchone()

    def JSONPath(self, column):
        if '.' in column:
            # JSON data path
            cwords = column.split('.')
            path = cwords[0]
            for cw in cwords[1:]:
                path += "->'%s'" % (cw,)
            column = path    
        return column

    Ops = {
        'lt':   '<',
        'le':   '<=',
        'eq':   '=',
        'ge':   '>=',
        'gt':   '>',
        'ne':   '!='
    }

    @webmethod()
    @add_data_origin        
    def version(self, req, relpath, **args):
        return Response(self.App.Version, content_type="text/plain")
        
    @webmethod()
    @add_data_origin        
    def env(self, req, relpath, **args):
        text = ''.join(["%s = %s\n" % (k, v) for k, v in sorted(req.environ.items())])
        return Response(text, content_type="text/plain")

    def buildSQL(self, req):
        if req.params.get('t'):
            table = req.params["t"]
            self.check_for_injunction(table)
        elif req.params.get('F'):
            function = req.params["F"]
            self.check_for_injunction(function)
            args = []
            for a in req.params.getall('a'):
                self.check_for_injunction(a)
                args.append("'%s'" % (a,))
            table = "%s(%s)" % (function, ','.join(args))
        else:
            raise ValueError("Either table name or function name must be specified")
            
        columns = req.params.get('c', None)
        if columns:
            columns = columns.split(',')
        else:
            columns = []
        
        aliases = columns[:]
        if not columns: columns = ['*']
        for c in columns:
            self.check_for_injunction(c)
                
        columns = [self.JSONPath(c) for c in columns]
        
        sql = "select %s from %s " % (','.join(columns), table)
        
        wheres = []
        
        for w in req.params.getall('w'):
            q = unquote(w)
            words = q.split(':', 1)
            c = words[0]
            rest = words[1]
            self.check_for_injunction(c)
            c = self.JSONPath(c)
            words = rest.split(':', 1)
            if len(words) == 2 and words[0] in self.Ops:
                sign = self.Ops[words[0]]
                v = words[1]
            else:
                sign = '='
                v = rest

                        
            self.check_for_injunction(v)
            wheres.append("%s %s '%s'" % (c, sign, v))
        if wheres:
            sql += "where %s " % (' and '.join(wheres))
            
        orders = []
        for o in req.params.getall('o'):
            self.check_for_injunction(o)
            for o in o.split(','):
                o = o.strip()
                desc = o[0] == '-'
                if desc:
                    orders.append(o[1:] + ' desc')
                else:
                    orders.append(o)
        if orders:
            sql += "order by " + ','.join(orders)
            
        limit = req.params.get('l', None)
        if limit:
            self.check_for_injunction(limit)
            sql  += " limit %s " % (limit,)
        sql = str(sql)
        return sql, aliases   

    @webmethod()
    @add_data_origin        
    def query(self, req, relpath, dbname=None, x='no', f='csv', t=None, F=None, cache_ttl=None, **args):
        # args:
        # dbname - optional
        # t=table
        # w=column:value[&...]
        # w=column:<sign>:value[&...]  sign=lt|le|eq|ge|gt|ne
        # c=column[&...] or c=col1,col2,col3
        # l=limit
        # f=format (csv, xml) - ignored for now, always csv
        # o=col1,col2,-col3
        # x=no - do not cache
        #---- function call ----
        # F=function name
        # a=arg1&a=arg2...
        #
        conn = self.App.connect(dbname)
        #print "Using connection %x" % (id(conn),)
        c = conn.cursor()
        table_or_func = t or F
        sql, columns = self.buildSQL(req)
        #print "sql=<%s>" % (sql,)
        #print "columns=", columns
        data = None
        cache_control = x
        query = req.query_string
        if cache_control == 'clear':
            self.App.clear_cache()
        use_cache = cache_control != "no" \
            and self.App.UseCache \
            and self.getDBParams().get("use_cache", "no") == "yes"
        if use_cache:
            tup = self.App.get_cache(query)
            #print "No cache: %s" % (self.Cache.Cache,)
            if tup:
                columns, data = tup
        if data is None:
            #print "Not in cache: "+query
            #print "sql: <%s>" % (sql,)
            c.execute(sql)
            if not columns: columns = [x[0] for x in c.description]
            data = self.cursorIterator(c)
            if use_cache:
                data = list(data)
                self.App.put_cache(query, (columns, data))
        else:
            pass
        quote_strings = self.getDBParams().get("quote_strings", False)
        output = self.mergeLines(self.formatCSV(columns, data, quote_strings))
        resp = Response(app_iter = output, content_type = 'text/csv')
        
        if cache_ttl is None:
            cache_ttl = self.App.cacheTTL(dbname, table_or_func) or 0
        else:
            cache_ttl = int(cache_ttl)
        resp.cache_expires(cache_ttl)
        return resp            
        
    @webmethod()
    @add_data_origin        
    def flush(self, req, relpath, **args):
        self.App.clear_cache()
        return Response("OK")
        


