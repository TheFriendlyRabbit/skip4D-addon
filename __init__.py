bl_info = {
    "name": "Skip4D Base Plugin",
    "description": "Optimizer plugin for Skip4D's VRChat model base",
    "author": "Aura (https://twitter.com/RedBirdRabbit)", 
    "version": (0, 2, 1),
    "blender": (2, 80, 0),
    "location": "View3D",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Generic"}

import bpy
import pathlib
from bpy.types import Operator
from mathutils import Matrix

# Materials counter function ===================================================================================

class SkipMaterialsCount(Operator):
    
    # Change this label to change the text on the button
    bl_label = "Count Active Materials"
    
    # Ignore
    bl_idname = "object.skip_count_materials"

    def execute(self, context):
        
        # DON'T TOUCH ===========================================================================================
        
        # Collect visible meshes
        meshes = [ob for ob in bpy.context.scene.objects if (ob.visible_get() and ob.type == 'MESH')]
        
        # Count materials that are actually used on meshes
        used_materials = []
        for mesh in meshes:
            for idx, mat in enumerate(mesh.material_slots):
                if mat.material not in used_materials:
                    for p in mesh.data.polygons:
                        if p.material_index == idx:
                            used_materials.append(mat.material)
                            break
        
        self.report({"INFO"}, f"Counted {len(used_materials)} active materials.")
        return {'FINISHED'}
        
        # END DON'T TOUCH ======================================================================================


# Merger function ==============================================================================================

class SkipOptim(Operator):
    
    # Change this label to change the text on the button
    bl_label = "Optimize Model"
    
    # Ignore
    bl_idname = "object.skip_optim_modelbase"

    def execute(self, context):
        
        # Edit this if you've changed the collection to which the base armature belongs
        ARMATURE_COLL_NAME = "skip4d Chibi Base"
        
        # Edit this if you've changed the name of the base armature
        ARMATURE_NAME = "Armature"
        
        # Edit this if you've changed the name of the body mesh
        BODY_NAME = "Body"
        
        # Edit this if you need more collections. Format is "parent bone": [collection names]
        MERGE_CORRESPONDENCES = {
                                 "head": ["Cheek Fluff", "Ears", "Hairstyles"],
                                 "hips": ["Tails"]
                                }
        
        # Edit this to add additional items that should NOT be merged into the base body mesh.                        
        DO_NOT_MERGE = ["Hoodie", "Hoodie - Mesh", "Collar - Regular", "Collar - Regular Mesh", "Collar - Spiked", "Collar - Spiked Mesh"]
        
        # Edit this to add FULL COLLECTIONS which should not be merged into the base body mesh.
        STANDALONE_COLLS = ["CUSTOMIZATION MENU", "Clothing DLC", "Accessories DLC"]
        
        # Edit this if you've changed the name of the customization UI armature object
        CUSTOM_UI_NAME = "CUSTOMIZATION UI"
        
        
        # DON'T TOUCH ===========================================================================================
        
        print("Attempting backup...")
        
        # Backup
        blender_file_path = pathlib.Path(bpy.data.filepath)
        new_file_path = str(bpy.data.filepath[:-6] + "_unmerged.blend")
        bpy.ops.wm.save_as_mainfile(filepath=new_file_path, copy=True)
        
        self.report({"INFO"}, f"Pre-merge file backed up as {new_file_path}")
        
        # Hacky fix for "Unable to pack file" issue
        if bpy.data.use_autopack:
            self.report({"INFO"}, "User enabled texture autopack. Disabling.")
            bpy.ops.file.autopack_toggle()
        
        print("Merging...")
        
        skip_armature = None
        base_mesh = None
        merge_armatures = {}
        
        success = []
        
        for bone in MERGE_CORRESPONDENCES.keys():
            merge_armatures[bone] = []
        
        for collection in bpy.data.collections:
            if collection.name == ARMATURE_COLL_NAME:
                # Get base armature object
                skip_armature = collection.objects[ARMATURE_NAME]
                base_mesh = collection.objects[BODY_NAME]
            else:
                # Collect all visible items into merge_armatures
                for bone, colls in MERGE_CORRESPONDENCES.items():
                    if collection.name in colls:
                        merge_armatures[bone].extend([ob for ob in collection.objects if (ob.visible_get() and ob.type == 'ARMATURE')])
        
        # Set armature as active object
        bpy.context.view_layer.objects.active = skip_armature
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
        
        for bone_name, merge_objs in merge_armatures.items():
            
            if len(merge_objs) > 0:
                # Merge objects on a per-target-parent basis
                meshes = [base_mesh]
                
                # Merge armatures one at a time to handle bone parenting    
                for arm in merge_objs:
                    # Clear armature transform
                    bpy.context.view_layer.objects.active = arm
                    with bpy.context.temp_override(active_object=arm, selected_editable_objects=[arm]):
                        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                    
                    # Ensure all armatures are in rest position
                    for pose_bone in arm.pose.bones:
                        if pose_bone.matrix_basis != Matrix():
                            self.report({"ERROR"}, (f"Armature {arm.name} was modified in pose mode. "
                                                        "The merge was cancelled to avoid overwriting user changes. "
                                                        "Use 'Apply Selected as Rest Pose' to set current pose as rest pose. "))
                            return {'CANCELLED'}
                    
                    # Find root bones
                    unparented_bones = []
                    
                    for merge_bone in arm.data.bones:
                        if not merge_bone.parent:
                            unparented_bones.append(merge_bone.name)
                            
                    # Merge armatures
                    bpy.context.view_layer.objects.active = skip_armature
                    with bpy.context.temp_override(active_object=skip_armature, selected_editable_objects=[skip_armature, arm]):
                        bpy.ops.object.join()
                       
                    # Handle parenting
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.context.view_layer.objects.active = skip_armature
                    with bpy.context.temp_override(mode='EDIT_ARMATURE', active_object=skip_armature, selected_editable_objects=[skip_armature]):
                        for name, bone in skip_armature.data.edit_bones.items():
                            if name in unparented_bones:
                                bone.parent = skip_armature.data.edit_bones[bone_name]
                    bpy.ops.object.mode_set(mode='OBJECT')
                        
                success.append(bone_name)  
        
        # Failed merge warnings
        for bone, children in merge_armatures.items():
            if len(children) > 0 and bone not in success:
                self.report({"WARNING"}, (f"The bone {bone} is missing from the base armature. " 
                                                "If you haven't modified the armature yourself, "
                                                 "tell Skip about this!"))
                                                 
        # Clean viewport visibility drivers on armature
        for driver in skip_armature.animation_data.drivers.values():      
             skip_armature.driver_remove(driver.data_path)
                                                 
        # Collect legal visible meshes
        meshes = [ob for ob in bpy.context.scene.objects if (ob.visible_get() and ob.type == 'MESH' and ob.name not in DO_NOT_MERGE and all(coll.name not in STANDALONE_COLLS for coll in ob.users_collection))]  
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # Make sure armature modifiers have the correct target, apply all other modifiers
        for ob in meshes:
            bpy.context.view_layer.objects.active = ob
            if ob.modifiers:
                for mod in ob.modifiers:
                    if mod.type == 'ARMATURE':
                        mod.object = skip_armature
                    else:
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                        
                          
        # Clear additional drivers from e.g. hoodie
        hidden_meshes = [ob for ob in bpy.context.scene.objects if ob not in meshes]  
        for ob in hidden_meshes:
            if ob.animation_data:
                for driver in ob.animation_data.drivers.values():      
                    ob.driver_remove(driver.data_path)
                        
        # Merge visible meshes into parent mesh
        bpy.context.view_layer.objects.active = base_mesh
        with bpy.context.temp_override(active_object=base_mesh, selected_editable_objects=meshes):
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            bpy.ops.object.join()
         
        # Cleanup   
        for ob in bpy.data.objects:
            if ob.hide_viewport or ob.hide_render or ob.hide_get() or ob.name == CUSTOM_UI_NAME: 
                bpy.data.objects.remove(ob, do_unlink=True)
        
        return {'FINISHED'}
    
        # END DON'T TOUCH ======================================================================================


# Registers the UI panel =======================================================================================

class SkipPanel(bpy.types.Panel):
    
    # Change this label to change the name of the panel
    bl_label = "Optimize Model"
    
    # Change this label to change the name of the category tab in which the panel appears
    bl_category = "Skip4D"
    
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    
    
    def draw(self, context):
        layout = self.layout
        
        # Registers the optimizer button. Change the "icon" parameter to change the small icon that displays on the button
        layout.operator(SkipOptim.bl_idname, text=SkipOptim.bl_label, icon="FULLSCREEN_EXIT")
        
        # Registers the optimizer button. Change the "icon" parameter to change the small icon that displays on the button
        layout.operator(SkipMaterialsCount.bl_idname, text=SkipMaterialsCount.bl_label, icon="SHADING_RENDERED")



# Below this line: registering and unregistering the add-on - ignore ===========================================

def register():
    bpy.utils.register_class(SkipOptim)
    bpy.utils.register_class(SkipMaterialsCount)
    bpy.utils.register_class(SkipPanel)

def unregister():
    bpy.utils.unregister_class(SkipOptim)
    bpy.utils.unregister_class(SkipMaterialsCount)
    bpy.utils.unregister_class(SkipPanel)

if __name__ == "__main__":
    register()