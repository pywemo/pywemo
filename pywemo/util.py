"""Miscellaneous utility functions."""
from collections import defaultdict
import netifaces


# Taken from http://stackoverflow.com/a/10077069
def etree_to_dict(tree):
    """Split a tree into a dict."""
    # strip namespace
    tag_name = tree.tag[tree.tag.find("}")+1:]

    tree_dict = {tag_name: {} if tree.attrib else None}
    children = list(tree)
    if children:
        default_dict = defaultdict(list)
        for dict_children in map(etree_to_dict, children):
            for key, value in dict_children.items():
                default_dict[key].append(value)
        tree_dict = {
            tag_name: {
                key: value[0] if len(value) == 1 else value
                for key, value in
                default_dict.items()}}
    if tree.attrib:
        tree_dict[tag_name].update(('@' + key, value)
                                   for key, value in tree.attrib.items())
    if tree.text:
        text = tree.text.strip()
        if children or tree.attrib:
            if text:
                tree_dict[tag_name]['#text'] = text
        else:
            tree_dict[tag_name] = text
    return tree_dict


def interface_addresses(family=netifaces.AF_INET):
    """
    Return local address for broadcast/multicast.

    Return local address of any network associated with a local interface
    that has broadcast (and probably multicast) capability.
    """
    return [addr['addr']
            for i in netifaces.interfaces()
            for addr in netifaces.ifaddresses(i).get(family) or []
            if 'broadcast' in addr]
