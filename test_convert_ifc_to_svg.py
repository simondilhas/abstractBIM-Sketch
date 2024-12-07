from convert_ifc_to_svg import process_ifc



svg_content = process_ifc("test/Mustermodell V2.ifc")
svg_content = process_ifc("test/S22.ifc")
with open("output/ifc_to_svg.svg", "w") as f:
    f.write(svg_content)