import bpy
import os
import math
import numpy
import threading
import shutil

{
    "name": "Sprite Frame Generator",
    "author": "Pururum LLC",
    "version": (1, 0),
    "blender": (3, 0),
    "location": "View3D > Sidebar > Sprite Frame Generator",
    "description": "Generates sprite frames from a 3D model.",
    "category": "3D View",
}

# The global function to reuse for applying render settings.
def apply_render_settings(context):
    # set render resolution
    bpy.context.scene.render.resolution_x = context.scene.sprite_frame_generator_config.render_resolution[0]
    bpy.context.scene.render.resolution_y = context.scene.sprite_frame_generator_config.render_resolution[1]

    # set render frames per second
    bpy.context.scene.render.fps = context.scene.sprite_frame_generator_config.render_fps

    # set scene settings
    bpy.context.scene.frame_step = context.scene.sprite_frame_generator_config.animation_frame_step

    camera = bpy.context.scene.camera
    reset_camera_rotation(camera)

def rotate_camera_around_z_axis(camera, angle):
    rotation_matrix = numpy.array([[math.cos(angle), -math.sin(angle), 0],
                                   [math.sin(angle), math.cos(angle), 0],
                                   [0, 0, 1]])
    camera.location = numpy.dot(camera.location, rotation_matrix)
    reset_camera_rotation(camera)
    camera.rotation_euler[2] -= math.pi/2

def reset_camera_rotation(camera):
    # make camera to look at the world origin
    camera_location = camera.matrix_world.to_translation()
    camera_direction = - camera_location
    camera.rotation_euler = camera_direction.to_track_quat('-Z', 'Y').to_euler()

# Apply the render settings.
class SpriteFrameGeneratorRenderSettingsAction(bpy.types.Operator):
    """Apply the render settings."""
    bl_idname = "sprite_frame_generator.apply_render_settings"
    bl_label = "Apply Render Settings"
    bl_options = {'REGISTER'}

    def execute(self, context):
        apply_render_settings(context)
        return {'FINISHED'}


# Configurations
class SpriteFrameGeneratorConfig(bpy.types.PropertyGroup):
    """The configuration for the sprite frame generator."""
    render_expanded: bpy.props.BoolProperty(
        name="Camera Settings", default=True)
    render_resolution: bpy.props.IntVectorProperty(name="Resolution", default=(
        1920, 1080), size=2, min=1, max=10000)
    render_rotation_angles: bpy.props.IntProperty(
        name="Rotation Angles", default=4, min=1, max=10000)
    render_fps: bpy.props.IntProperty(name="FPS", default=30, min=1, max=10000)
    animation_frame_step: bpy.props.IntProperty(
        name="Frame Step", default=1, min=1, max=10000)

    output_expanded: bpy.props.BoolProperty(
        name="Output Settings", default=True)
    output_path: bpy.props.StringProperty(
        name="Output Folder", default="", subtype='DIR_PATH')

    action_list_expanded: bpy.props.BoolProperty(
        name="Action Settings", default=True)
    action_list: bpy.props.BoolVectorProperty(name="Action List", size=30, default=[True] * 30) # NOTE: Strange, I cannot set a higher size number than 30. I don't know why.

# The main operator to generate the sprite frames.
class SpriteFrameGeneratorRenderAction(bpy.types.Operator):
    """Render the sprite frames."""
    bl_idname = "sprite_frame_generator.render_sprite_frames"
    bl_label = "Render Sprite Frames"
    bl_options = {'REGISTER'}

    _timer = None
    th = None
    stop_early = False

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)
        self.stop_early = True
        self.th.join()

    def modal(self, context, event):
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel(context)
            self.report({'INFO'}, "Rendering canceled.")
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self.th.is_alive():
                return {'PASS_THROUGH'}
            else:
                self.cancel(context)
                self.report({'INFO'}, "Rendering finished.")
                return {'FINISHED'}

        return {'PASS_THROUGH'}

    def execute(self, context):
        apply_render_settings(context)
        # notify the user that the rendering has started.
        self.report({'INFO'}, "Rendering started.")

        self.output_path = bpy.path.abspath(context.scene.sprite_frame_generator_config.output_path)
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
        
        # Get list of selected objects.
        self.selected_objects = bpy.context.selected_objects
        
        if len(self.selected_objects) == 0:
            self.report({'ERROR'}, "No object is selected.")
            return {'CANCELLED'}

        # Cancel if a selected object has no animation data.
        for obj in self.selected_objects:
            if obj.animation_data is None:
                self.report({'ERROR'}, "Object " + obj.name + " has no animation data.")
                return {'CANCELLED'}
        
        # Cancel if no action is selected.
        if not any(context.scene.sprite_frame_generator_config.action_list):
            self.report({'ERROR'}, "No action is selected.")
            return {'CANCELLED'}

        def long_task(self):
            # Loop through all actions.
            for i in range(len(bpy.data.actions)):
                if self.stop_early:
                    return
                action = bpy.data.actions[i]
                # Check if the action is selected.
                if not bpy.context.scene.sprite_frame_generator_config.action_list[i]:
                    continue

                self.report({'INFO'}, "Rendering action " + action.name + "...")

                # dynamically set the last frame to render based on the action
                bpy.context.scene.frame_start = int(action.frame_range[0])
                bpy.context.scene.frame_end = int(action.frame_range[1])

                # delete action folder if it already exists
                action_folder = os.path.join(self.output_path, action.name)
                if os.path.exists(action_folder):
                    shutil.rmtree(action_folder)

                # Loop through all rotation angles.
                for j in range(bpy.context.scene.sprite_frame_generator_config.render_rotation_angles):
                    if self.stop_early:
                        return

                    self.report({'INFO'}, "Rendering direction " + str(j) + "...")
                    # create folder for the angle and action
                    angle_folder = os.path.join(self.output_path, action.name, "direction_"+str(j))

                    # create the folder if it doesn't exist
                    if not os.path.exists(angle_folder):
                        os.makedirs(angle_folder)
                    
                    # make all selected objects to rotate around the z axis
                    for obj in self.selected_objects:
                        # assign the action to the object
                        obj.animation_data.action = action
                    
                    # make the camera to rotate around the z axis at the center of the world, keeping the offset from the world origin.
                    camera = bpy.data.objects['Camera']

                    # make camera location vector to rotate around the z axis at the center of the world
                    rotate_camera_around_z_axis(camera, 2*math.pi/context.scene.sprite_frame_generator_config.render_rotation_angles)
                    
                    # set output file path
                    bpy.context.scene.render.filepath = os.path.join(angle_folder, "frame_####")

                    # render animation.
                    bpy.ops.render.render(animation=True)
        
        self.th = threading.Thread(target=long_task, args=(self,))
        self.th.start()

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}


