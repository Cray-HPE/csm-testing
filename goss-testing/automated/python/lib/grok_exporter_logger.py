#!/usr/bin/env python3
#
# MIT License
#
# (C) Copyright 2022 Hewlett Packard Enterprise Development LP
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

from .common import timestamp_string


# Simplified type hints to use for JSON-able dicts.
JSONDict = Dict[str, Any]

GROK_EXPORTER_LOG_DIR = "/opt/cray/tests/install/logs/grok_exporter"

class LogEntry:
    field_position = { "log_timestamp": 1, "Product": 2, "log_script": 3, "log_message": 4 }

    def field_order_key(field_name) -> Tuple[int, str]:
        """
        Class method that returns a value used to sort the log entry field keys.
        The first four fields are (in order) log_timestamp, Product, log_script, and log_message
        After that the remaining fields (if any) use the default ascii string sort
        """
        # The second field of the tuple is the field name string.
        # For the fixed fields, the integer in the tuple will be set to the position for that field.
        # Otherwise, the integer will be set to a fixed higher value. Thus, for these fields, their
        # names will end up being how they are sorted.
        return (LogEntry.field_position.get(field_name, len(LogEntry.field_position)+1), field_name)


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
                logger.warning(f"grok_exporter_logger.set_data_field: Field '{field_name}' "
                               f"already set to '{logdata[field_name]}'; "
                               f"overwriting it to '{field_value}'")
            logdata[field_name] = field_value

        # Generate ordered dict of the data
        ordered_data = OrderedDict(sorted(logdata.items(),
                                          key=lambda item: LogEntry.field_order_key(item[0])))

        # Generate the log string
        try:
            self.json_string = json.dumps(ordered_data)
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
