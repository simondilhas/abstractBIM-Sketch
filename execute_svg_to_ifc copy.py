from utils.convert_svg_to_ifc import process_svg_layers
import os


svg_filename = "tests/groundfloor_test1.svg" #replace with your filename
output_folder = "output"
process_svg_layers(svg_filename, output_folder)
