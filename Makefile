project := opentracing_instrumentation

pytest := PYTHONDONTWRITEBYTECODE=1 py.test --tb short -rxs \
	--cov-config .coveragerc --cov $(project) tests

html_report := --cov-report=html
test_args := --cov-report xml --cov-report term-missing

.PHONY: clean-pyc clean-build docs clean
.DEFAULT_GOAL : help

help:
	@echo "bootstrap - initialize local environement for development. Requires virtualenv."
	@echo "clean - remove all build, test, coverage and Python artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "clean-test - remove test and coverage artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
	@echo "coverage - check code coverage quickly with the default Python"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "dist - package"
	@echo "install - install the package to the active Python's site-packages"

check-virtualenv:
	@[ -d env ] || echo "Please run 'virtualenv env' first"
	@[ -d env ] || exit 1

bootstrap: check-virtualenv install-deps

install-deps:
	pip install -r requirements.txt
	pip install -r requirements-test.txt
	python setup.py develop

install-ci: install-deps

clean: clean-build clean-pyc clean-test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -rf {} +

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:
	rm -f .coverage
	rm -fr htmlcov/

lint:
	flake8 $(project)

test:
	$(pytest) $(test_args)

coverage: test
	coverage html
	open htmlcov/index.html

docs:
	$(MAKE) -C docs clean
	$(MAKE) -C docs html

release: clean
	python setup.py sdist upload
	python setup.py bdist_wheel upload

dist: clean
	python setup.py sdist
	python setup.py bdist_wheel
	ls -l dist

install: install-deps
	python setup.py install
