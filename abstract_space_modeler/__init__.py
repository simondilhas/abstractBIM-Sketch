import inkex
from .abstract_space_modeler import create_ifc


class SpaceModelerPlugin(inkex.EffectExtension):
    def add_arguments(self, pars):
        pars.add_argument("--output_path", type=str, help="Path to save the IFC file")
        pars.add_argument("--height", type=float, default=3.0, help="Default height of the space (in meters)")

    def effect(self):
        if not self.options.output_path:
            inkex.errormsg("Please specify an output IFC file path.")
            return

        # Extract SVG file and dimensions
        svg_file = self.args[-1]
        ifc_file = self.options.output_path
        height = self.options.height

        create_ifc(svg_file, ifc_file, default_height=height)
        inkex.utils.debug(f"IFC file created at: {ifc_file}")


if __name__ == "__main__":
    SpaceModelerPlugin().run()
