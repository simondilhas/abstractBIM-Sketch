import inkex
import os
from utils.convert_ifc_to_svg import process_ifc
from utils.convert_svg_to_ifc import process_svg_layers

class AbstractBIMSketch(inkex.EffectExtension):
    def add_arguments(self, pars):
        # General arguments
        pars.add_argument("--ifc_file", type=inkex.Path, help="Path to the IFC file")
        pars.add_argument("--output_unit", type=str, default="centimeters", help="Unit for the output SVG")

        # Operation selection
        pars.add_argument("--operation", type=str, default="process_ifc", 
                        help="Choose the operation to perform: process_ifc")


    def effect(self):
        # Extract user input
        operation = self.options.operation
        ifc_file_path = self.options.ifc_file
        output_unit = self.options.output_unit

        # Dispatch based on the operation selected
        if operation == "process_ifc":
            self.process_ifc(ifc_file_path, output_unit)
        elif operation == "other_function":
            self.other_function()
        else:
            inkex.errormsg(f"Unknown operation: {operation}")

    def process_ifc(self, ifc_file_path, output_unit):
        """Process an IFC file and generate SVG."""
        # Validate the IFC file path
        if not os.path.isfile(ifc_file_path):
            inkex.errormsg(f"The file {ifc_file_path} does not exist.")
            return

        # Process the IFC file
        try:
            svg_content = process_ifc(ifc_file_path, unit=output_unit)
        except Exception as e:
            inkex.errormsg(f"Error processing IFC file: {e}")
            return

        # Add SVG content to the Inkscape document
        try:
            svg_root = inkex.etree.fromstring(svg_content)
            self.svg.getroot().append(svg_root)
        except Exception as e:
            inkex.errormsg(f"Error adding SVG to Inkscape: {e}")


# Entry point for the plugin
if __name__ == "__main__":
    AbstractBIMSketch().run()
