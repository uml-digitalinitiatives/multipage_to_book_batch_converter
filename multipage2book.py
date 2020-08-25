#!/usr/bin/env python3
# encoding: utf-8
"""
Multipage 2 PDF to Islandora Book Batch converter

Created by Jared Whiklo on 2016-03-16.
Copyright (c) 2016 University of Manitoba Libraries. All rights reserved.
"""
import sys
import os
import argparse
import re
import logging
import logging.config
import subprocess
import time
import PyPDF2
import shutil

from Derivatives import Derivatives
from MODSSpreader import MODSSpreader

"""logger placeholder"""
logger = None

"""derivative generator"""
derivative_gen = None

"""MODS spreader"""
spreader = None

"""External programs needed for this to operate"""
required_programs = [
    {'exec': 'gs', 'check_var': '--help'},
    {'exec': 'convert', 'check_var': '-version'},
    {'exec': 'identify', 'check_var': '-version'}
]

"""External programs needed for creating derivatives."""
hocr_programs = [
    {'exec': 'tesseract', 'check_var': '-v'},
]

"""External programs for Jpeg2000 derivatives."""
jp2_programs = [
    {'exec': 'kdu_compress', 'check_var': '-version'}
]

"""Options dictionary placeholder, generated by ArgumentParser"""
options = None

"""Regex - Count pages from parsed PDF."""
rxcountpages = re.compile(b"/Type\s*/Page([^s]|$)", re.MULTILINE | re.DOTALL)
"""Regex - Match HTML tags"""
htmlmatch = re.compile(r'<[^>]+>', re.MULTILINE | re.DOTALL)
"""Regex - Match blank lines/characters"""
blanklines = re.compile(r'^[\x01|\x0a|\s]*$', re.MULTILINE)
"""Regex - Match file extensions"""
valid_extensions = re.compile(r'.*\.(pdf|tiff?)$', re.IGNORECASE)
"""Regex - Match PDF extension"""
is_pdf = re.compile(r'.*\.pdf$', re.IGNORECASE)


def preprocess_file(input_file):
    # Check for an existing directory
    book_name = os.path.splitext(os.path.split(input_file)[1])[0]
    book_number = None
    if options.merge and re.search(r'\d+$', book_name) is not None:
        (book_name, book_number, junk) = re.split(r'(\d+)$', book_name)
        book_name = book_name.strip()
    book_name = re.sub(r'[\s\',\-]+', '_', book_name.rstrip())
    book_dir = None
    if options.output_dir != '.':
        if options.output_dir[0:1] == '/' and os.path.exists(options.output_dir):
            book_dir = os.path.join(options.output_dir, book_name + '_dir')
        elif options.output_dir[0:1] != '/' and os.path.exists(os.path.join(os.getcwd(), options.output_dir)):
            book_dir = os.path.join(os.getcwd(), options.output_dir, book_name + '_dir')
    try:
        if book_dir is not None:
            logger.debug("Output directory was set to {}".format(book_dir))
    except UnboundLocalError:
        # not set, so use old default
        book_dir = os.path.join(os.path.dirname(input_file), book_name + '_dir')
    return book_dir, book_name, book_number


