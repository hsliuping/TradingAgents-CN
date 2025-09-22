#!/usr/bin/python

import io
import sys

try:
    from .renderer import render
    from .metadata import version
except (ValueError, SystemError):  # python 2
    from renderer import render
    from metadata import version


def main(template, data=None, **kwargs):
    with io.open(template, 'r', encoding='utf-8') as template_file:
        yaml_loader = kwargs.pop('yaml_loader', None) or 'SafeLoader'

        if data is not None:
            with io.open(data, 'r', encoding='utf-8') as data_file:
                data = _load_data(data_file, yaml_loader)
        else:
            data = {}

        args = {
            'template': template_file,
            'data': data
        }

        args.update(kwargs)
        return render(**args)


def _load_data(file, yaml_loader):
    try:
        import yaml
        loader = getattr(yaml, yaml_loader)  # not tested
        return yaml.load(file, Loader=loader)  # not tested
    except ImportError:
        import json
        return json.load(file)


def cli_main():
    """Render mustache templates using json files"""
    import argparse
    import os

    def is_file_or_pipe(arg):
        if not os.path.exists(arg) or os.path.isdir(arg):
            parser.error('The file {0} does not exist!'.format(arg))
        else:
            return arg

    def is_dir(arg):
        if not os.path.isdir(arg):
            parser.error('The directory {0} does not exist!'.format(arg))
        else:
            return arg

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-v', '--version', action='version',
                        version=version)

    parser.add_argument('template', help='The mustache file',
                        type=is_file_or_pipe)

    parser.add_argument('-d', '--data', dest='data',
                        help='The json data file',
                        type=is_file_or_pipe, default={})

    parser.add_argument('-y', '--yaml-loader', dest='yaml_loader',
                        help=argparse.SUPPRESS)

    parser.add_argument('-p', '--path', dest='partials_path',
                        help='The directory where your partials reside',
                        type=is_dir, default='.')

    parser.add_argument('-e', '--ext', dest='partials_ext',
                        help='The extension for your mustache\
                              partials, \'mustache\' by default',
                        default='mustache')

    parser.add_argument('-l', '--left-delimiter', dest='def_ldel',
                        help='The default left delimiter, "{{" by default.',
                        default='{{')

    parser.add_argument('-r', '--right-delimiter', dest='def_rdel',
                        help='The default right delimiter, "}}" by default.',
                        default='}}')

    parser.add_argument('-w', '--warn', dest='warn',
                        help='Print a warning to stderr for each undefined template key encountered',
                        action='store_true')


    args = vars(parser.parse_args())

    try:
        sys.stdout.write(main(**args))
        sys.stdout.flush()
    except SyntaxError as e:
        print('Chevron: syntax error')
        sys.exit('    ' + '\n    '.join(e.args[0].split('\n')))


if __name__ == '__main__':
    cli_main()
