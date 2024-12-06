import ifcopenshell
import ifcopenshell.geom
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import hashlib
from typing import Dict, List, Tuple

def get_color_from_name(name):
    """Generate a consistent color based on the name"""
    hash_object = hashlib.md5(str(name).encode())
    hash_hex = hash_object.hexdigest()
    return f"#{hash_hex[:6]}"

def get_spaces_by_storey(ifc_file) -> Dict[str, List]:
    """Get all spaces organized by storey"""
    spaces_by_storey = {}
    
    for space in ifc_file.by_type('IfcSpace'):
        for rel in space.Decomposes:
            if rel.RelatingObject.is_a('IfcBuildingStorey'):
                storey = rel.RelatingObject
                if storey.GlobalId not in spaces_by_storey:
                    spaces_by_storey[storey.GlobalId] = {
                        'storey': storey,
                        'spaces': []
                    }
                spaces_by_storey[storey.GlobalId]['spaces'].append(space)
                break
    
    return spaces_by_storey

def process_space_geometry(space, settings):
    """Process individual space geometry and return polygon and actual space height"""
    try:
        shape = ifcopenshell.geom.create_shape(settings, space)
        vertices = np.array(shape.geometry.verts).reshape((-1, 3))
        faces = np.array(shape.geometry.faces).reshape((-1, 3))
        
        min_z = np.min(vertices[:, 2])
        max_z = np.max(vertices[:, 2])
        space_height = max_z - min_z  # Calculate the actual height of the space
        space_faces = []
        
        for face in faces:
            face_verts = vertices[face]
            face_z = face_verts[:, 2]
            
            if np.allclose(face_z, min_z, rtol=1e-5) and np.allclose(face_z, face_z[0], rtol=1e-5):
                face_2d = [(x, y) for x, y, z in face_verts]
                space_faces.append(Polygon(face_2d))
        
        if space_faces:
            return unary_union(space_faces), space_height
        return None, None
    
    except Exception as e:
        print(f"Error processing space {space.GlobalId}: {e}")
        return None, None

def process_ifc(file_path: str) -> str:
    """Process IFC file and create SVG"""
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    
    ifc_file = ifcopenshell.open(file_path)
    
    # Get project hierarchy
    project = ifc_file.by_type("IfcProject")[0]
    site = ifc_file.by_type("IfcSite")[0]
    building = ifc_file.by_type("IfcBuilding")[0]
    
    project_data = {
        "name": project.Name or "Unnamed Project",
        "guid": project.GlobalId,
        "site": site.Name or "Unnamed Site",
        "site_guid": site.GlobalId,
        "building": building.Name or "Unnamed Building",
        "building_guid": building.GlobalId
    }
    
    spaces_by_storey = get_spaces_by_storey(ifc_file)
    spaces_by_level = {}
    
    # Process geometry for each space
    all_points = []
    for storey_guid, data in spaces_by_storey.items():
        storey = data['storey']
        storey_elevation = float(storey.Elevation or 0) / 100  # Convert cm to m for display
        
        for space in data['spaces']:
            polygon, space_height = process_space_geometry(space, settings)
            if polygon is None:
                continue
            
            if isinstance(polygon, MultiPolygon):
                polygons = list(polygon.geoms)
            else:
                polygons = [polygon]
            
            points = []
            for poly in polygons:
                coords = list(poly.exterior.coords)[:-1]  # Exclude last point (same as first)
                points.extend(coords)
                all_points.extend(coords)
            
            space_data = {
                "guid": space.GlobalId,
                "long_name": space.LongName or space.Name or "Unnamed Space",
                "storey": storey.Name or f"Level {storey_elevation:.2f}m",
                "storey_guid": storey.GlobalId,
                "points": points,
                "color": get_color_from_name(space.LongName or space.Name or "Unnamed Space"),
                "elevation": storey_elevation,  # Store storey elevation
                "space_height": space_height  # Convert space Z coordinate from cm to m
            }
            
            if storey_elevation not in spaces_by_level:
                spaces_by_level[storey_elevation] = []
            spaces_by_level[storey_elevation].append(space_data)

    
    return create_svg(spaces_by_level, project_data, all_points)

