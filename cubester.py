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

bl_info = {
    "name": "CubeSter",
    "author": "Jacob Morris",
    "version": (2, 0, 0),
    "blender": (2, 80, 0),
    "location": "View 3D > Toolbar > CubeSter",
    "description": "Take an image, image sequence, or audio file and use it to generate a mesh",
    "category": "Add Mesh"
}

from bpy.types import Scene, Object, Panel, Operator, PropertyGroup
from bpy.props import PointerProperty, IntProperty, EnumProperty, FloatProperty
from bpy.utils import register_class, unregister_class
from bpy import app


def frame_handler(scene):
    pass


# PROPERTIES ----------------------------------------------------
class CSSceneProperties(PropertyGroup):
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


class CSPanel(Panel):
    bl_idname = "OBJECT_PT_cs_panel"
    bl_label = "CubeSter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        layout = self.layout


class CSLoadImageSequence(Operator):
    bl_idname = "object.cs_load_image_sequence"
    bl_label = "Load Image Sequence"
    bl_description = "Load CubeSter Image Sequence"

    def execute(self, context):
        return {"FINISHED"}


classes = [
    CSSceneProperties,
    CSPanel, 
    CSLoadImageSequence,
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