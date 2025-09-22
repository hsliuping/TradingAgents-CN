function Base64() {
  _keyStr = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=", this.encode = function(a) {
    var c, d, e, f, g, h, i, b = "",
        j = 0;
    for (a = _utf8_encode(a); j < a.length;) c = a.charCodeAt(j++), d = a.charCodeAt(j++), e = a.charCodeAt(j++), f = c >> 2, g = (3 & c) << 4 | d >> 4, h = (15 & d) << 2 | e >> 6, i = 63 & e, isNaN(d) ? h = i = 64 : isNaN(e) && (i = 64), b = b + _keyStr.charAt(f) + _keyStr.charAt(g) + _keyStr.charAt(h) + _keyStr.charAt(i);
    return b
  }, this.decode = function(a) {
    var c, d, e, f, g, h, i, b = "",
        j = 0;
    for (a = a.replace(/[^A-Za-z0-9\+\/\=]/g, ""); j < a.length;) f = _keyStr.indexOf(a.charAt(j++)), g = _keyStr.indexOf(a.charAt(j++)), h = _keyStr.indexOf(a.charAt(j++)), i = _keyStr.indexOf(a.charAt(j++)), c = f << 2 | g >> 4, d = (15 & g) << 4 | h >> 2, e = (3 & h) << 6 | i, b += String.fromCharCode(c), 64 != h && (b += String.fromCharCode(d)), 64 != i && (b += String.fromCharCode(e));
    return b = _utf8_decode(b)
  }, _utf8_encode = function(a) {
    var b, c, d;
    for (a = a.replace(/\r\n/g, "\n"), b = "", c = 0; c < a.length; c++) d = a.charCodeAt(c), 128 > d ? b += String.fromCharCode(d) : d > 127 && 2048 > d ? (b += String.fromCharCode(192 | d >> 6), b += String.fromCharCode(128 | 63 & d)) : (b += String.fromCharCode(224 | d >> 12), b += String.fromCharCode(128 | 63 & d >> 6), b += String.fromCharCode(128 | 63 & d));
    return b
  }, _utf8_decode = function(a) {
    for (var b = "", c = 0, d = c1 = c2 = 0; c < a.length;) d = a.charCodeAt(c), 128 > d ? (b += String.fromCharCode(d), c++) : d > 191 && 224 > d ? (c2 = a.charCodeAt(c + 1), b += String.fromCharCode((31 & d) << 6 | 63 & c2), c += 2) : (c2 = a.charCodeAt(c + 1), c3 = a.charCodeAt(c + 2), b += String.fromCharCode((15 & d) << 12 | (63 & c2) << 6 | 63 & c3), c += 3);
    return b
  }
}

function hex_md5(a) {
  return binl2hex(core_md5(str2binl(a), a.length * chrsz))
}

function b64_md5(a) {
  return binl2b64(core_md5(str2binl(a), a.length * chrsz))
}

function str_md5(a) {
  return binl2str(core_md5(str2binl(a), a.length * chrsz))
}

function hex_hmac_md5(a, b) {
  return binl2hex(core_hmac_md5(a, b))
}

function b64_hmac_md5(a, b) {
  return binl2b64(core_hmac_md5(a, b))
}

function str_hmac_md5(a, b) {
  return binl2str(core_hmac_md5(a, b))
}

function md5_vm_test() {
  return "900150983cd24fb0d6963f7d28e17f72" == hex_md5("abc")
}

