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

from lark import Lark, UnexpectedInput, Transformer, ParseError
from lark.reconstruct import Reconstructor

from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import TerminalFormatter

from skydive.rest.client import RESTClient, BadRequest


# We explicitly define all terminal in order to predict their name for
# the completion mapping
skydive_grammar = """
start : gremlin                 -> gremlin_query
      | _SET " " _option
      | _HELP                    -> help
      | capture
      | _EXIT                    -> exit

capture : capture_list
        | capture_delete
        | capture_create

capture_list : CAPTURE " " CAPTURE_LIST
capture_create : CAPTURE " " CAPTURE_CREATE " " gremlin
capture_delete : CAPTURE " " CAPTURE_DELETE " " CAPTURE_UUID

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
!format : _PRETTY -> pretty
        | _JSON   -> json

HAS_METADATA : STRING
HAS_VALUE : STRING
CAPTURE_UUID : /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/

%import common.ESCAPED_STRING   -> STRING
%import common.NUMBER
"""

# The grammar and tokens are split in order to be able to generate
# completion items from tokens
skydive_tokens = """
G : "G"
V : "V("
HAS : "Has("
VALUES : "Values"
DEDUP : "Dedup()"
FLOWS : "Flows()"
LIMIT : "Limit"
OUT : "Out()"
KEYS : "Keys()"
COUNT : "Count()"
_PRETTY : "pretty"
_JSON : "json"
_SET : "set"
_FORMAT : "format"
_HELP : "?"
CAPTURE: "capture"
CAPTURE_LIST: "list"
CAPTURE_CREATE: "create"
CAPTURE_DELETE: "delete"
_EXIT : "exit"
"""

larkParser = Lark(skydive_grammar + skydive_tokens)


# From the tokens string, generates a completion dict
def token_to_completions(tokens):
    c = {}
    for i in tokens.split("\n"):
        t = i.replace(" ", "").replace('"', '').split(":")
        if len(t) == 2:
            c.update({t[0]: t[1]})
    return c

# This is to generate completions based on parsing errors
token_mapping = {"__COMMA": ",",
                 "__RPAR": ")",
                 "__LPAR": "(",
                 "__DOT": "."}
token_mapping.update(token_to_completions(skydive_tokens))


def help():
    msg = (
        "--- The Skydive Shell help ---\n"
        " > ?          for infinite recursion\n"
        " > set        to set contextual options\n"
        " > g          for Skydive query (Gremlin dialect)\n"
        " > capture    manage Skydive capture\n"
    )
    print(msg)


# We iterate on the expression to find a valid Gremlin expression by removing
# each time the last character.
# For instance:
# find_valid_expr("g.v().has(") returns ("g.v()", ".has(")
def _find_valid_expr(expr):
    tree = None
    for i in range(len(expr), 1, -1):
        try:
            tree = larkParser.parse(expr[:i])
        except (UnexpectedInput, ParseError):
            continue
        base = expr[:i]
        return tree, base, expr[i+1:]
    return tree, "", ""


def find_valid_gremlin_expr(expr):
    tree, base, partial = _find_valid_expr(expr)
    if tree is None:
        return "", partial
    try:
        g = next(tree.find_data("gremlin"))
    except StopIteration:
        return "", partial
    return Reconstructor(larkParser).reconstruct(g), partial


# Generates a list of string (if possible) from the skydive_query
# output.
def gremlin_query_list_string(skydive_client, query):
    objs = skydive_client.lookup(query)
    return ['"%s"' % a for a in objs if a.__class__ == str]


# We use parser errors with expected TOKEN to generate the completion
# list.
def get_completions(skydive_client, query):
    completions = []
    position = 0
    try:
        # We add a eol at the end of the query to let the parser
        # generates an UnexpectedInput error in order to get back
        # useful parsing information
        larkParser.parse(query + "\0")
    except UnexpectedInput as e:
        logging.debug("UnexpectedInput: %s" % e)
        partial = ""
        position = e.column - len(query)
        if "HAS_METADATA" in e.allowed:
            gremlin, partial = find_valid_gremlin_expr(query)
            # To remove the introduced leading character
            # Be careful, this only work if we complete the end of the query
            partial = query[e.column:]
            request = format("%s.keys()" % gremlin)
            completions = gremlin_query_list_string(skydive_client, request)
        elif "HAS_VALUE" in e.allowed:
            gremlin, partial = find_valid_gremlin_expr(query)
            # To remove the introduced leading introduced character...
            # Be careful, this only work if we complete the end of the query
            partial = query[e.column:]
            gremlin, last = (find_valid_gremlin_expr(query[0:e.column-1]))
            request = gremlin + "." + last.replace("Has", "values") + ")"
            completions = gremlin_query_list_string(skydive_client, request)
        elif "CAPTURE_UUID" in e.allowed:
            j = skydive_client.capture_list()
            completions = j.keys()
        elif "STRING" in e.allowed:
            pass
        else:
            partial = query[e.column:]
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
    def __init__(self, skydive_client):
        self._skydive_client = skydive_client

    def get_completions(self, document, complete_event):
        position, c = get_completions(self._skydive_client,
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


class Eval(Transformer):
    formatFunction = format_json

    def __init__(self, skydive_client):
        self._skydive_client = skydive_client

    def exit(self, *args): exit(0)

    def capture_create(self, args):
        g = args[2]
        q = Reconstructor(larkParser).reconstruct(g)
        r = self._skydive_client.capture_create(q)
        print(format_json(r))

    def capture_list(self, args):
        r = self._skydive_client.capture_list()
        print(format_json(r))

    def capture_delete(self, args):
        uuid = args[2]
        self._skydive_client.capture_delete(uuid)

    def help(self, *args): help()

    def pretty(self, data):
        print("Set format pretty")
        Eval.formatFunction = format_pretty

    def json(self, data):
        print("Set format json")
        Eval.formatFunction = format_json

    def gremlin_query(self, *args):
        q = Reconstructor(larkParser).reconstruct(args[0][0])
        r = self._skydive_client.lookup(q)
        print(Eval.formatFunction(r))


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
    skydive_client = RESTClient(skydive_url)

    print("Using Skydive Analyzer %s:%s" % (args.host, args.port))
    print("Type ? for help, CTRL-d for exiting")

    conf_dir = os.path.expanduser('~/.config/skydive-shell/')
    os.makedirs(conf_dir, exist_ok=True)
    history = FileHistory(os.path.os.path.join(conf_dir, "history"))

    validator = SkydiveValidator()
    if args.disable_validation:
        print("WARINING: ':set' commamnds are not supported when 'disable-validation' is set")
        validator = None

    while True:
        try:
            query = prompt('> ',
                           completer=SkydiveCompleter(skydive_client),
                           validator=validator,
                           history=history,
                           complete_while_typing=True)
        except KeyboardInterrupt:
            continue
        except EOFError:
            print("Exiting")
            exit(0)

        tree = larkParser.parse(query)
        logging.debug("Tree: %s" % tree)

        try:
            Eval(skydive_client).transform(tree)
        except BadRequest as e:
            print("Error: %s" % e)
