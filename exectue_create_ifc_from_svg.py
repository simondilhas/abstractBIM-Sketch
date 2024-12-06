from convert_svg_to_ifc import process_svg_layers

if __name__ == "__main__":
    svg_filename = "test/groundfloor_test1.svg"
    output_folder = "output"
    process_svg_layers(svg_filename, output_folder)