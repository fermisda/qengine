# -*- coding: utf-8 -*-

from webpie import WPApp, app_synchronized

from SimpleQueryHandler import SimpleQueryHandler
from QEConfigFile import QEConfigFile
from LRUCache import LRUCache

import os, sys

from wsdbtools import ConnectionPool

from Version import Version


""" comment out
class __LRUCache:

    def __init__(self, maxslots, ttl = None, lowwater = None):
        self._Lock = RLock()
        self.Cache = {}
        self.MaxSlots = maxslots
        self.TTL = ttl
        self.LowWater = lowwater

    @synchronized
    def setTTL(self, ttl):
        self.TTL = ttl

    @synchronized
    def get(self, k):
        if k not in self.Cache:
            #print "key %s not found" % (k,)
            return None
        tc, ta, data = self.Cache[k]
        now = time.time()
        if self.TTL != None and tc < now - self.TTL:
            #print "old entry: ", now - tc
            del self.Cache[k]
            return None
        self.Cache[k] = (tc, now, data)
        return data

    __getitem__ = get

    @synchronized
    def purge(self):
        nkeep = self.LowWater
        if nkeep == None:   nkeep = self.MaxSlots
        if len(self.Cache) > nkeep:
            lst = list(self.Cache.items())
            # sort by access time in reverse order, latest first
            lst.sort(key=lambda x: -x[1][1])
            while lst and len(lst) > nkeep:
                k, v = lst.pop()
                del self.Cache[k]

    @synchronized
    def put(self, k, data):
        now = time.time()
        self.Cache[k] = (now, now, data)
        self.purge()

    __setitem__ = put

    @synchronized
    def remove(self, k):
        try:    del self.Cache[k]
        except KeyError:    pass

    __delitem__ = remove

    def keys(self):
        return list(self.Cache.keys())

    @synchronized
    def clear(self):
        self.Cache = {}

"""


def strftime(dt, fmt):
    return dt.strftime(fmt)

class SQEngineApp(WPApp):

    Version = Version
    #COOKIE_PATH = "/QE"

    def __init__(self, *params, config=None, **args):
        WPApp.__init__(self, *params, **args)
        self.PostgresPools = {}      # connection string -> connection pool
        self.Debug = False
        self.RequestCache = LRUCache(10, ttl=3600)
        self.Cfg = None
        self.UseCache = False

        config = config or os.environ.get("QENGINE_CFG")

        self.Cfg = QEConfigFile(config)
        self.Debug = self.Cfg.Debug
        self.UseCache = self.Cfg.UseCache



    def init(self):
        pass

    @app_synchronized
    def get_cache(self, key):
        return self.RequestCache[key]

    @app_synchronized
    def clear_cache(self, key):
        return self.RequestCache.clear()

    @app_synchronized
    def put_cache(self, key, data):
        self.RequestCache[key] = data

    @app_synchronized
    def getPostgresPool(self, connstr):
        pool = self.PostgresPools.get(connstr)
        if pool is None:
            pool = ConnectionPool(postgres=connstr)
            self.PostgresPools[connstr] = pool
        return pool

    def log(self, msg):
        open('/tmp/log', 'a').write('%s.%s: %s\n' % (
            self.__class__.__name__, id(self), msg))

    def getDBParams(self, dbn = None):
        return self.Cfg.getDBParams(dbn)

    def connect(self, dbn):
        dbparams = self.getDBParams(dbn)
        #dbparams['dbname'] = dbn
        dbparams['user'] = dbparams['read_user']
        dbparams['password'] = dbparams['read_password']
        self.DBParams = dbparams
        conn = None
        typ = None
        #raise '%s' % (dbparams,)
        if dbparams['type'].lower() == 'postgres':
            #import psycopg2
            dbparams['port'] = dbparams.get('port', 5432)
            constr = 'dbname=%(dbname)s host=%(host)s user=%(user)s password=%(password)s port=%(port)s' % \
                dbparams
            pool = self.getPostgresPool(constr)
            conn = pool.connect()
            #print "pool at %x, connection: %x" % (id(pool),id(conn))
            conn.cursor().execute("set search_path to %s" % (dbparams.get('namespace','public'),))
        elif dbparams['type'].lower() == 'oracle':
            # Oracle
            import cx_Oracle
            str = '%(user)s/%(password)s@%(tns)s' % dbparams
            conn = cx_Oracle.connect(str)
        elif dbparams['type'].lower() == 'mysql':
            # Oracle
            import MySQLdb
            conn = MySQLdb.connect(host=dbparams["host"], port=int(dbparams["port"]),
                    db=dbparams["dbname"], user=dbparams["user"],
                    passwd=dbparams["password"])
        return conn

    def defaultDB(self):
        return self.Cfg.defaultDatabaseName

    def cacheTTL(self, dbname, table):
        return self.Cfg.cacheTTL(dbname, table)


#application = SQEngineApp(SimpleQueryHandler)

def create_application(config):
    app = SQEngineApp(SimpleQueryHandler, config=config)
    return app

# In case you want to run this standalone.
# You will need to define soft links to pythreader, webpie and wsdbtools source directories, or the build area.  And you will
# need to supply a config file.
if __name__ == "__main__":
    import sys, getopt
    opts, args = getopt.getopt(sys.argv[1:], "c:p:")
    opts = dict(opts)
    config = opts.get("-c")
    if config:
        print("Using config file:", config)
    port = int(opts.get("-p", 8888))
    print(f"Starting HTTP server at port {port}...")
    application = create_application(config)
    application.run_server(port)
