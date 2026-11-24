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


def coursed_material(mat, color, paving=False):
    """Place staggered joints in world metres across separately exported meshes."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    surface = nodes.get("Principled BSDF")
    geometry = nodes.new("ShaderNodeNewGeometry")
    position = nodes.new("ShaderNodeSeparateXYZ")
    normal = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geometry.outputs["Position"], position.inputs[0])
    links.new(geometry.outputs["Normal"], normal.inputs[0])
    projected = nodes.new("ShaderNodeCombineXYZ")
    if paving:
        links.new(position.outputs["X"], projected.inputs["X"])
        links.new(position.outputs["Y"], projected.inputs["Y"])
    else:
        absolute = nodes.new("ShaderNodeMath")
        absolute.operation = "ABSOLUTE"
        links.new(normal.outputs["X"], absolute.inputs[0])
        horizontal = nodes.new("ShaderNodeMixRGB")
        links.new(absolute.outputs[0], horizontal.inputs[0])
        links.new(position.outputs["X"], horizontal.inputs[1])
        links.new(position.outputs["Y"], horizontal.inputs[2])
        links.new(horizontal.outputs["Color"], projected.inputs["X"])
        links.new(position.outputs["Z"], projected.inputs["Y"])
    brick = nodes.new("ShaderNodeTexBrick")
    links.new(projected.outputs[0], brick.inputs["Vector"])
    brick.inputs["Scale"].default_value = 1
    brick.inputs["Brick Width"].default_value = .58 if paving else 1.12
    brick.inputs["Row Height"].default_value = .30 if paving else .46
    brick.inputs["Mortar Size"].default_value = .005 if paving else .003
    brick.inputs["Mortar Smooth"].default_value = .002
    rgb = [linear(color[i:i+2]) for i in (1, 3, 5)]
    for name, factor in (("Color1", .96), ("Color2", 1.04), ("Mortar", .74)):
        brick.inputs[name].default_value = (*[min(1, c*factor) for c in rgb], 1)
    variation = nodes.new("ShaderNodeMixRGB")
    variation.blend_type = "MULTIPLY"
    variation.inputs[0].default_value = .22
    links.new(surface.inputs["Base Color"].links[0].from_socket, variation.inputs[2])
    links.new(brick.outputs["Color"], variation.inputs[1])
    links.new(variation.outputs[0], surface.inputs["Base Color"])
    joints = nodes.new("ShaderNodeBump")
    joints.invert = True
    joints.inputs["Distance"].default_value = .008 if paving else .004
    joints.inputs["Strength"].default_value = .45
    links.new(surface.inputs["Normal"].links[0].from_socket, joints.inputs["Normal"])
    links.new(brick.outputs["Fac"], joints.inputs["Height"])
    links.new(joints.outputs[0], surface.inputs["Normal"])


CLASSICAL_FINISHES = {
    "#e5dfd4": ("#e9dfce", "stone"),
    "#b0a08a": ("#e0d1b8", "stone"),
    "#618a9b": ("#53636a", "glass"),
    "#a09a8e": ("#b4a591", "stone"),
    "#aaa59a": ("#c6b9a4", "stone"),
}

def orient(obj,target):
    obj.rotation_euler = (target-obj.location).to_track_quat("-Z","Y").to_euler()


def main(input_path, output_path):
    request = json.loads(input_path.read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    classical = request.get("style") == "classical"
    groups = {}
    for face, color in request["faces"]:
        groups.setdefault(color,[]).append(face)
    all_points = [point for faces in groups.values() for face in faces for point in face]
    minimum = [min(v[i] for v in all_points) for i in range(3)]
    maximum = [max(v[i] for v in all_points) for i in range(3)]
    minimum, maximum = request.get("framing_bounds", (minimum, maximum))
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
        finish, kind = CLASSICAL_FINISHES.get(color, (color, kind)) if classical else (color, kind)
        mat = material(finish, kind)
        if classical and color == "#e5dfd4":
            coursed_material(mat, finish)
        mesh.materials.append(mat)
    bpy.ops.mesh.primitive_plane_add(size=diameter*100, location=(center.x,center.y,minimum[2]-.012))
    ground_color = "#a29989" if classical else "#a39b89"
    ground_mat = material(ground_color, "ground")
    if classical:
        coursed_material(ground_mat, ground_color, paving=True)
    bpy.context.object.data.materials.append(ground_mat)
    world = bpy.data.worlds.new("Daylight")
    scene.world = world
    world.use_nodes = True
    sky = world.node_tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(38)
    sun_offset = Vector((18, -12, 17) if classical else (-18, -24, 31))
    if classical:
        sky.sun_elevation = math.atan2(sun_offset.z, math.hypot(sun_offset.x, sun_offset.y))
    sky.sun_rotation = math.atan2(sun_offset.y, sun_offset.x) if classical else math.radians(135)
    sky.sun_disc = False
    background = world.node_tree.nodes.get("Background")
    background.inputs["Strength"].default_value = .31
    world.node_tree.links.new(sky.outputs["Color"],background.inputs["Color"])
    sun = bpy.data.lights.new("Sun","SUN")
    sun.energy = 2.2
    sun.angle = math.radians(3)
    lamp = bpy.data.objects.new("Sun",sun)
    scene.collection.objects.link(lamp)
    lamp.location = center+sun_offset
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
    if "entry_camera" in request:
        close = request["entry_camera"]
        camera.location = Vector(close["eye"])
        orient(camera, Vector(close["target"]))
        camera.data.lens = 17
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
    scene.render.resolution_x, scene.render.resolution_y = request.get("resolution", (3840, 2160))
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)


source, output = map(Path,sys.argv[sys.argv.index("--")+1:])
main(source,output)
