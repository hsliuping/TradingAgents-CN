# Globals
_CURRENT_LINE = 1
_LAST_TAG_LINE = None


class ChevronError(SyntaxError):
    pass

#
# Helper functions
#


def grab_literal(template, l_del):
    """Parse a literal from the template"""

    global _CURRENT_LINE

    try:
        # Look for the next tag and move the template to it
        literal, template = template.split(l_del, 1)
        _CURRENT_LINE += literal.count('\n')
        return (literal, template)

    # There are no more tags in the template?
    except ValueError:
        # Then the rest of the template is a literal
        return (template, '')


def l_sa_check(template, literal, is_standalone):
    """Do a preliminary check to see if a tag could be a standalone"""

    # If there is a newline, or the previous tag was a standalone
    if literal.find('\n') != -1 or is_standalone:
        padding = literal.split('\n')[-1]

        # If all the characters since the last newline are spaces
        if padding.isspace() or padding == '':
            # Then the next tag could be a standalone
            return True
        else:
            # Otherwise it can't be
            return False


def r_sa_check(template, tag_type, is_standalone):
    """Do a final checkto see if a tag could be a standalone"""

    # Check right side if we might be a standalone
    if is_standalone and tag_type not in ['variable', 'no escape']:
        on_newline = template.split('\n', 1)

        # If the stuff to the right of us are spaces we're a standalone
        if on_newline[0].isspace() or not on_newline[0]:
            return True
        else:
            return False

    # If we're a tag can't be a standalone
    else:
        return False


def parse_tag(template, l_del, r_del):
    """Parse a tag from a template"""
    global _CURRENT_LINE
    global _LAST_TAG_LINE

    tag_types = {
        '!': 'comment',
        '#': 'section',
        '^': 'inverted section',
        '/': 'end',
        '>': 'partial',
        '=': 'set delimiter?',
        '{': 'no escape?',
        '&': 'no escape'
    }

    # Get the tag
    try:
        tag, template = template.split(r_del, 1)
    except ValueError:
        raise ChevronError('unclosed tag '
                           'at line {0}'.format(_CURRENT_LINE))

    # Find the type meaning of the first character
    tag_type = tag_types.get(tag[0], 'variable')

    # If the type is not a variable
    if tag_type != 'variable':
        # Then that first character is not needed
        tag = tag[1:]

    # If we might be a set delimiter tag
    if tag_type == 'set delimiter?':
        # Double check to make sure we are
        if tag.endswith('='):
            tag_type = 'set delimiter'
            # Remove the equal sign
            tag = tag[:-1]

        # Otherwise we should complain
        else:
            raise ChevronError('unclosed set delimiter tag\n'
                               'at line {0}'.format(_CURRENT_LINE))

    # If we might be a no html escape tag
    elif tag_type == 'no escape?':
        # And we have a third curly brace
        # (And are using curly braces as delimiters)
        if l_del == '{{' and r_del == '}}' and template.startswith('}'):
            # Then we are a no html escape tag
            template = template[1:]
            tag_type = 'no escape'

    # Strip the whitespace off the key and return
    return ((tag_type, tag.strip()), template)


#
# The main tokenizing function
#

def tokenize(template, def_ldel='{{', def_rdel='}}'):
    """Tokenize a mustache template

    Tokenizes a mustache template in a generator fashion,
    using file-like objects. It also accepts a string containing
    the template.


    Arguments:

    template -- a file-like object, or a string of a mustache template

    def_ldel -- The default left delimiter
                ("{{" by default, as in spec compliant mustache)

    def_rdel -- The default right delimiter
                ("}}" by default, as in spec compliant mustache)


    Returns:

    A generator of mustache tags in the form of a tuple

    -- (tag_type, tag_key)

    Where tag_type is one of:
     * literal
     * section
     * inverted section
     * end
     * partial
     * no escape

    And tag_key is either the key or in the case of a literal tag,
    the literal itself.
    """

    global _CURRENT_LINE, _LAST_TAG_LINE
    _CURRENT_LINE = 1
    _LAST_TAG_LINE = None
    # If the template is a file-like object then read it
    try:
        template = template.read()
    except AttributeError:
        pass

    is_standalone = True
    open_sections = []
    l_del = def_ldel
    r_del = def_rdel

    while template:
        literal, template = grab_literal(template, l_del)

        # If the template is completed
        if not template:
            # Then yield the literal and leave
            yield ('literal', literal)
            break

        # Do the first check to see if we could be a standalone
        is_standalone = l_sa_check(template, literal, is_standalone)

        # Parse the tag
        tag, template = parse_tag(template, l_del, r_del)
        tag_type, tag_key = tag

        # Special tag logic

        # If we are a set delimiter tag
        if tag_type == 'set delimiter':
            # Then get and set the delimiters
            dels = tag_key.strip().split(' ')
            l_del, r_del = dels[0], dels[-1]

        # If we are a section tag
        elif tag_type in ['section', 'inverted section']:
            # Then open a new section
            open_sections.append(tag_key)
            _LAST_TAG_LINE = _CURRENT_LINE

        # If we are an end tag
        elif tag_type == 'end':
            # Then check to see if the last opened section
            # is the same as us
            try:
                last_section = open_sections.pop()
            except IndexError:
                raise ChevronError('Trying to close tag "{0}"\n'
                                   'Looks like it was not opened.\n'
                                   'line {1}'
                                   .format(tag_key, _CURRENT_LINE + 1))
            if tag_key != last_section:
                # Otherwise we need to complain
                raise ChevronError('Trying to close tag "{0}"\n'
                                   'last open tag is "{1}"\n'
                                   'line {2}'
                                   .format(tag_key, last_section,
                                           _CURRENT_LINE + 1))

        # Do the second check to see if we're a standalone
        is_standalone = r_sa_check(template, tag_type, is_standalone)

        # Which if we are
        if is_standalone:
            # Remove the stuff before the newline
            template = template.split('\n', 1)[-1]

            # Partials need to keep the spaces on their left
            if tag_type != 'partial':
                # But other tags don't
                literal = literal.rstrip(' ')

        # Start yielding
        # Ignore literals that are empty
        if literal != '':
            yield ('literal', literal)

        # Ignore comments and set delimiters
        if tag_type not in ['comment', 'set delimiter?']:
            yield (tag_type, tag_key)

    # If there are any open sections when we're done
    if open_sections:
        # Then we need to complain
        raise ChevronError('Unexpected EOF\n'
                           'the tag "{0}" was never closed\n'
                           'was opened at line {1}'
                           .format(open_sections[-1], _LAST_TAG_LINE))
