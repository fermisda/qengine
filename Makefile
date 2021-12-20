VERSION = 6.5

BUILDDIR = $(HOME)/build/QEngine
TARDIR =  /tmp/$(USER)
TARFILE = $(TARDIR)/QEngine_$(VERSION).tar

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



