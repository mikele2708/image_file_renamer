#renaming JPG, JPEG and NEF files in a given Source directory by exif_date

import os.path
import ntpath
from time import localtime, strftime, strptime, mktime
import shutil
import exifread


#fetching date of creation in exif data
def getMinimumCreationTime(exif_data):
    creationTime = None
    dateTime = exif_data.get('DateTime')
    dateTimeOriginal = exif_data.get('EXIF DateTimeOriginal')
    dateTimeDigitized = exif_data.get('EXIF DateTimeDigitized')

    # 3 differnt time fields that can be set independently result in 9 if-cases
    if (dateTime is None):
        if (dateTimeOriginal is None):
            # case 1/9: dateTime, dateTimeOriginal, and dateTimeDigitized = None
            # case 2/9: dateTime and dateTimeOriginal = None, then use dateTimeDigitized
            creationTime = dateTimeDigitized
        else:
            # case 3/9: dateTime and dateTimeDigitized = None, then use dateTimeOriginal
            # case 4/9: dateTime = None, prefere dateTimeOriginal over dateTimeDigitized
            creationTime = dateTimeOriginal
    else:
        # case 5-9: when creationTime is set, prefere it over the others
        creationTime = dateTime

    return creationTime

#getting arguments in terminal command code
def get_args():
    import argparse

    description = (
        "Renaming jpeg-files based on creation Date of Exif-Dates.\n"
        "Certain patterns will be excluded."
        "The input files will remain at their destination.\n"
    )

    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('source', metavar='src', type=str, help='source directory with files recovered by routine')
    #parser.add_argument('destination', metavar='dest', type=str, help='destination directory to write sorted files to')
    parser.add_argument('-n', '--max-per-dir', type=int, default=100000, required=False, help='maximum number of files per directory')

    return parser.parse_args()


maxNumberOfFilesPerFolder = 100000
source = None
destination = None

args = get_args()
source = args.source
#destination = args.destination
maxNumberOfFilesPerFolder = args.max_per_dir

#key routine to rename
fileCounter = 0
for root, dirs, files in os.walk(source, topdown=False):

    for file in files:
        extension = os.path.splitext(file)[1][1:].upper()
        sourcePath = os.path.join(root, file)
        coreFilename = os.path.splitext(file)[0]

        filepatterns = ['IMG', 'CIMG', 'P10', 'DSC', 'CSC', '_DSC']


        #destinationDirectory = os.path.join(destination, extension)

        if extension == "JPG" or extension == "JPEG" or extension == "NEF":
            #match-Argument aufbauen mit den Pattern IMG, P100, DSC, CIM --> dann renaming starten
            if coreFilename[:3] in filepatterns or coreFilename[:4] in filepatterns:
                image = open(sourcePath, 'rb')
                exifTags = exifread.process_file(image, details=False)
                creationTime = getMinimumCreationTime(exifTags)
                image.close()

                creationTime = strptime(str(creationTime), "%Y:%m:%d %H:%M:%S")
                t = localtime(mktime(creationTime))
                newFilename = strftime("%Y%m%d_%H%M%S", t) +'.'+ extension

                destinationFile = os.path.join(root, newFilename)
                if not os.path.exists(destinationFile):
                    os.rename(sourcePath, destinationFile)
                    fileCounter += 1
                else:
                    i = 1
                    while os.path.exists(destinationFile):
                        newFilename = strftime("%Y%m%d_%H%M%S", t)+'_'+ str(i) +'.'+ extension
                        destinationFile = os.path.join(root, newFilename)
                        i += 1
                    os.rename(sourcePath, destinationFile)
                    fileCounter += 1
            else:
                continue
        else:
            continue

print("I've' renamed",fileCounter,"JPG, JPEG, or NEF files for you." )
