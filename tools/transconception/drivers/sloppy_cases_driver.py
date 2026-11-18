"""The boundary of sloppy-xml-py for the x0 experiment: one request on stdin, the result as JSON lines on stdout.

sloppy-xml-py is a library, so it has no command line of its own to be judged at. This driver is the agreed
boundary: the original (and the round trip's Python cshort) is judged through it, and every cshort in another
language must ship a program named `sloppy-cases` that reads the same request and writes the same lines. The
contract below is part of what the transcoder rules (worksheet item S-I0); it is not sloppy-xml-py's own.

Run by x0.sh only, inside the sandbox, with PYTHONPATH pointing at the copy under test. Owner's to run.

Request (one JSON object, UTF-8, JSON's own \\u escapes allowed, lone surrogates included):
    {"call": "stream_parse" | "tree_parse",
     "input": "<text>"            # the input as text, or
     "input_b64": "<base64>",     # the input as bytes
     "as": "str" | "text-file" | "bytes-file" | "bytes",   # how the input reaches the library (default "str")
     "options": {"recover": true, "recovery_strategy": "LENIENT", ...}}   # keyword options, enums by name

Output, one JSON object per line, ASCII only (separators "," and ":"; keys in the order written here):
    stream_parse: one line per event, in order:
      {"event":"StartElement","name":…,"attrs":[[k,v],…],"line":…,"column":…,"namespace":…}
      {"event":"EndElement","name":…,"line":…,"column":…,"auto_closed":…}
      {"event":"Text","content":…,"line":…,"column":…,"is_cdata":…}
      {"event":"Comment","content":…,"line":…,"column":…}
      {"event":"ProcessingInstruction","target":…,"data":…,"line":…,"column":…}
      {"event":"EntityRef","name":…,"resolved":…,"line":…,"column":…}
      {"event":"ParseError","error_type":…,"message":…,"line":…,"column":…,"recovery":…,"fatal":…,
       "context":…,"severity":…}
    tree_parse: one line {"tree": NODE}, NODE = {"tag":…,"attrib":[[k,v],…],"text":…,"tail":…,"children":[…]}
    then always a last line: {"end":"ok"}  or, when the library raised: {"end":"raised","type":…,"message":…}
Exit status 0 when the library returned, 1 when it raised. Events already produced before a raise are written.
"""
import base64
import io
import json
import sys

import sloppy_xml as sx


def out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True, separators=(",", ":")) + "\n")


def event_line(ev):
    name = type(ev).__name__
    d = {"event": name}
    for field in ev._fields:
        v = getattr(ev, field)
        if field == "attrs":
            v = [[k, val] for k, val in v.items()]
        d[field] = v
    return d


def node(el):
    return {"tag": el.tag if isinstance(el.tag, str) else "#" + getattr(el.tag, "__name__", "special"),
            "attrib": [[k, v] for k, v in el.attrib.items()],
            "text": el.text, "tail": el.tail, "children": [node(c) for c in el]}


def main():
    req = json.loads(sys.stdin.buffer.read().decode("utf-8", "surrogatepass"))
    opts = dict(req.get("options", {}))
    if "recovery_strategy" in opts:
        opts["recovery_strategy"] = sx.RecoveryStrategy[opts["recovery_strategy"]]
    if "input_b64" in req:
        data = base64.b64decode(req["input_b64"])
    else:
        data = req["input"]
    how = req.get("as", "str")
    if how == "text-file":
        arg = io.StringIO(data)
    elif how == "bytes-file":
        arg = io.BytesIO(data if isinstance(data, bytes) else data.encode("utf-8", "surrogatepass"))
    elif how == "bytes":
        arg = data if isinstance(data, bytes) else data.encode("utf-8", "surrogatepass")
    else:
        arg = data
    try:
        if req["call"] == "stream_parse":
            for ev in sx.stream_parse(arg, **opts):
                out(event_line(ev))
        elif req["call"] == "tree_parse":
            out({"tree": node(sx.tree_parse(arg, **opts))})
        else:
            raise SystemExit(f"unknown call {req['call']!r}")
    except Exception as e:  # the library raised: the type's name and its message are the boundary
        out({"end": "raised", "type": type(e).__name__, "message": str(e)})
        sys.stdout.flush()
        sys.exit(1)
    out({"end": "ok"})


if __name__ == "__main__":
    main()
