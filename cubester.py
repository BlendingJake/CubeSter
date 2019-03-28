# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Original Author = Jacob Morris
# URL = github.com/BlendingJake/CubeSter
from operator import itemgetter

import bpy
from bpy.path import abspath
from mathutils import Vector

bl_info = {
    "name": "CubeSter",
    "author": "Jacob Morris",
    "version": (2, 0, 0),
    "blender": (2, 80, 0),
    "location": "View 3D > Toolbar > CubeSter",
    "description": "Take an image, image sequence, or audio file and use it to generate a mesh",
    "category": "Add Mesh"
}

from bpy.types import Scene, Object, Panel, Operator, PropertyGroup, Image
from bpy.props import PointerProperty, IntProperty, EnumProperty, FloatProperty, StringProperty, BoolProperty, \
    CollectionProperty, FloatVectorProperty
from bpy.utils import register_class, unregister_class
from bpy import app
from pathlib import Path
from typing import List, Tuple
from os import walk
from random import uniform
import bmesh
import logging


logging.basicConfig(level=logging.DEBUG)
CACHE = {}  # keep track of loaded images data to allow faster creation the second time around


def build_bmesh(vertices: list, faces: list) -> bmesh.types.BMesh:
    logging.debug("BMESH: {} Vertices, {} Faces".format(len(vertices), len(faces)))

    bm = bmesh.new()

    for v in vertices:
        bm.verts.new(v)
    bm.verts.ensure_lookup_table()

    for f in faces:
        bm.faces.new([bm.verts[i] for i in f])
    bm.faces.ensure_lookup_table()

    return bm


def create_block_geometry(height_layers, height_factor: float, xy: float, spacing: float, dims: Tuple[int, int]
                          ) -> Tuple[list, list]:
    """
    Create vertex and face data from the given heights.
    :param height_layers: The layers of rows of columns of height data
    :param height_factor: the height of the max value
    :param xy: the x-y dimensions of each block
    :param spacing: the x-y space between each block
    :param dims: the number of rows and columns of blocks
    :return: vertex positions and faces
    """
    verts, faces = [], []
    rows, cols = dims
    sx = -((cols*xy) + ((cols - 1)*spacing)) / 2
    sy = -((rows*xy) + ((rows - 1)*spacing)) / 2

    # vertices
    p = 0
    for layer in height_layers:
        y = sy
        for row in layer:
            x = sx

            for bz, height in row:
                for z in (bz, bz+height):
                    z *= height_factor
                    verts += [
                        (x, y, z), (x, y+xy, z), (x+xy, y+xy, z), (x+xy, y, z)
                    ]

                x += xy + spacing
            y += xy + spacing

        # faces
        for _ in range(rows * cols):
            faces += [
                (p, p+1, p+2, p+3), (p+4, p+7, p+6, p+5), (p, p+4, p+5, p+1), (p, p+3, p+7, p+4), (p+3, p+2, p+6, p+7),
                (p+1, p+5, p+6, p+2)
            ]

            p += 8

    logging.debug("Blocks: {} Vertices, {} Faces".format(len(verts), len(faces)))

    return verts, faces


def create_random_data(rows: int, columns: int, layer_count) -> List[List[List[Tuple[float, float]]]]:
    """
    Create the random heights and colors needed.
    :param rows: the number of rows to create data for
    :param columns: the number of columns to create data for
    :param layer_count: the number of layers to create data for
    :return: Layers[Rows[Columns[Tuple[z, height]]]
    """
    height_layers = []
    for layer_i in range(layer_count):
        height_layers.append([])

        for r in range(rows):
            height_layers[-1].append([])

            for c in range(columns):
                height = uniform(0, 1)

                if layer_i >= 1:
                    z = height_layers[-2][r][c][0] + height_layers[-2][r][c][1]  # base + height
                else:
                    z = 0

                height_layers[-1][-1].append((z, height))

    return height_layers


