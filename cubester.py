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
    CollectionProperty
from bpy.utils import register_class, unregister_class
from bpy import app
from pathlib import Path
from typing import List, Tuple
from os import walk
from random import uniform


CACHE = {}  # keep track of loaded images data to allow faster creation the second time around


def create_random_data(rows: int, columns: int, layer_count) -> List[List[Tuple[list, float]]]:
    """
    Create the random heights and colors needed.
    :param rows: the number of rows to create data for
    :param columns: the number of columns to create data for
    :param layer_count: the number of layers to create data for
    :return: Layers[Rows[Columns[color, height]]]
    """
    layers = []
    for _ in range(layer_count):
        layers.append([])

        for r in range(rows):
            layers[-1].append([])

            for c in range(columns):
                height = uniform(0, 1)
                color = [0, 0, 0, 0]  # TODO: allow user to specify how to generate colors

                layers[-1][-1].append((color, height))


def collect_image_data(image: Image, rows: int, columns: int, multiple_layers: bool) -> List[List[Tuple[list, float]]]:
    """
    Collect height and color data from the given image
    :param image: the image to get the data from
    :param rows: the number of rows to collect data on
    :param columns: the number of columns to collect data on
    :param multiple_layers: whether to split the color channels in distinct layers or to combine them into one
    :return: Layers[Rows[Columns[color, height]]]
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

    layers = []
    for ch in range(channels if multiple_layers else 1):
        layers.append([])

        r = 0
        for _ in range(rows):  # manually run loop to ensure that exactly the right number of rows is created
            layers[-1].append([])

            c = 0
            for _ in range(columns):
                pos = (((r * width) + c) * channels) + ch

                total = 0
                if multiple_layers:
                    total = pixels[pos]

                    # construct color with value only in proper channel
                    color = [0] * channels
                    color[ch] = pixels[pos]
                else:
                    for i in range(pos, pos+channels):
                        total += pixels[i]

                    color = pixels[pos: pos+channels]

                layers[-1][-1].append((color[:channels] + padding, total))

                c += col_step
            r += row_step

    return layers


def frame_handler(scene):
    pass


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
        items=(("point", "Point", ""), ("block", "Block", ""), ("object", "Object", "")),
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


class CSPanel(Panel):
    bl_idname = "OBJECT_PT_cs_panel"
    bl_label = "CubeSter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        layout = self.layout
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

        layout.separator()
        layout.operator("object.cs_generate_mesh", icon="SHADERFX")


class CSGenerateMesh(Operator):
    bl_idname = "object.cs_generate_mesh"
    bl_label = "Generate Mesh"
    bl_description = "Generate CubeSter Mesh"

    def execute(self, context):
        props = context.scene.cs_properties

        frames = []
        if props.source_type == "image":
            layers = collect_image_data(props.image, props.row_count, props.column_count, props.create_layers)
            frames.append(layers)
        elif props.source_type == "image_sequence":
            for image in props.image_sequence_images:
                layers = collect_image_data(image.image, props.row_count, props.column_count, props.create_layers)
                frames.append(layers)
        elif props.source_type == "audio":
            pass
        else:
            layers = create_random_data(props.row_count, props.column_count, 1)

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