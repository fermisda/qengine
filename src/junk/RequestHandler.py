#
# @(#) $Id: RequestHandler.py,v 1.4 2010/12/07 21:18:04 ivm Exp $
#
"""
This module contains classes that provide functionality for managing Apache
requests.  They are intended to interface with the handler.py module.  Any user
defined class that is to be invoked from a URL must be a child of these classes.
"""
from mod_python.Session import FileSession
#from FileSession import Session
from mod_python import apache, util, Cookie
import StringIO
import sys
import time, string
import urllib
from Version import Version as V

class   RequestHandler:

    Version = V

    """
    The base class for handling requests.  
    """
    def __init__(self, parent = None):
        self.Parent = parent
        self.BeingDestroyed = 0
        self.URIPath = None       # after script name (.../qq.py/a/b/c -> /a/b/c)

    def _checkPermissions(self, x):
        self.apacheLog("doc: %s" % (x.__doc__,))
        try:    docstr = x.__doc__
        except: docstr = None
        if docstr and docstr[:10] == '__roles__:':
            roles = [x.strip() for x in docstr[10:].strip().split(',')]
            self.apacheLog("roles: %s" % (roles,))
            return self._checkRoles(roles)
        return True
                        

    def _processRequest(self, req, fcn, relpath, *unnamed, **kv):
        """
        Internal method.  Checks that fcn is the last value on the
        relpath.  When so, it is  invoked as a function and passed
        the values req, *unamed, *kv.
        """
        x = getattr(self, fcn)
        if isinstance(x, RequestHandler):
            # this is a subobject
            words = relpath.split('/', 1)
            fcn = words[0]
            relpath = ''
            if len(words) > 1:  relpath = words[1]
            return x._processRequest(req, fcn, relpath, *unnamed, **kv)
        elif callable(x):
            # check permissions
            if not self._checkPermissions(x):
                return apache.HTTP_UNAUTHORIZED
            else:
                return x(req, relpath, *unnamed, **kv)
        else:
            raise ValueError, 'Can not locate RequestHandler object for %s/%s' % (fcn, relpath)

    def _checkRoles(self, roles):
        return self.Parent._checkRoles(roles)

    def getParent(self):
        """
        Returns the class parent.
        """
        return self.Parent
        
    def getTopHandler(self):
        """
        Returns the TopHandler parent if it exists otherwise
        it returns None.
        """
        if self.Parent:
            return self.Parent.getTopHandler()
        else:
            return self

    def getSessionData(self):
        """
        Returns the current Apache session.
        """
        return self.Parent.getSessionData()
                
    def parseArgs(self, req):
        """
        Arguments that are present within the req are parsed into a
        list of unnamed arguments and a standard keword/value
        dictionary for the named arguments.  Both the dictionary
        and list are returned to the caller.
        """
        dict = {}
        unnamed = []
        args = req.args
        if args:
                args = args.split('&')
                for a in args:
                        kv = a.split('=',1)
                        if len(kv) > 1:
                                dict[kv[0]] = urllib.unquote(kv[1])
                        else:
                                unnamed.append(kv[0])
        return unnamed, dict
        
    def sameURI(self, req, **kv):
        """
        From the req, constructs a new uri with the
        same base uri but with the additional arguments
        added in.  The updated uri is returned.
        """
        uri = req.uri
        oargs, okv = self.parseArgs(req)
        okv.update(kv)
        argsstr = ""
        for a in oargs:
            if argsstr: argsstr = argsstr + '&'
            argsstr = argsstr + '%s' % (a,)
        for k, v in okv.items():
            if argsstr: argsstr = argsstr + '&'
            argsstr = argsstr + '%s=%s' % (k, v)
        if argsstr:
            return uri + '?%s' % (argsstr,)
        else:
            return uri

    def uriDir(self, req):
        """
        Returns the directory the product exits in assuming the
        URL follows the defined convention.
        """
        uri = self.scriptUri(req)
        lst = string.split(uri, '/')
        p = string.join(lst[:-1], '/')
        if not p:   p = '/'
        return p        

    def scriptUri(self, req=None):
        """
        Takes the URI from the req and removes path_info. What
        remains is returned to the caller.  
        """
        if req == None: req = self.getRequest()
        uri = req.uri
        path = req.path_info
        if path:
            tail = len(path)
            uri = uri[:-tail]
        return uri

    def getRequest(self):
        return self.Parent.getRequest()

    def myUri(self, down = None):
        myname = self.Parent.findChild(self)
        uri = self.Parent.myUri(myname)
        if down:    uri += '/' + down
        return uri

    def findChild(self, x):
        for n, v in self.__dict__.items():
            if v is x:  return n
        return None
            
    def myUri_old(self, down = None):
        uri = self.scriptUri()
        if self.URIPath:    uri += '/' + self.URIPath
        if down:    uri += '/' + down
        return uri
    
    def addCookie(self, req, name, value, exp = 15*24*60*60):
        """
        Creates a cookie attached to the req.
          name - the name given to the cookie
          value - what is to be marshaled into the cookie
          exp - number of seconds the cookie is active for.
        """
        Cookie.add_cookie(req, 
            Cookie.MarshalCookie(name, 
                value, self.CookieSecret, 
                expires=time.time() + exp))

    def saveFormAsCookie(self, req, f, *items):
        """
        Adds cookies to the req with one cookie for each
        value.  The cookie is named after the key in f.
          f - dictionary of values to add.
          *items - list of specific items to add, if
             None all values in f will be added.
        """
        if not items:   items = f.keys()
        for i in items:
            if f.has_key(i):
                self.addCookie(req, i, '%s' % (f[i],))

    def getCookiesAsDict(self, req):
        """
        Returns a dictionary of the cookies where the key is the
        name of the cookie and the value is what is in it.
        """
        cookies = Cookie.get_cookies(req, Cookie.MarshalCookie,
            secret = self.CookieSecret)
        dict = {}
        for k, v in cookies.items():
            dict[k] = v.value        
        return dict

    def authenticateX509(self, req, debug=0):
        """
        Ensures the connection is made via x509 and through a
        trusted KCA. A valid certificate will return
        SSL_CLIENT_S_DN, UID.  Errors will cause the return of
        '','some error message'.
        """
        req.add_common_vars()
        if req.subprocess_env.get('HTTPS',None) != 'on':
            return '', 'Please use HTTPS'

        if debug:
            for n in ('SSL_CLIENT_I_DN', 'SSL_CLIENT_S_DN'):
                req.write("<!-- %s='%s' -->\r\n" %
                    (n, req.subprocess_env.get(n, "--")))
        if req.subprocess_env.get('SSL_CLIENT_I_DN', None) != \
                        '/DC=gov/DC=fnal/O=Fermilab/OU=Certificate Authorities/CN=Kerberized CA':
                return '', 'We accept certificates issued by FNAL KCA only'

        dn = req.subprocess_env.get('SSL_CLIENT_S_DN', '')
        if not dn:
                return '', 'SSL_CLIENT_S_DN not found'

        # There are 3 possible formats being parsed for - listed below.   The one with "CN=UID:"
        # is the new one FNAL is moving to. But I am making them all work.
        #SSL_CLIENT_S_DN: /DC=gov/DC=fnal/O=Fermilab/OU=People/CN=Stephen P. White/UID=swhite 
        #SSL_CLIENT_S_DN: /DC=gov/DC=fnal/O=Fermilab/OU=People/CN=Stephen P. White/'0.9.2342.19200300.100.1.1=swhite 
        #SSL_CLIENT_S_DN: /DC=gov/DC=fnal/O=Fermilab/OU=People/CN=Stephen P. White/CN=UID:swhite

        dnWords = dn.split('/')
        dnWordList = []
        for word in dnWords:
            dnWordList.append(word.split('='))

        # Locate the 2nd CN.
        cnt = 0
        uidList = None
        while cnt < len(dnWordList):
            if dnWordList[cnt][0] == 'CN':
                uidList = dnWordList[cnt+1]
                break;
            cnt += 1;

        # Now break it apart for the user id.
        uid = None
        if uidList[0] == 'UID' or uidList[0] == '0.9.2342.19200300.100.1.1':
            uid = uidList[1]
        elif uidList[0] == 'CN':
            uid = uidList[1].split(':')[1]

        if uid is None:
            return '', 'Unable to determine UID'
        return uid, dn

    def apacheLog(self, msg):
        """
        Logs the msg via the normal Apache logging
        routine.
        """
        top = self.getTopHandler()
        if top:
            top.apacheLog(msg)


    def __del__(self):
        """
        Does nothing.
        """
        #self.apacheLog("%s: delete" % (self,))
        pass


    def getFormData(self, req):
        f = None
        try:
            f = req.form_data
        except:
            pass
        if not f:
            f = util.FieldStorage(req)
            req.form_data = f
        return f

    def _destroy(self):
        """
        Breaks any cicular dependencies that may exist in a
        ReqestHandler inheritance.
        """
        if self.BeingDestroyed: return
        self.BeingDestroyed = 1
        #self.apacheLog("destroying %s ..." % (self,))
        for n, x in self.__dict__.items():
            if isinstance(x, RequestHandler):
                try:
                    #self.apacheLog("call to destroy my %s: %s" % (n, x))  
                    x.destroy()
                    x._destroy()
                except: 
                        self.apacheLog("Error deleting %s: %s %s" % (n, sys.exc_type, sys.exc_value))
                        pass
            else:
                #if not type(x) in (type(()), type([]), type(''), type(1), type({}), type(1.0), type(None),
                #                               type(1L)):
                #       self.apacheLog("Child %s is not a RequestHandler: %s %s" % (n, type(x), x))
                pass
        self.Parent = None      # this will break circular dependencies
        #self.apacheLog("done destroying %s" % (self,))

    def destroy(self):
        #override me
        pass

    def buildPaths(self, path=None):
        return
        if self.URIPath != None:    return  #already done
        self.URIPath = path
        #self.apacheLog("%s: createPaths" % (self.URIPath,))
        for n, x in self.__dict__.items():
            if isinstance(x, RequestHandler):
                p = n
                if self.URIPath != None:    p = self.URIPath + '/' + n
                x.buildPaths(p)
        
    def redirect(self, url):
        self.Parent.redirect(url)       # up to TopRequestHandler

    