def create_svg(spaces_by_level: Dict[float, List[dict]], project_data: dict, all_points: List[Tuple[float, float]]) -> str:
    """Generate SVG with Inkscape template structure"""
    # Calculate bounds for viewBox
    if all_points:
        all_points = np.array(all_points)
        min_x, min_y = all_points.min(axis=0)
        max_x, max_y = all_points.max(axis=0)
        width = max_x - min_x
        height = max_y - min_y
        padding = max(width, height) * 0.1  # 10% padding
    else:
        min_x, min_y = 0, 0
        width, height = 100000, 100000
        padding = 1000

    # SVG header with viewBox
    svg_header = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg
    width="{width/10}cm"
    height="{height/10}cm"
    viewBox="{min_x-padding} {min_y-padding} {width+2*padding} {height+2*padding}"
    version="1.1"
    id="svg1"
    inkscape:version="1.4 (e7c3feb100, 2024-10-09)"
    sodipodi:docname="ifc_spaces.svg"
    xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
    xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
    xmlns="http://www.w3.org/2000/svg"
    xmlns:svg="http://www.w3.org/2000/svg">'''

    namedview = '''    <sodipodi:namedview
        id="namedview1"
        pagecolor="#ffffff"
        bordercolor="#000000"
        borderopacity="0.25"
        inkscape:showpageshadow="2"
        inkscape:pageopacity="0.0"
        inkscape:pagecheckerboard="0"
        inkscape:deskcolor="#d1d1d1"
        inkscape:document-units="cm"
        showguides="true"
        inkscape:zoom="0.01"
        inkscape:cx="188950"
        inkscape:cy="127550"
        inkscape:window-width="1832"
        inkscape:window-height="1076"
        inkscape:window-x="0"
        inkscape:window-y="0"
        inkscape:window-maximized="1"
        inkscape:current-layer="layer3"
        showgrid="true">
        <inkscape:grid
            id="grid1"
            units="cm"
            originx="0"
            originy="0"
            spacingx="125"
            spacingy="125"
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

    # Project hierarchy
    svg_content = f'''    <g
        inkscape:groupmode="layer"
        id="{project_data['guid']}"
        inkscape:label="Project={project_data['name']}">
        <g
            inkscape:groupmode="layer"
            id="{project_data['site_guid']}"
            inkscape:label="Site={project_data['site']}">
            <g
                inkscape:groupmode="layer"
                id="{project_data['building_guid']}"
                inkscape:label="Building={project_data['building']}"
                style="display:inline">'''

    # Add storeys and spaces
    for height, spaces in spaces_by_level.items():
        storey_guid = spaces[0]['storey_guid']
        svg_content += f'''                <g
                    inkscape:groupmode="layer"
                    id="{storey_guid}"
                    inkscape:label="Storey={spaces[0]['storey']}, h={height:.2f}m">
                    <g
                        inkscape:groupmode="layer"
                        id="space_{storey_guid}"
                        inkscape:label="Space, h={spaces[0]['space_height']:.2f}m">'''
        
        for space in spaces:
            points = space['points']
            if points:
                path_data = f"M {points[0][0]},{points[0][1]}"
                for point in points[1:]:
                    path_data += f" L {point[0]},{point[1]}"
                path_data += " Z"
                
                svg_content += f'''                        <path
                            id="{space['guid']}"
                            d="{path_data}"
                            inkscape:label="{space['long_name']}"
                            style="fill:{space['color']};stroke:#000000;stroke-width:0.1;fill-opacity:0.7"/>'''
        
        svg_content += '''                    </g>
                </g>'''
    return svg_header + namedview + svg_content

if __name__ == "__main__":
    svg_content = process_ifc("test/Mustermodell V2.ifc")
    with open("output/ifc_to_svg.svg", "w") as f:
        f.write(svg_content)