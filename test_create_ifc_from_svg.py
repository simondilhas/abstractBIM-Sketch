from create_ifc_from_svg import process_svg_layers

if __name__ == "__main__":
    svg_filename = "test/tests_input.svg"
    output_folder = "output"
    process_svg_layers(svg_filename, output_folder)