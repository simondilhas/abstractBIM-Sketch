import ifcopenshell
import ifcopenshell.geom
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import hashlib
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import math

from utils.unit_class import UnitConverter, ModelUnit



@dataclass
class ViewBox:
    min_x: float
    min_y: float
    width: float
    height: float
    
    def __str__(self) -> str:
        return f"{self.min_x} {self.min_y} {self.width} {self.height}"

@dataclass
class SpaceData:
    guid: str
    long_name: str
    storey: str
    storey_guid: str
    points: List[Tuple[float, float]]
    color: str
    relative_z: float  # Z position relative to storey elevation
    space_height: float
    absolute_z: float  # Absolute Z position



class SVGGenerator:
    def __init__(self, model_unit: ModelUnit = ModelUnit.METERS, 
                 output_unit: ModelUnit = ModelUnit.CENTIMETERS,
                 padding_percent: float = 0.1):
        self.unit_converter = UnitConverter(model_unit, output_unit)
        self.unit = ModelUnit(output_unit.value)  # Convert ModelUnit to SVGUnit
        self.padding_percent = padding_percent
        self.settings = self._init_geometry_settings()

    def _process_space_geometry(self, space: 'IfcSpace') -> Tuple[Optional[Polygon], Optional[float]]:
        shape = ifcopenshell.geom.create_shape(self.settings, space)
        vertices = np.array(shape.geometry.verts).reshape((-1, 3))
        vertices = self.unit_converter.convert_points(vertices)
        
    def _init_geometry_settings(self) -> ifcopenshell.geom.settings:
        """Initialize geometry settings with proper configuration"""
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        return settings
    
    def _calculate_viewbox(self, points: List[Tuple[float, float]]) -> ViewBox:
        """Calculate ViewBox with proper padding"""
        if not points:
            return ViewBox(0, 0, 1000, 1000)
            
        points_array = np.array(points)
        min_x, min_y = points_array.min(axis=0)
        max_x, max_y = points_array.max(axis=0)
        
        width = max_x - min_x
        height = max_y - min_y
        
        padding = max(width, height) * self.padding_percent
        
        return ViewBox(
            min_x=min_x - padding,
            min_y=min_y - padding,
            width=width + 2 * padding,
            height=height + 2 * padding
        )
    
    def _generate_color(self, name: str) -> str:
        """Generate a consistent color based on the name"""
        hash_object = hashlib.md5(str(name).encode())
        hash_hex = hash_object.hexdigest()
        
        # Generate HSL color for better visual distinction
        hue = int(hash_hex[:3], 16) % 360
        saturation = 70  # Fixed saturation for consistency
        lightness = 50 + (int(hash_hex[3:6], 16) % 20)  # Vary lightness slightly
        
        # Convert HSL to hex color
        h = hue / 360
        s = saturation / 100
        l = lightness / 100
        
        def hue_to_rgb(p: float, q: float, t: float) -> float:
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1/6:
                return p + (q - p) * 6 * t
            if t < 1/2:
                return q
            if t < 2/3:
                return p + (q - p) * (2/3 - t) * 6
            return p
        
        if s == 0:
            r = g = b = l
        else:
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    def _process_space_geometry(self, space: 'IfcSpace') -> Tuple[Optional[Polygon], Optional[float]]:
        """Process space geometry with error handling"""
        try:
            shape = ifcopenshell.geom.create_shape(self.settings, space)
            vertices = np.array(shape.geometry.verts).reshape((-1, 3)) * 100 #careful

            faces = np.array(shape.geometry.faces).reshape((-1, 3))
            
            # Calculate space height
            min_z = np.min(vertices[:, 2])
            max_z = np.max(vertices[:, 2])
            space_height = max_z - min_z
            
            # Process bottom faces
            space_faces = []
            z_tolerance = 1e-5
            
            for face in faces:
                face_verts = vertices[face]
                face_z = face_verts[:, 2]
                
                if np.allclose(face_z, min_z, rtol=z_tolerance):
                    face_2d = [(x, y) for x, y, z in face_verts]
                    try:
                        poly = Polygon(face_2d)
                        if poly.is_valid:
                            space_faces.append(poly)
                    except ValueError:
                        continue
            
            if space_faces:
                return unary_union(space_faces), space_height
            return None, None
            
        except Exception as e:
            print(f"Error processing space {space.GlobalId}: {e}")
            return None, None

    def _generate_path_data(self, points: List[Tuple[float, float]]) -> str:
        """Generate optimized SVG path data"""
        if not points:
            return ""
            
        path_data = [f"M {points[0][0]:.3f},{points[0][1]:.3f}"]
        
        prev_x, prev_y = points[0]
        for x, y in points[1:]:
            if math.isclose(y, prev_y, rel_tol=1e-9):
                path_data.append(f"H {x:.3f}")
            elif math.isclose(x, prev_x, rel_tol=1e-9):
                path_data.append(f"V {y:.3f}")
            else:
                path_data.append(f"L {x:.3f},{y:.3f}")
            prev_x, prev_y = x, y
        
        path_data.append("Z")
        return " ".join(path_data)

    def get_spaces_by_storey(self, ifc_file) -> Dict[float, List[SpaceData]]:
        """Get spaces organized by storey with relative Z positions"""
        spaces_by_level = {}
        spaces_by_storey_temp = {}
        
        # First pass: collect all spaces and their absolute Z positions
        for space in ifc_file.by_type('IfcSpace'):
            polygon, space_height = self._process_space_geometry(space)
            if polygon is None:
                continue
            
            points = []
            if isinstance(polygon, MultiPolygon):
                for poly in polygon.geoms:
                    points.extend(list(poly.exterior.coords)[:-1])
            else:
                points.extend(list(polygon.exterior.coords)[:-1])
            
            # Get the storey information
            storey = None
            for rel in space.Decomposes:
                if rel.RelatingObject.is_a('IfcBuildingStorey'):
                    storey = rel.RelatingObject
                    break
            
            if not storey:
                continue

            # Calculate absolute bottom Z position from geometry
            shape = ifcopenshell.geom.create_shape(self.settings, space)
            vertices = np.array(shape.geometry.verts).reshape((-1, 3))
            absolute_z = np.min(vertices[:, 2])
            
            storey_id = storey.GlobalId
            storey_elevation = float(storey.Elevation or 0)
            
            if storey_id not in spaces_by_storey_temp:
                spaces_by_storey_temp[storey_id] = {
                    'spaces': [],
                    'z_positions': [],
                    'storey': storey,
                    'elevation': storey_elevation
                }
            
            # Add space information to temporary storage
            space_info = {
                'guid': space.GlobalId,
                'long_name': space.LongName or space.Name or "Unnamed Space",
                'points': points,
                'color': self._generate_color(space.LongName or space.Name or "Unnamed Space"),
                'absolute_z': absolute_z,
                'space_height': space_height or 0.0,
                'relative_z': absolute_z - storey_elevation
            }
            spaces_by_storey_temp[storey_id]['spaces'].append(space_info)
            spaces_by_storey_temp[storey_id]['z_positions'].append(absolute_z)

        spaces_by_level = {}
    
        for storey_data in spaces_by_storey_temp.values():
            storey = storey_data['storey']
            storey_elevation = storey_data['elevation']
            
            # Calculate the most common Z position as the base for this storey
            z_positions = np.array(storey_data['z_positions'])
            base_z = float(np.median(z_positions))  # Use median as base elevation
            
            for space_info in storey_data['spaces']:
                relative_z = space_info['absolute_z'] - base_z  # Calculate relative to base
                
                space_data = SpaceData(
                    guid=space_info['guid'],
                    long_name=space_info['long_name'],
                    storey=storey.Name or f"Level {base_z:.2f}m",
                    storey_guid=storey.GlobalId,
                    points=space_info['points'],
                    color=space_info['color'],
                    relative_z=relative_z,
                    space_height=space_info['space_height'],
                    absolute_z=space_info['absolute_z']
                )
                
                if base_z not in spaces_by_level:
                    spaces_by_level[base_z] = []
                spaces_by_level[base_z].append(space_data)
        
        return spaces_by_level

    def _generate_project_hierarchy(self, project_data: dict,
                                  spaces_by_level: Dict[float, List[SpaceData]],
                                  viewbox: ViewBox) -> str:
        """Generate project hierarchy groups with relative Z positions"""
        elements = []
        
        # Add project, site, building hierarchy
        elements.extend([
            f'''    <g
        id="{project_data['guid']}"
        inkscape:label="Project={project_data['name']}">''',
            f'''        <g
            id="{project_data['site_guid']}"
            inkscape:label="Site={project_data['site']}">''',
            f'''            <g
                id="{project_data['building_guid']}"
                inkscape:label="Building={project_data['building']}"
                style="display:inline">'''
        ])
        
        # Add storeys and spaces
        for storey_elevation, spaces in sorted(spaces_by_level.items()):
            if not spaces:
                continue
            
            # Group spaces by unique combinations of height and relative Z
            space_groups = {}
            for space in spaces:
                # Round values to avoid floating point comparison issues
                height = round(space.space_height, 3)
                rel_z = round(space.relative_z, 3)
                key = (height, rel_z)
                
                if key not in space_groups:
                    space_groups[key] = []
                space_groups[key].append(space)
            
            storey_guid = spaces[0].storey_guid
            storey_name = spaces[0].storey
            
            # Storey level
            elements.append(f'''                <g
                    inkscape:groupmode="layer"
                    id="{storey_guid}"
                    inkscape:label="Storey={storey_name}, Z={self.unit_converter.convert(storey_elevation):.2f}">''')
            
            
            # Create single layer for each unique height and Z combination
            for (height, rel_z), group_spaces in sorted(space_groups.items()):
                # Convert rel_z before using it in formatting
                converted_rel_z = self.unit_converter.convert(rel_z)
                z_offset_str = "0.00" if abs(rel_z) < 0.001 else f"{converted_rel_z:.2f}"
                
                # Generate unique ID for this group
                group_id = f"spaces_{storey_guid}_h{height:.2f}_z{converted_rel_z:.2f}"
                elements.append(f''' <g
                inkscape:groupmode="layer"
                id="{group_id}"
                inkscape:label="Spaces, h={height:.2f}, relZ={z_offset_str}">''')
                
                # Add all spaces with this height and Z to the same layer
                for space in group_spaces:
                    path_data = self._generate_path_data(space.points)
                    if path_data:
                        elements.append(f'''                        <path
                                id="{space.guid}"
                                d="{path_data}"
                                inkscape:label="{space.long_name}"
                                style="fill:{space.color};stroke:#000000;stroke-width:0.1;fill-opacity:0.7"/>''')
                
                elements.append('                    </g>')
            
            elements.append('                </g>')
        # Close hierarchy groups
        elements.extend([
            '            </g>',  # Close Building
            '        </g>',      # Close Site
            '    </g>'           # Close Project
        ])
        
        return '\n'.join(elements)
    
    def generate_svg(self, spaces_by_level: Dict[float, List[SpaceData]], 
                    project_data: dict) -> str:
        """Generate SVG content with full IFC hierarchy"""
        all_points = [point for spaces in spaces_by_level.values() 
                     for space in spaces for point in space.points]
        viewbox = self._calculate_viewbox(all_points)
        
        svg_elements = [
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
            f'''<svg
    width="{viewbox.width}{self.unit.value}"
    height="{viewbox.height}{self.unit.value}"
    viewBox="{viewbox}"
    version="1.1"
    xmlns="http://www.w3.org/2000/svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">''',
            '''    <sodipodi:namedview
        id="namedview1"
        pagecolor="#ffffff"
        bordercolor="#000000"
        borderopacity="0.25"
        inkscape:showpageshadow="2"
        inkscape:pageopacity="0.0"
        inkscape:pagecheckerboard="0"
        inkscape:deskcolor="#d1d1d1"
        inkscape:document-units="cm"
        showgrid="true">
        <inkscape:grid
            id="grid1"
            units="cm"
            originx="0"
            originy="0"
            spacingx="12.5"
            spacingy="12.5"
            empcolor="#0099e5"
            empopacity="0.30196078"
            color="#0099e5"
            opacity="0.14901961"
            empspacing="5"
            enabled="true"
            visible="true"
            dotted="false" />
            </sodipodi:namedview>
            <defs id="defs1" />'''
        ]
        
        svg_elements.append(self._generate_project_hierarchy(
            project_data, spaces_by_level, viewbox))
        
        svg_elements.append('</svg>')
        return '\n'.join(svg_elements)

    def _generate_level_group(self, height: float, 
                            spaces: List[SpaceData]) -> List[str]:
        """Generate level group with spaces"""
        elements = []
        
        elements.append(f'''        <g
            id="level_{height:.2f}"
            inkscape:label="Level {height:.2f}{self.unit.value}">''')
        
        for space in spaces:
            path_data = self._generate_path_data(space.points)
            if path_data:
                elements.append(f'''            <path
                id="{space.guid}"
                d="{path_data}"
                inkscape:label="{space.long_name}"
                style="fill:{space.color};stroke:#000000;stroke-width:0.1;fill-opacity:0.7"/>''')
        
        elements.append('        </g>')
        return elements

def get_project_data(ifc_file) -> dict:
    """Extract project hierarchy data"""
    project = ifc_file.by_type("IfcProject")[0] if ifc_file.by_type("IfcProject") else None
    site = ifc_file.by_type("IfcSite")[0] if ifc_file.by_type("IfcSite") else None
    building = ifc_file.by_type("IfcBuilding")[0] if ifc_file.by_type("IfcBuilding") else None
    
    return {
        "name": project.Name if project and project.Name else "Unnamed Project",
        "guid": project.GlobalId if project else "N/A",
        "site": site.Name if site and site.Name else "Unnamed Site",
        "site_guid": site.GlobalId if site else "N/A",
        "building": building.Name if building and building.Name else "Unnamed Building",
        "building_guid": building.GlobalId if building else "N/A"
    }

def process_ifc(file_path: str, unit: ModelUnit = ModelUnit.CENTIMETERS) -> str:
    ifc_file = ifcopenshell.open(file_path)
    generator = SVGGenerator(model_unit=ModelUnit.METERS, output_unit=unit)
    spaces_by_level = generator.get_spaces_by_storey(ifc_file)
    project_data = get_project_data(ifc_file)
    return generator.generate_svg(spaces_by_level, project_data)