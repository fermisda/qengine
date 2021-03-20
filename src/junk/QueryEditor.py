from QERequestHandler import QERequestHandler
from mod_python import util
import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse
import sys, os, re

class QueryEditor(QERequestHandler):
    
    def __init__(self, parent):
        QERequestHandler.__init__(self, parent)

    def sanitizeSQL(self, sql):
        sql = sql.split(';')[0].strip()
        if sql[:6].lower() != 'select':
            sql = 'select '+sql
        return sql

    def form(self, req, **args):
        qdict = self.readRequest(req, args)
        sql = qdict.get('sql', '')
        sql = self.sanitizeSQL(sql)
        self.renderTemplate(req, 'query_edit_form.html', 
            {'sql':sql, 'action':'./E/run', 'dbname':qdict['dbname']})

        
