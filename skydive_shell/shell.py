import argparse
import json
import logging
import functools
import operator
import os

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.history import FileHistory

from lark import Lark, UnexpectedInput, InlineTransformer

from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import TerminalFormatter

from . import api


# We explicitly define all terminal in order to predict their name for
# the completion mapping
skydive_grammar = """
start : gremlin                  -> gremlin
      | _SET " " _option         -> set
      | _HELP                    -> help
      | _capture                 -> capture

_capture : _CAPTURE " " CAPTURE_LIST
         | _CAPTURE " " CAPTURE_CREATE " " gremlin
         | _CAPTURE " " CAPTURE_DELETE " " CAPTURE_UUID
gremlin : G "." v ("." expr)?

v : V ")"
  | V STRING ")"

expr : expr "." expr
     | traversal

traversal : HAS HAS_METADATA ("," HAS_VALUE)? ")"
          | OUT
          | KEYS
          | COUNT
          | VALUES "(" HAS_METADATA ")"
          | DEDUP
          | LIMIT "(" NUMBER ")"
          | FLOWS

_option : _FORMAT " " format
!format : _PRETTY
        | _JSON

HAS_METADATA : STRING
HAS_VALUE : STRING
CAPTURE_UUID : /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/

G : "g"
V : "v("
HAS : "has("
VALUES : "values"
DEDUP : "dedup()"
FLOWS : "flows()"
LIMIT : "limit"
OUT : "out()"
KEYS : "keys()"
COUNT : "count()"
_PRETTY : "pretty"
_JSON : "json"
_SET : ":set"
_FORMAT : "format"
_HELP : ":?"
_CAPTURE: "capture"
CAPTURE_LIST: "list"
CAPTURE_CREATE: "create"
CAPTURE_DELETE: "delete"

%import common.ESCAPED_STRING   -> STRING
%import common.NUMBER
"""

larkParser = Lark(skydive_grammar)

# This is to generate completions based on parsing errors
token_mapping = {"__COMMA": ",",
                 "__RPAR": ")",
                 "__LPAR": "(",
                 "__DOT": ".",

                 "_CAPTURE": "capture",
                 "CAPTURE_LIST": "list",
                 "CAPTURE_CREATE": "create",
                 "CAPTURE_DELETE": "delete",
                 "V": "v(",
                 "HAS": "has(",
                 "VALUES": "values",
                 "DEDUP": "dedup()",
                 "FLOWS": "flows()",
                 "LIMIT": "limit",
                 "KEYS": "keys()",
                 "COUNT": "count()",
                 "G": "g",
                 "_SET": ":set",
                 "_HELP": ":?",
                 "_FORMAT": "format",
                 "_PRETTY": "pretty",
                 "_JSON": "json",
                 "OUT": "out()"}


def help():
    msg = (
        "--- The Skydive shell help ---\n"
        " > :?   for infinite recursion\n"
        " > :set to set contextual options\n"
        " > g    for Skydive query (Gremlin dialect)\n"
    )
    print(msg)


# We iterate on the expression to find a valid Gremlin expression by removing
# each time the last character.
# For instance:
# find_valid_expr("g.v().has(") returns ("g.v()", ".has(")
def find_valid_expr(expr):
    for i in range(len(expr), 1, -1):
        try:
            larkParser.parse(expr[:i])
        except:
            continue
        # Really hacky!!! this is to remove "capture list g."
        base = expr[:i].split(" ")[-1]
        return base, expr[i+1:]
    return "", ""


# We use parser errors with expected TOKEN to generate the completion
# list.
def get_completions(endpoint, query):
    completions = []
    position = 0
    try:
        # We add a space at the end of the query to let the parser
        # generates an UnexpectedInput error in order to get back
        # useful parsing information
        larkParser.parse(query + "\0")
    except UnexpectedInput as e:
        logging.debug("UnexpectedInput: %s" % e)
        base, partial = (find_valid_expr(query))
        position = e.column - len(query)
        if "HAS_METADATA" in e.allowed:
            # To remove the introduced leading space
            partial = e.context[:-1]
            request = format("%s.keys()" % base)
            completions = api.gremlin_query_list_string(endpoint, request)
        elif "HAS_VALUE" in e.allowed:
            # To remove the introduced leading space
            partial = e.context[:-1]
            base, last = (find_valid_expr(query[0:e.column-1]))
            request = base + "." + last.replace("has", "values") + ")"
            completions = api.gremlin_query_list_string(endpoint, request)
        elif "CAPTURE_UUID" in e.allowed:
            j = json.loads(api.request(
                "http://%s/api/capture" % endpoint))
            completions = j.keys()
            pass
        elif "STRING" in e.allowed:
            pass
        else:
            completions = [token_mapping[c] for c in e.allowed
                           if token_mapping.get(c)]

        completions = [c for c in completions if c.startswith(partial)]

    return position, sorted(set(completions))


