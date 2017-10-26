#!/usr/bin/env python3
#
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Adapted from https://github.com/tmbdev/hocr-tools/blob/master/hocr-pdf

# Create a searchable PDF from a pile of HOCR + JPEG. Tested with
# Tesseract.

from __future__ import print_function
import argparse
import base64
import io
import os.path
import re
import zlib
import math

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader

import xml.etree.ElementTree as ET
from PIL import Image


class HocrPdf:

    dpi = 300

    height = 0

    width = 0

    debug = False

    pattern1 = re.compile('bbox((\s+\d+){4})')

    pattern2 = re.compile('baseline((\s+[\d.\-]+){2})')

    def __init__(self):
        pdfmetrics.findFontAndRegister('Courier')
        #self.load_invisible_font()

    def set_dpi(self, new_dpi):
        self.dpi = int(new_dpi)

    def enable_debug(self):
        self.debug = True

    def get_debug(self):
        return self.debug

    def create_pdf(self, image_file, hocr_file, pdf_filename, dpi=300):
        """Create a PDF from an image and HOCR"""
        im = Image.open(image_file)
        w, h = im.size
        if dpi != 300:
            self.set_dpi(dpi)
        try:
            self.dpi = int(im.info['dpi'][0])
        except KeyError:
            pass
        self.width = self.dpi_to_point(w)
        self.height = self.dpi_to_point(h)
        image_wrapper = ImageReader(im)
        with open(hocr_file, 'r') as hocr_fp:
            hocr_data = hocr_fp.read()
        pdf_data = self.process_pdf(image_wrapper, hocr_data, pdf_filename)
        with open(pdf_filename, 'wb') as pdf_fp:
            pdf_fp.write(pdf_data)

    def process_pdf(self, image_data, hocr_data, pdf_filename):
        """Utility function if you'd rather get the PDF data back instead of save it automatically."""
        pdf = Canvas(pdf_filename, pageCompression=1)
        pdf.setCreator('hocr-tools')
        pdf.setPageSize((self.width, self.height))
        pdf.drawImage(image_data, 0, 0, width=self.width, height=self.height)
        pdf = self.add_text_layer(pdf, hocr_data)
        pdf_data = pdf.getpdfdata()
        return pdf_data

    def add_text_layer(self, pdf, hocrdata):
        """Draw an invisible text layer for OCR data"""
        font_name = "Courier"
        hocr = ET.fromstring(hocrdata)
        for line in hocr.findall('.//*[@class="ocr_line"]'):
            linebox = self.pattern1.search(line.attrib['title']).group(1).split()
            try:
                baseline = self.pattern2.search(line.attrib['title']).group(1).split()
            except AttributeError:
                baseline = [0, 0]
            linebox = [float(i) for i in linebox]
            baseline = [float(i) for i in baseline]
            xpath_elements = './/*[@class="ocrx_word"]'
            angle = math.atan(baseline[0])
            cosine = math.cos(angle)
            sine = math.sin(angle)
            if len(line.findall(xpath_elements)) == 0:
                # if there are no words elements present,
                # we switch to lines as elements
                xpath_elements = '.'
            for word in line.findall(xpath_elements):
                rawtext = (" ".join([item.strip() for item in word.itertext()]))
                if rawtext == '':
                    continue
                box = self.pattern1.search(word.attrib['title']).group(1).split()
                box = [float(i) for i in box]
                point_height = self.dpi_to_point(box[3] - box[1])
                font_width = pdf.stringWidth(rawtext, font_name, point_height)
                if font_width <= 0:
                    continue
                b = self.polyval(baseline,
                            (box[1] + box[3]) / 2 - linebox[1]) + linebox[3]
                text = pdf.beginText()
                if not self.debug:
                    # Show the text in the PDF if you are debugging.
                    text.setTextRenderMode(3)  # make text invisible.
                text.setFont(font_name, point_height)
                text.setTextTransform(cosine, -1 * sine, sine, cosine, self.dpi_to_point(box[0]),
                                      self.height - self.dpi_to_point(b))
                box_width = self.dpi_to_point(box[2] - box[0])
                text.setHorizScale(100.0 * box_width / font_width)
                text.textLine(rawtext)
                pdf.drawText(text)
        return pdf

    @staticmethod
    def polyval(poly, x):
        return x * poly[0] + poly[1]

    def dpi_to_point(self, x):
        return float((x * 72) / self.dpi)

    # Glyphless variation of vedaal's invisible font retrieved from
    # http://www.angelfire.com/pr/pgpf/if.html, which says:
    # 'Invisible font' is unrestricted freeware. Enjoy, Improve, Distribute freely
    @staticmethod
    def load_invisible_font():
        font = """
    eJzdlk1sG0UUx/+zs3btNEmrUKpCPxikSqRS4jpfFURUagmkEQQoiRXgAl07Y3vL2mvt2ml8APXG
    hQPiUEGEVDhWVHyIC1REPSAhBOWA+BCgSoULUqsKcWhVBKjhzfPU+VCi3Flrdn7vzZv33ryZ3TUE
    gC6chsTx8fHck1ONd98D0jnS7jn26GPjyMIleZhk9fT0wcHFl1/9GRDPkTxTqHg1dMkzJH9CbbTk
    xbWlJfKEdB+Np0pBswi+nH/Nvay92VtfJp4nvEztUJkUHXsdksUOkveXK/X5FNuLD838ICx4dv4N
    I1e8+ZqbxwCNP2jyqXoV/fmhy+WW/2SqFsb1pX68SfEpZ/TCrI3aHzcP//jitodvYmvL+6Xcr5mV
    vb1ScCzRnPRPfz+LsRSWNasuwRrZlh1sx0E8AriddyzEDfE6EkglFhJDJO5u9fJbFJ0etEMB78D5
    4Djm/7kjT0wqhSNURyS+u/2MGJKRu+0ExNkrt1pJti9p2x6b3TBJgmUXuzgnDmI8UWMbkVxeinCw
    Mo311/l/v3rF7+01D+OkZYE0PrbsYAu+sSyxU0jLLtIiYzmBrFiwnCT9FcsdOOK8ZHbFleSn0znP
    nDCnxbnAnGT9JeYtrP+FOcV8nTlNnsoc3bBAD85adtCNRcsSffjBsoseca/lBE7Q09LiJOm/ttyB
    0+IqcwfncJt5q4krO5k7jV7uY+5m7mPebuLKUea7iHvk48w72OYF5rvZT8C8k/WvMN/Dc19j3s02
    bzPvZZv3me9j/ox5P9t/xdzPzPVJcc7yGnPL/1+GO1lPVTXM+VNWOTRRg0YRHgrUK5yj1kvaEA1E
    xAWiCtl4qJL2ADKkG6Q3XxYjzEcR0E9hCj5KtBd1xCxp6jV5mKP7LJBr1nTRK2h1TvU2w0akCmGl
    5lWbBzJqMJsdyaijQaCm/FK5HqspHetoTtMsn4LO0T2mlqcwmlTVOT/28wGhCVKiNANKLiJRlxqB
    F603axQznIzRhDSq6EWZ4UUs+xud0VHsh1U1kMlmNwu9kTuFaRqpURU0VS3PVmZ0iE7gct0MG/8+
    2fmUvKlfRLYmisd1w8pk1LSu1XUlryM1MNTH9epTftWv+16gIh1oL9abJZyjrfF5a4qccp3oFAcz
    Wxxx4DpvlaKKxuytRDzeth5rW4W8qBFesvEX8RFRmLBHoB+TpCmRVCCb1gFCruzHqhhW6+qUF6tC
    pL26nlWN2K+W1LhRjxlVGKmRTFYVo7CiJug09E+GJb+QocMCPMWBK1wvEOfRFF2U0klK8CppqqvG
    pylRc2Zn+XDQWZIL8iO5KC9S+1RekOex1uOyZGR/w/Hf1lhzqVfFsxE39B/ws7Rm3N3nDrhPuMfc
    w3R/aE28KsfY2J+RPNp+j+KaOoCey4h+Dd48b9O5G0v2K7j0AM6s+5WQ/E0wVoK+pA6/3bup7bJf
    CMGjwvxTsr74/f/F95m3TH9x8o0/TU//N+7/D/ScVcA=
    """.encode('latin1')
        uncompressed = bytearray(zlib.decompress(base64.decodebytes(font)))
        ttf = io.BytesIO(uncompressed)
        setattr(ttf, "name", "(invisible.ttf)")
        pdfmetrics.registerFont(TTFont('invisible', ttf))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage="searchablePDF <image_file> <hocr_file>",
                                     description="Create a searchable PDF from an image file and a hocr file.")
    parser.add_argument('image_file', help="An image file (JP2, JPG).")
    parser.add_argument('hocr_file', help="The Hocr file for the provided image.")
    parser.add_argument('-o', '--output', dest="filename",
                        help="Filename to save PDF as. Defaults to image_file path and name with pdf extension")
    parser.add_argument('--density', dest="dpi", default=300, help="Density of source images.")
    args = parser.parse_args()
    if not os.path.exists(args.image_file):
        parser.error("File {} does not exist".format(args.image_file))
    if not os.path.exists(args.hocr_file):
        parser.error("File {} does not exist".format(args.hocr_file))
    if args.filename is None:
        pdf_filename = os.path.splitext(args.image_file)[0] + ".pdf"
    else:
        pdf_filename = args.filename
    hocr = HocrPdf()
    hocr.create_pdf(args.image_file, args.hocr_file, pdf_filename, args.dpi)
