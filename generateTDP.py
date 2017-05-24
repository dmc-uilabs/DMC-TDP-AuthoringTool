#!/usr/bin/python
# coding: utf-8

import uuid
import re
import time
import sys
import zipfile
import aocxchange.step
import xml.etree.cElementTree as ET
from PyQt5 import QtWidgets
from PIL import Image
from OCC.Bnd import Bnd_Box
from OCC.Display.OCCViewer import Viewer3d
from OCC.BRepBndLib import brepbndlib_Add
from OCC.GProp import GProp_GProps
from OCC.BRepGProp import (brepgprop_LinearProperties,
                           brepgprop_SurfaceProperties,
                           brepgprop_VolumeProperties)

TOLERANCE = 1e-6

# Unit: kg/m^3
DENSITIES = {
    "Steel": 8000,
    "Aluminum": 2700
}

UNIT_FACTOR = {
    "units": 1,
    "m": 1,
    "cm": .01,
    "mm": .001
}

VIEWS = ["front", "rear", "top", "bottom", "left", "right", "iso"]

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
        key = kv[0].strip()
        value = kv[1].strip()
        inputs[key] = value
        
    return inputs
    
def get_metadata(filename, material, coatings):
    header = stp_header_parser()
    header = header.stp_header_parser(stp_filename=filename)
    
    return {'name': header[3][1], 'material': material, 'coatings': coatings, 'unit': header[11][1]}
    
def import_step(filename):
    my_importer = aocxchange.step.StepImporter(filename)
    return my_importer.shapes[0]
    
def get_geometry(shape, material, unit="units"):
    boundingbox_points = get_boundingbox(shape)
    length = boundingbox_points[3] - boundingbox_points[0]
    height = boundingbox_points[5] - boundingbox_points[2]
    width = boundingbox_points[4] - boundingbox_points[1]
    
    gprop = GpropsFromShape(shape)
    volume = gprop.volume().Mass()
    density = DENSITIES[material]
    mass = volume*density*pow(UNIT_FACTOR[unit], 3)
    surface_area = gprop.surface().Mass()
    
    return {'length': length, 'height': height, 'width': width, 'volume': volume, 'mass': mass, 'surface_area': surface_area}
    
def generate_xml(metadata, geometry, part_id):
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
    manufacturingDetails = ET.SubElement(part, "manufacturingDetails")
    ET.SubElement(manufacturingDetails, "material").text = metadata["material"]
    ET.SubElement(manufacturingDetails, "coatings").text = metadata["coatings"]
    
    return mBOM

def generate_snapshots(shape):
    app = QtWidgets.QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    widget.resize(1000,1000)
    view = Viewer3d(int(widget.winId()))
    view.Create()
    view.SetModeShaded()
    view.DisplayShape(shape, update=True)
    
    VIEW_FUNC = {
        "front": view.View_Front,
        "rear": view.View_Rear,
        "top": view.View_Top,
        "bottom": view.View_Bottom,
        "left": view.View_Left,
        "right": view.View_Right,
        "iso": view.View_Iso
    }
    
    snapshots = []
    
    for view_type in VIEWS:
        VIEW_FUNC[view_type]()
        view.ExportToImage('capture.ppm')
        im = Image.open('capture.ppm')
        snapshot = view_type + '_capture.png'
        im.save(snapshot)
        snapshots.append(snapshot)
    
    return snapshots

def generate_zip(xml, filename, snapshots):
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
    
    return zip_filename

if __name__ == '__main__':
    inputs = get_dome_inputs()
    filename = inputs["filename"]
    filename = '23059898_C_x_t.stp'
    material = inputs["material"]
    coatings = inputs["coatings"]
    part_id = str(uuid.uuid4())
    
    metadata = get_metadata(filename, material, coatings)
    
    shape = import_step(filename)
    geometry = get_geometry(shape, material, metadata["unit"])
    
    xml = generate_xml(metadata, geometry, part_id)
    
    snapshots = generate_snapshots(shape)
    
    zip_filename = generate_zip(xml, filename, snapshots)
    
    outfile = open('out.txt', 'w')
    outfile.write("TDP_xml=" + zip_filename)
    outfile.close()