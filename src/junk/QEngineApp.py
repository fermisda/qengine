# -*- coding: utf-8 -*-

from WSGIApp import WSGIHandler, WSGISessionApp, Response, Application
from dbdig import DbDig

from SimpleQueryHandler import SimpleQueryHandler

import os, urllib.request, urllib.parse, urllib.error, sys, urllib.request, urllib.error, urllib.parse

from configparser import ConfigParser

from Version import Version


class   QEConfigFile(ConfigParser):
    def __init__(self, req, path=None, envVar=None):
        """
        path is a fully qualified path/file name of the
        configuration file to open.  If not provided it will
        will be taken from the environment varable envVar.  If no
        environment variable is passed in APACHE_PYTHON_CFG_FILE
        will be used.  If both path and envVar are defined, envVar
        will be used.
        """
        ConfigParser.__init__(self)
        if not path:
            if envVar is None:
                envVar = 'APACHE_PYTHON_CFG_FILE'
            path = req.environ.get(envVar, None) or \
                os.environ[envVar]
        self.read(path)

    def getDBList(self):
        return [x for x in self.get('Global','databases').split(' ')
                    if x]

    def getDBParams(self, dbname):
        dict = {}
        for n, v in self.items(dbname):
            dict[n] = v.strip()
        return dict


