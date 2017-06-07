#!/usr/bin/python
# coding: utf-8

# TODO: add functionality for multi-part assemblies
# TODO: customUI; inputTemplate, outputTemplate

import uuid
import re
import time
import sys
import zipfile
import os
import urllib
import json
import xml.etree.cElementTree as ET
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from OCC.Bnd import Bnd_Box
from OCC.BRepBndLib import brepbndlib_Add
from OCC.GProp import GProp_GProps
from OCC.BRepGProp import (brepgprop_LinearProperties,
                           brepgprop_SurfaceProperties,
                           brepgprop_VolumeProperties)
from tdpUtility import import_step, FILENAME, SNAPSHOTS_FILE

OUTPUT_TEMPLATE = "<div class=\"project-run-services padding-10\" ng-if=\"!runHistory\" layout=\"column\">          <style>            #custom-dome-UI {             margin-top: -30px;           }          </style>            <div id=\"custom-dome-UI\">             <div layout=\"row\" layout-wrap style=\"padding: 0px 30px\">               <h2>Technical Data Package Created Successfully:</h2>               <p><a href=\"{{outputFile}}\">{{outputFile}}</a></p>             </div>           </div>        </div>   <script> </script>"

TOLERANCE = 1e-6

# Unit: kg/m^3
DENSITIES = {
    "": 1,
    "Steel": 8000,
    "Aluminum": 2700
}

UNIT_FACTOR = {
    "units": 1,
    "m": 1,
    "cm": .01,
    "mm": .001
}

def exit_app(outtext, status_code=0):
    outfile = open('out.txt', 'w')
    outfile.write("outputFile=" + outtext)
    outfile.write("\noutputTemplate=" + OUTPUT_TEMPLATE)
    outfile.close()
    sys.exit(0)

class GpropsFromShape(object):
    def __init__(self, shape, tolerance=1e-5):
        self.shape = shape
        self.tolerance = tolerance

    def volume(self):
        '''returns the volume of a solid
        '''
        prop = GProp_GProps()
        brepgprop_VolumeProperties(self.shape, prop, self.tolerance)
        return prop

    def surface(self):
        '''returns the area of a surface
        '''
        prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.shape, prop, self.tolerance)
        return prop

    def linear(self):
        '''returns the length of a wire or edge
        '''
        prop = GProp_GProps()
        brepgprop_LinearProperties(self.shape, prop)
        return prop

def get_boundingbox(shape, tol=TOLERANCE):
    '''
    :param shape: TopoDS_Shape such as TopoDS_Face
    :param tol: tolerance
    :return: xmin, ymin, zmin, xmax, ymax, zmax
    '''
    bbox = Bnd_Box()
    bbox.SetGap(tol)
    brepbndlib_Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return xmin, ymin, zmin, xmax, ymax, zmax

class stp_header_parser():

    def stp_header_parser(self, stp_filename='', is_debug=False):

        def get_unit_abbr(units):
            prefix = {'MILLI': 'm'}
            unit = {'METRE': 'm'}
            return prefix[units[0]]+unit[units[1]]

        def remove_comments(line):
            comment_pattern = re.compile('/\*.*?\*/')
            return comment_pattern.sub('', line)

        def line_extract(filehandle=None, str_startswith='', str_endswith=''):

            while True:

                line = filehandle.readline().strip()
                #if line.startswith(str_startswith):

                if not line:
                    break

                if str_startswith in line:
                    line_extracted = ''
                    while True:
                        line_extracted += line
                        if line.endswith(str_endswith):
                            break
                        else:
                            line = filehandle.readline().strip()

                    return line_extracted

        infos_name = [
            'ISO Standard',
            'Description',
            'Implementation Level',
            'Name',
            'Time_Stamp',
            'Author',
            'Organization',
            'Preprocessor Version',
            'Originating System',
            'Authorization',
            'Schema',
            'Unit'
        ]

        infos_value = []

        len_infos_name = len(infos_name)

        with open(stp_filename, 'r') as f:

            line = line_extract(f, 'ISO-', ';')

            if line:
                ISO_Standard = line[:-1]
                infos_value.append(ISO_Standard)

            line = line_extract(f, 'HEADER', ';')

            if line:
                if is_debug:
                    print('>>> Header Start Mark Found <<<')

                line = line_extract(f, 'FILE_DESCRIPTION', ';')
                line = remove_comments(line)
                File_Description = eval(line[16:-1])
                infos_value += File_Description

                line = line_extract(f, 'FILE_NAME', ';')
                line = remove_comments(line)
                File_Name = eval(line[9:-1])
                infos_value += File_Name

                line = line_extract(f, 'FILE_SCHEMA', ';')
                line = remove_comments(line)
                File_Schema = eval(line[11:-1])
                infos_value.append(File_Schema)

                if line_extract(f, 'ENDSEC', ';'):
                    if is_debug:
                        print('>>> Header End Mark Found <<<')

            while True:
                line = line_extract(f, 'LENGTH_UNIT', ';')
                if not line:
                    break
                units = line.split('SI_UNIT')
                if(len(units) == 2):
                    units = units[1].split('.')[1:4:2]
                    units = get_unit_abbr(units)
                    infos_value.append(units)
                    break


        infos_dict = {
            index: list(parameter) for (
                index, parameter) in zip(
                range(len_infos_name), zip(
                    infos_name, infos_value))}

        if is_debug:
            for key in infos_dict:
                print('{:02}\t{}'.format(key, infos_dict[key]))

        return infos_dict

