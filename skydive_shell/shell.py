import pprint
import argparse
import json
import urllib.request

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.history import InMemoryHistory
from lark import Lark, UnexpectedInput


grammar = """
start : G "." v ("." expr)? " "?
G : "g"
v : V ")"
  | V STRING ")"

V : "v("

expr : expr "." expr
     | traversal

traversal : HAS "(" HAS_METADATA ("," HAS_VALUE)? ")"
          | OUT

HAS : "has"
HAS_METADATA : STRING
HAS_VALUE : STRING

OUT : "out()"
%import common.ESCAPED_STRING   -> STRING
"""


larkParser = Lark(grammar)


def find_valid_expr(expr):
    for i in range(len(expr), 1, -1):
        try:
            tree = larkParser.parse(expr[:i])
        except:
            continue
        return expr[:i], expr[i+1:], tree
    return "", "", None


token_mapping = {"__COMMA": ",",
                 "__RPAR": ")",
                 "__LPAR": "(",
                 "__DOT": ".",
                 "V": "v(",
                 "HAS": "has",
                 "OUT": "out"}


def skydive_query(endpoint, query):
        data = json.dumps(
            {"GremlinQuery": query}
        )
        req = urllib.request.Request("http://%s/api/topology" % endpoint,
                                     data.encode(),
                                     {'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req)
        if resp.getcode() != 200:
            print(resp.getcode())
            return

        data = resp.read()
        objs = json.loads(data.decode())
        return objs


def skydive_query_list_string(endpoint, query):
    l = skydive_query(endpoint, query)
    return ['"%s"' % a for a in l if a.__class__ == str]


def skydive_get_completions(endpoint, query):
    completions = []
    position = 0
    try:
        # We add a space at the end of the query to let the parser
        # generates UnexpectedInput in order to get back expected
        # TOKEN list.
        tree = larkParser.parse(query + " ")
    except UnexpectedInput as e:
        # print(e)
        base, partial, tree = (find_valid_expr(query))
        # print("base: %s last: %s tree: %s" % (base, last, tree))
        position = e.column - len(query)
        if "HAS_METADATA" in e.allowed:
            # To remove the introduced leading space
            partial = e.context[:-1]
            request = format("%s.keys()" % base)
            completions = skydive_query_list_string(skydive_url, request)
        elif "HAS_VALUE" in e.allowed:
            partial = e.context[:-1]
            base, last, tree = (find_valid_expr(query[0:e.column-1]))
            request = base + "." + last.replace("has", "values") + ")"
            completions = skydive_query_list_string(skydive_url, request)
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
    def get_completions(self, document, complete_event):
        position, c = skydive_get_completions(skydive_url,
                                              document.text_before_cursor)
        return [Completion(i, start_position=position) for i in c]


def main():
    history = InMemoryHistory()

    while True:
        query = prompt('> ',
                       completer=SkydiveCompleter(),
                       validator=SkydiveValidator(),
                       history=history,
                       complete_while_typing=False)
        r = skydive_query(skydive_url, query)
        pprint.pprint(r)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
         description='Skydive Network Analyzer Shell')
    parser.add_argument('--host', default="localhost",
                        help='Skydive analyzer host')
    parser.add_argument('--port', default="8081",
                        help='Skydive analyzer port')
    args = parser.parse_args()
    skydive_url = "%s:%s" % (args.host, args.port)
    print("Using Skydive Analyzer %s:%s" % (args.host, args.port))
    main()


# def test(query):
#     print(query)
#     print(skydive_get_completions("localhost:8182", query))

# test(sys.argv[1])
# assert skydive_get_completions("localhost:8182", "g") == (0, ["."])
# assert skydive_get_completions("localhost:8182", "g.v(") == (0, [])
# print("iop", skydive_get_completions("localhost:8182", "g.v"))
# assert skydive_get_completions("localhost:8182", "g.v") == (-1, ['v('])


# test('g.v().values("Name")')
# print()
