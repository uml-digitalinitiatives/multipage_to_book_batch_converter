#!/usr/bin/env python3


import argparse
import html
import logging
import os
import os.path
import re
import shutil
import subprocess
import sys

from hocrpdf import HocrPdf


class Derivatives(object):
    """Regex - Match HTML tags"""
    htmlmatch = re.compile(r'<[^>]+>', re.MULTILINE | re.DOTALL)
    """Regex - Match blank lines/characters"""
    blanklines = re.compile(r'^[\x01|\x0a|\s]*$', re.MULTILINE)
    """Regex - Match PDF extension"""
    is_pdf = re.compile(r'.*\.pdf$', re.IGNORECASE)

    def __init__(self, options, logger):
        self.logger = logger
        self.options = options

    def do_page_derivatives(self, tiff_file, out_dir, input_file=None):
        if not self.options.skip_hocr_ocr:
            self.do_hocr_ocr(tiff_file, out_dir)
        self.get_jpegs(tiff_file, out_dir)
        if input_file is not None and not Derivatives.is_pdf.match(input_file):
            self.make_pdf(os.path.join(out_dir, 'JP2.jp2'), os.path.join(out_dir, 'HOCR.html'), out_dir)

    def do_book_derivatives(self, input_file, out_dir):
        if input_file is not None and Derivatives.is_pdf.match(input_file):
            # For our directory scanner, leave this as a manual process for now.
            # Last copy the original PDF to the book level as PDF.pdf
            shutil.copy(input_file, os.path.join(out_dir, 'PDF.pdf'))
        elif self.has_page_pdfs(out_dir):
            # Try to make a combined PDF.
            operations = [
                "gs", "-dBATCH", "-dNOPAUSE", "-q", "-sDEVICE=pdfwrite", "-dAutoRotatePages=/None",
                "-sOutputFile={}".format(os.path.join(out_dir, 'PDF.pdf')), "$(", "find", ".", "-type", "f", "-name",
                "'PDF.pdf'", "-print", "|", "sort", "-t'/'", "-k", "2,2", "-n", ")"
            ]
            Derivatives.do_system_call(operations, logger=self.logger)
        if os.path.exists(os.path.join(out_dir, '1', 'TN.jpg')):
            # Copy the first page thumbnail up to the book.
            shutil.copy(os.path.join(out_dir, '1', 'TN.jpg'), os.path.join(out_dir, 'TN.jpg'))

    def do_hocr_ocr(self, tiff_file, out_dir):
        # Skip HOCR/OCR generation.
        hocr_file = self.get_hocr(tiff_file, out_dir)
        self.get_ocr(tiff_file, hocr_file, out_dir)

    def get_jpegs(self, tiff_file, out_dir):
        """Produce the needed JPEGs for ingest.

        Keyword arguments
        tiff_file -- The tiff file
        out_dir -- The directory to save the images to.
        """
        if not self.options.skip_jp2:
            self._make_jpeg_2000(tiff_file, out_dir)
        self._make_jpeg(tiff_file, out_dir, 'JPG', height=800, width=800)
        self._make_jpeg(tiff_file, out_dir, 'TN', height=110, width=110)

    def _make_jpeg_2000(self, tiff_file, out_dir, second_try=False):
        size = self.get_image_size(tiff_file)
        res = self.get_image_resolution(tiff_file)
        loseless = (size['height'] < 1024 or size['width'] < 1024 or res['x'] < 300 or res['y'] < 300)
        just_file = os.path.split(tiff_file)[1]
        output_file = os.path.join(out_dir, 'JP2.jp2')

        if os.path.exists(output_file) and os.path.isfile(output_file) and self.options.overwrite:
            os.remove(output_file)
            self.logger.debug("{} exists and we are deleting it.".format(output_file))

        if not os.path.exists(output_file):
            self.logger.debug("Generating Jpeg2000")
            # Use Kakadu
            op = ['kdu_compress', '-i', tiff_file, '-o', output_file]
            if loseless:
                # Do loseless
                op.extend(['-quiet', 'Creversible=yes', '-rate', '-,1,0.5,0.25', 'Clevels=5'])
            else:
                op.extend(['-quiet', 'Clayers=5', 'Clevels=7',
                           'Cprecincts={256,256},{256,256},{256,256},{128,128},{128,128},{64,64},{64,64},{32,32},{16,16}',
                           'Corder=RPCL', 'ORGgen_plt=yes', 'ORGtparts=R', 'Cblk={32,32}', 'Cuse_sop=yes'])
            if not self.do_system_call(op, logger=self.logger):
                if self.is_compressed(tiff_file) and not second_try:
                    # We failed, the tiff is compressed and we haven't tried with an uncompressed tiff
                    temp_tiff = os.path.join(os.path.dirname(tiff_file),
                                             os.path.splitext(just_file)[0] + "_tmp" + os.path.splitext(just_file)[1])
                    op = ['convert', '-compress', 'None', tiff_file, temp_tiff]
                    self.do_system_call(op, timeout=600, logger=self.logger)
                    self._make_jpeg_2000(temp_tiff, out_dir, second_try=True)
                else:
                    # We failed
                    self.logger.error("Failed to generate JPEG2000 from %s" % tiff_file)
                    print("Failed to generate JPEG2000 from %s" % tiff_file)
                    os.remove(tiff_file)
                    quit(1)

            if second_try:
                # If we made an uncompressed copy, delete it.
                os.remove(tiff_file)

    def _make_jpeg(self, tiff_file, out_dir, out_name, height=None, width=None):
        """Make a Jpeg of max size height x width"""

        op = ['convert', tiff_file]

        output_file = os.path.join(out_dir, out_name + '.jpg')

        if os.path.exists(output_file) and os.path.isfile(output_file) and self.options.overwrite:
            os.remove(output_file)
            self.logger.debug("{} exists and we are deleting it.".format(output_file))

        if not os.path.exists(output_file):
            self.logger.debug("Creating JPEG with size maximum width and height {}x{}".format(width, height))
            if height is not None or width is not None:
                op.append('-resize')
                if height is not None and width is not None:
                    op.append("{}x{}".format(width, height))
                elif width is not None:
                    op.append(width)
                else:
                    op.append("x{}".format(height))
            op.append(output_file)

            self.do_system_call(op, logger=self.logger)

    def get_ocr(self, tiff_file, hocr_file, out_dir):
        """Which way to get OCR.

        Keyword arguments
        tiff_file -- Tiff file to process from
        hocr_file -- Hocr file to extract from
        out_dir -- Directory to write OCR file to.
        """
        if tiff_file is not None and os.path.exists(tiff_file) and os.path.isfile(tiff_file) and not \
                self.options.use_hocr:
            self.process_ocr(tiff_file, out_dir)
        elif hocr_file is not None and os.path.exists(hocr_file) and os.path.isfile(hocr_file) and \
                self.options.use_hocr:
            self.get_ocr_from_hocr(hocr_file, out_dir)
        else:
            self.logger.error("Unable to generate OCR")

    def get_ocr_from_hocr(self, hocr_file, out_dir):
        """Extract OCR from the Hocr data

        Keyword arguments
        hocr_file -- The HOCR file
        out_dir -- Directory to write OCR file to.
        """
        output_file = os.path.join(out_dir, 'OCR.txt')
        if os.path.exists(output_file) and os.path.isfile(output_file) and self.options.overwrite:
            os.remove(output_file)
            self.logger.debug("{} exists and we are deleting it.".format(output_file))
        if not os.path.exists(output_file):
            self.logger.debug("Generating OCR.")
            data = ''
            with open(hocr_file, 'r') as fpr:
                data += fpr.read()
            data = html.unescape(Derivatives.blanklines.sub('', Derivatives.htmlmatch.sub('\1', data)))
            with open(output_file, 'w') as fpw:
                fpw.write(data)

    def process_ocr(self, tiff_file, out_dir):
        """Get the OCR from a Tiff file.

        Keyword arguments
        tiff_file -- The TIFF image
        out_dir -- The output directory"""
        output_file = os.path.join(out_dir, 'OCR.txt')
        output_stub = os.path.join(out_dir, 'OCR')
        if os.path.exists(output_file) and os.path.isfile(output_file) and self.options.overwrite:
            os.remove(output_file)
            self.logger.debug("{} exists and we are deleting it.".format(output_file))
        if not os.path.exists(output_file):
            self.logger.debug("Generating OCR.")
            op = ['tesseract', tiff_file, output_stub, '-l', self.options.language]
            if not self.do_system_call(op, logger=self.logger):
                quit()

    def get_hocr(self, tiff_file, out_dir):
        """Get the HOCR from a Tiff file.

        Keyword arguments
        tiff_file -- The TIFF image
        out_dir -- The output directory"""
        output_stub = os.path.join(out_dir, 'HOCR')
        tmp_file = output_stub + '.hocr'
        output_file = output_stub + '.html'
        if os.path.exists(output_file) and os.path.isfile(output_file) and self.options.overwrite:
            os.remove(output_file)
            self.logger.debug("{} exists and we are deleting it.".format(output_file))
        if not os.path.exists(output_file):
            self.logger.debug("Generating HOCR.")
            op = ['tesseract', tiff_file, output_stub, '-l', self.options.language, 'hocr']
            if not self.do_system_call(op, timeout=600, logger=self.logger):
                self.logger.error("Problems generating HOCR from %s" % tiff_file)
                print("Problems generating HOCR from %s" % tiff_file)
                quit()
            os.rename(tmp_file, output_file)
            if os.path.exists(output_stub + '.txt') and self.options.use_hocr:
                # Some tesseracts seem to generate OCR at the same time as HOCR,
                # so lets move it to OCR if we are going to create OCR from HOCR.
                os.rename(output_stub + '.txt', os.path.join(out_dir, 'OCR.txt'))
        return output_file

    def make_pdf(self, jp2_file, hocr_file, out_dir):
        if os.path.exists(jp2_file) and os.path.exists(hocr_file):
            """Make PDF out of JP2 and HOCR."""
            hocr = HocrPdf()
            if self.options.debug_level == 'DEBUG':
                hocr.enable_debug()
            output_file = os.path.join(out_dir, 'PDF.pdf')
            if os.path.exists(output_file) and os.path.isfile(output_file) and self.options.overwrite:
                os.remove(output_file)
                self.logger.debug("{} exists and we are deleting it.".format(output_file))
            if not os.path.exists(output_file):
                self.logger.debug("Generating searchable PDF from tiff and hocr.")
                hocr.create_pdf(image_file=jp2_file, hocr_file=hocr_file, pdf_filename=output_file,
                                dpi=self.options.resolution)

    def image_magick_opts(self, lossless=False):
        """Stores and returns the Kakadu JP2 creation args"""
        args = list()
        args.append(" -depth 8")
        args.append(" -define jp2:tilewidth=1024")
        args.append(" -define jp2:tileheight=1024")
        if lossless:
            args.append(" -define numrlvls=6")
            args.append(" -define jp2:rate=1.0")
            args.append(" -define jp2:lazy")
            args.append(" -define jp2:prg=rlcp")
            args.append(
                " -define jp2:ilyrrates='0.015625,0.01858,0.0221,0.025,0.03125,0.03716,0.04419,0.05,0.0625,0.075,0.088"
                ",0.1,0.125,0.15,0.18,0.21,0.25,0.3,0.35,0.4,0.5,0.6,0.7,0.84'")
            args.append(" -define jp2:mode=int")
        else:
            args.append("-define numrlvls=7")
            args.append("-define jp2:rate=0.02348")
            args.append("-define jp2:prg=rpcl")
            args.append("-define jp2:mode=int")
            args.append("-define jp2:prcwidth=16383")
            args.append("-define jp2:prcheight=16383")
            args.append("-define jp2:cblkwidth=64")
            args.append("-define jp2:cblkheight=64")
            args.append("-define jp2:sop")
        return args

    def get_bit_depth(self, image_file):
        """Return the bit depth"""
        op = ['identify', '-format', '%[depth]', image_file]
        result = self.do_system_call(ops=op, return_result=True, logger=self.logger)
        result = result.rstrip('\r\n')
        self.logger.debug("Getting the bit depth ({}) for {}".format(result, image_file))
        return int(result)

    def get_image_size(self, image_file):
        """Return a dict of the height and width of the image"""
        self.logger.debug("Getting the height and width of {}".format(image_file))
        op = ['identify', '-format', '%[height]-%[width]', image_file]
        result = self.do_system_call(ops=op, return_result=True, logger=self.logger)
        if not result:
            self.logger.error("Problem getting image size for %s: %s" % (image_file, result))
            print("Problem getting image size for %s: %s" % (image_file, result))
            quit(1)
        res_list = result.rstrip('\r\n').split('-')
        return {'height': int(res_list[0]), 'width': int(res_list[1])}

    def get_image_resolution(self, image_file):
        """Return a dict of the X and Y resolutions of the image"""
        self.logger.debug("Getting the resolutions of {}".format(image_file))
        op = ['identify', '-format', '%x-%y', image_file]
        result = self.do_system_call(ops=op, return_result=True, logger=self.logger)
        result = result.rstrip('\r\n')
        if result.lower().find("undefined"):
            result = result.lower().replace("undefined", "")
        res_list = result.split('-')
        res_list = [int(re.search(r'\d+', value).group(0)) for value in res_list]
        self.logger.debug("Image resolution is " + str(res_list))
        return {'x': res_list[0], 'y': res_list[1]}

    def is_compressed(self, image_file):
        """Does identify see compression on the file."""
        self.logger.debug("Checking compression for {}".format(image_file))
        op = ['identify', '-format', '%[C]', image_file]
        result = self.do_system_call(ops=op, return_result=True, logger=self.logger)
        return result.rstrip('\r\n') != "None"

    def has_page_pdfs(self, out_dir):
        self.logger.debug("Checking for PDFs in the page directories of %s" % out_dir)
        for path, dirs, files in os.walk(out_dir):
            if dirs == out_dir:
                continue
            if 'PDF.pdf' in files:
                return True
        return False

    @staticmethod
    def do_system_call(ops, logger=None, return_result=False, timeout=60, fail_on_error=True):
        """Execute an external system call

        Keyword arguments
        ops -- a list of the executable and any arguments.
        return_result -- return the result of the call if successful.
        timeout -- Time to wait for the process to complete.
        """
        if logger is not None:
            logger.debug("Running system call - %s" % " ".join(ops))
        try:
            if sys.version_info.major == 3 and sys.version_info.minor < 7:
                process = subprocess.run(ops, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                                         universal_newlines=True)
            else:
                process = subprocess.run(ops, capture_output=True, timeout=timeout, universal_newlines=True)
            outs = process.stdout
            errs = process.stderr
            if not process.returncode == 0 and fail_on_error:
                if logger is not None:
                    logger.error(
                        "Error executing command: \n{}\nOutput: {}\nError: {}".format(' '.join(ops), outs, errs))
                return False
        except TimeoutError as e:
            if logger is not None:
                logger.error(
                    "Error executing command: \n{}\nMessage: {}\nOutput: {}\nSTDOUT: ".format(e.cmd, e.stderr, e.output,
                                                                                              e.stdout))
            return False
        except subprocess.CalledProcessError as e:
            if logger is not None:
                logger.error(
                    "Error executing command: \n{}\nMessage: {}\nOutput: {}\nSTDOUT: ".format(e.cmd, e.stderr, e.output,
                                                                                              e.stdout))
            return False
        if logger is not None:
            logger.debug("Command result:\n{}".format(outs))
        if return_result:
            return outs
        else:
            return True


