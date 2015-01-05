from collections import defaultdict


# Taken from http://stackoverflow.com/a/10077069
def etree_to_dict(t):
    # strip namespace
    tag_name = t.tag[t.tag.find("}")+1:]

    d = {tag_name: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.items():
                dd[k].append(v)
        d = {tag_name: {k: v[0] if len(v) == 1 else v for k, v in dd.items()}}
    if t.attrib:
        d[tag_name].update(('@' + k, v) for k, v in t.attrib.items())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
                d[tag_name]['#text'] = text
        else:
            d[tag_name] = text
    return d
