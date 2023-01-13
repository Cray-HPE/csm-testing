#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2022-2023 Hewlett Packard Enterprise Development LP
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

"""
Helper functions for Goss Python automated scripts

These functions relate to generating log files to be consumed by
grok-exporter. These log files 
"""

from collections import OrderedDict
import copy
import json
import logging
from typing import Any, Dict, TextIO, Tuple

from .common import fmt_exc, stderr_print, timestamp_string


# Simplified type hints to use for JSON-able dicts.
JSONDict = Dict[str, Any]

GROK_EXPORTER_LOG_DIR = "/opt/cray/tests/install/logs/grok_exporter"

def data_to_json(obj) -> str:
    """
    We want to be able to override the formatting that is used by default by the
    Python json module. In particular, we want to avoid use of scientific notation for
    some floating point numbers (test duration in seconds, specifically). Unfortunately,
    the JSON module does not offer this as an option. Instead, this function will
    generate a JSON string from any object passed into it.
    """
    # Use the to_json method if it exists
    try:
        return obj.to_json()
    except (AttributeError, TypeError):
        # The custom method does not exist or is not callable
        pass
    # For dicts and lists we cannot call json.dumps on them, because that would not handle the case
    # where items in those containers had custom to_json methods. Fortunately, since
    # dicts and lists are the only containers supported by JSON, we just need to add some simple
    # code here to handle those.
    if isinstance(obj, dict):
        items_json_list = [f"{data_to_json(key)}: {data_to_json(value)}"
                           for key, value in obj.items()]
        return "{%s}" % ", ".join(items_json_list)
    elif isinstance(obj, list):
        items_json_list = [data_to_json(item) for item in obj]
        return "[%s]" % ", ".join(items_json_list)
    # Otherwise, just call regular json.dumps on it, since this should mean it is a primitive
    # type like int, float, str, or bool. If it is not, then the json module will raise an
    # exception, which is what we want.
    return json.dumps(obj)

class LogEntry:
    field_position = { "log_timestamp": 1, "Product": 2, "log_script": 3, "log_message": 4 }

    @classmethod
    def field_order_key(cls, field_name: str) -> Tuple[int, str]:
        """
        Class method that returns a value used to sort the log entry field keys.
        The first four fields are (in order) log_timestamp, Product, log_script, and log_message
        After that the remaining fields (if any) use the default ascii string sort
        """
        # The second field of the tuple is the field name string.
        # For the fixed fields, the integer in the tuple will be set to the position for that field.
        # Otherwise, the integer will be set to a fixed higher value. Thus, for these fields, their
        # names will end up being how they are sorted.
        return (cls.field_position.get(field_name, len(cls.field_position)+1), field_name)


    def __init__(self, message: str, script_name: str, product: str, data: JSONDict=None
                 ) -> None:
        """
        The log entry data includes the data argument (if any), updated with the following fields:
        log_timestamp
        log_message (from the message argument)
        log_script (from script_name argument)
        Product (from the product argument)
        """
        if data is None:
            logdata = dict()
        else:
            # Make a copy since we will be editing it in place
            logdata = copy.deepcopy(data)

        # Add/update fields
        updated_fields = { "log_timestamp": timestamp_string(),
                            "Product": product,
                            "log_script": script_name,
                            "log_message": message }
        for field_name, field_value in updated_fields.items():
            if field_name in logdata:
                logging.warning(f"grok_exporter_logger.set_data_field: Field '{field_name}' "
                                f"already set to '{logdata[field_name]}'; "
                                f"overwriting it to '{field_value}'")
            logdata[field_name] = field_value

        # Generate ordered dict of the data
        ordered_data = OrderedDict(sorted(logdata.items(),
                                          key=lambda item: LogEntry.field_order_key(item[0])))

        # Generate the log string
        try:
            self.json_string = data_to_json(ordered_data)
        except TypeError as exc:
            msg = f"Error encoding data for grok-exporter log. {fmt_exc(exc)}"
            logging.error(msg)
            stderr_print(msg)
            self.json_string = msg


    def to_json_str(self) -> str:
        """
        Return the JSON string representation of this dict, with the field ordering specified above
        """
        return self.json_string


def grok_exporter_log(message: str, script_name: str, outfile: TextIO,
                      data: JSONDict=None, product: str="CSM") -> None:
    """
    Add a line to the grok-exporter log file. Format is:
    <single-line JSON representation of data>
    """
    # If the outfile we are given is None, just return
    if outfile is None:
        return
    log_entry = LogEntry(message=message, script_name=script_name, product=product, data=data)
    log_string = log_entry.to_json_str()
    try:
        outfile.write(f"{log_string}\n")
        outfile.flush()
    except Exception as exc:
        msg = f"Error writing to output file. {fmt_exc(exc)}"
        logging.error(msg)
        stderr_print(msg)