function core_md5(a, b) {
  var c, d, e, f, g, h, i, j, k;
  for (a[b >> 5] |= 128 << b % 32, a[(b + 64 >>> 9 << 4) + 14] = b, c = 1732584193, d = -271733879, e = -1732584194, f = 271733878, g = 0; g < a.length; g += 16) h = c, i = d, j = e, k = f, c = md5_ff(c, d, e, f, a[g + 0], 7, -680876936), f = md5_ff(f, c, d, e, a[g + 1], 12, -389564586), e = md5_ff(e, f, c, d, a[g + 2], 17, 606105819), d = md5_ff(d, e, f, c, a[g + 3], 22, -1044525330), c = md5_ff(c, d, e, f, a[g + 4], 7, -176418897), f = md5_ff(f, c, d, e, a[g + 5], 12, 1200080426), e = md5_ff(e, f, c, d, a[g + 6], 17, -1473231341), d = md5_ff(d, e, f, c, a[g + 7], 22, -45705983), c = md5_ff(c, d, e, f, a[g + 8], 7, 1770035416), f = md5_ff(f, c, d, e, a[g + 9], 12, -1958414417), e = md5_ff(e, f, c, d, a[g + 10], 17, -42063), d = md5_ff(d, e, f, c, a[g + 11], 22, -1990404162), c = md5_ff(c, d, e, f, a[g + 12], 7, 1804603682), f = md5_ff(f, c, d, e, a[g + 13], 12, -40341101), e = md5_ff(e, f, c, d, a[g + 14], 17, -1502002290), d = md5_ff(d, e, f, c, a[g + 15], 22, 1236535329), c = md5_gg(c, d, e, f, a[g + 1], 5, -165796510), f = md5_gg(f, c, d, e, a[g + 6], 9, -1069501632), e = md5_gg(e, f, c, d, a[g + 11], 14, 643717713), d = md5_gg(d, e, f, c, a[g + 0], 20, -373897302), c = md5_gg(c, d, e, f, a[g + 5], 5, -701558691), f = md5_gg(f, c, d, e, a[g + 10], 9, 38016083), e = md5_gg(e, f, c, d, a[g + 15], 14, -660478335), d = md5_gg(d, e, f, c, a[g + 4], 20, -405537848), c = md5_gg(c, d, e, f, a[g + 9], 5, 568446438), f = md5_gg(f, c, d, e, a[g + 14], 9, -1019803690), e = md5_gg(e, f, c, d, a[g + 3], 14, -187363961), d = md5_gg(d, e, f, c, a[g + 8], 20, 1163531501), c = md5_gg(c, d, e, f, a[g + 13], 5, -1444681467), f = md5_gg(f, c, d, e, a[g + 2], 9, -51403784), e = md5_gg(e, f, c, d, a[g + 7], 14, 1735328473), d = md5_gg(d, e, f, c, a[g + 12], 20, -1926607734), c = md5_hh(c, d, e, f, a[g + 5], 4, -378558), f = md5_hh(f, c, d, e, a[g + 8], 11, -2022574463), e = md5_hh(e, f, c, d, a[g + 11], 16, 1839030562), d = md5_hh(d, e, f, c, a[g + 14], 23, -35309556), c = md5_hh(c, d, e, f, a[g + 1], 4, -1530992060), f = md5_hh(f, c, d, e, a[g + 4], 11, 1272893353), e = md5_hh(e, f, c, d, a[g + 7], 16, -155497632), d = md5_hh(d, e, f, c, a[g + 10], 23, -1094730640), c = md5_hh(c, d, e, f, a[g + 13], 4, 681279174), f = md5_hh(f, c, d, e, a[g + 0], 11, -358537222), e = md5_hh(e, f, c, d, a[g + 3], 16, -722521979), d = md5_hh(d, e, f, c, a[g + 6], 23, 76029189), c = md5_hh(c, d, e, f, a[g + 9], 4, -640364487), f = md5_hh(f, c, d, e, a[g + 12], 11, -421815835), e = md5_hh(e, f, c, d, a[g + 15], 16, 530742520), d = md5_hh(d, e, f, c, a[g + 2], 23, -995338651), c = md5_ii(c, d, e, f, a[g + 0], 6, -198630844), f = md5_ii(f, c, d, e, a[g + 7], 10, 1126891415), e = md5_ii(e, f, c, d, a[g + 14], 15, -1416354905), d = md5_ii(d, e, f, c, a[g + 5], 21, -57434055), c = md5_ii(c, d, e, f, a[g + 12], 6, 1700485571), f = md5_ii(f, c, d, e, a[g + 3], 10, -1894986606), e = md5_ii(e, f, c, d, a[g + 10], 15, -1051523), d = md5_ii(d, e, f, c, a[g + 1], 21, -2054922799), c = md5_ii(c, d, e, f, a[g + 8], 6, 1873313359), f = md5_ii(f, c, d, e, a[g + 15], 10, -30611744), e = md5_ii(e, f, c, d, a[g + 6], 15, -1560198380), d = md5_ii(d, e, f, c, a[g + 13], 21, 1309151649), c = md5_ii(c, d, e, f, a[g + 4], 6, -145523070), f = md5_ii(f, c, d, e, a[g + 11], 10, -1120210379), e = md5_ii(e, f, c, d, a[g + 2], 15, 718787259), d = md5_ii(d, e, f, c, a[g + 9], 21, -343485551), c = safe_add(c, h), d = safe_add(d, i), e = safe_add(e, j), f = safe_add(f, k);
  return Array(c, d, e, f)
}

