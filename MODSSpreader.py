#!/usr/bin/env python3

import sys
import argparse
import lxml.etree as ET
import os
import logging
import copy
import re
import shutil


directory_regexp = re.compile(r'^\d+$')


class MODSSpreader:

    logger = None

    page_title_regexp = re.compile(r'\sPage\s*\(?\s*\d+\s*\)?\s*$')

    def __init__(self, logger=None):
        if logger is None:
            self.setup_console_logger()
        else:
            self.logger = logger

    def setup_console_logger(self):
        """Setup logging"""
        self.logger = logging.getLogger('multipage2book')
        self.logger.propogate = False
        # Logging Level
        self.logger.setLevel(logging.INFO)
        filename = os.path.join(os.getcwd(), 'spreadMODS.log')
        fh = logging.FileHandler(filename, 'w', 'utf-8')
        formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def make_page_mods(self, filename, output_dir, page):
        """Using a Book level MODS record insert the relatedItem/part information

        Keyword arguments
        filename -- The filename of the top level MODS file
        output_dir -- The page level directory to save the MODS to
        page -- The page number"""
        mods_namespace = '{http://www.loc.gov/mods/v3}'
        self.logger.debug("In make_page_mods")
        if os.path.exists(filename) and os.path.isfile(filename):
            self.logger.debug("Have file {}".format(filename))
            try:
                tree = ET.parse(filename)
            except:
                self.logger.error("Error parsing MODS in file {}: {}".format(filename, sys.exc_info()[0]))
                return
            related = tree.find("{0}relatedItem[@type=\"host\"]".format(mods_namespace))
            if related is None:
                root = tree.getroot()
                related = ET.SubElement(root, "{0}relatedItem".format(mods_namespace), {'type': 'host'})
            if related.find("./{0}titleInfo/{0}title".format(mods_namespace)) is None:
                title = tree.find("./{0}titleInfo/{0}title".format(mods_namespace))
                if title is None:
                    self.logger.warning("Unable to locate the title page {}".format(page))
                else:
                    tmp = ET.Element("{0}titleInfo".format(mods_namespace))
                    tmp.append(copy.deepcopy(title))
                    related.append(tmp)
                    self.logger.debug("Copied titleInfo to relatedItem, now add page number to top level titleInfo/title")
                    title.text = title.text + ' (Page {})'.format(page)
            part = related.find("./{0}part".format(mods_namespace))
            if part is None:
                part = ET.SubElement(related, '{0}part'.format(mods_namespace))
            extent = part.find("./{0}extent[@unit=\"pages\"]".format(mods_namespace))
            if extent is None:
                extent = ET.SubElement(part, "{0}extent".format(mods_namespace), {'unit': 'pages'})
            start = extent.find("./{0}start".format(mods_namespace))
            if start is not None:
                start.getparent().remove(start)
            start = ET.SubElement(extent, '{0}start'.format(mods_namespace))
            start.text = str(page)
            end = extent.find('./{0}end'.format(mods_namespace))
            if end is not None:
                end.getparent().remove(end)
            end = ET.SubElement(extent, '{0}end'.format(mods_namespace))
            end.text = str(page)
            # Remove the book level page count
            phys_desc = tree.find("./{0}physicalDescription/{0}extent[@unit=\"pages\"]".format(mods_namespace))
            if phys_desc is not None:
                phys_desc.getparent().remove(phys_desc)

            try:
                tree.write(os.path.join(output_dir, 'MODS.xml'), encoding='utf-8', xml_declaration=True, method='xml')
            except IOError as e:
                self.logger.error("Error writing out page level MODS to directory {}: {}".format(output_dir, e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage="spreadMODS <source MODS> <directory of pages>",
                                     description="Take a book/newspaper issue level MODS and make modifications and save to page directories.")
    parser.add_argument('source_mods', help="The book/newspaper issue level MODS record.")
    parser.add_argument('page_directory', help="A directory containing the page level directories (named 1, 2, 3, etc)")
    args = parser.parse_args()
    args.source_mods = os.path.realpath(args.source_mods)
    args.page_directory = os.path.realpath(args.page_directory)

    if not os.path.exists(args.source_mods):
        parser.error("File {} does not exist".format(args.source_mods))
    if not os.path.exists(args.page_directory) or not os.path.isdir(args.page_directory):
        parser.error("{} does not exist or is not a directory".format(args.page_directory))
    pages = list()
    with os.scandir(args.page_directory) as it:
        for item in it:
            if os.path.isdir(item.path) and directory_regexp.match(item.name):
                pages.append(item)
    if len(pages) > 0:
        spreader = MODSSpreader()
        pages.sort(key=lambda x: x.name, reverse=False)
        for page in pages:
            spreader.make_page_mods(args.source_mods, page.path, int(page.name))
        # Copy the source to the top-level as the MODS.xml
        shutil.copy(args.source_mods, os.path.join(args.page_directory, 'MODS.xml'))
