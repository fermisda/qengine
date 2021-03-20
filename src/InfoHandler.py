from SQBaseHandler import SQBaseHandler, add_data_origin
from webpie import WPHandler, Response, webmethod
import time, json
from wsdbtools import DbDig

class InfoHandler(SQBaseHandler):

    @add_data_origin
    def columns(self, req, relpath, dbname=None, t=None, f="json", **args):
        # postgres version
        self.check_for_injunction(t or "")
        conn = self.App.connect(dbname)
        nspace = 'public'
        if '.' in t:
            nspace, t = tuple(t.split('.',1))
        f = args.get("f", "json")
        columns = DbDig(conn, "Postgres").columns(nspace, t)
        
        if f == "csv":
            cnames = ["column", "type"]
            cols = [(c,t) for c, t, m, n, d in columns]
            csv = self.mergeLines(self.formatCSV(cnames, cols))
            resp = Response(app_iter = csv, content_type='text/plain')
            return resp
        elif f == "json":
            lst = []
            for c, t, m, n, d in columns:
                lst.append({
                    "name":c,
                    "type":t,
                    "modifiers":m,
                    "not_null":n,
                    "description":d
                })
            resp = Response(json.dumps(lst), content_type='text/plain')
            return resp
            
    @add_data_origin   
    def tables(self, req, relpath, ns="public", dbname=None, f="json", **args):
        # postgres version
        conn = self.App.connect(dbname)
        nspace = ns
        self.check_for_injunction(ns)
        tables = DbDig(conn, "Postgres").tables(nspace)
        if f == 'csv':
            tuples = [(t,) for t in tables]
            csv = self.mergeLines(self.formatCSV(["name"], tuples))
            resp = Response(app_iter = csv, content_type='text/plain')
            return resp
        else:
            resp = Response(json.dumps(tables), content_type='text/plain')
            return resp
                
        
        

        
        
