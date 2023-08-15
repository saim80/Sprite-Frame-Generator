# (c) 2023 Pururum LLC
# This code is licensed under MIT license (see LICENSE for details)

import bpy
import os
import math
import numpy
import threading
import shutil

{
    "name": "Sprite Frame Generator",
    "author": "Pururum LLC",
    "version": (1, 1, 0),
    "blender": (3, 0),
    "location": "View3D > Sidebar > Sprite Frame Generator",
    "description": "Generates sprite frames from a 3D model.",
    "category": "3D View",
}

################
# Global Functions
################

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

################
# Data Structures
################

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

    composite_expanded: bpy.props.BoolProperty(
        name="Pixel Art Settings", default=True)
    composite_pixel_size: bpy.props.FloatProperty(
        name="Pixel Size", default=12.0, min=1.0, max=10000.0)
    composite_color_palette_size: bpy.props.FloatProperty(
        name="Color Palette Size", default=30.0, min=1.0, max=10000.0)

################
# Operators
################

class SpriteFrameGeneratorConfirmCompositeNodesAction(bpy.types.Operator):
    """Warning: This will clear all nodes in the compositor."""
    bl_idname = "sprite_frame_generator.confirm_composite_nodes"
    bl_label = "Delete All Composite Nodes"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        bpy.ops.sprite_frame_generator.generate_composite_nodes()
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

