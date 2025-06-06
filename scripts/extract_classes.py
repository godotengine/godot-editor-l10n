#!/usr/bin/env python3

import argparse
import os
import shutil
import textwrap
from collections import OrderedDict

EXTRACT_ATTRIBS = ["deprecated", "experimental"]
EXTRACT_TAGS = ["description", "brief_description", "member", "constant", "theme_item", "link"]
HEADER = """\
# LANGUAGE translation of the Godot Engine class reference.
# Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).
# Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.
# This file is distributed under the same license as the Godot source code.
#
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
#
#, fuzzy
msgid ""
msgstr ""
"Project-Id-Version: Godot Engine class reference\\n"
"Report-Msgid-Bugs-To: https://github.com/godotengine/godot\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8-bit\\n"

"""
# Some strings used by `doc/tools/make_rst.py` (godotengine/godot repo) are normally part of the editor translations,
# so we need to include them manually here for the online docs.
BASE_STRINGS = [
    "All classes",
    "Globals",
    "Nodes",
    "Resources",
    "Editor-only",
    "Other objects",
    "Variant types",
    "Description",
    "Tutorials",
    "Properties",
    "Constructors",
    "Methods",
    "Operators",
    "Theme Properties",
    "Signals",
    "Enumerations",
    "Constants",
    "Annotations",
    "Property Descriptions",
    "Constructor Descriptions",
    "Method Descriptions",
    "Operator Descriptions",
    "Theme Property Descriptions",
    "Inherits:",
    "Inherited By:",
    "(overrides %s)",
    "Default",
    "Setter",
    "value",
    "Getter",
    "This method should typically be overridden by the user to have any effect.",
    "This method has no side effects. It doesn't modify any of the instance's member variables.",
    "This method accepts any number of arguments after the ones described here.",
    "This method is used to construct a type.",
    "This method doesn't need an instance to be called, so it can be called directly using the class name.",
    "This method describes a valid operator to use with this type as left-hand operand.",
    "This value is an integer composed as a bitmask of the following flags.",
    "No return value.",
    "There is currently no description for this class. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this signal. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this enum. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this constant. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this annotation. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this property. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this constructor. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this method. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this operator. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There is currently no description for this theme property. Please help us by :ref:`contributing one <doc_updating_the_class_reference>`!",
    "There are notable differences when using this API with C#. See :ref:`doc_c_sharp_differences` for more information.",
    "Deprecated:",
    "Experimental:",
    "This signal may be changed or removed in future versions.",
    "This constant may be changed or removed in future versions.",
    "This property may be changed or removed in future versions.",
    "This constructor may be changed or removed in future versions.",
    "This method may be changed or removed in future versions.",
    "This operator may be changed or removed in future versions.",
    "This theme property may be changed or removed in future versions.",
]

## <xml-line-number-hack from="https://stackoverflow.com/a/36430270/10846399">
import sys

sys.modules["_elementtree"] = None  # type: ignore
import xml.etree.ElementTree as ET

## override the parser to get the line number
class LineNumberingParser(ET.XMLParser):
    def _start(self, *args, **kwargs):
        ## Here we assume the default XML parser which is expat
        ## and copy its element position attributes into output Elements
        element = super(self.__class__, self)._start(*args, **kwargs)
        element._start_line_number = self.parser.CurrentLineNumber
        element._start_column_number = self.parser.CurrentColumnNumber
        element._start_byte_index = self.parser.CurrentByteIndex
        return element

    def _end(self, *args, **kwargs):
        element = super(self.__class__, self)._end(*args, **kwargs)
        element._end_line_number = self.parser.CurrentLineNumber
        element._end_column_number = self.parser.CurrentColumnNumber
        element._end_byte_index = self.parser.CurrentByteIndex
        return element


## </xml-line-number-hack>


class Desc:
    def __init__(self, line_no, msg, desc_list=None):
        ## line_no   : the line number where the desc is
        ## msg       : the description string
        ## desc_list : the DescList it belongs to
        self.line_no = line_no
        self.msg = msg
        self.desc_list = desc_list


class DescList:
    def __init__(self, doc, path):
        ## doc  : root xml element of the document
        ## path : file path of the xml document
        ## list : list of Desc objects for this document
        self.doc = doc
        self.path = path
        self.list = []


def print_error(error):
    print("ERROR: {}".format(error))


## build classes with xml elements recursively
def _collect_classes_dir(path, classes):
    if not os.path.isdir(path):
        print_error("Invalid directory path: {}".format(path))
        exit(1)
    for _dir in map(lambda dir: os.path.join(path, dir), os.listdir(path)):
        if os.path.isdir(_dir):
            _collect_classes_dir(_dir, classes)
        elif os.path.isfile(_dir):
            if not _dir.endswith(".xml"):
                # print("Got non-.xml file '{}', skipping.".format(path))
                continue
            _collect_classes_file(_dir, classes)


