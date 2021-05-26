from configparser import ConfigParser
import yaml, os


class QEConfigFile(object):
    def __new__(cls, path=None, envVar='QENGINE_CFG'):
        path = path or os.environ.get(envVar)
        if cls is QEConfigFile:
            if path.endswith(".yaml") or path.endswith(".yml"):
                return super(QEConfigFile, cls).__new__(QEConfigFile_yaml)
            elif path.endswith(".cfg") or path.endswith(".ini"):
                return super(QEConfigFile, cls).__new__(QEConfigFile_cfg)
            else:
                raise ValueError("Unknown configuration file format: %s" % (path,))
        else:
            return super(QEConfigFile, cls).__new__(cls, path=path, envVar=envVar)
        

class   QEConfigFile_cfg(QEConfigFile):

    def __init__(self, path=None, envVar='QENGINE_CFG'):
        self.Cfg = ConfigParser()
        path = path or os.environ.get(envVar)
        if not path: return

        self.Cfg.read(path)
        self.DefaultDatabaseName = self.get("Global", "default_db")
        self.DefaultCacheTTL = self.get("Global", "default_cache_ttl", 3600)        
        self.Debug = self.get("Global", "debug", False)
        self.UseCache = self.get("Global", "use_cache", False)
        
    def get(self, section, name, default=None, required=False):
        value = default
        try:    value = self.Cfg.get(section, name)
        except:
            if required:    raise
        return value


    def cacheTTL(self, dbname, table):
        ttl = self.get(dbname, "cache_ttl", self.DefaultCacheTTL)
        try:    ttl = float(ttl)
        except: pass
        return ttl
        
    @property
    def defaultDatabaseName(self):
        if self.DefaultDatabaseName is None:
            raise KeyError("Default database name is undefined")
        return self.DefaultDatabaseName
            
    def getDBParams(self, dbname = None):
        dbname = dbname or self.defaultDatabaseName
        dict = {}
        for n, v in self.Cfg.items(dbname):
            dict[n] = v.strip()
        return dict

class QEConfigFile_yaml(QEConfigFile):

    def __init__(self, path=None, envVar='QENGINE_CFG'):
        path = path or os.environ.get(envVar)
        config = {}
        if not path:
            return

        config = yaml.load(open(path, "r"), Loader=yaml.SafeLoader)
        self.Databases = config["databases"]
        self.DefaultDatabaseName = config.get("default_database")
        self.DefaultCacheTTL = config.get("default_cache_ttl", 3600)
        self.Debug = config.get("debug", True)
        self.Config = config
        self.UseCache = config.get("use_cache", False)
        
    @property
    def defaultDatabaseName(self):
        if self.DefaultDatabaseName is None:
            raise KeyError("Default database name is undefined")
        return self.DefaultDatabaseName
    
    def getDBParams(self, dbname=None):
        dbname = dbname or self.defaultDatabaseName
        return self.Databases[dbname]
        
    def cacheTTL(self, dbname, table):
        dbparams = self.getDBParams(dbname)
        default_ttl = dbparams.get("default_cache_ttl", self.DefaultCacheTTL)
        cache_ttl_per_table_or_function = dbparams.get("cache_ttl", {})
        cache_ttl = cache_ttl_per_table_or_function.get(table, default_ttl)
        return cache_ttl