# The main panel to control how the sprite frames are generated.
#
# Section 1: Render Settings
#
# - Define render resolution in pixels (width, height). Default is 1920x1080. Two text fields are given for convenience.
# - Define the number of rotation angles of the camera with respect to the z axis. Default is 4. We will split the 360 degrees into this many angles to repeat the render. Given as a text field.
# - Define fps (frames per second) of the animation. Default is 30. Given as a text field.
# - Define the number of skip frames between each render. Default is 0. Given as a text field.
#
# Section 2: Output Settings
#
# - Define the output folder. Default is the current folder. Given as a file dialog.
#
# Section 4: Action List
#
# - All actions are listed as checkboxes. The user can select which actions to render.
#
# Section 5: Render Button
#
# - Render button to start the rendering process.
#
class SpriteFrameGeneratorPanel(bpy.types.Panel):
    """Creates a Panel in the configect properties window"""
    bl_label = "Sprite Frame Generator"
    bl_category = "Sprite"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_options = {'HEADER_LAYOUT_EXPAND'}

    def draw(self, context):
        config = context.scene.sprite_frame_generator_config
        layout = self.layout
        # Use box layout
        box = layout.box()

        # Section 1: Camera Settings
        # Add prop for expanded property on config.
        box.row().prop(config, "render_expanded",
                       icon="TRIA_DOWN" if config.render_expanded else "TRIA_RIGHT", icon_only=True, emboss=False, text="Render Settings")

        if config.render_expanded:
            box.row().prop(config, "render_resolution", text="Resolution")
            box.row().prop(config, "render_rotation_angles", text="Rotation Angles")
            box.row().prop(config, "render_fps", text="FPS")
            box.row().prop(config, "animation_frame_step", text="Frame Step")
            box.row().operator("sprite_frame_generator.apply_render_settings", text="Apply Render Settings")

        # Section 2: Output Settings
        box = layout.box()
        # Add prop for expand property on config.
        box.row().prop(config, "output_expanded",
                       icon="TRIA_DOWN" if config.output_expanded else "TRIA_RIGHT", icon_only=True, emboss=False, text="Output Settings")

        if config.output_expanded:
            box.row().prop(config, "output_path", text="Output Folder")

        # Section 3: Action List
        box = layout.box()
        # Add prop for expanded property on config.
        box.row().prop(config, "action_list_expanded",
                       icon="TRIA_DOWN" if config.action_list_expanded else "TRIA_RIGHT", icon_only=True, emboss=False, text="Actions")

        if config.action_list_expanded:
            # if actions is None or empty, show a message.
            if len(config.action_list) == 0:
                box.row().label(text="No actions found.")
            else:
                all_actions = bpy.data.actions
                # for each action in the action map, add a checkbox.
                for i in range(len(all_actions)):
                    box.row().prop(config, "action_list",
                                   index=i, text=all_actions[i].name)

        # Section 4: Render Button
        layout.row().operator("sprite_frame_generator.render_sprite_frames", text="Render")


classes = (
    SpriteFrameGeneratorRenderAction,
    SpriteFrameGeneratorRenderSettingsAction,
    SpriteFrameGeneratorConfig,
    SpriteFrameGeneratorPanel,
)


def register():
    # for each class, register it using bpy.utils.register_class
    for cls in classes:
        bpy.utils.register_class(cls)
    # Add config object to the scene.
    bpy.types.Scene.sprite_frame_generator_config = bpy.props.PointerProperty(
        type=SpriteFrameGeneratorConfig)


def unregister():
    # Delete config object from the scene.
    del bpy.types.Scene.sprite_frame_generator_config
    # for each class, unregister it using bpy.utils.unregister_class
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
