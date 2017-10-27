### Summary

This script takes one or more multi-page PDFS or Tiffs and generates the directory structure necessary to ingest it into an Islandora instance as a book object.

It assumes that your source objects contain the entirity of a single book.

### Installation

This script was written using Python 3 but it should also be compatible with Python 2.7.

1. Clone the this repository
1. Install dependencies `pip (or pip3) install -r requirements.txt`
1. Run

To run this script **requires** the existance of:

* ghostscript
* Imagemagick convert
* Imagemagick identify

in the working PATH.

It also needs **tesseract** and **kdu\_compress** unless you specify the `--skip-derivatives` option.

### Contents

This repository contains scripts.

1. multipage2book.py - this is the main script which does the bulk of the work in generating your book object
1. hocrpdf.py - this is a standalone script and a class to create a searchable PDF out of an image file and a HOCR file.

### Usage

The script takes the file or a directory of files for each file it creates a clean directory name of the file, with spaces replaced by underscores and the word `_dir` at the end.

ie. The Heart of the Continent.tiff --> The\_Heart\_of\_the\_Continent\_dir

If you provide the `--mods-dir` option, it should point to a directory containing MODS files with the same name as the source file but with a `.mods` extension. (ie. The\_Heart\_of\_the\_Continent.mods)

### Configuration options

Running the `multipage2book.py` with a `-h` or `--help` argument will get you a description of the possible options.

```
usage: multipage2book.py [-h] [--password PASSWORD] [--overwrite]
                         [--language LANGUAGE] [--resolution RESOLUTION]
                         [--use-hocr] [--mods-dir MODS_DIR]
                         [--output-dir OUTPUT_DIR] [--skip-derivatives]
                         [-d {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                         files

Turn a PDF/Tiff or set of PDFs/Tiffs into properly formatted directories for
Islandora Book Batch.

positional arguments:
  files                 A file or directory of files to process.

optional arguments:
  -h, --help            show this help message and exit
  --password PASSWORD   Password to use when parsing PDFs.
  --overwrite           Overwrite any existing Tiff/PDF/OCR/Hocr files with
                        new copies.
  --language LANGUAGE   Language of the source material, used for OCRing.
                        Defaults to eng.
  --resolution RESOLUTION
                        Resolution of the source material, used when
                        generating Tiff. Defaults to 300.
  --use-hocr            Generate OCR by stripping HTML characters from HOCR,
                        otherwise run tesseract a second time. Defaults to use tesseract.
  --mods-dir MODS_DIR   Directory of files with a matching name but with the
                        extension '.mods' to be added to the books.
  --output-dir OUTPUT_DIR
                        Directory to build books in, defaults to current
                        directory.
  --skip-derivatives    Only split the source file into the separate pages and
                        directories, don't generate derivatives.
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set logging level, defaults to ERROR.
```

#### Caveat

The `hocrpdf.py` class is included in such a way that if you specify a `--loglevel` level of `DEBUG` searchable PDFs generate will have the text visibly written over the image. Only use this setting for debugging, never for production.

### Searchable PDFs

You can also use the `hocrpdf.py` script separately as a script or an importable module into your own Python code. It takes an image that Pillow can read (GIF, JPEG, JP2, PNG) and an HOCR of that file and creates a PDF with the image as the background and writes the words in the appropriate coordinates without rendering them (ie. make them invisible).

This is a modification/rewrite of [hocr-pdf](https://github.com/tmbdev/hocr-tools/blob/master/hocr-pdf) from  [tmbdev](https://github.com/tmbdev).

It has been modified to:

1. make it a class for inclusion in other code
1. modifications to the [calculation of the word box base](https://github.com/tmbdev/hocr-tools/blob/master/hocr-pdf#L103-L104)
1. changed from using [`setTextOrigin()`](https://github.com/tmbdev/hocr-tools/blob/master/hocr-pdf#L108) to using `setTextTransform()` to assign the rotation of the box.
1. stopped using the included invisible font.
1. set the font height to match the box height to get better word highlighting.
1. switched from `lxml.etree` library to `xml.etree` library

### Maintainer

[Jared Whiklo](https://github.com/whikloj)

### License

* [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) 