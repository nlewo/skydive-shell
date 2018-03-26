import json
import urllib.request
import logging

def request(url, method=None, data=None):
    d = None
    if data is not None:
        d = data.encode()
    req = urllib.request.Request(url,
                                 d,
                                 {'Content-Type': 'application/json'},
                                 method=method)
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.URLError as e:
        logging.warning("Error while connecting to '%s': %s" % (url, str(e)))
        return "{}"
    if resp.getcode() != 200:
        logging.warning("Skydive returns error code '%d' for the data '%s'" % (resp.getcode(), data))
        return "{}"

    data = resp.read()
    return data.decode()


def gremlin_query(endpoint, query):
    data = json.dumps(
        {"GremlinQuery": query}
    )
    return request("http://%s/api/topology" % endpoint, data=data)


def capture_create(endpoint, query):
    data = json.dumps(
        {"GremlinQuery": query}
    )
    return request("http://%s/api/capture" % endpoint, data=data)


def capture_list(endpoint):
    return request("http://%s/api/capture" % endpoint)


def capture_delete(endpoint, capture_id):
    return request("http://%s/api/capture/%s" % (endpoint, capture_id),
                   method="DELETE")


# Generates a list of string (if possible) from the skydive_query
# output.
def gremlin_query_list_string(endpoint, query):
    l = gremlin_query(endpoint, query)
    objs = json.loads(l)
    return ['"%s"' % a for a in objs if a.__class__ == str]