def process_file(input_file):
    """Parse a PDF and produce derivatives

    Keyword arguments
    pdf -- The full path to the input file
    """
    logger.info("Processing {}".format(input_file))
    (book_dir, book_name, book_number) = preprocess_file(input_file)
    mods_file = None
    if not os.path.exists(book_dir):
        os.mkdir(book_dir)
    if options.mods_dir is not None:
        tmpfile = os.path.join(options.mods_dir, book_name + '.mods')
        logger.debug("We have a MODS directory to use {}, look for file {}".format(options.mods_dir, tmpfile))
        if os.path.exists(tmpfile) and os.path.isfile(tmpfile):
            logger.debug("Found file {} and it is a file.".format(tmpfile))
            mods_file = os.path.join(book_dir, 'MODS.xml')
            logger.debug("copy file to {} and set that as mods_file".format(mods_file))
            shutil.copyfile(tmpfile, mods_file)
            logger.debug("Setting up MODS spreader")
        else:
            logger.error("Missing MODS file for {}".format(input_file))

    pages = count_pages(input_file)
    logger.debug("counted {} pages in {}".format(pages, input_file))
    if options.merge and book_number is not None:
        boost = count_subdirectories(book_dir)
        logger.debug("There are already {} directories, boosting page count.".format(boost))
    for p in list(range(1, pages + 1)):
        if options.merge and book_number is not None:
            page_number = p + boost
        else:
            page_number = p
        logger.info("Processing page {}".format(str(page_number)))
        out_dir = os.path.join(book_dir, str(page_number))
        if not os.path.exists(os.path.join(book_dir, str(page_number))):
            logger.debug("Creating directory for page {} in {}".format(page_number, book_dir))
            os.mkdir(os.path.join(book_dir, out_dir))
        if is_pdf.match(input_file):
            new_pdf = get_pdf_page(input_file, p, out_dir)
            if not options.skip_derivatives:
                tiff_file = get_tiff(new_pdf, out_dir)
        else:
            tiff_file = get_tiff_page(input_file, p, out_dir)
        if not options.skip_derivatives:
            derivative_gen.do_page_derivatives(tiff_file, out_dir, input_file=input_file)

        if mods_file is not None:
            logger.debug("We have a mods_file.")
            # Copy mods file and insert
            spreader.make_page_mods(filename=mods_file, output_dir=os.path.join(book_dir, out_dir), page=p)
    if not options.skip_derivatives:
        derivative_gen.do_book_derivatives(input_file, book_dir)


def get_tiff(new_pdf, out_dir):
    """Produce a single page Tiff from a single page PDF

    Keyword arguments
    new_pdf -- The full path to the PDF file
    out_dir -- The directory to save the single page Tiff to
    """
    logger.debug("in get_tiff")
    resolution = options.resolution
    # Increase density by 25%, then resize to only 75%
    altered_resolution = int(resolution * 1.25)
    output_file = os.path.join(out_dir, 'OBJ.tiff')
    if os.path.exists(output_file) and os.path.isfile(output_file) and options.overwrite:
        # Delete the file if it exists AND we set --overwrite
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))

    if not os.path.exists(output_file):
        # Only run if the file doesn't exist.
        logger.debug("Generating Tiff")
        op = ['convert', '-density', str(altered_resolution), new_pdf, '-resize', '75%', '-colorspace', 'rgb', '-alpha',
              'Off', output_file]
        if not Derivatives.do_system_call(op, logger=logger):
            quit()
    return output_file


def get_tiff_page(tiff_file, page_num, out_dir):
    """Produce a single page Tiff from a multi-page Tiff

    Positional arguments:
    tiff_file - multipage tiff
    page_num - page to extract
    out_dir - The directory to save the image to.
    """
    output_file = os.path.join(out_dir, 'OBJ.tiff')
    adjusted_page = page_num - 1
    if os.path.exists(output_file) and os.path.isfile(output_file) and options.overwrite:
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))
    if not os.path.exists(output_file):
        logger.debug("Getting Tiff from multi-page Tiff")
        op = ['convert', '{0}[{1}]'.format(tiff_file, str(adjusted_page)), output_file]
        if not Derivatives.do_system_call(op, logger=logger):
            quit()
    return output_file


