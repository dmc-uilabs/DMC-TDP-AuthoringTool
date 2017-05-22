#!/usr/bin/python
# coding: utf-8

from STParser import stp_header_parser
import aocxchange.step
from OCCUtils import Common
import xml.etree.cElementTree as ET
import uuid

def get_dome_inputs():
    with open('in.txt') as f:
        lines = f.readlines()

    inputs = {}

    for line in lines:
        kv = line.rstrip().split("=")
        key = kv[0]
        value = kv[1]
        inputs[key] = value
        
    return inputs
    
def get_metadata(filename, material, coatings):
    header = stp_header_parser.stp_header_parser()
    header = header.stp_header_parser(stp_filename=filename)
    
    return {'name': header[3][1], 'material': material, 'coatings': coatings, 'unit': header[11][1]}
    
def import_step(filename):
    my_importer = aocxchange.step.StepImporter(filename)
    return my_importer.shapes[0]
    
def get_geometry(shape, unit="units"):
    boundingbox_points = Common.get_boundingbox(shape)
    length = boundingbox_points[3] - boundingbox_points[0]
    height = boundingbox_points[5] - boundingbox_points[2]
    width = boundingbox_points[4] - boundingbox_points[1]
    
    gprop = Common.GpropsFromShape(shape)
    volume = gprop.volume().Mass()
    density = 1
    mass = volume*density
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
    
    return ET.tostring(mBOM)

if __name__ == '__main__':
    inputs = get_dome_inputs()
    filename = inputs["filename"]
    filename = '23059898_C_x_t.stp'
    material = inputs["material"]
    coatings = inputs["coatings"]
    part_id = str(uuid.uuid4())
    
    metadata = get_metadata(filename, material, coatings)
    
    shape = import_step(filename)
    geometry = get_geometry(shape)
    
    xml = generate_xml(metadata, geometry, part_id)
    outfile = open('out.txt', 'w')
    outfile.write(xml)
    outfile.close()