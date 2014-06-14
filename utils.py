# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common utility functions."""

__author__ = 'sll@google.com (Sean Lip)'

import base64
import datetime
import hashlib
import json
import os
import random
import re
import StringIO
import time
import unicodedata
import urllib
import urlparse
import yaml
import zipfile



# Sentinel value for schema verification, indicating that a value can take any
# type.
ANY_TYPE = 1


class InvalidInputException(Exception):
    """Error class for invalid input."""
    pass


class EntityIdNotFoundError(Exception):
    """Error class for when an entity ID is not in the datastore."""
    pass


class ValidationError(Exception):
    """Error class for when a domain object fails validation."""
    pass


def create_enum(*sequential, **names):
    enums = dict(zip(sequential, sequential), **names)
    return type('Enum', (), enums)


def get_file_contents(filepath, raw_bytes=False, mode='r'):
    """Gets the contents of a file, given a relative filepath from oppia/."""
    with open(filepath, mode) as f:
        return f.read() if raw_bytes else f.read().decode('utf-8')


def get_exploration_components_from_dir(dir_path):
    """Gets the (yaml, assets) from the contents of an exploration data dir.

    Args:
      dir_path: a full path to the exploration root directory.

    Returns:
      a 2-tuple, the first element of which is a yaml string, and the second
      element of which is a list of (filepath, content) 2-tuples. The filepath
      does not include the assets/ prefix.

    Raises:
      Exception: if the following condition doesn't hold: "There is exactly one
        file not in assets/, and this file has a .yaml suffix".
    """
    yaml_content = None
    assets_list = []

    dir_path_array = dir_path.split('/')
    while dir_path_array[-1] == '':
        dir_path_array = dir_path_array[:-1]
    dir_path_length = len(dir_path_array)

    for root, dirs, files in os.walk(dir_path):
        for directory in dirs:
            if root == dir_path and directory != 'assets':
                raise Exception(
                    'The only directory in %s should be assets/' % dir_path)

        for filename in files:
            filepath = os.path.join(root, filename)
            if root == dir_path:
                if filepath.endswith('.DS_Store'):
                    # These files are added automatically by Mac OS Xsystems.
                    # We ignore them.
                    continue

                if yaml_content is not None:
                    raise Exception('More than one non-asset file specified '
                                    'for %s' % dir_path)
                elif not filepath.endswith('.yaml'):
                    raise Exception('Found invalid non-asset file %s. There '
                                    'should only be a single non-asset file, '
                                    'and it should have a .yaml suffix.' %
                                    filepath)
                else:
                    yaml_content = get_file_contents(filepath)
            else:
                filepath_array = filepath.split('/')
                # The additional offset is to remove the 'assets/' prefix.
                filename = '/'.join(filepath_array[dir_path_length + 1:])
                assets_list.append((filename, get_file_contents(
                    filepath, raw_bytes=True)))

    if yaml_content is None:
        raise Exception('No yaml file specifed for %s' % dir_path)

    return yaml_content, assets_list


def get_exploration_components_from_zip(zip_file_contents):
    """Gets the (yaml, assets) from the contents of an exploration zip file.

    Args:
      zip_file_contents: a string of raw bytes representing the contents of
        a zip file that comprises the exploration.

    Returns:
      a 2-tuple, the first element of which is a yaml string, and the second
      element of which is a list of (filepath, content) 2-tuples. The filepath
      does not include the assets/ prefix.

    Raises:
      Exception: if the following condition doesn't hold: "There is exactly one
        file not in assets/, and this file has a .yaml suffix".
    """
    o = StringIO.StringIO()
    o.write(zip_file_contents)

    zf = zipfile.ZipFile(o, 'r')
    yaml_content = None
    assets_list = []
    for filepath in zf.namelist():
        if filepath.startswith('assets/'):
            assets_list.append('/'.join(filepath.split('/')[1:]),
                               zf.read(filepath))
        else:
            if yaml_content is not None:
                raise Exception(
                    'More than one non-asset file specified for zip file')
            elif not filepath.endswith('.yaml'):
                raise Exception('Found invalid non-asset file %s. There '
                                'should only be a single file not in assets/, '
                                'and it should have a .yaml suffix.' %
                                filepath)
            else:
                yaml_content = zf.read(filepath)

    if yaml_content is None:
        raise Exception('No yaml file specified in zip file contents')

    return yaml_content, assets_list


def get_comma_sep_string_from_list(items):
    """Turns a list of items into a comma-separated string."""

    if not items:
        return ''

    if len(items) == 1:
        return items[0]

    return '%s and %s' % (', '.join(items[:-1]), items[-1])


def to_ascii(string):
    """Change unicode characters in a string to ascii if possible."""
    return unicodedata.normalize(
        'NFKD', unicode(string)).encode('ascii', 'ignore')


def yaml_from_dict(dictionary):
    """Gets the YAML representation of a dict."""
    return yaml.safe_dump(dictionary, default_flow_style=False)


def dict_from_yaml(yaml_str):
    """Gets the dict representation of a YAML string."""
    try:
        retrieved_dict = yaml.safe_load(yaml_str)
        assert isinstance(retrieved_dict, dict)
        return retrieved_dict
    except yaml.YAMLError as e:
        raise InvalidInputException(e)


def recursively_remove_key(obj, key_to_remove):
    """Recursively removes keys from a list or dict."""
    if isinstance(obj, list):
        for item in obj:
            recursively_remove_key(item, key_to_remove)
    elif isinstance(obj, dict):
        if key_to_remove in obj:
            del obj[key_to_remove]
        for key, unused_value in obj.items():
            recursively_remove_key(obj[key], key_to_remove)


