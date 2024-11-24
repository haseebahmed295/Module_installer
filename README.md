A simple add-on that allows the developers to install third part modules in blender using new extension python wheel feature .
# Features:
- Addon allows user to install module from add-on preferences
- Install in separate thread so no blender freezing
- Allows uninstallation of individual modules
- Auto Reload after after installation
- No admin privileges required 

# How to use:
1) Go to preferences of the addon 
2) Type the name of the module you want .And click install (Make sure you have internet access
3) You can check the installation process in console
4) After addon is done downloading modules it automatically reloads
5) You can check already installed modules by clicking on list button 
6) You can uninstall individual module if you want
# How it works:
This Addon use extension feature that allows the bundling wheel files of third party modules . It downloads the wheel file of required modules in addon dir and modifies the ```blender_manifest.toml file``` so these wheels files are loaded by blender