function md5_cmn(a, b, c, d, e, f) {
  return safe_add(bit_rol(safe_add(safe_add(b, a), safe_add(d, f)), e), c)
}

function md5_ff(a, b, c, d, e, f, g) {
  return md5_cmn(b & c | ~b & d, a, b, e, f, g)
}

function md5_gg(a, b, c, d, e, f, g) {
  return md5_cmn(b & d | c & ~d, a, b, e, f, g)
}

function md5_hh(a, b, c, d, e, f, g) {
  return md5_cmn(b ^ c ^ d, a, b, e, f, g)
}

function md5_ii(a, b, c, d, e, f, g) {
  return md5_cmn(c ^ (b | ~d), a, b, e, f, g)
}

function core_hmac_md5(a, b) {
  var d, e, f, g, c = str2binl(a);
  for (c.length > 16 && (c = core_md5(c, a.length * chrsz)), d = Array(16), e = Array(16), f = 0; 16 > f; f++) d[f] = 909522486 ^ c[f], e[f] = 1549556828 ^ c[f];
  return g = core_md5(d.concat(str2binl(b)), 512 + b.length * chrsz), core_md5(e.concat(g), 640)
}

function safe_add(a, b) {
  var c = (65535 & a) + (65535 & b),
      d = (a >> 16) + (b >> 16) + (c >> 16);
  return d << 16 | 65535 & c
}

function bit_rol(a, b) {
  return a << b | a >>> 32 - b
}

function str2binl(a) {
  var d, b = Array(),
      c = (1 << chrsz) - 1;
  for (d = 0; d < a.length * chrsz; d += chrsz) b[d >> 5] |= (a.charCodeAt(d / chrsz) & c) << d % 32;
  return b
}

function binl2str(a) {
  var d, b = "",
      c = (1 << chrsz) - 1;
  for (d = 0; d < 32 * a.length; d += chrsz) b += String.fromCharCode(a[d >> 5] >>> d % 32 & c);
  return b
}

function binl2hex(a) {
  var d, b = hexcase ? "0123456789ABCDEF" : "0123456789abcdef",
      c = "";
  for (d = 0; d < 4 * a.length; d++) c += b.charAt(15 & a[d >> 2] >> 8 * (d % 4) + 4) + b.charAt(15 & a[d >> 2] >> 8 * (d % 4));
  return c
}

function binl2b64(a) {
  var d, e, f, b = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
      c = "";
  for (d = 0; d < 4 * a.length; d += 3)
    for (e = (255 & a[d >> 2] >> 8 * (d % 4)) << 16 | (255 & a[d + 1 >> 2] >> 8 * ((d + 1) % 4)) << 8 | 255 & a[d + 2 >> 2] >> 8 * ((d + 2) % 4), f = 0; 4 > f; f++) c += 8 * d + 6 * f > 32 * a.length ? b64pad : b.charAt(63 & e >> 6 * (3 - f));
  return c
}

function encode_param(a) {
  var b = new Base64;
  return b.encode(a)
}

function encode_secret() {
  var b, a = appId;
  for (b = 0; b < arguments.length; b++) a += arguments[b];
  return a = a.replace(/\s/g, ""), hex_md5(a)
}

function decode_result(a) {
  var b = new Base64;
  return b.decode(b.decode(b.decode(a)))
}
var hexcase = 0,
    b64pad = "",
    chrsz = 8,
    appId = "a01901d3caba1f362d69474674ce477f";