class SkydiveValidator(Validator):
    def validate(self, document):
        if document.text == "":
            raise ValidationError(message='Input cannot be empty!',
                                  cursor_position=len(document.text))
        try:
            larkParser.parse(document.text)
        except:
            raise ValidationError(message='This is a non valid Gremlin expression',
                                  cursor_position=len(document.text))


class SkydiveCompleter(Completer):
    def __init__(self, skydive_url):
        self._skydive_url = skydive_url

    def get_completions(self, document, complete_event):
        position, c = get_completions(self._skydive_url,
                                      document.text_before_cursor)
        return [Completion(i, start_position=position) for i in c]


def format_json(objs):
    j = json.dumps(objs, indent=2, sort_keys=True)
    return highlight(j, JsonLexer(), TerminalFormatter())


# We fallback on format_json if objs can not be pretty printed
def format_pretty(objs):
    fields = ("Name", "Host", "Metadata.Name", "Metadata.Type")
    short = []

    def get_by_path(d, path):
        try:
            return functools.reduce(operator.getitem, path.split("."), d)
        except KeyError:
            return None

    if objs.__class__ is list:
        for o in objs:
            # If object is not a node, we don't  it
            if o.__class__ != dict or not o.get("ID"):
                return format_json(objs)
            short += ["{} {}".format("ID", o["ID"])]
            short += ([" {: <15} {}".format(p, get_by_path(o, p))
                       for p in fields if get_by_path(o, p) is not None])
    return "\n".join(short)


class ShellTree(InlineTransformer):
    formatter = "json"

    def capture(self, *args):
        return ("capture", args[0])

    def help(self, *args): return ("help", None)

    def set(self, a): return ("set", a)

    def gremlin(self, *args): return ("gremlin", None)

    def format(self, arg):
        return "format_" + arg


def main():
    parser = argparse.ArgumentParser(
         description='Skydive Network Analyzer Shell')
    parser.add_argument('--host', default="localhost",
                        help='Skydive analyzer host')
    parser.add_argument('--port', default="8082",
                        help='Skydive analyzer port')
    parser.add_argument('--debug', default=False,
                        action="store_true",
                        help='Enable debug mode')
    parser.add_argument('--disable-validation', default=False,
                        action="store_true",
                        help='Disable Gremlin query validation')
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    skydive_url = "%s:%s" % (args.host, args.port)
    print("Using Skydive Analyzer %s:%s" % (args.host, args.port))
    print("Type :? for help")

    conf_dir = os.path.expanduser('~/.config/skydive-shell/')
    os.makedirs(conf_dir, exist_ok=True)
    history = FileHistory(os.path.os.path.join(conf_dir, "history"))

    validator = SkydiveValidator()
    if args.disable_validation:
        print("WARINING: ':set' commamnds are not supported when 'disable-validation' is set")
        validator = None

    formatFunctionName = format_json
    while True:
        query = prompt('> ',
                       completer=SkydiveCompleter(skydive_url),
                       validator=validator,
                       history=history,
                       complete_while_typing=False)

        tree = larkParser.parse(query)
        logging.debug("Tree: %s" % tree)
        action, arg = ShellTree().transform(tree)
        if action == "set":
            formatFunctionName = eval(arg)
        elif action == "help":
            help()
        elif action == "capture" and arg == "list":
            r = api.capture_list(skydive_url)
            j = json.loads(r)
            print(format_json(j))
        elif action == "capture" and arg == "create":
            # Hacky. We should use the tree to rebuild the gremlin
            # expression...
            q = query.split(" ", 2)[2]
            r = api.capture_create(skydive_url, q)
            j = json.loads(r)
            print(format_json(j))
        elif action == "capture" and arg == "delete":
            capture_id = query.split(" ", 2)[2]
            api.capture_delete(skydive_url, capture_id)
        else:
            r = api.gremlin_query(skydive_url, query)
            j = json.loads(r)
            print(formatFunctionName(j))
