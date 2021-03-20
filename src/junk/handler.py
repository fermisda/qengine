#
# @(#) $Id: handler.py,v 1.2 2010/05/24 19:38:49 ivm Exp $
#

"""
General methods used for communication with the Apache server. 
"""
import mod_python
from mod_python import apache
import string
import sys

def handler(req, debug=0):
    """
    This is the standard method called from apache for invoking user
    python code.  It accepts the Apache suppled request (req) and
    uses it for all required information. 

    All projects are to be laid out in their own directory within the
    document root.  He is an example directory structure:
        /.../docRoot/projectA
        /.../docRoot/projectB
        /.../docRoot/projectC
    The python files invoked by this method are expected to be in the top
    level project's directory.

    This method expects req to contain a URL would be formed as:
    
      http:/node.fnal.gov:port/projectA/PythonClass.py/mymethod

    PythonClass.py is the user supplied class you wish to invoke, mymethod
    is the name of the specific method in that class.  If no method is provided
    then 'main' is assumed. The name of the python file and the name of the
    class within it must be the same.

    The above URL would be deconstructed and its data used to:
      1.  import projectA.PythonClass
      2.  Create the class PythonClass (The module name (file name) and class
            name are expected to be the same.
      3.  Invoke the dispatch method of the class which will
            start 'mymethod'.

    Classes invoked by this utility are expected to be a child of TopRequestHandler,
    in RequestHandler.py.
    """
    #raise 'hello'
    fn = req.filename.split('/')[-1]
    package = req.filename.split('/')[-2]

    if fn[-3:] == '.py':    fn = fn[:-3]
    if debug:
        req.content_type = 'text/plain'
        req.write("module: %s\r\n" % (fn,))
        req.write("package: %s\r\n" % (package))
    path = req.path_info
    while path and path[0] == '/':  path = path[1:]
    words = path.split('/',1)
    fcn = ''
    relpath = ''
    if words:
        fcn = words[0]
        if words[1:]:
            relpath = words[1]
    if not fcn: fcn = 'main'

    module = "%s.%s" % (package,fn)
    #raise 'importing '+module
    mod = apache.import_module(module)
    #raise 'imported'
    if debug:
        req.log_error("module %s imported" % module,apache.APLOG_NOTICE)
    req.content_type = 'text/html'
    # here we expect the class to be named the same as the file.
    sess = getattr(mod,fn)(req)
    #raise 'created'
    if debug:
        req.write('Session: %s, new=%s\r\n' % (sess.id(),sess.is_new()))
        req.write("URI: %s\r\n" % (req.uri,))
        req.write("File: %s\r\n" % (req.filename,))
        req.write("args: %s\r\n" % (req.args,))
        req.write("path: %s\r\nfcn: %s\r\nrelpath: %s\r\n" % 
                (path, fcn, relpath))
        return apache.OK
    #raise 'created'
    ret = sess.dispatch(req, fcn, relpath, req.args)
    #req.write("Ref count=%d" % (sys.getrefcount(sess),))
    return ret
    