def collect_image_data(image: Image, rows: int, columns: int, multiple_layers: bool
                       ) -> Tuple[List[List[List[list]]], List[List[List[Tuple[float, float]]]]]:
    """
    Collect height and color data from the given image
    :param image: the image to get the data from
    :param rows: the number of rows to collect data on
    :param columns: the number of columns to collect data on
    :param multiple_layers: whether to split the color channels in distinct layers or to combine them into one
    :return: Layers[Rows[Columns[color]]], Layers[Rows[Columns[Tuple(bottom z, height)]]]
    """
    if image.name in CACHE:
        pixels = CACHE[image.name]
    else:
        pixels = list(image.pixels)
        CACHE[image.name] = pixels

    width, height = image.size
    row_step, col_step = height // rows, width // columns
    channels = image.channels
    padding = [0] * (4 - channels)  # amount of padding needed to make sure all colors are RGBA

    color_layers = []
    height_layers = []
    layer_count = channels if multiple_layers else 1
    for layer_i in range(layer_count):
        color_layers.append([])
        height_layers.append([])

        r = 0
        for _ in range(rows):  # manually run loop to ensure that exactly the right number of rows is created
            color_layers[-1].append([])
            height_layers[-1].append([])

            c = 0
            for _ in range(columns):
                pos = (((r * width) + c) * channels) + layer_i

                height = 0
                if multiple_layers:
                    height = pixels[pos]

                    # construct color with value only in proper channel
                    color = [0] * channels
                    color[layer_i] = pixels[pos]

                    # determine z height for bottom of this layer
                    cur_r, cur_c = len(height_layers[-1]) - 1, len(height_layers[-1][-1]) - 1
                    if layer_i >= 1:
                        z = height_layers[-2][cur_r][cur_c][0] + height_layers[-2][cur_r][cur_c][1]  # z + height
                    else:
                        z = 0

                else:
                    z = 0
                    for i in range(pos, pos+channels):
                        height += pixels[i]

                    color = pixels[pos: pos+channels]

                color_layers[-1][-1].append(color[:channels] + padding)
                height_layers[-1][-1].append((z, height))

                c += col_step
            r += row_step

    logging.debug("Image {}: {} Layers, {} Rows, {} Columns".format(image.name, len(color_layers),
                                                                    len(color_layers[-1]), len(color_layers[-1][-1])))

    return color_layers, height_layers


def frame_handler(scene):
    pass


def generate_linear_colors(layers: int, rows: int, cols: int, height_layers, min_color: tuple, max_color: tuple,
                           min_height: float, max_height: float) -> List[List[List[list]]]:
    """
    Generate colors based on a linear scale
    :param layers: the number of layers to generate colors for
    :param rows: the number of rows to create colors for
    :param cols: the number of columns to create colors for
    :param height_layers: the heights for all the layers, rows, and columns to base the colors on
    :param min_color: the color of the minimum height
    :param max_color: the color of the maximum height
    :param min_height: the minimum height
    :param max_height: the maximum height
    :return: Layers[Rows[Columns[color]]]
    """
    min_vec, max_vec = Vector(min_color), Vector(max_color)
    slope = (max_vec - min_vec) / (max_height - min_height)

    color_layers = []
    for l in range(layers):
        color_layers.append([])

        for r in range(rows):
            color_layers[-1].append([])

            for c in range(cols):
                h = height_layers[l][r][c]
                color_layers[-1][-1].append(list((slope * h) + min_vec))

    return color_layers


def invert_all_heights(frames, max_value: float, dims: Tuple[int, int]) -> None:
    """
    Invert all the heights
    :param frames: Frames[Frame Data[Color Layers, Height Layers[Rows[Columns[Tuple[z, height]]]]]]
    :param max_value: the maximum value possible to allow inversion
    :param dims: the row and column counts, respectively
    """
    rows, cols = dims
    for frame in frames:
        height_layers = frame[1]
        for l in range(len(height_layers)):
            for r in range(rows):
                for c in range(cols):
                    z, height = height_layers[l][r][c]
                    height = max_value - height  # invert

                    if l >= 1:  # if not the first layer
                        z = height_layers[-2][r][c][0] + height_layers[-2][r][c][1]  # update z to be above lower level

                    height_layers[l][r][c] = (z, height)


# PROPERTIES ----------------------------------------------------
class CSImageProperties(PropertyGroup):
    image: PointerProperty(
        type=Image
    )