def get_dome_inputs():
    with open('in.txt') as f:
        lines = f.readlines()

    inputs = {}

    for line in lines:
        kv = line.rstrip().split("=")
        key = kv.pop(0).strip()
        value = "=".join(kv).strip()
        inputs[key] = value

    return inputs

def validate_inputs(inputFile, material, coatings):
    assert(inputFile)
    assert(material in DENSITIES)
    assert(coatings)

def get_tdp_inputs():
    print "Getting TDP inputs..."

    try:
        inputs = get_dome_inputs()
        inputFile = inputs["inputFile"]
        material = inputs["material"]
        coatings = inputs["coatings"]
    except:
        exit_app("Error parsing inputs.", status_code=1)
        sys.exit()

    try:
        validate_inputs(inputFile, material, coatings)
    except:
        exit_app("One or more of the inputs is not valid.", status_code=1)
        sys.exit()

    return inputFile, material, coatings

def download_stp_file(url, filename):
    print "Downloading STP file..."
    try:
        urllib.urlretrieve(url, filename)
    except:
        exit_app("Unable to download STP file.", status_code=1)

def upload_zip(zipfile):
    print "Uploading zipfile..."

    try:
        timestamp = int(time.time())

        with open('aws.json') as json_data:
            aws = json.load(json_data)
            access_key = aws['accessKeyId']
            secret_key = aws['secretAccessKey']

        conn = S3Connection(access_key, secret_key)
        bucket = conn.get_bucket('psubucket01')

        k = Key(bucket)
        k.key = zipfile
        k.set_contents_from_filename('./'+zipfile)

        return conn.generate_url(
            expires_in=long(1209600),
            method='GET',
            bucket='psubucket01',
            key=k.key,
            query_auth=True,
        )
    except:
        exit_app("Error uploading zipfile.", status_code=1)

def get_metadata(filename, material, coatings):
    print "Gathering metatdata from STP file..."

    try:
        header = stp_header_parser()
        header = header.stp_header_parser(stp_filename=filename)
        metadata = {'name': header[3][1], 'material': material, 'coatings': coatings, 'unit': header[11][1]}
    except:
        exit_app("Error gathering metadata from STP file.", status_code=1)

    return metadata

# def import_step(filename):
#     print "Importing shapes from STP file..."
#
#     try:
#         my_importer = aocxchange.step.StepImporter(filename)
#         assert(len(my_importer.shapes))
#         print str(len(my_importer.shapes)) + " shapes loaded..."
#     except:
#         exit_app("Error importing shapes from STP file.", status_code=1)
#
#     return my_importer.shapes[0]

def get_geometry(shape, material, unit="units"):
    print "Calculating geometry..."

    try:
        boundingbox_points = get_boundingbox(shape)
        length = boundingbox_points[3] - boundingbox_points[0]
        height = boundingbox_points[5] - boundingbox_points[2]
        width = boundingbox_points[4] - boundingbox_points[1]

        gprop = GpropsFromShape(shape)
        volume = gprop.volume().Mass()
        density = DENSITIES[material]
        mass = volume*density*pow(UNIT_FACTOR[unit], 3)
        surface_area = gprop.surface().Mass()
    except:
        exit_app("Error calculating geometry.", status_code=1)

    return {'length': length, 'height': height, 'width': width, 'volume': volume, 'mass': mass, 'surface_area': surface_area}

