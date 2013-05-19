import os
import argparse
import re
import base64
from urlparse import urlparse, urlunparse

import lxml.html
from lxml.cssselect import CSSSelector
import requests


class Extractor(object):

    def __init__(self, args):
        self.args = args

    def download(self, url, headers):
        """
        Download a file and return the contents.
        """
        if self.args.verbose:
            print "  Downloading %s..." % url
        headers.setdefault('User-Agent',
                           'Mozilla/5.0 (iPad; CPU OS 6_0 like Mac OS X) '
                           'AppleWebKit/536.26 (KHTML, like Gecko) '
                           'Version/6.0 Mobile/10A5355d Safari/8536.25')
        headers.setdefault('DNT', '1')
        r = requests.get(url, headers=headers)
        return r.text

    def ensure_schema(self, url, base_schema):
        if url.startswith('//'):
            return base_schema + ':' + url
        else:
            return url

    def find_typekit_js_urls(self, doc):
        """
        Given an lxml.html doc, return an array of typekit javascript URLs.
        """
        if self.args.verbose:
            print "  Hunting for JS URLs..."
        sel = CSSSelector('script')
        urls = []
        for el in sel(doc):
            src = el.attrib.get('src')
            if src and src.startswith('//use.typekit.net'):
                if self.args.verbose:
                    print "    Found JS URL: %s" % src
                urls.append(src)
        return urls

    def find_typekit_css_url(self, s, base_url):
        """
        Given a file of typekit javascript, return the CSS file loaded.
        """
        if self.args.verbose:
            print "  Hunting for CSS URL..."
        regex = 'Typekit\.config\=\{"f"\:"(.+?)"'
        m = re.search(regex, s)
        assert m, "typekit js doesn't match for a CSS file!"
        url = m.group(1)

        # Possible values for this format key seem to be: a, d, i, f, b
        if self.args.format == 'otf':
            url = url.replace('{format}{/extras*}', 'd')
        elif self.args.format == 'eot':
            o = urlparse(base_url)
            domain = o.netloc
            url = url.replace('{format}{/extras*}', 'i/%s/1f' % domain)
        else:
            assert False

        if self.args.verbose:
            print "    Found CSS URL: %s" % url
        return url

    def load_font_url(self, url, base_url, headers):
        regex = 'data:font\/opentype;base64\,(?P<font>.+)'
        m = re.match(regex, url)
        if m:
            # This is a data URI
            return base64.b64decode(m.group('font'))
        else:
            # Try to fetch it.
            if url.startswith('/'):
                o = list(urlparse(base_url))
                o[2] = url
                url = urlunparse(o)
                return self.download(url, headers)
            else:
                assert False, "no handling for relative URLs"

    def extract_font_urls(self, css):
        """
        Given a CSS document containing base64-encoded (data URI) fonts, extract
        the @font-face declaratons. Return them as a dict mapping font name to
        opentype font file.
        """
        if self.args.verbose:
            print "  Extracting CSS fonts..."

        #print "***********"
        #for line in css.split('\n'):
        #    print line
        #print "***********"

        regex = (
            '\@font-face\ \{\n'
            'font-family:"(?P<name>.+?)";\n'
            'src:url\((?P<url>.+?)\);\n'
            'font-style:(?P<style>\w+);font-weight:(?P<weight>\w+);\n'
            '}'
        )

        fonts = {}
        for m in re.finditer(regex, css):
            name = m.group('name')
            style = m.group('style')
            weight = m.group('weight')
            url = m.group('url')
            print "    Found font"
            print "      font-family: %s" % name
            print "      font-style: %s" % style
            print "      font-weight: %s" % weight
            print "      url: %s..." % url[:50]
            font_name = '%s_%s_%s' % (name, style, weight)
            fonts[font_name] = m.group('url')

        return fonts

    def extract(self, url, dir):
        """
        Extract Typekit fonts from this URL, and place .otf files into dir.
        """
        base_schema = url.split(':', 1)[0]
        headers = {'Referer': url}

        doc = lxml.html.parse(url)
        js_urls = self.find_typekit_js_urls(doc)

        font_urls = {}
        for js_url in js_urls:
            js_url = self.ensure_schema(js_url, base_schema)
            js_body = self.download(js_url, headers)

            css_url = self.find_typekit_css_url(js_body, url)
            css_url = self.ensure_schema(css_url, base_schema)
            css_body = self.download(css_url, headers)

            font_urls.update(self.extract_font_urls(css_body))

        fonts = {}
        for font_name, font_url in font_urls.iteritems():
            fonts[font_name] = self.load_font_url(font_url, url, headers)

        for font_name, font_body in fonts.iteritems():
            path = os.path.join(dir, '%s.%s' % (font_name, self.args.format))
            with open(path, 'w') as f:
                f.write(font_body)


def main():
    p = argparse.ArgumentParser(
        description='Extract typekit fonts.')

    p.add_argument('urls', metavar='URLS', type=str, nargs='+',
                   help='URLs to extract from')
    p.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                   default=False, help='Print detailed output')
    p.add_argument('-f', '--format', dest='format', type=str,
                   default='otf', help='Font format to download')
    p.add_argument('-o', '--out', dest='output_dir', type=str,
                   default=None,
                   help='Output directory for font files (defaults to CWD)')

    args = p.parse_args()

    dir = args.output_dir or os.getcwd()
    extractor = Extractor(args)
    for url in args.urls:
        extractor.extract(url, dir)