class CSSceneProperties(PropertyGroup):
    # GENERAL
    row_count: IntProperty(
        name="# Rows", min=1, default=50,
        description="The number of rows in the output mesh"
    )

    column_count: IntProperty(
        name="# Columns", min=1, default=100,
        description="The number of columns in the output mesh"
    )

    xy_size: FloatProperty(
        name="X-Y Size", min=0.0001, default=0.01,
        unit="LENGTH", description="The X-Y size of each mesh instance"
    )

    instance_spacing: FloatProperty(
        name="Instance Spacing", min=0, default=0,
        unit="LENGTH", description="The spacing between each row and column"
    )

    mesh_type: EnumProperty(
        name="Mesh Type",
        items=(("point", "Points", ""), ("block", "Blocks", ""), ("object", "Object", "")),
        description="The style of mesh to generate", default="block"
    )

    source_object: PointerProperty(
        name="Source Object", type=Object
    )

    # SOURCE
    source_type: EnumProperty(
        name="Source Type",
        items=(("image", "Image", ""), ("image_sequence", "Image Sequence", ""), ("audio", "Audio File", ""),
               ("random", "Random", "")),
        default="image", description="The source for generating the mesh heights"
    )

    image: PointerProperty(
        name="Image", type=Image, description="The image to use for generating the heights and colors"
    )

    # image sequence
    base_name: StringProperty(
        name="Base Name", default="", description="The base name shared by all images in the sequence"
    )

    image_start_offset: IntProperty(
        name="Start Image Offset", min=0, default=0,
        description="Skip this many images at the beginning of the list of images found"
    )

    image_step: IntProperty(
        name="Image Step", min=1, default=1, description="Step past this many images. Select and use one. Repeat."
    )

    image_end_offset: IntProperty(
        name="End Image Offset", min=0, default=0,
        description="Skip this many images at the end of the list of images found"
    )

    image_sequence_images: CollectionProperty(
        type=CSImageProperties
    )

    # audio file
    audio_file: StringProperty(
        name="Audio File", subtype="FILE_PATH"
    )

    min_freq: IntProperty(
        name="Minimum Frequency", min=0, default=20
    )

    max_freq: IntProperty(
        name="Maximum Frequency", min=0, default=20_000
    )

    audio_row_style: EnumProperty(
        name="Row Style",
        items=(("by_delay", "Divide By Delay", ""), ("by_freq", "Divide By Frequency", ""))
    )

    delay_amount: IntProperty(
        name="Frame Delay", min=1, default=5,
        description="Number of frames of delay between each row"
    )

    # random
    random_layer_count: IntProperty(
        name="# of Layers", min=1, default=1
    )

    # SCALING
    height: FloatProperty(
        name="Height", min=0, default=0.25,
        description="Height of max value"
    )

    invert_heights: BoolProperty(
        name="Invert Heights", default=True,
        description="Make the tallest height actually have the shortest height"
    )

    # LAYERS
    create_layers: BoolProperty(
        name="Create Layers?", default=False
    )

    layer_style: EnumProperty(
        name="Layer Style",
        items=(("stacked", "Stacked", ""), ("distinct", "Distinct", "")),
        default="stacked"
    )

    layer_offset: FloatProperty(
        name="Layer Offset", min=0, default=0
    )

    centering: EnumProperty(
        name="Centering",
        items=(("none", "None", ""), ("overall", "Overall", ""), ("per_layer", "Per Layer", "")),
        default="none"
    )

    # COLORING
    coloring_type: EnumProperty(
        name="Coloring Type",
        items=(("from_source", "From Source", ""), ("linear", "Linear", ""), ("random", "Random", "")),
        default="from_source"
    )

    linear_min_color: FloatVectorProperty(
        name="Color of Min Height", default=(0, 0, 0, 1),
        subtype="COLOR", size=4, description="The color of the minimum height in the mesh"
    )

    linear_max_color: FloatVectorProperty(
        name="Color of Max Height", default=(1, 1, 1, 1),
        subtype="COLOR", size=4, description="The color of the max height in the mesh"
    )


class CSPanel(Panel):
    bl_idname = "OBJECT_PT_cs_panel"
    bl_label = "CubeSter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        layout = self.layout

        if context.mode != "OBJECT":
            layout.label(text="CubeSter only works in Object Mode")
            return

        props = context.scene.cs_properties

        # GENERAL
        box = layout.box()
        box.label(text="General")

        row = box.row()
        row.prop(props, "row_count")
        row.prop(props, "column_count")

        box.separator()
        box.prop(props, "mesh_type")

        if props.mesh_type == "object":
            box.prop_search(props, "source_object", context.scene, "objects")
        else:
            box.prop(props, "xy_size")

        if props.mesh_type != "point":
            box.prop(props, "instance_spacing")

        # SOURCE
        box = layout.box()
        box.label(text="Source")
        box.prop(props, "source_type")
        box.separator()

        if props.source_type == "image":
            box.template_ID(props, "image", open="image.open")
        elif props.source_type == "image_sequence":
            box.template_ID(props, "image", open="image.open")
            box.prop(props, "base_name")
            box.operator("object.cs_load_image_sequence", icon="WINDOW")

            box.separator()
            box.prop(props, "image_start_offset")
            box.prop(props, "image_step")
            box.prop(props, "image_end_offset")
            box.label(text="Found {} Images".format(len(props.image_sequence_images)), icon="INFO")
        elif props.source_type == "audio":
            box.prop(props, "audio_file")

            box.separator()
            row = box.row()
            row.prop(props, "min_freq")
            row.prop(props, "max_freq")

            box.separator()
            box.prop(props, "audio_row_style")

            if props.audio_row_style == "by_delay":
                box.prop(props, "delay_amount")
        else:
            box.prop(props, "random_layer_count")

        # SCALING
        box = layout.box()
        box.label(text="Scaling")
        box.prop(props, "height")
        box.prop(props, "invert_heights", icon="FILE_REFRESH")

        # LAYERS
        box = layout.box()
        box.label(text="Layers")
        box.prop(props, "create_layers", icon="NODE_COMPOSITING")

        if props.create_layers:
            box.separator()
            box.prop(props, "layer_style")
            box.prop(props, "layer_offset")
            box.prop(props, "centering")

        # COLORING
        box = layout.box()
        box.label(text="Coloring")
        box.prop(props, "coloring_type")

        if props.coloring_type == "linear":
            box.separator()
            box.prop(props, "linear_min_color")
            box.prop(props, "linear_max_color")

        layout.separator()
        layout.operator("object.cs_generate_mesh", icon="SHADERFX")