def get_pdf_page(pdf, page, out_dir):
    """Produce a single page PDF from a multi-page PDF

    Keyword arguments
    pdf -- The full path to the PDF file
    page -- The page to extract
    out_dir -- The directory to save the single page PDF to

    Returns the path to the new PDF file
    """
    output_file = os.path.join(out_dir, 'PDF.pdf')
    if os.path.exists(output_file) and os.path.isfile(output_file) and options.overwrite:
        # Delete the file if it exists AND we set --overwrite
        os.remove(output_file)
        logger.debug("{} exists and we are deleting it.".format(output_file))

    if not os.path.exists(output_file):
        # Only run if the file doesn't exist.
        logger.debug("Generating PDF for page {}".format(str(page)))
        op = ['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.3',
              '-dAutoRotatePages=/None',
              '-sOutputFile={}'.format(output_file),
              '-dFirstPage={}'.format(str(page)), '-dLastPage={}'.format(str(page)), pdf]
        if not Derivatives.do_system_call(op, logger=logger):
            quit()
    return output_file


def count_pages(input_file):
    """Count the number of pages in a file

    Keyword arguments
    input_file -- the full path to the input file
    """
    count = 0
    if is_pdf.match(input_file):
        with open(input_file, 'rb') as fp:
            count += len(rxcountpages.findall(fp.read()))
        if count == 0:
            pdf_read = PyPDF2.PdfFileReader(input_file)
            count = pdf_read.getNumPages()
            pdf_read = None
    else:
        ops = [
            'identify', '-strip', '-ping', '-format', "%n\\n", input_file
        ]
        results = Derivatives.do_system_call(ops, logger=logger, return_result=True, fail_on_error=False)
        count = int(results.rstrip().split('\n').pop())

    return count


def count_subdirectories(the_dir):
    if os.path.exists(the_dir):
        subdirs = [f for f in os.listdir(the_dir) if os.path.isdir(os.path.join(the_dir, f))]
        return len(subdirs)
    else:
        return 0


def parse_dir(the_dir):
    """Act on all valid files in a directory, not recursing down.

    Keyword arguments
    the_dir -- The full path to the directory to operate on
    """
    files = [f for f in os.listdir(the_dir) if valid_extensions.search(f)]
    processed = list()
    for f in files:
        if f in processed:
            continue
        book_name = os.path.splitext(os.path.split(f)[1])[0]
        if options.merge and re.search(r'\d+$', book_name) is not None:
            (book_name, book_number, junk) = re.split(r'(\d+)$', book_name)
            other_books = [re.split(r'(\d+)(\.)', f) for f in os.listdir(the_dir) if re.match(r'' + book_name + '\d+\.', f)]
            other_books = sorted(other_books, key=lambda x: int(x[1]))
            other_books = [''.join(f) for f in other_books]
            for fx in other_books:
                processed.append(fx)
            # Before we start make sure the target directory is empty
            (book_dir, name, number) = preprocess_file(other_books[0])
            if count_subdirectories(book_dir) > 0:
                mesg = "We are attempting to merge {} files into {} and there are already existing subdirectories. " \
                       "This must be an empty directory".format(len(other_books), book_dir)
                logger.error(mesg)
                print("ERROR: " + mesg)
                quit()
            for same_books in other_books:
                # Process all books together in sequence
                process_file(os.path.join(the_dir, same_books))
        else:
            process_file(os.path.join(the_dir, f))


def set_up(args):
    """Do setup functions

    Keyword arguments
    args -- the ArgumentParser object
    """
    global options, derivative_gen, spreader
    options = args
    setup_log()
    derivative_gen = Derivatives(options, logger)
    spreader = MODSSpreader(logger=logger)
    test_programs = required_programs
    if not options.skip_derivatives and not options.skip_hocr_ocr:
        test_programs.extend(hocr_programs)
    if not options.skip_derivatives and not options.skip_jp2:
        test_programs.extend(jp2_programs)

    try:
        for prog in test_programs:
            subprocess.run([prog.get('exec'), prog.get('check_var')], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
    except FileNotFoundError as e:
        print("A required program could not be found: {}".format(e.strerror.split(':')[1]))
        quit()


def setup_log():
    """Setup logging"""
    global logger
    logger = logging.getLogger('multipage2book')
    logger.propogate = False
    # Logging Level 
    eval('logger.setLevel(logging.{})'.format(options.debug_level))
    filename = os.path.join(os.getcwd(), 'multipage2book.log')
    fh = logging.FileHandler(filename, 'w', 'utf-8')
    formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)


