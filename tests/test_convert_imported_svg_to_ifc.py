import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.convert_svg_to_ifc import process_svg_layers

svg_filename = "output/ifc_to_svg.svg"
if not os.path.exists(svg_filename):
    raise FileNotFoundError(f"SVG file not found: {svg_filename}")
output_folder = "output"

process_svg_layers(svg_filename, output_folder)