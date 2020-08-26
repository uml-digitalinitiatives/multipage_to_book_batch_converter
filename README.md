## Summary

This script takes one or more multi-page PDFS or Tiffs and generates the directory structure necessary to ingest it into an Islandora instance as a book object.

It assumes that your source objects contain the entirety of a single book.

## Installation

This script requires Python 3.

1. Clone the this repository
1. Install dependencies `pip (or pip3) install -r requirements.txt`
1. Run

To run this script **requires** the existence of:

* ghostscript
* Imagemagick convert
* Imagemagick identify

in the working PATH.

It also needs:
 
* **tesseract** unless you specify the `--skip-hocr-ocr` option
* **kdu\_compress** unless you specify the `--skip-jp2` option

If you specify the `--skip-derivatives` option, neither is required.

## multipage2book.py

This is the main script which does the bulk of the work in generating your book object.

The script takes the file or a directory of files for each file it creates a clean directory name of the file, with 
spaces replaced by underscores and the word `_dir` at the end.

ie. The Heart of the Continent.tiff --> The\_Heart\_of\_the\_Continent\_dir

If you provide the `--mods-dir` option, it should point to a directory containing MODS files with the same name as the 
source file but with a `.mods` extension. (ie. The\_Heart\_of\_the\_Continent.mods).

**Note:** You can alter the MODS file extension with the `--mods-extension` argument.

If you don't provide a `--mods-dir` option but your `files` argument is a directory, then that same directory will be
checked for MODS files.

### Configuration options

Running the `multipage2book.py` with a `-h` or `--help` argument will get you a description of the possible options.

```
usage: multipage2book.py [-h] [--password PASSWORD] [--overwrite] [--language LANGUAGE] [--resolution RESOLUTION] [--use-hocr] [--mods-dir MODS_DIR] [--mods-extension MODS_EXTENSION]
                         [--output-dir OUTPUT_DIR] [--merge] [--skip-derivatives] [--skip-hocr-ocr] [--skip-jp2] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                         files

Turn a PDF/Tiff or set of PDFs/Tiffs into properly formatted directories for Islandora Book Batch.

positional arguments:
  files                 A file or directory of files to process.

optional arguments:
  -h, --help            show this help message and exit
  --password PASSWORD   Password to use when parsing PDFs.
  --overwrite           Overwrite any existing Tiff/PDF/OCR/Hocr files with new copies.
  --language LANGUAGE   Language of the source material, used for OCRing. Defaults to eng.
  --resolution RESOLUTION
                        Resolution of the source material, used when generating Tiff. Defaults to 300.
  --use-hocr            Generate OCR by stripping HTML characters from HOCR, otherwise run tesseract a second time. Defaults to use tesseract.
  --mods-dir MODS_DIR   Directory of files with a matching name but with the extension "mods" to be added to the books.
  --mods-extension MODS_EXTENSION
                        The extension of the MODS files existing in the above directory. Files are matched based on filename but with this extension. Defaults to 'mods'
  --output-dir OUTPUT_DIR
<<<<<<< Updated upstream
                        Directory to build books in, defaults to current
                        directory.
  --merge               Files that have the same name but with a numeric
                        suffix are considered the same book and directories
                        are merged. (ie. MyBook1.pdf and MyBook2.pdf)
  --skip-derivatives    Only split the source file into the separate pages and
                        directories, don't generate derivatives.
  --mods-extension      The extension for the MODS files in your source directory.
                        Either 'mods' or 'xml'. Defaults to 'mods'.
=======
                        Directory to build books in, defaults to current directory.
  --merge               Files that have the same name but with a numeric suffix are considered the same book and directories are merged. (ie. MyBook1.pdf and MyBook2.pdf)
  --skip-derivatives    Only split the source file into the separate pages and directories, don't generate derivatives.
  --skip-hocr-ocr       Do not generate OCR/HOCR datastreams, this cannot be used with --skip-derivatives
  --skip-jp2            Do not generate JP2 datastreams, this cannot be used with --skip-derivatives
>>>>>>> Stashed changes
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --loglevel {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set logging level, defaults to ERROR.
```

### Examples

