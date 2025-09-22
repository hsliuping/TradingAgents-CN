#!/usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = "Deron Meranda <http://deron.meranda.us/>"
__homepage__ = "http://deron.meranda.us/python/demjson/"

__date__ = "2015-12-22"
__version__ = "2.2.4"
__version_info__ = (2, 2, 4)  # Will be converted into a namedtuple below

__credits__ = "Short of demjson"

# Set demjson version
try:
    from collections import namedtuple as _namedtuple
    import codecs

    __version_info__ = _namedtuple("version_info", ["major", "minor", "micro"])(
        *__version_info__
    )
except ImportError:
    raise ImportError("demjson %s requires a Python 2.6 or later" % __version__)

version, version_info = __version__, __version_info__

# Determine Python version
_py_major, _py_minor = None, None


def _get_pyver():
    global _py_major, _py_minor
    import sys

    vi = sys.version_info
    try:
        _py_major, _py_minor = vi.major, vi.minor
    except AttributeError:
        _py_major, _py_minor = vi[0], vi[1]


_get_pyver()

# ----------------------------------------------------------------------
# Useful global constants

content_type = "application/json"
file_ext = "json"


class _dummy_context_manager(object):
    """A context manager that does nothing on entry or exit."""

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


_dummy_context_manager = _dummy_context_manager()

# ----------------------------------------------------------------------
# Decimal and float types.
#
# If a JSON number can not be stored in a Python float without loosing
# precision and the Python has the decimal type, then we will try to
# use decimal instead of float.  To make this determination we need to
# know the limits of the float type, but Python doesn't have an easy
# way to tell what the largest floating-point number it supports.  So,
# we detemine the precision and scale of the float type by testing it.

try:
    # decimal module was introduced in Python 2.4
    import decimal
except ImportError:
    decimal = None


def determine_float_limits(number_type=float):
    """Determines the precision and range of the given float type.

    The passed in 'number_type' argument should refer to the type of
    floating-point number.  It should either be the built-in 'float',
    or decimal context or constructor; i.e., one of:

        # 1. FLOAT TYPE
        determine_float_limits( float )

        # 2. DEFAULT DECIMAL CONTEXT
        determine_float_limits( decimal.Decimal )

        # 3. CUSTOM DECIMAL CONTEXT
        ctx = decimal.Context( prec=75 )
        determine_float_limits( ctx )

    Returns a named tuple with components:

         ( significant_digits,
           max_exponent,
           min_exponent )

    Where:
        * significant_digits -- maximum number of *decimal* digits
             that can be represented without any loss of precision.
             This is conservative, so if there are 16 1/2 digits, it
             will return 16, not 17.

        * max_exponent -- The maximum exponent (power of 10) that can
             be represented before an overflow (or rounding to
             infinity) occurs.

        * min_exponent -- The minimum exponent (negative power of 10)
             that can be represented before either an underflow
             (rounding to zero) or a subnormal result (loss of
             precision) occurs.  Note this is conservative, as
             subnormal numbers are excluded.

    """
    if decimal:
        numeric_exceptions = (ValueError, decimal.Overflow, decimal.Underflow)
    else:
        numeric_exceptions = (ValueError,)

    if decimal and number_type is decimal.Decimal:
        number_type = decimal.DefaultContext

    if decimal and isinstance(number_type, decimal.Context):
        # Passed a decimal Context, extract the bound creator function.
        create_num = number_type.create_decimal
        decimal_ctx = decimal.localcontext(number_type)
        is_zero_or_subnormal = lambda n: n.is_zero() or n.is_subnormal()  # noqa: E731
    elif number_type is float:
        create_num = number_type
        decimal_ctx = _dummy_context_manager
        is_zero_or_subnormal = lambda n: n == 0  # noqa: E731
    else:
        raise TypeError("Expected a float type, e.g., float or decimal context")

    with decimal_ctx:
        zero = create_num("0.0")

        # Find signifianct digits by comparing floats of increasing
        # number of digits, differing in the last digit only, until
        # they numerically compare as being equal.
        sigdigits = None
        n = 0
        while True:
            n = n + 1
            pfx = "0." + "1" * n
            a = create_num(pfx + "0")
            for sfx in "123456789":  # Check all possible last digits to
                # avoid any partial-decimal.
                b = create_num(pfx + sfx)
                if (a + zero) == (b + zero):
                    sigdigits = n
                    break
            if sigdigits:
                break

        # Find exponent limits.  First find order of magnitude and
        # then use a binary search to find the exact exponent.
        base = "1." + "1" * (sigdigits - 1)
        base0 = "1." + "1" * (sigdigits - 2)
        minexp, maxexp = None, None

        for expsign in ("+", "-"):
            minv = 0
            maxv = 10
            # First find order of magnitude of exponent limit
            while True:
                try:
                    s = base + "e" + expsign + str(maxv)
                    s0 = base0 + "e" + expsign + str(maxv)
                    f = create_num(s) + zero
                    f0 = create_num(s0) + zero
                except numeric_exceptions:
                    f = None
                if (
                    not f
                    or not str(f)[0].isdigit()
                    or is_zero_or_subnormal(f)
                    or f == f0
                ):
                    break
                else:
                    minv = maxv
                    maxv = maxv * 10

            # Now do a binary search to find exact limit
            while True:
                if minv + 1 == maxv:
                    if expsign == "+":
                        maxexp = minv
                    else:
                        minexp = minv
                    break
                elif maxv < minv:
                    if expsign == "+":
                        maxexp = None
                    else:
                        minexp = None
                    break
                m = (minv + maxv) // 2
                try:
                    s = base + "e" + expsign + str(m)
                    s0 = base0 + "e" + expsign + str(m)
                    f = create_num(s) + zero
                    f0 = create_num(s0) + zero
                except numeric_exceptions:
                    f = None
                else:
                    if not f or not str(f)[0].isdigit():
                        f = None
                    elif is_zero_or_subnormal(f) or f == f0:
                        f = None
                if not f:
                    # infinite
                    maxv = m
                else:
                    minv = m

    return _namedtuple(
        "float_limits", ["significant_digits", "max_exponent", "min_exponent"]
    )(sigdigits, maxexp, -minexp)


float_sigdigits, float_maxexp, float_minexp = determine_float_limits(float)


# For backwards compatibility with older demjson versions:
def determine_float_precision():
    v = determine_float_limits(float)
    return (v.significant_digits, v.max_exponent)


# ----------------------------------------------------------------------
# The undefined value.
#
# ECMAScript has an undefined value (similar to yet distinct from null).
# Neither Python or strict JSON have support undefined, but to allow
# JavaScript behavior we must simulate it.


class _undefined_class(object):
    """Represents the ECMAScript 'undefined' value."""

    __slots__ = []

    def __repr__(self):
        return self.__module__ + ".undefined"

    def __str__(self):
        return "undefined"

    def __bool__(self):
        return False


undefined = _undefined_class()
syntax_error = _undefined_class()  # same as undefined, but has separate identity
del _undefined_class


# ----------------------------------------------------------------------
# Non-Numbers: NaN, Infinity, -Infinity
#
# ECMAScript has official support for non-number floats, although
# strict JSON does not.  Python doesn't either.  So to support the
# full JavaScript behavior we must try to add them into Python, which
# is unfortunately a bit of black magic.  If our python implementation
# happens to be built on top of IEEE 754 we can probably trick python
# into using real floats.  Otherwise we must simulate it with classes.