class CSGenerateMesh(Operator):
    bl_idname = "object.cs_generate_mesh"
    bl_label = "Generate Mesh"
    bl_description = "Generate CubeSter Mesh"

    def execute(self, context):
        props = context.scene.cs_properties
        dims = (props.row_count, props.column_count)

        frames = []
        if props.source_type == "image":
            colors, heights = collect_image_data(props.image, props.row_count, props.column_count, props.create_layers)
            frames.append([colors, heights])
        elif props.source_type == "image_sequence":
            for image in props.image_sequence_images:
                colors, heights = collect_image_data(image.image, props.row_count, props.column_count,
                                                     props.create_layers)
                frames.append([colors, heights])
        elif props.source_type == "audio":
            pass
        else:
            heights = create_random_data(props.row_count, props.column_count, props.random_layer_count)
            frames.append([[], heights])

        logging.debug("{} Frames, {} Layers, {} Rows, {} Columns".format(len(frames), len(frames[0][0]),
                                                                         len(frames[0][0][0]), len(frames[0][0][0][0])))

        # SCALING
        if props.source_type == "audio":
            max_value = props.max_freq
        else:
            max_value = 1 if props.create_layers else props.image.channels
        height_factor = props.height / max_value

        if props.invert_heights:
            invert_all_heights(frames, max_value, dims)

        # COLORING
        if props.coloring_type == "from_source":
            pass

        elif props.coloring_type == "linear":
            max_height = 1 if props.create_layers else 4
            for frame in frames:
                frame[0] = generate_linear_colors(len(frame[1]), props.row_count, props.column_count, frame[1],
                                                  props.linear_min_color, props.linear_max_color,
                                                  0, max_height)
        elif props.coloring_type == "random":
            pass

        # MESH
        if props.mesh_type == "point":
            verts, faces = [], []
        elif props.mesh_type == "block":
            verts, faces = create_block_geometry(frames[0][1], height_factor, props.xy_size, props.instance_spacing,
                                                 dims)
        else:
            verts, faces = [], []

        bm = build_bmesh(verts, faces)
        bpy.ops.mesh.primitive_cube_add()
        bm.to_mesh(context.object.data)

        return {"FINISHED"}


class CSLoadImageSequence(Operator):
    bl_idname = "object.cs_load_image_sequence"
    bl_label = "Load Image Sequence"
    bl_description = "Load CubeSter Image Sequence"

    def execute(self, context):
        props = context.scene.cs_properties

        if props.image and props.base_name:
            base_path = Path(abspath(props.image.filepath)).parent

            # collect any matching files and their paths
            temp_data = {}
            for root, _, files in walk(base_path):
                for file in files:
                    if file.startswith(props.base_name):
                        temp_data[file] = str(Path(root) / file)

            ordered = sorted(temp_data.items(), key=itemgetter(0))  # sort the items by the file name

            # load and store any matching images
            props.image_sequence_images.clear()
            for i in range(props.image_start_offset, len(ordered) - props.image_end_offset, props.image_step):
                name, path = ordered[i]
                if name not in bpy.data.images:
                    bpy.data.images.load(path)

                item = props.image_sequence_images.add()
                item.image = bpy.data.images[name]

            self.report({"INFO"}, "Loaded {} images".format(len(props.image_sequence_images)))

        else:
            self.report({"WARNING"}, "There must be an image selected to load an image sequence")

        return {"FINISHED"}


classes = [
    CSImageProperties,
    CSSceneProperties,
    CSPanel,
    CSGenerateMesh,
]


def register():
    for cls in classes:
        register_class(cls)

    Scene.cs_properties = PointerProperty(
        name="CubeSter Scene Properties",
        type=CSSceneProperties
    )

    app.handlers.frame_change_pre.append(frame_handler)


def unregister():
    del Scene.cs_properties

    for cls in classes:
        unregister_class(cls)

    app.handlers.frame_change_pre.remove(frame_handler)


if __name__ == "__main__":
    register() 