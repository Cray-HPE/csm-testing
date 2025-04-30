#
# MIT License
#
# (C) Copyright 2019-2025 Hewlett Packard Enterprise Development LP
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
ifeq ($(NAME),)
NAME := $(shell basename $(shell pwd))
endif

ifeq ($(ARCH),)
export ARCH := noarch
endif

ifeq ($(VERSION),)
VERSION := $(shell git describe --tags | tr -s '-' '~' | sed 's/^v//')
endif

SIMPLE_VERSION := $(shell echo $(VERSION) | grep -Eo '^[0-9]+[.][0-9]+[.][0-9]+')

ifeq ($(PY_VERSION),)
export PY_VERSION := 3.6
endif

ifeq ($(PY_BIN_PATH),)
export PY_BIN_PATH := /usr/bin/python$(PY_VERSION)
endif

PYTHON_BIN := $(shell basename $(PY_BIN_PATH))

SPEC_FILES := ${NAME}.spec ${NAME}-internal.spec
STANDARD_SPEC := ${NAME}.spec
INTERNAL_SPEC := ${NAME}-internal.spec
SOURCE_NAME_STANDARD := ${NAME}-${VERSION}
SOURCE_NAME_INTERNAL := ${NAME}-internal-${VERSION}

BUILD_DIR ?= $(PWD)/dist/rpmbuild
SOURCE_PATH_STANDARD := ${BUILD_DIR}/SOURCES/${SOURCE_NAME_STANDARD}.tar.bz2
SOURCE_PATH_INTERNAL := ${BUILD_DIR}/SOURCES/${SOURCE_NAME_INTERNAL}.tar.bz2
PYLINT_VENV_DIR := pylint-venv
PYLINT_VENV_PYBIN := $(PYLINT_VENV_DIR)/bin/python3
MIN_PYLINT_RATING ?= 9.3

rpm: rpm_all

rpm_all: rpm_package_source rpm_build_source rpm_build

pymod:
	SIMPLE_VERSION=$(SIMPLE_VERSION) ./update-pyproject.sh
	$(PY_BIN_PATH) --version
	$(PY_BIN_PATH) -m pip install --upgrade --user --no-cache-dir --upgrade-strategy=eager pip build setuptools wheel
	$(PY_BIN_PATH) -m pip list --format freeze
	$(PY_BIN_PATH) -m build --wheel
	cp ./dist/csm_testing*.whl .

pylint:
	$(PY_BIN_PATH) --version
	$(PY_BIN_PATH) -m venv $(PYLINT_VENV_DIR)
	$(PYLINT_VENV_PYBIN) -m pip install --upgrade --no-cache pip
	./update-pylint-requirements.sh
	$(PYLINT_VENV_PYBIN) -m pip install --disable-pip-version-check --no-cache -r pylint-requirements.txt pylint csm_testing*.whl
	$(PYLINT_VENV_PYBIN) -m pip list --format freeze
	$(PYLINT_VENV_PYBIN) -m pylint --errors-only csm_testing
	$(PYLINT_VENV_PYBIN) -m pylint --fail-under $(MIN_PYLINT_RATING) csm_testing

prepare:
	@echo $(NAME)
	rm -rf $(BUILD_DIR)
	mkdir -p $(BUILD_DIR)/SPECS $(BUILD_DIR)/SOURCES
	cp $(SPEC_FILES) $(BUILD_DIR)/SPECS/

rpm_package_source: rpm_package_source_standard rpm_package_source_internal

rpm_package_source_standard:
	tar --transform 'flags=r;s,^,/$(SOURCE_NAME_STANDARD)/,' --exclude ./.nox --exclude .git --exclude ./build --exclude ./'$(PYLINT_VENV_DIR)' --exclude ./dist --exclude ./$(SOURCE_NAME_STANDARD).tar.bz2 -cvjf $(SOURCE_PATH_STANDARD) .

rpm_package_source_internal:
	tar --transform 'flags=r;s,^,/$(SOURCE_NAME_INTERNAL)/,' --exclude ./.nox --exclude .git --exclude ./build --exclude ./'$(PYLINT_VENV_DIR)' --exclude ./dist --exclude ./$(SOURCE_NAME_INTERNAL).tar.bz2 -cvjf $(SOURCE_PATH_INTERNAL) .

rpm_build_source: rpm_build_source_standard rpm_build_source_internal

rpm_build_source_standard:
	rpmbuild -vv -bs $(BUILD_DIR)/SPECS/$(STANDARD_SPEC) --target ${ARCH} --define "_topdir $(BUILD_DIR)"

rpm_build_source_internal:
	rpmbuild -vv -bs $(BUILD_DIR)/SPECS/$(INTERNAL_SPEC) --target ${ARCH} --define "_topdir $(BUILD_DIR)"

rpm_build: rpm_build_standard rpm_build_internal

rpm_build_standard: 
	rpmbuild -vv -ba $(BUILD_DIR)/SPECS/$(STANDARD_SPEC) --target ${ARCH} --define "_topdir $(BUILD_DIR)"

rpm_build_internal:
	rpmbuild -vv -ba $(BUILD_DIR)/SPECS/$(INTERNAL_SPEC) --target ${ARCH} --define "_topdir $(BUILD_DIR)"