def _nonnumber_float_constants():
    """Try to return the Nan, Infinity, and -Infinity float values.

    This is necessarily complex because there is no standard
    platform-independent way to do this in Python as the language
    (opposed to some implementation of it) doesn't discuss
    non-numbers.  We try various strategies from the best to the
    worst.

    If this Python interpreter uses the IEEE 754 floating point
    standard then the returned values will probably be real instances
    of the 'float' type.  Otherwise a custom class object is returned
    which will attempt to simulate the correct behavior as much as
    possible.

    """
    try:
        # First, try (mostly portable) float constructor.  Works under
        # Linux x86 (gcc) and some Unices.
        nan = float("nan")
        inf = float("inf")
        neginf = float("-inf")
    except ValueError:
        try:
            # Try the AIX (PowerPC) float constructors
            nan = float("NaNQ")
            inf = float("INF")
            neginf = float("-INF")
        except ValueError:
            try:
                # Next, try binary unpacking.  Should work under
                # platforms using IEEE 754 floating point.
                import struct
                import sys

                xnan = "7ff8000000000000".decode("hex")  # Quiet NaN
                xinf = "7ff0000000000000".decode("hex")
                xcheck = "bdc145651592979d".decode("hex")  # -3.14159e-11
                # Could use float.__getformat__, but it is a new python feature,
                # so we use sys.byteorder.
                if sys.byteorder == "big":
                    nan = struct.unpack("d", xnan)[0]
                    inf = struct.unpack("d", xinf)[0]
                    check = struct.unpack("d", xcheck)[0]
                else:
                    nan = struct.unpack("d", xnan[::-1])[0]
                    inf = struct.unpack("d", xinf[::-1])[0]
                    check = struct.unpack("d", xcheck[::-1])[0]
                neginf = -inf
                if check != -3.14159e-11:
                    raise ValueError("Unpacking raw IEEE 754 floats does not work")
            except (ValueError, TypeError):
                # Punt, make some fake classes to simulate.  These are
                # not perfect though.  For instance nan * 1.0 == nan,
                # as expected, but 1.0 * nan == 0.0, which is wrong.
                class nan(float):
                    """An approximation of the NaN (not a number) floating point number."""

                    def __repr__(self):
                        return "nan"

                    def __str__(self):
                        return "nan"

                    def __add__(self, x):
                        return self

                    def __radd__(self, x):
                        return self

                    def __sub__(self, x):
                        return self

                    def __rsub__(self, x):
                        return self

                    def __mul__(self, x):
                        return self

                    def __rmul__(self, x):
                        return self

                    def __div__(self, x):
                        return self

                    def __rdiv__(self, x):
                        return self

                    def __divmod__(self, x):
                        return (self, self)

                    def __rdivmod__(self, x):
                        return (self, self)

                    def __mod__(self, x):
                        return self

                    def __rmod__(self, x):
                        return self

                    def __pow__(self, exp):
                        return self

                    def __rpow__(self, exp):
                        return self

                    def __neg__(self):
                        return self

                    def __pos__(self):
                        return self

                    def __abs__(self):
                        return self

                    def __lt__(self, x):
                        return False

                    def __le__(self, x):
                        return False

                    def __eq__(self, x):
                        return False

                    def __neq__(self, x):
                        return True

                    def __ge__(self, x):
                        return False

                    def __gt__(self, x):
                        return False

                    def __complex__(self, *a):
                        raise NotImplementedError(
                            "NaN can not be converted to a complex"
                        )

                if decimal:
                    nan = decimal.Decimal("NaN")
                else:
                    nan = nan()

                class inf(float):
                    """An approximation of the +Infinity floating point number."""

                    def __repr__(self):
                        return "inf"

                    def __str__(self):
                        return "inf"

                    def __add__(self, x):
                        return self

                    def __radd__(self, x):
                        return self

                    def __sub__(self, x):
                        return self

                    def __rsub__(self, x):
                        return self

                    def __mul__(self, x):
                        if x is neginf or x < 0:
                            return neginf
                        elif x == 0:
                            return nan
                        else:
                            return self

                    def __rmul__(self, x):
                        return self.__mul__(x)

                    def __div__(self, x):
                        if x == 0:
                            raise ZeroDivisionError("float division")
                        elif x < 0:
                            return neginf
                        else:
                            return self

                    def __rdiv__(self, x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return 0.0

                    def __divmod__(self, x):
                        if x == 0:
                            raise ZeroDivisionError("float divmod()")
                        elif x < 0:
                            return (nan, nan)
                        else:
                            return (self, self)

                    def __rdivmod__(self, x):
                        if x is inf or x is neginf or x is nan:
                            return (nan, nan)
                        return (0.0, x)

                    def __mod__(self, x):
                        if x == 0:
                            raise ZeroDivisionError("float modulo")
                        else:
                            return nan

                    def __rmod__(self, x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return x

                    def __pow__(self, exp):
                        if exp == 0:
                            return 1.0
                        else:
                            return self

                    def __rpow__(self, x):
                        if -1 < x < 1:
                            return 0.0
                        elif x == 1.0:
                            return 1.0
                        elif x is nan or x is neginf or x < 0:
                            return nan
                        else:
                            return self

                    def __neg__(self):
                        return neginf

                    def __pos__(self):
                        return self

                    def __abs__(self):
                        return self

                    def __lt__(self, x):
                        return False

                    def __le__(self, x):
                        if x is self:
                            return True
                        else:
                            return False

                    def __eq__(self, x):
                        if x is self:
                            return True
                        else:
                            return False

                    def __neq__(self, x):
                        if x is self:
                            return False
                        else:
                            return True

                    def __ge__(self, x):
                        return True

                    def __gt__(self, x):
                        return True

                    def __complex__(self, *a):
                        raise NotImplementedError(
                            "Infinity can not be converted to a complex"
                        )

                if decimal:
                    inf = decimal.Decimal("Infinity")
                else:
                    inf = inf()

                class neginf(float):
                    """An approximation of the -Infinity floating point number."""

                    def __repr__(self):
                        return "-inf"

                    def __str__(self):
                        return "-inf"

                    def __add__(self, x):
                        return self

                    def __radd__(self, x):
                        return self

                    def __sub__(self, x):
                        return self

                    def __rsub__(self, x):
                        return self

                    def __mul__(self, x):
                        if x is self or x < 0:
                            return inf
                        elif x == 0:
                            return nan
                        else:
                            return self

                    def __rmul__(self, x):
                        return self.__mul__(self)

                    def __div__(self, x):
                        if x == 0:
                            raise ZeroDivisionError("float division")
                        elif x < 0:
                            return inf
                        else:
                            return self

                    def __rdiv__(self, x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return -0.0

                    def __divmod__(self, x):
                        if x == 0:
                            raise ZeroDivisionError("float divmod()")
                        elif x < 0:
                            return (nan, nan)
                        else:
                            return (self, self)

                    def __rdivmod__(self, x):
                        if x is inf or x is neginf or x is nan:
                            return (nan, nan)
                        return (-0.0, x)

                    def __mod__(self, x):
                        if x == 0:
                            raise ZeroDivisionError("float modulo")
                        else:
                            return nan

                    def __rmod__(self, x):
                        if x is inf or x is neginf or x is nan:
                            return nan
                        return x

                    def __pow__(self, exp):
                        if exp == 0:
                            return 1.0
                        else:
                            return self

                    def __rpow__(self, x):
                        if x is nan or x is inf or x is inf:
                            return nan
                        return 0.0

                    def __neg__(self):
                        return inf

                    def __pos__(self):
                        return self

                    def __abs__(self):
                        return inf

                    def __lt__(self, x):
                        return True

                    def __le__(self, x):
                        return True

                    def __eq__(self, x):
                        if x is self:
                            return True
                        else:
                            return False

                    def __neq__(self, x):
                        if x is self:
                            return False
                        else:
                            return True

                    def __ge__(self, x):
                        if x is self:
                            return True
                        else:
                            return False

                    def __gt__(self, x):
                        return False

                    def __complex__(self, *a):
                        raise NotImplementedError(
                            "-Infinity can not be converted to a complex"
                        )

                if decimal:
                    neginf = decimal.Decimal("-Infinity")
                else:
                    neginf = neginf(0)
    return nan, inf, neginf


nan, inf, neginf = _nonnumber_float_constants()
del _nonnumber_float_constants


# ----------------------------------------------------------------------
# Integers


class json_int((1).__class__):  # Have to specify base this way to satisfy 2to3
    """A subclass of the Python int/long that remembers its format (hex,octal,etc).

    Initialize it the same as an int, but also accepts an additional keyword
    argument 'number_format' which should be one of the NUMBER_FORMAT_* values.

        n = json_int( x[, base, number_format=NUMBER_FORMAT_DECIMAL] )

    """

    def __new__(cls, *args, **kwargs):
        if "number_format" in kwargs:
            number_format = kwargs["number_format"]
            del kwargs["number_format"]
            if number_format not in (
                NUMBER_FORMAT_DECIMAL,
                NUMBER_FORMAT_HEX,
                NUMBER_FORMAT_OCTAL,
                NUMBER_FORMAT_LEGACYOCTAL,
                NUMBER_FORMAT_BINARY,
            ):
                raise TypeError("json_int(): Invalid value for number_format argument")
        else:
            number_format = NUMBER_FORMAT_DECIMAL
        obj = super(json_int, cls).__new__(cls, *args, **kwargs)
        obj._jsonfmt = number_format
        return obj

    @property
    def number_format(self):
        """The original radix format of the number"""
        return self._jsonfmt

    def json_format(self):
        """Returns the integer value formatted as a JSON literal"""
        fmt = self._jsonfmt
        if fmt == NUMBER_FORMAT_HEX:
            return format(self, "#x")
        elif fmt == NUMBER_FORMAT_OCTAL:
            return format(self, "#o")
        elif fmt == NUMBER_FORMAT_BINARY:
            return format(self, "#b")
        elif fmt == NUMBER_FORMAT_LEGACYOCTAL:
            if self == 0:
                return "0"  # For some reason Python's int doesn't do '00'
            elif self < 0:
                return "-0%o" % (-self)
            else:
                return "0%o" % self
        else:
            return str(self)


# ----------------------------------------------------------------------
# String processing helpers


def skipstringsafe(s, start=0, end=None):
    i = start
    # if end is None:
    #    end = len(s)
    unsafe = helpers.unsafe_string_chars
    while i < end and s[i] not in unsafe:
        # c = s[i]
        # if c in unsafe_string_chars:
        #    break
        i += 1
    return i


def skipstringsafe_slow(s, start=0, end=None):
    i = start
    if end is None:
        end = len(s)
    while i < end:
        c = s[i]
        if c == '"' or c == "'" or c == "\\" or ord(c) <= 0x1F:
            break
        i += 1
    return i


def extend_list_with_sep(orig_seq, extension_seq, sepchar=""):
    if not sepchar:
        orig_seq.extend(extension_seq)
    else:
        for i, x in enumerate(extension_seq):
            if i > 0:
                orig_seq.append(sepchar)
            orig_seq.append(x)


def extend_and_flatten_list_with_sep(orig_seq, extension_seq, separator=""):
    for i, part in enumerate(extension_seq):
        if i > 0 and separator:
            orig_seq.append(separator)
        orig_seq.extend(part)


# ----------------------------------------------------------------------
# Unicode UTF-32
# ----------------------------------------------------------------------


def _make_raw_bytes(byte_list):
    """Takes a list of byte values (numbers) and returns a bytes (Python 3) or string (Python 2)"""
    if _py_major >= 3:
        b = bytes(byte_list)
    else:
        b = "".join(chr(n) for n in byte_list)
    return b


class utf32(codecs.CodecInfo):
    """Unicode UTF-32 and UCS4 encoding/decoding support.

    This is for older Pythons whch did not have UTF-32 codecs.

    JSON requires that all JSON implementations must support the
    UTF-32 encoding (as well as UTF-8 and UTF-16).  But earlier
    versions of Python did not provide a UTF-32 codec, so we must
    implement UTF-32 ourselves in case we need it.

    See http://en.wikipedia.org/wiki/UTF-32

    """

    BOM_UTF32_BE = _make_raw_bytes([0, 0, 0xFE, 0xFF])  # '\x00\x00\xfe\xff'
    BOM_UTF32_LE = _make_raw_bytes([0xFF, 0xFE, 0, 0])  # '\xff\xfe\x00\x00'

    @staticmethod
    def lookup(name):
        """A standard Python codec lookup function for UCS4/UTF32.

        If if recognizes an encoding name it returns a CodecInfo
        structure which contains the various encode and decoder
        functions to use.

        """
        ci = None
        name = name.upper()
        if name in (
            "UCS4BE",
            "UCS-4BE",
            "UCS-4-BE",
            "UTF32BE",
            "UTF-32BE",
            "UTF-32-BE",
        ):
            ci = codecs.CodecInfo(
                utf32.utf32be_encode, utf32.utf32be_decode, name="utf-32be"
            )
        elif name in (
            "UCS4LE",
            "UCS-4LE",
            "UCS-4-LE",
            "UTF32LE",
            "UTF-32LE",
            "UTF-32-LE",
        ):
            ci = codecs.CodecInfo(
                utf32.utf32le_encode, utf32.utf32le_decode, name="utf-32le"
            )
        elif name in ("UCS4", "UCS-4", "UTF32", "UTF-32"):
            ci = codecs.CodecInfo(utf32.encode, utf32.decode, name="utf-32")
        return ci

    @staticmethod
    def encode(obj, errors="strict", endianness=None, include_bom=True):
        """Encodes a Unicode string into a UTF-32 encoded byte string.

        Returns a tuple: (bytearray, num_chars)

        The errors argument should be one of 'strict', 'ignore', or 'replace'.

        The endianness should be one of:
            * 'B', '>', or 'big'     -- Big endian
            * 'L', '<', or 'little'  -- Little endien
            * None                   -- Default, from sys.byteorder

        If include_bom is true a Byte-Order Mark will be written to
        the beginning of the string, otherwise it will be omitted.

        """
        import sys
        import struct

        # Make a container that can store bytes
        if _py_major >= 3:
            f = bytearray()
            write = f.extend

            def tobytes():
                return bytes(f)
        else:
            try:
                import io as sio
            except ImportError:
                import io as sio
            f = sio.StringIO()
            write = f.write
            tobytes = f.getvalue

        if not endianness:
            endianness = sys.byteorder

        if endianness.upper()[0] in ("B>"):
            big_endian = True
        elif endianness.upper()[0] in ("L<"):
            big_endian = False
        else:
            raise ValueError(
                "Invalid endianness %r: expected 'big', 'little', or None" % endianness
            )

        pack = struct.pack
        packspec = ">L" if big_endian else "<L"

        num_chars = 0

        if include_bom:
            if big_endian:
                write(utf32.BOM_UTF32_BE)
            else:
                write(utf32.BOM_UTF32_LE)
            num_chars += 1

        for pos, c in enumerate(obj):
            n = ord(c)
            if 0xD800 <= n <= 0xDFFF:  # surrogate codepoints are prohibited by UTF-32
                if errors == "ignore":
                    pass
                elif errors == "replace":
                    n = 0xFFFD
                else:
                    raise UnicodeEncodeError(
                        "utf32",
                        obj,
                        pos,
                        pos + 1,
                        "surrogate code points from U+D800 to U+DFFF are not allowed",
                    )
            write(pack(packspec, n))
            num_chars += 1

        return (tobytes(), num_chars)

    @staticmethod
    def utf32le_encode(obj, errors="strict", include_bom=False):
        """Encodes a Unicode string into a UTF-32LE (little endian) encoded byte string."""
        return utf32.encode(obj, errors=errors, endianness="L", include_bom=include_bom)

    @staticmethod
    def utf32be_encode(obj, errors="strict", include_bom=False):
        """Encodes a Unicode string into a UTF-32BE (big endian) encoded byte string."""
        return utf32.encode(obj, errors=errors, endianness="B", include_bom=include_bom)

    @staticmethod
    def decode(obj, errors="strict", endianness=None):
        """Decodes a UTF-32 byte string into a Unicode string.

        Returns tuple (bytearray, num_bytes)

        The errors argument shold be one of 'strict', 'ignore',
        'replace', 'backslashreplace', or 'xmlcharrefreplace'.

        The endianness should either be None (for auto-guessing), or a
        word that starts with 'B' (big) or 'L' (little).

        Will detect a Byte-Order Mark. If a BOM is found and endianness
        is also set, then the two must match.

        If neither a BOM is found nor endianness is set, then big
        endian order is assumed.

        """
        import struct
        import sys

        maxunicode = sys.maxunicode
        unpack = struct.unpack

        # Detect BOM
        if obj.startswith(utf32.BOM_UTF32_BE):
            bom_endianness = "B"
            start = len(utf32.BOM_UTF32_BE)
        elif obj.startswith(utf32.BOM_UTF32_LE):
            bom_endianness = "L"
            start = len(utf32.BOM_UTF32_LE)
        else:
            bom_endianness = None
            start = 0

        num_bytes = start

        if endianness is None:
            if bom_endianness is None:
                endianness = sys.byteorder.upper()[0]  # Assume platform default
            else:
                endianness = bom_endianness
        else:
            endianness = endianness[0].upper()
            if bom_endianness and endianness != bom_endianness:
                raise UnicodeDecodeError(
                    "utf32", obj, 0, start, "BOM does not match expected byte order"
                )

        # Check for truncated last character
        if ((len(obj) - start) % 4) != 0:
            raise UnicodeDecodeError(
                "utf32", obj, start, len(obj), "Data length not a multiple of 4 bytes"
            )

        # Start decoding characters
        chars = []
        packspec = ">L" if endianness == "B" else "<L"
        i = 0
        for i in range(start, len(obj), 4):
            seq = obj[i : i + 4]
            n = unpack(packspec, seq)[0]
            num_bytes += 4

            if n > maxunicode or (0xD800 <= n <= 0xDFFF):
                if errors == "strict":
                    raise UnicodeDecodeError(
                        "utf32", obj, i, i + 4, "Invalid code point U+%04X" % n
                    )
                elif errors == "replace":
                    chars.append(chr(0xFFFD))
                elif errors == "backslashreplace":
                    if n > 0xFFFF:
                        esc = "\\u%04x" % (n,)
                    else:
                        esc = "\\U%08x" % (n,)
                    for esc_c in esc:
                        chars.append(esc_c)
                elif errors == "xmlcharrefreplace":
                    esc = "&#%d;" % (n,)
                    for esc_c in esc:
                        chars.append(esc_c)
                else:  # ignore
                    pass
            else:
                chars.append(helpers.safe_unichr(n))
        return ("".join(chars), num_bytes)

    @staticmethod
    def utf32le_decode(obj, errors="strict"):
        """Decodes a UTF-32LE (little endian) byte string into a Unicode string."""
        return utf32.decode(obj, errors=errors, endianness="L")

    @staticmethod
    def utf32be_decode(obj, errors="strict"):
        """Decodes a UTF-32BE (big endian) byte string into a Unicode string."""
        return utf32.decode(obj, errors=errors, endianness="B")


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------


def _make_unsafe_string_chars():
    import unicodedata

    unsafe = []
    for c in [chr(i) for i in range(0x100)]:
        if c == '"' or c == "\\" or unicodedata.category(c) in ["Cc", "Cf", "Zl", "Zp"]:
            unsafe.append(c)
    return "".join(unsafe)


class helpers(object):
    """A set of utility functions."""

    hexdigits = "0123456789ABCDEFabcdef"
    octaldigits = "01234567"
    unsafe_string_chars = _make_unsafe_string_chars()

    import sys

    maxunicode = sys.maxunicode

    always_use_custom_codecs = False  # If True use demjson's codecs
    # before system codecs. This
    # is mainly here for testing.

    javascript_reserved_words = frozenset(
        [
            # Keywords (plus "let")  (ECMAScript 6 section 11.6.2.1)
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "debugger",
            "default",
            "delete",
            "do",
            "else",
            "export",
            "extends",
            "finally",
            "for",
            "function",
            "if",
            "import",
            "in",
            "instanceof",
            "let",
            "new",
            "return",
            "super",
            "switch",
            "this",
            "throw",
            "try",
            "typeof",
            "var",
            "void",
            "while",
            "with",
            "yield",
            # Future reserved words (ECMAScript 6 section 11.6.2.2)
            "enum",
            "implements",
            "interface",
            "package",
            "private",
            "protected",
            "public",
            "static",
            # null/boolean literals
            "null",
            "true",
            "false",
        ]
    )

    @staticmethod
    def make_raw_bytes(byte_list):
        """Constructs a byte array (bytes in Python 3, str in Python 2) from a list of byte values (0-255)."""
        return _make_raw_bytes(byte_list)

    @staticmethod
    def is_hex_digit(c):
        """Determines if the given character is a valid hexadecimal digit (0-9, a-f, A-F)."""
        return c in helpers.hexdigits

    @staticmethod
    def is_octal_digit(c):
        """Determines if the given character is a valid octal digit (0-7)."""
        return c in helpers.octaldigits

    @staticmethod
    def is_binary_digit(c):
        """Determines if the given character is a valid binary digit (0 or 1)."""
        return c == "0" or c == "1"

    @staticmethod
    def char_is_json_ws(c):
        """Determines if the given character is a JSON white-space character"""
        return c in " \t\n\r"

    @staticmethod
    def safe_unichr(codepoint):
        """Just like Python's unichr() but works in narrow-Unicode Pythons."""
        if codepoint >= 0x10000 and codepoint > helpers.maxunicode:
            # Narrow-Unicode python, construct a UTF-16 surrogate pair.
            w1, w2 = helpers.make_surrogate_pair(codepoint)
            if w2 is None:
                c = chr(w1)
            else:
                c = chr(w1) + chr(w2)
        else:
            c = chr(codepoint)
        return c

    @staticmethod
    def char_is_unicode_ws(c):
        """Determines if the given character is a Unicode space character"""
        if not isinstance(c, str):
            c = str(c)
        if c in " \t\n\r\f\v":
            return True
        import unicodedata

        return unicodedata.category(c) == "Zs"

    @staticmethod
    def char_is_json_eol(c):
        """Determines if the given character is a JSON line separator"""
        return c in "\n\r"

    @staticmethod
    def char_is_unicode_eol(c):
        """Determines if the given character is a Unicode line or
        paragraph separator. These correspond to CR and LF as well as
        Unicode characters in the Zl or Zp categories.

        """
        return c in "\r\n\u2028\u2029"

    @staticmethod
    def char_is_identifier_leader(c):
        """Determines if the character may be the first character of a
        JavaScript identifier.
        """
        return c.isalpha() or c in "_$"

    @staticmethod
    def char_is_identifier_tail(c):
        """Determines if the character may be part of a JavaScript
        identifier.
        """
        return c.isalnum() or c in "_$\u200c\u200d"

    @staticmethod
    def extend_and_flatten_list_with_sep(orig_seq, extension_seq, separator=""):
        for i, part in enumerate(extension_seq):
            if i > 0 and separator:
                orig_seq.append(separator)
            orig_seq.extend(part)

    @staticmethod
    def strip_format_control_chars(txt):
        """Filters out all Unicode format control characters from the string.

        ECMAScript permits any Unicode "format control characters" to
        appear at any place in the source code.  They are to be
        ignored as if they are not there before any other lexical
        tokenization occurs.  Note that JSON does not allow them,
        except within string literals.

        * Ref. ECMAScript section 7.1.
        * http://en.wikipedia.org/wiki/Unicode_control_characters

        There are dozens of Format Control Characters, for example:
            U+00AD   SOFT HYPHEN
            U+200B   ZERO WIDTH SPACE
            U+2060   WORD JOINER

        """
        import unicodedata

        txt2 = [c for c in txt if unicodedata.category(str(c)) != "Cf"]

        # 2to3 NOTE: The following is needed to work around a broken
        # Python3 conversion in which filter() will be transformed
        # into a list rather than a string.
        if not isinstance(txt2, str):
            txt2 = "".join(txt2)
        return txt2

    @staticmethod
    def lookup_codec(encoding):
        """Wrapper around codecs.lookup().

        Returns None if codec not found, rather than raising a LookupError.
        """
        import codecs

        if isinstance(encoding, codecs.CodecInfo):
            return encoding
        encoding = encoding.lower()
        import codecs

        if helpers.always_use_custom_codecs:
            # Try custom utf32 first, then standard python codecs
            cdk = utf32.lookup(encoding)
            if not cdk:
                try:
                    cdk = codecs.lookup(encoding)
                except LookupError:
                    cdk = None
        else:
            # Try standard python codecs first, then custom utf32
            try:
                cdk = codecs.lookup(encoding)
            except LookupError:
                cdk = utf32.lookup(encoding)
        return cdk

    @staticmethod
    def auto_detect_encoding(s):
        """Takes a string (or byte array) and tries to determine the Unicode encoding it is in.

        Returns the encoding name, as a string.

        """
        if not s or len(s) == 0:
            return "utf-8"

        # Get the byte values of up to the first 4 bytes
        ords = []
        for i in range(0, min(len(s), 4)):
            x = s[i]
            if isinstance(x, str):
                x = ord(x)
            ords.append(x)

        # Look for BOM marker
        import codecs

        bom2, bom3, bom4 = None, None, None
        if len(s) >= 2:
            bom2 = s[:2]
        if len(s) >= 3:
            bom3 = s[:3]
        if len(s) >= 4:
            bom4 = s[:4]

        # Assign values of first four bytes to: a, b, c, d; and last byte to: z
        a, b, c, d, z = None, None, None, None, None
        if len(s) >= 1:
            a = ords[0]
        if len(s) >= 2:
            b = ords[1]
        if len(s) >= 3:
            c = ords[2]
        if len(s) >= 4:
            d = ords[3]

        z = s[-1]
        if isinstance(z, str):
            z = ord(z)

        if bom4 and (
            (hasattr(codecs, "BOM_UTF32_LE") and bom4 == codecs.BOM_UTF32_LE)
            or (bom4 == utf32.BOM_UTF32_LE)
        ):
            encoding = "utf-32le"
            s = s[4:]
        elif bom4 and (
            (hasattr(codecs, "BOM_UTF32_BE") and bom4 == codecs.BOM_UTF32_BE)
            or (bom4 == utf32.BOM_UTF32_BE)
        ):
            encoding = "utf-32be"
            s = s[4:]
        elif bom2 and bom2 == codecs.BOM_UTF16_LE:
            encoding = "utf-16le"
            s = s[2:]
        elif bom2 and bom2 == codecs.BOM_UTF16_BE:
            encoding = "utf-16be"
            s = s[2:]
        elif bom3 and bom3 == codecs.BOM_UTF8:
            encoding = "utf-8"
            s = s[3:]

        # No BOM, so autodetect encoding used by looking at first four
        # bytes according to RFC 4627 section 3.  The first and last bytes
        # in a JSON document will be ASCII.  The second byte will be ASCII
        # unless the first byte was a quotation mark.

        elif (
            len(s) >= 4 and a == 0 and b == 0 and c == 0 and d != 0
        ):  # UTF-32BE  (0 0 0 x)
            encoding = "utf-32be"
        elif (
            len(s) >= 4 and a != 0 and b == 0 and c == 0 and d == 0 and z == 0
        ):  # UTF-32LE  (x 0 0 0 [... 0])
            encoding = "utf-32le"
        elif len(s) >= 2 and a == 0 and b != 0:  # UTF-16BE  (0 x)
            encoding = "utf-16be"
        elif len(s) >= 2 and a != 0 and b == 0 and z == 0:  # UTF-16LE  (x 0 [... 0])
            encoding = "utf-16le"
        elif ord("\t") <= a <= 127:
            # First byte appears to be ASCII, so guess UTF-8.
            encoding = "utf8"
        else:
            raise ValueError("Can not determine the Unicode encoding for byte stream")

        return encoding

    @staticmethod
    def unicode_decode(txt, encoding=None):
        """Takes a string (or byte array) and tries to convert it to a Unicode string.

        Returns a named tuple:  (string, codec, bom)

        The 'encoding' argument, if supplied, should either the name of
        a character encoding, or an instance of codecs.CodecInfo.  If
        the encoding argument is None or "auto" then the encoding is
        automatically determined, if possible.

        Any BOM (Byte Order Mark) that is found at the beginning of the
        input will be stripped off and placed in the 'bom' portion of
        the returned value.

        """
        if isinstance(txt, str):
            res = _namedtuple("DecodedString", ["string", "codec", "bom"])(
                txt, None, None
            )
        else:
            if encoding is None or encoding == "auto":
                encoding = helpers.auto_detect_encoding(txt)

            cdk = helpers.lookup_codec(encoding)
            if not cdk:
                raise LookupError("Can not find codec for encoding %r" % encoding)

            try:
                # Determine if codec takes arguments; try a decode of nothing
                cdk.decode(helpers.make_raw_bytes([]), errors="strict")
            except TypeError:
                cdk_kw = {}  # This coded doesn't like the errors argument
            else:
                cdk_kw = {"errors": "strict"}

            unitxt, numbytes = cdk.decode(txt, **cdk_kw)  # DO THE DECODE HERE!

            # Remove BOM if present
            if len(unitxt) > 0 and unitxt[0] == "\ufeff":
                bom = cdk.encode(unitxt[0])[0]
                unitxt = unitxt[1:]
            elif len(unitxt) > 0 and unitxt[0] == "\ufffe":  # Reversed BOM
                raise UnicodeDecodeError(
                    cdk.name, txt, 0, 0, "Wrong byte order, found reversed BOM U+FFFE"
                )
            else:
                bom = None

            res = _namedtuple("DecodedString", ["string", "codec", "bom"])(
                unitxt, cdk, bom
            )
        return res

    @staticmethod
    def surrogate_pair_as_unicode(c1, c2):
        """Takes a pair of unicode surrogates and returns the equivalent unicode character.

        The input pair must be a surrogate pair, with c1 in the range
        U+D800 to U+DBFF and c2 in the range U+DC00 to U+DFFF.

        """
        n1, n2 = ord(c1), ord(c2)
        if n1 < 0xD800 or n1 > 0xDBFF or n2 < 0xDC00 or n2 > 0xDFFF:
            raise JSONDecodeError("illegal Unicode surrogate pair", (c1, c2))
        a = n1 - 0xD800
        b = n2 - 0xDC00
        v = (a << 10) | b
        v += 0x10000
        return helpers.safe_unichr(v)

    @staticmethod
    def unicode_as_surrogate_pair(c):
        """Takes a single unicode character and returns a sequence of surrogate pairs.

        The output of this function is a tuple consisting of one or two unicode
        characters, such that if the input character is outside the BMP range
        then the output is a two-character surrogate pair representing that character.

        If the input character is inside the BMP then the output tuple will have
        just a single character...the same one.

        """
        n = ord(c)
        w1, w2 = helpers.make_surrogate_pair(n)
        if w2 is None:
            return (chr(w1),)
        else:
            return (chr(w1), chr(w2))

    @staticmethod
    def make_surrogate_pair(codepoint):
        """Given a Unicode codepoint (int) returns a 2-tuple of surrogate codepoints."""
        if codepoint < 0x10000:
            return (codepoint, None)  # in BMP, surrogate pair not required
        v = codepoint - 0x10000
        vh = (v >> 10) & 0x3FF  # highest 10 bits
        vl = v & 0x3FF  # lowest 10 bits
        w1 = 0xD800 | vh
        w2 = 0xDC00 | vl
        return (w1, w2)

    @staticmethod
    def isnumbertype(obj):
        """Is the object of a Python number type (excluding complex)?"""
        return (
            isinstance(obj, (int, float))
            and not isinstance(obj, bool)
            or obj is nan
            or obj is inf
            or obj is neginf
            or (decimal and isinstance(obj, decimal.Decimal))
        )

    @staticmethod
    def is_negzero(n):
        """Is the number value a negative zero?"""
        if isinstance(n, float):
            return n == 0.0 and repr(n).startswith("-")
        elif decimal and isinstance(n, decimal.Decimal):
            return n.is_zero() and n.is_signed()
        else:
            return False

    @staticmethod
    def is_nan(n):
        """Is the number a NaN (not-a-number)?"""
        if isinstance(n, float):
            return n is nan or n.hex() == "nan" or n != n
        elif decimal and isinstance(n, decimal.Decimal):
            return n.is_nan()
        else:
            return False

    @staticmethod
    def is_infinite(n):
        """Is the number infinite?"""
        if isinstance(n, float):
            return n is inf or n is neginf or n.hex() in ("inf", "-inf")
        elif decimal and isinstance(n, decimal.Decimal):
            return n.is_infinite()
        else:
            return False

    @staticmethod
    def isstringtype(obj):
        """Is the object of a Python string type?"""
        if isinstance(obj, str):
            return True
        # Must also check for some other pseudo-string types
        import collections

        return isinstance(obj, (str,)) or isinstance(obj, collections.UserString)
        ## or isinstance(obj, UserString.MutableString)

    @staticmethod
    def decode_hex(hexstring):
        """Decodes a hexadecimal string into it's integer value."""
        # We don't use the builtin 'hex' codec in python since it can
        # not handle odd numbers of digits, nor raise the same type
        # of exceptions we want to.
        n = 0
        for c in hexstring:
            if "0" <= c <= "9":
                d = ord(c) - ord("0")
            elif "a" <= c <= "f":
                d = ord(c) - ord("a") + 10
            elif "A" <= c <= "F":
                d = ord(c) - ord("A") + 10
            else:
                raise ValueError("Not a hexadecimal number", hexstring)
            # Could use ((n << 4 ) | d), but python 2.3 issues a FutureWarning.
            n = (n * 16) + d
        return n

    @staticmethod
    def decode_octal(octalstring):
        """Decodes an octal string into it's integer value."""
        n = 0
        for c in octalstring:
            if "0" <= c <= "7":
                d = ord(c) - ord("0")
            else:
                raise ValueError("Not an octal number", octalstring)
            # Could use ((n << 3 ) | d), but python 2.3 issues a FutureWarning.
            n = (n * 8) + d
        return n

    @staticmethod
    def decode_binary(binarystring):
        """Decodes a binary string into it's integer value."""
        n = 0
        for c in binarystring:
            if c == "0":
                d = 0
            elif c == "1":
                d = 1
            else:
                raise ValueError("Not an binary number", binarystring)
            # Could use ((n << 3 ) | d), but python 2.3 issues a FutureWarning.
            n = (n * 2) + d
        return n

    @staticmethod
    def format_timedelta_iso(td):
        """Encodes a datetime.timedelta into ISO-8601 Time Period format."""
        d = td.days
        s = td.seconds
        ms = td.microseconds
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        a = ["P"]
        if d:
            a.append("%dD" % d)
        if h or m or s or ms:
            a.append("T")
        if h:
            a.append("%dH" % h)
        if m:
            a.append("%dM" % m)
        if s or ms:
            if ms:
                a.append("%d.%06d" % (s, ms))
            else:
                a.append("%d" % s)
        if len(a) == 1:
            a.append("T0S")
        return "".join(a)


# ----------------------------------------------------------------------
# File position indicator
# ----------------------------------------------------------------------


class position_marker(object):
    """A position marks a specific place in a text document.
    It consists of the following attributes:

        * line - The line number, starting at 1
        * column - The column on the line, starting at 0
        * char_position - The number of characters from the start of
                          the document, starting at 0
        * text_after - (optional) a short excerpt of the text of
                       document starting at the current position

    Lines are separated by any Unicode line separator character. As an
    exception a CR+LF character pair is treated as being a single line
    separator demarcation.

    Columns are simply a measure of the number of characters after the
    start of a new line, starting at 0.  Visual effects caused by
    Unicode characters such as combining characters, bidirectional
    text, zero-width characters and so on do not affect the
    computation of the column regardless of visual appearance.

    The char_position is a count of the number of characters since the
    beginning of the document, starting at 0. As used within the
    buffered_stream class, if the document starts with a Unicode Byte
    Order Mark (BOM), the BOM prefix is NOT INCLUDED in the count.

    """

    def __init__(self, offset=0, line=1, column=0, text_after=None):
        self.__char_position = offset
        self.__line = line
        self.__column = column
        self.__text_after = text_after
        self.__at_end = False
        self.__last_was_cr = False

    @property
    def line(self):
        """The current line within the document, starts at 1."""
        return self.__line

    @property
    def column(self):
        """The current character column from the beginning of the
        document, starts at 0.
        """
        return self.__column

    @property
    def char_position(self):
        """The current character offset from the beginning of the
        document, starts at 0.
        """
        return self.__char_position

    @property
    def at_start(self):
        """Returns True if the position is at the start of the document."""
        return self.char_position == 0

    @property
    def at_end(self):
        """Returns True if the position is at the end of the document.

        This property must be set by the user.
        """
        return self.__at_end

    @at_end.setter
    def at_end(self, b):
        """Sets the at_end property to True or False."""
        self.__at_end = bool(b)

    @property
    def text_after(self):
        """Returns a textual excerpt starting at the current position.

        This property must be set by the user.
        """
        return self.__at_end

    @text_after.setter
    def text_after(self, value):
        """Sets the text_after property to a given string."""
        self.__text_after = value

    def __repr__(self):
        s = "%s(offset=%r,line=%r,column=%r" % (
            self.__class__.__name__,
            self.__char_position,
            self.__line,
            self.__column,
        )
        if self.text_after:
            s += ",text_after=%r" % (self.text_after,)
        s += ")"
        return s

    def describe(self, show_text=True):
        """Returns a human-readable description of the position, in English."""
        s = "line %d, column %d, offset %d" % (
            self.__line,
            self.__column,
            self.__char_position,
        )
        if self.at_start:
            s += " (AT-START)"
        elif self.at_end:
            s += " (AT-END)"
        if show_text and self.text_after:
            s += ", text %r" % (self.text_after)
        return s

    def __str__(self):
        """Same as the describe() function."""
        return self.describe(show_text=True)

    def copy(self):
        """Create a copy of the position object."""
        p = self.__class__()
        p.__char_position = self.__char_position
        p.__line = self.__line
        p.__column = self.__column
        p.text_after = self.__text_after
        p.at_end = self.at_end
        p.__last_was_cr = self.__last_was_cr
        return p

    def rewind(self):
        """Set the position to the start of the document."""
        if not self.at_start:
            self.text_after = None
            self.at_end = False
        self.__char_position = 0
        self.__line = 1
        self.__column = 0
        self.__last_was_cr = False

    def advance(self, s):
        """Advance the position from its current place according to
        the given string of characters.

        """
        if s:
            self.text_after = None
        for c in s:
            self.__char_position += 1
            if c == "\n" and self.__last_was_cr:
                self.__last_was_cr = False
            elif helpers.char_is_unicode_eol(c):
                self.__line += 1
                self.__column = 0
                self.__last_was_cr = c == "\r"
            else:
                self.__column += 1
                self.__last_was_cr = False


# ----------------------------------------------------------------------
# Buffered Stream Reader
# ----------------------------------------------------------------------


class buffered_stream(object):
    """A helper class for the JSON parser.

    It allows for reading an input document, while handling some
    low-level Unicode issues as well as tracking the current position
    in terms of line and column position.

    """

    def __init__(self, txt="", encoding=None):
        self.reset()
        self.set_text(txt, encoding)

    def reset(self):
        """Clears the state to nothing."""
        self.__pos = position_marker()
        self.__saved_pos = []  # Stack of saved positions
        self.__bom = helpers.make_raw_bytes(
            []
        )  # contains copy of byte-order mark, if any
        self.__codec = None  # The CodecInfo
        self.__encoding = None  # The name of the codec's encoding
        self.__input_is_bytes = False
        self.__rawbuf = None
        self.__raw_bytes = None
        self.__cmax = 0
        self.num_ws_skipped = 0

    def save_position(self):
        self.__saved_pos.append(self.__pos.copy())
        return True

    def clear_saved_position(self):
        if self.__saved_pos:
            self.__saved_pos.pop()
            return True
        else:
            return False

    def restore_position(self):
        try:
            old_pos = self.__saved_pos.pop()  # Can raise IndexError
        except IndexError:
            raise IndexError("Attempt to restore buffer position that was never saved")
        else:
            self.__pos = old_pos
            return True

    def _find_codec(self, encoding):
        if encoding is None:
            self.__codec = None
            self.__encoding = None
        elif isinstance(encoding, codecs.CodecInfo):
            self.__codec = encoding
            self.__encoding = self.__codec.name
        else:
            self.__encoding = encoding
            self.__codec = helpers.lookup_codec(encoding)
            if not self.__codec:
                raise JSONDecodeError(
                    "no codec available for character encoding", encoding
                )
        return self.__codec

    def set_text(self, txt, encoding=None):
        """Changes the input text document and rewinds the position to
        the start of the new document.

        """
        import sys

        self.rewind()
        self.__codec = None
        self.__bom = None
        self.__rawbuf = ""
        self.__cmax = 0  # max number of chars in input
        try:
            decoded = helpers.unicode_decode(txt, encoding)
        except JSONError:
            raise
        except Exception as err:
            # Re-raise as a JSONDecodeError
            e2 = sys.exc_info()
            newerr = JSONDecodeError("a Unicode decoding error occurred")
            # Simulate Python 3's: "raise X from Y" exception chaining
            newerr.__cause__ = err
            newerr.__traceback__ = e2[2]
            raise newerr
        else:
            self.__codec = decoded.codec
            self.__bom = decoded.bom
            self.__rawbuf = decoded.string
            self.__cmax = len(self.__rawbuf)

    def __repr__(self):
        return "<%s at %r text %r>" % (
            self.__class__.__name__,
            self.__pos,
            self.text_context,
        )

    def rewind(self):
        """Resets the position back to the start of the input text."""
        self.__pos.rewind()

    @property
    def codec(self):
        """The codec object used to perform Unicode decoding, or None."""
        return self.__codec

    @property
    def bom(self):
        """The Unicode Byte-Order Mark (BOM), if any, that was present
        at the start of the input text.  The returned BOM is a string
        of the raw bytes, and is not Unicode-decoded.

        """
        return self.__bom

    @property
    def cpos(self):
        """The current character offset from the start of the document."""
        return self.__pos.char_position

    @property
    def position(self):
        """The current position (as a position_marker object).
        Returns a copy.

        """
        p = self.__pos.copy()
        p.text_after = self.text_context
        p.at_end = self.at_end
        return p

    @property
    def at_start(self):
        """Returns True if the position is currently at the start of
        the document, or False otherwise.

        """
        return self.__pos.at_start

    @property
    def at_end(self):
        """Returns True if the position is currently at the end of the
        document, of False otherwise.

        """
        c = self.peek()
        return not c

    def at_ws(self, allow_unicode_whitespace=True):
        """Returns True if the current position contains a white-space
        character.

        """
        c = self.peek()
        if not c:
            return False
        elif allow_unicode_whitespace:
            return helpers.char_is_unicode_ws(c)
        else:
            return helpers.char_is_json_ws(c)

    def at_eol(self, allow_unicode_eol=True):
        """Returns True if the current position contains an
        end-of-line control character.

        """
        c = self.peek()
        if not c:
            return True  # End of file is treated as end of line
        elif allow_unicode_eol:
            return helpers.char_is_unicode_eol(c)
        else:
            return helpers.char_is_json_eol(c)

    def peek(self, offset=0):
        """Returns the character at the current position, or at a
        given offset away from the current position.  If the position
        is beyond the limits of the document size, then an empty
        string '' is returned.

        """
        i = self.cpos + offset
        if i < 0 or i >= self.__cmax:
            return ""
        return self.__rawbuf[i]

    def peekstr(self, span=1, offset=0):
        """Returns one or more characters starting at the current
        position, or at a given offset away from the current position,
        and continuing for the given span length.  If the offset and
        span go outside the limit of the current document size, then
        the returned string may be shorter than the requested span
        length.

        """
        i = self.cpos + offset
        j = i + span
        if i < 0 or i >= self.__cmax:
            return ""
        return self.__rawbuf[i:j]

    @property
    def text_context(self, context_size=20):
        """A short human-readable textual excerpt of the document at
        the current position, in English.

        """
        context_size = max(context_size, 4)
        s = self.peekstr(context_size + 1)
        if not s:
            return ""
        if len(s) > context_size:
            s = s[: context_size - 3] + "..."
        return s

    def startswith(self, s):
        """Determines if the text at the current position starts with
        the given string.

        See also method: pop_if_startswith()

        """
        s2 = self.peekstr(len(s))
        return s == s2

    def skip(self, span=1):
        """Advances the current position by one (or the given number)
        of characters.  Will not advance beyond the end of the
        document.  Returns the number of characters skipped.

        """

        i = self.cpos
        self.__pos.advance(self.peekstr(span))
        return self.cpos - i

    def skipuntil(self, testfn):
        """Advances the current position until a given predicate test
        function succeeds, or the end of the document is reached.

        Returns the actual number of characters skipped.

        The provided test function should take a single unicode
        character and return a boolean value, such as:

            lambda c : c == '.'   # Skip to next period

        See also methods: skipwhile() and popuntil()

        """
        i = self.cpos
        while True:
            c = self.peek()
            if not c or testfn(c):
                break
            else:
                self.__pos.advance(c)
        return self.cpos - i

    def skipwhile(self, testfn):
        """Advances the current position until a given predicate test
        function fails, or the end of the document is reached.

        Returns the actual number of characters skipped.

        The provided test function should take a single unicode
        character and return a boolean value, such as:

            lambda c : c.isdigit()   # Skip all digits

        See also methods: skipuntil() and popwhile()

        """
        return self.skipuntil(lambda c: not testfn(c))

    def skip_to_next_line(self, allow_unicode_eol=True):
        """Advances the current position to the start of the next
        line.  Will not advance beyond the end of the file.  Note that
        the two-character sequence CR+LF is recognized as being just a
        single end-of-line marker.

        """
        ln = self.__pos.line
        while True:
            c = self.pop()
            if not c or self.__pos.line > ln:
                if c == "\r" and self.peek() == "\n":
                    self.skip()
                break

    def skipws(self, allow_unicode_whitespace=True):
        """Advances the current position past all whitespace, or until
        the end of the document is reached.

        """
        if allow_unicode_whitespace:
            n = self.skipwhile(helpers.char_is_unicode_ws)
        else:
            n = self.skipwhile(helpers.char_is_json_ws)
        self.num_ws_skipped += n
        return n

    def pop(self):
        """Returns the character at the current position and advances
        the position to the next character.  At the end of the
        document this function returns an empty string.

        """
        c = self.peek()
        if c:
            self.__pos.advance(c)
        return c

    def popstr(self, span=1, offset=0):
        """Returns a string of one or more characters starting at the
        current position, and advances the position to the following
        character after the span.  Will not go beyond the end of the
        document, so the returned string may be shorter than the
        requested span.

        """
        s = self.peekstr(span)
        if s:
            self.__pos.advance(s)
        return s

    def popif(self, testfn):
        """Just like the pop() function, but only returns the
        character if the given predicate test function succeeds.
        """
        c = self.peek()
        if c and testfn(c):
            self.__pos.advance(c)
            return c
        return ""

    def pop_while_in(self, chars):
        """Pops a sequence of characters at the current position
        as long as each of them is in the given set of characters.

        """
        if not isinstance(chars, (set, frozenset)):
            cset = set(chars)
        c = self.peek()
        if c and c in cset:
            s = self.popwhile(lambda c: c and c in cset)
            return s
        return None

    def pop_identifier(self, match=None):
        """Pops the sequence of characters at the current position
        that match the syntax for a JavaScript identifier.

        """
        c = self.peek()
        if c and helpers.char_is_identifier_leader(c):
            s = self.popwhile(helpers.char_is_identifier_tail)
            return s
        return None

    def pop_if_startswith(self, s):
        """Pops the sequence of characters if they match the given string.

        See also method: startswith()

        """
        s2 = self.peekstr(len(s))
        if s2 != s:
            return None
        self.__pos.advance(s2)
        return s2

    def popwhile(self, testfn, maxchars=None):
        """Pops all the characters starting at the current position as
        long as each character passes the given predicate function
        test.  If maxchars a numeric value instead of None then then
        no more than that number of characters will be popped
        regardless of the predicate test.

        See also methods: skipwhile() and popuntil()

        """
        s = []
        i = 0
        while maxchars is None or i < maxchars:
            c = self.popif(testfn)
            if not c:
                break
            s.append(c)
            i += 1
        return "".join(s)

    def popuntil(self, testfn, maxchars=None):
        """Just like popwhile() method except the predicate function
        should return True to stop the sequence rather than False.

        See also methods: skipuntil() and popwhile()

        """
        return self.popwhile(lambda c: not testfn(c), maxchars=maxchars)

    def __getitem__(self, index):
        """Returns the character at the given index relative to the current position.

        If the index goes beyond the end of the input, or prior to the
        start when negative, then '' is returned.

        If the index provided is a slice object, then that range of
        characters is returned as a string. Note that a stride value other
        than 1 is not supported in the slice.  To use a slice, do:

            s = my_stream[ 1:4 ]

        """
        if isinstance(index, slice):
            return self.peekstr(index.stop - index.start, index.start)
        else:
            return self.peek(index)


# ----------------------------------------------------------------------
# Exception classes.
# ----------------------------------------------------------------------


class JSONException(Exception):
    """Base class for all JSON-related exceptions."""

    pass


class JSONSkipHook(JSONException):
    """An exception to be raised by user-defined code within hook
    callbacks to indicate the callback does not want to handle the
    situation.

    """

    pass


class JSONStopProcessing(JSONException):
    """Can be raised by anyplace, including inside a hook function, to
    cause the entire encode or decode process to immediately stop
    with an error.

    """

    pass


class JSONAbort(JSONException):
    pass


class JSONError(JSONException):
    """Base class for all JSON-related errors.

    In addition to standard Python exceptions, these exceptions may
    also have additional properties:

        * severity - One of: 'fatal', 'error', 'warning', 'info'
        * position - An indication of the position in the input where the error occured.
        * outer_position - A secondary position (optional) that gives
          the location of the outer data item in which the error
          occured, such as the beginning of a string or an array.
        * context_description - A string that identifies the context
          in which the error occured.  Default is "Context".
    """

    severities = frozenset(["fatal", "error", "warning", "info"])

    def __init__(self, message, *args, **kwargs):
        self.severity = "error"
        self._position = None
        self.outer_position = None
        self.context_description = None
        for kw, val in list(kwargs.items()):
            if kw == "severity":
                if val not in self.severities:
                    raise TypeError(
                        "%s given invalid severity %r" % (self.__class__.__name__, val)
                    )
                self.severity = val
            elif kw == "position":
                self.position = val
            elif kw == "outer_position":
                self.outer_position = val
            elif kw == "context_description" or kw == "context":
                self.context_description = val
            else:
                raise TypeError(
                    "%s does not accept %r keyword argument"
                    % (self.__class__.__name__, kw)
                )
        super(JSONError, self).__init__(message, *args)
        self.message = message

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        if pos == 0:
            self._position = 0  # position_marker() # start of input
        else:
            self._position = pos

    def __repr__(self):
        s = "%s(%r" % (self.__class__.__name__, self.message)
        for a in self.args[1:]:
            s += ", %r" % (a,)
        if self.position:
            s += ", position=%r" % (self.position,)
        if self.outer_position:
            s += ", outer_position=%r" % (self.outer_position,)
        s += ", severity=%r)" % (self.severity,)
        return s

    def pretty_description(self, show_positions=True, filename=None):
        if filename:
            pfx = filename.rstrip().rstrip(":") + ":"
        else:
            pfx = ""
        # Print file position as numeric abbreviation
        err = pfx
        if self.position == 0:
            err += "0:0:"
        elif self.position:
            err += "%d:%d:" % (self.position.line, self.position.column)
        else:
            err += "    "
        # Print severity and main error message
        err += " %s: %s" % (self.severity.capitalize(), self.message)
        if len(self.args) > 1:
            err += ": "
            for anum, a in enumerate(self.args[1:]):
                if anum > 1:
                    err += ", "
                astr = repr(a)
                if len(astr) > 30:
                    astr = astr[:30] + "..."
                err += astr
        # Print out exception chain
        e2 = self
        while e2:
            if hasattr(e2, "__cause__") and isinstance(e2.__cause__, Exception):
                e2 = e2.__cause__
                e2desc = str(e2).strip()
                if not e2desc:
                    e2desc = repr(e2).strip()
                err += "\n   |  Cause: %s" % e2desc.strip().replace(
                    "\n", "\n   |         "
                )
            else:
                e2 = None
        # Show file position
        if show_positions and self.position is not None:
            if self.position == 0:
                err += "\n   |  At start of input"
            else:
                err += "\n   |  At %s" % (self.position.describe(show_text=False),)
                if self.position.text_after:
                    err += "\n   |    near text: %r" % (self.position.text_after,)
        # Show context
        if show_positions and self.outer_position:
            if self.context_description:
                cdesc = self.context_description.capitalize()
            else:
                cdesc = "Context"
            err += "\n   |  %s started at %s" % (
                cdesc,
                self.outer_position.describe(show_text=False),
            )
            if self.outer_position.text_after:
                err += "\n   |    with text: %r" % (self.outer_position.text_after,)
        return err


class JSONDecodeError(JSONError):
    """An exception class raised when a JSON decoding error (syntax error) occurs."""

    pass


class JSONDecodeHookError(JSONDecodeError):
    """An exception that occured within a decoder hook.

    The original exception is available in the 'hook_exception' attribute.
    """

    def __init__(self, hook_name, exc_info, encoded_obj, *args, **kwargs):
        self.hook_name = hook_name
        if not exc_info:
            exc_info = (None, None, None)
        exc_type, self.hook_exception, self.hook_traceback = exc_info
        self.object_type = type(encoded_obj)
        msg = "Hook %s raised %r while decoding type <%s>" % (
            hook_name,
            self.hook_exception.__class__.__name__,
            self.object_type.__name__,
        )
        if len(args) >= 1:
            msg += ": " + args[0]
            args = args[1:]
        super(JSONDecodeHookError, self).__init__(msg, *args, **kwargs)


class JSONEncodeError(JSONError):
    """An exception class raised when a python object can not be encoded as a JSON string."""

    pass


class JSONEncodeHookError(JSONEncodeError):
    """An exception that occured within an encoder hook.

    The original exception is available in the 'hook_exception' attribute.
    """

    def __init__(self, hook_name, exc_info, encoded_obj, *args, **kwargs):
        self.hook_name = hook_name
        if not exc_info:
            exc_info = (None, None, None)
        exc_type, self.hook_exception, self.hook_traceback = exc_info
        self.object_type = type(encoded_obj)
        msg = "Hook %s raised %r while encoding type <%s>" % (
            self.hook_name,
            self.hook_exception.__class__.__name__,
            self.object_type.__name__,
        )
        if len(args) >= 1:
            msg += ": " + args[0]
            args = args[1:]
        super(JSONEncodeHookError, self).__init__(msg, *args, **kwargs)


# ----------------------------------------------------------------------
# Encoder state object
# ----------------------------------------------------------------------


class encode_state(object):
    """An internal transient object used during JSON encoding to
    record the current construction state.

    """

    def __init__(self, jsopts=None, parent=None):
        self.chunks = []
        if not parent:
            self.parent = None
            self.nest_level = 0
            self.options = jsopts
            self.escape_unicode_test = False  # or a function f(unichar)=>True/False
        else:
            self.parent = parent
            self.nest_level = parent.nest_level + 1
            self.escape_unicode_test = parent.escape_unicode_test
            self.options = parent.options

    def make_substate(self):
        return encode_state(parent=self)

    def join_substate(self, other_state):
        self.chunks.extend(other_state.chunks)
        other_state.chunks = []

    def append(self, s):
        """Adds a string to the end of the current JSON document"""
        self.chunks.append(s)

    def combine(self):
        """Returns the accumulated string and resets the state to empty"""
        s = "".join(self.chunks)
        self.chunks = []
        return s

    def __eq__(self, other_state):
        return (
            self.nest_level == other_state.nest_level
            and self.chunks == other_state.chunks
        )

    def __lt__(self, other_state):
        if self.nest_level != other_state.nest_level:
            return self.nest_level < other_state.nest_level
        return self.chunks < other_state.chunks


# ----------------------------------------------------------------------
# Decoder statistics
# ----------------------------------------------------------------------


class decode_statistics(object):
    """An object that records various statistics about a decoded JSON document."""

    int8_max = 0x7F
    int8_min = -0x7F - 1
    int16_max = 0x7FFF
    int16_min = -0x7FFF - 1
    int32_max = 0x7FFFFFFF
    int32_min = -0x7FFFFFFF - 1
    int64_max = 0x7FFFFFFFFFFFFFFF
    int64_min = -0x7FFFFFFFFFFFFFFF - 1

    double_int_max = 2**53 - 1
    double_int_min = -(2**53 - 1)

    def __init__(self):
        # Nesting
        self.max_depth = 0
        self.max_items_in_array = 0
        self.max_items_in_object = 0
        # Integer stats
        self.num_ints = 0
        self.num_ints_8bit = 0
        self.num_ints_16bit = 0
        self.num_ints_32bit = 0
        self.num_ints_53bit = 0  # ints which will overflow IEEE doubles
        self.num_ints_64bit = 0
        self.num_ints_long = 0
        self.num_negative_zero_ints = 0
        # Floating-point stats
        self.num_negative_zero_floats = 0
        self.num_floats = 0
        self.num_floats_decimal = 0  # overflowed 'float'
        # String stats
        self.num_strings = 0
        self.max_string_length = 0
        self.total_string_length = 0
        self.min_codepoint = None
        self.max_codepoint = None
        # Other data type stats
        self.num_arrays = 0
        self.num_objects = 0
        self.num_bools = 0
        self.num_nulls = 0
        self.num_undefineds = 0
        self.num_nans = 0
        self.num_infinities = 0
        self.num_comments = 0
        self.num_identifiers = 0  # JavaScript identifiers
        self.num_excess_whitespace = 0

    @property
    def num_infinites(self):
        """Misspelled 'num_infinities' for backwards compatibility"""
        return self.num_infinities

    def pretty_description(self, prefix=""):
        import unicodedata

        lines = [
            "Number of integers:",
            "    8-bit:     %5d   (%d to %d)"
            % (self.num_ints_8bit, self.int8_min, self.int8_max),
            "   16-bit:     %5d   (%d to %d)"
            % (self.num_ints_16bit, self.int16_min, self.int16_max),
            "   32-bit:     %5d   (%d to %d)"
            % (self.num_ints_32bit, self.int32_min, self.int32_max),
            " > 53-bit:     %5d   (%d to %d - overflows JavaScript)"
            % (self.num_ints_53bit, self.double_int_min, self.double_int_max),
            "   64-bit:     %5d   (%d to %d)"
            % (self.num_ints_64bit, self.int64_min, self.int64_max),
            ' > 64 bit:     %5d   (not portable, may require a "Big Num" package)'
            % self.num_ints_long,
            "   total ints: %5d" % self.num_ints,
            "   Num -0:     %5d   (negative-zero integers are not portable)"
            % self.num_negative_zero_ints,
            "Number of floats:",
            "   doubles:    %5d" % self.num_floats,
            " > doubles:    %5d   (will overflow IEEE doubles)"
            % self.num_floats_decimal,
            "   total flts: %5d" % (self.num_floats + self.num_floats_decimal),
            "   Num -0.0:   %5d   (negative-zero floats are usually portable)"
            % self.num_negative_zero_floats,
            "Number of:",
            "   nulls:      %5d" % self.num_nulls,
            "   booleans:   %5d" % self.num_bools,
            "   arrays:     %5d" % self.num_arrays,
            "   objects:    %5d" % self.num_objects,
            "Strings:",
            "   number:         %5d strings" % self.num_strings,
            "   max length:     %5d characters" % self.max_string_length,
            "   total chars:    %5d across all strings" % self.total_string_length,
        ]

        if self.min_codepoint is not None:
            cp = "U+%04X" % self.min_codepoint
            try:
                charname = unicodedata.name(chr(self.min_codepoint))
            except ValueError:
                charname = "? UNKNOWN CHARACTER"
            lines.append("   min codepoint: %6s  (%s)" % (cp, charname))
        else:
            lines.append("   min codepoint: %6s" % ("n/a",))

        if self.max_codepoint is not None:
            cp = "U+%04X" % self.max_codepoint
            try:
                charname = unicodedata.name(chr(self.max_codepoint))
            except ValueError:
                charname = "? UNKNOWN CHARACTER"
            lines.append("   max codepoint: %6s  (%s)" % (cp, charname))
        else:
            lines.append("   max codepoint: %6s" % ("n/a",))

        lines.extend(
            [
                "Other JavaScript items:",
                "   NaN:         %5d" % self.num_nans,
                "   Infinite:    %5d" % self.num_infinities,
                "   undefined:   %5d" % self.num_undefineds,
                "   Comments:    %5d" % self.num_comments,
                "   Identifiers: %5d" % self.num_identifiers,
                "Max items in any array: %5d" % self.max_items_in_array,
                "Max keys in any object: %5d" % self.max_items_in_object,
                "Max nesting depth:      %5d" % self.max_depth,
            ]
        )
        if self.total_chars == 0:
            lines.append("Unnecessary whitespace:     0 of 0 characters")
        else:
            lines.append(
                "Unnecessary whitespace: %5d of %d characters (%.2f%%)"
                % (
                    self.num_excess_whitespace,
                    self.total_chars,
                    self.num_excess_whitespace * 100.0 / self.total_chars,
                )
            )
        if prefix:
            return "\n".join([prefix + s for s in lines]) + "\n"
        else:
            return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------
# Decoder state object
# ----------------------------------------------------------------------


class decode_state(object):
    """An internal transient object used during JSON decoding to
    record the current parsing state and error messages.

    """

    def __init__(self, options=None):
        self.reset()
        self.options = options

    def reset(self):
        """Clears all errors, statistics, and input text."""
        self.buf = None
        self.errors = []
        self.obj = None
        self.cur_depth = 0  # how deep in nested structures are we?
        self.stats = decode_statistics()
        self._have_warned_nonbmp = False
        self._have_warned_long_string = False
        self._have_warned_max_depth = False

    @property
    def should_stop(self):
        if self.has_fatal:
            return True
        return False

    @property
    def has_errors(self):
        """Have any errors been seen already?"""
        return (
            len([err for err in self.errors if err.severity in ("fatal", "error")]) > 0
        )

    @property
    def has_fatal(self):
        """Have any errors been seen already?"""
        return len([err for err in self.errors if err.severity in ("fatal",)]) > 0

    def set_input(self, txt, encoding=None):
        """Initialize the state by setting the input document text."""
        import sys

        self.reset()
        try:
            self.buf = buffered_stream(txt, encoding=encoding)
        except JSONError as err:
            err.position = 0  # set position to start of file
            err.severity = "fatal"
            self.push_exception(err)
        except Exception as err:
            # Re-raise as JSONDecodeError
            e2 = sys.exc_info()  # noqa: F841
            newerr = JSONDecodeError(  # noqa: F841
                "Error while reading input", position=0, severity="fatal"
            )  # noqa: F841
            self.push_exception(err)
            self.buf = None
        else:
            if self.buf.bom:
                self.push_cond(
                    self.options.bom,
                    "JSON document was prefixed by a BOM (Byte Order Mark)",
                    self.buf.bom,
                )
        if not self.buf:
            self.push_fatal("Aborting, can not read JSON document.", position=0)

    def push_exception(self, exc):
        """Add an already-built exception to the error list."""
        self.errors.append(exc)

    def push_fatal(self, message, *args, **kwargs):
        """Create a fatal error."""
        kwargs["severity"] = "fatal"
        self.__push_err(message, *args, **kwargs)

    def push_error(self, message, *args, **kwargs):
        """Create an error."""
        kwargs["severity"] = "error"
        self.__push_err(message, *args, **kwargs)

    def push_warning(self, message, *args, **kwargs):
        """Create a warning."""
        kwargs["severity"] = "warning"
        self.__push_err(message, *args, **kwargs)

    def push_info(self, message, *args, **kwargs):
        """Create a informational message."""
        kwargs["severity"] = "info"
        self.__push_err(message, *args, **kwargs)

    def push_cond(self, behavior_value, message, *args, **kwargs):
        """Creates an conditional error or warning message.

        The behavior value (from json_options) controls whether
        a message will be pushed and whether it is an error
        or warning message.

        """
        if behavior_value == ALLOW:
            return
        elif behavior_value == WARN:
            kwargs["severity"] = "warning"
        else:
            kwargs["severity"] = "error"
        self.__push_err(message, *args, **kwargs)

    def __push_err(self, message, *args, **kwargs):
        """Stores an error in the error list."""
        position = None
        outer_position = None
        severity = "error"
        context_description = None
        for kw, val in list(kwargs.items()):
            if kw == "position":
                position = val
            elif kw == "outer_position":
                outer_position = val
            elif kw == "severity":
                severity = val
            elif kw == "context_description" or kw == "context":
                context_description = val
            else:
                raise TypeError("Unknown keyword argument", kw)
        if position is None and self.buf:
            position = self.buf.position  # Current position
        err = JSONDecodeError(
            message,
            position=position,
            outer_position=outer_position,
            context_description=context_description,
            severity=severity,
            *args,
        )
        self.push_exception(err)

    def update_depth_stats(self, **kwargs):
        st = self.stats
        st.max_depth = max(st.max_depth, self.cur_depth)
        if (
            not self._have_warned_max_depth
            and self.cur_depth > self.options.warn_max_depth
        ):
            self._have_warned_max_depth = True
            self.push_cond(
                self.options.non_portable,
                "Arrays or objects nested deeper than %d levels may not be portable"
                % self.options.warn_max_depth,
            )

    def update_string_stats(self, s, **kwargs):
        st = self.stats
        st.num_strings += 1
        st.max_string_length = max(st.max_string_length, len(s))
        st.total_string_length += len(s)
        if (
            self.options.warn_string_length
            and len(s) > self.options.warn_string_length
            and not self._have_warned_long_string
        ):
            self._have_warned_long_string = True
            self.push_cond(
                self.options.non_portable,
                "Strings longer than %d may not be portable"
                % self.options.warn_string_length,
                **kwargs,
            )
        if len(s) > 0:
            mincp = ord(min(s))
            maxcp = ord(max(s))
            if st.min_codepoint is None:
                st.min_codepoint = mincp
                st.max_codepoint = maxcp
            else:
                st.min_codepoint = min(st.min_codepoint, mincp)
                st.max_codepoint = max(st.max_codepoint, maxcp)
            if maxcp > 0xFFFF and not self._have_warned_nonbmp:
                self._have_warned_nonbmp = True
                self.push_cond(
                    self.options.non_portable,
                    "Strings containing non-BMP characters (U+%04X) may not be portable"
                    % maxcp,
                    **kwargs,
                )

    def update_negzero_int_stats(self, **kwargs):
        st = self.stats
        st.num_negative_zero_ints += 1
        if st.num_negative_zero_ints == 1:  # Only warn once
            self.push_cond(
                self.options.non_portable,
                "Negative zero (-0) integers are usually not portable",
                **kwargs,
            )

    def update_negzero_float_stats(self, **kwargs):
        st = self.stats
        st.num_negative_zero_floats += 1
        if st.num_negative_zero_floats == 1:  # Only warn once
            self.push_cond(
                self.options.non_portable,
                "Negative zero (-0.0) numbers may not be portable",
                **kwargs,
            )

    def update_float_stats(self, float_value, **kwargs):
        st = self.stats
        if "sign" in kwargs:
            del kwargs["sign"]

        if helpers.is_negzero(float_value):
            self.update_negzero_float_stats(**kwargs)

        if helpers.is_infinite(float_value):
            st.num_infinities += 1

        if isinstance(float_value, decimal.Decimal):
            st.num_floats_decimal += 1
            if st.num_floats_decimal == 1:  # Only warn once
                self.push_cond(
                    self.options.non_portable,
                    'Floats larger or more precise than an IEEE "double" may not be portable',
                    **kwargs,
                )
        elif isinstance(float_value, float):
            st.num_floats += 1

    def update_integer_stats(self, int_value, **kwargs):
        sign = kwargs.get("sign", 1)
        if "sign" in kwargs:
            del kwargs["sign"]

        if int_value == 0 and sign < 0:
            self.update_negzero_int_stats(**kwargs)

        if sign < 0:
            int_value = -int_value

        st = self.stats
        st.num_ints += 1
        if st.int8_min <= int_value <= st.int8_max:
            st.num_ints_8bit += 1
        elif st.int16_min <= int_value <= st.int16_max:
            st.num_ints_16bit += 1
        elif st.int32_min <= int_value <= st.int32_max:
            st.num_ints_32bit += 1
        elif st.int64_min <= int_value <= st.int64_max:
            st.num_ints_64bit += 1
        else:
            st.num_ints_long += 1

        if int_value < st.double_int_min or st.double_int_max < int_value:
            st.num_ints_53bit += 1
            if st.num_ints_53bit == 1:  # Only warn once
                self.push_cond(
                    self.options.non_portable,
                    "Integers larger than 53-bits are not portable",
                    **kwargs,
                )


# ----------------------------------------------------------------------
# JSON strictness options
# ----------------------------------------------------------------------

STRICTNESS_STRICT = "strict"
STRICTNESS_WARN = "warn"
STRICTNESS_TOLERANT = "tolerant"

ALLOW = "allow"
WARN = "warn"
FORBID = "forbid"

# For float_type option
NUMBER_AUTO = "auto"
NUMBER_FLOAT = "float"
NUMBER_DECIMAL = "decimal"

# For json_int class
NUMBER_FORMAT_DECIMAL = "decimal"
NUMBER_FORMAT_HEX = "hex"
NUMBER_FORMAT_LEGACYOCTAL = "legacyoctal"
NUMBER_FORMAT_OCTAL = "octal"
NUMBER_FORMAT_BINARY = "binary"


class _behaviors_metaclass(type):
    """Meta class used to establish a set of "behavior" options.

    Classes that use this meta class must defined a class-level
    variable called '_behaviors' that is a list of tuples, each of
    which describes one behavior and is like: (behavior_name,
    documentation).  Also define a second class-level variable called
    '_behavior_values' which is a list of the permitted values for
    each behavior, each being strings.

    For each behavior (e.g., pretty), and for each value (e.g.,
    yes) the following methods/properties will be created:

      * pretty - value of 'pretty' behavior (read-write)
      * ispretty_yes - returns True if 'pretty' is 'yes'

    For each value (e.g., pink) the following methods/properties
    will be created:

      * all_behaviors - set of all behaviors (read-only)
      * pink_behaviors - set of behaviors with value of 'pink' (read-only)
      * set_all('pink')
      * set_all_pink()    - set all behaviors to value of 'pink'

    """

    def __new__(cls, clsname, bases, attrs):
        values = attrs.get("_behavior_values")
        attrs["values"] = property(
            lambda self: set(self._behavior_values),
            doc="Set of possible behavior values",
        )
        behaviors = attrs.get("_behaviors")

        def get_behavior(self, name):
            """Returns the value for a given behavior"""
            try:
                return getattr(self, "_behavior_" + name)
            except AttributeError:
                raise ValueError("Unknown behavior", name)

        attrs["get_behavior"] = get_behavior

        def set_behavior(self, name, value):
            """Changes the value for a given behavior"""
            if value not in self._behavior_values:
                raise ValueError("Unknown value for behavior", value)
            varname = "_behavior_" + name
            if hasattr(self, varname):
                setattr(self, varname, value)
            else:
                raise ValueError("Unknown behavior", name)

        attrs["set_behavior"] = set_behavior

        def describe_behavior(self, name):
            """Returns documentation about a given behavior."""
            for n, doc in self._behaviors:
                if n == name:
                    return doc
            else:
                raise AttributeError("No such behavior", name)

        attrs["describe_behavior"] = describe_behavior

        for name, doc in behaviors:
            attrs["_behavior_" + name] = True
            for v in values:
                vs = v + "_" + name  # noqa: F841

                def getx(self, name=name, forval=v):
                    return self.get_behavior(name) == forval

                attrs["is_" + v + "_" + name] = property(
                    getx, doc=v.capitalize() + " " + doc
                )
                # method value_name()
                fnset = lambda self, _name=name, _value=v: self.set_behavior(  # noqa: E731
                    _name, _value
                )  # noqa: E731
                fnset.__name__ = v + "_" + name
                fnset.__doc__ = "Set behavior " + name + " to " + v + "."
                attrs[fnset.__name__] = fnset

            def get_value_for_behavior(self, name=name):
                return self.get_behavior(name)

            def set_value_for_behavior(self, value, name=name):
                self.set_behavior(name, value)

            attrs[name] = property(
                get_value_for_behavior, set_value_for_behavior, doc=doc
            )

        @property
        def all_behaviors(self):
            """Returns the names of all known behaviors."""
            return set([t[0] for t in self._behaviors])

        attrs["all_behaviors"] = all_behaviors

        def set_all(self, value):
            """Changes all behaviors to have the given value."""
            if value not in self._behavior_values:
                raise ValueError("Unknown behavior", value)
            for name in self.all_behaviors:
                setattr(self, "_behavior_" + name, value)

        attrs["set_all"] = set_all

        def is_all(self, value):
            """Determines if all the behaviors have the given value."""
            if value not in self._behavior_values:
                raise ValueError("Unknown behavior", value)
            for name in self.all_behaviors:
                if getattr(self, "_behavior_" + name) != value:
                    return False
            return True

        attrs["is_all"] = is_all

        for v in values:
            # property value_behaviors
            def getbehaviorsfor(self, value=v):
                return set(
                    [
                        name
                        for name in self.all_behaviors
                        if getattr(self, name) == value
                    ]
                )

            attrs[v + "_behaviors"] = property(
                getbehaviorsfor,
                doc="Return the set of behaviors with the value " + v + ".",
            )
            # method set_all_value()
            setfn = lambda self, _value=v: set_all(self, _value)  # noqa: E731
            setfn.__name__ = "set_all_" + v
            setfn.__doc__ = "Set all behaviors to value " + v + "."
            attrs[setfn.__name__] = setfn
            # property is_all_value
            attrs["is_all_" + v] = property(
                lambda self, v=v: is_all(self, v),
                doc="Determines if all the behaviors have the value " + v + ".",
            )

        def behaviors_eq(self, other):
            """Determines if two options objects are equivalent."""
            if self.all_behaviors != other.all_behaviors:
                return False
            return self.allowed_behaviors == other.allowed_behaviors

        attrs["__eq__"] = behaviors_eq

        return super(_behaviors_metaclass, cls).__new__(cls, clsname, bases, attrs)


SORT_NONE = "none"
SORT_PRESERVE = "preserve"
SORT_ALPHA = "alpha"
SORT_ALPHA_CI = "alpha_ci"
SORT_SMART = "smart"

sorting_methods = {
    SORT_NONE: "Do not sort, resulting order may be random",
    SORT_PRESERVE: "Preserve original order when reformatting",
    SORT_ALPHA: "Sort strictly alphabetically",
    SORT_ALPHA_CI: "Sort alphabetically case-insensitive",
    SORT_SMART: "Sort alphabetically and numerically (DEFAULT)",
}
sorting_method_aliases = {"ci": SORT_ALPHA_CI}


def smart_sort_transform(key):
    numfmt = "%012d"
    digits = "0123456789"
    zero = ord("0")
    if not key:
        key = ""
    elif isinstance(key, int):
        key = numfmt % key
    elif isinstance(key, str):
        keylen = len(key)
        words = []
        i = 0
        while i < keylen:
            if key[i] in digits:
                num = 0
                while i < keylen and key[i] in digits:
                    num *= 10
                    num += ord(key[i]) - zero
                    i += 1
                words.append(numfmt % num)
            else:
                words.append(key[i].upper())
                i += 1
        key = "".join(words)
    else:
        key = str(key)
    return key


# Find Enum type (introduced in Python 3.4)
try:
    from enum import Enum as _enum
except ImportError:
    _enum = None
# Find OrderedDict type
try:
    from collections import OrderedDict as _OrderedDict
except ImportError:
    _OrderedDict = None


class json_options(object, metaclass=_behaviors_metaclass):
    """Options to determine how strict the decoder or encoder should be."""

    _behavior_values = (ALLOW, WARN, FORBID)
    _behaviors = (
        (
            "all_numeric_signs",
            "Numbers may be prefixed by any '+' and '-', e.g., +4, -+-+77",
        ),
        (
            "any_type_at_start",
            "A JSON document may start with any type, not just arrays or objects",
        ),
        ("comments", "JavaScript comments, both /*...*/ and //... styles"),
        (
            "control_char_in_string",
            "Strings may contain raw control characters without \\u-escaping",
        ),
        ("hex_numbers", "Hexadecimal numbers, e.g., 0x1f"),
        ("binary_numbers", "Binary numbers, e.g., 0b1001"),
        (
            "octal_numbers",
            "New-style octal numbers, e.g., 0o731  (see leading-zeros for legacy octals)",
        ),
        (
            "initial_decimal_point",
            "Floating-point numbers may start with a decimal point (no units digit)",
        ),
        (
            "extended_unicode_escapes",
            "Extended Unicode escape sequence \\u{..} for non-BMP characters",
        ),
        (
            "js_string_escapes",
            "All JavaScript character \\-escape sequences may be in strings",
        ),
        (
            "leading_zeros",
            "Numbers may have extra leading zeros (see --leading-zero-radix option)",
        ),
        ("non_numbers", "Non-numbers may be used, such as NaN or Infinity"),
        (
            "nonescape_characters",
            "Unknown character \\-escape sequences stand for that character (\\Q -> 'Q')",
        ),
        (
            "identifier_keys",
            "JavaScript identifiers are converted to strings when used as object keys",
        ),
        (
            "nonstring_keys",
            "Value types other than strings (or identifiers) may be used as object keys",
        ),
        (
            "omitted_array_elements",
            "Arrays may have omitted/elided elements, e.g., [1,,3] == [1,undefined,3]",
        ),
        (
            "single_quoted_strings",
            "Strings may be delimited with both double (\") and single (') quotation marks",
        ),
        ("trailing_comma", "A final comma may end the list of array or object members"),
        (
            "trailing_decimal_point",
            "Floating-point number may end with a decimal point and no following fractional digits",
        ),
        ("undefined_values", "The JavaScript 'undefined' value may be used"),
        (
            "format_control_chars",
            'Unicode "format control characters" may appear in the input',
        ),
        (
            "unicode_whitespace",
            "Treat any Unicode whitespace character as valid whitespace",
        ),
        # Never legal
        ("leading_zeros", "Numbers may have leading zeros"),
        # Normally warnings
        ("duplicate_keys", "Objects may have repeated keys"),
        (
            "zero_byte",
            "Strings may contain U+0000, which may not be safe for C-based programs",
        ),
        ("bom", "A JSON document may start with a Unicode BOM (Byte Order Mark)"),
        (
            "non_portable",
            "Anything technically valid but likely to cause data portablibity issues",
        ),
    )  # end behavior list

    def reset_to_defaults(self):
        # Plain attrs (other than above behaviors) are simply copied
        # by value, either during initialization (via keyword
        # arguments) or via the copy() method.
        self._plain_attrs = [
            "leading_zero_radix",
            "encode_namedtuple_as_object",
            "encode_enum_as",
            "encode_compactly",
            "escape_unicode",
            "always_escape_chars",
            "warn_string_length",
            "warn_max_depth",
            "int_as_float",
            "decimal_context",
            "float_type",
            "keep_format",
            "date_format",
            "datetime_format",
            "time_format",
            "timedelta_format",
            "sort_keys",
            "indent_amount",
            "indent_tab_width",
            "indent_limit",
            "max_items_per_line",
            "py2str_encoding",
        ]

        self.strictness = STRICTNESS_WARN
        self._leading_zero_radix = 8  # via property: leading_zero_radix
        self._sort_keys = SORT_SMART  # via property: sort_keys

        self.int_as_float = False
        self.float_type = NUMBER_AUTO
        self.decimal_context = decimal.DefaultContext if decimal else None
        self.keep_format = False  # keep track of when numbers are hex, octal, etc.

        self.encode_namedtuple_as_object = True
        self._encode_enum_as = "name"  # via property
        self.encode_compactly = True
        self.escape_unicode = False
        self.always_escape_chars = (
            None  # None, or a set of Unicode characters to always escape
        )

        self.warn_string_length = 0xFFFD  # with 16-bit length prefix
        self.warn_max_depth = 64

        self.date_format = "iso"  # or strftime format
        self.datetime_format = "iso"  # or strftime format
        self.time_format = "iso"  # or strftime format
        self.timedelta_format = "iso"  # or 'hms'

        self.sort_keys = SORT_ALPHA
        self.indent_amount = 2
        self.indent_tab_width = 0  # 0, or number of equivalent spaces
        self.indent_limit = None
        self.max_items_per_line = 1  # When encoding how many items per array/object
        # before breaking into multiple lines
        # For interpreting Python 2 'str' types:
        if _py_major == 2:
            self.py2str_encoding = "ascii"
        else:
            self.py2str_encoding = None

    def __init__(self, **kwargs):
        """Set JSON encoding and decoding options.

        If 'strict' is set to True, then only strictly-conforming JSON
        output will be produced.  Note that this means that some types
        of values may not be convertable and will result in a
        JSONEncodeError exception.

        If 'compactly' is set to True, then the resulting string will
        have all extraneous white space removed; if False then the
        string will be "pretty printed" with whitespace and indentation
        added to make it more readable.

        If 'escape_unicode' is set to True, then all non-ASCII characters
        will be represented as a unicode escape sequence; if False then
        the actual real unicode character will be inserted if possible.

        The 'escape_unicode' can also be a function, which when called
        with a single argument of a unicode character will return True
        if the character should be escaped or False if it should not.

        """
        self.reset_to_defaults()

        if "strict" in kwargs:
            # Do this keyword first, so other keywords may override specific behaviors
            self.strictness = kwargs["strict"]

        for kw, val in list(kwargs.items()):
            if kw == "compactly":  # alias for 'encode_compactly'
                self.encode_compactly = val
            elif kw == "strict":
                pass  # Already handled
            elif kw == "warnings":
                if val:
                    self.suppress_warnings()
            elif kw == "html_safe" or kw == "xml_safe":
                if bool(val):
                    if self.always_escape_chars is None:
                        self.always_escape_chars = set("<>/&")
                    else:
                        self.always_escape_chars.update(set("<>/&"))
            elif kw == "always_escape":
                if val:
                    if self.always_escape_chars is None:
                        self.always_escape_chars = set(val)
                    else:
                        self.always_escape_chars.update(set(val))
            elif kw == "int_as_float":
                self.int_as_float = bool(val)
            elif kw == "keep_format":
                self.keep_format = bool(val)
            elif kw == "float_type":
                if val in (NUMBER_AUTO, NUMBER_FLOAT, NUMBER_DECIMAL):
                    self.float_type = val
                else:
                    raise ValueError(
                        "Unknown option %r for argument %r to initialize %s"
                        % (val, kw, self.__class__.__name__)
                    )
            elif kw == "decimal" or kw == "decimal_context":
                if decimal:
                    if not val or val == "default":
                        self.decimal_context = decimal.DefaultContext
                    elif val == "basic":
                        self.decimal_context = decimal.BasicContext
                    elif val == "extended":
                        self.decimal_context = decimal.ExtendedContext
                    elif isinstance(val, decimal.Context):
                        self.decimal_context = val
                    elif isinstance(val, int) or val[0].isdigit:
                        prec = int(val)
                        self.decimal_context = decimal.Context(prec=prec)
                    else:
                        raise ValueError(
                            "Option for %r should be a decimal.Context, a number of significant digits, or one of 'default','basic', or 'extended'."
                            % (kw,)
                        )
            elif kw in ("allow", "warn", "forbid", "prevent", "deny"):
                action = {
                    "allow": ALLOW,
                    "warn": WARN,
                    "forbid": FORBID,
                    "prevent": FORBID,
                    "deny": FORBID,
                }[kw]
                if isinstance(val, str):
                    val = [b.replace("-", "_") for b in val.replace(",", " ").split()]
                for behavior in val:
                    self.set_behavior(behavior, action)
            elif (
                kw.startswith("allow_")
                or kw.startswith("forbid_")
                or kw.startswith("prevent_")
                or kw.startswith("deny_")
                or kw.startswith("warn_")
            ):
                action, behavior = kw.split("_", 1)
                if action == "allow":
                    if val:
                        self.set_behavior(behavior, ALLOW)
                    else:
                        self.set_behavior(behavior, FORBID)
                elif action in ("forbid", "prevent", "deny"):
                    if val:
                        self.set_behavior(behavior, FORBID)
                    else:
                        self.set_behavior(behavior, ALLOW)
                elif action == "warn":
                    if val:
                        self.set_behavior(behavior, WARN)
                    else:
                        self.set_behavior(behavior, ALLOW)
            elif kw in self._plain_attrs:
                setattr(self, kw, val)
            else:
                raise ValueError(
                    "Unknown keyword argument %r to initialize %s"
                    % (kw, self.__class__.__name__)
                )

    def copy(self):
        other = self.__class__()
        other.copy_from(self)
        return other

    def copy_from(self, other):
        if self is other:
            return  # Myself!

        self.strictness = other.strictness  # sets behaviors in bulk

        for name in self.all_behaviors:
            self.set_behavior(name, other.get_behavior(name))

        for name in self._plain_attrs:
            val = getattr(other, name)
            if isinstance(val, set):
                val = val.copy()
            elif decimal and isinstance(val, decimal.Decimal):
                val = val.copy()

            setattr(self, name, val)

    def spaces_to_next_indent_level(self, min_spaces=1, subtract=0):
        n = self.indent_amount - subtract
        if n < 0:
            n = 0
        n = max(min_spaces, n)
        return " " * n

    def indentation_for_level(self, level=0):
        """Returns a whitespace string used for indenting."""
        if self.indent_limit is not None and level > self.indent_limit:
            n = self.indent_limit
        else:
            n = level
        n *= self.indent_amount
        if self.indent_tab_width:
            tw, sw = divmod(n, self.indent_tab_width)
            return "\t" * tw + " " * sw
        else:
            return " " * n

    def set_indent(self, num_spaces, tab_width=0, limit=None):
        """Changes the indentation properties when outputting JSON in non-compact mode.

        'num_spaces' is the number of spaces to insert for each level
        of indentation, which defaults to 2.

        'tab_width', if not 0, is the number of spaces which is equivalent
        to one tab character.  Tabs will be output where possible rather
        than runs of spaces.

        'limit', if not None, is the maximum indentation level after
        which no further indentation will be output.

        """
        n = int(num_spaces)
        if n < 0:
            raise ValueError("indentation amount can not be negative", n)
        self.indent_amount = n
        self.indent_tab_width = tab_width
        self.indent_limit = limit

    @property
    def sort_keys(self):
        """The method used to sort dictionary keys when encoding JSON"""
        return self._sort_keys

    @sort_keys.setter
    def sort_keys(self, method):
        if not method:
            self._sort_keys = SORT_NONE
        elif callable(method):
            self._sort_keys = method
        elif method in sorting_methods:
            self._sort_keys = method
        elif method in sorting_method_aliases:  # alias
            self._sort_keys = sorting_method_aliases[method]
        elif method is True:
            self._sort_keys = SORT_ALPHA
        else:
            raise ValueError("Not a valid sorting method: %r" % method)

    @property
    def encode_enum_as(self):
        """The strategy for encoding Python Enum values."""
        return self._encode_enum_as

    @encode_enum_as.setter
    def encode_enum_as(self, val):
        if val not in ("name", "qname", "value"):
            raise ValueError("encode_enum_as must be one of 'name','qname', or 'value'")
        self._encode_enum_as = val

    @property
    def zero_float(self):
        """The numeric value 0.0, either a float or a decimal."""
        if decimal and self.float_type == NUMBER_DECIMAL:
            return self.decimal_context.create_decimal("0.0")
        else:
            return 0.0

    @property
    def negzero_float(self):
        """The numeric value -0.0, either a float or a decimal."""
        if decimal and self.float_type == NUMBER_DECIMAL:
            return self.decimal_context.create_decimal("-0.0")
        else:
            return -0.0

    @property
    def nan(self):
        """The numeric value NaN, either a float or a decimal."""
        if decimal and self.float_type == NUMBER_DECIMAL:
            return self.decimal_context.create_decimal("NaN")
        else:
            return nan

    @property
    def inf(self):
        """The numeric value Infinity, either a float or a decimal."""
        if decimal and self.float_type == NUMBER_DECIMAL:
            return self.decimal_context.create_decimal("Infinity")
        else:
            return inf

    @property
    def neginf(self):
        """The numeric value -Infinity, either a float or a decimal."""
        if decimal and self.float_type == NUMBER_DECIMAL:
            return self.decimal_context.create_decimal("-Infinity")
        else:
            return neginf

    def make_int(self, s, sign=None, number_format=NUMBER_FORMAT_DECIMAL):
        """Makes an integer value according to the current options.

        First argument should be a string representation of the number,
        or an integer.

        Returns a number value, which could be an int, float, or decimal.

        """
        if isinstance(sign, int):
            if sign < 0:
                sign = "-"
            else:
                sign = "+"
        if isinstance(s, str):
            if s.startswith("-") or s.startswith("+"):
                sign = s[0]
                s = s[1:]

        if self.int_as_float:
            # Making a float/decimal
            if isinstance(s, int):
                if self.float_type == NUMBER_DECIMAL:
                    n = self.decimal_context.create_decimal(s)
                    if sign == "-":
                        n = n.copy_negate()
                elif s == 0 and sign == "-":
                    n = self.negzero_float
                elif -999999999999999 <= s <= 999999999999999:
                    n = float(s)
                    if sign == "-":
                        n *= -1
                else:
                    n = float(s)
                    if (n == inf or int(n) != s) and self.float_type != NUMBER_FLOAT:
                        n = self.decimal_context.create_decimal(s)
                        if sign == "-":
                            n = n.copy_negate()
                    elif sign == "-":
                        n *= -1
            else:  # not already an int
                n = self.make_float(s, sign)
                n2 = self.make_float(s[:-1] + ("9" if s[-1] <= "5" else "0"), sign)
                if (n == inf or n == n2) and self.float_type != NUMBER_FLOAT:
                    n = self.make_decimal(s, sign)
        elif isinstance(s, int):
            # already an integer
            n = s
            if sign == "-":
                if n == 0:
                    n = self.negzero_float
                else:
                    n *= -1
        else:
            # Making an actual integer
            try:
                n = int(s)
            except ValueError:
                n = self.nan
            else:
                if sign == "-":
                    if n == 0:
                        n = self.negzero_float
                    else:
                        n *= -1
        if isinstance(n, int) and self.keep_format:
            n = json_int(n, number_format=number_format)
        return n

    def make_decimal(self, s, sign="+"):
        """Converts a string into a decimal or float value."""
        if not decimal or self.float_type == NUMBER_FLOAT:
            return self.make_float(s, sign)

        if s.startswith("-") or s.startswith("+"):
            sign = s[0]
            s = s[1:]
        elif isinstance(sign, int):
            if sign < 0:
                sign = "-"
            else:
                sign = "+"

        try:
            f = self.decimal_context.create_decimal(s)
        except decimal.InvalidOperation:
            f = self.decimal_context.create_decimal("NaN")
        except decimal.Overflow:
            if sign == "-":
                f = self.decimal_context.create_decimal("-Infinity")
            else:
                f = self.decimal_context.create_decimal("Infinity")
        else:
            if sign == "-":
                f = f.copy_negate()
        return f

    def make_float(self, s, sign="+"):
        """Converts a string into a float or decimal value."""
        if decimal and self.float_type == NUMBER_DECIMAL:
            return self.make_decimal(s, sign)

        if s.startswith("-") or s.startswith("+"):
            sign = s[0]
            s = s[1:]
        elif isinstance(sign, int):
            if sign < 0:
                sign = "-"
            else:
                sign = "+"

        try:
            f = float(s)
        except ValueError:
            f = nan
        else:
            if sign == "-":
                f *= -1
        return f

    @property
    def leading_zero_radix(self):
        """The radix to be used for numbers with leading zeros.  8 or 10"""
        return self._leading_zero_radix

    @leading_zero_radix.setter
    def leading_zero_radix(self, radix):
        if isinstance(radix, str):
            try:
                radix = int(radix)
            except ValueError:
                radix = radix.lower()
                if radix == "octal" or radix == "oct" or radix == "8":
                    radix = 8
                elif radix == "decimal" or radix == "dec":
                    radix = 10
        if radix not in (8, 10):
            raise ValueError("Radix must either be 8 (octal) or 10 (decimal)")
        self._leading_zero_radix = radix

    @property
    def leading_zero_radix_as_word(self):
        return {8: "octal", 10: "decimal"}[self._leading_zero_radix]

    def suppress_warnings(self):
        for name in self.warn_behaviors:
            self.set_behavior(name, "allow")

    @property
    def allow_or_warn_behaviors(self):
        """Returns the set of all behaviors that are not forbidden (i.e., are allowed or warned)."""
        return self.allow_behaviors.union(self.warn_behaviors)

    @property
    def strictness(self):
        return self._strictness

    @strictness.setter
    def strictness(self, strict):
        """Changes whether the options should be re-configured for strict JSON conformance."""
        if strict == STRICTNESS_WARN:
            self._strictness = STRICTNESS_WARN
            self.set_all_warn()
        elif strict == STRICTNESS_STRICT or strict is True:
            self._strictness = STRICTNESS_STRICT
            self.keep_format = False
            self.set_all_forbid()
            self.warn_duplicate_keys()
            self.warn_zero_byte()
            self.warn_bom()
            self.warn_non_portable()
        elif strict == STRICTNESS_TOLERANT or strict is False:
            self._strictness = STRICTNESS_TOLERANT
            self.set_all_allow()
            self.warn_duplicate_keys()
            self.warn_zero_byte()
            self.warn_leading_zeros()
            self.leading_zero_radix = 8
            self.warn_bom()
            self.allow_non_portable()
        else:
            raise ValueError("Unknown strictness options %r" % strict)
        self.allow_any_type_at_start()


# ----------------------------------------------------------------------
# The main JSON encoder/decoder class.
# ----------------------------------------------------------------------


class JSON(object):
    """An encoder/decoder for JSON data streams.

    Usually you will call the encode() or decode() methods.  The other
    methods are for lower-level processing.

    Whether the JSON parser runs in strict mode (which enforces exact
    compliance with the JSON spec) or the more forgiving non-string mode
    can be affected by setting the 'strict' argument in the object's
    initialization; or by assigning True or False to the 'strict'
    property of the object.

    You can also adjust a finer-grained control over strictness by
    allowing or forbidding specific behaviors.  You can get a list of
    all the available behaviors by accessing the 'behaviors' property.
    Likewise the 'allowed_behaviors' and 'forbidden_behaviors' list which
    behaviors will be allowed and which will not.  Call the allow()
    or forbid() methods to adjust these.

    """

    _string_quotes = "\"'"

    _escapes_json = {  # character escapes in JSON
        '"': '"',
        "/": "/",
        "\\": "\\",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
    }

    _escapes_js = {  # character escapes in Javascript
        '"': '"',
        "'": "'",
        "\\": "\\",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
        "0": "\x00",
    }

    # Following is a reverse mapping of escape characters, used when we
    # output JSON.  Only those escapes which are always safe (e.g., in JSON)
    # are here.  It won't hurt if we leave questionable ones out.
    _rev_escapes = {
        "\n": "\\n",
        "\t": "\\t",
        "\b": "\\b",
        "\r": "\\r",
        "\f": "\\f",
        '"': '\\"',
        "\\": "\\\\",
    }
    _optional_rev_escapes = {"/": "\\/"}  # only escaped if forced to do so

    json_syntax_characters = '{}[]"\\,:0123456789.-+abcdefghijklmnopqrstuvwxyz \t\n\r'

    all_hook_names = (
        "decode_number",
        "decode_float",
        "decode_object",
        "decode_array",
        "decode_string",
        "encode_value",
        "encode_dict",
        "encode_dict_key",
        "encode_sequence",
        "encode_bytes",
        "encode_default",
    )

    def __init__(self, **kwargs):
        """Creates a JSON encoder/decoder object.

        You may pass encoding and decoding options either by passing
        an argument named 'json_options' with an instance of a
        json_options class; or with individual keyword/values that will
        be used to initialize a new json_options object.

        You can also set hooks by using keyword arguments using the
        hook name; e.g., encode_dict=my_hook_func.

        """
        import unicodedata

        kwargs = kwargs.copy()
        # Initialize hooks
        for hookname in self.all_hook_names:
            if hookname in kwargs:
                self.set_hook(hookname, kwargs[hookname])
                del kwargs[hookname]
            else:
                self.set_hook(hookname, None)

        # Set options
        if "json_options" in kwargs:
            self._options = kwargs["json_options"]
        else:
            self._options = json_options(**kwargs)

        # The following is a boolean map of the first 256 characters
        # which will quickly tell us which of those characters never
        # need to be escaped.

        self._asciiencodable = [
            32 <= c < 128
            and chr(c) not in self._rev_escapes
            and unicodedata.category(chr(c)) not in ["Cc", "Cf", "Zl", "Zp"]
            for c in range(0, 256)
        ]

    @property
    def options(self):
        """The optional behaviors used, e.g., the JSON conformance
        strictness.  Returns an instance of json_options.

        """
        return self._options

    def clear_hook(self, hookname):
        """Unsets a hook callback, as previously set with set_hook()."""
        self.set_hook(hookname, None)

    def clear_all_hooks(self):
        """Unsets all hook callbacks, as previously set with set_hook()."""
        for hookname in self.all_hook_names:
            self.clear_hook(hookname)

    def set_hook(self, hookname, function):
        """Sets a user-defined callback function used during encoding or decoding.

        The 'hookname' argument must be a string containing the name of
        one of the available hooks, listed below.

        The 'function' argument must either be None, which disables the hook,
        or a callable function.  Hooks do not stack, if you set a hook it will
        undo any previously set hook.

        Netsted values.  When decoding JSON that has nested objects or
        arrays, the decoding hooks will be called once for every
        corresponding value, even if nested.  Generally the decoding
        hooks will be called from the inner-most value outward, and
        then left to right.

        Skipping. Any hook function may raise a JSONSkipHook exception
        if it does not wish to handle the particular invocation.  This
        will have the effect of skipping the hook for that particular
        value, as if the hook was net set.

        AVAILABLE HOOKS:

        * decode_string
            Called for every JSON string literal with the
            Python-equivalent string value as an argument. Expects to
            get a Python object in return.

        * decode_float:
            Called for every JSON number that looks like a float (has
            a ".").  The string representation of the number is passed
            as an argument.  Expects to get a Python object in return.

        * decode_number:
            Called for every JSON number. The string representation of
            the number is passed as an argument.  Expects to get a
            Python object in return.  NOTE: If the number looks like a
            float and the 'decode_float' hook is set, then this hook
            will not be called.

        * decode_array:
            Called for every JSON array. A Python list is passed as
            the argument, and expects to get a Python object back.
            NOTE: this hook will get called for every array, even
            for nested arrays.

        * decode_object:
            Called for every JSON object.  A Python dictionary is passed
            as the argument, and expects to get a Python object back.
            NOTE: this hook will get called for every object, even
            for nested objects.

        * encode_value:
            Called for every Python object which is to be encoded into JSON.

        * encode_dict:
            Called for every Python dictionary or anything that looks
            like a dictionary.

        * encode_dict_key:
            Called for every dictionary key.

        * encode_sequence:
            Called for every Python sequence-like object that is not a
            dictionary or string. This includes lists and tuples.

        * encode_bytes:
            Called for every Python bytes or bytearray type; or for
            any memoryview with a byte ('B') item type.  (Python 3 only)

        * encode_default:
            Called for any Python type which can not otherwise be converted
            into JSON, even after applying any other encoding hooks.

        """
        if hookname in self.all_hook_names:
            att = hookname + "_hook"
            if function is not None and not callable(function):
                raise ValueError(
                    "Hook %r must be None or a callable function" % hookname
                )
            setattr(self, att, function)
        else:
            raise ValueError("Unknown hook name %r" % hookname)

    def has_hook(self, hook_name):
        if not hook_name or hook_name not in self.all_hook_names:
            return False
        hook = getattr(self, hook_name + "_hook")
        return callable(hook)

    def call_hook(self, hook_name, input_object, position=None, *args, **kwargs):
        """Wrapper function to invoke a user-supplied hook function.

        This will capture any exceptions raised by the hook and do something
        appropriate with it.

        """
        import sys

        if hook_name not in self.all_hook_names:
            raise AttributeError("No such hook %r" % hook_name)
        hook = getattr(self, hook_name + "_hook")
        if not callable(hook):
            raise TypeError("Hook is not callable: %r" % (hook,))
        try:
            rval = hook(input_object, *args, **kwargs)
        except JSONSkipHook:
            raise  # Do nothing
        except Exception as err:
            exc_info = sys.exc_info()
            if hook_name.startswith("encode_"):
                ex_class = JSONEncodeHookError
            else:
                ex_class = JSONDecodeHookError

            if isinstance(err, JSONStopProcessing):
                severity = "fatal"
            else:
                severity = "error"

            newerr = ex_class(
                hook_name,
                exc_info,
                input_object,
                *args,
                position=position,
                severity=severity,
            )

            # Simulate Python 3's: "raise X from Y" exception chaining
            newerr.__cause__ = err
            newerr.__traceback__ = exc_info[2]
            raise newerr
        return rval

    def isws(self, c):
        """Determines if the given character is considered as white space.

        Note that Javscript is much more permissive on what it considers
        to be whitespace than does JSON.

        Ref. ECMAScript section 7.2

        """
        if not self.options.unicode_whitespace:
            return c in " \t\n\r"
        else:
            if not isinstance(c, str):
                c = str(c)
            if c in " \t\n\r\f\v":
                return True
            import unicodedata

            return unicodedata.category(c) == "Zs"

    def islineterm(self, c):
        """Determines if the given character is considered a line terminator.

        Ref. ECMAScript section 7.3

        """
        if c == "\r" or c == "\n":
            return True
        if c == "\u2028" or c == "\u2029":  # unicodedata.category(c) in  ['Zl', 'Zp']
            return True
        return False

    def recover_parser(self, state):
        """Try to recover after a syntax error by locating the next "known" position."""
        buf = state.buf
        buf.skipuntil(lambda c: c in ",:[]{}\"';" or helpers.char_is_unicode_eol(c))
        stopchar = buf.peek()
        self.skipws(state)
        if buf.at_end:
            state.push_info(
                "Could not recover parsing after previous error", position=buf.position
            )
        else:
            state.push_info(
                "Recovering parsing after character %r" % stopchar,
                position=buf.position,
            )
        return stopchar

    def decode_null(self, state):
        """
        Intermediate-level decoder for ECMAScript 'null' keyword.
        Takes a string and a starting index, and returns a Python
        None object and the index of the next unparsed character.
        """
        buf = state.buf
        start_position = buf.position
        kw = buf.pop_identifier()
        if not kw or kw != "null":
            state.push_error("Expected a 'null' keyword'", kw, position=start_position)
        else:
            state.stats.num_nulls += 1
        return None

    def encode_undefined(self, state):
        """Produces the ECMAScript 'undefined' keyword."""
        state.append("undefined")

    def encode_null(self, state):
        """Produces the JSON 'null' keyword."""
        state.append("null")

    def decode_boolean(self, state):
        """Intermediate-level decode for JSON boolean literals.

        Takes a string and a starting index, and returns a Python bool
        (True or False) and the index of the next unparsed character.

        """
        buf = state.buf
        start_position = buf.position
        kw = buf.pop_identifier()
        if not kw or kw not in ("true", "false"):
            state.push_error(
                "Expected a 'true' or 'false' keyword'", kw, position=start_position
            )
        else:
            state.stats.num_bools += 1
        return kw == "true"

    def encode_boolean(self, bval, state):
        """Encodes the Python boolean into a JSON Boolean literal."""
        state.append("true" if bool(bval) else "false")

    def decode_number(self, state):
        """Intermediate-level decoder for JSON numeric literals.

        Takes a string and a starting index, and returns a Python
        suitable numeric type and the index of the next unparsed character.

        The returned numeric type can be either of a Python int,
        long, or float.  In addition some special non-numbers may
        also be returned such as nan, inf, and neginf (technically
        which are Python floats, but have no numeric value.)

        Ref. ECMAScript section 8.5.

        """
        buf = state.buf
        self.skipws(state)
        start_position = buf.position

        # Use external number parser hook if available
        if self.has_hook("decode_number") or self.has_hook("decode_float"):
            c = buf.peek()
            if c and c in "-+0123456789.":  # First chars for a number-like value
                buf.save_position()
                nbr = buf.pop_while_in("-+0123456789abcdefABCDEF" "NaN" "Infinity.")
                if "." in nbr and self.has_hook("decode_float"):
                    hook_name = "decode_float"
                elif self.has_hook("decode_number"):
                    hook_name = "decode_number"
                else:
                    hook_name = None

                if hook_name:
                    try:
                        val = self.call_hook(hook_name, nbr, position=start_position)
                    except JSONSkipHook:
                        pass
                    except JSONError as err:
                        state.push_exception(err)
                        val = undefined
                    else:
                        buf.clear_saved_position()
                        return val
                # Hook didn't handle it, restore old position
                buf.restore_position()

        # Detect initial sign character(s)
        sign = +1
        sign_count = 0
        sign_saw_plus = False
        sign_saw_ws = False
        c = buf.peek()
        while c and c in "+-":
            if c == "-":
                sign = sign * -1
            elif c == "+":
                sign_saw_plus = True
            sign_count += 1
            buf.skip()
            if self.skipws_nocomments(state) > 0:
                sign_saw_ws = True
            c = buf.peek()

        if sign_count > 1 or sign_saw_plus:
            state.push_cond(
                self.options.all_numeric_signs,
                'Numbers may only have a single "-" as a sign prefix',
                position=start_position,
            )
        if sign_saw_ws:
            state.push_error(
                "Spaces may not appear between a +/- number sign and the digits",
                position=start_position,
            )

        # Check for ECMAScript symbolic non-numbers
        if not c:
            state.push_error(
                "Missing numeric value after sign", position=start_position
            )
            self.recover_parser(state)
            self.stats.num_undefineds += 1
            return undefined
        elif c.isalpha() or c in "_$":
            kw = buf.popwhile(lambda c: c.isalnum() or c in "_$")
            if kw == "NaN":
                state.push_cond(
                    self.options.non_numbers,
                    "NaN literals are not allowed in strict JSON",
                    position=start_position,
                )
                state.stats.num_nans += 1
                return self.options.nan
            elif kw == "Infinity":
                state.push_cond(
                    self.options.non_numbers,
                    "Infinity literals are not allowed in strict JSON",
                    position=start_position,
                )
                state.stats.num_infinities += 1
                if sign < 0:
                    return self.options.neginf
                else:
                    return self.options.inf
            else:
                state.push_error(
                    "Unknown numeric value keyword", kw, position=start_position
                )
                return undefined

        # Check for radix-prefixed numbers
        elif c == "0" and (buf.peek(1) in ["x", "X"]):
            # ----- HEX NUMBERS 0x123
            prefix = buf.popstr(2)
            digits = buf.popwhile(helpers.is_hex_digit)
            state.push_cond(
                self.options.hex_numbers,
                "Hexadecimal literals are not allowed in strict JSON",
                prefix + digits,
                position=start_position,
            )
            if len(digits) == 0:
                state.push_error(
                    "Hexadecimal number is invalid", position=start_position
                )
                self.recover_parser(state)
                return undefined
            ival = helpers.decode_hex(digits)
            state.update_integer_stats(ival, sign=sign, position=start_position)
            n = state.options.make_int(ival, sign, number_format=NUMBER_FORMAT_HEX)
            return n
        elif c == "0" and (buf.peek(1) in ["o", "O"]):
            # ----- NEW-STYLE OCTAL NUMBERS  0o123
            prefix = buf.popstr(2)
            digits = buf.popwhile(helpers.is_octal_digit)
            state.push_cond(
                self.options.octal_numbers,
                "Octal literals are not allowed in strict JSON",
                prefix + digits,
                position=start_position,
            )
            if len(digits) == 0:
                state.push_error("Octal number is invalid", position=start_position)
                self.recover_parser(state)
                return undefined
            ival = helpers.decode_octal(digits)
            state.update_integer_stats(ival, sign=sign, position=start_position)
            n = state.options.make_int(ival, sign, number_format=NUMBER_FORMAT_OCTAL)
            return n
        elif c == "0" and (buf.peek(1) in ["b", "B"]):
            # ----- NEW-STYLE BINARY NUMBERS  0b1101
            prefix = buf.popstr(2)
            digits = buf.popwhile(helpers.is_binary_digit)
            state.push_cond(
                self.options.binary_numbers,
                "Binary literals are not allowed in strict JSON",
                prefix + digits,
                position=start_position,
            )
            if len(digits) == 0:
                state.push_error("Binary number is invalid", position=start_position)
                self.recover_parser(state)
                return undefined
            ival = helpers.decode_binary(digits)
            state.update_integer_stats(ival, sign=sign, position=start_position)
            n = state.options.make_int(ival, sign, number_format=NUMBER_FORMAT_BINARY)
            return n
        else:
            # ----- DECIMAL OR LEGACY-OCTAL NUMBER.   123, 0123
            # General syntax is:  \d+[\.\d+][e[+-]?\d+]
            number = buf.popwhile(lambda c: c in "0123456789.+-eE")
            imax = len(number)
            if imax == 0:
                state.push_error("Missing numeric value", position=start_position)
            has_leading_zero = False
            units_digits = []  # digits making up whole number portion
            fraction_digits = []  # digits making up fractional portion
            exponent_digits = []  # digits making up exponent portion (excluding sign)
            esign = "+"  # sign of exponent
            sigdigits = 0  # number of significant digits (approximate)
            saw_decimal_point = False
            saw_exponent = False

            # Break number into parts in a first pass...use a mini state machine
            in_part = "units"
            for i, c in enumerate(number):
                if c == ".":
                    if in_part != "units":
                        state.push_error("Bad number", number, position=start_position)
                        self.recover_parser(state)
                        return undefined
                    in_part = "fraction"
                    saw_decimal_point = True
                elif c in "eE":
                    if in_part == "exponent":
                        state.push_error("Bad number", number, position=start_position)
                        self.recover_parser(state)
                        return undefined
                    in_part = "exponent"
                    saw_exponent = True
                elif c in "+-":
                    if in_part != "exponent" or exponent_digits:
                        state.push_error("Bad number", number, position=start_position)
                        self.recover_parser(state)
                        return undefined
                    esign = c
                else:  # digit
                    if in_part == "units":
                        units_digits.append(c)
                    elif in_part == "fraction":
                        fraction_digits.append(c)
                    elif in_part == "exponent":
                        exponent_digits.append(c)
            units_s = "".join(units_digits)
            fraction_s = "".join(fraction_digits)
            exponent_s = "".join(exponent_digits)

            # Basic syntax rules checking
            is_integer = not (saw_decimal_point or saw_exponent)

            if not units_s and not fraction_s:
                state.push_error("Bad number", number, position=start_position)
                self.recover_parser(state)
                return undefined

            if saw_decimal_point and not fraction_s:
                state.push_cond(
                    self.options.trailing_decimal_point,
                    "Bad number, decimal point must be followed by at least one digit",
                    number,
                    position=start_position,
                )
                fraction_s = "0"

            if saw_exponent and not exponent_s:
                state.push_error(
                    "Bad number, exponent is missing", number, position=start_position
                )
                self.recover_parser(state)
                return undefined

            if not units_s:
                state.push_cond(
                    self.options.initial_decimal_point,
                    "Bad number, decimal point must be preceded by at least one digit",
                    number,
                    position=start_position,
                )
                units = "0"  # noqa: F841
            elif len(units_s) > 1 and units_s[0] == "0":
                has_leading_zero = True
                if self.options.is_forbid_leading_zeros:
                    state.push_cond(  # noqa: F841
                        self.options.leading_zeros,
                        "Numbers may not have extra leading zeros",
                        number,
                        position=start_position,
                    )
                elif self.options.is_warn_leading_zeros:
                    state.push_cond(  # noqa: F841
                        self.options.leading_zeros,
                        "Numbers may not have leading zeros; interpreting as %s"
                        % self.options.leading_zero_radix_as_word,
                        number,
                        position=start_position,
                    )

            # Estimate number of significant digits
            sigdigits = len((units_s + fraction_s).replace("0", " ").strip())

            # Handle legacy octal integers.
            if has_leading_zero and is_integer and self.options.leading_zero_radix == 8:
                # ----- LEGACY-OCTAL  0123
                try:
                    ival = helpers.decode_octal(units_s)
                except ValueError:
                    state.push_error(
                        "Bad number, not a valid octal value",
                        number,
                        position=start_position,
                    )
                    self.recover_parser(state)
                    return self.options.nan  # undefined
                state.update_integer_stats(ival, sign=sign, position=start_position)
                n = state.options.make_int(
                    ival, sign, number_format=NUMBER_FORMAT_LEGACYOCTAL
                )
                return n

            # Determine the exponential part
            if exponent_s:
                try:
                    exponent = int(exponent_s)
                except ValueError:
                    state.push_error(
                        "Bad number, bad exponent", number, position=start_position
                    )
                    self.recover_parser(state)
                    return undefined
                if esign == "-":
                    exponent = -exponent
            else:
                exponent = 0

            # Try to make an int/long first.
            if not saw_decimal_point and exponent >= 0:
                # ----- A DECIMAL INTEGER
                ival = int(units_s)
                if exponent != 0:
                    ival *= 10**exponent
                state.update_integer_stats(ival, sign=sign, position=start_position)
                n = state.options.make_int(ival, sign)
            else:
                # ----- A FLOATING-POINT NUMBER
                try:
                    if (
                        exponent < float_minexp
                        or exponent > float_maxexp
                        or sigdigits > float_sigdigits
                    ):
                        n = state.options.make_decimal(number, sign)
                    else:
                        n = state.options.make_float(number, sign)
                except ValueError as err:
                    state.push_error(
                        "Bad number, %s" % err.message, number, position=start_position
                    )
                    n = undefined
                else:
                    state.update_float_stats(n, sign=sign, position=start_position)
            return n

    def encode_number(self, n, state):
        """Encodes a Python numeric type into a JSON numeric literal.

        The special non-numeric values of float('nan'), float('inf')
        and float('-inf') are translated into appropriate JSON
        literals.

        Note that Python complex types are not handled, as there is no
        ECMAScript equivalent type.

        """
        if isinstance(n, complex):
            if n.imag:
                raise JSONEncodeError(
                    "Can not encode a complex number that has a non-zero imaginary part",
                    n,
                )
            n = n.real

        if isinstance(n, json_int):
            state.append(n.json_format())
            return

        if isinstance(n, int):
            state.append(str(n))
            return

        if decimal and isinstance(n, decimal.Decimal):
            if n.is_nan():  # Could be 'NaN' or 'sNaN'
                state.append("NaN")
            elif n.is_infinite():
                if n.is_signed():
                    state.append("-Infinity")
                else:
                    state.append("Infinity")
            else:
                s = str(n).lower()
                if "e" not in s and "." not in s:
                    s = s + ".0"
                state.append(s)
            return

        global nan, inf, neginf  # noqa: F824
        if n is nan:
            state.append("NaN")
        elif n is inf:
            state.append("Infinity")
        elif n is neginf:
            state.append("-Infinity")
        elif isinstance(n, float):
            # Check for non-numbers.
            # In python nan == inf == -inf, so must use repr() to distinguish
            reprn = repr(n).lower()
            if ("inf" in reprn and "-" in reprn) or n == neginf:
                state.append("-Infinity")
            elif "inf" in reprn or n is inf:
                state.append("Infinity")
            elif "nan" in reprn or n is nan:
                state.append("NaN")
            else:
                # A normal float.
                state.append(repr(n))
        else:
            raise TypeError(
                "encode_number expected an integral, float, or decimal number type",
                type(n),
            )

    def decode_string(self, state):
        """Intermediate-level decoder for JSON string literals.

        Takes a string and a starting index, and returns a Python
        string (or unicode string) and the index of the next unparsed
        character.

        """
        buf = state.buf
        self.skipws(state)
        quote = buf.peek()
        if quote == '"':
            pass
        elif quote == "'":
            state.push_cond(
                self.options.single_quoted_strings,
                "String literals must use double quotation marks in strict JSON",
            )
        else:
            state.push_error("String literal must be properly quoted")
            return undefined

        string_position = buf.position
        buf.skip()

        if self.options.is_forbid_js_string_escapes:
            escapes = self._escapes_json
        else:
            escapes = self._escapes_js
        ccallowed = not self.options.is_forbid_control_char_in_string
        chunks = []
        _append = chunks.append

        # Used to track the last seen high-surrogate character
        high_surrogate = None
        highsur_position = None

        # Used to track if errors occured so we don't keep reporting multiples
        had_lineterm_error = False

        # Start looping character by character until the final quotation mark
        saw_final_quote = False
        should_stop = False
        while not saw_final_quote and not should_stop:
            if buf.at_end:
                state.push_error(
                    "String literal is not terminated",
                    outer_position=string_position,
                    context="String",
                )
                break
            c = buf.peek()

            # Make sure a high surrogate is immediately followed by a low surrogate
            if high_surrogate:
                if 0xDC00 <= ord(c) <= 0xDFFF:
                    low_surrogate = buf.pop()
                    try:
                        uc = helpers.surrogate_pair_as_unicode(
                            high_surrogate, low_surrogate
                        )
                    except ValueError:
                        state.push_error(
                            "Illegal Unicode surrogate pair",
                            (high_surrogate, low_surrogate),
                            position=highsur_position,
                            outer_position=string_position,
                            context="String",
                        )
                        should_stop = state.should_stop
                        uc = "\ufffd"  # replacement char
                    _append(uc)
                    high_surrogate = None
                    highsur_position = None
                    continue  # ==== NEXT CHAR
                elif buf.peekstr(2) != "\\u":
                    state.push_error(
                        "High unicode surrogate must be followed by a low surrogate",
                        position=highsur_position,
                        outer_position=string_position,
                        context="String",
                    )
                    should_stop = state.should_stop
                    _append("\ufffd")  # replacement char
                    high_surrogate = None
                    highsur_position = None

            if c == quote:
                buf.skip()  # skip over closing quote
                saw_final_quote = True
                break
            elif c == "\\":
                # Escaped character
                escape_position = buf.position
                buf.skip()  # skip over backslash
                c = buf.peek()
                if not c:
                    state.push_error(
                        "Escape in string literal is incomplete",
                        position=escape_position,
                        outer_position=string_position,
                        context="String",
                    )
                    should_stop = state.should_stop
                    break
                elif helpers.is_octal_digit(c):
                    # Handle octal escape codes first so special \0 doesn't kick in yet.
                    # Follow Annex B.1.2 of ECMAScript standard.
                    if "0" <= c <= "3":
                        maxdigits = 3
                    else:
                        maxdigits = 2
                    digits = buf.popwhile(helpers.is_octal_digit, maxchars=maxdigits)
                    n = helpers.decode_octal(digits)
                    if n == 0:
                        state.push_cond(
                            self.options.zero_byte,
                            "Zero-byte character (U+0000) in string may not be universally safe",
                            "\\" + digits,
                            position=escape_position,
                            outer_position=string_position,
                            context="String",
                        )
                    else:  # n != 0
                        state.push_cond(
                            self.options.octal_numbers,
                            'JSON does not allow octal character escapes other than "\\0"',
                            "\\" + digits,
                            position=escape_position,
                            outer_position=string_position,
                            context="String",
                        )
                    should_stop = state.should_stop
                    if n < 128:
                        _append(chr(n))
                    else:
                        _append(helpers.safe_unichr(n))
                elif c in escapes:
                    buf.skip()
                    _append(escapes[c])
                elif c == "u" or c == "x":
                    buf.skip()
                    esc_opener = "\\" + c
                    esc_closer = ""
                    if c == "u":
                        if buf.peek() == "{":
                            buf.skip()
                            esc_opener += "{"
                            esc_closer = "}"
                            maxdigits = None
                            state.push_cond(
                                self.options.extended_unicode_escapes,
                                "JSON strings do not allow \\u{...} escapes",
                                position=escape_position,
                                outer_position=string_position,
                                context="String",
                            )
                        else:
                            maxdigits = 4
                    else:  # c== 'x'
                        state.push_cond(
                            self.options.js_string_escapes,
                            "JSON strings may not use the \\x hex-escape",
                            position=escape_position,
                            outer_position=string_position,
                            context="String",
                        )
                        should_stop = state.should_stop
                        maxdigits = 2

                    digits = buf.popwhile(helpers.is_hex_digit, maxchars=maxdigits)

                    if esc_closer:
                        if buf.peek() != esc_closer:
                            state.push_error(
                                "Unicode escape sequence is missing closing '%s'"
                                % esc_closer,
                                esc_opener + digits,
                                position=escape_position,
                                outer_position=string_position,
                                context="String",
                            )
                            should_stop = state.should_stop
                        else:
                            buf.skip()

                    esc_sequence = esc_opener + digits + esc_closer

                    if not digits:
                        state.push_error(
                            "numeric character escape sequence is truncated",
                            esc_sequence,
                            position=escape_position,
                            outer_position=string_position,
                            context="String",
                        )
                        should_stop = state.should_stop
                        codepoint = 0xFFFD  # replacement char
                    else:
                        if maxdigits and len(digits) != maxdigits:
                            state.push_error(
                                "escape sequence has too few hexadecimal digits",
                                esc_sequence,
                                position=escape_position,
                                outer_position=string_position,
                                context="String",
                            )
                        codepoint = helpers.decode_hex(digits)

                    if codepoint > 0x10FFFF:
                        state.push_error(
                            "Unicode codepoint is beyond U+10FFFF",
                            esc_opener + digits + esc_closer,
                            position=escape_position,
                            outer_position=string_position,
                            context="String",
                        )
                        codepoint = 0xFFFD  # replacement char

                    if high_surrogate:
                        # Decode surrogate pair and clear high surrogate
                        low_surrogate = chr(codepoint)
                        try:
                            uc = helpers.surrogate_pair_as_unicode(
                                high_surrogate, low_surrogate
                            )
                        except ValueError:
                            state.push_error(
                                "Illegal Unicode surrogate pair",
                                (high_surrogate, low_surrogate),
                                position=highsur_position,
                                outer_position=string_position,
                                context="String",
                            )
                            should_stop = state.should_stop
                            uc = "\ufffd"  # replacement char
                        _append(uc)
                        high_surrogate = None
                        highsur_position = None
                    elif codepoint < 128:
                        # ASCII chars always go in as a str
                        if codepoint == 0:
                            state.push_cond(
                                self.options.zero_byte,
                                "Zero-byte character (U+0000) in string may not be universally safe",
                                position=escape_position,
                                outer_position=string_position,
                                context="String",
                            )
                            should_stop = state.should_stop
                        _append(chr(codepoint))
                    elif 0xD800 <= codepoint <= 0xDBFF:  # high surrogate
                        high_surrogate = chr(
                            codepoint
                        )  # remember until we get to the low surrogate
                        highsur_position = escape_position.copy()
                    elif 0xDC00 <= codepoint <= 0xDFFF:  # low surrogate
                        state.push_error(
                            "Low unicode surrogate must be proceeded by a high surrogate",
                            position=escape_position,
                            outer_position=string_position,
                            context="String",
                        )
                        should_stop = state.should_stop
                        _append("\ufffd")  # replacement char
                    else:
                        # Other chars go in as a unicode char
                        _append(helpers.safe_unichr(codepoint))
                else:
                    # Unknown escape sequence
                    state.push_cond(
                        self.options.nonescape_characters,
                        "String escape code is not allowed in strict JSON",
                        "\\" + c,
                        position=escape_position,
                        outer_position=string_position,
                        context="String",
                    )
                    should_stop = state.should_stop
                    _append(c)
                    buf.skip()
            elif ord(c) <= 0x1F:  # A control character
                if ord(c) == 0:
                    state.push_cond(
                        self.options.zero_byte,
                        "Zero-byte character (U+0000) in string may not be universally safe",
                        position=buf.position,
                        outer_position=string_position,
                        context="String",
                    )
                    should_stop = state.should_stop
                if self.islineterm(c):
                    if not had_lineterm_error:
                        state.push_error(
                            "Line terminator characters must be escaped inside string literals",
                            "U+%04X" % ord(c),
                            position=buf.position,
                            outer_position=string_position,
                            context="String",
                        )
                        should_stop = state.should_stop
                        had_lineterm_error = True
                    _append(c)
                    buf.skip()
                elif ccallowed:
                    _append(c)
                    buf.skip()
                else:
                    state.push_error(
                        "Control characters must be escaped inside JSON string literals",
                        "U+%04X" % ord(c),
                        position=buf.position,
                        outer_position=string_position,
                        context="String",
                    )
                    should_stop = state.should_stop
                    buf.skip()
            elif 0xD800 <= ord(c) <= 0xDBFF:  # a raw high surrogate
                high_surrogate = buf.pop()  # remember until we get to the low surrogate
                highsur_position = buf.position.copy()
            else:  # A normal character; not an escape sequence or end-quote.
                # Find a whole sequence of "safe" characters so we can append them
                # all at once rather than one a time, for speed.
                chunk = buf.popwhile(
                    lambda c: c not in helpers.unsafe_string_chars and c != quote
                )
                if not chunk:
                    _append(c)
                    buf.skip()
                else:
                    _append(chunk)

        # Check proper string termination
        if high_surrogate:
            state.push_error(
                "High unicode surrogate must be followed by a low surrogate",
                position=highsur_position,
                outer_position=string_position,
                context="String",
            )
            _append("\ufffd")  # replacement char
            high_surrogate = None
            highsur_position = None

        if not saw_final_quote:
            state.push_error(
                "String literal is not terminated with a quotation mark",
                position=buf.position,
                outer_position=string_position,
                context="String",
            )

        if state.should_stop:
            return undefined

        # Compose the python string and update stats
        s = "".join(chunks)
        state.update_string_stats(s, position=string_position)

        # Call string hook
        if self.has_hook("decode_string"):
            try:
                s = self.call_hook("decode_string", s, position=string_position)
            except JSONSkipHook:
                pass
            except JSONError as err:
                state.push_exception(err)
                s = undefined
        return s

    def encode_string(self, s, state):
        """Encodes a Python string into a JSON string literal."""
        # Must handle instances of UserString specially in order to be
        # able to use ord() on it's simulated "characters".  Also
        # convert Python2 'str' types to unicode strings first.
        import unicodedata
        import sys
        import collections

        py2strenc = self.options.py2str_encoding
        if isinstance(s, collections.UserString):

            def tochar(c):
                c2 = c.data
                if py2strenc and not isinstance(c2, str):
                    return c2.decode(py2strenc)
                else:
                    return c2
        elif py2strenc and not isinstance(s, str):
            s = s.decode(py2strenc)
            tochar = None
        else:
            # Could use "lambda c:c", but that is too slow.  So we set to None
            # and use an explicit if test inside the loop.
            tochar = None

        chunks = []
        chunks.append('"')
        revesc = self._rev_escapes
        optrevesc = self._optional_rev_escapes
        asciiencodable = self._asciiencodable
        always_escape = state.options.always_escape_chars
        encunicode = state.escape_unicode_test
        i = 0
        imax = len(s)
        while i < imax:
            if tochar:
                c = tochar(s[i])
            else:
                c = s[i]
            cord = ord(c)
            if (
                cord < 256
                and asciiencodable[cord]
                and isinstance(encunicode, bool)
                and not (always_escape and c in always_escape)
            ):
                # Contiguous runs of plain old printable ASCII can be copied
                # directly to the JSON output without worry (unless the user
                # has supplied a custom is-encodable function).
                j = i
                i += 1
                while i < imax:
                    if tochar:
                        c = tochar(s[i])
                    else:
                        c = s[i]
                    cord = ord(c)
                    if (
                        cord < 256
                        and asciiencodable[cord]
                        and not (always_escape and c in always_escape)
                    ):
                        i += 1
                    else:
                        break
                chunks.append(str(s[j:i]))
            elif c in revesc:
                # Has a shortcut escape sequence, like "\n"
                chunks.append(revesc[c])
                i += 1
            elif cord <= 0x1F:
                # Always unicode escape ASCII-control characters
                chunks.append(r"\u%04x" % cord)
                i += 1
            elif 0xD800 <= cord <= 0xDFFF:
                # A raw surrogate character!
                # This should ONLY happen in "narrow" Python builds
                # where (sys.maxunicode == 65535) as Python itself
                # uses UTF-16.  But for "wide" Python builds, a raw
                # surrogate should never happen.
                handled_raw_surrogates = False
                if (
                    sys.maxunicode == 0xFFFF
                    and 0xD800 <= cord <= 0xDBFF
                    and (i + 1) < imax
                ):
                    # In a NARROW Python, output surrogate pair as-is
                    hsurrogate = cord
                    i += 1
                    if tochar:
                        c = tochar(s[i])
                    else:
                        c = s[i]
                    cord = ord(c)
                    i += 1
                    if 0xDC00 <= cord <= 0xDFFF:
                        lsurrogate = cord
                        chunks.append(r"\u%04x\u%04x" % (hsurrogate, lsurrogate))
                        handled_raw_surrogates = True
                if not handled_raw_surrogates:
                    cname = "U+%04X" % cord
                    raise JSONEncodeError(
                        "can not include or escape a Unicode surrogate character", cname
                    )
            elif cord <= 0xFFFF:
                # Other BMP Unicode character
                if always_escape and c in always_escape:
                    doesc = True
                elif unicodedata.category(c) in ["Cc", "Cf", "Zl", "Zp"]:
                    doesc = True
                elif callable(encunicode):
                    doesc = encunicode(c)
                else:
                    doesc = encunicode

                if doesc:
                    if c in optrevesc:
                        chunks.append(optrevesc[c])
                    else:
                        chunks.append(r"\u%04x" % cord)
                else:
                    chunks.append(c)
                i += 1
            else:  # ord(c) >= 0x10000
                # Non-BMP Unicode
                if always_escape and c in always_escape:
                    doesc = True
                elif unicodedata.category(c) in ["Cc", "Cf", "Zl", "Zp"]:
                    doesc = True
                elif callable(encunicode):
                    doesc = encunicode(c)
                else:
                    doesc = encunicode

                if doesc:
                    for surrogate in helpers.unicode_as_surrogate_pair(c):
                        chunks.append(r"\u%04x" % ord(surrogate))
                else:
                    chunks.append(c)
                i += 1

        chunks.append('"')
        state.append("".join(chunks))

    def decode_identifier(self, state, identifier_as_string=False):
        """Decodes an identifier/keyword."""
        buf = state.buf
        self.skipws(state)
        start_position = buf.position
        obj = None

        kw = buf.pop_identifier()

        if not kw:
            state.push_error("Expected an identifier", position=start_position)
        elif kw == "null":
            obj = None
            state.stats.num_nulls += 1
        elif kw == "true":
            obj = True
            state.stats.num_bools += 1
        elif kw == "false":
            obj = False
            state.stats.num_bools += 1
        elif kw == "undefined":
            state.push_cond(
                self.options.undefined_values,
                "Strict JSON does not allow the 'undefined' keyword",
                kw,
                position=start_position,
            )
            obj = undefined
            state.stats.num_undefineds += 1
        elif kw == "NaN" or kw == "Infinity":
            state.push_cond(
                self.options.non_numbers,
                "%s literals are not allowed in strict JSON" % kw,
                kw,
                position=start_position,
            )
            if self.has_hook("decode_float"):
                try:
                    val = self.call_hook("decode_float", kw, position=start_position)
                except JSONSkipHook:
                    pass
                except JSONError as err:
                    state.push_exception(err)
                    return undefined
                else:
                    return val
            elif self.has_hook("decode_number"):
                try:
                    val = self.call_hook("decode_number", kw, position=start_position)
                except JSONSkipHook:
                    pass
                except JSONError as err:
                    state.push_exception(err)
                    return undefined
                else:
                    return val
            if kw == "NaN":
                state.stats.num_nans += 1
                obj = state.options.nan
            else:
                state.stats.num_infinities += 1
                obj = state.options.inf
        else:
            # Convert unknown identifiers into strings
            if identifier_as_string:
                if kw in helpers.javascript_reserved_words:
                    state.push_warning(
                        "Identifier is a JavaScript reserved word",
                        kw,
                        position=start_position,
                    )
                state.push_cond(
                    self.options.identifier_keys,
                    "JSON does not allow identifiers to be used as strings",
                    kw,
                    position=start_position,
                )
                state.stats.num_identifiers += 1
                obj = self.decode_javascript_identifier(kw)
            else:
                state.push_error("Unknown identifier", kw, position=start_position)
                obj = undefined
                state.stats.num_identifiers += 1
        return obj

    def skip_comment(self, state):
        """Skips an ECMAScript comment, either // or /* style.

        The contents of the comment are returned as a string, as well
        as the index of the character immediately after the comment.

        """
        buf = state.buf
        uniws = self.options.unicode_whitespace
        s = buf.peekstr(2)
        if s != "//" and s != "/*":
            return None
        state.push_cond(
            self.options.comments, "Comments are not allowed in strict JSON"
        )
        start_position = buf.position
        buf.skip(2)
        multiline = s == "/*"
        saw_close = False
        while not buf.at_end:
            if multiline:
                if buf.peekstr(2) == "*/":
                    buf.skip(2)
                    saw_close = True
                    break
                elif buf.peekstr(2) == "/*":
                    state.push_error(
                        "Multiline /* */ comments may not nest",
                        outer_position=start_position,
                        context="Comment",
                    )
            else:
                if buf.at_eol(uniws):
                    buf.skip_to_next_line(uniws)
                    saw_close = True
                    break
            buf.pop()

        if not saw_close and multiline:
            state.push_error(
                "Comment was never terminated",
                outer_position=start_position,
                context="Comment",
            )
        state.stats.num_comments += 1

    def skipws_nocomments(self, state):
        """Skips whitespace (will not allow comments)."""
        return state.buf.skipws(not self.options.is_forbid_unicode_whitespace)

    def skipws(self, state):
        """Skips all whitespace, including comments and unicode whitespace

        Takes a string and a starting index, and returns the index of the
        next non-whitespace character.

        If the 'skip_comments' behavior is True and not running in
        strict JSON mode, then comments will be skipped over just like
        whitespace.

        """
        buf = state.buf
        uniws = not self.options.unicode_whitespace
        while not buf.at_end:
            c = buf.peekstr(2)
            if c == "/*" or c == "//":
                cmt = self.skip_comment(state)  # noqa: F841
            elif buf.at_ws(uniws):
                buf.skipws(uniws)
            else:
                break

    def decode_composite(self, state):
        """Intermediate-level JSON decoder for composite literal types (array and object)."""
        if state.should_stop:
            return None
        buf = state.buf
        self.skipws(state)
        opener = buf.peek()
        if opener not in "{[":
            state.push_error('Composite data must start with "[" or "{"')
            return None
        start_position = buf.position
        buf.skip()
        if opener == "[":
            isdict = False
            closer = "]"
            obj = []
        else:
            isdict = True
            closer = "}"
            if state.options.sort_keys == SORT_PRESERVE and _OrderedDict:
                obj = _OrderedDict()
            else:
                obj = {}
        num_items = 0
        self.skipws(state)

        c = buf.peek()
        if c == closer:
            # empty composite
            buf.skip()
            done = True
        else:
            saw_value = False  # set to false at beginning and after commas
            done = False
            while not done and not buf.at_end and not state.should_stop:
                self.skipws(state)
                c = buf.peek()
                if c == "":
                    break  # will report error futher down because done==False
                elif c == ",":
                    if not saw_value:
                        # no preceding value, an elided (omitted) element
                        if isdict:
                            state.push_error(
                                "Can not omit elements of an object (dictionary)",
                                outer_position=start_position,
                                context="Object",
                            )
                        else:
                            state.push_cond(
                                self.options.omitted_array_elements,
                                "Can not omit elements of an array (list)",
                                outer_position=start_position,
                                context="Array",
                            )
                            obj.append(undefined)
                            if state.stats:
                                state.stats.num_undefineds += 1
                    buf.skip()  # skip over comma
                    saw_value = False
                    continue
                elif c == closer:
                    if not saw_value:
                        if isdict:
                            state.push_cond(
                                self.options.trailing_comma,
                                "Strict JSON does not allow a final comma in an object (dictionary) literal",
                                outer_position=start_position,
                                context="Object",
                            )
                        else:
                            state.push_cond(
                                self.options.trailing_comma,
                                "Strict JSON does not allow a final comma in an array (list) literal",
                                outer_position=start_position,
                                context="Array",
                            )
                    buf.skip()  # skip over closer
                    done = True
                    break
                elif c in "]}":
                    if isdict:
                        cdesc = "Object"
                    else:
                        cdesc = "Array"
                    state.push_error(
                        "Expected a '%c' but saw '%c'" % (closer, c),
                        outer_position=start_position,
                        context=cdesc,
                    )
                    done = True
                    break

                if state.should_stop:
                    break

                # Decode the item/value
                value_position = buf.position

                if isdict:
                    val = self.decodeobj(state, identifier_as_string=True)
                else:
                    val = self.decodeobj(state, identifier_as_string=False)

                if val is syntax_error:
                    recover_c = self.recover_parser(state)
                    if recover_c not in ":":
                        continue

                if state.should_stop:
                    break

                if saw_value:
                    # Two values without a separating comma
                    if isdict:
                        cdesc = "Object"
                    else:
                        cdesc = "Array"
                    state.push_error(
                        "Values must be separated by a comma",
                        position=value_position,
                        outer_position=start_position,
                        context=cdesc,
                    )

                saw_value = True
                self.skipws(state)

                if state.should_stop:
                    break

                if isdict:
                    skip_item = False
                    key = val  # Ref 11.1.5
                    key_position = value_position
                    if not helpers.isstringtype(key):
                        if helpers.isnumbertype(key):
                            state.push_cond(
                                self.options.nonstring_keys,
                                "JSON only permits string literals as object properties (keys)",
                                position=key_position,
                                outer_position=start_position,
                                context="Object",
                            )
                        else:
                            state.push_error(
                                "Object properties (keys) must be string literals, numbers, or identifiers",
                                position=key_position,
                                outer_position=start_position,
                                context="Object",
                            )
                            skip_item = True
                    c = buf.peek()
                    if c != ":":
                        state.push_error(
                            'Missing value for object property, expected ":"',
                            position=value_position,
                            outer_position=start_position,
                            context="Object",
                        )
                    buf.skip()  # skip over colon
                    self.skipws(state)

                    rval = self.decodeobj(state)
                    self.skipws(state)
                    if not skip_item:
                        if key in obj:
                            state.push_cond(
                                self.options.duplicate_keys,
                                "Object contains duplicate key",
                                key,
                                position=key_position,
                                outer_position=start_position,
                                context="Object",
                            )
                        if key == "":
                            state.push_cond(
                                self.options.non_portable,
                                'Using an empty string "" as an object key may not be portable',
                                position=key_position,
                                outer_position=start_position,
                                context="Object",
                            )
                        obj[key] = rval
                        num_items += 1
                else:  # islist
                    obj.append(val)
                    num_items += 1
            # end while

        if state.stats:
            if isdict:
                state.stats.max_items_in_object = max(
                    state.stats.max_items_in_object, num_items
                )
            else:
                state.stats.max_items_in_array = max(
                    state.stats.max_items_in_array, num_items
                )

        if state.should_stop:
            return obj

        # Make sure composite value is properly terminated
        if not done:
            if isdict:
                state.push_error(
                    "Object literal (dictionary) is not terminated",
                    outer_position=start_position,
                    context="Object",
                )
            else:
                state.push_error(
                    "Array literal (list) is not terminated",
                    outer_position=start_position,
                    context="Array",
                )

        # Update stats and run hooks
        if isdict:
            state.stats.num_objects += 1
            if self.has_hook("decode_object"):
                try:
                    obj = self.call_hook("decode_object", obj, position=start_position)
                except JSONSkipHook:
                    pass
                except JSONError as err:
                    state.push_exception(err)
                    obj = undefined
        else:
            state.stats.num_arrays += 1
            if self.has_hook("decode_array"):
                try:
                    obj = self.call_hook("decode_array", obj, position=start_position)
                except JSONSkipHook:
                    pass
                except JSONError as err:
                    state.push_exception(err)
                    obj = undefined
        return obj

    def decode_javascript_identifier(self, name):
        """Convert a JavaScript identifier into a Python string object.

        This method can be overriden by a subclass to redefine how JavaScript
        identifiers are turned into Python objects.  By default this just
        converts them into strings.

        """
        return name

    def decodeobj(self, state, identifier_as_string=False, at_document_start=False):
        """Intermediate-level JSON decoder.

        Takes a string and a starting index, and returns a two-tuple consting
        of a Python object and the index of the next unparsed character.

        If there is no value at all (empty string, etc), then None is
        returned instead of a tuple.

        """
        buf = state.buf
        obj = None
        self.skipws(state)
        if buf.at_end:
            state.push_error("Unexpected end of input")

        c = buf.peek()
        if c in "{[":
            state.cur_depth += 1
            try:
                state.update_depth_stats()
                obj = self.decode_composite(state)
            finally:
                state.cur_depth -= 1
        else:
            if at_document_start:
                state.push_cond(
                    self.options.any_type_at_start,
                    "JSON document must start with an object or array type only",
                )
            if c in self._string_quotes:
                obj = self.decode_string(state)
            elif c.isdigit() or c in ".+-":
                obj = self.decode_number(state)
            elif c.isalpha() or c in "_$":
                obj = self.decode_identifier(
                    state, identifier_as_string=identifier_as_string
                )
            else:
                state.push_error("Can not decode value starting with character %r" % c)
                buf.skip()
                self.recover_parser(state)
                obj = syntax_error
        return obj

    def decode(self, txt, encoding=None, return_errors=False, return_stats=False):
        """Decodes a JSON-encoded string into a Python object.

        The 'return_errors' parameter controls what happens if the
        input JSON has errors in it.

            * False: the first error will be raised as a Python
              exception. If there are no errors then the corresponding
              Python object will be returned.

            * True: the return value is always a 2-tuple: (object, error_list)

        """
        import sys

        state = decode_state(options=self.options)

        # Prepare the input
        state.set_input(txt, encoding=encoding)

        # Do the decoding
        if not state.has_errors:
            self.__sanity_check_start(state)

        if not state.has_errors:
            try:
                self._do_decode(state)  # DECODE!
            except JSONException as err:
                state.push_exception(err)
            except (
                Exception
            ) as err:  # Mainly here to catch maximum recursion depth exceeded
                e2 = sys.exc_info()
                raise
                newerr = JSONDecodeError(
                    "An unexpected failure occured",
                    severity="fatal",
                    position=state.buf.position,
                )
                newerr.__cause__ = err
                newerr.__traceback__ = e2[2]
                state.push_exception(newerr)

        if return_stats and state.buf:
            state.stats.num_excess_whitespace = state.buf.num_ws_skipped
            state.stats.total_chars = state.buf.position.char_position

        # Handle the errors
        result_type = _namedtuple("json_results", ["object", "errors", "stats"])

        if return_errors:
            if return_stats:
                return result_type(state.obj, state.errors, state.stats)
            else:
                return result_type(state.obj, state.errors, None)
        else:
            # Don't cause warnings to raise an error
            errors = [err for err in state.errors if err.severity in ("fatal", "error")]
            if errors:
                raise errors[0]
            if return_stats:
                return result_type(state.obj, None, state.stats)
            else:
                return state.obj

    def __sanity_check_start(self, state):
        """Check that the document seems sane by looking at the first couple characters.

        Check that the decoding seems sane.  Per RFC 4627 section 3:
            "Since the first two characters of a JSON text will
             always be ASCII characters [RFC0020], ..."
        [WAS removed from RFC 7158, but still valid via the grammar.]

        This check is probably not necessary, but it allows us to
        raise a suitably descriptive error rather than an obscure
        syntax error later on.

        Note that the RFC requirements of two ASCII characters seems
        to be an incorrect statement as a JSON string literal may have
        as it's first character any unicode character.  Thus the first
        two characters will always be ASCII, unless the first
        character is a quotation mark.  And in non-strict mode we can
        also have a few other characters too.

        """
        is_sane = True
        unitxt = state.buf.peekstr(2)
        if len(unitxt) >= 2:
            first, second = unitxt[:2]
            if first in self._string_quotes:
                pass  # second can be anything inside string literal
            else:
                if (
                    (ord(first) < 0x20 or ord(first) > 0x7F)
                    or (ord(second) < 0x20 or ord(second) > 0x7F)
                ) and (not self.isws(first) and not self.isws(second)):
                    # Found non-printable ascii, must check unicode
                    # categories to see if the character is legal.
                    # Only whitespace, line and paragraph separators,
                    # and format control chars are legal here.
                    import unicodedata

                    catfirst = unicodedata.category(str(first))
                    catsecond = unicodedata.category(str(second))
                    if catfirst not in ("Zs", "Zl", "Zp", "Cf") or catsecond not in (
                        "Zs",
                        "Zl",
                        "Zp",
                        "Cf",
                    ):
                        state.push_fatal(
                            "The input is gibberish, is the Unicode encoding correct?"
                        )
        return is_sane

    def _do_decode(self, state):
        """This is the internal function that does the JSON decoding.

        Called by the decode() method, after it has performed any Unicode decoding, etc.
        """
        buf = state.buf
        self.skipws(state)

        if buf.at_end:
            state.push_error("No value to decode")
        else:
            if state.options.decimal_context:
                dec_ctx = decimal.localcontext(state.options.decimal_context)
            else:
                dec_ctx = _dummy_context_manager

            with dec_ctx:
                state.obj = self.decodeobj(state, at_document_start=True)

            if not state.should_stop:
                # Make sure there's nothing at the end
                self.skipws(state)
                if not buf.at_end:
                    state.push_error("Unexpected text after end of JSON value")

    def _classify_for_encoding(self, obj):
        import datetime

        c = "other"
        if obj is None:
            c = "null"
        elif obj is undefined:
            c = "undefined"
        elif isinstance(obj, bool):
            c = "bool"
        elif isinstance(obj, (int, float, complex)) or (
            decimal and isinstance(obj, decimal.Decimal)
        ):
            c = "number"
        elif isinstance(obj, str) or helpers.isstringtype(obj):
            c = "string"
        else:
            if isinstance(obj, dict):
                c = "dict"
            elif (
                isinstance(obj, tuple)
                and hasattr(obj, "_asdict")
                and callable(obj._asdict)
            ):
                # Have a named tuple
                enc_nt = self.options.encode_namedtuple_as_object
                if enc_nt and (enc_nt is True or (callable(enc_nt) and enc_nt(obj))):
                    c = "namedtuple"
                else:
                    c = "sequence"
            elif isinstance(obj, (list, tuple, set, frozenset)):
                c = "sequence"
            elif hasattr(obj, "iterkeys") or (
                hasattr(obj, "__getitem__") and hasattr(obj, "keys")
            ):
                c = "dict"
            elif isinstance(obj, datetime.datetime):
                # Check datetime before date because it is a subclass!
                c = "datetime"
            elif isinstance(obj, datetime.date):
                c = "date"
            elif isinstance(obj, datetime.time):
                c = "time"
            elif isinstance(obj, datetime.timedelta):
                c = "timedelta"
            elif _py_major >= 3 and isinstance(obj, (bytes, bytearray)):
                c = "bytes"
            elif _py_major >= 3 and isinstance(obj, memoryview):
                c = "memoryview"
            elif _enum is not None and isinstance(obj, _enum):
                c = "enum"
            else:
                c = "other"
        return c

    def encode(self, obj, encoding=None):
        """Encodes the Python object into a JSON string representation.

        This method will first attempt to encode an object by seeing
        if it has a json_equivalent() method.  If so than it will
        call that method and then recursively attempt to encode
        the object resulting from that call.

        Next it will attempt to determine if the object is a native
        type or acts like a squence or dictionary.  If so it will
        encode that object directly.

        Finally, if no other strategy for encoding the object of that
        type exists, it will call the encode_default() method.  That
        method currently raises an error, but it could be overridden
        by subclasses to provide a hook for extending the types which
        can be encoded.

        """
        import sys
        import codecs

        # Make a fresh encoding state
        state = encode_state(self.options)

        # Find the codec to use. CodecInfo will be in 'cdk' and name in 'encoding'.
        #
        # Also set the state's 'escape_unicode_test' property which is used to
        # determine what characters to \u-escape.
        if encoding is None:
            cdk = None
        elif isinstance(encoding, codecs.CodecInfo):
            cdk = encoding
            encoding = cdk.name
        else:
            cdk = helpers.lookup_codec(encoding)
            if not cdk:
                raise JSONEncodeError(
                    "no codec available for character encoding", encoding
                )

        if self.options.escape_unicode and callable(self.options.escape_unicode):  # noqa: E712
            # User-supplied repertoire test function
            state.escape_unicode_test = self.options.escape_unicode
        else:
            if (
                self.options.escape_unicode is True
                or not cdk
                or cdk.name.lower() == "ascii"
            ):
                # ASCII, ISO8859-1, or and Unknown codec -- \u escape anything not ASCII
                state.escape_unicode_test = lambda c: ord(c) >= 0x80
            elif cdk.name == "iso8859-1":
                state.escape_unicode_test = lambda c: ord(c) >= 0x100
            elif cdk and cdk.name.lower().startswith("utf"):
                # All UTF-x encodings can do the whole Unicode repertoire, so
                # do nothing special.
                state.escape_unicode_test = False
            else:
                # An unusual codec.  We need to test every character
                # to see if it is in the codec's repertoire to determine
                # if we should \u escape that character.
                enc_func = cdk.encode

                def escape_unicode_hardway(c):
                    try:
                        enc_func(c)
                    except UnicodeEncodeError:
                        return True
                    else:
                        return False

                state.escape_unicode_test = escape_unicode_hardway

        # Make sure the encoding is not degenerate: it can encode the minimal
        # number of characters needed by the JSON syntax rules.
        if encoding is not None:
            try:
                output, nchars = cdk.encode(JSON.json_syntax_characters)
            except UnicodeError:
                raise JSONEncodeError(
                    "Output encoding %s is not sufficient to encode JSON" % cdk.name
                )

        # Do the JSON encoding!
        self._do_encode(obj, state)
        if not self.options.encode_compactly:
            state.append("\n")
        unitxt = state.combine()

        # Do the final Unicode encoding
        if encoding is None:
            output = unitxt
        else:
            try:
                output, nchars = cdk.encode(unitxt)
            except UnicodeEncodeError as err:
                # Re-raise as a JSONDecodeError
                e2 = sys.exc_info()
                newerr = JSONEncodeError("a Unicode encoding error occurred")
                # Simulate Python 3's: "raise X from Y" exception chaining
                newerr.__cause__ = err
                newerr.__traceback__ = e2[2]
                raise newerr
        return output

    def _do_encode(self, obj, state):
        """Internal encode function."""
        obj_classification = self._classify_for_encoding(obj)

        if self.has_hook("encode_value"):
            orig_obj = obj
            try:
                obj = self.call_hook("encode_value", obj)
            except JSONSkipHook:
                pass

            if obj is not orig_obj:
                prev_cls = obj_classification
                obj_classification = self._classify_for_encoding(obj)
                if obj_classification != prev_cls:
                    # Got a different type of object, re-encode again
                    self._do_encode(obj, state)
                    return

        if hasattr(obj, "json_equivalent"):
            success = self.encode_equivalent(obj, state)
            if success:
                return

        if obj_classification == "null":
            self.encode_null(state)
        elif obj_classification == "undefined":
            if not self.options.is_forbid_undefined_values:
                self.encode_undefined(state)
            else:
                raise JSONEncodeError('strict JSON does not permit "undefined" values')
        elif obj_classification == "bool":
            self.encode_boolean(obj, state)
        elif obj_classification == "number":
            try:
                self.encode_number(obj, state)
            except JSONEncodeError as err1:
                # Bad number, probably a complex with non-zero imaginary part.
                # Let the default encoders take a shot at encoding.
                try:
                    self.try_encode_default(obj, state)
                except Exception:
                    # Default handlers couldn't deal with it, re-raise original exception.
                    raise err1
        elif obj_classification == "string":
            self.encode_string(obj, state)
        elif obj_classification == "enum":  # Python 3.4 enum.Enum
            self.encode_enum(obj, state)
        elif obj_classification == "datetime":  # Python datetime.datetime
            self.encode_datetime(obj, state)
        elif obj_classification == "date":  # Python datetime.date
            self.encode_date(obj, state)
        elif obj_classification == "time":  # Python datetime.time
            self.encode_time(obj, state)
        elif obj_classification == "timedelta":  # Python datetime.time
            self.encode_timedelta(obj, state)
        else:
            # Anything left is probably composite, or an unconvertable type.
            self.encode_composite(obj, state)

    def encode_enum(self, val, state):
        """Encode a Python Enum value into JSON."""
        eas = self.options.encode_enum_as
        if eas == "qname":
            self.encode_string(str(val), state)
        elif eas == "value":
            self._do_encode(val.value, state)
        else:  # eas == 'name'
            self.encode_string(val.name, state)

    def encode_date(self, dt, state):
        fmt = self.options.date_format
        if not fmt or fmt == "iso":
            fmt = "%Y-%m-%d"
        self.encode_string(dt.strftime(fmt), state)

    def encode_datetime(self, dt, state):
        fmt = self.options.datetime_format
        is_iso = not fmt or fmt == "iso"
        if is_iso:
            if dt.microsecond == 0:
                fmt = "%Y-%m-%dT%H:%M:%S%z"
            else:
                fmt = "%Y-%m-%dT%H:%M:%S.%f%z"
        s = dt.strftime(fmt)
        if is_iso and s.endswith("-00:00") or s.endswith("+00:00"):
            s = s[:-6] + "Z"  # Change UTC to use 'Z' notation
        self.encode_string(s, state)

    def encode_time(self, dt, state):
        fmt = self.options.datetime_format
        is_iso = not fmt or fmt == "iso"
        if is_iso:
            if dt.microsecond == 0:
                fmt = "T%H:%M:%S%z"
            else:
                fmt = "T%H:%M:%S.%f%z"
        s = dt.strftime(fmt)
        if is_iso and s.endswith("-00:00") or s.endswith("+00:00"):
            s = s[:-6] + "Z"  # Change UTC to use 'Z' notation
        self.encode_string(s, state)

    def encode_timedelta(self, td, state):
        fmt = self.options.timedelta_format
        if not fmt or fmt == "iso":
            s = helpers.format_timedelta_iso(td)
        elif fmt == "hms":
            s = str(td)
        else:
            raise ValueError("Unknown timedelta_format %r" % fmt)
        self.encode_string(s, state)

    def encode_composite(self, obj, state, obj_classification=None):
        """Encodes just composite objects: dictionaries, lists, or sequences.

        Basically handles any python type for which iter() can create
        an iterator object.

        This method is not intended to be called directly.  Use the
        encode() method instead.

        """
        if not obj_classification:
            obj_classification = self._classify_for_encoding(obj)

        # Convert namedtuples to dictionaries
        if obj_classification == "namedtuple":
            obj = obj._asdict()
            obj_classification = "dict"

        # Convert 'unsigned byte' memory views into plain bytes
        if obj_classification == "memoryview" and obj.format == "B":
            obj = obj.tobytes()
            obj_classification = "bytes"

        # Run hooks
        hook_name = None
        if obj_classification == "dict":
            hook_name = "encode_dict"
        elif obj_classification == "sequence":
            hook_name = "encode_sequence"
        elif obj_classification == "bytes":
            hook_name = "encode_bytes"

        if self.has_hook(hook_name):
            try:
                new_obj = self.call_hook(hook_name, obj)
            except JSONSkipHook:
                pass
            else:
                if new_obj is not obj:
                    obj = new_obj
                    prev_cls = obj_classification
                    obj_classification = self._classify_for_encoding(obj)
                    if obj_classification != prev_cls:
                        # Transformed to a different kind of object, call
                        # back to the general encode() method.
                        self._do_encode(obj, state)
                        return
                    # Else, fall through

        # At his point we have decided to do with an object or an array
        isdict = obj_classification == "dict"

        # Get iterator
        it = None
        if isdict and hasattr(obj, "iterkeys"):
            try:
                it = iter(obj.keys())
            except AttributeError:
                pass
        else:
            try:
                it = iter(obj)
            except TypeError:
                pass

        # Convert each member to JSON
        if it is not None:
            # Try to get length, but don't fail if we can't
            try:
                numitems = len(obj)
            except TypeError:
                numitems = 0

            # Output the opening bracket or brace
            compactly = self.options.encode_compactly
            if not compactly:
                indent0 = self.options.indentation_for_level(state.nest_level)
                indent = self.options.indentation_for_level(state.nest_level + 1)

            spaces_after_opener = ""
            if isdict:
                opener = "{"
                closer = "}"
                if compactly:
                    dictcolon = ":"
                else:
                    dictcolon = " : "
            else:
                opener = "["
                closer = "]"
            if not compactly:
                # opener = opener + ' '
                spaces_after_opener = self.options.spaces_to_next_indent_level(
                    subtract=len(opener)
                )

            state.append(opener)
            state.append(spaces_after_opener)

            # Now iterate through all the items and collect their representations
            parts = []  # Collects each of the members
            part_keys = []  # For dictionary key sorting, tuples (key,index)

            try:  # while not StopIteration
                part_idx = 0
                while True:
                    obj2 = next(it)
                    part_idx += 1  # Note, will start counting at 1
                    if obj2 is obj:
                        raise JSONEncodeError(
                            "trying to encode an infinite sequence", obj
                        )
                    if isdict:
                        obj3 = obj[obj2]
                        # Dictionary key is in obj2 and value in obj3.

                        # Let any hooks transform the key.
                        if self.has_hook("encode_value"):
                            try:
                                newobj = self.call_hook("encode_value", obj2)
                            except JSONSkipHook:
                                pass
                            else:
                                obj2 = newobj
                        if self.has_hook("encode_dict_key"):
                            try:
                                newkey = self.call_hook("encode_dict_key", obj2)
                            except JSONSkipHook:
                                pass
                            else:
                                obj2 = newkey

                        # Check JSON restrictions on key types
                        if not helpers.isstringtype(obj2):
                            if helpers.isnumbertype(obj2):
                                if not self.options.is_allow_nonstring_keys:
                                    raise JSONEncodeError(
                                        "object properties (dictionary keys) must be strings in strict JSON",
                                        obj2,
                                    )
                            else:
                                raise JSONEncodeError(
                                    "object properties (dictionary keys) can only be strings or numbers in ECMAScript",
                                    obj2,
                                )
                        part_keys.append((obj2, part_idx - 1))

                    # Encode this item in the sequence and put into item_chunks
                    substate = state.make_substate()
                    self._do_encode(obj2, substate)
                    if isdict:
                        substate.append(dictcolon)
                        substate2 = substate.make_substate()
                        self._do_encode(obj3, substate2)
                        substate.join_substate(substate2)
                    parts.append(substate)
                # Next item iteration
            except StopIteration:
                pass

            # Sort dictionary keys
            if isdict:
                srt = self.options.sort_keys
                if srt == SORT_PRESERVE:
                    if _OrderedDict and isinstance(obj, _OrderedDict):
                        srt = SORT_NONE  # Will keep order
                    else:
                        srt = SORT_SMART

                if not srt or srt in (SORT_NONE, SORT_PRESERVE):
                    srt = None
                elif callable(srt):
                    part_keys.sort(key=(lambda t: (srt(t[0]), t[0])))
                elif srt == SORT_SMART:
                    part_keys.sort(key=(lambda t: (smart_sort_transform(t[0]), t[0])))
                elif srt == SORT_ALPHA_CI:
                    part_keys.sort(key=(lambda t: (str(t[0]).upper(), t[0])))
                elif srt or srt == SORT_ALPHA:
                    part_keys.sort(key=(lambda t: str(t[0])))
                # Now make parts match the new sort order
                if srt is not None:
                    parts = [parts[pk[1]] for pk in part_keys]

            if compactly:
                sep = ","
            elif len(parts) <= self.options.max_items_per_line:
                sep = ", "
            else:
                # state.append(spaces_after_opener)
                state.append("\n" + indent)
                sep = ",\n" + indent

            for pnum, substate in enumerate(parts):
                if pnum > 0:
                    state.append(sep)
                state.join_substate(substate)

            if not compactly:
                if numitems > self.options.max_items_per_line:
                    state.append("\n" + indent0)
                else:
                    state.append(" ")
            state.append(closer)  # final '}' or ']'
        else:  # Can't create an iterator for the object
            self.try_encode_default(obj, state)

    def encode_equivalent(self, obj, state):
        """This method is used to encode user-defined class objects.

        The object being encoded should have a json_equivalent()
        method defined which returns another equivalent object which
        is easily JSON-encoded.  If the object in question has no
        json_equivalent() method available then None is returned
        instead of a string so that the encoding will attempt the next
        strategy.

        If a caller wishes to disable the calling of json_equivalent()
        methods, then subclass this class and override this method
        to just return None.

        """
        if hasattr(obj, "json_equivalent") and callable(
            getattr(obj, "json_equivalent")
        ):
            obj2 = obj.json_equivalent()
            if obj2 is obj:
                # Try to prevent careless infinite recursion
                raise JSONEncodeError(
                    "object has a json_equivalent() method that returns itself", obj
                )
            self._do_encode(obj2, state)
            return True
        else:
            return False

    def try_encode_default(self, obj, state):
        orig_obj = obj
        if self.has_hook("encode_default"):
            try:
                obj = self.call_hook("encode_default", obj)
            except JSONSkipHook:
                pass
            else:
                if obj is not orig_obj:
                    # Hook made a transformation, re-encode it
                    return self._do_encode(obj, state)

        # End of the road.
        raise JSONEncodeError("can not encode object into a JSON representation", obj)


# ------------------------------


def encode(obj, encoding=None, **kwargs):
    r"""Encodes a Python object into a JSON-encoded string.

    * 'strict'    (Boolean, default False)

        If 'strict' is set to True, then only strictly-conforming JSON
        output will be produced.  Note that this means that some types
        of values may not be convertable and will result in a
        JSONEncodeError exception.

    * 'compactly'    (Boolean, default True)

        If 'compactly' is set to True, then the resulting string will
        have all extraneous white space removed; if False then the
        string will be "pretty printed" with whitespace and
        indentation added to make it more readable.

    * 'encode_namedtuple_as_object'  (Boolean or callable, default True)

        If True, then objects of type namedtuple, or subclasses of
        'tuple' that have an _asdict() method, will be encoded as an
        object rather than an array.
        If can also be a predicate function that takes a namedtuple
        object as an argument and returns True or False.

    * 'indent_amount'   (Integer, default 2)

        The number of spaces to output for each indentation level.
        If 'compactly' is True then indentation is ignored.

    * 'indent_limit'    (Integer or None, default None)

        If not None, then this is the maximum limit of indentation
        levels, after which further indentation spaces are not
        inserted.  If None, then there is no limit.

    CONCERNING CHARACTER ENCODING:

    The 'encoding' argument should be one of:

        * None - The return will be a Unicode string.
        * encoding_name - A string which is the name of a known
              encoding, such as 'UTF-8' or 'ascii'.
        * codec - A CodecInfo object, such as as found by codecs.lookup().
              This allows you to use a custom codec as well as those
              built into Python.

    If an encoding is given (either by name or by codec), then the
    returned value will be a byte array (Python 3), or a 'str' string
    (Python 2); which represents the raw set of bytes.  Otherwise,
    if encoding is None, then the returned value will be a Unicode
    string.

    The 'escape_unicode' argument is used to determine which characters
    in string literals must be \u escaped.  Should be one of:

        * True  -- All non-ASCII characters are always \u escaped.
        * False -- Try to insert actual Unicode characters if possible.
        * function -- A user-supplied function that accepts a single
             unicode character and returns True or False; where True
             means to \u escape that character.

    Regardless of escape_unicode, certain characters will always be
    \u escaped. Additionaly any characters not in the output encoding
    repertoire for the encoding codec will be \u escaped as well.

    """
    # Do the JSON encoding
    j = JSON(**kwargs)
    output = j.encode(obj, encoding)
    return output


def decode(txt, encoding=None, **kwargs):
    """Decodes a JSON-encoded string into a Python object.

    == Optional arguments ==

    * 'encoding'  (string, default None)

       This argument provides a hint regarding the character encoding
       that the input text is assumed to be in (if it is not already a
       unicode string type).

       If set to None then autodetection of the encoding is attempted
       (see discussion above). Otherwise this argument should be the
       name of a registered codec (see the standard 'codecs' module).

    * 'strict'    (Boolean, default False)

        If 'strict' is set to True, then those strings that are not
        entirely strictly conforming to JSON will result in a
        JSONDecodeError exception.

    * 'return_errors'    (Boolean, default False)

        Controls the return value from this function. If False, then
        only the Python equivalent object is returned on success, or
        an error will be raised as an exception.

        If True then a 2-tuple is returned: (object, error_list). The
        error_list will be an empty list [] if the decoding was
        successful, otherwise it will be a list of all the errors
        encountered.  Note that it is possible for an object to be
        returned even if errors were encountered.

    * 'return_stats'    (Boolean, default False)

        Controls whether statistics about the decoded JSON document
        are returns (and instance of decode_statistics).

        If True, then the stats object will be added to the end of the
        tuple returned.  If return_errors is also set then a 3-tuple
        is returned, otherwise a 2-tuple is returned.

    * 'write_errors'    (Boolean OR File-like object, default False)

        Controls what to do with errors.

        - If False, then the first decoding error is raised as an exception.
        - If True, then errors will be printed out to sys.stderr.
        - If a File-like object, then errors will be printed to that file.

        The write_errors and return_errors arguments can be set
        independently.

    * 'filename_for_errors'   (string or None)

        Provides a filename to be used when writting error messages.

    * 'allow_xxx', 'warn_xxx', and 'forbid_xxx'    (Booleans)

        These arguments allow for fine-adjustments to be made to the
        'strict' argument, by allowing or forbidding specific
        syntaxes.

        There are many of these arguments, named by replacing the
        "xxx" with any number of possible behavior names (See the JSON
        class for more details).

        Each of these will allow (or forbid) the specific behavior,
        after the evaluation of the 'strict' argument.  For example,
        if strict=True then by also passing 'allow_comments=True' then
        comments will be allowed.  If strict=False then
        forbid_comments=True will allow everything except comments.

    Unicode decoding:
    -----------------
    The input string can be either a python string or a python unicode
    string (or a byte array in Python 3).  If it is already a unicode
    string, then it is assumed that no character set decoding is
    required.

    However, if you pass in a non-Unicode text string (a Python 2
    'str' type or a Python 3 'bytes' or 'bytearray') then an attempt
    will be made to auto-detect and decode the character encoding.
    This will be successful if the input was encoded in any of UTF-8,
    UTF-16 (BE or LE), or UTF-32 (BE or LE), and of course plain ASCII
    works too.

    Note though that if you know the character encoding, then you
    should convert to a unicode string yourself, or pass it the name
    of the 'encoding' to avoid the guessing made by the auto
    detection, as with

        python_object = demjson.decode( input_bytes, encoding='utf8' )

    Callback hooks:
    ---------------
    You may supply callback hooks by using the hook name as the
    named argument, such as:
        decode_float=decimal.Decimal

    See the hooks documentation on the JSON.set_hook() method.

    """
    import sys

    # Initialize the JSON object
    return_errors = False
    return_stats = False
    write_errors = False
    filename_for_errors = None
    write_stats = False

    kwargs = kwargs.copy()

    todel = []
    for kw, val in list(kwargs.items()):
        if kw == "return_errors":
            return_errors = bool(val)
            todel.append(kw)
        elif kw == "return_stats":
            return_stats = bool(val)
            todel.append(kw)
        elif kw == "write_errors":
            write_errors = val
            todel.append(kw)
        elif kw == "filename_for_errors":
            filename_for_errors = val
            todel.append(kw)
        elif kw == "write_stats":
            write_stats = val
            todel.append(kw)
    # next keyword argument
    for kw in todel:
        del kwargs[kw]

    j = JSON(**kwargs)

    # Now do the actual JSON decoding
    result = j.decode(
        txt,
        encoding=encoding,
        return_errors=(return_errors or write_errors),
        return_stats=(return_stats or write_stats),
    )

    if write_errors:
        import sys

        if write_errors is True:
            write_errors = sys.stderr
        for err in result.errors:
            write_errors.write(
                err.pretty_description(filename=filename_for_errors) + "\n"
            )

    if write_stats:
        import sys

        if write_stats is True:
            write_stats = sys.stderr
        if result.stats:
            write_stats.write("%s----- Begin JSON statistics\n" % filename_for_errors)
            write_stats.write(result.stats.pretty_description(prefix="   | "))
            write_stats.write("%s----- End of JSON statistics\n" % filename_for_errors)
    return result


def encode_to_file(filename, obj, encoding="utf-8", overwrite=False, **kwargs):
    """Encodes a Python object into JSON and writes into the given file.

    If no encoding is given, then UTF-8 will be used.

    See the encode() function for a description of other possible options.

    If the file already exists and the 'overwrite' option is not set
    to True, then the existing file will not be overwritten.  (Note,
    there is a subtle race condition in the check so there are
    possible conditions in which a file may be overwritten)

    """
    import os
    import errno

    if not encoding:
        encoding = "utf-8"

    if not isinstance(filename, str) or not filename:
        raise TypeError("Expected a file name")

    if not overwrite and os.path.exists(filename):
        raise IOError(errno.EEXIST, "File exists: %r" % filename)

    jsondata = encode(obj, encoding=encoding, **kwargs)

    try:
        fp = open(filename, "wb")
    except Exception:
        raise
    else:
        try:
            fp.write(jsondata)
        finally:
            fp.close()


def decode_file(filename, encoding=None, **kwargs):
    """Decodes JSON found in the given file.

    See the decode() function for a description of other possible options.

    """
    if isinstance(filename, str):
        try:
            fp = open(filename, "rb")
        except Exception:
            raise
        else:
            try:
                jsondata = fp.read()
            finally:
                fp.close()
    else:
        raise TypeError("Expected a file name")
    return decode(jsondata, encoding=encoding, **kwargs)


# ======================================================================


class jsonlint(object):
    """This class contains most of the logic for the "jsonlint" command.

    You generally create an instance of this class, to defined the
    program's environment, and then call the main() method.  A simple
    wrapper to turn this into a script might be:

        import sys, demjson
        if __name__ == '__main__':
            lint = demjson.jsonlint( sys.argv[0] )
            return lint.main( sys.argv[1:] )

    """

    _jsonlint_usage = r"""Usage: %(program_name)s [<options> ...] [--] inputfile.json ...

With no input filename, or "-", it will read from standard input.

The return status will be 0 if the file is conforming JSON (per the
RFC 7159 specification), or non-zero otherwise.

GENERAL OPTIONS:

 -v | --verbose    Show details of lint checking
 -q | --quiet      Don't show any output (except for reformatting)

STRICTNESS OPTIONS (WARNINGS AND ERRORS):

 -W | --tolerant   Be tolerant, but warn about non-conformance (default)
 -s | --strict     Be strict in what is considered conforming JSON
 -S | --nonstrict  Be tolerant in what is considered conforming JSON

 --allow=...      -\
 --warn=...         |-- These options let you pick specific behaviors.
 --forbid=...     -/      Use --help-behaviors for more

STATISTICS OPTIONS:

 --stats       Show statistics about JSON document

REFORMATTING OPTIONS:

 -f | --format     Reformat the JSON text (if conforming) to stdout
 -F | --format-compactly
        Reformat the JSON simlar to -f, but do so compactly by
        removing all unnecessary whitespace

 -o filename | --output filename
        The filename to which reformatted JSON is to be written.
        Without this option the standard output is used.

 --[no-]keep-format   Try to preserve numeric radix, e.g., hex, octal, etc.
 --html-safe          Escape characters that are not safe to embed in HTML/XML.

 --sort <kind>     How to sort object/dictionary keys, <kind> is one of:
%(sort_options_help)s

 --indent tabs | <nnn>   Number of spaces to use per indentation level,
                         or use tab characters if "tabs" given.

UNICODE OPTIONS:

 -e codec | --encoding=codec     Set both input and output encodings
 --input-encoding=codec          Set the input encoding
 --output-encoding=codec         Set the output encoding

    These options set the character encoding codec (e.g., "ascii",
    "utf-8", "utf-16").  The -e will set both the input and output
    encodings to the same thing.  The output encoding is used when
    reformatting with the -f or -F options.

    Unless set, the input encoding is guessed and the output
    encoding will be "utf-8".

OTHER OPTIONS:

 --recursion-limit=nnn     Set the Python recursion limit to number
 --leading-zero-radix=8|10 The radix to use for numbers with leading
                           zeros. 8=octal, 10=decimal.

REFORMATTING / PRETTY-PRINTING:

    When reformatting JSON with -f or -F, output is only produced if
    the input passed validation.  By default the reformatted JSON will
    be written to standard output, unless the -o option was given.

    The default output codec is UTF-8, unless an encoding option is
    provided.  Any Unicode characters will be output as literal
    characters if the encoding permits, otherwise they will be
    \u-escaped.  You can use "--output-encoding ascii" to force all
    Unicode characters to be escaped.

MORE INFORMATION:

    Use '%(program_name)s --version [-v]' to see versioning information.
    Use '%(program_name)s --copyright' to see author and copyright details.
    Use '%(program_name)s [-W|-s|-S] --help-behaviors' for help on specific checks.

    %(program_name)s is distributed as part of the "demjson" Python module.
    See %(homepage)s
"""
    SUCCESS_FAIL = "E"
    SUCCESS_WARNING = "W"
    SUCCESS_OK = "OK"

    def __init__(self, program_name="jsonlint", stdin=None, stdout=None, stderr=None):
        """Create an instance of a "jsonlint" program.

        You can optionally pass options to define the program's environment:

          * program_name  - the name of the program, usually sys.argv[0]
          * stdin   - the file object to use for input, default sys.stdin
          * stdout  - the file object to use for output, default sys.stdout
          * stderr  - the file object to use for error output, default sys.stderr

        After creating an instance, you typically call the main() method.

        """
        import os
        import sys

        self.program_path = program_name
        self.program_name = os.path.basename(program_name)
        if stdin:
            self.stdin = stdin
        else:
            self.stdin = sys.stdin

        if stdout:
            self.stdout = stdout
        else:
            self.stdout = sys.stdout

        if stderr:
            self.stderr = stderr
        else:
            self.stderr = sys.stderr

    @property
    def usage(self):
        """A multi-line string containing the program usage instructions."""
        sorthelp = "\n".join(
            [
                "          %12s - %s" % (sm, sd)
                for sm, sd in sorted(sorting_methods.items())
                if sm != SORT_NONE
            ]
        )
        return self._jsonlint_usage % {
            "program_name": self.program_name,
            "homepage": __homepage__,
            "sort_options_help": sorthelp,
        }

    def _lintcheck_data(
        self,
        jsondata,
        verbose_fp=None,
        reformat=False,
        show_stats=False,
        input_encoding=None,
        output_encoding=None,
        escape_unicode=True,
        pfx="",
        jsonopts=None,
    ):
        global decode, encode  # noqa: F824
        success = self.SUCCESS_FAIL
        reformatted = None
        if show_stats:
            stats_fp = verbose_fp
        else:
            stats_fp = None
        try:
            results = decode(
                jsondata,
                encoding=input_encoding,
                return_errors=True,
                return_stats=True,
                write_errors=verbose_fp,
                write_stats=stats_fp,
                filename_for_errors=pfx,
                json_options=jsonopts,
            )
        except JSONError as err:
            success = self.SUCCESS_FAIL
            if verbose_fp:
                verbose_fp.write("%s%s\n" % (pfx, err.pretty_description()))
        except Exception as err:
            success = self.SUCCESS_FAIL
            if verbose_fp:
                verbose_fp.write("%s%s\n" % (pfx, str(err)))
        else:
            errors = [
                err for err in results.errors if err.severity in ("fatal", "error")
            ]
            warnings = [err for err in results.errors if err.severity in ("warning",)]
            if errors:
                success = self.SUCCESS_FAIL
            elif warnings:
                success = self.SUCCESS_WARNING
            else:
                success = self.SUCCESS_OK

            if reformat:
                encopts = jsonopts.copy()
                encopts.strictness = STRICTNESS_TOLERANT
                if reformat == "compactly":
                    encopts.encode_compactly = True
                else:
                    encopts.encode_compactly = False

                reformatted = encode(
                    results.object, encoding=output_encoding, json_options=encopts
                )

        return (success, reformatted)

    def _lintcheck(
        self,
        filename,
        output_filename,
        verbose=False,
        reformat=False,
        show_stats=False,
        input_encoding=None,
        output_encoding=None,
        escape_unicode=True,
        jsonopts=None,
    ):
        import sys

        verbose_fp = None

        if not filename or filename == "-":
            pfx = "<stdin>: "
            jsondata = self.stdin.read()
            if verbose:
                verbose_fp = self.stderr
        else:
            pfx = "%s: " % filename
            try:
                fp = open(filename, "rb")
                jsondata = fp.read()
                fp.close()
            except IOError as err:
                self.stderr.write("%s: %s\n" % (pfx, str(err)))
                return self.SUCCESS_FAIL
            if verbose:
                verbose_fp = self.stdout

        success, reformatted = self._lintcheck_data(
            jsondata,
            verbose_fp=verbose_fp,
            reformat=reformat,
            show_stats=show_stats,
            input_encoding=input_encoding,
            output_encoding=output_encoding,
            pfx=pfx,
            jsonopts=jsonopts,
        )

        if success != self.SUCCESS_FAIL and reformat:
            if output_filename:
                try:
                    fp = open(output_filename, "wb")
                    fp.write(reformatted)
                except IOError as err:
                    self.stderr.write("%s: %s\n" % (pfx, str(err)))
                    success = False
            else:
                if hasattr(
                    sys.stdout, "buffer"
                ):  # To write binary data rather than strings
                    self.stdout.buffer.write(reformatted)
                else:
                    self.stdout.write(reformatted)
        elif success == self.SUCCESS_OK and verbose_fp:
            verbose_fp.write("%sok\n" % pfx)
        elif success == self.SUCCESS_WARNING and verbose_fp:
            verbose_fp.write("%sok, with warnings\n" % pfx)
        elif verbose_fp:
            verbose_fp.write("%shas errors\n" % pfx)

        return success

    def main(self, argv):
        """The main routine for program "jsonlint".

        Should be called with sys.argv[1:] as its sole argument.

        Note sys.argv[0] which normally contains the program name
        should not be passed to main(); instead this class itself
        is initialized with sys.argv[0].

        Use "--help" for usage syntax, or consult the 'usage' member.

        """
        import sys
        import getopt
        import unicodedata

        recursion_limit = None
        success = True
        verbose = "auto"  # one of 'auto', True, or False
        reformat = False
        show_stats = False
        output_filename = None
        input_encoding = None
        output_encoding = "utf-8"

        kwoptions = {  # Will be used to initialize json_options
            "sort_keys": SORT_SMART,
            "strict": STRICTNESS_WARN,
            "keep_format": True,
            "decimal_context": 100,
        }

        try:
            opts, args = getopt.getopt(
                argv,
                "vqfFe:o:sSW",
                [
                    "verbose",
                    "quiet",
                    "format",
                    "format-compactly",
                    "stats",
                    "output",
                    "strict",
                    "nonstrict",
                    "warn",
                    "html-safe",
                    "xml-safe",
                    "encoding=",
                    "input-encoding=",
                    "output-encoding=",
                    "sort=",
                    "recursion-limit=",
                    "leading-zero-radix=",
                    "keep-format",
                    "no-keep-format",
                    "indent=",
                    "indent-amount=",
                    "indent-limit=",
                    "indent-tab-width=",
                    "max-items-per-line=",
                    "allow=",
                    "warn=",
                    "forbid=",
                    "deny=",
                    "help",
                    "help-behaviors",
                    "version",
                    "copyright",
                ],
            )
        except getopt.GetoptError as err:
            self.stderr.write(
                'Error: %s.  Use "%s --help" for usage information.\n'
                % (err.msg, self.program_name)
            )
            return 1

        # Set verbose before looking at any other options
        for opt, val in opts:
            if opt in ("-v", "--verbose"):
                verbose = True

        # Process all options
        for opt, val in opts:
            if opt in ("-h", "--help"):
                self.stdout.write(self.usage)
                return 0
            elif opt == "--help-behaviors":
                self.stdout.write(
                    """
BEHAVIOR OPTIONS:

These set of options let you control which checks are to be performed.
They may be turned on or off by listing them as arguments to one of
the options --allow, --warn, or --forbid ; for example:

    %(program_name)s --allow comments,hex-numbers --forbid duplicate-keys

"""
                    % {"program_name": self.program_name}
                )
                self.stdout.write(
                    "The default shown is for %s mode\n\n" % kwoptions["strict"]
                )
                self.stdout.write(
                    "%-7s %-25s %s\n" % ("Default", "Behavior_name", "Description")
                )
                self.stdout.write("-" * 7 + " " + "-" * 25 + " " + "-" * 50 + "\n")
                j = json_options(**kwoptions)
                for behavior in sorted(j.all_behaviors):
                    v = j.get_behavior(behavior)
                    desc = j.describe_behavior(behavior)
                    self.stdout.write(
                        "%-7s %-25s %s\n"
                        % (v.lower(), behavior.replace("_", "-"), desc)
                    )
                return 0
            elif opt == "--version":
                self.stdout.write(
                    "%s (%s) version %s (%s)\n"
                    % (self.program_name, __name__, __version__, __date__)
                )
                if verbose is True:
                    self.stdout.write("demjson from %r\n" % (__file__,))
                if verbose is True:
                    self.stdout.write(
                        "Python version: %s\n" % (sys.version.replace("\n", " "),)
                    )
                    self.stdout.write("This python implementation supports:\n")
                    self.stdout.write("  * Max unicode: U+%X\n" % (sys.maxunicode,))
                    self.stdout.write(
                        "  * Unicode version: %s\n" % (unicodedata.unidata_version,)
                    )
                    self.stdout.write(
                        "  * Floating-point significant digits: %d\n"
                        % (float_sigdigits,)
                    )
                    self.stdout.write(
                        "  * Floating-point max 10^exponent: %d\n" % (float_maxexp,)
                    )
                    if str(0.0) == str(-0.0):
                        szero = "No"
                    else:
                        szero = "Yes"
                    self.stdout.write(
                        "  * Floating-point has signed-zeros: %s\n" % (szero,)
                    )
                    if decimal:
                        has_dec = "Yes"
                    else:
                        has_dec = "No"
                    self.stdout.write(
                        "  * Decimal (bigfloat) support: %s\n" % (has_dec,)
                    )
                return 0
            elif opt == "--copyright":
                self.stdout.write(
                    '%s is distributed as part of the "demjson" python package.\n'
                    % (self.program_name,)
                )
                self.stdout.write("See %s\n\n\n" % (__homepage__,))
                self.stdout.write(__credits__)
                return 0
            elif opt in ("-v", "--verbose"):
                verbose = True
            elif opt in ("-q", "--quiet"):
                verbose = False
            elif opt in ("-s", "--strict"):
                kwoptions["strict"] = STRICTNESS_STRICT
                kwoptions["keep_format"] = False
            elif opt in ("-S", "--nonstrict"):
                kwoptions["strict"] = STRICTNESS_TOLERANT
            elif opt in ("-W", "--tolerant"):
                kwoptions["strict"] = STRICTNESS_WARN
            elif opt in ("-f", "--format"):
                reformat = True
                kwoptions["encode_compactly"] = False
            elif opt in ("-F", "--format-compactly"):
                kwoptions["encode_compactly"] = True
                reformat = "compactly"
            elif opt in ("--stats",):
                show_stats = True
            elif opt in ("-o", "--output"):
                output_filename = val
            elif opt in ("-e", "--encoding"):
                input_encoding = val
                output_encoding = val
                escape_unicode = False  # noqa: F841
            elif opt in ("--output-encoding"):
                output_encoding = val
                escape_unicode = False  # noqa: F841
            elif opt in ("--input-encoding"):
                input_encoding = val
            elif opt in ("--html-safe", "--xml-safe"):
                kwoptions["html_safe"] = True
            elif opt in ("--allow", "--warn", "--forbid"):
                action = opt[2:]
                if action in kwoptions:
                    kwoptions[action] += "," + val
                else:
                    kwoptions[action] = val
            elif opt in ("--keep-format",):
                kwoptions["keep_format"] = True
            elif opt in ("--no-keep-format",):
                kwoptions["keep_format"] = False
            elif opt == "--leading-zero-radix":
                kwoptions["leading_zero_radix"] = val
            elif opt in ("--indent", "--indent-amount"):
                if val in ("tab", "tabs"):
                    kwoptions["indent_amount"] = 8
                    kwoptions["indent_tab_width"] = 8
                else:
                    try:
                        kwoptions["indent_amount"] = int(val)
                    except ValueError:
                        self.stderr.write("Indentation amount must be a number\n")
                        return 1
            elif opt == "indent-tab-width":
                try:
                    kwoptions["indent_tab_width"] = int(val)
                except ValueError:
                    self.stderr.write("Indentation tab width must be a number\n")
                    return 1
            elif opt == "--max-items-per-line":
                try:
                    kwoptions["max_items_per_line"] = int(val)
                except ValueError:
                    self.stderr.write("Max items per line must be a number\n")
                    return 1
            elif opt == "--sort":
                val = val.lower()
                if val == "alpha":
                    kwoptions["sort_keys"] = SORT_ALPHA
                elif val == "alpha_ci":
                    kwoptions["sort_keys"] = SORT_ALPHA_CI
                elif val == "preserve":
                    kwoptions["sort_keys"] = SORT_PRESERVE
                else:
                    kwoptions["sort_keys"] = SORT_SMART
            elif opt == "--recursion-limit":
                try:
                    recursion_limit = int(val)
                except ValueError:
                    self.stderr.write("Recursion limit must be a number: %r\n" % val)
                    return 1
                else:
                    max_limit = 100000
                    old_limit = sys.getrecursionlimit()
                    if recursion_limit > max_limit:
                        self.stderr.write(
                            "Recursion limit must be a number between %d and %d\n"
                            % (old_limit, max_limit)
                        )
                        return 1
                    elif recursion_limit > old_limit:
                        sys.setrecursionlimit(recursion_limit)
            else:
                self.stderr.write("Unknown option %r\n" % opt)
                return 1

        # Make the JSON options
        kwoptions["decimal_context"] = 100
        jsonopts = json_options(**kwoptions)

        # Now decode each file...
        if not args:
            args = [None]

        for fn in args:
            try:
                rc = self._lintcheck(
                    fn,
                    output_filename=output_filename,
                    verbose=verbose,
                    reformat=reformat,
                    show_stats=show_stats,
                    input_encoding=input_encoding,
                    output_encoding=output_encoding,
                    jsonopts=jsonopts,
                )
                if rc != self.SUCCESS_OK:
                    # Warnings or errors should result in failure.  If
                    # checking multiple files, do not change a
                    # previous error back to ok.
                    success = False
            except KeyboardInterrupt:
                sys.stderr.write("\njsonlint interrupted!\n")
                sys.exit(1)

        if not success:
            return 1
        return 0


# end file