def generate_xml(metadata, geometry):
    print "Generating xml..."

    try:
        part_id = str(uuid.uuid4())
        instance_id = str(uuid.uuid4())

        mBOM = ET.Element("mBOM", version="2.0")
        parts = ET.SubElement(mBOM, "parts")
        part = ET.SubElement(parts, "part", id=part_id)
        ET.SubElement(part, "name").text = metadata["name"]
        ET.SubElement(part, "length", unit=metadata["unit"]).text = str(geometry["length"])
        ET.SubElement(part, "height", unit=metadata["unit"]).text = str(geometry["height"])
        ET.SubElement(part, "width", unit=metadata["unit"]).text = str(geometry["width"])
        ET.SubElement(part, "surface_area", unit=metadata["unit"]+"2").text = str(geometry["surface_area"])
        ET.SubElement(part, "volume", unit=metadata["unit"]+"3").text = str(geometry["volume"])
        ET.SubElement(part, "weight", unit="kg").text = str(geometry["mass"])
        instances = ET.SubElement(part, "instances")
        ET.SubElement(instances, "instance", instance_id=instance_id)
        manufacturingDetails = ET.SubElement(part, "manufacturingDetails")
        ET.SubElement(manufacturingDetails, "material").text = metadata["material"]
        ET.SubElement(manufacturingDetails, "coatings").text = metadata["coatings"]
        assemblies = ET.SubElement(mBOM, "assemblies")
    except:
        exit_app("Error generating xml.", status_code=1)

    return mBOM

# def generate_snapshots(shape):
#     print "Generating snapshots..."
#
#     try:
#         app = QtWidgets.QApplication(sys.argv)
#         widget = QtWidgets.QWidget()
#         widget.resize(1000,1000)
#         view = Viewer3d(int(widget.winId()))
#         view.Create()
#         view.SetModeShaded()
#         view.DisplayShape(shape, update=True)
#
#         VIEW_FUNC = {
#             "front": view.View_Front,
#             "rear": view.View_Rear,
#             "top": view.View_Top,
#             "bottom": view.View_Bottom,
#             "left": view.View_Left,
#             "right": view.View_Right,
#             "iso": view.View_Iso
#         }
#
#         snapshots = []
#
#         for view_type in VIEWS:
#             VIEW_FUNC[view_type]()
#             view.ExportToImage('capture.ppm')
#             im = Image.open('capture.ppm')
#             snapshot = view_type + '_capture.png'
#             im.save(snapshot)
#             snapshots.append(snapshot)
#     except:
#         exit_app("Error generating snapshots.", status_code=1)
#
#     return snapshots

def get_snapshots():
    try:
        return_val = os.system("xvfb-run -a --server-args='-screen 0 1360x768x24' /home/dmcAdmin/anaconda2/bin/python generateSnapshots.py")
        #return_val = os.system("xvfb-run -a --server-args='-screen 0 1360x768x24' python generateSnapshots.py")
        print("return val = " + str(return_val))
        assert(not return_val)

        with open(SNAPSHOTS_FILE) as f:
            lines = f.readlines()

        snapshots = []
        for snapshot in lines:
            snapshots.append(snapshot.rstrip('\n'))

        return snapshots
    except:
        exit_app("Error generating snapshots.", status_code=1)

def generate_zip(xml, filename, snapshots):
    print "Generating zipfile..."

    try:
        file_id = int(time.time())
        zip_filename = 'TDP_' + str(file_id) + '.zip'

        tree = ET.ElementTree(xml)
        xml_file = "TDP_" + str(file_id) + ".xml"
        tree.write(xml_file)

        with zipfile.ZipFile(zip_filename, 'w') as myzip:
            myzip.write(filename)
            myzip.write(xml_file)
            for snapshot in snapshots:
                myzip.write(snapshot)

        myzip.close()
    except:
        exit_app("Error generating zipfile.", status_code=1)

    return zip_filename

if __name__ == '__main__':
    try:
        inputFile, material, coatings = get_tdp_inputs()

        filename = FILENAME
        download_stp_file(inputFile, filename)

        metadata = get_metadata(filename, material, coatings)

        try:
            shape = import_step(filename)
        except:
            exit_app("Error importing shapes from STP file.", status_code=1)

        geometry = get_geometry(shape, material, metadata["unit"])

        xml = generate_xml(metadata, geometry)

        snapshots = get_snapshots()

        zip_filename = generate_zip(xml, filename, snapshots)

        zip_url = upload_zip(zip_filename)

        exit_app(zip_url)
    except SystemExit as e:
        sys.exit(0)
    except:
        exit_app("Unknown error.", status_code=1)
