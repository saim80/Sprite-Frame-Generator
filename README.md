# Sprite Frame Generator Addon for Blender

This addon can generate animation frames from animated objects in blender.

## Setup

Using Blender's addon menu, install this folder that contains __init__.py.

## How to Use

Once installed, 3D view port's right side menu shows a category called "Sprite". Open it.

The addon's UI provides a set of convenient options to render sprite frames:
- Resolution of rendered frame images.
- The number of camera directions to render animations.
- Frames per seconds
- How many frames to skip when generating sprite frames.
- Output path (Note that sprites will be organized into 'Action Name' > 'Camera Direction' hierarchy.)
- List of actions to filter for sprite generation. By default, all actions are selected.

After reviewing the above options, hit 'render' button.

## Caveat

The blender will freeze until all renderning is finished. This is a known issue for now.
