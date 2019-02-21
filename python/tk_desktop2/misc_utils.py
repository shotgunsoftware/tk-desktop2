# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

import json
import pickle


def _byteify(input):
    """
    Replaces dictionary 'unicode' members with 'str'

    This was required to keep the pickle-JSON conversion reflective.
    The normal JSON parser behavior is to load string from dict as 'unicode' rather than 'str' as with a pickle.
    Some of the SG code relies on string being of type 'str'

    TODO: This is NOT Python 3 working code (e.g.: unicode, dict.iteritems)

    https://stackoverflow.com/a/13105359

    :param input: A dict
    :return: A dict
    """

    if isinstance(input, dict):
        return {_byteify(key): _byteify(value)
                for key, value in input.iteritems()}

    elif isinstance(input, list):
        return [_byteify(element) for element in input]

    elif isinstance(input, unicode):
        return input.encode('utf-8')

    else:
        return input


def pickle_to_json(pickle_string):
    """
    Converts the specified pickle string into JSON string format

    :param pickle_string: A string of pickle format
    :return: A str in JSON format
    """
    a_pickle = pickle.loads(pickle_string)
    json_string = json.dumps(a_pickle)
    return json_string


def json_to_pickle(json_string):
    """
    Converts the specified JSON string into Python pickle

    :param json_string: A str in JSON format
    :return: A str in Python pickle format
    """
    json_obj = json.loads(json_string)
    json_obj2 = _byteify(json_obj)
    pickle_string = pickle.dumps(json_obj2, 0)
    return pickle_string