class RequestHandler(WSGIHandler):

    MAXROWLIMIT = 2400

    def __init__(self, req, app):
        WSGIHandler.__init__(self, req, app)
        self.SQ = SimpleQueryHandler(req, app)

    def hello(self, req, relpath, **args):
        req.write("hello")

    def getDB(self, qdict = {}, dbname = None):
        return self.App.getDB(qdict, dbname)

    def defaultDB(self):
        return self.App.defaultDB()

    def getDBParams(self, dbname):
        return self.App.getDBParams(dbname)

    def probe(self, req, relpath, dbname=None, **args):
        # probe method for the HTTP redirector
        req.content_type = "text/plain"
        dbname = dbname or self.App.defaultDB()
        dbparams = self.App.getDBParams(dbname)
        dbtype = dbparams.get('type', 'Postgres')
        try:    conn = self.App.getDB(dbname = dbname)
        except:
            req.status = apache.HTTP_BAD_REQUEST
            req.write("can not connect to database")        
            return apache.OK
            
        c = conn.cursor()
        probe = False
        if dbtype == 'Oracle':
            c.execute('select 1 from dual')
            probe = c.fetchone()[0] == 1
        elif dbtype == 'Postgres':
            c.execute('select 1')
            probe = c.fetchone()[0] == 1
        if probe:
            return Response('OK')
        else:
            resp = Response('database is unaccessible')
            resp.status = 400
            return resp

    def ping(self, req, relpath, **args):
        txt = "<html><body><pre>"
        for k, v in list(req.environ.items()):
            txt += "%s = %s\n" % (k, v)
        txt += "</pre></body></html>"
        return Response(txt)
            
    def showSession(self, req, relpath, **args):
        response = Response("""
            <html>
            <body>
            <h1>Session</h1>
            <table>""")
        lst = list(self.getSessionData().items())
        lst.sort()
        f = response.body_file
        for k, v in lst:
            f.write("<tr><td>%s</td><td>%s</td></tr>" % (k,v))
        f.write("""
            </table>
            </body>
            </html>""")
        return response

    def destroy(self):
        #self.apacheLog("QEnginApp.destroy")
        if self.DBConn:
            #self.apacheLog("Disconnecting")
            self.DBConn.close()
        self.DBConn = None

    def request(self, req, relpath, **args):
        f = req.str_params
        args.update(f)
        f = args
        action = f.get('action', 'Run')
        if action == 'Run':
            return self.run(req, relpath, **args)
        elif action == 'Edit':
            return self.edit(req, relpath, **args)
        elif action == 'Build':
            return self.build(req, relpath, **args)
            
    index = request 

    def error_(self, req, relpath, **args):
        sess = self.getSessionData()
        #self.apacheLog("error: session_id:%s" % (sess.id(),))
        #raise ValueError, 'sess: %s' % (sess,)
        #raise "%s" % (sess.items(),)
        error = args.get("error","")
        qdict = sess.get('query', {})
        sql = qdict.get('executed_sql','')
        self.renderTemplate(req, 'error.html', {
            'sql':sql, 'error':error })    

    def join(self, lst, lst2):
        if type(lst2) != type([]):
            lst2 = [lst2]
        for x in lst2:
            if not x in lst:    lst.append(x)
        return lst

    def sanitizeSQL(self, sql):
        sql = sql.split(';')[0].strip()
        if sql[:6].lower() != 'select':
            sql = 'select '+sql
        return sql

    def buildSQL(self, params, override = False):
        if not override and params.get('sql', None):
            return self.sanitizeSQL(params['sql'])
        #dbname = form.get('dbname',None)
        dbname = params['dbname']
        #raise dbname
        dbtype = params['dbtype']
        tables = params['tables']
        columns = params.get('columns', '*')
        orders = params['orders'] or ""
        conditions = []
        joins = params['joins']
        if joins:   conditions = [joins]
        form = params['form']
        #wheres = []
        for k in list(form.keys()):
            if k[:13] == 'wheres_column':
                i = k[13:]
                col = form[k]
                if not col: continue
                op = form.get('wheres_logic'+i, 'like')
                val = form['wheres_value'+i]
                if op == 'skip':    continue
                if op == 'is null':
                    conditions.append("(%s is null)" % (col,))
                    continue
                elif op == 'is not null':
                    conditions.append("(%s is not null)" % (col,))
                    continue
                    
                if not val: continue

                if op == 'array contains':      # array contains value
                    conditions.append("(%s @> array[%s])" % (col, val))
                    continue
                    
                if op == 'not array contains':      # array does not contains value
                    conditions.append("(not %s @> array[%s])" % (col, val))
                    continue
                    
                #print k, col, val
                func = form.get('wheres_function'+i, None)
                esc = form.get('wheres_escape'+i, '')
                if esc:
                    esc_auto = form.get('wheres_escape_auto'+i, None)
                    if esc_auto:
                        val = val.replace(esc_auto, esc+esc_auto)
                #wheres.append((col, op, val, func, esc))
                val = "'%s'" % (val,)
                if func:
                    val = '%s(%s)' % (func, val)
                if esc: esc = "escape '%s'" % (esc,)
                conditions.append("(%s %s %s %s)" % (col, op, val, esc))

                wh_tables = form.get('wheres_table'+i, None)
                if wh_tables:
                    self.join(tables, [x.strip() for x in wh_tables.split(',')])
                    j = form.get('wheres_join'+i, '').strip()
                    if j: self.join(conditions,j)
        #print conditions
        #ccs, cts, cws = self.processConditionals(form)
        #self.apacheLog('cws=%s' % (cws,))
        #self.join(conditions, ['( %s )' % (x,) for x in cws])
        #self.join(tables, cts)   
        #self.join(columns, ccs)    
        gwh = params.get('wheres','')  
        #raise 'gwh=%s' % (gwh,)        
        #raise "conditions=%s" % (conditions,)
        if gwh:
            self.join(conditions, gwh)
        #raise "conditions=%s" % (conditions,)
        drill_from_field = params['drill_from_field']
        drill_arg = params['drill_arg']
        if drill_from_field and drill_arg:
            conditions.append("(%s = '%s')" % (drill_from_field, drill_arg))
        
        """ maxrow things moved to applyRowLimit()
        maxrows = params['maxrows']
        if maxrows != None and dbtype == 'Oracle':
            conditions.append("rownum < %s" % (maxrows,))
        """
        and_or = params.get('wheres_bool', 'and')
        try:
            conds_txt = (' ' + and_or + ' ').join(conditions)
        except:
            raise ValueError('conditions=%s' % (conditions,))
        #raise "conds_txt="+conds_txt
        params['conditions'] = conds_txt
        tables = ','.join(params['tables'])
        groups = params['groups']
        sql = """select %s 
                from 
                    %s""" % (columns, tables)
        if conds_txt:
            sql += """
                where 
                    %s""" % (conds_txt,)
        if groups:
            sql += """
                group by 
                    %s""" % (groups,)
        if orders:
            sql += """
                order by 
                    %s""" % (orders,)
                    
        """ maxrow things moved to applyRowLimit()
        if maxrows != None and dbtype == 'Postgres':
            sql += '''
            limit %s''' % (maxrows,)
        """

        #print sql

        return sql

    def mergeInputs(self, req, args):
        ret = {}
        args = dict(args)
        for k, v in list(req.params.items()):
            v = str(v).strip()
            vals = ret.get(k)
            if vals:
                vals = vals + ',' + v
            else:
                vals = v
            ret[k] = vals
        ret.update(args)
        return ret

    def readForm(self, req, args):
        form = self.mergeInputs(req, args)
        #raise '%s' % (self.getFormData(req).list,)
        #raise form.get('dbname')
        dbname = '%s' % (form.get('dbname',self.defaultDB()),)
        #raise dbname
        dbparams = self.getDBParams(dbname)
        dbtype = dbparams.get('type','postgres')
        if dbtype == 'Oracle':
            namespace = form.get('owner', form.get('namespace', ''))
        else:
            namespace = form.get('namespace', form.get('owner', 'public'))
        encoding = form.get('encoding', dbparams.get('encoding',None))
        encoding_mode = form.get('encoding_mode', 
            dbparams.get('encoding_mode','replace'))
        wheres_bool = form.get('wheres_bool', 'and')
        action = form.get('action','Run')
        title = form.get('title', '')
        tables = [x.strip() for x in form.get('tables','').split(',')]
        orig_columns = form.get('columns',None)
        columns = form.get('columns', '*')
        joins = form.get('joins',None)
        orders  = form.get('orders', "")
        for k, v in list(form.items()):
            if v and k.startswith('orders'):
                n = k.split('orders',1)[1]
                if n:
                    if orders:  orders += ','
                    orders += v
                    desc = form.get("orders_desc"+n, "")
                    if desc:    orders += " " + desc
        pagerows = int(form.get('pagerows',50))
        breaks = form.get('breaks','')
        output_type = form.get('output_type','HTML')
        maxrows = form.get('maxrows', self.MAXROWLIMIT) or self.MAXROWLIMIT
        maxrows = min(self.MAXROWLIMIT, int(maxrows))
        #self.apacheLog("pagerows=%s, maxrows=%s" % (pagerows,maxrows))
        drill_baggage = form.get('drill_baggage',None)
        drill_wheres = form.get('drill_wheres','yes')
        drill_down_field = form.get('drill_down_field', '')
        drill_from_field = form.get('drill_from_field', '')
        drill_arg = form.get('drill_arg', None)
        groups = form.get('groups', None)
        wheres = form.get('wheres', None)
        sql = form.get('sql_statement', None)
                
        #self.apacheLog("sql: %s" % (sql,))
        return {
            'namespace':    namespace,
            'form':     form,
            'action':   action,
            'columns':  columns,
            'orig_columns':  orig_columns,
            'tables':   tables,
            'joins':    joins,
            'orders':    orders,
            'sql':      sql,
            'title':    title,
            'pagerows': pagerows,
            'breaks':   breaks,
            'output_type':  output_type,
            'maxrows':  maxrows,
            'groups':   groups,
            'drill_baggage':    drill_baggage,
            'drill_wheres':    drill_wheres,
            'drill_down_field':    drill_down_field.lower(),
            'drill_from_field':    drill_from_field.lower(),
            'drill_arg':    drill_arg,
            'wheres':   wheres,
            'wheres_bool':  wheres_bool,
            #'dbuser':       form.get('dbuser', None),
            'dbname':       dbname,
            'dbtype':       dbtype,
            'encoding':     encoding,
            'encoding_mode':     encoding_mode,
            #'dbpswd':       form.get('dbpswd', None),
            #'dbhost':       form.get('dbhost', None),
        }
            
    def edit(self, req, relpath, **args):
        qdict = self.readForm(req, args)
        sql = self.buildSQL(qdict)
        self.renderTemplate(req, 'query_edit_form.html', 
            {'sql':sql, 'action':'./run', 'dbname':qdict['dbname'],
                'pagerows': qdict.get('pagerows', 50),
                'maxrows': qdict.get('maxrows'),
                'title':qdict.get('title','')
                })

    def query_edit_action(self, req, relpath, **args):
        sess = self.getSessionData()
        qdict = self.readRequest(req, args)
        qdict['action'] = 'Edit'
        #raise 'qdict=%s' % (qdict,)
        sql = self.sanitizeSQL(qdict['sql'])
        qdict['sql'] = sql
        #raise 'sql=%s' % (sql,)
        sess['query'] = qdict
        #raise '%s' % (qdict,)
        sess.save()
        self.redirect('./run')
        
    def createDataset(self, sess, qdict, columns, data):
        lst = []
        dbname = qdict['dbname']
        encoding = qdict['encoding']
        encoding_mode = qdict['encoding_mode']
        for d in data:
            if encoding:
                decoded = []
                for x in d:
                    if type(x) == type(''):
                        x = x.decode(encoding, encoding_mode)
                    decoded.append(x)
                d = decoded
            lst.append([{'val':d[i], 'col':columns[i].lower()} for i in range(len(d))])
        dsid = sess.get('last_dsid',0) + 1
        sess['last_dsid'] = dsid
        dataset = (qdict, columns, lst)
        sess.bulkSave("dataset:%d" % (dsid,), dataset)
        return dsid
        
    def getDataset(self, sess, dsid):
        return sess.bulkRead("dataset:%s" % (dsid,))

    def createDataset_(self, sess, qdict, columns, data):
        lst = []
        for d in data:
            lst.append([{'val':d[i], 'col':columns[i].lower()} for i in range(len(d))])
        dsid = sess.get('last_dsid',0) + 1
        sess['last_dsid'] = dsid
        datasets = sess.get('datasets', {})
        datasets[dsid] = (qdict, columns, lst)
        sess['datasets'] = datasets
        return dsid

    def applyRowLimit(self, sql, maxrows, dbtype):
        if dbtype == 'Oracle':
            sql = """select a.* from (%s) a where rownum <= %s""" % (sql, maxrows)
        elif dbtype == 'Postgres':
            sql = '%s limit %s' % (sql, maxrows)
        return sql
        
    def build(self, req, relpath, **args):
        qdict = self.readForm(req, args)
        dbname = qdict['dbname']
        dbtype = qdict['dbtype']
        namespace = qdict.get('namespace', qdict.get('user', ''))
        tlist = []
        for t in qdict['tables']:
            # parse aliases
            words = t.split()
            words = (words + [''])[:2]
            tname, alias = tuple(words)
            tlist.append((tname, alias))
        tlist.sort()
        numSorts = int(qdict.get('numSorts',3))
        numWheres = int(qdict.get('numWheres',3))
        orig_columns = qdict.get('orig_columns', None)
        columns = qdict.get('columns', None)
        if not orig_columns:
            columns = None
        tcolumns = []
        #print dbname, dbtype, tlist, namespace, orig_columns, columns
        conn = self.getDB(qdict)
        dig = DbDig(conn, dbtype)
        for tname, alias in tlist:
            clist = dig.columns(namespace, tname)
            clist.sort()
            tcolumns.append((tname, alias, clist))
        wheres = qdict.get('wheres', None)
        self.renderTemplate(req, "build.html",
            {
                'columns':columns, 'table_columns':tcolumns,
                'table_list':tlist, 'tables':qdict['tables'],
                'dbname':dbname,
                'namespace':namespace, 'numWheres':numWheres, 
                'numSorts':numSorts, 'wheres':wheres,
                'pagerows': qdict.get('pagerows', 50),
                'maxrows': qdict.get('maxrows'),
                'title':qdict.get('title','')
            }
        )

    def run(self, req, relpath, **args):
        #self.apacheLog("Executor.run")
        #raise "run"
        #raise "args=%s page=(%s) (%s)" % (args, type(page), page,)
        page = int(args.get('page',0))
        pagerows = args.get('pagerows', None)
        if pagerows != None:
            pagerows = int(pagerows)
        qdict = self.readForm(req, args)
        #raise 'qdict: %s' % (qdict,)
        sql = self.buildSQL(qdict)
        
        #raise ValueError, "SQL: %s" % (sql,)
        
        sess = self.getSessionData()  
        qdict['expanded_sql'] = sql
        qdict['executed_sql'] = self.collapseSQL(sql)
        sess['query'] = qdict
        c = self.getDB(qdict).cursor()
        
        maxrows = qdict.get('maxrows', self.MAXROWLIMIT)
        sql = self.applyRowLimit(sql, maxrows, qdict['dbtype'])
        
        #raise sql
        try:    c.execute(sql)
        except:
            #raise ValueError, "SQL: %s\nerror:%s %s" % (sql,sys.exc_type, sys.exc_value)
            sess.save()
            self.redirect('./error?error=%s' % 
                (urllib.parse.quote('SQL Error: %s %s' % (sys.exc_info()[0], sys.exc_info()[1])),)
                )
            return
        cols = [x[0] for x in c.description]
        data = c.fetchall()
        if qdict['dbtype'] == 'Oracle':
            # restore aliases specified in the original query
            columns = qdict.get('columns', None) or '*'
            aliases = [cn.strip().split()[-1] for cn in qdict['columns'].split(',')]
            
            #self.apacheLog('aliases: %s' % (aliases,))
            #raise 'cols=%s, ocols=%s' % (cols, ocols)
            ncols = []
            for i in range(len(cols)):
                #self.apacheLog("%s -> split: %s" % (ocols[i], ocols[i].split(),))
                cname = cols[i]
                alias = cname
                for a in aliases:
                    if a.lower() == cname.lower():
                        alias = a
                        break
                ncols.append(alias)
            cols = ncols
        dsid = self.createDataset(sess, qdict, cols, data)
        sess.save()
        output_type = self.readForm(req, args).get('output_type','HTML')
        if not output_type in ('HTML', 'form'):
            self.redirect('./show_data/data.csv?output_type=%s&dsid=%s' % (output_type,dsid))
            
        return self.show_data(req, relpath, page=page, pagerows=pagerows, sess=sess, dsid=dsid)

    query = run

    def collapseSQL(self, sql):
        return ' '.join([s.strip() for s in sql.split('\n')])
                
    def buildLink(self, qdict, page):
        link = None
        
        if qdict.get('sql', None):
            sql = self.collapseSQL(qdict['sql'])
            #raise 'sql=%s' % (sql,)
            link = './query?sql_statement=%s' % (urllib.parse.quote(sql),)
        else:
            link = './query?tables=%s&columns=%s' % (
                urllib.parse.quote(','.join(qdict['tables'])), 
                urllib.parse.quote(qdict.get('columns', '*')))
            if qdict['orders']:
                link += '&orders=%s' % (urllib.parse.quote(qdict['orders']),)
            if qdict['conditions']:
                link += '&wheres=%s' % (urllib.parse.quote(qdict['conditions']),)
            if qdict['title']:
                link += '&title=%s' % (urllib.parse.quote(qdict['title']),)
            if qdict['breaks']:
                link += '&breaks=%s' % (urllib.parse.quote(qdict['breaks']),)
            if qdict['drill_down_field']:
                link += '&drill_down_field=%s' % (urllib.parse.quote(qdict['drill_down_field']),)
            if qdict['drill_wheres']:
                link += '&drill_wheres=%s' % (urllib.parse.quote(qdict['drill_wheres']),)
            if qdict['drill_baggage']:
                link += '&drill_baggage=%s' % (urllib.parse.quote(qdict['drill_baggage']),)
        if link:
            if qdict['dbname']:
                link += '&dbname=%s' % (urllib.parse.quote(qdict['dbname']),)
            link += "&page=%s" % (page,)
            output_type = qdict.get('output_type','')
            if output_type:
                link += "&output_type=%s" % (urllib.parse.quote(output_type),)
            maxrows = qdict.get('maxrows')
            link += "&maxrows=%s" % (maxrows,)
            pagerows = qdict.get('pagerows', None)
            if pagerows:
                link += "&pagerows=%s" % (pagerows,)
        return link

    def show_data(self, req, relpath, page=0, pagerows = None, sess=None, dsid=None, **args):
        #self.apacheLog("pagerows=%s" % (pagerows,))
        page = int(page)
        if not sess:    sess = self.getSessionData()
        dsid = int(dsid)
        #qdict, cols, data = sess['datasets'][dsid]
        qdict, cols, data = self.getDataset(sess, dsid)
        maxrows = qdict.get('maxrows')
        sql = qdict['executed_sql']
        expanded_sql = qdict['expanded_sql']
        qdict.update(args)
        link = None
        if qdict['action'] == 'Run':
            link = self.buildLink(qdict, page)
        #raise 'Link=%s' % (link,)       
        ncols = 0
        if data:
            ncols = len(cols)
        names = []

        if pagerows == None:
            pagerows = int(qdict.get('pagerows',50))
        if pagerows:    pagerows = int(pagerows)
        
        lst = data
        nrows = len(data)
        output_type = self.readForm(req, args).get('output_type','HTML')
        prevpage = None
        nextpage = None
        npages = (nrows+pagerows-1)/pagerows
        if output_type in ('HTML', 'form'):        
            lst = data[page*pagerows:]
            lst = lst[:pagerows]
            breaks = qdict.get('breaks', None)
            if breaks:
                breaks = [x.strip().lower() for x in breaks.split(',')]
                last_dict = {}
                for d in lst:
                    this_dict = {}
                    for i in range(len(d)):
                        c = cols[i].lower()
                        if c in breaks:
                            this_dict[c] = d[i]
                    if this_dict == last_dict:
                        for i in range(len(d)):
                            c = cols[i].lower()
                            if c in breaks:
                                d[i] = ''
                    last_dict = this_dict
        
            if page > 0:    prevpage = page - 1
            if (page+1)*pagerows < nrows:  nextpage = page+1
        #raise ValueError, "pagerows: %d, size: %d" % (pagerows, len(data)) 
        
        csv_commas_link = './show_data/data.csv?output_type=text,&dsid=%s' % (dsid,)
        csv_tabs_link = './show_data/data.csv?output_type=text&dsid=%s' % (dsid,)
        
        tempname = 'browser_data.html'
        if output_type == 'text':   
            tempname = 'browser_data.tsv'
            req.content_type='text/csv'
        if output_type == 'text,':   
            tempname = 'browser_data.csv'
            req.content_type='text/csv'
        if output_type == 'application/xls':   
            tempname = 'browser_data.csv'
            req.content_type='text/csv'
        if output_type == 'form':
            tempname = 'data_as_form.html'
        drill_where = ''
        if qdict.get('drill_wheres', None) and qdict['drill_wheres'].lower() != 'no':
            drill_where = qdict['drill_wheres']
        bag = ''
        if qdict.get('drill_baggage', None):
            #raise ValueError, 'Bag path: '+os.path.dirname(__file__)+'/bags/'+qdict['drill_baggage']
            #bag=open(os.path.dirname(__file__)+'/bags/'+qdict['drill_baggage'], 'r').read()
            bag=urllib.request.urlopen(qdict['drill_baggage']).read()
        title = None
        if qdict['action'] == 'Run':   title = qdict.get('title', None)
        
        self.renderTemplate(req, tempname, 
            {
                'data':lst, 'cols':cols, 'ncols':ncols,
                'debug':self.App.Debug,
                'sql':expanded_sql, 
                'link':link,
                'page':page,    'pagerows':pagerows,    'npages':npages,
                'maxrows': maxrows or '', 
                'prevpage':prevpage,    'nextpage':nextpage,
                'output_type': output_type,
                'drill_bag':bag,
                'drill_baggage':qdict.get('drill_baggage', ''),
                'drill_down_field':qdict.get('drill_down_field', None),
                'drill_wheres':drill_where,
                'drill_arg':qdict.get('drill_arg',''),
                'title': title,
                #'dbhost':   qdict['dbhost'] or '',
                'dbname':   qdict['dbname'] or '',
                'csv_commas_link': csv_commas_link,
                'csv_tabs_link': csv_tabs_link,
                'show_edit':output_type != 'form',
                'dsid':dsid,
                'nrows':nrows
                #'dbpswd':   qdict['dbpswd'] or '',
                #'dbuser':   qdict['dbuser'] or '',
                })  

    def error(self, req, relpath, error=''):
        sess = self.getSessionData()
        qdict = sess.get('query', {})
        sql = qdict.get('executed_sql','')
        self.renderTemplate(req, 'error.html', 
                {'error':error, 'sql':sql, 'qdict':list(qdict.items())})
                