## opens a file and parse xml add to classes
def _collect_classes_file(path, classes):
    if not os.path.isfile(path) or not path.endswith(".xml"):
        print_error("Invalid xml file path: {}".format(path))
        exit(1)
    print("Collecting file: {}".format(os.path.basename(path)))

    try:
        tree = ET.parse(path, parser=LineNumberingParser())
    except ET.ParseError as e:
        print_error("Parse error reading file '{}': {}".format(path, e))
        exit(1)

    doc = tree.getroot()

    if "name" in doc.attrib:
        name = doc.attrib["name"]
        if name in classes:
            print_error("Duplicate class {} at path {}".format(name, path))
            exit(1)
        classes[name] = DescList(doc, path)
    else:
        print_error("Unknown XML file {}, skipping".format(path))


def _c_escape(string):
    result = ""
    for i in range(len(string)):
        c = string[i]
        if c == "\n":
            c = "\\n"
        if c == '"':
            c = '\\"'
        if c == "\\":
            c = "\\\\"
        if c == "\t":
            c = "\\t"
        result += c
    return result


## make catalog strings from xml elements
def _make_translation_catalog(classes):
    unique_msgs = OrderedDict()
    for class_name in classes:
        desc_list = classes[class_name]
        for elem in desc_list.doc.iter():
            for attrib_name in elem.attrib:
                if attrib_name not in EXTRACT_ATTRIBS:
                    continue
                attrib_value = elem.attrib[attrib_name]
                if not attrib_value:
                    continue
                line_no = elem._start_line_number
                attrib_msg = _c_escape(attrib_value)
                desc_obj = Desc(line_no, attrib_msg, desc_list)
                desc_list.list.append(desc_obj)

                if attrib_msg not in unique_msgs:
                    unique_msgs[attrib_msg] = [desc_obj]
                else:
                    unique_msgs[attrib_msg].append(desc_obj)

            if elem.tag in EXTRACT_TAGS:
                elem_text = elem.text
                if elem.tag == "link":
                    elem_text = elem.attrib["title"] if "title" in elem.attrib else ""
                if not elem_text or len(elem_text) == 0:
                    continue

                line_no = elem._start_line_number if elem_text[0] != "\n" else elem._start_line_number + 1
                # The magic happens here, we remove XML indentation (keeping potential indentation in code blocks),
                # and escape special characters. The actual clean POT format with wrapping is handled later with msgmerge.
                desc_msg = _c_escape(textwrap.dedent(elem_text).strip())
                desc_obj = Desc(line_no, desc_msg, desc_list)
                desc_list.list.append(desc_obj)

                if desc_msg not in unique_msgs:
                    unique_msgs[desc_msg] = [desc_obj]
                else:
                    unique_msgs[desc_msg].append(desc_obj)
    return unique_msgs


## generate the catalog file
def _generate_translation_catalog_file(unique_msgs, output, location_line=False):
    with open(output, "w", encoding="utf8") as f:
        f.write(HEADER)
        for msg in BASE_STRINGS:
            f.write("#: doc/tools/make_rst.py\n")
            f.write('msgid "{}"\n'.format(msg))
            f.write('msgstr ""\n\n')
        for msg in unique_msgs:
            if len(msg) == 0 or msg in BASE_STRINGS:
                continue

            f.write("#:")
            desc_list = unique_msgs[msg]
            for desc in desc_list:
                path = desc.desc_list.path.replace("\\", "/")
                if path.startswith("./"):
                    path = path[2:]
                if location_line:  # Can be skipped as diffs on line numbers are spammy.
                    f.write(" {}:{}".format(path, desc.line_no))
                else:
                    f.write(" {}".format(path))
            f.write("\n")

            f.write('msgid "{}"\n'.format(msg))
            f.write('msgstr ""\n\n')

    print("Wrapping template at 80 characters for compatibility with Weblate.")
    os.system("msgmerge -w80 {0} {0} > {0}.wrap".format(output))
    shutil.move("{}.wrap".format(output), output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path", "-p", nargs="+", default=".", help="The directory or directories containing XML files to collect."
    )
    parser.add_argument("--output", "-o", default="translation_catalog.pot", help="The path to the output file.")
    args = parser.parse_args()

    output = os.path.abspath(args.output)
    if not os.path.isdir(os.path.dirname(output)) or not output.endswith(".pot"):
        print_error("Invalid output path: {}".format(output))
        exit(1)

    classes = OrderedDict()
    for path in args.path:
        if not os.path.isdir(path):
            print_error("Invalid working directory path: {}".format(path))
            exit(1)

        print("\nCurrent working dir: {}".format(path))

        path_classes = OrderedDict()  ## dictionary of key=class_name, value=DescList objects
        _collect_classes_dir(path, path_classes)
        classes.update(path_classes)

    classes = OrderedDict(sorted(classes.items(), key=lambda kv: kv[0].lower()))
    unique_msgs = _make_translation_catalog(classes)
    _generate_translation_catalog_file(unique_msgs, output)


if __name__ == "__main__":
    main()
