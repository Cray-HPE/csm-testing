#
# MIT License
#
# (C) Copyright 2025 Hewlett Packard Enterprise Development LP
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
import unittest
import hashlib


class SATTestCaseMeta(type):
    """
    Metaclass for SAT test cases that automatically generates a unique
    identifier for each test class based on the MD5 hash of the class name.
    """
    def __new__(mcs, name, bases, namespace):
        # Generate a unique identifier based on the class name
        class_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        namespace['unique_id'] = class_hash
        return super().__new__(mcs, name, bases, namespace)


class SATTestCase(unittest.TestCase, metaclass=SATTestCaseMeta):
    """Base class for SAT test cases.

    Each test class automatically gets a unique unique_id attribute based on
    the MD5 hash of the class name. This can be used to create unique resource
    names for tests to avoid collisions when tests are run in parallel.
    """

    # Class attribute set by SATTestCaseMeta metaclass
    unique_id: str

    pass
