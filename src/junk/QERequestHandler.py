from RequestHandler import RequestHandler

class QERequestHandler(RequestHandler):

    def renderToString(self, req, tmplfile, args={}):
        return self.getTopHandler().renderToString(req, tmplfile, args)
                
    def renderTemplate(self, req, tmplfile, data):
        return self.getTopHandler().renderTemplate(req, tmplfile, data)
        
    def getDB(self, *pars, **args):
        return self.getTopHandler().getDB(*pars, **args)
        
    def getDBParams(self, *pos, **args):
        return self.getTopHandler().getDBParams(*pos, **args)

    def readRequest(self, req, args):
        form = self.getFormData(req)
        args = dict(args)
        args.update(form)
        form = args
        dbname = '%s' % (args.get('dbname',None),)
        #raise dbname
        dbtype = self.getDBParams(dbname)['type']

        action = form.get('action','Run')
        title = form.get('title', '')
        tables = [x.strip() for x in form['tables'].split(',')]
        columns = [x.strip() for x in form.get('columns','*').split(',')]
        joins = form.get('joins','')
        orders  =form.get('orders','')
        pagerows = int(form.get('pagerows',50))
        #self.apacheLog("pagerows=%s" % (pagerows,))
        breaks = form.get('breaks','')
        output_type = form.get('output_type','HTML')
        maxrows = form.get('maxrows', None)
        drill_baggage = form.get('drill_baggage',None)
        drill_wheres = form.get('drill_wheres','yes')
        drill_down_field = form.get('drill_down_field', '')
        drill_from_field = form.get('drill_from_field', '')
        drill_arg = form.get('drill_arg', None)
        sql = form.get('sql_statement', None)
        if not sql:
            groups = form.get('groups', None)
            #dbname = form.get('dbname',None)
            wheres = []
            conditions = []
            if joins:   conditions = [joins]
            for k in list(form.keys()):
                if k[:12] == 'wheres_value':
                    i = k[12:]
                    col = form['wheres_column'+i]
                    op = form.get('wheres_logic'+i, 'like')
                    val = form['wheres_value'+i]
                    func = form.get('wheres_function'+i, None)
                    esc = form.get('wheres_escape'+i, '')
                    if esc:
                        esc_auto = form.get('wheres_escape_auto'+i, None)
                        if esc_auto:
                            val = val.replace(esc_auto, esc+esc_auto)
                    wheres.append((col, op, val, func, esc))
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
            ccs, cts, cws = self.processConditionals(form)
            #self.apacheLog('cws=%s' % (cws,))
            self.join(conditions, ['( %s )' % (x,) for x in cws])
            self.join(tables, cts)   
            self.join(columns, ccs)              
            gwh = form.get('wheres', None)
            if gwh:
                self.join(conditions, gwh)
            if drill_from_field and drill_arg:
                conditions.append("(%s = '%s')" % (drill_from_field, drill_arg))
            if maxrows != None and dbtype == 'Oracle':
                conditions.append("rownum < %s" % (maxrows,))
            conds_txt = ' and '.join(conditions)
            tables = ','.join(tables)
            columns = ','.join(columns)
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
            if maxrows != None and dbtype == 'Postgres':
                sql += """
                limit %s""" % (maxrows,)

                
        #self.apacheLog("sql: %s" % (sql,))
        return {
            'action':   action,
            'columns':  columns,
            'tables':   tables,
            'where':    conds_txt,
            'order':    orders,
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
            #'dbuser':       form.get('dbuser', None),
            'dbname':       form.get('dbname', None),
            #'dbpswd':       form.get('dbpswd', None),
            #'dbhost':       form.get('dbhost', None),
        }
            

    def processListOfConditionals(self, lst, form):
        outlist = []
        for cw in lst:
            cw = cw.strip()
            m = self.WhereFragmentRE.match(cw)
            out = None
            if m:
                name = m.group('name').strip()
                tfr = m.group('tfragment').strip()
                ffr = m.group('ffragment')
                #self.apacheLog('name=<%s> t=<%s> f=<%s>' % (name, tfr, ffr))
                if ffr: ffr = ffr.strip()
                if name in form:
                    out = tfr.replace('$'+name, form[name])
                elif ffr:
                    out = ffr
            else:
                out = cw
            if out and not out in outlist:
                outlist.append(out)
        return outlist

    def processConditionals(self, form):
        cwlist = form.get('cwheres', [])
        if type(cwlist) == type(''):
            cwlist = [cwlist]
        #self.apacheLog('cwheres=%s' % (cwlist,))
        outw = self.processListOfConditionals(cwlist, form)
        ctlist = form.get('ctables', [])
        if type(ctlist) == type(''):
            ctlist = [ctlist]
        outt = self.processListOfConditionals(ctlist, form)
        cclist = form.get('ccolumns', [])
        if type(cclist) == type(''):
            cclist = [cclist]
        outc = self.processListOfConditionals(cclist, form)
        return outc, outt, outw

    def join(self, lst, lst2):
        if type(lst2) != type([]):
            lst2 = [lst2]
        for x in lst2:
            if not x in lst:    lst.append(x)
        return lst

        
