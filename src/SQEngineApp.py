# -*- coding: utf-8 -*-

from webpie import WPApp, app_synchronized

from SimpleQueryHandler import SimpleQueryHandler
from QEConfigFile import QEConfigFile

import os, sys

from wsdbtools import ConnectionPool

from Version import Version

from LRUCache import LRUCache


def strftime(dt, fmt):
    return dt.strftime(fmt)

class SQEngineApp(WPApp):

    Version = Version
    #COOKIE_PATH = "/QE"

    def __init__(self, root_class):
        WPApp.__init__(self, root_class)
        self.PostgresPools = {}      # connection string -> connection pool
        self.Debug = False
        self.Cfg = QEConfigFile()
        self.Debug = self.Cfg.Debug
        self.UseCache = self.Cfg.UseCache
        self.RequestCache = LRUCache(10, ttl=3600)
        
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
        
    
application = SQEngineApp(SimpleQueryHandler)
