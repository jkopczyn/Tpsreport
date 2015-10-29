from __future__ import division
from colour import Color
from bs4 import BeautifulSoup
import copy
import os

# This file generates HSV-based recolorizations of logo.html for the purposes
# of testing color schemes. Huerange is a range of hues to check, Lumrange
# is a range of luminosities to check.

Humrange = range(280, 291, 10)
Lumrange = range(90, 160, 5)


def fileToStr(fileName):
    """Return a string containing the contents of the named file."""
    fin = open(fileName)
    contents = fin.read()
    fin.close()
    return contents

if os.path.isfile("blah.html"):
    os.remove("blah.html")


with open("blah.html", "a+") as blah:
    blah.write("""<html>
                <head>
                <style>
                table {display: inline}
                </style>
                </head>
                <body>""")

document = open("logo.html")
soup = BeautifulSoup(document, "html.parser")
for hues in Humrange:
    for lums in Lumrange:
        itersoup = copy.copy(soup)
        for tag in itersoup.find_all("td"):
            try:
                col = Color(tag['bgcolor'])
            except KeyError:
                continue
            col.hue = hues/360
            colold = copy.copy(col)
            colold.saturation = max(1, col.luminance * lums / 300)
            col.luminance = min(1, col.luminance * lums / 100)
            if col.luminance == 1:
                col = colold
            tag["bgcolor"] = col.hex_l

        with open("blah.html", "a+") as blah:
            blah.write("<!--{0} hue, {1} lums -->".format(
                    str(hues), str(lums)))
            blah.write(str(itersoup))
        print "wrote", hues, lums


os.startfile("blah.html")
