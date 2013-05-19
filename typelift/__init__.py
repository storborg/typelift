import os
import argparse
import re
import base64

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

    def find_typekit_css_url(self, s):
        """
        Given a file of typekit javascript, return the CSS file loaded.
        """
        if self.args.verbose:
            print "  Hunting for CSS URL..."
        regex = 'Typekit\.config\=\{"f"\:"(.+?)"'
        m = re.search(regex, s)
        assert m, "typekit js doesn't match for a CSS file!"
        url = m.group(1)
        url = url.replace('{format}{/extras*}', 'd')
        if self.args.verbose:
            print "    Found CSS URL: %s" % url
        return url

    def extract_css_fonts(self, css):
        """
        Given a CSS document containing base64-encoded (data URI) fonts, extract
        the @font-face declaratons. Return them as a dict mapping font name to
        opentype font file.
        """
        if self.args.verbose:
            print "  Extracting CSS fonts..."

        regex = (
            '\@font-face\ \{\n'
            'font-family:"(?P<name>.+?)";\n'
            'src:url\(data:font\/opentype;base64\,(?P<font>.+?);\n'
            'font-style:(?P<style>\w+);font-weight:(?P<weight>\w+);\n'
            '}'
        )

        fonts = {}
        for m in re.finditer(regex, css):
            name = m.group('name')
            style = m.group('style')
            weight = m.group('weight')
            if self.args.verbose:
                print "    Found match"
                print "      font-family: %s" % name
                print "      font-style: %s" % style
                print "      font-weight: %s" % weight
            font_name = '%s_%s_%s' % (name, style, weight)
            fonts[font_name] = base64.b64decode(m.group('font'))

        return fonts

    def extract(self, url, dir):
        """
        Extract Typekit fonts from this URL, and place .otf files into dir.
        """
        base_schema = url.split(':', 1)[0]
        headers = {'Referer': url}

        doc = lxml.html.parse(url)
        js_urls = self.find_typekit_js_urls(doc)
        fonts = {}
        for js_url in js_urls:
            js_url = self.ensure_schema(js_url, base_schema)
            js_body = self.download(js_url, headers)

            css_url = self.find_typekit_css_url(js_body)
            css_url = self.ensure_schema(css_url, base_schema)
            css_body = self.download(css_url, headers)

            fonts.update(self.extract_css_fonts(css_body))

        for font_name, font_body in fonts.iteritems():
            path = os.path.join(dir, '%s.otf' % font_name)
            with open(path, 'w') as f:
                print "Writing:\n%r" % font_body
                f.write(font_body)


def main():
    p = argparse.ArgumentParser(
        description='Extract typekit fonts.')

    p.add_argument('urls', metavar='URLS', type=str, nargs='+',
                   help='URLs to extract from')
    p.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                   default=False, help='Print detailed output')

    args = p.parse_args()

    dir = os.getcwd()
    extractor = Extractor(args)
    for url in args.urls:
        extractor.extract(url, dir)
