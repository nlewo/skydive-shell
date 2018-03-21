import argparse
import json
import urllib.request
import logging
import functools
import operator

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.history import InMemoryHistory

from lark import Lark, UnexpectedInput, InlineTransformer

from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import TerminalFormatter

# We explicitly define all terminal in order to predict their name for
# the completion mapping
skydive_grammar = """
start : G "." v ("." expr)? " "? -> gremlin
      | _SET " " _option         -> set
v : V ")"
  | V STRING ")"

expr : expr "." expr
     | traversal

traversal : HAS "(" HAS_METADATA ("," HAS_VALUE)? ")"
          | OUT
          | KEYS
          | COUNT
          | VALUES "(" HAS_METADATA ")"

_option : _FORMAT " " format
!format : _PRETTY
        | _JSON

HAS_METADATA : STRING
HAS_VALUE : STRING

G : "g"
V : "v("
HAS : "has"
VALUES : "values"
OUT : "out()"
KEYS : "keys()"
COUNT : "count()"
_PRETTY : "pretty"
_JSON : "json"
_SET : ":set"
_FORMAT : "format"

%import common.ESCAPED_STRING   -> STRING
"""

larkParser = Lark(skydive_grammar)

# This is to generate completions based on parsing errors
token_mapping = {"__COMMA": ",",
                 "__RPAR": ")",
                 "__LPAR": "(",
                 "__DOT": ".",

                 "V": "v(",
                 "HAS": "has",
                 "VALUES": "values",
                 "KEYS": "keys()",
                 "COUNT": "count()",
                 "G": "g",
                 "_SET": ":set",
                 "_FORMAT": "format",
                 "_PRETTY": "pretty",
                 "_JSON": "json",
                 "OUT": "out()"}


# We iterate on the expression to find a valid expression by removing
# each time the last character.
# For instance:
# find_valid_expr("g.v().has(") returns ("g.v()", ".has(")
def find_valid_expr(expr):
    for i in range(len(expr), 1, -1):
        try:
            larkParser.parse(expr[:i])
        except:
            continue
        return expr[:i], expr[i+1:]
    return "", ""


def skydive_query(endpoint, query):
        data = json.dumps(
            {"GremlinQuery": query}
        )
        req = urllib.request.Request("http://%s/api/topology" % endpoint,
                                     data.encode(),
                                     {'Content-Type': 'application/json'})
        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.URLError as e:
            logging.warning("Error while connecting to '%s': %s" % (endpoint, str(e)))
            return "{}"
        if resp.getcode() != 200:
            logging.warning("Skydive returns error code '%d' for the query '%s'" % (resp.getcode(), query))
            return "{}"

        data = resp.read()
        return data.decode()


# Generates a list of string (if possible) from the skydive_query
# output.
def skydive_query_list_string(endpoint, query):
    l = skydive_query(endpoint, query)
    objs = json.loads(l)
    return ['"%s"' % a for a in objs if a.__class__ == str]


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
            partial = e.context[:-2]
            request = format("%s.keys()" % base)
            completions = skydive_query_list_string(endpoint, request)
        elif "HAS_VALUE" in e.allowed:
            # To remove the introduced leading space
            partial = e.context[:-2]
            base, last = (find_valid_expr(query[0:e.column-1]))
            request = base + "." + last.replace("has", "values") + ")"
            completions = skydive_query_list_string(endpoint, request)
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
            if not o.get("ID"):
                return format_json(objs)
            short += ["{} {}".format("ID", o["ID"])]
            short += ([" {: <15} {}".format(p, get_by_path(o, p))
                       for p in fields if get_by_path(o, p) is not None])
    return "\n".join(short)


class ShellTree(InlineTransformer):
    formatter = "json"

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

    history = InMemoryHistory()

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
        else:
            r = skydive_query(skydive_url, query)
            j = json.loads(r)
            print(formatFunctionName(j))