Persistent = {}



def strftime(dt, fmt):
    return dt.strftime(fmt)

class QEngineApp(WSGISessionApp):

    Version = Version
    #COOKIE_PATH = "/QE"

    def __init__(self, request, root_class):
        WSGISessionApp.__init__(self, request, root_class)
        #raise 'contrtuctor'
        self.DBConn = None
        self.DBParams = {}
        #raise 'cfg..'
        self.Debug = False
        self.JEnv = None
        self.Cfg = None
        self.initJinja2(
                    tempdirs = [os.path.dirname(__file__)], 
                    filters = {'strftime':strftime}
                    )
        self.Cfg = QEConfigFile(request, envVar = 'QENGINE_CFG')
        try:
            self.Debug = self.Cfg.get('Global','debug')
            self.Debug = self.Debug.lower() != 'no'
        except:
            self.Debug = False
        try:
            self.SESSION_STORAGE_PATH = self.Cfg.get('Global','session_storage')
        except:
            self.SESSION_STORAGE_PATH = '/tmp/QE_Sessions'
        #print "sessions: ", self.SESSION_STORAGE_PATH
        #print "DB: ", self.Cfg.get('Global','default_db')

    def JinjaGlobals(self):
        data = {}
        return {"GLOBAL_GUI_Version":  self.Version}

    

    def log(self, msg):
        open('/tmp/log', 'a').write('%s.%s: %s\n' % (
            self.__class__.__name__, id(self), msg))

    def getPersistent(self, key):
        return Persistent.get(key, None)

    def savePersistent(self, key, data):
        Persistent[key] = data

    def getDBParams(self, dbn = None):
        #raise ValueError, 'dbn=%s' % (dbn,)
        if not dbn: return self.DBParams
        return self.Cfg.getDBParams(dbn)

    def connect(self, dbn, qdict):
        dbparams = self.getDBParams(dbn)
        #dbparams['dbname'] = dbn
        dbparams['user'] = dbparams['read_user']
        dbparams['password'] = dbparams['read_password']
        self.DBParams = dbparams
        conn = None
        typ = None
        #raise '%s' % (dbparams,)
        if dbparams['type'] == 'Postgres':
            import psycopg2
            dbparams['port'] = dbparams.get('port', 5432)
            str = 'dbname=%(dbname)s host=%(host)s user=%(user)s password=%(password)s port=%(port)s' % \
                dbparams
            conn = psycopg2.connect(str)
            conn.cursor().execute("set search_path to %s" % (dbparams.get('namespace','public'),))
        elif dbparams['type'] == 'Oracle':
            # Oracle
            import cx_Oracle
            str = '%(user)s/%(password)s@%(tns)s' % dbparams
            conn = cx_Oracle.connect(str)
        return conn
    

    def defaultDB(self):
        sess = self.getSessionData()
        return sess.get('dbname', None) or \
                self.Cfg.get('Global','default_db')

    def getDB(self, qdict = {}, dbname = None):
        if self.DBConn == None: 
            #sess = self.getSessionData()
            dbname = dbname or qdict.get('dbname',None) or \
                self.defaultDB()
            #self.apacheLog("connecting")
            self.DBConn = self.connect(dbname, qdict)
        return self.DBConn       

    
application = Application(QEngineApp, RequestHandler)