def setup_log(level):
    """Setup an internal logging"""
    logger = logging.getLogger('multipage2book_derivatives')
    logger.propogate = False
    # Logging Level
    eval('logger.setLevel(logging.{})'.format(level))
    filename = os.path.join(os.getcwd(), 'multipage2book_derivatives.log')
    fh = logging.FileHandler(filename, 'w', 'utf-8')
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return logger


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Process derivatives for a directory or set of directories")
    parser.add_argument('process_dir', help="Paged content or single page directory")
    parser.add_argument('--single', action='store_true', dest="single_page", default=False,
                        help="Process as a single page instead of a directory of page directories.")
    parser.add_argument('--resolution', dest="resolution", type=int, default=300,
                        help="Resolution of the source material, used when generating Tiff. Defaults to 300.")
    parser.add_argument('--use-hocr', dest="use_hocr", action='store_true', default=False,
                        help='Generate OCR by stripping HTML characters from HOCR, otherwise run tesseract a second '
                             'time. Defaults to use tesseract.')
    parser.add_argument('--skip-hocr-ocr', dest="skip_hocr_ocr", action='store_true', default=False,
                        help='Do not generate OCR/HOCR datastreams')
    parser.add_argument('--skip-jp2', dest="skip_jp2", action='store_true', default=False,
                        help='Do not generate JP2 datastreams')
    parser.add_argument('-l', '--loglevel', dest="debug_level",
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='ERROR', help='Set logging level, defaults to ERROR.')

    args = parser.parse_args()
    if args.process_dir[0] != '/' and args.process_dir[0] != '~':
        args.process_dir = os.path.join(os.getcwd(), args.process_dir)
    args.process_dir = os.path.realpath(args.process_dir)
    if not os.path.exists(args.process_dir) or not os.access(args.process_dir, os.R_OK | os.W_OK) or not \
            os.path.isdir(args.process_dir):
        parser.error("%s does not exist is or not a read/writeable directory" % args.process_dir)
    else:
        internal_logger = setup_log(args.debug_level)
        d = Derivatives(args, internal_logger)
        if args.single_page:
            tiffs = [x for x in os.listdir(args.process_dir) if os.path.splitext(x) == 'tif' or os.path.splitext(x) ==
                     'tiff']
            if len(tiffs) == 1:
                d.do_page_derivatives(tiffs[0], args.process_dir)
            else:
                print("Error no tiff files found in %s" % args.process_dir)
                quit(1)
        else:
            dirs = [os.path.join(args.process_dir, x) for x in os.listdir(args.process_dir) if
                    os.path.isdir(os.path.join(args.process_dir, x))]
            for dir in dirs:
                tiffs = [os.path.join(dir, x) for x in os.listdir(dir) if
                         os.path.splitext(x)[1] == '.tif' or os.path.splitext(x)[1] ==
                         '.tiff']
                if len(tiffs) == 1:
                    d.do_page_derivatives(tiffs[0], dir)
                else:
                    print("Error no (or more than one) tiff files found in %s" % dir)
            d.do_book_derivatives(None, args.process_dir)