# The operator to generate composite nodes for pixelation effect.
class SpriteFrameGeneratorCompositeNodesAction(bpy.types.Operator):
    """Generates composite nodes for pixelation effect."""
    bl_idname = "sprite_frame_generator.generate_composite_nodes"
    bl_label = "Generate Composite Nodes"
    bl_options = {'REGISTER'}

    def execute(self, context):
        config = context.scene.sprite_frame_generator_config

        # clear all nodes
        bpy.context.scene.use_nodes = True
        tree = bpy.context.scene.node_tree
        for node in tree.nodes:
            tree.nodes.remove(node)
        
        # Add Render Layers node
        render_layers_node = tree.nodes.new(type='CompositorNodeRLayers')
        render_layers_node.location = (0, 0)

        # Create blur node
        blur_node = tree.nodes.new(type='CompositorNodeBlur')
        blur_node.location = (200, 0)
        blur_node.filter_type = 'GAUSS'
        blur_node.size_x = 1
        blur_node.size_y = 1

        # Connect Blur and Render Layers Nodes
        tree.links.new(render_layers_node.outputs[0], blur_node.inputs[0])

        # Create a scale node
        scale_node = tree.nodes.new(type='CompositorNodeScale')
        scale_node.location = (400, 0)
        scale_node.space = 'RELATIVE'

        # Connect Scale and Blur Nodes
        tree.links.new(blur_node.outputs[0], scale_node.inputs[0])

        # Create Pixelate node
        pixelate_node = tree.nodes.new(type='CompositorNodePixelate')
        pixelate_node.location = (600, 0)

        # Connect Pixelate and Scale Nodes
        tree.links.new(scale_node.outputs[0], pixelate_node.inputs[0])

        # Create Scale node
        scale_node2 = tree.nodes.new(type='CompositorNodeScale')
        scale_node2.location = (800, 0)
        scale_node2.space = 'RELATIVE'

        # Connect Scale and Pixelate Nodes
        tree.links.new(pixelate_node.outputs[0], scale_node2.inputs[0])

        # Create Separate Color node
        separate_color_node = tree.nodes.new(type='CompositorNodeSeparateColor')
        separate_color_node.mode = 'HSV'
        separate_color_node.location = (1000, 0)

        # Connect Separate Color and Scale Nodes
        tree.links.new(scale_node2.outputs[0], separate_color_node.inputs[0])

        # Create Multiply node
        multiply_node = tree.nodes.new(type='CompositorNodeMath')
        multiply_node.location = (1200, -100)
        multiply_node.operation = 'MULTIPLY'

        # Connect Multiply and Separate Color Nodes
        tree.links.new(separate_color_node.outputs[2], multiply_node.inputs[0])

        # Create Round node
        round_node = tree.nodes.new(type='CompositorNodeMath')
        round_node.location = (1400, -100)
        round_node.operation = 'ROUND'

        # Connect Round and Multiply Nodes
        tree.links.new(multiply_node.outputs[0], round_node.inputs[0])

        # Create Divide node
        divide_node = tree.nodes.new(type='CompositorNodeMath')
        divide_node.location = (1600, -100)
        divide_node.operation = 'DIVIDE'

        # Connect Divide and Round Nodes
        tree.links.new(round_node.outputs[0], divide_node.inputs[0])

        # Create Combine HSV node
        combine_hsv_node = tree.nodes.new(type='CompositorNodeCombineColor')
        combine_hsv_node.mode = 'HSV'
        combine_hsv_node.location = (1800, 0)

        # Connect Combine HSV and Divide Nodes
        tree.links.new(divide_node.outputs[0], combine_hsv_node.inputs[2])
        # Connect Separate Color and Combine HSV Nodes
        tree.links.new(separate_color_node.outputs[0], combine_hsv_node.inputs[0])
        tree.links.new(separate_color_node.outputs[1], combine_hsv_node.inputs[1])

        # Create Viewer node
        viewer_node = tree.nodes.new(type='CompositorNodeViewer')
        viewer_node.location = (2000, 0)

        # Connect Viewer and Combine HSV Nodes
        tree.links.new(combine_hsv_node.outputs[0], viewer_node.inputs[0])

        # Create Composite node
        composite_node = tree.nodes.new(type='CompositorNodeComposite')
        composite_node.location = (2000, 100)

        # Connect Composite and Combine HSV Nodes
        tree.links.new(combine_hsv_node.outputs[0], composite_node.inputs[0])

        # Create Value node
        value_node = tree.nodes.new(type='CompositorNodeValue')
        value_node.location = (0, -300)
        value_node.outputs[0].default_value = config.composite_pixel_size
        value_node.name = 'Pixel Size'
        value_node.label = 'Pixel Size'

        # Create Divide node
        divide_node2 = tree.nodes.new(type='CompositorNodeMath')
        divide_node2.location = (300, -200)
        divide_node2.inputs[0].default_value = 1
        divide_node2.operation = 'DIVIDE'
        
        # Connect Divide and Value Nodes
        tree.links.new(value_node.outputs[0], divide_node2.inputs[1])

        # Connect Divide and Scale Nodes
        tree.links.new(divide_node2.outputs[0], scale_node.inputs[1])
        tree.links.new(divide_node2.outputs[0], scale_node.inputs[2])

        # Connect Value and Scale 2 Nodes
        tree.links.new(value_node.outputs[0], scale_node2.inputs[1])
        tree.links.new(value_node.outputs[0], scale_node2.inputs[2])

        # Create Value node for Color Palette Size
        value_node2 = tree.nodes.new(type='CompositorNodeValue')
        value_node2.location = (1000, -400)
        value_node2.outputs[0].default_value = config.composite_color_palette_size
        value_node2.name = 'Color Palette Size'
        value_node2.label = 'Color Palette Size'

        # Connect Value and Multiply Nodes
        tree.links.new(value_node2.outputs[0], multiply_node.inputs[1])
        # Connect Value and Divide Nodes
        tree.links.new(value_node2.outputs[0], divide_node.inputs[1])

        # Create Round node for Separate Color
        round_node2 = tree.nodes.new(type='CompositorNodeMath')
        round_node2.location = (1200, -400)
        round_node2.operation = 'ROUND'
        round_node2.use_clamp = True

        # Connect Round and Separate Color Nodes
        tree.links.new(separate_color_node.outputs[3], round_node2.inputs[0])

        # Connect Round and Combine HSV Nodes
        tree.links.new(round_node2.outputs[0], combine_hsv_node.inputs[3])

        return {'FINISHED'}

# Apply the render settings.
class SpriteFrameGeneratorRenderSettingsAction(bpy.types.Operator):
    """Apply the render settings."""
    bl_idname = "sprite_frame_generator.apply_render_settings"
    bl_label = "Apply Render Settings"
    bl_options = {'REGISTER'}

    def execute(self, context):
        apply_render_settings(context)
        return {'FINISHED'}


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


################
# Panels
################

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
        
        # Section 4: Composition Settings
        box = layout.box()
        # Add prop for expanded property on config.
        box.row().prop(config, "composite_expanded",
                          icon="TRIA_DOWN" if config.composite_expanded else "TRIA_RIGHT", icon_only=True, emboss=False, text="Pixel Art Settings")
        
        if config.composite_expanded:
            box.row().prop(config, "composite_pixel_size", text="Pixel Size")
            box.row().prop(config, "composite_color_palette_size", text="Color Palette Size")
            box.row().operator("sprite_frame_generator.confirm_composite_nodes", text="Apply Pixel Art")

        # Section 5: Render Button
        layout.row().operator("sprite_frame_generator.render_sprite_frames", text="Render")

################
# Registration
################

classes = (
    SpriteFrameGeneratorConfirmCompositeNodesAction,
    SpriteFrameGeneratorCompositeNodesAction,
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
