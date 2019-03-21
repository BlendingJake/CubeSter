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

from bpy.types import Scene, Object, Panel, Operator
from bpy.props import PointerProperty
from bpy.utils import register_class, unregister_class
from bpy import app


def frame_handler(scene):
    pass


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
    CSPanel, 
    CSLoadImageSequence,
]


def register():
    for cls in classes:
        register_class(cls)

    app.handlers.frame_change_pre.append(frame_handler)


def unregister():
    for cls in classes:
        unregister_class(cls)

    app.handlers.frame_change_pre.remove(frame_handler)


if __name__ == "__main__":
    register() 