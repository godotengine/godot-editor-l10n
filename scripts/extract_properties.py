#!/bin/python

import os
import os.path
import re
import shutil
import subprocess
import sys
from typing import Dict, Tuple
from common import get_source_files, ExtractType, Message, PropertyNameProcessor


messages_map: Dict[Tuple[str, str], Message] = {}  # (id, context) -> Message.

line_nb = False

for arg in sys.argv[1:]:
    if arg == "--with-line-nb":
        print("Enabling line numbers in the context locations.")
        line_nb = True
    else:
        sys.exit("Non supported argument '" + arg + "'. Aborting.")


if not os.path.exists("editor"):
    sys.exit("ERROR: This script should be started from the root of the Godot git repo.")

processor = PropertyNameProcessor()

main_po = """
# LANGUAGE translation of the Godot Engine editor properties.
# Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md).
# Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.
# This file is distributed under the same license as the Godot source code.
#
# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.
#
#, fuzzy
msgid ""
msgstr ""
"Project-Id-Version: Godot Engine properties\\n"
"Report-Msgid-Bugs-To: https://github.com/godotengine/godot\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8-bit\\n"\n
"""


# Regex "(?P<name>([^"\\]|\\.)*)" creates a group named `name` that matches a string.
message_patterns = {
    re.compile(r'_initial_set\("(?P<message>[^"]+?)",'): ExtractType.PROPERTY_PATH,
    re.compile(r'GLOBAL_DEF(_RST)?(_NOVAL)?(_BASIC)?\("(?P<message>[^"]+?)",'): ExtractType.PROPERTY_PATH,
    re.compile(r'EDITOR_DEF(_RST)?\("(?P<message>[^"]+?)",'): ExtractType.PROPERTY_PATH,
    re.compile(
        r'EDITOR_SETTING(_USAGE)?\(Variant::[_A-Z0-9]+, [_A-Z0-9]+, "(?P<message>[^"]+?)",'
    ): ExtractType.PROPERTY_PATH,
    re.compile(
        r"(ADD_PROPERTYI?|GLOBAL_DEF(_RST)?(_NOVAL)?(_BASIC)?|ImportOption|ExportOption)\(PropertyInfo\("
        + r"Variant::[_A-Z0-9]+"  # Name
        + r', "(?P<message>[^"]+)"'  # Type
        + r'(, [_A-Z0-9]+(, "(?P<hint_string>(?:[^"\\]|\\.)*)"(, (?P<usage>[_A-Z0-9 |]+))?)?|\))'  # [, hint[, hint string[, usage]]].
    ): ExtractType.PROPERTY_PATH,
    re.compile(r'ADD_ARRAY\("(?P<message>[^"]+)", '): ExtractType.PROPERTY_PATH,
    re.compile(r'ADD_ARRAY_COUNT(_WITH_USAGE_FLAGS)?\("(?P<message>[^"]+)", '): ExtractType.TEXT,
    re.compile(r'(ADD_GROUP|GNAME)\("(?P<message>[^"]+)", "(?P<prefix>[^"]*)"\)'): ExtractType.GROUP,
    re.compile(r'ADD_GROUP_INDENT\("(?P<message>[^"]+)", "(?P<prefix>[^"]*)", '): ExtractType.GROUP,
    re.compile(r'ADD_SUBGROUP\("(?P<message>[^"]+)", "(?P<prefix>[^"]*)"\)'): ExtractType.SUBGROUP,
    re.compile(r'ADD_SUBGROUP_INDENT\("(?P<message>[^"]+)", "(?P<prefix>[^"]*)", '): ExtractType.GROUP,
    re.compile(r'PNAME\("(?P<message>[^"]+)"\)'): ExtractType.PROPERTY_PATH,
}
theme_property_patterns = {
    re.compile(r'set_(constant|font|font_size|stylebox|color|icon)\("(?P<message>[^"]+)", '): ExtractType.PROPERTY_PATH,
}


def _is_block_translator_comment(translator_line):
    line = translator_line.strip()
    if line.find("//") == 0:
        return False
    else:
        return True


def _extract_translator_comment(line, is_block_translator_comment):
    line = line.strip()
    reached_end = False
    extracted_comment = ""

    start = line.find("TRANSLATORS:")
    if start == -1:
        start = 0
    else:
        start += len("TRANSLATORS:")

    if is_block_translator_comment:
        # If '*/' is found, then it's the end.
        if line.rfind("*/") != -1:
            extracted_comment = line[start : line.rfind("*/")]
            reached_end = True
        else:
            extracted_comment = line[start:]
    else:
        # If beginning is not '//', then it's the end.
        if line.find("//") != 0:
            reached_end = True
        else:
            start = 2 if start == 0 else start
            extracted_comment = line[start:]

    return (not reached_end, extracted_comment)


