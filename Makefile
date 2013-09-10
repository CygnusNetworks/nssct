# This Makefile is not for building or installing nssct. Use setup.py instead.
# It contains abbreviations for common tasks during development such as running
# the test suite or printing a coverage report.

PYTHON ?= python
PYTHON_COVERAGE ?= python-coverage

test:
	$(PYTHON) -m unittest2 discover -v

clean:
	rm -f .coverage
	rm -Rf build nssct.egg-info
	find . \( -name "*.pyc" -o -name "*.pyo" -o -name "*,cover" \) -delete

.coverage: .coveragerc $(wildcard nssct/*.py nssct/*/*.py)
	rm -f .coverage
	$(PYTHON_COVERAGE) run ./setup.py test

coverage:.coverage
	$(PYTHON_COVERAGE) report -m -i "nssct/*.py" -i "nssct/*/*.py"

coverage-annotate:.coverage
	find nssct -name "*.py" | xargs $(PYTHON_COVERAGE) annotate
