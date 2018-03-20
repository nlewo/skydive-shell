import pprint
import argparse
import json
import urllib.request
import logging

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.history import InMemoryHistory

from lark import Lark, UnexpectedInput

import json
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import TerminalFormatter


skydive_grammar = """
start : G "." v ("." expr)? " "?
G : "g"
v : V ")"
  | V STRING ")"

V : "v("

expr : expr "." expr
     | traversal

traversal : HAS "(" HAS_METADATA ("," HAS_VALUE)? ")"
          | OUT
          | KEYS
          | COUNT

HAS : "has"
HAS_METADATA : STRING
HAS_VALUE : STRING

OUT : "out()"
KEYS : "keys()"
COUNT : "count()"

%import common.ESCAPED_STRING   -> STRING
"""

larkParser = Lark(skydive_grammar)

token_mapping = {"__COMMA": ",",
                 "__RPAR": ")",
                 "__LPAR": "(",
                 "__DOT": ".",
                 "V": "v(",
                 "HAS": "has",
                 "KEYS": "keys()",
                 "COUNT": "count()",
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


def skydive_query_list_string(endpoint, query):
    l = skydive_query(endpoint, query)
    objs = json.loads(l)
    return ['"%s"' % a for a in objs if a.__class__ == str]


def skydive_get_completions(endpoint, query):
    completions = []
    position = 0
    try:
        # We add a space at the end of the query to let the parser
        # generates an UnexpectedInput error in order to get back
        # useful parsing information
        larkParser.parse(query + " ")
    except UnexpectedInput as e:
        # print(e)
        base, partial = (find_valid_expr(query))
        # print("base: %s last: %s tree: %s" % (base, last, tree))
        position = e.column - len(query)
        if "HAS_METADATA" in e.allowed:
            # To remove the introduced leading space
            partial = e.context[:-1]
            request = format("%s.keys()" % base)
            completions = skydive_query_list_string(endpoint, request)
        elif "HAS_VALUE" in e.allowed:
            # To remove the introduced leading space
            partial = e.context[:-1]
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
        try:
            larkParser.parse(document.text)
        except:
            raise ValidationError(message='Non valid Gremlin expression',
                                  cursor_position=len(document.text))


class SkydiveCompleter(Completer):
    def __init__(self, skydive_url):
        self._skydive_url = skydive_url

    def get_completions(self, document, complete_event):
        position, c = skydive_get_completions(self._skydive_url,
                                              document.text_before_cursor)
        return [Completion(i, start_position=position) for i in c]


def main():
    parser = argparse.ArgumentParser(
         description='Skydive Network Analyzer Shell')
    parser.add_argument('--host', default="localhost",
                        help='Skydive analyzer host')
    parser.add_argument('--port', default="8082",
                        help='Skydive analyzer port')
    parser.add_argument('--disable-validation', default=False,
                        action="store_true",
                        help='Disable Gremlin query validation ')
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    skydive_url = "%s:%s" % (args.host, args.port)
    print("Using Skydive Analyzer %s:%s" % (args.host, args.port))

    history = InMemoryHistory()

    validator = SkydiveValidator()
    if args.disable_validation:
        validator = None

    while True:
        query = prompt('> ',
                       completer=SkydiveCompleter(skydive_url),
                       validator=validator,
                       history=history,
                       complete_while_typing=False)

        r = skydive_query(skydive_url, query)
        j = json.dumps(json.loads(r), indent=2, sort_keys=True)
        print(highlight(j, JsonLexer(), TerminalFormatter()))