def process_file(f, fname):
    l = f.readline()
    lc = 1
    reading_translator_comment = False
    is_block_translator_comment = False
    translator_comment = ""
    current_group = ""
    current_subgroup = ""

    patterns = message_patterns
    if os.path.basename(fname) == "default_theme.cpp":
        patterns = {**message_patterns, **theme_property_patterns}

    while l:

        # Detect translator comments.
        if not reading_translator_comment and l.find("TRANSLATORS:") != -1:
            reading_translator_comment = True
            is_block_translator_comment = _is_block_translator_comment(l)
            translator_comment = ""

        # Gather translator comments. It will be gathered for the next translation function.
        if reading_translator_comment:
            reading_translator_comment, extracted_comment = _extract_translator_comment(l, is_block_translator_comment)
            if extracted_comment != "":
                translator_comment += extracted_comment + "\n"
            if not reading_translator_comment:
                translator_comment = translator_comment[:-1]  # Remove extra \n at the end.

        if not reading_translator_comment:
            for pattern, extract_type in patterns.items():
                for m in pattern.finditer(l):
                    location = os.path.relpath(fname).replace("\\", "/")
                    if line_nb:
                        location += ":" + str(lc)

                    captures = m.groupdict("")
                    msg = captures.get("message", "")
                    msg_plural = captures.get("plural_message", "")
                    msgctx = captures.get("context", "")

                    if extract_type == ExtractType.TEXT:
                        _add_message(msg, msg_plural, msgctx, location, translator_comment)
                    elif extract_type == ExtractType.PROPERTY_PATH:
                        usage_string = captures.get("usage") or "PROPERTY_USAGE_DEFAULT"
                        usages = [e.strip() for e in usage_string.split("|")]

                        if "PROPERTY_USAGE_GROUP" in usages:
                            _add_message(msg, msg_plural, msgctx, location, translator_comment)
                            current_group = captures["hint_string"]
                            current_subgroup = ""
                            continue

                        # Ignore properties that are not meant to be displayed in the editor.
                        if "PROPERTY_USAGE_NO_EDITOR" in usages:
                            continue
                        if "PROPERTY_USAGE_DEFAULT" not in usages and "PROPERTY_USAGE_EDITOR" not in usages:
                            continue

                        if current_subgroup:
                            if msg.startswith(current_subgroup):
                                msg = msg[len(current_subgroup) :]
                            elif current_subgroup.startswith(msg):
                                pass  # Keep this as-is. See EditorInspector::update_tree().
                            else:
                                current_subgroup = ""
                        elif current_group:
                            if msg.startswith(current_group):
                                msg = msg[len(current_group) :]
                            elif current_group.startswith(msg):
                                pass  # Keep this as-is. See EditorInspector::update_tree().
                            else:
                                current_group = ""
                                current_subgroup = ""

                        if "." in msg:  # Strip feature tag.
                            msg = msg.split(".", 1)[0]
                        for part in msg.split("/"):
                            _add_message(processor.process_name(part), msg_plural, msgctx, location, translator_comment)
                    elif extract_type == ExtractType.GROUP:
                        _add_message(msg, msg_plural, msgctx, location, translator_comment)
                        current_group = captures["prefix"]
                        current_subgroup = ""
                    elif extract_type == ExtractType.SUBGROUP:
                        _add_message(msg, msg_plural, msgctx, location, translator_comment)
                        current_subgroup = captures["prefix"]
            translator_comment = ""

        l = f.readline()
        lc += 1


def _add_message(msg, msg_plural, msgctx, location, translator_comment):
    key = (msg, msgctx)
    message = messages_map.get(key)
    if not message:
        message = Message()
        message.msgid = msg
        message.msgid_plural = msg_plural
        message.msgctxt = msgctx
        message.locations = []
        message.comments = []
        messages_map[key] = message
    if location not in message.locations:
        message.locations.append(location)
    if translator_comment and translator_comment not in message.comments:
        message.comments.append(translator_comment)


print("Updating the properties.pot template...")

for fname in get_source_files():
    with open(fname, "r", encoding="utf8") as f:
        process_file(f, fname)

main_po += "\n\n".join(message.format() for message in messages_map.values())

with open("properties.pot", "w") as f:
    f.write(main_po)

if os.name == "posix":
    print("Wrapping template at 79 characters for compatibility with Weblate.")
    os.system("msgmerge -w79 properties.pot properties.pot > properties.pot.wrap")
    shutil.move("properties.pot.wrap", "properties.pot")

shutil.move("properties.pot", "../properties/properties.pot")

# TODO: Make that in a portable way, if we care; if not, kudos to Unix users
if os.name == "posix":
    os.chdir("..")
    added = subprocess.check_output(
        r"git diff properties/properties.pot | grep \+msgid | wc -l", shell=True
    )
    removed = subprocess.check_output(
        r"git diff properties/properties.pot | grep \\\-msgid | wc -l", shell=True
    )
    print("\n# Template changes compared to the staged status:")
    print("#   Additions: %s msgids.\n#   Deletions: %s msgids." % (int(added), int(removed)))