def get_random_int(upper_bound):
    """Returns a random integer in [0, upper_bound)."""
    assert upper_bound >= 0 and isinstance(upper_bound, int)

    generator = random.SystemRandom()
    return generator.randrange(0, upper_bound)


def get_random_choice(alist):
    """Gets a random element from a list."""
    assert isinstance(alist, list) and len(alist) > 0

    index = get_random_int(len(alist))
    return alist[index]


def verify_dict_keys_and_types(adict, dict_schema):
    """Checks the keys in adict, and that their values have the right types.

    Args:
      adict: the dictionary to test.
      dict_schema: list of 2-element tuples. The first element of each
        tuple is the key name and the second element is the value type.
    """
    for item in dict_schema:
        if len(item) != 2:
            raise Exception('Schema %s is invalid.' % dict_schema)
        if not isinstance(item[0], str):
            raise Exception('Schema key %s is not a string.' % item[0])
        if item[1] != ANY_TYPE and not isinstance(item[1], type):
            raise Exception('Schema value %s is not a valid type.' % item[1])

    TOP_LEVEL_KEYS = [item[0] for item in dict_schema]
    if sorted(TOP_LEVEL_KEYS) != sorted(adict.keys()):
        raise ValidationError(
            'Dict %s should conform to schema %s.' % (adict, dict_schema))

    for item in dict_schema:
        if item[1] == ANY_TYPE:
            continue
        if not isinstance(adict[item[0]], item[1]):
            raise ValidationError(
                'Value \'%s\' for key \'%s\' is not of type %s in:\n\n %s'
                % (adict[item[0]], item[0], item[1], adict))


def convert_png_to_data_url(filepath):
    """Converts the png file at filepath to a data URL.

    This method is currently used only in tests for the non-interactive
    widgets.
    """
    file_contents = get_file_contents(filepath, raw_bytes=True, mode='rb')
    return 'data:image/png;base64,%s' % urllib.quote(
        file_contents.encode('base64'))


def camelcase_to_hyphenated(camelcase_str):
    s = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', camelcase_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s).lower()


def set_url_query_parameter(url, param_name, param_value):
    """Set or replace a query parameter, and return the modified URL."""
    if not isinstance(param_name, basestring):
        raise Exception(
            'URL query parameter name must be a string, received %s'
            % param_name)

    scheme, netloc, path, query_string, fragment = urlparse.urlsplit(url)
    query_params = urlparse.parse_qs(query_string)

    query_params[param_name] = [param_value]
    new_query_string = urllib.urlencode(query_params, doseq=True)

    return urlparse.urlunsplit(
        (scheme, netloc, path, new_query_string, fragment))


class JSONEncoderForHTML(json.JSONEncoder):
    """Encodes JSON that is safe to embed in HTML."""

    def encode(self, o):
        chunks = self.iterencode(o, True)
        return ''.join(chunks) if self.ensure_ascii else u''.join(chunks)

    def iterencode(self, o, _one_shot=False):
        chunks = super(JSONEncoderForHTML, self).iterencode(o, _one_shot)
        for chunk in chunks:
            yield chunk.replace('&', '\\u0026').replace(
                '<', '\\u003c').replace('>', '\\u003e')


def convert_to_hash(string, max_length):
    """Convert a string to a SHA1 hash."""
    if not isinstance(string, basestring):
        raise Exception(
            'Expected string, received %s of type %s' %
            (string, type(string)))

    encoded_string = base64.urlsafe_b64encode(
        hashlib.sha1(string).digest())

    return encoded_string[:max_length]


def base64_from_int(value):
    return base64.b64encode(bytes([value]))


def get_time_in_millisecs(datetime_obj):
    """Returns time in milliseconds since the Epoch.

    Args:
      datetime_obj: An object of type datetime.datetime.
    """
    return time.mktime(datetime_obj.timetuple()) * 1000


def get_current_time_in_millisecs():
    """Returns time in milliseconds since the Epoch.

    Args:
      datetime_obj: An object of type datetime.datetime.
    """
    return get_time_in_millisecs(datetime.datetime.utcnow())


def get_epoch_time():
    return int(time.time())


def generate_random_string(length):
    return base64.urlsafe_b64encode(os.urandom(length))

def vfs_construct_path(a, *p):
    """Mimics behavior of os.path.join on Posix machines."""
    path = a
    for b in p:
        if b.startswith('/'):
            path = b
        elif path == '' or path.endswith('/'):
            path += b
        else:
            path += '/' + b
    return path


def vfs_normpath(path):
    """Normalize path from posixpath.py, eliminating double slashes, etc."""
    # Preserve unicode (if path is unicode)
    slash, dot = (u'/', u'.') if isinstance(path, unicode) else ('/', '.')
    if path == '':
        return dot
    initial_slashes = path.startswith('/')
    # POSIX allows one or two initial slashes, but treats three or more
    # as single slash.
    if (initial_slashes and
        path.startswith('//') and not path.startswith('///')):
        initial_slashes = 2
    comps = path.split('/')
    new_comps = []
    for comp in comps:
        if comp in ('', '.'):
            continue
        if (comp != '..' or (not initial_slashes and not new_comps) or
             (new_comps and new_comps[-1] == '..')):
            new_comps.append(comp)
        elif new_comps:
            new_comps.pop()
    comps = new_comps
    path = slash.join(comps)
    if initial_slashes:
        path = slash*initial_slashes + path
    return path or dot

