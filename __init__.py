from calendar import c
import importlib
import inspect
import sys
import requests
import threading
import bpy
import subprocess
import os
import toml

Message = ""

def get_classes() -> list:
    """Get a list of all classes in the current module."""
    current_module = sys.modules[__name__]
    classes = []
    for name, obj in inspect.getmembers(current_module):
        if inspect.isclass(obj) and obj.__module__ == __name__:
            classes.append(obj)
    return classes

class Module_installer(bpy.types.Operator):
    """Install a specified module from PyPI into Blender."""
    bl_idname = "module_installer.install"
    bl_label = "Module Installer"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        """Ensure installation can be performed only when no other installation is in progress."""
        return not context.scene.intalling

    def modal(self, context: bpy.types.Context, event: bpy.types.Event) -> set:
        """
        Handle timer events for monitoring installation progress.
        
        Checks every 0.01s for installation status and updates the user on success or failure.
        """
        if event.type == 'TIMER':
            if not self.is_working:
                if self._is_error:
                    self.report({"ERROR"}, "Installation Failed")
                else:
                    self.report({"INFO"}, "Reloading Modules...")
                context.scene.intalling = False
                bpy.app.timers.register(self.reload, first_interval=2)
                self.report({"INFO"}, "Installation Done")
                return {'FINISHED'}

        return {'PASS_THROUGH'}
        
    def execute(self, context):
        """Execute the installation process with validation checks."""
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
            args=(module, wheels_path, toml_path)
        )
        module_thread.start()
        context.scene.intalling = True
        self.report({"INFO"}, "Installing Modules... 😎")
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def check_package_on_pypi(self, package_name):
        """Check if the specified package is available on PyPI."""
        try:
            url = f"https://pypi.org/pypi/{package_name}/json"
            response = requests.get(url)
            return response.status_code == 200
        except requests.RequestException as e:
            print(f"An error occurred: {e}")
            return None
    
    def install_modules(self, module_name, wheels_path, toml_path):
        """Install the specified module and update the TOML configuration."""
        wheel_list = self.download_wheels(module_name, wheels_path)
        if len(wheel_list) == 0:
            self.is_working = False
        for wheel in wheel_list:
            self.append_wheel(toml_path, wheel)
        self.is_working = False
        return
    
    def reload(self):
        """Reload Blender scripts and update module list."""
        bpy.ops.script.reload()
        bpy.ops.module_installer.load_wheels(cmd="LOAD")
    
    def append_wheel(self, file_path, module: str):
        """Add the module to the TOML configuration."""
        try:
            with open(file_path, 'r') as f:
                config = toml.load(f)
            wheel_name = f"./wheels/{module}"
            if wheel_name not in config['wheels']:
                config['wheels'].append(wheel_name)
            with open(file_path, 'w') as f:
                toml.dump(config, f)
        except Exception as e:
            print(f"An error occurred: {str(e)}")
    
    def download_wheels(self, module_name, output_dir):
        """Download the module's wheel files."""
        try:
            command = ["pip", "download", module_name, f"--dest={output_dir}"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            for line in iter(process.stdout.readline, ""):
                print(line.strip())
            wheel_files = [f for f in os.listdir(output_dir) if f.endswith('.whl')]
            return wheel_files
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            self._is_error = True
            return []

class Remove_Module(bpy.types.Operator):
    """Remove a module from the installation list and update the configuration."""
    bl_idname = "module_installer.remove_module"
    bl_label = "Remove Module"
    bl_options = {'REGISTER', 'UNDO'}
    bl_property = "index"

    index: bpy.props.IntProperty(options={'HIDDEN'}, description="Index of the module to be removed")

    def execute(self, context):
        """Remove the selected module from Blender."""
        prop = context.scene.module_list[self.index]
        self.remove_wheel(prop)
        os.remove(os.path.join(os.path.dirname(__file__), "wheels", prop.path))
        context.scene.module_list.remove(self.index)
        return {'FINISHED'}
    
    def remove_wheel(self, prop):
        """Remove the module's wheel entry from the TOML configuration."""
        try:
            toml_path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
            module = prop.name
            with open(toml_path, 'r') as f:
                config = toml.load(f)
            wheel_name = f"./wheels/{module}"
            if wheel_name in config['wheels']:
                config['wheels'].remove(wheel_name)
            with open(toml_path, 'w') as f:
                toml.dump(config, f)
        except Exception as e:
            print(f"An error occurred: {str(e)}")

class Wheels_lister(bpy.types.Operator):
    """List, clear, reload, or uninstall all modules."""
    bl_idname = "module_installer.load_wheels"
    bl_label = "Wheel Lister"

    cmd: bpy.props.StringProperty(description="Command for managing module lists")

    def execute(self, context):
        """Execute the command to list, clear, reload, or uninstall modules."""
        global Message
        if self.cmd == "LOAD":
            self.load_wheels(context)
            if len(context.scene.module_list) == 0:
                Message = "No wheels found"
            else:
                Message = "Loaded Successfully"
        elif self.cmd == "CLEAR":
            context.scene.module_list.clear()
            Message = "Cleared Successfully"
        elif self.cmd == "RELOAD":
            bpy.app.timers.register(self.reload, first_interval=2)
            bpy.context.scene.intalling = True
        elif self.cmd == "UN_ALL":
            self.load_wheels(context)
            for i in range(len(context.scene.module_list)):
                bpy.ops.module_installer.remove_module(index=0)
            Message = "Uninstalled All Modules Successfully"
        return {'FINISHED'}
    
    def load_wheels(self, context):
        """Load installed modules from the wheels directory."""
        context.scene.module_list.clear()
        wheels_path = os.path.join(os.path.dirname(__file__), "wheels")
        for filename in os.listdir(wheels_path):
            if filename.endswith('.whl'):
                prop = context.scene.module_list.add()
                prop.name = filename
                prop.path = os.path.join(wheels_path, filename)
        return len(context.scene.module_list)
    
    def reload(self):
        """Reload Blender scripts after a command is completed."""
        bpy.ops.script.reload()
        bpy.context.scene.intalling = False
        global Message
        Message = "Reloaded Successfully"

class MI_Preferences(bpy.types.AddonPreferences):
    """Preferences UI for module management in Blender."""
    bl_idname = __package__

    def draw(self, context):
        layout = self.layout
        layout.enabled = not context.scene.intalling

        scene = context.scene
        row = layout.row()
        row.prop(scene, 'module_to_install', text="Module Name", icon="TEXT")
        row.operator(Module_installer.bl_idname, text="Install", icon="PLUS")

        row_ = layout.row()
        row = row_.row(align=True)
        row.operator(Wheels_lister.bl_idname, text="List", icon="ZOOM_IN").cmd = "LOAD"
        row.operator(Wheels_lister.bl_idname, text="Hide List", icon="ZOOM_OUT").cmd = "CLEAR"
        row = row.row(align=True)
        row.operator(Wheels_lister.bl_idname, text="Reload", icon="FILE_REFRESH").cmd = "RELOAD"
        row.operator(Wheels_lister.bl_idname, text="Uninstall All", icon="X").cmd = "UN_ALL"

        col_flow = layout.grid_flow(columns=1, align=True)
        for i, module in enumerate(context.scene.module_list):
            box = col_flow.box()
            row = box.row(align=True)
            # row.alignment = 'LEFT'
            row.label(text=module.name, icon="FILE")
            row.operator(Remove_Module.bl_idname, text="", icon="TRASH").index = i

        if Message != "":
            layout.separator()
            row = layout.row()
            row.label(text=Message, icon="INFO")

class Module_Prop(bpy.types.PropertyGroup):
    """Property group for storing installed module information."""
    name: bpy.props.StringProperty(description="Module name")
    path: bpy.props.StringProperty(description="Module file path")

def register():
    bpy.utils.register_class(Module_installer)
    bpy.utils.register_class(Remove_Module)
    bpy.utils.register_class(Wheels_lister)
    bpy.utils.register_class(MI_Preferences)
    bpy.utils.register_class(Module_Prop)

    bpy.types.Scene.module_to_install = bpy.props.StringProperty(
        name="Module",
        description="Enter the name of the module to install",
        default=""
    )
    bpy.types.Scene.module_list = bpy.props.CollectionProperty(type=Module_Prop)
    bpy.types.Scene.intalling = bpy.props.BoolProperty(name="intalling", default=False)

def unregister():
    bpy.utils.unregister_class(Module_installer)
    bpy.utils.unregister_class(Remove_Module)
    bpy.utils.unregister_class(Wheels_lister)
    bpy.utils.unregister_class(MI_Preferences)
    bpy.utils.unregister_class(Module_Prop)
    
    del bpy.types.Scene.module_to_install
    del bpy.types.Scene.module_list
    del bpy.types.Scene.intalling
