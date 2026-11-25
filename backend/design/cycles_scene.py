"""Headless Blender scene. Run under Blender's bundled Python."""
import json
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def linear(channel):
    value = int(channel,16)/255
    return value/12.92 if value < .04045 else ((value+.055)/1.055)**2.4


def material(hex_color, kind):
    color = tuple(linear(hex_color[i:i+2]) for i in (1,3,5))
    mat = bpy.data.materials.new(kind+" "+hex_color)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    surface = nodes.get("Principled BSDF")
    surface.inputs["Base Color"].default_value = (*color,1)
    if kind == "glass":
        surface.inputs["Roughness"].default_value = .13
        surface.inputs["Metallic"].default_value = .19
        surface.inputs["Coat Weight"].default_value = .65
        surface.inputs["Transmission Weight"].default_value = .14
        return mat
    if kind == "metal":
        surface.inputs["Metallic"].default_value = .49
        surface.inputs["Roughness"].default_value = .32
        return mat
    surface.inputs["Roughness"].default_value = .79 if kind != "wood" else .46
    noise = nodes.new("ShaderNodeTexNoise")
    coordinates = nodes.new("ShaderNodeTexCoord")
    if kind == "wood":
        mapping = nodes.new("ShaderNodeVectorMath")
        mapping.operation = "MULTIPLY"
        mapping.inputs[1].default_value = (18,18,.32)
        links.new(coordinates.outputs["Object"],mapping.inputs[0])
        links.new(mapping.outputs["Vector"],noise.inputs["Vector"])
    else:
        links.new(coordinates.outputs["Object"],noise.inputs["Vector"])
    noise.inputs["Scale"].default_value = 1.3 if kind=="ground" else 16
    noise.inputs["Detail"].default_value = 3
    tone = nodes.new("ShaderNodeValToRGB")
    for stop, mult in zip(tone.color_ramp.elements, (.73,1.16)):
        stop.color = (*[min(1,v*mult) for v in color],1)
    links.new(noise.outputs["Fac"],tone.inputs["Fac"])
    links.new(tone.outputs["Color"],surface.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = .21
    bump.inputs["Distance"].default_value = .013
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], surface.inputs["Normal"])
    return mat


def orient(obj,target):
    obj.rotation_euler = (target-obj.location).to_track_quat("-Z","Y").to_euler()


def main(input_path, output_path):
    request = json.loads(input_path.read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    groups = {}
    for face, color in request["faces"]:
        groups.setdefault(color,[]).append(face)
    all_points = [point for faces in groups.values() for face in faces for point in face]
    minimum = [min(v[i] for v in all_points) for i in range(3)]
    maximum = [max(v[i] for v in all_points) for i in range(3)]
    center = Vector([(a+b)/2 for a,b in zip(minimum,maximum)])
    diameter = max(1,(Vector(maximum)-Vector(minimum)).length)
    for color, faces in groups.items():
        indices, vertices, polygons = {}, [], []
        for face in faces:
            polygon = []
            for point in face:
                key = tuple(point)
                if key not in indices:
                    indices[key] = len(vertices)
                    vertices.append(point)
                polygon.append(indices[key])
            if len(set(polygon)) >= 3:
                polygons.append(polygon)
        mesh = bpy.data.meshes.new("Villa")
        mesh.from_pydata(vertices,[],polygons)
        mesh.validate()
        mesh.update()
        obj = bpy.data.objects.new("Villa "+color,mesh)
        scene.collection.objects.link(obj)
        kind = {"#618a9b":"glass","#353a3f":"metal","#845737":"wood"}.get(color,"stone")
        mesh.materials.append(material(color,kind))
    bpy.ops.mesh.primitive_plane_add(size=diameter*100, location=(center.x,center.y,minimum[2]-.012))
    bpy.context.object.data.materials.append(material("#a39b89","ground"))
    world = bpy.data.worlds.new("Daylight")
    scene.world = world
    world.use_nodes = True
    sky = world.node_tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(38)
    sky.sun_rotation = math.radians(135)
    sky.sun_disc = False
    background = world.node_tree.nodes.get("Background")
    background.inputs["Strength"].default_value = .31
    world.node_tree.links.new(sky.outputs["Color"],background.inputs["Color"])
    sun = bpy.data.lights.new("Sun","SUN")
    sun.energy = 2.2
    sun.angle = math.radians(3)
    lamp = bpy.data.objects.new("Sun",sun)
    scene.collection.objects.link(lamp)
    lamp.location = center+Vector((-18,-24,31))
    orient(lamp,center)
    camera = bpy.data.objects.new("Architectural camera",bpy.data.cameras.new("Architectural camera"))
    scene.collection.objects.link(camera)
    scene.camera = camera
    view = request["camera"]
    yaw,pitch,zoom = view["yaw"],view["pitch"],view["zoom"]
    direction = Vector((-math.sin(yaw)*math.cos(pitch),-math.cos(yaw)*math.cos(pitch),math.sin(pitch)))
    camera.location = center+direction*(diameter*1.18/zoom)
    orient(camera,center)
    camera.data.clip_end = diameter*160
    if view["mode"] == "elevation":
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = diameter*1.14/zoom
    else:
        camera.data.lens = 43
    camera.data.sensor_fit="HORIZONTAL"
    camera.data.shift_x=-view.get("pan_x",0)
    camera.data.shift_y=view.get("pan_y",0)*9/16
    scene.render.engine = "CYCLES"
    import _cycles
    denoise = bool(getattr(_cycles, "with_openimagedenoise", False))
    scene.cycles.samples = min(256,max(8,int(os.getenv("ANT_RENDER_SAMPLES", "12" if denoise else "16"))))
    scene.cycles.adaptive_threshold = .085 if denoise else .055
    scene.cycles.adaptive_min_samples = min(scene.cycles.samples,6 if denoise else 12)
    scene.cycles.use_denoising = denoise
    scene.cycles.use_auto_tile = False
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 2
    scene.view_settings.view_transform = "AgX"
    width = int(os.environ.get("ANT_RENDER_WIDTH", "3840"))
    if width not in (1280,1920,3840):
        raise ValueError("Unsupported render width")
    scene.render.resolution_x = width
    scene.render.resolution_y = width*9//16
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)


source, output = map(Path,sys.argv[sys.argv.index("--")+1:])
main(source,output)