class   TopRequestHandler(RequestHandler):
    """
    This specific instance of RequestHandler add functionality for Apache
    session management and provides the interface for methods indentified in
    the url to be instainiated and executed.
    """
    def __init__(self, req, redirect_stdio=1,applicationPath=None):
        """
        Initializer.
          redirect_stdio - When not 0, causes the standard output to be
              redirected to the request (req).
          applicationPath - Allows an application to add a path to cookie(s)
              created for it.  When used, multiple applications run on the same
              server will have different cookies, each holding its own session
              id.  example:  applicationPath='/myProject'
        """
        RequestHandler.__init__(self)
        self.Request = req
        if applicationPath:
            opts = req.get_options()
            opts['mod_python.session.application_path'] = applicationPath

        self.RedirectStdio = redirect_stdio
        sess = FileSession(req)
        if sess.is_new():       sess.save()
        self.ApacheSession = sess

    def newSession(self, req):
        """
        Creates a new Apache session.  The new session
        is returned to the caller.
        """
        sess = FileSession(req, 1234)
        sess.update(self.ApacheSession)
        sess.save()
        self.ApacheSession = sess
        return sess

    # we should call parseArgs, so if we over ride parseArgs
    # in a subclass, we get those args passed to the
    # function as well...
    def dispatch(self, req, fcn, relpath, args):
        """
        Invokes the provided function name (fcn).

        Checks that fcn is the last value on the
        relpath.  When so, it is  invoked as a function and passed
        the values req, *unamed, *kv.  *unamed is a list of any
        unamed arguments and *kv is a dictionary of arguments both
        are derived from args.
        Returns what every value the called function returns or apache.OK
        if the function returns None.
        """
        self.buildPaths()
        out_save = None
        if self.RedirectStdio:
            out_save = sys.stdout
            sys.stdout = req
        exc = None
        ret = None
        try:
                unnamed, dict = self.parseArgs(req)
                ret = self._processRequest(req, fcn, relpath, *tuple(unnamed), **dict)
        finally:
            if out_save:
                sys.stdout = out_save
            if ret == None:
                ret = apache.OK
            #self.apacheLog("My ref count at: %d" % (sys.getrefcount(self),))
            self.ApacheSession = None
            self._destroy()
            #self.apacheLog("My ref count: %d" % (sys.getrefcount(self),))
        return ret

    def apacheLog(self, msg):
        """
        Logs a message (msg) to the Apache log.  All messages
        are logged as a APLOG_NOTICE
        """
        self.Request.log_error(msg, apache.APLOG_NOTICE)

    def getTopHandler(self):
        """
        Returns current instance of TopRequestHandler associated
        with the class.
        """
        return self

    def _checkRoles(self, roles):
        # override me
        return True

    def getSessionData(self):
        """
        Returns current Apache session.
        """
        return self.ApacheSession
        
    def redirect(self, url):
        try:    util.redirect(self.Request, url)
        except apache.SERVER_RETURN, val:
            self.destroy()
            raise apache.SERVER_RETURN, val

    def getRequest(self):
        return self.Request

    def myUri(self, down=None):
        uri = self.scriptUri()
        if down:    uri += '/' + down
        return uri