def format_time(seconds):
    """Format seconds """
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%d:%02d:%02d" % (h, m, s)


def main():
    """The main body of code"""
    start_time = time.perf_counter()

    parser = argparse.ArgumentParser(
        description='Turn a PDF/Tiff or set of PDFs/Tiffs into properly formatted directories for Islandora Book Batch.')
    parser.add_argument('files', help="A file or directory of files to process.")
    parser.add_argument('--password', dest="password", default='', help='Password to use when parsing PDFs.')
    parser.add_argument('--overwrite', dest="overwrite", action='store_true', default=False,
                        help='Overwrite any existing Tiff/PDF/OCR/Hocr files with new copies.')
    parser.add_argument('--language', dest="language", default='eng',
                        help="Language of the source material, used for OCRing. Defaults to eng.")
    parser.add_argument('--resolution', dest="resolution", type=int, default=300,
                        help="Resolution of the source material, used when generating Tiff. Defaults to 300.")
    parser.add_argument('--use-hocr', dest="use_hocr", action='store_true', default=False,
                        help='Generate OCR by stripping HTML characters from HOCR, otherwise run tesseract a second '
                             'time. Defaults to use tesseract.')
    parser.add_argument('--mods-dir', dest="mods_dir", default=None,
                        help='Directory of files with a matching name but with the extension ".mods" to be added to '
                             'the books.')
    parser.add_argument('--output-dir', dest="output_dir", default=".",
                        help="Directory to build books in, defaults to current directory.")
    parser.add_argument('--merge', dest="merge", action='store_true', default=False,
                        help='Files that have the same name but with a numeric suffix are considered the '
                             'same book and directories are merged. (ie. MyBook1.pdf and MyBook2.pdf)')
    parser.add_argument('--skip-derivatives', dest="skip_derivatives", action='store_true', default=False,
                        help='Only split the source file into the separate pages and directories, don\'t generate '
                             'derivatives.')
    parser.add_argument('--skip-hocr-ocr', dest="skip_hocr_ocr", action='store_true', default=False,
                        help='Do not generate OCR/HOCR datastreams, this cannot be used with --skip-derivatives')
    parser.add_argument('--skip-jp2', dest="skip_jp2", action='store_true', default=False,
                        help='Do not generate JP2 datastreams, this cannot be used with --skip-derivatives')
    parser.add_argument('-l', '--loglevel', dest="debug_level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='ERROR', help='Set logging level, defaults to ERROR.')
    args = parser.parse_args()

    if not args.files[0] == '/':
        # Relative filepath
        args.files = os.path.join(os.getcwd(), args.files)

    if args.mods_dir is not None:
        if not args.mods_dir[0] == '/':
            # Relative directory
            args.mods_dir = os.path.abspath(args.mods_dir)
        if not (os.path.exists(args.mods_dir) or os.path.isdir(args.mods_dir)):
            parser.error("--mods-dir was not found or is not a directory.")
            quit()
    if args.merge and args.overwrite:
        parser.error("--merge and --overwrite are mutually exclusive options, you can only use one at a time.")

    if args.merge:
        print("Warning: merge attempts to combine multiple files that start with the same name and end with a digit "
              "before the extension. Files are sorted by the number and require an empty starting directory. If the "
              "expected directory contains files, it will halt with a warning.")
        input("Press any key to proceed")

    if not os.path.exists(args.output_dir):
        os.mkdir(args.output_dir)

    if os.path.isfile(args.files) and valid_extensions.match(args.files):
        set_up(args)
        process_file(args.files)
    elif os.path.isdir(args.files):
        set_up(args)
        parse_dir(args.files)
    else:
        parser.error("{} could not be resolved to a directory or a PDF file".format(args.files))

    total_time = time.perf_counter() - start_time
    print("Finished in {}".format(format_time(total_time)))


if __name__ == '__main__':
    main()
    quit()
