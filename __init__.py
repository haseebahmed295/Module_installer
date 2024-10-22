import threading
import bpy
import subprocess
import os
import toml


class TU_image_Upscaler(bpy.types.Operator):
    """Upscales the active images in image editor"""
    bl_idname = "active_image.upscale"
    bl_label = "Texture Upscaler"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return not context.preferences.addons[__package__].preferences.runing
    def modal(self, context, event: bpy.types.Event) -> set:
        """
        Handles the timer events for the modal operator.

        This function is called every 0.01s while the operator is running.
        It checks if the upscaling thread is outputing any things and if so, it reports the output and resets the
        is_updated flag so that the operator can be exited.
        """
        prop = context.preferences.addons[__package__].preferences

        if event.type == 'TIMER':
        
            # Check if the upscaling thread is still running
            if not prop.runing:
                # The upscaling thread is not running, report the result
                if self._is_error:
                    self.report({"INFO"} , "Upscaling Failed 👎")
                else:
                    self.report({"INFO"} , "Upscaling Done 👍")
                # Return FINISHED to exit the operator
                return {'FINISHED'}

        # Return PASS_THROUGH to continue running the operator
        return {'PASS_THROUGH'}
    def execute(self, context):
        self._is_error = False
        toml_path = os.path.join(os.path.dirname(__file__), "blender_manifest.toml")
        wheels_path = os.path.join(os.path.dirname(__file__), "wheels")
        self.prop = context.preferences.addons[__package__].preferences
        module = context.scene.module_to_install.strip() 
        # Start the upscaling thread
        module_thread = threading.Thread(
            target=self.install_modules,
            args=(
                module,wheels_path,toml_path
            )
        )
        module_thread.start()
        self.prop.runing = True
        # Start the timer to check for updates
        self.report({"INFO"} , "Installing Modules... 😎")
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    def install_modules(self , module_name , wheels_path , toml_path):
        wheel_list = self.download_wheels(module_name , wheels_path)
        if len(wheel_list) == 0:
            self.prop.runing = False
        for wheel in wheel_list:
            self.modify_wheels_toml(toml_path , wheel)
        self.prop.runing = False
        return
    def modify_wheels_toml(self, file_path , module:str):
        try:
            # Read and parse the TOML file
            with open(file_path, 'r') as f:
                config = toml.load(f)
            
            # Modify the wheels list
            # Example: Add a new wheel
            if module not in config['wheels']:
                config['wheels'].append(f"./wheels/{module}")
            
            # Example: Remove a wheel
            # config['wheels'].remove("./wheels/six-1.16.0-py2.py3-none-any.whl")
            
            # Write the modified configuration back to the file
            with open(file_path, 'w') as f:
                toml.dump(config, f)
        except FileNotFoundError:
            print(f"The file {file_path} was not found.")
        except toml.TomlDecodeError:
            print(f"Failed to parse TOML file: {file_path}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

    def download_wheels(self,module_name, output_folder):
        
        try:
        
            # Download wheels
            download_command = ["pip", "download", module_name, f"--dest={output_folder}"]
            process = subprocess.Popen(download_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            for line in iter(process.stdout.readline, ""):
                print(line.strip())
            
            # Move downloaded wheels to output folder
            wheel_files = []
            for filename in os.listdir(output_folder):
                if filename.endswith('.whl'):
                    wheel_files.append(filename)

            return wheel_files
        
        except subprocess.CalledProcessError as e:
            print(f"Error executing pip command: {e}")
            self._is_error = True
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            self._is_error = True
        
        return []
    
class TU_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    runing: bpy.props.BoolProperty(
        name='Runing',
        default=False,
    )
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene, 'module_to_install')
        layout.operator(TU_image_Upscaler.bl_idname, icon='IMAGE')
            
def register():

    bpy.types.Scene.module_to_install = bpy.props.StringProperty(
        name="Module to Install",
        description="Module to install",
        default="",
    )

    bpy.utils.register_class(TU_Preferences)
    bpy.utils.register_class(TU_image_Upscaler)


def unregister():
    pass

if __name__ == "__main__":
    register()