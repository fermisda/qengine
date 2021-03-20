VERSION = 6.4

BUILDDIR = $(HOME)/build/qengine
TARDIR =  /tmp/$(USER)
TARFILE = $(TARDIR)/qengine_$(VERSION).tar




all:    build tarball

build:	$(BUILDDIR)
	cd src; make DSTTOP=$(BUILDDIR) VERSION=$(VERSION) build
	
tarball: $(TARDIR)
	cd $(BUILDDIR); tar cf $(TARFILE) *
	@echo 
	@echo Tarfile: $(TARFILE)
	@echo

clean:
	rm -rf $(BUILDDIR)

$(TARDIR):
	mkdir -p $@	

$(BUILDDIR):
	mkdir -p $@	



