import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.convert_ifc_to_svg import process_ifc

#svg_content = process_ifc("tests/Mustermodell V2.ifc")
svg_content = process_ifc("tests/S22.ifc")
with open("output/ifc_to_svg.svg", "w") as f:
    f.write(svg_content)