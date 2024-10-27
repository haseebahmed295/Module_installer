
from calendar import c
import importlib
import inspect
import sys

import requests
if "bpy" in locals():
    importlib.reload(bpy)
import threading
import bpy
import subprocess
import os
import toml

Message = ""
def get_classes() -> list:
    current_module = sys.modules[__name__]
    classes = []
    for name, obj in inspect.getmembers(current_module):
        if inspect.isclass(obj) and obj.__module__ == __name__:
            classes.append(obj)
    return classes

class Module_installer(bpy.types.Operator):
    """Operator to install modules"""
    bl_idname = "module_installer.install"
    bl_label = "Module Installer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return not context.scene.intalling

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set:
        """
        Handles the timer events for the modal operator.

        This function is called every 0.01s while the operator is running.
        It checks if the upscaling thread is outputing any things and if so, it reports the output and resets the
        is_updated flag so that the operator can be exited.
        """
        if event.type == 'TIMER':
            if not self.is_working:
                if self._is_error:
                    self.report({"ERROR"}, "Installation Failed")
                else:
                    self.report({"INFO"}, "Installation Done")
                context.scene.intalling = False
                bpy.app.timers.register(self.reload, first_interval=2)
                
                return {'FINISHED'}

        return {'PASS_THROUGH'}
        
    def execute(self, context):
        if not bpy.app.online_access:
            self.report({"ERROR"}, "No internet connection")
            return {'CANCELLED'}
        if context.scene.module_to_install == "":
            self.report({"ERROR"}, "Enter Module Name")
            return {'CANCELLED'}
        if not self.check_package_on_pypi(context.scene.module_to_install):
            self.report({"ERROR"}, "Module Not Found")
            return {'CANCELLED'}
        self._is_error = False
        self.is_working = True
        toml_path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
        wheels_path = os.path.join(os.path.dirname(__file__), "wheels")
        module = context.scene.module_to_install.strip() 
        # Start the upscaling thread
        module_thread = threading.Thread(
            target=self.install_modules,
            args=(
                module,wheels_path,toml_path
            )
        )
        module_thread.start()
        context.scene.intalling = True
        # Start the timer to check for updates
        self.report({"INFO"} , "Installing Modules... 😎")
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def check_package_on_pypi(self,package_name):
        try:
            url = f"https://pypi.org/pypi/{package_name}/json"
            response = requests.get(url)
            
            if response.status_code == 200:
                return True
            elif response.status_code == 404:
                return False
            else:
                raise ValueError(f"Unexpected status code: {response.status_code}")
        
        except requests.RequestException as e:
            print(f"An error occurred: {e}")
            return None
    def install_modules(self , module_name , wheels_path , toml_path):
        wheel_list = self.download_wheels(module_name , wheels_path)
        if len(wheel_list) == 0:
            self.is_working = False
        for wheel in wheel_list:
            self.append_wheel(toml_path , wheel)
        self.is_working = False
        return
    def reload(self):
        bpy.ops.script.reload()
        bpy.ops.module_installer.load_wheels(cmd="LOAD")
    def append_wheel(self, file_path , module:str):
        try:
            # Read and parse the TOML file
            with open(file_path, 'r') as f:
                config = toml.load(f)
            
            wheel_name = f"./wheels/{module}"

            # Example: Add a new wheel
            if wheel_name not in config['wheels']:
                config['wheels'].append(wheel_name)
            
            # Write the modified configuration back to the file
            with open(file_path, 'w') as f:
                toml.dump(config, f)
        except FileNotFoundError:
            print(f"The file {file_path} was not found.")
        except toml.TomlDecodeError:
            print(f"Failed to parse TOML file: {file_path}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
    def download_wheels(self, module_name, output_dir):
        try:
            # Construct and execute the pip download command
            command = ["pip", "download", module_name, f"--dest={output_dir}"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            for line in iter(process.stdout.readline, ""):
                print(line.strip())

            # Collect downloaded wheel files
            wheel_files = [f for f in os.listdir(output_dir) if f.endswith('.whl')]

            return wheel_files

        except Exception as e:
            print(f"An error occurred: {str(e)}")
            self._is_error = True
            return []
class Remove_Module(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "module_installer.remove_module"
    bl_label = "Remove Module"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "index"

    index : bpy.props.IntProperty(options={'HIDDEN'})

    def execute(self, context):
        prop = context.scene.module_list[self.index]
        self.remove_wheel(prop)
        os.remove(os.path.join(os.path.dirname(__file__), "wheels", prop.path))
        context.scene.module_list.remove(self.index)
        return {'FINISHED'}
    def remove_wheel(self,prop):
        try:
            toml_path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
            module = prop.name
            # Read and parse the TOML file
            with open(toml_path, 'r') as f:
                config = toml.load(f)
            
            wheel_name = f"./wheels/{module}"
            # Modify the wheels list
            if wheel_name in config['wheels']:
                config['wheels'].remove(wheel_name)
            # Write the modified configuration back to the file
            with open(toml_path, 'w') as f:
                toml.dump(config, f)
        except FileNotFoundError:
            print(f"The file {toml_path} was not found.")
        except toml.TomlDecodeError:
            print(f"Failed to parse TOML file: {toml_path}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")
class Wheels_lister(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "module_installer.load_wheels"
    bl_label = "Wheel Lister"

    cmd : bpy.props.StringProperty()
    def execute(self, context):
        global Message
        if self.cmd == "LOAD":
            self.load_wheels(context)
            if len(context.scene.module_list) == 0:
                Message = "No wheels found"
        elif self.cmd == "CLEAR":
            context.scene.module_list.clear()
            Message = "Cleared Successfully"
        elif self.cmd == "RELOAD":
            bpy.app.timers.register(self.reload , first_interval = 2)
            bpy.context.scene.intalling = True
        elif self.cmd == "UN_ALL":
            self.load_wheels(context)
            for i in range(len(context.scene.module_list)):
                bpy.ops.module_installer.remove_module(index = 0)
            Message = "Uninstalled All Modules Successfully"
        return {'FINISHED'}
    def load_wheels(self, context):
        context.scene.module_list.clear()
        wheels_path = os.path.join(os.path.dirname(__file__), "wheels")
        for filename in os.listdir(wheels_path):
            if filename.endswith('.whl'):
                prop = context.scene.module_list.add()
                prop.name = filename
                prop.path = os.path.join(wheels_path, filename)
        return len(context.scene.module_list)
    def reload(self):
        bpy.ops.script.reload()
        bpy.context.scene.intalling = False
        global Message
        Message = "Reloaded Successfully"
class MI_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    def draw(self, context):
        layout = self.layout
        layout.enabled = not context.scene.intalling
        
        scene = context.scene
        row = layout.row()
        row.prop(scene, 'module_to_install' , text="Module Name")
        row.operator(Module_installer.bl_idname , text="Install")

        row_ = layout.row()

        row = row_.row(align=True)
        row.operator(Wheels_lister.bl_idname , text="List").cmd = "LOAD"
        row.operator(Wheels_lister.bl_idname , text="Hide List").cmd = "CLEAR"
        row = row.row(align=True)
        row.operator(Wheels_lister.bl_idname , text="Reload").cmd = "RELOAD"
        row.operator(Wheels_lister.bl_idname , text="Uninstall All").cmd = "UN_ALL"

        # Create a grid flow with 2 columns
        col_flow = layout.grid_flow(columns=1, align=True)
        # Assuming module_list is a collection property
        for i, module in enumerate(context.scene.module_list):
            box = col_flow.box()
            row = box.row(align=True)
            # First column: Show module name
            row.label(text=module.name)
            # Second column: Add operator button
            op = row.operator(Remove_Module.bl_idname, text="", icon="TRASH")
            op.index = i
        if Message != "":
            box = layout.box()
            box.label(text = Message)
class Module_Prop(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    path: bpy.props.StringProperty()
def register():
    for cls in get_classes():
            bpy.utils.register_class(cls)

    bpy.types.Scene.module_to_install = bpy.props.StringProperty(
        name="Module to Install",
        description="Module to install",
        default="",
    )
    bpy.types.Scene.module_list = bpy.props.CollectionProperty(type=Module_Prop)
    bpy.types.Scene.intalling = bpy.props.BoolProperty(default=False)
def unregister():
    for cls in get_classes():
            bpy.utils.unregister_class(cls)

    del bpy.types.Scene.module_to_install

if __name__ == "__main__":
    register()