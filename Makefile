# Some simple testing tasks (sorry, UNIX only).

PYTHON=venv/bin/python3
PSERVE=venv/bin/gunicorn --paste
PIP=venv/bin/pip
EI=venv/bin/easy_install
NOSE=venv/bin/nosetests
FLAKE=venv/bin/flake8
FLAGS=


env:
	python3 -m venv venv
	$(PYTHON) ./setup.py develop

dev:
	$(PIP) install flake8 nose coverage requests
	$(PYTHON) ./setup.py develop

install:
	$(PYTHON) ./setup.py install

flake:
	$(FLAKE) validator tests

test: flake
	$(NOSE) -s $(FLAGS)

vtest:
	$(NOSE) -s -v $(FLAGS)

testloop:
	while sleep 1; do $(NOSE) -s $(FLAGS); done

cov cover coverage:
	$(NOSE) -s --with-cover --cover-html --cover-html-dir ./coverage $(FLAGS)
	echo "open file://`pwd`/coverage/index.html"

clean:
	rm -rf `find . -name __pycache__`
	rm -f `find . -type f -name '*.py[co]' `
	rm -f `find . -type f -name '*~' `
	rm -f `find . -type f -name '.*~' `
	rm -f `find . -type f -name '@*' `
	rm -f `find . -type f -name '#*#' `
	rm -f `find . -type f -name '*.orig' `
	rm -f `find . -type f -name '*.rej' `
	rm -f .coverage
	rm -rf coverage
	rm -rf build


.PHONY: all build env linux run pep test vtest testloop cov clean
