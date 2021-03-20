FILES = InfoHandler.py  SimpleQueryHandler.py  SQEngineApp.py  Version.py \
     __init__.py     LRUCache.py  QEConfigFile.py  SQBaseHandler.py  

all:
	@echo run make from top directory

build: $(DSTTOP) 
	cp $(FILES) $(DSTTOP)
	cd $(DSTTOP); echo "Version=\"$(VERSION)\"" > Version.py

$(DSTTOP):
	mkdir -p $@
	