1. Process a PDF file into the correct directory structure with just each PDF page split out.
   ```shell script
   ./multipage2book.py --output-dir=OUTPUT --skip-derivatives MyBook.pdf 
   ```

   This creates the following structure
    ```
    OUTPUT/
          MyBook_dir/
                     PDF.pdf
                     1/
                       PDF.pdf
                     2/
                       PDF.pdf
                     ...
    ```

2. Process a PDF file into the correct directory structure with simple derivatives from the source.
    ```shell
    ./multipage2book.py --output-dir=OUTPUT --skip-hocr-ocr --skip-jp2 MyBook.pdf 
    ```
    
    This creates the following structure
    ```
    OUTPUT/
          MyBook_dir/
                     PDF.pdf
                     TN.jpg
                     1/
                       OBJ.tiff
                       PDF.pdf
                       JPG.jpg
                       TN.jpg
                     2/
                       OBJ.tiff
                       PDF.pdf
                       JPG.jpg
                       TN.jpg
                     ...
    ```

3. Process a PDF file into the correct directory structure processing the MODS file down to the pages.

    Assuming a directory called "INPUT"
    ```shell script
    INPUT/
          MyPDF.pdf
          MyPDF.xml
    ```
    Then calling:
    ```shell script
    ./multipage2book.py INPUT --output-dir=/output/directory --skip-hocr-ocr --skip-jp2 --mods-extension=xml 
    ```
    
    This creates the following structure
    ```
    OUTPUT/
          MyPDF_dir/
                     PDF.pdf
                     MODS.xml
                     TN.jpg
                     1/
                       JPG.jpg
                       MODS.xml
                       OBJ.tiff
                       PDF.pdf
                       TN.jpg
                     2/
                       JPG.jpg
                       MODS.xml
                       OBJ.tiff
                       PDF.pdf
                       TN.jpg
                     ...
    ```
1. The `--merge` option is useful, but problematic. Its use case is when a single Tiff could not hold all the pages of 
a book. In which case so long as the various files share a common basename but with an integer appended. 
(ie. SomeBook1.tiff, SomeBook2.tiff, SomeBook3.tiff). These books will all be combined into a single set of pages.

   Normally you can process a book overtop of a previous run, the script will just fill in the missing parts. However 
   the `--merge` option requires that there **NOT** be a book directory in the output directory. Because we are adding
   pages we can't guarantee correct order and numbering unless it starts fresh each time.
    
   Also any MODS file must match the filename **WITHOUT** the numeric extension. 
    
   ie. `MyTitle1.tiff -> MyTitle.mods`
    
   Assuming an "INPUT" directory containing 3 files each with 10 pages
   ```text
   INPUT/
          MyBook1.tiff
          MyBook2.tiff
          MyBook3.tiff
          MyBook.mods
   ```
   
   we process them with
   ```text
   ./multipage2book.py INPUT --output-dir=OUTPUT --merge --skip-derivatives
   Warning: merge attempts to combine multiple files that start with the same name and end with a digit before the extension. Files are sorted by the number and require an empty starting directory. If the expected directory contains files, it will halt with a warning.
   Press any key to proceed
   ```
   
   The output directory would look like
   ```text
   OUTPUT/
          MyBook_dir/
                     MODS.xml
                     1/
                       OBJ.tiff
                       MODS.xml
                     2/
                       OBJ.tiff
                       MODS.xml
                     ...
                     29/
                       OBJ.tiff
                       MODS.xml
                     30/
                       OBJ.tiff
                       MODS.xml
    ```

## Caveat

The `hocrpdf.py` class is included in such a way that if you specify a `--loglevel` level of `DEBUG`, any searchable 
PDFs generated will have the text visibly written over the page image. Only use this setting for debugging, never for 
production.

## Other scripts

Along with `multipage2book.py` there are several support classes that can be run as standalone scripts. These are:
* `Derivatives.py` - generate derivatives for a directory or set of directories.
* `MODSSpreader.py` - copy/alter a MODS files for each page of a paged content item.
* `hocrpdf.py` - generate a searchable PDF using an image (JP2, JPG) and an hOCR file. 

All of these scripts have usage arguments that can be revealed by running them with the `-h` or `--help` argument. 

## Acknowledgements

`hocrpdf.py` is a modification/rewrite of [hocr-pdf](https://github.com/tmbdev/hocr-tools/blob/master/hocr-pdf) from  
[tmbdev](https://github.com/tmbdev).

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
